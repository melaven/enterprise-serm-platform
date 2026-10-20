"""
ARQ Worker for background processing of reviews
Async Redis queue with RLS-aware database sessions
"""

import os
from uuid import UUID

import arq
from arq import WorkerSettings
from arq.connections import RedisSettings

from app.core.database import AsyncSessionLocal
from app.core.logger import generate_correlation_id, get_logger, set_correlation_id
from app.core.tenant_session import get_tenant_session

logger = get_logger("worker")


async def process_reviews_batch(
    ctx: arq.Context, tenant_id: str, review_ids: list[str]
) -> dict:
    """
    Process a batch of reviews with RLS isolation

    Args:
        ctx: ARQ context
        tenant_id: Tenant ID for RLS isolation
        review_ids: List of review IDs to process

    Returns:
        Dict with processing results
    """
    # Set correlation ID for tracing
    correlation_id = generate_correlation_id()
    set_correlation_id(correlation_id)

    logger.info(
        "worker.batch.started",
        tenant_id=tenant_id,
        review_count=len(review_ids),
        review_ids=review_ids,
        correlation_id=correlation_id,
    )

    try:
        # Convert tenant_id to UUID
        tenant_uuid = UUID(tenant_id)

        # Create RLS-aware session
        session = await get_tenant_session(
            factory=AsyncSessionLocal,
            tenant_id=tenant_uuid,
            user_id=None,  # Worker has no user context
        )

        # TODO: Implement actual review processing logic
        # This is a placeholder for the actual business logic
        # Example: sentiment analysis, classification, etc.

        # Placeholder: simulate processing
        processed_count = len(review_ids)

        logger.info(
            "worker.batch.completed",
            tenant_id=tenant_id,
            processed_count=processed_count,
            correlation_id=correlation_id,
        )

        return {
            "success": True,
            "processed_count": processed_count,
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
        }

    except ValueError as e:
        logger.error(
            "worker.batch.failed",
            tenant_id=tenant_id,
            error=str(e),
            error_type="invalid_uuid",
            correlation_id=correlation_id,
        )
        return {
            "success": False,
            "error": "Invalid tenant_id format",
            "correlation_id": correlation_id,
        }

    except Exception as e:
        logger.error(
            "worker.batch.failed",
            tenant_id=tenant_id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )
        return {"success": False, "error": str(e), "correlation_id": correlation_id}

    finally:
        # Ensure session is closed
        try:
            await session.close()
        except Exception:
            pass


async def worker_startup(_ctx):
    logger.info("worker.started")


async def worker_shutdown(_ctx):
    logger.info("worker.shutdown")


class WorkerSettings(WorkerSettings):
    """
    ARQ Worker configuration with Redis connection
    """

    # Redis connection from environment variable
    redis_settings = RedisSettings.from_dsn(
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # Register worker functions
    functions = [process_reviews_batch]

    # Worker settings
    on_startup = worker_startup
    on_shutdown = worker_shutdown

    # Job settings
    max_jobs = 10  # Max concurrent jobs per worker
    job_timeout = 300  # 5 minutes timeout per job

    # Retry settings
    retry_jobs = True
    max_retries = 3
