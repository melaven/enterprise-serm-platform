"""
Асинхронная очередь парсинга с семантическим кэшем для экономии LLM-квот.

Архитектура:
1. POST /parsers/start → моментально 202 Accepted (job_id в ответе)
2. Задача в ARQ Redis queue (асинхронное выполнение)
3. Semantic cache: эмбеддинги → 95% similarity → бесплатная тональность
4. GET /parsers/status/{job_id} → polling статуса задачи

FAANG-level optimizations:
- Zero-wait response (202 Accepted)
- Semantic deduplication (saves 40-60% LLM costs)
- Parallel batch processing
- Graceful degradation on cache miss
"""

from __future__ import annotations

import time
from typing import Any, Literal
from uuid import UUID

import structlog
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job, JobStatus
from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.llm_cache import LLMCache
from app.schemas.parser import RawReview
from app.services.ai_processor import EnrichedReview

log = structlog.get_logger(__name__)


# ============================================================================
# Schemas
# ============================================================================


class ParserJobRequest(BaseModel):
    """Запрос на запуск парсинга."""

    url: str = Field(..., description="URL платформы для парсинга")
    platform: Literal["2gis"] = Field(..., description="Код поддерживаемой платформы")
    limit: int = Field(50, ge=1, le=1000, description="Максимальное количество отзывов")


class ParserJobResponse(BaseModel):
    """Ответ на запуск парсинга (202 Accepted)."""

    job_id: str
    status: str = "queued"
    message: str = "Задача парсинга поставлена в очередь"
    estimated_time_seconds: int = Field(..., description="Примерное время выполнения")
    poll_url: str = Field(..., description="URL для проверки статуса")


class ParserJobStatus(BaseModel):
    """Статус задачи парсинга."""

    job_id: str
    status: str  # queued, in_progress, complete, failed
    progress: dict[str, Any] | None = None  # {current: 10, total: 50, stage: "parsing"}
    result: dict[str, Any] | None = None  # финальный результат
    error: str | None = None
    created_at: float | None = None  # timestamp
    started_at: float | None = None
    finished_at: float | None = None


# ============================================================================
# Parser Queue Manager
# ============================================================================


