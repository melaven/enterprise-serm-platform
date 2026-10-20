"""Background publication of customer-approved review replies."""

from urllib.parse import quote
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger
from app.core.tenant_session import get_tenant_session
from app.models.economics import PlatformIntegration, Review
from app.schemas.economics import ReviewStatus

logger = get_logger(__name__)
GOOGLE_REPLY_URL = (
    "https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/"
    "{location_id}/reviews/{review_id}/reply"
)


async def publish_review_reply(
    ctx: dict[str, object],
    tenant_id: str,
    review_id: str,
    reply_text: str,
) -> dict[str, str]:
    tenant_uuid = UUID(tenant_id)
    review_uuid = UUID(review_id)
    session: AsyncSession = await get_tenant_session(
        factory=AsyncSessionLocal,
        tenant_id=tenant_uuid,
    )
    try:
        review = await session.scalar(
            select(Review).where(
                Review.id == review_uuid,
                Review.company_id == tenant_uuid,
            )
        )
        if review is None:
            raise ValueError("Review not found for tenant")
        if (review.platform or "").lower() not in {"google", "google_business"}:
            raise ValueError(
                "Review replies are currently supported for Google Business"
            )
        if not review.external_review_id:
            raise ValueError("Review has no external platform ID")

        integrations = await session.scalars(
            select(PlatformIntegration).where(
                PlatformIntegration.company_id == tenant_uuid,
                PlatformIntegration.platform.in_(("google", "google_business")),
                PlatformIntegration.is_active.is_(True),
            )
        )
        active_integrations = list(integrations.all())
        if len(active_integrations) != 1:
            raise ValueError(
                "Exactly one active Google Business integration is required"
            )
        integration = active_integrations[0]
        if not integration.external_account_id or not integration.external_location_id:
            raise ValueError(
                "Google Business account and location IDs are not configured"
            )

        url = GOOGLE_REPLY_URL.format(
            account_id=quote(integration.external_account_id, safe=""),
            location_id=quote(integration.external_location_id, safe=""),
            review_id=quote(review.external_review_id, safe=""),
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.put(
                url,
                headers={"Authorization": f"Bearer {integration.api_key}"},
                json={"comment": reply_text},
            )
            response.raise_for_status()

        review.si_response = reply_text
        review.auto_reply = reply_text
        review.status = ReviewStatus.RESOLVED
        review.ai_pending = False
        await session.commit()
        logger.info(
            "review_reply_published",
            tenant_id=tenant_id,
            review_id=review_id,
            platform="google_business",
        )
        return {"review_id": review_id, "status": "published"}
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
