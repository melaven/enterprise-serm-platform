"""
ARQ фоновые задачи для парсинга отзывов с Tenable SERM архитектурой
Интегрированы с системой биллинга для точного учета токенов LLM
"""

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from arq import Retry
from pydantic import BaseModel

from ...core.logger import get_logger
from ...core.tracing import traced_task
from ...schemas.parser import RawReview
from ..parsers.base import ParserTransportError
from ..parsers.factory import ParserDeps, create_parser
from ..llm_analyzer import AnalysisOutcome, LLMTransportError
from ..billing import QuotaService
from .hooks import dlq_protected

logger = get_logger(__name__)


class AnalyzedReview(BaseModel):
    """Отзыв после LLM-анализа."""
    raw: RawReview
    analysis: AnalysisOutcome


# Константа оценочного резервирования токенов на 1 отзыв
# (средняя длина отзыва ~500 токенов для Gemini)
ESTIMATED_TOKENS_PER_REVIEW = 1000


async def _publish_parser_progress(
    ctx: dict[str, Any],
    job_id: str,
    stage: str,
) -> None:
    redis = ctx.get("redis")
    if redis is None:
        logger.warning("parser_progress_redis_unavailable", job_id=job_id, stage=stage)
        return

    try:
        await redis.set(
            f"parser_job:{job_id}:progress",
            json.dumps({"stage": stage}),
            ex=3600,
        )
    except Exception as exc:
        logger.warning(
            "parser_progress_publish_failed",
            job_id=job_id,
            stage=stage,
            error=str(exc),
        )


