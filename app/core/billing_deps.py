"""Dependency Injection для биллинга и квот.

Предоставляет зависимости FastAPI для интеграции QuotaService в роутеры,
включая проверку квот перед выполнением операций и возврат HTTP 402 при превышении.
"""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import get_current_tenant
from ..dependencies import get_tenant_db
from ..schemas.billing import QuotaCheck, QuotaExceededError, QuotaStatus
from ..services.billing import QuotaNotFoundError, QuotaService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def get_quota_service(
    db: AsyncSession = Depends(get_tenant_db),
) -> QuotaService:
    """Фабрика для QuotaService с tenant-aware сессией.

    Args:
        db: AsyncSession с RLS контекстом

    Returns:
        QuotaService для управления квотами
    """
    return QuotaService(db)


async def get_quota_status(
    tenant_id: UUID = Depends(get_current_tenant),
    quota_service: QuotaService = Depends(get_quota_service),
) -> QuotaStatus:
    """Получить текущий статус квот для tenant'а.

    Args:
        tenant_id: UUID компании из JWT
        quota_service: QuotaService для работы с квотами

    Returns:
        QuotaStatus с лимитами и использованием

    Raises:
        HTTPException 404: Если квота не найдена (не инициализирована)
    """
    try:
        return await quota_service.get_status(tenant_id)
    except QuotaNotFoundError as e:
        logger.error(
            "quota_not_found",
            tenant_id=str(tenant_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quota not found for tenant {tenant_id}",
        ) from e


def check_quota(
    *,
    tokens: int = 0,
    reviews: int = 0,
) -> "Depends":  # type: ignore[valid-type]
    """Dependency для проверки квоты перед выполнением операции.

    Проверяет доступность запрошенных ресурсов и возвращает HTTP 402 Payment Required
    если квота превышена. Использовать как зависимость в роутерах.

    Args:
        tokens: Количество токенов, необходимых для операции (оценка)
        reviews: Количество отзывов, которые будут обработаны

    Returns:
        QuotaCheck с результатом проверки (если available=True)

    Raises:
        HTTPException 402: Если квота превышена

    Example:
        @router.post("/reviews/parse")
        async def parse_reviews(
            quota: QuotaCheck = Depends(check_quota(tokens=5000, reviews=10)),
            ...
        ):
            # Квота проверена, можно выполнять операцию
            ...
    """

    async def _check_quota(
        tenant_id: UUID = Depends(get_current_tenant),
        quota_service: QuotaService = Depends(get_quota_service),
    ) -> QuotaCheck:
        """Внутренняя функция проверки квоты."""
        try:
            quota_check = await quota_service.check_quota(
                tenant_id,
                tokens=tokens,
                reviews=reviews,
            )

            if not quota_check.available:
                # Получаем полный статус квот для деталей ошибки
                quota_status = await quota_service.get_status(tenant_id)

                error_response = QuotaExceededError(
                    message=quota_check.reason or "Quota exceeded",
                    quota_status=quota_status,
                    requested={
                        "tokens": tokens,
                        "reviews": reviews,
                    },
                )

                logger.warning(
                    "quota_exceeded",
                    tenant_id=str(tenant_id),
                    tokens_requested=tokens,
                    reviews_requested=reviews,
                    tokens_available=quota_check.tokens_available,
                    reviews_available=quota_check.reviews_available,
                    reason=quota_check.reason,
                )

                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=error_response.model_dump(),
                )

            logger.info(
                "quota_check_passed",
                tenant_id=str(tenant_id),
                tokens_requested=tokens,
                reviews_requested=reviews,
                tokens_available=quota_check.tokens_available,
                reviews_available=quota_check.reviews_available,
            )

            return quota_check

        except QuotaNotFoundError as e:
            logger.error(
                "quota_not_found_during_check",
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quota not initialized for tenant {tenant_id}",
            ) from e

    return Depends(_check_quota)


async def require_quota_available(
    tenant_id: UUID = Depends(get_current_tenant),
    quota_service: QuotaService = Depends(get_quota_service),
) -> QuotaStatus:
    """Dependency для проверки, что у tenant'а есть хоть какие-то доступные ресурсы.

    Полезно для общих проверок перед выполнением любых операций.

    Args:
        tenant_id: UUID компании из JWT
        quota_service: QuotaService для работы с квотами

    Returns:
        QuotaStatus если есть доступные ресурсы

    Raises:
        HTTPException 402: Если все квоты исчерпаны
        HTTPException 404: Если квота не найдена
    """
    try:
        quota_status = await quota_service.get_status(tenant_id)

        # Проверяем, что есть хоть что-то доступное
        if quota_status.tokens_available <= 0 and quota_status.reviews_available <= 0:
            error_response = QuotaExceededError(
                message="All quotas exhausted",
                quota_status=quota_status,
                requested={"tokens": 0, "reviews": 0},
            )

            logger.warning(
                "all_quotas_exhausted",
                tenant_id=str(tenant_id),
                tokens_used=quota_status.usage.used_llm_tokens,
                reviews_used=quota_status.usage.used_reviews,
            )

            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=error_response.model_dump(),
            )

        return quota_status

    except QuotaNotFoundError as e:
        logger.error(
            "quota_not_found_during_require",
            tenant_id=str(tenant_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quota not initialized for tenant {tenant_id}",
        ) from e


# Экспорт для удобного импорта
__all__ = [
    "get_quota_service",
    "get_quota_status",
    "check_quota",
    "require_quota_available",
]
