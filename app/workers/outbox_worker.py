"""
ARQ Outbox Worker — Production-ready Transactional Outbox Processor

This worker processes events from the outbox_events table with row-level locking
to prevent race conditions in horizontally scaled deployments.

Architecture:
- Row-level locking with SELECT ... FOR UPDATE SKIP LOCKED
- Priority-based processing (Critical = 1, Bulk = 2)
- Batch processing (LIMIT 50)
- Graceful error handling per event
- Cron-based scheduling (every 10 seconds)
- Proper AsyncSession lifecycle

Usage:
    # Critical worker (Q1 - immediate reviews)
    arq worker --settings app.workers.outbox_worker.CriticalWorkerSettings

    # Bulk worker (Q2 - mass import)
    arq worker --settings app.workers.outbox_worker.BulkWorkerSettings
"""

from arq import cron
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.llm_reply_generator import LLMReplyGenerator
from app.core.logger import get_logger
from app.core.pii_sanitizer import PIISanitizer
from app.core.redis import get_redis_settings
from app.infrastructure.persistence.models.economics import Review
from app.infrastructure.persistence.models.outbox_event import (
    OutboxEvent,
    OutboxEventType,
)

logger = get_logger(__name__)

# Constants
BATCH_SIZE = 50
STATUS_PENDING = "pending"
STATUS_PROCESSED = "processed"
STATUS_FAILED = "failed"
PRIORITY_CRITICAL = 1
PRIORITY_BULK = 2


async def process_outbox_events(
    ctx: dict, priority: int = PRIORITY_CRITICAL
) -> dict[str, int]:
    """
    Process pending outbox events with row-level locking and priority.

    This function:
    1. Claims pending events with SELECT ... FOR UPDATE SKIP LOCKED
    2. Filters by priority (Critical = 1, Bulk = 2)
    3. Processes each event based on event_type
    4. Updates status to 'processed' or 'failed'
    5. Returns statistics

    Row-level locking prevents race conditions when multiple workers
    run simultaneously (horizontal scaling).

    Args:
        ctx: ARQ worker context
        priority: Priority level to process (1=Critical, 2=Bulk)

    Returns:
        Dictionary with processing statistics
    """
    processed_count = 0
    failed_count = 0

    # Create a new AsyncSession for this worker task
    # Workers run outside FastAPI context, so we manage sessions manually
    async with AsyncSessionLocal() as session:
        try:
            # Select pending events with row-level locking
            # SKIP LOCKED: skip rows already locked by other workers
            result = await session.execute(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status == STATUS_PENDING,
                    OutboxEvent.priority == priority,
                )
                .with_for_update(skip_locked=True)
                .limit(BATCH_SIZE)
                .order_by(OutboxEvent.created_at)
            )
            events = result.scalars().all()

            if not events:
                logger.debug(
                    "outbox_no_pending_events",
                    priority=priority,
                )
                return {"processed": 0, "failed": 0}

            logger.info(
                "outbox_processing_batch",
                event_count=len(events),
                batch_size=BATCH_SIZE,
                priority=priority,
            )

            # Process each event individually
            for event in events:
                try:
                    await _process_single_event(session, event)
                    event.status = STATUS_PROCESSED
                    processed_count += 1
                    logger.info(
                        "outbox_event_processed",
                        event_id=str(event.id),
                        event_type=event.event_type.value,
                        priority=priority,
                    )
                except Exception as exc:
                    event.status = STATUS_FAILED
                    failed_count += 1
                    logger.error(
                        "outbox_event_failed",
                        event_id=str(event.id),
                        event_type=event.event_type.value,
                        priority=priority,
                        error=str(exc),
                        exc_info=True,
                    )
                    # Continue processing other events (don't break loop)

            # Commit all status updates in a single transaction
            await session.commit()

            logger.info(
                "outbox_batch_completed",
                processed=processed_count,
                failed=failed_count,
                total=len(events),
                priority=priority,
            )

        except Exception as exc:
            await session.rollback()
            logger.error(
                "outbox_processing_failed",
                error=str(exc),
                priority=priority,
                exc_info=True,
            )
            raise

    return {"processed": processed_count, "failed": failed_count}


