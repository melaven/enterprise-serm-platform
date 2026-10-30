"""API endpoints для управления квотами и биллингом.

Предоставляет эндпоинты для просмотра статуса квот, обновления лимитов (admin).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas.auth import JWTPayload
from app.api.schemas.billing import QuotaStatus, QuotaUpdateLimits
from app.application.billing.service import QuotaNotFoundError, QuotaService
from app.core.auth import get_current_tenant, get_jwt_payload
from app.core.billing_deps import get_quota_service, get_quota_status

router = APIRouter(prefix="/api/v1/quotas", tags=["Quotas & Billing"])


def _require_quota_admin(payload: JWTPayload) -> None:
    if payload.company_role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only company owners and admins can update quota limits.",
        )


@router.get(
    "/status",
    response_model=QuotaStatus,
    summary="Получить статус квот текущего tenant'а",
    description="""
    Возвращает текущее состояние квот:
    - Лимиты (max_llm_tokens, max_reviews)
    - Использование (used_llm_tokens, used_reviews, reserved_llm_tokens)
    - Доступные ресурсы (вычисляемые свойства)
    - Процент использования
    """,
)
async def get_my_quota_status(
    quota_status: QuotaStatus = Depends(get_quota_status),
) -> QuotaStatus:
    """Получить статус квот для текущего tenant'а."""
    return quota_status


@router.get(
    "/status/{tenant_id}",
    response_model=QuotaStatus,
    summary="Получить статус квот для конкретного tenant'а (admin)",
    description="Только для администраторов. Позволяет просматривать квоты других tenant'ов.",
)
async def get_tenant_quota_status(
    requested_tenant_id: UUID,
    current_tenant: UUID = Depends(get_current_tenant),
    quota_service: QuotaService = Depends(get_quota_service),
) -> QuotaStatus:
    """Проверяет, что клиент запрашивает только собственный tenant_id из JWT."""
    if requested_tenant_id != current_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch: JWT tenant and requested tenant must match.",
        )

    try:
        return await quota_service.get_status(current_tenant)
    except QuotaNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quota not found for tenant {current_tenant}",
        ) from e


@router.patch(
    "/limits",
    response_model=QuotaStatus,
    summary="Обновить лимиты квот текущего tenant'а (admin)",
    description="""
    Обновляет лимиты квот для текущего tenant'а.
    Можно обновить как токены, так и отзывы, или только одно значение.
    """,
)
async def update_my_quota_limits(
    limits: QuotaUpdateLimits,
    current_tenant: UUID = Depends(get_current_tenant),
    payload: JWTPayload = Depends(get_jwt_payload),
    quota_service: QuotaService = Depends(get_quota_service),
) -> QuotaStatus:
    """Обновить лимиты квот только для текущего tenant из JWT."""
    _require_quota_admin(payload)

    try:
        return await quota_service.update_limits(
            current_tenant,
            actor_id=payload.sub,
            max_llm_tokens=limits.max_llm_tokens,
            max_reviews=limits.max_reviews,
        )
    except QuotaNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quota not found for tenant {current_tenant}",
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/limits/{tenant_id}",
    response_model=QuotaStatus,
    summary="Обновить лимиты квот для конкретного tenant'а (super admin)",
    description="Только для супер-администраторов. Позволяет изменять квоты других tenant'ов.",
)
async def update_tenant_quota_limits(
    requested_tenant_id: UUID,
    limits: QuotaUpdateLimits,
    current_tenant: UUID = Depends(get_current_tenant),
    payload: JWTPayload = Depends(get_jwt_payload),
    quota_service: QuotaService = Depends(get_quota_service),
) -> QuotaStatus:
    """Запрещает менять чужой tenant, даже если он передан в пути."""
    if requested_tenant_id != current_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch: JWT tenant and requested tenant must match.",
        )
    _require_quota_admin(payload)

    try:
        return await quota_service.update_limits(
            current_tenant,
            actor_id=payload.sub,
            max_llm_tokens=limits.max_llm_tokens,
            max_reviews=limits.max_reviews,
        )
    except QuotaNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quota not found for tenant {current_tenant}",
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Экспорт роутера
__all__ = ["router"]
