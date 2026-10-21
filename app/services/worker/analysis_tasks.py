"""Disabled legacy background analysis task."""

from typing import Any
from uuid import UUID


async def process_reviews_batch(
    ctx: dict[str, Any], tenant_id: UUID, review_ids: list[UUID]
) -> dict[str, int]:
    raise RuntimeError(
        "Background review-text analysis is disabled; SI runs locally at ingestion"
    )