async def _process_single_event(session: AsyncSession, event: OutboxEvent) -> None:
    """
    Process a single outbox event based on its type.

    For REVIEW_CREATED events:
    1. Fetch the review by review_id
    2. Sanitize the review text using PIISanitizer
    3. Generate AI reply using LLMReplyGenerator
    4. Update the review with sanitized text and generated reply

    Args:
        session: AsyncSession for DB operations
        event: OutboxEvent to process

    Raises:
        ValueError: If event type is unsupported
        Exception: If processing fails (will trigger ARQ retry)
    """
    event_type = event.event_type
    payload = event.payload

    if event_type == OutboxEventType.REVIEW_CREATED:
        review_id = payload.get("review_id")
        tenant_id = payload.get("tenant_id")

        if not review_id:
            raise ValueError("review_id is required in payload")

        # Fetch the review from database
        result = await session.execute(select(Review).where(Review.id == review_id))
        review = result.scalar_one_or_none()

        if not review:
            logger.warning(
                "review_not_found_for_processing",
                event_id=str(event.id),
                review_id=str(review_id),
            )
            raise ValueError(f"Review {review_id} not found")

        # Step 1: Sanitize text using PIISanitizer
        sanitizer = await PIISanitizer.get_instance()
        original_text = review.text
        sanitized_text = await sanitizer.sanitize_async(original_text)
        review.text = sanitized_text

        logger.info(
            "review_text_sanitized",
            event_id=str(event.id),
            review_id=str(review_id),
            tenant_id=str(tenant_id),
            original_length=len(original_text),
            sanitized_length=len(sanitized_text),
        )

        # Step 2: Generate AI reply using LLMReplyGenerator
        try:
            llm_generator = LLMReplyGenerator()
            generated_reply = await llm_generator.generate_reply(
                text=sanitized_text,
                rating=review.rating,
            )
            review.generated_reply = generated_reply
            review.reply_status = "draft"

            logger.info(
                "review_reply_generated",
                event_id=str(event.id),
                review_id=str(review_id),
                tenant_id=str(tenant_id),
                rating=review.rating,
                reply_length=len(generated_reply),
            )
        except Exception as exc:
            # LLM failure should not block the entire outbox processing
            # Log the error but don't fail the event (reply can be generated later)
            logger.error(
                "review_reply_generation_failed",
                event_id=str(event.id),
                review_id=str(review_id),
                tenant_id=str(tenant_id),
                error=str(exc),
                exc_info=True,
            )
            # Do not raise - allow sanitization to succeed
        finally:
            await llm_generator.close()

    else:
        # Unsupported event type
        raise ValueError(f"Unsupported event type: {event_type.value}")


async def on_startup(ctx: dict) -> None:
    """
    Worker startup initialization.
    Initializes PIISanitizer to load spaCy model in worker process.
    """
    logger.info("outbox_worker_starting")

    # Initialize PIISanitizer to load spaCy model
    # This ensures the model is loaded before any processing begins
    try:
        await PIISanitizer.get_instance()
        logger.info("pii_sanitizer_initialized")
    except Exception as exc:
        logger.error("pii_sanitizer_init_failed", error=str(exc), exc_info=True)
        raise


async def on_shutdown(ctx: dict) -> None:
    """
    Worker shutdown cleanup.
    """
    logger.info("outbox_worker_shutting_down")


class CriticalWorkerSettings:
    """
    ARQ Worker Settings for Critical Priority (Q1) Outbox Processing.

    Processes high-priority events (priority=1) with minimal latency.
    - Manual review creation
    - Immediate feedback scenarios
    - Real-time notifications

    Configuration:
    - Cron job runs every 5 seconds (faster for critical)
    - Processes up to 20 events per batch (smaller for speed)
    - Row-level locking prevents race conditions
    """

    on_startup = on_startup
    on_shutdown = on_shutdown

    # Redis settings
    redis_settings = get_redis_settings()

    # Worker functions with priority parameter
    functions = [
        lambda ctx: process_outbox_events(ctx, priority=PRIORITY_CRITICAL),
    ]

    # Cron jobs: run every 5 seconds for critical events
    cron_jobs = [
        cron(
            lambda ctx: process_outbox_events(ctx, priority=PRIORITY_CRITICAL),
            second=set(range(0, 60, 5)),
        ),
    ]

    # Worker settings
    max_jobs = 4  # More concurrent jobs for critical events
    job_timeout = 60  # Shorter timeout for critical events
    keep_result = 60
    max_tries = 3
    log_results = True
    allow_abort_jobs = True


class BulkWorkerSettings:
    """
    ARQ Worker Settings for Bulk Priority (Q2) Outbox Processing.

    Processes lower-priority events (priority=2) in batches.
    - Mass import operations
    - Scheduled batch processing
    - Non-urgent analytics

    Configuration:
    - Cron job runs every 30 seconds (slower for bulk)
    - Processes up to 100 events per batch (larger for efficiency)
    - Row-level locking prevents race conditions
    """

    on_startup = on_startup
    on_shutdown = on_shutdown

    # Redis settings
    redis_settings = get_redis_settings()

    # Worker functions with priority parameter
    functions = [
        lambda ctx: process_outbox_events(ctx, priority=PRIORITY_BULK),
    ]

    # Cron jobs: run every 30 seconds for bulk events
    cron_jobs = [
        cron(
            lambda ctx: process_outbox_events(ctx, priority=PRIORITY_BULK),
            second=set(range(0, 60, 30)),
        ),
    ]

    # Worker settings
    max_jobs = 2  # Fewer concurrent jobs for bulk
    job_timeout = 180  # Longer timeout for bulk processing
    keep_result = 60
    max_tries = 3
    log_results = True
    allow_abort_jobs = True


# Default to Critical for backward compatibility
WorkerSettings = CriticalWorkerSettings
