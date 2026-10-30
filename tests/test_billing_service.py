from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.billing.exceptions import (
    QuotaExceededError,
    SubscriptionInactiveError,
)
from app.domain.billing.service import BillingService
from app.infrastructure.persistence.models.billing import (
    SubscriptionPlan,
    TenantSubscription,
    TokenUsageLog,
)


async def _create_subscription(
    session: AsyncSession,
    company_id: UUID,
    *,
    status: str = "active",
    token_limit: int = 100,
) -> tuple[datetime, datetime]:
    period_start = datetime.now(timezone.utc) - timedelta(days=1)
    period_end = period_start + timedelta(days=30)
    plan = SubscriptionPlan(
        name=f"Test plan {uuid4()}",
        monthly_price_usd=10.0,
        included_tokens_per_month=token_limit,
        overage_price_per_1k_usd=1.0,
    )
    session.add(plan)
    await session.flush()
    session.add(
        TenantSubscription(
            company_id=company_id,
            plan_id=plan.id,
            status=status,
            current_period_start=period_start,
            current_period_end=period_end,
        )
    )
    await session.flush()
    return period_start, period_end


@pytest.mark.asyncio
async def test_check_quota_allows_usage_below_limit(
    db_session: AsyncSession, company_id: UUID
) -> None:
    await _create_subscription(db_session, company_id, token_limit=100)
    await BillingService(db_session).log_usage(
        company_id, "test-model", input_tokens=30, output_tokens=20
    )

    await BillingService(db_session).check_quota(company_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("used_tokens", [100, 120])
async def test_check_quota_rejects_exhausted_or_exceeded_limit(
    db_session: AsyncSession,
    company_id: UUID,
    used_tokens: int,
) -> None:
    await _create_subscription(db_session, company_id, token_limit=100)
    db_session.add(
        TokenUsageLog(
            company_id=company_id,
            model_name="test-model",
            input_tokens=used_tokens,
            output_tokens=0,
            total_cost_usd=0.0,
        )
    )
    await db_session.flush()

    with pytest.raises(QuotaExceededError):
        await BillingService(db_session).check_quota(company_id)


@pytest.mark.asyncio
async def test_check_quota_rejects_inactive_subscription(
    db_session: AsyncSession, company_id: UUID
) -> None:
    await _create_subscription(db_session, company_id, status="canceled")

    with pytest.raises(SubscriptionInactiveError):
        await BillingService(db_session).check_quota(company_id)


@pytest.mark.asyncio
async def test_log_usage_persists_record_on_flush(
    db_session: AsyncSession, company_id: UUID
) -> None:
    service = BillingService(db_session)

    await service.log_usage(
        company_id,
        "test-model",
        input_tokens=12,
        output_tokens=8,
        total_cost_usd=0.25,
    )

    usage = await db_session.scalar(
        select(TokenUsageLog).where(TokenUsageLog.company_id == company_id)
    )
    assert usage is not None
    assert usage.model_name == "test-model"
    assert usage.input_tokens == 12
    assert usage.output_tokens == 8
    assert usage.total_cost_usd == 0.25
