"""
ARQ фоновые задачи для парсинга отзывов с боевыми парсерами ХИУС
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from arq import Retry
from pydantic import BaseModel

from ..core.logger import get_logger
from ..core.tracing import traced_task
from ..schemas.parser import RawReview
from ..services.parsers.base import ParserTransportError
from ..services.parsers.factory import ParserDeps, create_parser
from ..services.llm_analyzer import AnalysisOutcome, LLMTransportError
from .hooks import dlq_protected

logger = get_logger(__name__)


class AnalyzedReview(BaseModel):
    """Отзыв после LLM-анализа."""
    raw: RawReview
    analysis: AnalysisOutcome


@dlq_protected(max_tries=3)  # САМЫЙ ВНЕШНИЙ декоратор для DLQ
@traced_task("fetch_reviews")
async def fetch_reviews_task(
    ctx: dict[str, Any],
    company_id: UUID,
    platform: str,
    url: str,
    *,
    limit: int = 50,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Боевая задача парсинга отзывов с ХИУС архитектурой.
    
    Пайплайн: парсер -> параллельный LLM-анализ -> сохранение в review_sink.
    
    Args:
        ctx: Контекст ARQ с зависимостями (parser_deps, llm, review_sink)
        company_id: UUID компании для RLS
        platform: Код платформы ("2gis", "yandex", "google")
        url: URL для парсинга
        limit: Максимальное количество отзывов
        
    Returns:
        Статистика парсинга и анализа
    """
    
    job_id = ctx.get("job_id", "unknown")
    
    # Получаем зависимости из контекста воркера
    parser_deps: ParserDeps = ctx["parser_deps"]
    llm = ctx["llm"]
    review_sink = ctx["review_sink"]
    
    logger.info(
        "fetch_reviews_started",
        company_id=str(company_id),
        platform=platform,
        url=url,
        limit=limit,
        job_id=job_id
    )
    
    try:
        # Шаг 1: Парсинг отзывов
        parser = create_parser(platform, parser_deps)
        
        try:
            raw_reviews = await parser.fetch_reviews(url, limit)
        except ParserTransportError as e:
            # Транспортные ошибки парсера -> retry с учетом Retry-After
            defer = e.retry_after or 30.0
            logger.warning(
                "parser_transport_error_retry",
                platform=platform,
                error=str(e),
                defer_seconds=defer,
                job_id=job_id
            )
            raise Retry(defer=defer) from e
        
        if not raw_reviews:
            logger.info("no_reviews_found", job_id=job_id)
            return {"fetched": 0, "analyzed": 0, "fallbacks": 0, "saved": 0}
        
        logger.info(
            "parsing_completed", 
            fetched=len(raw_reviews), 
            job_id=job_id
        )
        
        # Шаг 2: Параллельный LLM-анализ
        analyzed_reviews: list[AnalyzedReview] = []
        fallback_count = 0
        
        for raw_review in raw_reviews:
            try:
                analysis = await llm.analyze_safe(
                    raw_review.text,
                    rating=int(raw_review.rating) if raw_review.rating is not None else None,
                    platform=platform
                )
                
                analyzed_reviews.append(AnalyzedReview(raw=raw_review, analysis=analysis))
                
                if analysis.is_fallback:
                    fallback_count += 1
                    
            except LLMTransportError as e:
                # LLM транспортные ошибки -> retry
                logger.warning(
                    "llm_transport_error_retry",
                    error=str(e),
                    job_id=job_id
                )
                raise Retry(defer=30) from e
            except Exception as e:
                # Другие ошибки LLM -> логируем и используем fallback
                logger.error(
                    "llm_analysis_failed_fallback",
                    error=str(e),
                    platform_id=raw_review.platform_id,
                    job_id=job_id
                )
                # Создаем fallback анализ
                from ..services.llm_analyzer import fallback_result
                fallback_analysis = AnalysisOutcome(
                    fallback_result(int(raw_review.rating) if raw_review.rating is not None else None),
                    is_fallback=True
                )
                analyzed_reviews.append(AnalyzedReview(raw=raw_review, analysis=fallback_analysis))
                fallback_count += 1
        
        analyzed_count = len(analyzed_reviews) - fallback_count
        
        logger.info(
            "llm_analysis_completed",
            analyzed=analyzed_count,
            fallbacks=fallback_count,
            job_id=job_id
        )
        
        # Шаг 3: Сохранение в review_sink
        saved_count = await review_sink.save(company_id, analyzed_reviews)
        
        logger.info(
            "reviews_saved",
            saved=saved_count,
            job_id=job_id
        )
        
        return {
            "fetched": len(raw_reviews),
            "analyzed": analyzed_count,
            "fallbacks": fallback_count,
            "saved": saved_count,
        }
        
    except Exception as e:
        # Проверяем на транзиентные ошибки для retry
        if any(keyword in str(e).lower() for keyword in ["timeout", "connection", "network"]):
            logger.warning(
                "transient_error_retry",
                error=str(e),
                error_type=type(e).__name__,
                job_id=job_id
            )
            raise Retry(defer=30) from e
        else:
            logger.error(
                "permanent_task_error",
                error=str(e),
                error_type=type(e).__name__,
                job_id=job_id
            )
            raise