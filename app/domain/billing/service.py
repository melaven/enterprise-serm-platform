"""Usage-based billing operations for tenant LLM token quotas."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.billing.exceptions import QuotaExceededError, SubscriptionInactiveError
from app.infrastructure.persistence.models.billing import (
    SubscriptionPlan,
    TenantSubscription,
    TokenUsageLog,
)


class BillingService:
    """Enforce subscription token allowances and record LLM usage."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check_quota(self, company_id: UUID) -> None:
        """Raise when the tenant has no active subscription or has exhausted quota."""
        subscription_result = await self._session.execute(
            select(
                TenantSubscription.status,
                TenantSubscription.current_period_start,
                TenantSubscription.current_period_end,
                SubscriptionPlan.included_tokens_per_month,
            )
            .join(
                SubscriptionPlan,
                TenantSubscription.plan_id == SubscriptionPlan.id,
            )
            .where(TenantSubscription.company_id == company_id)
            .order_by(TenantSubscription.current_period_end.desc())
            .limit(1)
        )
        subscription = subscription_result.one_or_none()

        if subscription is None or subscription.status != "active":
            raise SubscriptionInactiveError(
                f"No active subscription found for company {company_id}"
            )

        used_tokens_result = await self._session.execute(
            select(
                func.coalesce(
                    func.sum(TokenUsageLog.input_tokens + TokenUsageLog.output_tokens),
                    0,
                )
            ).where(
                TokenUsageLog.company_id == company_id,
                TokenUsageLog.created_at >= subscription.current_period_start,
                TokenUsageLog.created_at < subscription.current_period_end,
            )
        )
        used_tokens = used_tokens_result.scalar_one()

        if used_tokens >= subscription.included_tokens_per_month:
            raise QuotaExceededError(
                f"Token quota exhausted for company {company_id}: "
                f"{used_tokens} of "
                f"{subscription.included_tokens_per_month} tokens used"
            )

    async def log_usage(
        self,
        company_id: UUID,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        total_cost_usd: float = 0.0,
    ) -> None:
        """Add a usage record and flush it within the caller's transaction."""
        self._session.add(
            TokenUsageLog(
                company_id=company_id,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_cost_usd=total_cost_usd,
            )
        )
        await self._session.flush()
