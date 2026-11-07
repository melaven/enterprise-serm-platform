"""ARQ tasks for publishing AI-generated review replies."""

from uuid import UUID

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger
from app.core.tenant_session import set_tenant_rls_context
from app.infrastructure.persistence.models.economics import Review

logger = get_logger(__name__)


async def publish_review_reply(
    ctx: dict[str, object], event_payload: dict[str, object]
) -> None:
    tenant_id = UUID(str(event_payload.get("tenant_id", "")))
    review_id = UUID(str(event_payload.get("review_id", "")))

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_rls_context(session, tenant_id)
            review = await session.scalar(
                select(Review)
                .where(
                    Review.id == review_id,
                    Review.company_id == tenant_id,
                )
                .with_for_update()
            )
            if review is None:
                raise ValueError(f"Review {review_id} was not found for tenant")
            if review.reply_status == "published":
                return
            if review.reply_status != "approved" or not review.generated_reply:
                raise ValueError(f"Review {review_id} has no approved generated reply")

            logger.info(
                "Publishing reply to external platform...",
                review_id=str(review_id),
                tenant_id=str(tenant_id),
            )
            review.reply_status = "published"
