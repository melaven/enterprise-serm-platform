"""Проверка тарифа и квоты перед запуском парсинга: HTTP 402 при исчерпании лимита.

Это быстрый отказ. Жёсткую гарантию даёт атомарный резерв app.consume_quota в воркере
(между проверкой и резервом квоту может забрать параллельный запрос).
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ENT = text(
    "SELECT plan_code, status, reviews_parsed_used AS used, reviews_parsed_limit AS lim, reset_date "
    "FROM app.get_entitlement(CAST(:t AS uuid))"
)


def _payment_required(plan: str, used: int, limit: int, reset: object) -> HTTPException:
    return HTTPException(
        status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": "quota_exceeded",
            "message": "Лимит отзывов исчерпан. Повысьте тариф или дождитесь нового периода.",
            "requests_used": used,
            "max_requests": limit,
            "reset_date": reset.isoformat()
            if reset is not None and hasattr(reset, "isoformat")
            else None,
            "plan": plan,
            "upgrade_available": plan == "free",
        },
    )


async def enforce_reviews_quota(session: AsyncSession, company_id: UUID) -> None:
    row = (await session.execute(_ENT, {"t": str(company_id)})).mappings().one_or_none()
    if row is None:  # нет подписки/квоты = ошибка конфигурации: закрываемся
        raise _payment_required("free", 0, 0, None)
    used, limit = int(row["used"]), int(row["lim"])
    if used >= limit:
        raise _payment_required(str(row["plan_code"]), used, limit, row["reset_date"])
