"""Disabled legacy review-ingestion jobs."""

from typing import Any
from uuid import UUID


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
