"""
Billing middleware для Zero Trust quota enforcement.
Проверяет квоты организации перед выполнением дорогих операций (AI, парсинг).
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.billing import QuotaStatus
from app.application.billing.service import QuotaService
from app.core.auth import get_current_tenant
from app.core.dependencies import get_tenant_db

get_tenant_db_for_quotas = get_tenant_db


async def get_quota_service(
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db_for_quotas),
) -> QuotaService:
    """Сервис квот привязан к текущему tenant_id из JWT."""
    return QuotaService(db)


async def get_quota_status(
    tenant_id: UUID = Depends(get_current_tenant),
    quota_service: QuotaService = Depends(get_quota_service),
) -> QuotaStatus:
    """Возвращает квоты только для текущего tenant, игнорируя любые клиентские значения."""
    return await quota_service.get_status(tenant_id)


async def check_quota(
    db: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """
    Middleware для проверки квоты (Zero Trust).
    Ни один запрос не пройдет дальше, если лимит исчерпан.

    Raises:
        HTTPException 403: Если billing plan не найден для организации
        HTTPException 402: Если аккаунт неактивен или квота исчерпана

    Returns:
        dict: {"used": int, "limit": int} - текущее использование квоты
    """

    # Атомарный запрос: проверяем активность и лимиты одним ударом
    query = text(
        """
        SELECT is_active, reviews_parsed_used, reviews_parsed_limit
        FROM public.tenant_quotas
        WHERE tenant_id = :tenant_id
        """
    )

    result = await db.execute(query, {"tenant_id": tenant_id})
    quota = result.fetchone()

    if not quota:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Billing plan not found for this organization.",
        )

    is_active, requests_used, max_requests = quota

    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Organization account is inactive. Please update billing.",
        )

    if requests_used >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Quota Exceeded",
                "used": requests_used,
                "limit": max_requests,
            },
        )

    return {"used": requests_used, "limit": max_requests}


async def increment_quota(
    db: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """
    Инкрементирует счетчик использования квоты после успешного выполнения операции.

    ВАЖНО: Вызывать ТОЛЬКО после успешного выполнения дорогой операции.
    """
    if not await QuotaService(db).consume_reviews(tenant_id, 1):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Review quota exceeded.",
        )
    await db.commit()


async def consume_request(
    db: AsyncSession,
    tenant_id: UUID,
    amount: int = 1,
) -> dict[str, int]:
    """Atomically debit quota or return HTTP 402 when the plan limit is reached."""
    if amount < 1:
        raise ValueError("amount must be at least 1")

    quota_service = QuotaService(db)
    if not await quota_service.consume_reviews(tenant_id, amount):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Quota Exceeded during execution",
                "message": "Лимит тарифа исчерпан.",
            },
        )

    quota_status = await quota_service.get_status(tenant_id)
    await db.commit()
    return {
        "used": quota_status.usage.used_reviews,
        "limit": quota_status.limits.max_reviews,
    }
