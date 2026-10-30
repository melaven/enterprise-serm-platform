from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.economics import (
    Platform,
    PlatformStatistic,
    Review,
)


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
) -> dict[str, Any]:
    stmt = (
        select(
            Review.sentiment,
            Review.is_critical,
            Review.ai_pending,
            func.count(Review.id),
        )
        .where(Review.company_id == tenant_id)
        .group_by(Review.sentiment, Review.is_critical, Review.ai_pending)
    )
    result = await db.execute(stmt)

    sentiment_counts = {
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "unclassified": 0,
    }
    critical_reviews = 0
    ai_pending = 0
    total_reviews = 0
    for sentiment, is_critical, is_ai_pending, count in result.all():
        total_reviews += count
        normalized_sentiment = sentiment.upper() if sentiment is not None else None
        if normalized_sentiment in {"POSITIVE", "NEUTRAL", "NEGATIVE"}:
            sentiment_counts[normalized_sentiment.lower()] += count
        else:
            sentiment_counts["unclassified"] += count
        if is_critical:
            critical_reviews += count
        if is_ai_pending:
            ai_pending += count

    now = datetime.now(timezone.utc)
    first_day = now.date() - timedelta(days=29)
    start = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    avg_rating = await db.scalar(
        select(func.avg(func.nullif(Review.rating, 0))).where(
            Review.company_id == tenant_id
        )
    )
    timeline_result = await db.execute(
        select(func.date(Review.created_at), func.count(Review.id))
        .where(
            Review.company_id == tenant_id,
            Review.created_at >= start,
        )
        .group_by(func.date(Review.created_at))
        .order_by(func.date(Review.created_at))
    )
    timeline_counts: dict[date, int] = {}
    for day, count in timeline_result.all():
        if isinstance(day, datetime):
            day = day.date()
        elif isinstance(day, str):
            day = date.fromisoformat(day)
        timeline_counts[day] = int(count)
    timeline = [
        {
            "date": first_day + timedelta(days=day_offset),
            "reviews": timeline_counts.get(first_day + timedelta(days=day_offset), 0),
        }
        for day_offset in range(30)
    ]

    return {
        "total_reviews": total_reviews,
        "average_rating": round(float(avg_rating), 2)
        if avg_rating is not None
        else None,
        "sentiment": {
            **sentiment_counts,
            "total": sum(sentiment_counts.values()),
        },
        "timeline": timeline,
        "critical_reviews": critical_reviews,
        "ai_pending": ai_pending,
        "period": {"date_from": first_day, "date_to": now.date()},
    }


async def get_reputation_statistics(
    db: AsyncSession,
    tenant_id: UUID,
    period_days: int,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=period_days)
    platform_result = await db.execute(
        select(
            Platform.id,
            Platform.name,
            func.count(Review.id),
            func.avg(func.nullif(Review.rating, 0)),
            func.sum(case((Review.created_at >= since, 1), else_=0)),
        )
        .outerjoin(
            Review,
            and_(
                Review.platform_id == Platform.id,
                Review.company_id == tenant_id,
            ),
        )
        .where(Platform.company_id == tenant_id)
        .group_by(Platform.id, Platform.name)
        .order_by(Platform.name)
    )
    platform_rows = platform_result.all()

    ranked_stats = (
        select(
            PlatformStatistic.platform_id.label("platform_id"),
            PlatformStatistic.average_rating.label("average_rating"),
            PlatformStatistic.rating_change.label("rating_change"),
            PlatformStatistic.review_count.label("review_count"),
            PlatformStatistic.recorded_at.label("recorded_at"),
            func.row_number()
            .over(
                partition_by=PlatformStatistic.platform_id,
                order_by=PlatformStatistic.recorded_at.desc(),
            )
            .label("position"),
        )
        .where(PlatformStatistic.company_id == tenant_id)
        .subquery()
    )
    stats_result = await db.execute(
        select(ranked_stats).where(ranked_stats.c.position == 1)
    )
    latest_stats = {row.platform_id: row for row in stats_result.all()}

    platform_aliases = {
        "googlemaps": "google",
        "google": "google",
        "2gis": "2gis",
        "2гис": "2gis",
        "yandex": "yandex",
        "яндекс": "yandex",
        "trustpilot": "trustpilot",
    }
    platforms = []
    for platform_id, name, review_count, live_average, new_count in platform_rows:
        latest = latest_stats.get(platform_id)
        platform_key = str(name).strip().lower().replace(" ", "")
        platforms.append(
            {
                "platform": platform_aliases.get(platform_key, "unknown"),
                "average_rating": (
                    float(latest.average_rating)
                    if latest is not None
                    else (
                        round(float(live_average), 2)
                        if live_average is not None
                        else None
                    )
                ),
                "rating_delta": (
                    float(latest.rating_change) if latest is not None else None
                ),
                "total_reviews": (
                    int(latest.review_count)
                    if latest is not None
                    else int(review_count)
                ),
                "new_reviews": int(new_count or 0),
            }
        )

    updated_at = max(
        (row.recorded_at for row in latest_stats.values()),
        default=now,
    )
    return {
        "period_days": period_days,
        "updated_at": updated_at,
        "platforms": platforms,
    }
