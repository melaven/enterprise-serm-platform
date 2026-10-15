"""
Billing middleware для Zero Trust quota enforcement.
Проверяет квоты организации перед выполнением дорогих операций (AI, парсинг).
"""

from fastapi import HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from uuid import UUID

from app.core.database import get_db
from app.core.auth import get_current_tenant
from app.services.billing import QuotaService
from app.schemas.billing import QuotaStatus


async def get_tenant_db_for_quotas(
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> AsyncSession:
    """Вариант tenant-aware DB для квот с проверкой JWT сессии."""
    return db


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
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
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
    query = text("""
        SELECT o.is_active, o.requests_used, p.max_requests 
        FROM organization_quotas o
        JOIN billing_plans p ON o.plan_id = p.id
        WHERE o.org_id = :tenant_id
    """)
    
    result = await db.execute(query, {"tenant_id": tenant_id})
    quota = result.fetchone()

    if not quota:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Billing plan not found for this organization."
        )
        
    is_active, requests_used, max_requests = quota

    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Organization account is inactive. Please update billing."
        )

    if requests_used >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Quota Exceeded",
                "used": requests_used,
                "limit": max_requests
            }
        )
        
    return {"used": requests_used, "limit": max_requests}


async def increment_quota(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Инкрементирует счетчик использования квоты после успешного выполнения операции.
    
    ВАЖНО: Вызывать ТОЛЬКО после успешного выполнения дорогой операции.
    """
    query = text("""
        UPDATE organization_quotas 
        SET requests_used = requests_used + 1,
            updated_at = NOW()
        WHERE org_id = :tenant_id
    """)
    
    await db.execute(query, {"tenant_id": tenant_id})
    await db.commit()


async def consume_request(
    db: AsyncSession,
    tenant_id: UUID,
    amount: int = 1,
) -> dict[str, int]:
    """Atomically debit quota or return HTTP 402 when the plan limit is reached."""
    if amount < 1:
        raise ValueError("amount must be at least 1")

    query = text("""
        UPDATE organization_quotas o
        SET requests_used = o.requests_used + :amount,
            updated_at = NOW()
        FROM billing_plans p
        WHERE o.org_id = :tenant_id
          AND o.plan_id = p.id
          AND o.is_active = true
          AND o.requests_used + :amount <= p.max_requests
        RETURNING o.requests_used, p.max_requests
    """)

    result = await db.execute(
        query,
        {"tenant_id": tenant_id, "amount": amount},
    )
    updated_quota = result.fetchone()

    if updated_quota is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Quota Exceeded during execution",
                "message": "Лимит тарифа исчерпан.",
            },
        )

    await db.commit()
    return {"used": updated_quota[0], "limit": updated_quota[1]}
