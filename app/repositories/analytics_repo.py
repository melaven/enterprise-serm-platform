from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.economics import Review


async def get_reviews_list(
    db: AsyncSession,
    tenant_id: UUID,
    limit: int,
    offset: int,
) -> list[Review]:
    stmt = (
        select(Review)
        .where(Review.company_id == tenant_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_dashboard_metrics(
    db: AsyncSession,
    tenant_id: UUID,
) -> dict[str, int]:
    stmt = (
        select(Review.sentiment, Review.is_critical, func.count(Review.id))
        .where(Review.company_id == tenant_id)
        .group_by(Review.sentiment, Review.is_critical)
    )
    result = await db.execute(stmt)

    metrics = {
        "total_reviews": 0,
        "positive_reviews": 0,
        "negative_reviews": 0,
        "critical_reviews": 0,
    }
    for sentiment, is_critical, count in result.all():
        metrics["total_reviews"] += count
        normalized_sentiment = sentiment.upper() if sentiment is not None else None
        if normalized_sentiment == "POSITIVE":
            metrics["positive_reviews"] += count
        elif normalized_sentiment == "NEGATIVE":
            metrics["negative_reviews"] += count
        if is_critical:
            metrics["critical_reviews"] += count

    return metrics