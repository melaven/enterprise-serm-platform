"""
ARQ Outbox Worker — Production-ready Transactional Outbox Processor

This worker processes events from the outbox_events table with row-level locking
to prevent race conditions in horizontally scaled deployments.

Architecture:
- Row-level locking with SELECT ... FOR UPDATE SKIP LOCKED
- Batch processing (LIMIT 50)
- Graceful error handling per event
- Cron-based scheduling (every 10 seconds)
- Proper AsyncSession lifecycle

Usage:
    arq worker --settings app.workers.outbox_worker.WorkerSettings
"""

from datetime import datetime, timezone
from uuid import UUID

from arq import cron
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger
from app.core.redis import get_redis_settings
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


async def process_outbox_events(ctx: dict) -> dict[str, int]:
    """
    Process pending outbox events with row-level locking.

    This function:
    1. Claims pending events with SELECT ... FOR UPDATE SKIP LOCKED
    2. Processes each event based on event_type
    3. Updates status to 'processed' or 'failed'
    4. Returns statistics

    Row-level locking prevents race conditions when multiple workers
    run simultaneously (horizontal scaling).

    Args:
        ctx: ARQ worker context

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
                .where(OutboxEvent.status == STATUS_PENDING)
                .with_for_update(skip_locked=True)
                .limit(BATCH_SIZE)
                .order_by(OutboxEvent.created_at)
            )
            events = result.scalars().all()

            if not events:
                logger.debug("outbox_no_pending_events")
                return {"processed": 0, "failed": 0}

            logger.info(
                "outbox_processing_batch",
                event_count=len(events),
                batch_size=BATCH_SIZE,
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
                    )
                except Exception as exc:
                    event.status = STATUS_FAILED
                    failed_count += 1
                    logger.error(
                        "outbox_event_failed",
                        event_id=str(event.id),
                        event_type=event.event_type.value,
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
            )

        except Exception as exc:
            await session.rollback()
            logger.error(
                "outbox_processing_failed",
                error=str(exc),
                exc_info=True,
            )
            raise

    return {"processed": processed_count, "failed": failed_count}


async def _process_single_event(session: AsyncSession, event: OutboxEvent) -> None:
    """
    Process a single outbox event based on its type.

    Args:
        session: AsyncSession for DB operations
        event: OutboxEvent to process

    Raises:
        ValueError: If event type is unsupported
        Exception: If processing fails
    """
    event_type = event.event_type
    payload = event.payload

    if event_type == OutboxEventType.REVIEW_CREATED:
        # Simulate processing: log the event
        # In production, this would trigger actual business logic
        logger.info(
            "review_created_event",
            event_id=str(event.id),
            review_id=payload.get("review_id"),
            tenant_id=payload.get("tenant_id"),
            payload=payload,
        )
        # Example: could trigger notification, webhook, etc.
        # await send_notification(payload)
    else:
        # Unsupported event type
        raise ValueError(f"Unsupported event type: {event_type.value}")


async def on_startup(ctx: dict) -> None:
    """
    Worker startup initialization.
    """
    logger.info("outbox_worker_starting")


async def on_shutdown(ctx: dict) -> None:
    """
    Worker shutdown cleanup.
    """
    logger.info("outbox_worker_shutting_down")


class WorkerSettings:
    """
    ARQ Worker Settings for Outbox Processing.

    Configuration:
    - Cron job runs every 10 seconds
    - Processes up to 50 events per batch
    - Row-level locking prevents race conditions
    """

    on_startup = on_startup
    on_shutdown = on_shutdown

    # Redis settings
    redis_settings = get_redis_settings()

    # Worker functions
    functions = [process_outbox_events]

    # Cron jobs: run every 10 seconds
    cron_jobs = [
        cron(process_outbox_events, second=set(range(0, 60, 10))),
    ]

    # Database settings (inherited from app config)
    # Note: Workers use AsyncSessionLocal directly

    # Worker settings
    max_jobs = 1  # Only one outbox processing job at a time
    job_timeout = 60  # 60 seconds timeout per batch
    keep_result = 60  # Keep results for 60 seconds
    max_tries = 3  # Retry failed batches up to 3 times
    log_results = True
    allow_abort_jobs = True
