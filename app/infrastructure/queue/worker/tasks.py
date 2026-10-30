"""ARQ worker tasks for review processing and LLM analytics."""

from typing import Any
from uuid import UUID

import structlog

from app.infrastructure.integrations.review_platforms.factory import get_adapter

logger = structlog.get_logger(__name__)


async def process_company_reviews(
    ctx: dict[str, Any],
    company_id: str,
    platform: str,
    access_token: str,
    **kwargs: Any,
) -> dict[str, int | str]:
    """
    Fetch and process reviews from a platform with PII sanitization.

    This task:
    1. Gets the appropriate platform adapter
    2. Fetches sanitized reviews (PII removed)
    3. Logs each review (future: will call GroqReviewAnalyzer)

    Args:
        ctx: ARQ task context
        company_id: Company identifier on the platform
        platform: Platform name (e.g., "yandex", "google")
        access_token: Platform API access token

    Returns:
        Dictionary with processing statistics
    """
    logger.info(
        "process_company_reviews_started",
        company_id=company_id,
        platform=platform,
    )

    try:
        # Get the appropriate adapter for the platform
        adapter = get_adapter(platform)

        # Fetch sanitized reviews (PII already removed)
        reviews = await adapter.get_sanitized_reviews(company_id, access_token)

        logger.info(
            "reviews_fetched",
            company_id=company_id,
            platform=platform,
            count=len(reviews),
        )

        # Process each review (currently just logging, future: LLM analysis)
        for review in reviews:
            logger.info(
                "review_processed",
                external_id=review.external_id,
                platform=review.platform,
                author_hash=review.author_hash,
                author_display=review.author_display,
                rating=review.rating,
                text_length=len(review.text),
            )
            # TODO: Call GroqReviewAnalyzer here for sentiment analysis

        return {
            "processed": len(reviews),
            "company_id": company_id,
            "platform": platform,
        }

    except Exception as exc:
        logger.error(
            "process_company_reviews_failed",
            company_id=company_id,
            platform=platform,
            error=str(exc),
            exc_info=True,
        )
        raise


# Disabled legacy review-ingestion jobs
async def fetch_reviews_task(
    ctx: dict[str, Any],
    company_id: UUID,
    platform: str,
    url: str,
    *,
    limit: int = 50,
    correlation_id: str | None = None,
    **kwargs: Any,
) -> dict[str, int]:
    raise RuntimeError("Public-page scraping and review-text LLM analysis are disabled")


async def fetch_platform_reviews(
    ctx: dict[str, Any],
    company_id: UUID,
    platform: str,
    correlation_id: str | None = None,
    **kwargs: Any,
) -> dict[str, int]:
    raise RuntimeError("Platform review scraping is disabled")
