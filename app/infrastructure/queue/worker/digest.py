"""Scheduled weekly review analytics digests."""

from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger
from app.core.notifications import send_html_email
from app.core.tenant_session import get_tenant_session
from app.infrastructure.persistence.models.economics import Company, Review

logger = get_logger(__name__)


async def enqueue_weekly_digests(ctx: dict[str, Any]) -> dict[str, int]:
    redis = ctx.get("redis")
    if redis is None:
        raise RuntimeError("ARQ Redis connection is unavailable")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT tenant_id FROM public.weekly_digest_recipients()")
        )
        recipients = result.all()

    period_end = datetime.now(timezone.utc)
    period_end_iso = period_end.isoformat()
    week_key = period_end.strftime("%G-W%V")
    queued = 0
    duplicates = 0
    for (tenant_id,) in recipients:
        job = await redis.enqueue_job(
            "send_company_weekly_digest",
            str(tenant_id),
            period_end_iso,
            _job_id=f"weekly-digest-{tenant_id}-{week_key}",
        )
        if job is None:
            duplicates += 1
        else:
            queued += 1
    logger.info(
        "weekly_digest_jobs_enqueued",
        recipient_count=len(recipients),
        queued=queued,
        duplicates=duplicates,
        week=week_key,
    )
    return {"recipients": len(recipients), "queued": queued, "duplicates": duplicates}


async def _period_metrics(
    session: AsyncSession,
    tenant_id: UUID,
    start: datetime,
    end: datetime,
) -> tuple[int, int, float | None, float | None, int]:
    result = await session.execute(
        select(
            func.count(Review.id),
            func.count(case((Review.is_analyzed.is_(True), Review.id))),
            func.avg(Review.rating),
            func.avg(Review.threat_level),
            func.count(case((Review.threat_level >= 4, Review.id))),
        ).where(
            Review.company_id == tenant_id,
            Review.created_at >= start,
            Review.created_at < end,
        )
    )
    total, analyzed, average_rating, average_threat, high_threat_count = result.one()
    return (
        int(total or 0),
        int(analyzed or 0),
        float(average_rating) if average_rating is not None else None,
        float(average_threat) if average_threat is not None else None,
        int(high_threat_count or 0),
    )


def _format_metric(value: float | None, precision: int = 1) -> str:
    return f"{value:.{precision}f}" if value is not None else "нет данных"


def _weekly_digest_html(
    company_name: str,
    start: datetime,
    end: datetime,
    current: tuple[int, int, float | None, float | None, int],
    previous: tuple[int, int, float | None, float | None, int],
) -> str:
    total, analyzed, average_rating, average_threat, high_threat_count = current
    previous_average_threat = previous[3]
    if average_threat is None or previous_average_threat is None:
        threat_trend = "недостаточно данных для сравнения"
    else:
        delta = average_threat - previous_average_threat
        direction = (
            "рост" if delta > 0 else "снижение" if delta < 0 else "без изменений"
        )
        threat_trend = f"{direction} на {abs(delta):.1f} балла"

    return f"""<!doctype html>
<html lang="ru">
  <body style="font-family:Arial,sans-serif;color:#1f2937">
    <h1>Еженедельный отчет — {escape(company_name)}</h1>
    <p>Период: {start:%d.%m.%Y} — {end:%d.%m.%Y}</p>
    <ul>
      <li>Получено отзывов: {total}</li>
      <li>Обработано: {analyzed}</li>
      <li>Средний рейтинг: {_format_metric(average_rating)}</li>
      <li>Средний уровень угроз: {_format_metric(average_threat)}</li>
      <li>Высоких угроз (уровень 4–5): {high_threat_count}</li>
      <li>Тренд угроз к предыдущей неделе: {escape(threat_trend)}</li>
    </ul>
  </body>
</html>"""


async def send_company_weekly_digest(
    ctx: dict[str, Any],
    tenant_id: str,
    period_end_iso: str,
) -> dict[str, str]:
    tenant_uuid = UUID(tenant_id)
    period_end = datetime.fromisoformat(period_end_iso)
    if period_end.tzinfo is None:
        raise ValueError("period_end_iso must include a timezone")
    period_start = period_end - timedelta(days=7)
    previous_start = period_start - timedelta(days=7)

    session: AsyncSession = await get_tenant_session(
        factory=AsyncSessionLocal,
        tenant_id=tenant_uuid,
    )
    try:
        company_result = await session.execute(
            select(Company.name, Company.notification_email).where(
                Company.id == tenant_uuid
            )
        )
        company = company_result.one_or_none()
        if company is None:
            raise ValueError("Company not found for weekly digest")
        company_name, recipient_email = company
        if not recipient_email:
            logger.warning(
                "weekly_digest_skipped_no_recipient",
                tenant_id=tenant_id,
            )
            return {"tenant_id": tenant_id, "status": "skipped_no_recipient"}

        current = await _period_metrics(session, tenant_uuid, period_start, period_end)
        previous = await _period_metrics(
            session, tenant_uuid, previous_start, period_start
        )
    finally:
        await session.close()

    html_content = _weekly_digest_html(
        company_name,
        period_start,
        period_end,
        current,
        previous,
    )
    await send_html_email(
        recipient_email,
        f"Еженедельный отчет SERM — {company_name}",
        html_content,
    )
    logger.info(
        "weekly_digest_sent",
        tenant_id=tenant_id,
        review_count=current[0],
        analyzed_count=current[1],
    )
    return {"tenant_id": tenant_id, "status": "sent"}