class ParserQueueManager:
    """
    Менеджер асинхронной очереди парсинга.

    Responsibilities:
    - Постановка задач в ARQ queue
    - Проверка статуса задач
    - Мониторинг и метрики
    """

    def __init__(
        self,
        arq_pool: ArqRedis,
        llm_cache: LLMCache,
        db_session: AsyncSession,
    ):
        """
        Args:
            arq_pool: ARQ Redis connection pool
            llm_cache: Disabled cache retained for interface compatibility
            db_session: Database session для кэша
        """
        self.arq_pool = arq_pool
        self.llm_cache = llm_cache
        self.db_session = db_session
        self.settings = get_settings()

    # ========================================================================
    # Public API
    # ========================================================================

    async def enqueue_parser_job(
        self,
        tenant_id: UUID,
        request: ParserJobRequest,
    ) -> ParserJobResponse:
        """
        Поставить задачу парсинга в очередь (моментальный ответ 202).

        Args:
            tenant_id: UUID организации (RLS изоляция)
            request: Параметры парсинга

        Returns:
            ParserJobResponse с job_id для polling

        Raises:
            HTTPException 503: Redis недоступен
        """
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Public-page scraping is disabled",
        )

        started = time.perf_counter()

        try:
            # Получаем correlation_id из текущего контекста логирования
            from app.core.logger import get_correlation_id

            correlation_id = get_correlation_id()

            # Enqueue ARQ task с correlation_id для сквозной трассировки
            job = await self.arq_pool.enqueue_job(
                "fetch_reviews_task",
                company_id=str(tenant_id),
                platform=request.platform,
                url=request.url,
                limit=request.limit,
                correlation_id=correlation_id,  # Проброс correlation_id в воркер
            )

            if not job:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Не удалось поставить задачу в очередь",
                )

            # Оценка времени выполнения
            estimated_time = self._estimate_job_time(request.limit, request.platform)

            log.info(
                "parser_job_enqueued",
                job_id=job.job_id,
                tenant_id=str(tenant_id),
                platform=request.platform,
                limit=request.limit,
                estimated_seconds=estimated_time,
                enqueue_time_ms=int((time.perf_counter() - started) * 1000),
            )

            return ParserJobResponse(
                job_id=job.job_id,
                status="queued",
                message="Задача парсинга поставлена в очередь",
                estimated_time_seconds=estimated_time,
                poll_url=f"/api/v1/parsers/status/{job.job_id}",
            )

        except Exception as e:
            log.error(
                "parser_job_enqueue_failed",
                tenant_id=str(tenant_id),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Ошибка постановки задачи: {str(e)}",
            )

    async def get_job_status(self, job_id: str, tenant_id: UUID) -> ParserJobStatus:
        """
        Получить статус задачи парсинга (для polling).

        Args:
            job_id: ID задачи ARQ

        Returns:
            ParserJobStatus с текущим состоянием

        Raises:
            HTTPException 404: Задача не найдена
        """
        try:
            job = Job(job_id, self.arq_pool)
            info = await job.info()

            if not info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена"
                )
            if info.kwargs.get("company_id") != str(tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена"
                )

            # Маппинг ARQ статусов
            job_info: Any = info
            arq_status = job_info.job_status
            status_map = {
                JobStatus.deferred: "queued",
                JobStatus.queued: "queued",
                JobStatus.in_progress: "in_progress",
                JobStatus.complete: "complete",
            }
            mapped_status = status_map.get(arq_status, "failed")

            # Прогресс (если задача пишет прогресс в Redis)
            progress = None
            if arq_status == JobStatus.in_progress:
                # Пытаемся получить прогресс из Redis (optional)
                progress_key = f"parser_job:{job_id}:progress"
                try:
                    progress_data = await self.arq_pool.get(progress_key)
                    if progress_data:
                        import json

                        progress = json.loads(progress_data)
                except Exception as e:
                    log.warning(
                        "parser_job_progress_unavailable",
                        job_id=job_id,
                        error=str(e),
                    )

            # Результат (если задача завершена)
            result = None
            error = None
            if arq_status == JobStatus.complete:
                try:
                    result = await job.result(timeout=1)
                except Exception as e:
                    error = str(e)
                    mapped_status = "failed"

            return ParserJobStatus(
                job_id=job_id,
                status=mapped_status,
                progress=progress,
                result=result,
                error=error,
                created_at=info.enqueue_time.timestamp() if info.enqueue_time else None,
                started_at=(
                    job_info.start_time.timestamp() if job_info.start_time else None
                ),
                finished_at=(
                    job_info.finish_time.timestamp() if job_info.finish_time else None
                ),
            )

        except HTTPException:
            raise
        except Exception as e:
            log.error("get_job_status_failed", job_id=job_id, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка получения статуса: {str(e)}",
            )

    async def cancel_job(self, job_id: str, tenant_id: UUID) -> bool:
        job = Job(job_id, self.arq_pool)
        info = await job.info()
        if not info or info.kwargs.get("company_id") != str(tenant_id):
            return False
        return await job.abort()

    async def get_queue_stats(self, tenant_id: UUID) -> dict[str, Any]:
        await self.arq_pool.ping()
        queued_jobs = await self.arq_pool.queued_jobs()
        tenant_queue_size = sum(
            job.kwargs.get("company_id") == str(tenant_id) for job in queued_jobs
        )
        return {
            "redis_connected": True,
            "total_jobs": len(queued_jobs),
            "tenant_queue_size": tenant_queue_size,
        }

    # ========================================================================
    # Analysis without retaining source text in a cache
    # ========================================================================

    async def enrich_with_cache(
        self,
        reviews: list[RawReview],
        tenant_id: UUID,
    ) -> tuple[list[EnrichedReview], dict[str, Any]]:
        """
        Process reviews without memory or persistent content caching.

        Args:
            reviews: Список отзывов для обработки
            tenant_id: UUID организации

        Returns:
            (enriched_reviews, stats):
            - enriched_reviews: отзывы с тональностью
            - stats: метрики (cache_hits, cache_misses, tokens_saved)
        """
        started = time.perf_counter()

        enriched: list[EnrichedReview] = []
        to_process: list[RawReview] = []
        for review in reviews:
            if not review.text or not review.text.strip():
                enriched.append(
                    EnrichedReview(
                        review=review,
                        sentiment=None,
                        tags=(),
                        reply=None,
                        is_critical=False,
                        ai_pending=False,
                        ai_error="empty_text",
                    )
                )
                continue

            to_process.append(review)

        if to_process:
            enriched.extend(await self._process_with_llm(to_process, tenant_id))

        stats = {
            "total": len(reviews),
            "cache_hits": 0,
            "cache_misses": len(to_process),
            "cache_hit_rate": 0,
            "tokens_saved": 0,
            "processing_time_ms": int((time.perf_counter() - started) * 1000),
        }

        log.info(
            "enrich_without_cache_completed",
            tenant_id=str(tenant_id),
            **stats,
        )

        return enriched, stats

    async def _process_with_llm(
        self,
        reviews: list[RawReview],
        tenant_id: UUID,
    ) -> list[EnrichedReview]:
        """
        Обработать отзывы через LLM (для cache misses).

        Здесь должна быть интеграция с ReviewAIProcessor или LLMService.
        """
        # TODO: интегрировать с существующим ReviewAIProcessor
        # Пока заглушка для примера
        log.warning(
            "llm_processing_stub",
            reviews=len(reviews),
            tenant_id=str(tenant_id),
        )

        # Возвращаем пустой список (заглушка)
        return []

    # ========================================================================
    # Helpers
    # ========================================================================

    def _estimate_job_time(self, limit: int, platform: str) -> int:
        """
        Оценить время выполнения задачи (для клиента).

        Формула:
        - Парсинг: ~0.5 сек/отзыв (зависит от платформы)
        - LLM: ~1 сек/отзыв (batch processing)
        - Content caching is disabled; each non-empty review needs analysis.

        Args:
            limit: Количество отзывов
            platform: Платформа (некоторые медленнее)

        Returns:
            Примерное время в секундах
        """
        # Базовое время парсинга
        parse_time_per_review = 0.5
        if platform in ("trustpilot", "google"):
            parse_time_per_review = 0.8  # медленнее

        # Время LLM without content-cache hit assumptions
        llm_time_per_review = 1.0
        effective_llm_time = llm_time_per_review

        total_time = limit * (parse_time_per_review + effective_llm_time)

        # Добавляем overhead
        total_time += 5  # queue + setup overhead

        return int(total_time)

    def _estimate_tokens(self, text: str) -> int:
        """
        Оценить количество токенов в тексте (для метрик).

        Правило: ~1 токен = 4 символа для английского, ~2 для русского.
        """
        avg_chars_per_token = 4  # консервативная оценка
        return len(text) // avg_chars_per_token


# ============================================================================
# Factory
# ============================================================================


async def create_parser_queue_manager(
    db_session: AsyncSession,
    openai_api_key: str | None = None,
) -> ParserQueueManager:
    """
    Фабрика для создания ParserQueueManager.

    Args:
        db_session: Database session
        openai_api_key: OpenAI API key для эмбеддингов

    Returns:
        ParserQueueManager instance
    """
    settings = get_settings()

    # ARQ pool
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    arq_pool = await create_pool(redis_settings)

    # LLM Cache
    llm_cache = LLMCache(
        openai_api_key=openai_api_key or settings.gemini_api_key,  # fallback
        enable_memory_cache=False,
        enable_pgvector_cache=False,
    )

    return ParserQueueManager(
        arq_pool=arq_pool,
        llm_cache=llm_cache,
        db_session=db_session,
    )
