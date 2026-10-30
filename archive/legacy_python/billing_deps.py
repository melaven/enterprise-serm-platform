"""Проверка квоты организации перед тяжёлыми эндпоинтами (FastAPI Dependency).

Предполагаемая схема (см. migrations/009_billing_seed.sql):

    organization_quotas(organization_id, plan_id, requests_used, max_requests, is_active)

Использование::

    @router.post("/parsers/start", dependencies=[Depends(check_quota)])
    async def start_parsing(...): ...

    # или с доступом к снимку квоты:
    async def handler(quota: Annotated[QuotaSnapshot, Depends(check_quota)]): ...

`check_quota` — быстрый отказ (read-only). Между проверкой и работой счётчик
может вырасти, поэтому реальное списание делайте атомарно через `consume_request`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, Final

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentTenant
from app.core.auth_session import TenantSession

logger: Final = logging.getLogger(__name__)

_SELECT_QUOTA: Final = text(
    """
    SELECT is_active, requests_used, max_requests
    FROM organization_quotas
    WHERE organization_id = :org_id
    """
)

# Атомарное списание: условие лимита проверяется в самом UPDATE,
# поэтому две параллельные задачи не перешагнут max_requests.
_CONSUME: Final = text(
    """
    UPDATE organization_quotas
    SET requests_used = requests_used + :amount
    WHERE organization_id = :org_id
      AND is_active
      AND requests_used + :amount <= max_requests
    RETURNING is_active, requests_used, max_requests
    """
)


class QuotaErrorCode(StrEnum):
    NO_BILLING_PLAN = "no_billing_plan"
    SUBSCRIPTION_INACTIVE = "subscription_inactive"
    QUOTA_EXCEEDED = "quota_exceeded"
    BILLING_UNAVAILABLE = "billing_unavailable"


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    organization_id: str
    requests_used: int
    max_requests: int

    @property
    def remaining(self) -> int:
        return max(self.max_requests - self.requests_used, 0)


def _error(
    http_status: int, code: QuotaErrorCode, message: str, **extra: Any
) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"code": code.value, "message": message, **extra},
    )


async def _load_quota(session: AsyncSession, org_id: str) -> QuotaSnapshot:
    try:
        row = (
            (await session.execute(_SELECT_QUOTA, {"org_id": org_id}))
            .mappings()
            .first()
        )
    except SQLAlchemyError as exc:
        logger.exception(
            "billing: quota lookup failed", extra={"organization_id": org_id}
        )
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            QuotaErrorCode.BILLING_UNAVAILABLE,
            "Billing service is temporarily unavailable",
        ) from exc

    if row is None:
        raise _error(
            status.HTTP_403_FORBIDDEN,
            QuotaErrorCode.NO_BILLING_PLAN,
            "No billing plan is assigned to this organization",
        )

    if not row["is_active"]:
        raise _error(
            status.HTTP_402_PAYMENT_REQUIRED,
            QuotaErrorCode.SUBSCRIPTION_INACTIVE,
            "Subscription is inactive",
        )

    return QuotaSnapshot(
        organization_id=org_id,
        requests_used=int(row["requests_used"]),
        max_requests=int(row["max_requests"]),
    )


async def check_quota(
    tenant_id: CurrentTenant, session: TenantSession
) -> QuotaSnapshot:
    """402 Payment Required, если квота неактивна или `requests_used >= max_requests`."""
    org_id = str(tenant_id)
    quota = await _load_quota(session, org_id)

    if quota.requests_used >= quota.max_requests:
        logger.warning(
            "billing: quota exceeded",
            extra={
                "organization_id": org_id,
                "requests_used": quota.requests_used,
                "max_requests": quota.max_requests,
            },
        )
        raise _error(
            status.HTTP_402_PAYMENT_REQUIRED,
            QuotaErrorCode.QUOTA_EXCEEDED,
            "Request quota exceeded. Upgrade your plan to continue.",
            requests_used=quota.requests_used,
            max_requests=quota.max_requests,
        )
    return quota


async def consume_request(
    session: AsyncSession, organization_id: str, amount: int = 1
) -> QuotaSnapshot:
    """Атомарно списывает `amount` запросов; 402, если лимит не позволяет.

    Вызывать в той же транзакции, что и полезная работа, затем commit.
    """
    if amount < 1:
        raise ValueError("amount must be >= 1")
    try:
        row = (
            (
                await session.execute(
                    _CONSUME, {"org_id": organization_id, "amount": amount}
                )
            )
            .mappings()
            .first()
        )
    except SQLAlchemyError as exc:
        logger.exception(
            "billing: consume failed", extra={"organization_id": organization_id}
        )
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            QuotaErrorCode.BILLING_UNAVAILABLE,
            "Billing service is temporarily unavailable",
        ) from exc

    if row is None:
        # Не списали: нет строки, квота выключена или лимит исчерпан — различаем диагностикой.
        await check_quota_for(session, organization_id)
        raise _error(
            status.HTTP_402_PAYMENT_REQUIRED,
            QuotaErrorCode.QUOTA_EXCEEDED,
            "Request quota exceeded. Upgrade your plan to continue.",
        )
    return QuotaSnapshot(
        organization_id=organization_id,
        requests_used=int(row["requests_used"]),
        max_requests=int(row["max_requests"]),
    )


async def check_quota_for(session: AsyncSession, organization_id: str) -> QuotaSnapshot:
    """Та же проверка вне FastAPI (воркеры ARQ): бросает HTTPException 402/403/503."""
    quota = await _load_quota(session, organization_id)
    if quota.requests_used >= quota.max_requests:
        raise _error(
            status.HTTP_402_PAYMENT_REQUIRED,
            QuotaErrorCode.QUOTA_EXCEEDED,
            "Request quota exceeded. Upgrade your plan to continue.",
            requests_used=quota.requests_used,
            max_requests=quota.max_requests,
        )
    return quota


QuotaOk = Annotated[QuotaSnapshot, Depends(check_quota)]
