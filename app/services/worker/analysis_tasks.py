import logging
from asyncio import Semaphore, gather
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.tenant_session import get_tenant_session
from app.models.economics import Review
from app.services.si_pipeline import SentimentIntelligencePipeline
from app.services.webhooks_sender import dispatch_review_analyzed_event

logger = logging.getLogger(__name__)
MAX_BATCH = 200


async def process_reviews_batch(
    ctx: dict[str, object], tenant_id: UUID, review_ids: list[UUID]
) -> dict[str, int]:
    unique_review_ids = list(
        dict.fromkeys(UUID(str(review_id)) for review_id in review_ids)
    )
    if len(unique_review_ids) > MAX_BATCH:
        raise ValueError(f"batch too large: {len(unique_review_ids)} > {MAX_BATCH}")
    if not unique_review_ids:
        return {"requested": 0, "found": 0, "analyzed": 0}

    tenant_uuid = UUID(str(tenant_id))
    session: AsyncSession = await get_tenant_session(
        factory=AsyncSessionLocal,
        tenant_id=tenant_uuid,
    )
    analyzed_reviews: list[dict[str, object]] = []
    try:
        analyzed_count = await SentimentIntelligencePipeline().process_batch(
            session, unique_review_ids
        )
        if analyzed_count:
            result = await session.execute(
                select(
                    Review.id,
                    Review.created_at,
                    Review.platform,
                    Review.rating,
                    Review.sentiment,
                    Review.threat_level,
                    Review.analysis_tags,
                    Review.suggested_reply,
                ).where(
                    Review.company_id == tenant_uuid,
                    Review.id.in_(unique_review_ids),
                    Review.is_analyzed.is_(True),
                )
            )
            analyzed_reviews = [
                {
                    "review_id": str(review_id),
                    "created_at": created_at.isoformat() if created_at else None,
                    "platform": platform,
                    "rating": rating,
                    "sentiment": sentiment,
                    "threat_level": threat_level,
                    "analysis_tags": analysis_tags,
                    "suggested_reply": suggested_reply,
                }
                for (
                    review_id,
                    created_at,
                    platform,
                    rating,
                    sentiment,
                    threat_level,
                    analysis_tags,
                    suggested_reply,
                ) in result.all()
            ]
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            logger.exception("Failed to roll back review analysis batch")
        raise
    finally:
        await session.close()

    if analyzed_reviews:
        semaphore = Semaphore(5)

        async def dispatch(review_data: dict[str, object]) -> None:
            async with semaphore:
                delivery = await dispatch_review_analyzed_event(
                    tenant_uuid,
                    review_data,
                )
            if delivery["failed"]:
                logger.warning(
                    "Some review webhooks could not be delivered",
                    extra={
                        "tenant_id": str(tenant_uuid),
                        "review_id": review_data["review_id"],
                        **delivery,
                    },
                )

        await gather(*(dispatch(review_data) for review_data in analyzed_reviews))

    logger.info(
        "Review analysis batch completed",
        extra={
            "tenant_id": str(tenant_uuid),
            "requested": len(unique_review_ids),
            "analyzed": analyzed_count,
        },
    )
    return {
        "requested": len(unique_review_ids),
        "found": analyzed_count,
        "analyzed": analyzed_count,
    }
