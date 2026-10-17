"""Главный оркестратор: sync_platform_reviews = скрейпинг → AI → сохранение → биллинг.

Инварианты:
  * Сбой LLM НИКОГДА не роняет задачу: отзывы сохраняются с ai_pending=True,
    дообработку делает retry_pending_ai_reviews.
  * Платим за AI только за новые отзывы: уже известные external_id отсекаются до LLM.
  * Сохранение идемпотентно (ON CONFLICT DO NOTHING), поэтому Retry всей задачи безопасен.
  * Биллинг идёт ПОСЛЕ сохранения и только за реально вставленные строки; его сбой
    не откатывает данные и не ретраит задачу (иначе риск двойного списания).
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from uuid import UUID

import structlog
from arq.worker import Retry

from app.core.config import Settings, get_settings
from app.schemas.parser import ParseResult, Platform, host_allowed
from app.services.ai_processor import EnrichedReview
from app.services.scraping import (
    PermanentScrapeError,
    RawReview,
    RetryableScrapeError,
    ReviewScraper,
)
from app.services.sink import QuotaBilling, ReviewSink

log = structlog.get_logger(__name__)

Sleep = Callable[[float], Awaitable[None]]


def compute_backoff(
    attempt: int, *, base: float, cap: float, hint: float | None = None
) -> float:
    """Экспонента с full-jitter; Retry-After площадки — нижняя граница."""
    ceiling = min(cap, base * 2 ** (attempt - 1))
    delay = random.uniform(base, max(base, ceiling))
    return min(cap, max(delay, hint or 0.0))


def _pending(review: RawReview, reason: str) -> EnrichedReview:
    return EnrichedReview(review, None, (), None, False, True, reason)


# ── Этапы ────────────────────────────────────────────────────────────────────


async def _scrape(
    ctx: dict[str, Any],
    platform: Platform,
    url: str,
    settings: Settings,
    job_try: int,
    blog: Any,
) -> list[RawReview]:
    scraper: ReviewScraper = ctx["scraper"]
    try:
        async with asyncio.timeout(settings.scrape_timeout_s):
            return await scraper.fetch(platform, url, limit=settings.sync_max_reviews)
    except (RetryableScrapeError, TimeoutError) as exc:
        hint = exc.retry_after_s if isinstance(exc, RetryableScrapeError) else None
        reason = str(exc) or type(exc).__name__
        if job_try >= settings.worker_max_tries:
            blog.error("sync.scrape_failed_retries_exhausted", error=reason)
            raise
        delay = compute_backoff(
            job_try,
            base=settings.retry_base_delay_s,
            cap=settings.retry_max_delay_s,
            hint=hint,
        )
        blog.warning("sync.scrape_retry", error=reason, defer_s=round(delay, 1))
        raise Retry(defer=delay) from exc
    except PermanentScrapeError as exc:
        blog.error("sync.scrape_failed_permanent", error=str(exc))
        raise


async def _drop_known(
    sink: ReviewSink,
    tenant_id: UUID,
    platform: Platform,
    reviews: list[RawReview],
    blog: Any,
) -> list[RawReview]:
    """Не тратим токены на отзывы, которые уже в БД. Best-effort: при сбое идём дальше,
    дубликаты всё равно отсечёт ON CONFLICT."""
    try:
        known = await sink.existing_external_ids(
            tenant_id, platform, [r.external_id for r in reviews]
        )
    except Exception:
        blog.exception("sync.dedup_lookup_failed")
        return reviews
    fresh = [r for r in reviews if r.external_id not in known]
    blog.info(
        "sync.dedup",
        scraped=len(reviews),
        known=len(reviews) - len(fresh),
        new=len(fresh),
    )
    return fresh


async def _enrich(
    ctx: dict[str, Any], reviews: list[RawReview], settings: Settings, blog: Any
) -> list[EnrichedReview]:
    """Любой сбой AI → все отзывы уходят дальше с ai_pending=True. Не бросает (кроме отмены)."""
    processor = ctx.get("ai_processor")
    if processor is None:
        blog.warning("sync.ai_disabled")
        return [_pending(r, "ai_disabled") for r in reviews]
    try:
        async with asyncio.timeout(settings.sync_ai_timeout_s):
            enriched: list[EnrichedReview] = await processor.process(reviews)
    except TimeoutError:
        blog.error("sync.ai_timeout", timeout_s=settings.sync_ai_timeout_s)
        return [_pending(r, "processing_timeout") for r in reviews]
    except Exception:
        blog.exception("sync.ai_crashed")
        return [_pending(r, "internal_error") for r in reviews]

    if len(enriched) != len(reviews) or any(
        e.review.external_id != r.external_id
        for e, r in zip(enriched, reviews, strict=False)
    ):
        blog.error(
            "sync.ai_contract_violation", expected=len(reviews), got=len(enriched)
        )
        return [_pending(r, "internal_error") for r in reviews]
    return enriched


async def _save(
    sink: ReviewSink,
    tenant_id: UUID,
    enriched: Sequence[EnrichedReview],
    settings: Settings,
    job_try: int,
    sleep: Sleep,
    blog: Any,
) -> int:
    """Короткие локальные ретраи (транзиентные сбои БД), чтобы не повторять скрейпинг и
    не платить за AI заново. Исчерпали → Retry всей задачи (запись идемпотентна)."""
    last: Exception | None = None
    for attempt in range(1, settings.sync_save_attempts + 1):
        try:
            return await sink.save_many(tenant_id, enriched)
        except Exception as exc:
            last = exc
            blog.warning("sync.save_failed", attempt=attempt, error=type(exc).__name__)
            if attempt < settings.sync_save_attempts:
                await sleep(min(2.0**attempt, 10.0) * random.uniform(0.5, 1.0))
    assert last is not None
    if job_try >= settings.worker_max_tries:
        blog.error("sync.save_failed_retries_exhausted")
        raise last
    delay = compute_backoff(
        job_try, base=settings.retry_base_delay_s, cap=settings.retry_max_delay_s
    )
    blog.error("sync.save_retry_job", defer_s=round(delay, 1))
    raise Retry(defer=delay) from last


async def _bill(
    ctx: dict[str, Any],
    tenant_id: UUID,
    saved: int,
    enriched: Sequence[EnrichedReview],
    blog: Any,
) -> None:
    billing: QuotaBilling | None = ctx.get("billing")
    if billing is None or saved <= 0:
        return
    try:
        await billing.charge(tenant_id, reviews_saved=saved, enriched=enriched)
        blog.info("sync.billed", reviews_saved=saved)
    except Exception:
        # Данные уже сохранены. Не откатываем и не ретраим: повтор дал бы saved=0,
        # а недосписание лучше потерянных отзывов. Разбирать по этому событию.
        blog.exception("sync.billing_failed", reviews_saved=saved)


# ── Задача ───────────────────────────────────────────────────────────────────


async def sync_platform_reviews(
    ctx: dict[str, Any], tenant_id: UUID, platform: str, url: str
) -> dict[str, Any]:
    settings = get_settings()
    job_try: int = ctx.get("job_try", 1)
    sleep: Sleep = ctx.get("sleep", asyncio.sleep)
    started = time.perf_counter()

    blog = log.bind(
        job_id=ctx.get("job_id"),
        tenant_id=str(tenant_id),
        platform=platform,
        attempt=job_try,
    )

    # Входные данные не доверенные: невалидное → сразу ошибка без повторов и сетевых вызовов.
    try:
        platform_enum = Platform(platform)
    except ValueError:
        blog.error("sync.invalid_platform")
        raise
    if not host_allowed(url, platform_enum):
        blog.error("sync.invalid_host", url=url)
        raise ValueError("url host does not belong to platform")

    sink: ReviewSink = ctx["sink"]
    blog.info("sync.started", url=url)

    # 1. Скрейпинг
    scraped = await _scrape(ctx, platform_enum, url, settings, job_try, blog)
    if not scraped:
        blog.info("sync.nothing_scraped")
        return _result(0, 0, 0, [], started)

    # 2. Только новые → AI (сбой AI → ai_pending=True)
    fresh = await _drop_known(sink, tenant_id, platform_enum, scraped, blog)
    if not fresh:
        return _result(len(scraped), 0, 0, [], started)
    enriched = await _enrich(ctx, fresh, settings, blog)

    # 3. Сохранение
    saved = await _save(sink, tenant_id, enriched, settings, job_try, sleep, blog)

    # 4. Биллинг за фактически сохранённое
    await _bill(ctx, tenant_id, saved, enriched, blog)

    result = _result(len(scraped), len(fresh), saved, enriched, started)
    blog.info("sync.finished", **result)
    return result


def _result(
    found: int, new: int, saved: int, enriched: Sequence[EnrichedReview], started: float
) -> dict[str, Any]:
    pending = sum(1 for e in enriched if e.ai_pending)
    return ParseResult(
        reviews_found=found,
        reviews_new=new,
        reviews_saved=saved,
        ai_enriched=len(enriched) - pending,
        ai_pending=pending,
        duration_ms=int((time.perf_counter() - started) * 1000),
    ).model_dump()
