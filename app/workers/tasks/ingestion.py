"""Background sanitization and persistence for incoming platform reviews."""

from typing import Any
from uuid import UUID

from fastapi.concurrency import run_in_threadpool

from app.api.schemas.ingest import ReviewIngestPayload
from app.core.database import AsyncSessionLocal
from app.core.pii import PIISanitizer, redact_text
from app.core.tenant_session import get_tenant_session
from app.infrastructure.repositories.bulk_reviews import BulkReviewRepository


def _sanitize_review(
    tenant_id: UUID, payload: ReviewIngestPayload
) -> dict[str, object]:
    return {
        "tenant_id": tenant_id,
        "platform": payload.platform,
        "external_id": PIISanitizer.hash_user_id(payload.platform, payload.external_id),
        "author_hash": (
            PIISanitizer.hash_user_id(payload.platform, payload.raw_author)
            if payload.raw_author
            else None
        ),
        "author_display": PIISanitizer.mask_author_name(payload.raw_author),
        "clean_text": redact_text(payload.raw_text),
        "rating": payload.rating,
        "published_at": payload.published_at,
    }


async def process_review_ingestion(
    ctx: dict[str, Any],
    tenant_id: str,
    payload: dict[str, object],
) -> dict[str, int | str]:
    """Sanitize a queued review and upsert it inside the tenant's RLS context."""
    company_uuid = UUID(tenant_id)
    review_payload = ReviewIngestPayload.model_validate(payload)
    sanitized_review = await run_in_threadpool(
        _sanitize_review, company_uuid, review_payload
    )

    session = await get_tenant_session(AsyncSessionLocal, company_uuid)
    try:
        inserted = await BulkReviewRepository(session).bulk_upsert_reviews(
            [sanitized_review]
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

    return {"tenant_id": str(company_uuid), "processed": inserted}
