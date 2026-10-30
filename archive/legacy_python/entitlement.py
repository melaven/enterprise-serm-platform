"""Проверка подписки и квоты перед запуском парсинга: HTTP 402 при неоплате или исчерпании лимита.

Это быстрый отказ. Жёсткую гарантию даёт атомарный резерв app.consume_quota в воркере
(между проверкой и резервом квоту может забрать параллельный запрос).
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentAuth
from app.db.session import TenantSession

_ENT = text(
    "SELECT plan_code, status, reviews_parsed_used AS used, reviews_parsed_limit AS lim, reset_date "
    "FROM app.get_entitlement(CAST(:t AS uuid))"
)


def _payment_required(
    code: str, message: str, plan: str, used: int, limit: int, reset: object
) -> HTTPException:
    return HTTPException(
        status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": code,
            "message": message,
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
    """Правила:
    * free: статус не важен (после отмены Pro подписка остаётся 'canceled' на бесплатном плане), работает лимит;
    * платный план: нужен status='active'; past_due -> 402 payment_past_due; canceled -> 402 subscription_inactive;
    * used >= limit -> 402 quota_exceeded.
    """
    row = (await session.execute(_ENT, {"t": str(company_id)})).mappings().one_or_none()
    if row is None:  # нет подписки/квоты = ошибка конфигурации: закрываемся
        raise _payment_required(
            "subscription_inactive", "Подписка не найдена.", "free", 0, 0, None
        )
    plan, sub_status = str(row["plan_code"]), str(row["status"])
    used, limit, reset = int(row["used"]), int(row["lim"]), row["reset_date"]

    if plan != "free" and sub_status != "active":
        if sub_status == "past_due":
            raise _payment_required(
                "payment_past_due",
                "Платёж не прошёл. Обновите способ оплаты.",
                plan,
                used,
                limit,
                reset,
            )
        raise _payment_required(
            "subscription_inactive", "Подписка неактивна.", plan, used, limit, reset
        )
    if used >= limit:
        raise _payment_required(
            "quota_exceeded",
            "Лимит отзывов исчерпан. Повысьте тариф или дождитесь нового периода.",
            plan,
            used,
            limit,
            reset,
        )


async def verify_subscription_and_quota(
    auth: CurrentAuth, session: TenantSession
) -> None:
    """FastAPI-dependency: 402 до любой другой работы эндпоинта (Redis не трогаем).

    Использование: @router.post(..., dependencies=[Depends(verify_subscription_and_quota)]).
    Сессия та же, что у эндпоинта (кэш зависимостей), RLS-контекст уже выставлен.
    """
    await enforce_reviews_quota(session, auth.company_id)


require_reviews_quota = (
    verify_subscription_and_quota  # обратная совместимость с routers/reviews.py
)