@dlq_protected(max_tries=3)  # САМЫЙ ВНЕШНИЙ декоратор для DLQ
@traced_task("fetch_reviews")
async def fetch_reviews_task(
    ctx: dict[str, Any],
    company_id: UUID,
    platform: str,
    url: str,
    *,
    limit: int = 50,
    correlation_id: str | None = None,  # Correlation ID для трассировки
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Боевая задача парсинга отзывов с Tenable SERM архитектурой и биллингом.
    
    Пайплайн: 
    1. Резервирование токенов (оценка)
    2. Парсер -> параллельный LLM-анализ
    3. Точное списание токенов + возврат разницы
    4. Сохранение в review_sink
    5. Списание отзывов из квоты
    
    Args:
        ctx: Контекст ARQ с зависимостями (parser_deps, llm, review_sink, quota_service, db_session)
        company_id: UUID компании для RLS и биллинга
        platform: Код платформы ("2gis", "yandex", "google")
        url: URL для парсинга
        limit: Максимальное количество отзывов
        correlation_id: Correlation ID для сквозной трассировки (от клиента)
        
    Returns:
        Статистика парсинга, анализа и биллинга
    """
    
    company_id = UUID(str(company_id))
    job_id = ctx.get("job_id", "unknown")
    
    # Устанавливаем correlation_id в контекст для логирования
    from ...core.logger import set_correlation_id, generate_correlation_id
    if correlation_id:
        set_correlation_id(correlation_id)
    else:
        # Генерируем новый если не передан от клиента
        correlation_id = generate_correlation_id()
        set_correlation_id(correlation_id)
    
    # Получаем зависимости из контекста воркера
    parser_deps: ParserDeps = ctx["parser_deps"]
    llm = ctx["llm"]
    review_sink = ctx["review_sink"]
    quota_service: QuotaService = ctx.get("quota_service")
    
    logger.info(
        "fetch_reviews_started",
        company_id=str(company_id),
        platform=platform,
        url=url,
        limit=limit,
        job_id=job_id,
        correlation_id=correlation_id
    )
    
    # === ШАГ 0: РЕЗЕРВИРОВАНИЕ ТОКЕНОВ (ОЦЕНКА) ===
    estimated_tokens = limit * ESTIMATED_TOKENS_PER_REVIEW
    reserved_tokens = 0
    
    if quota_service:
        try:
            # Проверяем и резервируем токены
            quota_check = await quota_service.check_quota(
                company_id, 
                tokens=estimated_tokens,
                reviews=limit
            )
            
            if not quota_check.available:
                logger.error(
                    "quota_exceeded_before_task",
                    company_id=str(company_id),
                    estimated_tokens=estimated_tokens,
                    limit=limit,
                    reason=quota_check.reason,
                    job_id=job_id
                )
                raise Exception(f"Quota exceeded: {quota_check.reason}")
            
            # Резервируем токены
            if not await quota_service.reserve_llm_tokens(company_id, estimated_tokens):
                logger.error(
                    "token_reservation_failed",
                    company_id=str(company_id),
                    estimated_tokens=estimated_tokens,
                    job_id=job_id
                )
                raise Exception("Failed to reserve LLM tokens")
            
            reserved_tokens = estimated_tokens
            
            logger.info(
                "tokens_reserved",
                company_id=str(company_id),
                reserved=reserved_tokens,
                job_id=job_id
            )
            
        except Exception as e:
            logger.error(
                "quota_check_failed",
                company_id=str(company_id),
                error=str(e),
                job_id=job_id
            )
            raise
    
    try:
        # === ШАГ 1: ПАРСИНГ ОТЗЫВОВ ===
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
            
            # Возвращаем зарезервированные токены перед retry
            if quota_service and reserved_tokens > 0:
                await quota_service.release_llm_tokens(company_id, reserved_tokens)
                logger.info("tokens_released_before_retry", tokens=reserved_tokens)
            
            raise Retry(defer=defer) from e
        
        if not raw_reviews:
            logger.info("no_reviews_found", job_id=job_id)
            
            # Возвращаем зарезервированные токены
            if quota_service and reserved_tokens > 0:
                await quota_service.release_llm_tokens(company_id, reserved_tokens)
                logger.info("tokens_released_no_reviews", tokens=reserved_tokens)
            
            return {"fetched": 0, "analyzed": 0, "fallbacks": 0, "saved": 0, "tokens_used": 0}
        
        logger.info(
            "parsing_completed", 
            fetched=len(raw_reviews), 
            job_id=job_id
        )
        
        # === ШАГ 2: ПАРАЛЛЕЛЬНЫЙ LLM-АНАЛИЗ ===
        await _publish_parser_progress(ctx, job_id, "analyzing")
        analyzed_reviews: list[AnalyzedReview] = []
        fallback_count = 0
        total_tokens_used = 0
        
        for raw_review in raw_reviews:
            try:
                analysis = await llm.analyze_safe(
                    raw_review.text,
                    rating=int(raw_review.rating) if raw_review.rating is not None else None,
                    platform=platform
                )
                
                analyzed_reviews.append(AnalyzedReview(raw=raw_review, analysis=analysis))
                total_tokens_used += analysis.tokens_used
                
                if analysis.is_fallback:
                    fallback_count += 1
                    
            except LLMTransportError as e:
                # LLM транспортные ошибки -> retry
                logger.warning(
                    "llm_transport_error_retry",
                    error=str(e),
                    job_id=job_id
                )
                
                # Возвращаем зарезервированные токены перед retry
                if quota_service and reserved_tokens > 0:
                    await quota_service.release_llm_tokens(company_id, reserved_tokens)
                    logger.info("tokens_released_before_llm_retry", tokens=reserved_tokens)
                
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
                from ..llm_analyzer import fallback_result
                fallback_analysis = AnalysisOutcome(
                    fallback_result(int(raw_review.rating) if raw_review.rating is not None else None),
                    is_fallback=True,
                    tokens_used=0
                )
                analyzed_reviews.append(AnalyzedReview(raw=raw_review, analysis=fallback_analysis))
                fallback_count += 1
        
        analyzed_count = len(analyzed_reviews) - fallback_count
        
        logger.info(
            "llm_analysis_completed",
            analyzed=analyzed_count,
            fallbacks=fallback_count,
            total_tokens_used=total_tokens_used,
            job_id=job_id
        )
        
        # === ШАГ 3: ТОЧНОЕ СПИСАНИЕ ТОКЕНОВ ===
        if quota_service and reserved_tokens > 0:
            try:
                await quota_service.commit_llm_tokens(
                    company_id,
                    reserved=reserved_tokens,
                    actual=total_tokens_used
                )
                
                returned_tokens = max(0, reserved_tokens - total_tokens_used)
                logger.info(
                    "tokens_committed",
                    company_id=str(company_id),
                    reserved=reserved_tokens,
                    actual=total_tokens_used,
                    returned=returned_tokens,
                    job_id=job_id
                )
                
            except Exception as e:
                logger.error(
                    "token_commit_failed",
                    company_id=str(company_id),
                    error=str(e),
                    job_id=job_id
                )
                # Не падаем, но логируем проблему
        
        # === ШАГ 4: СОХРАНЕНИЕ В REVIEW_SINK ===
        saved_count = await review_sink.save(company_id, analyzed_reviews)
        
        logger.info(
            "reviews_saved",
            saved=saved_count,
            job_id=job_id
        )
        
        # === ШАГ 5: СПИСАНИЕ ОТЗЫВОВ ===
        if quota_service and saved_count > 0:
            try:
                if not await quota_service.consume_reviews(company_id, saved_count):
                    logger.warning(
                        "review_quota_exceeded_after_save",
                        company_id=str(company_id),
                        saved=saved_count,
                        job_id=job_id
                    )
            except Exception as e:
                logger.error(
                    "review_consumption_failed",
                    company_id=str(company_id),
                    error=str(e),
                    job_id=job_id
                )
        
        return {
            "fetched": len(raw_reviews),
            "analyzed": analyzed_count,
            "fallbacks": fallback_count,
            "saved": saved_count,
            "tokens_reserved": reserved_tokens,
            "tokens_used": total_tokens_used,
            "tokens_returned": max(0, reserved_tokens - total_tokens_used),
        }
        
    except Exception as e:
        # === ОБРАБОТКА ОШИБОК: ВОЗВРАТ ЗАРЕЗЕРВИРОВАННЫХ ТОКЕНОВ ===
        if quota_service and reserved_tokens > 0:
            try:
                await quota_service.release_llm_tokens(company_id, reserved_tokens)
                logger.info(
                    "tokens_released_on_error",
                    company_id=str(company_id),
                    tokens=reserved_tokens,
                    error=str(e),
                    job_id=job_id
                )
            except Exception as release_error:
                logger.error(
                    "token_release_failed",
                    company_id=str(company_id),
                    tokens=reserved_tokens,
                    error=str(release_error),
                    job_id=job_id
                )
        
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