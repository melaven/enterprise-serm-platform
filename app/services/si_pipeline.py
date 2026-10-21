"""Legacy review-text LLM pipeline; retained only for fail-closed compatibility."""

from typing import Any
from uuid import UUID


class SentimentIntelligencePipeline:
    def __init__(
        self,
        *,
        model: str | None = None,
        timeout: float = 20.0,
        max_concurrency: int = 5,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least one")

    async def analyze_review(self, text: str) -> Any:
        raise RuntimeError(
            "External review LLM analysis is disabled; use local SI instead"
        )

    async def process_batch(
        self,
        db_session: Any,
        review_ids: list[UUID],
        *,
        tenant_id: UUID | None = None,
        dlq_store: Any = None,
        job_id: str = "review-analysis",
        correlation_id: str = "unknown",
    ) -> int:
        raise RuntimeError(
            "Background review-text analysis is disabled; SI runs locally at ingestion"
        )
