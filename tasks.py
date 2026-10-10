"""ARQ-задачи. Здесь: fetch_reviews_task = парсер -> LLM-анализ -> сохранение."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import structlog
from arq.worker import Retry

from app.core.tracing import traced_task
from app.schemas.parser import RawReview
from app.services.llm_analyzer import AnalysisOutcome
from app.services.parsers.base import ParserTransportError
from app.services.parsers.factory import ParserDeps, create_parser
from app.worker.hooks import dlq_protected

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

MAX_TRIES = 3
RETRY_BASE_DELAY_S = 30  # пауза между попытками растёт: 30 с, 60 с
LLM_CONCURRENCY = 5


class LLMService(Protocol):
    """Контракт анализатора; его реализует LLMReviewAnalyzer из llm_analyzer.py."""

    async def analyze_safe(
        self, text: str, *, rating: int | None = None, platform: str | None = None
    ) -> AnalysisOutcome: ...


@dataclass(frozen=True, slots=True)
class AnalyzedReview:
    raw: RawReview
    outcome: AnalysisOutcome


class AnalyzedReviewSink(Protocol):
    """Сохранение результата. Подставь свою реализацию (код записи в БД)."""

    async def save(self, company_id: UUID, items: Sequence[AnalyzedReview]) -> int: ...


async def _analyze_all(
    llm: LLMService, reviews: Sequence[RawReview]
) -> list[AnalyzedReview]:
    semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

    async def one(review: RawReview) -> AnalyzedReview:
        async with semaphore:
            outcome = await llm.analyze_safe(
                review.text,
                rating=round(review.rating),
                platform=review.platform.value,
            )
        return AnalyzedReview(review, outcome)

    return list(await asyncio.gather(*(one(r) for r in reviews)))


# Порядок важен: dlq_protected СНАРУЖИ (видит kwargs с correlation_id),
# traced_task внутри.
@dlq_protected(max_tries=MAX_TRIES)
@traced_task("fetch_reviews")
async def fetch_reviews_task(
    ctx: dict[str, Any],
    company_id: UUID,
    platform: str,
    url: str,
    limit: int = 50,
) -> dict[str, int]:
    deps: ParserDeps = ctx["parser_deps"]
    llm: LLMService = ctx["llm"]
    sink: AnalyzedReviewSink = ctx["review_sink"]

    parser = create_parser(platform, deps)  # UnsupportedPlatformError -> сразу в DLQ
    try:
        raw_reviews = await parser.fetch_reviews(url, limit)
    except ParserTransportError as exc:
        defer = exc.retry_after or RETRY_BASE_DELAY_S * int(ctx.get("job_try", 1))
        logger.warning(
            "parser_transport_error",
            platform=platform,
            status_code=exc.status_code,
            retry_in_s=defer,
            job_try=ctx.get("job_try"),
        )
        # На 3-й попытке dlq_protected увидит Retry и положит задачу в DLQ.
        raise Retry(defer=defer) from exc

    analyzed = await _analyze_all(llm, raw_reviews)
    saved = await sink.save(company_id, analyzed)
    fallbacks = sum(1 for item in analyzed if item.outcome.is_fallback)
    logger.info(
        "reviews_processed",
        platform=platform,
        fetched=len(raw_reviews),
        saved=saved,
        llm_fallbacks=fallbacks,
    )
    return {
        "fetched": len(raw_reviews),
        "analyzed": len(analyzed) - fallbacks,
        "fallbacks": fallbacks,
        "saved": saved,
    }


# --- WorkerSettings (фрагмент) -------------------------------------------------
#   from arq import func
#   functions = [
#       func(fetch_reviews_task, name="fetch_reviews_task", max_tries=MAX_TRIES)
#   ]
#   # max_tries у ARQ и в @dlq_protected должны совпадать (иначе ARQ оборвёт раньше)
#
#   async def startup(ctx):
#       ctx["parser_deps"] = ParserDeps(http_client=httpx.AsyncClient(),
#                                       twogis_api_key=settings.twogis_reviews_api_key)
#       ctx["llm"] = build_gemini_analyzer(settings.gemini_api_key)   # temperature=0.0
#       ctx["review_sink"] = <твоя реализация сохранения>
#       ... dlq_store, RLS-проверки и configure_logging() как раньше
#   async def shutdown(ctx): await ctx["parser_deps"].http_client.aclose()
