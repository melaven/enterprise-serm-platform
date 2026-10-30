from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import structlog
from arq.worker import Retry
from pydantic import ValidationError

from app.core.config import get_settings
from app.api.schemas.parser import ParseJobPayload, ParseResult
from app.application.scraping import PermanentScrapeError, RetryableScrapeError, ReviewScraper
from app.application.sink import ReviewSink

log = structlog.get_logger(__name__)


def compute_backoff(
    attempt: int, *, base: float, cap: float, hint: float | None = None
) -> float:
    """Экспонента с full-jitter; Retry-After площадки — нижняя граница."""
    ceiling = min(cap, base * 2 ** (attempt - 1))
    delay = random.uniform(base, max(base, ceiling))
    return min(cap, max(delay, hint or 0.0))


async def parse_reviews(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Задача ARQ: скрейпинг → сохранение.

    Семантика ошибок:
      * невалидный payload / PermanentScrapeError → исключение, БЕЗ повтора;
      * RetryableScrapeError / таймаут → arq.Retry с backoff, пока есть попытки;
      * последняя попытка → исключение (задача в статусе failed).
    """
    settings = get_settings()
    job_try: int = ctx["job_try"]
    job_id: str = ctx["job_id"]

    try:
        job = ParseJobPayload.model_validate(payload)
    except ValidationError:
        log.error("parse.invalid_payload", job_id=job_id)
        raise

    bound = log.bind(
        job_id=job_id,
        tenant_id=str(job.tenant_id),
        platform=job.platform.value,
        attempt=job_try,
    )
    bound.info("parse.started", url=job.url)

    scraper: ReviewScraper = ctx["scraper"]
    sink: ReviewSink = ctx["sink"]
    started = time.perf_counter()

    try:
        async with asyncio.timeout(settings.scrape_timeout_s):
            reviews = await scraper.fetch(job.platform, job.url, limit=job.max_reviews)
        saved = await sink.save_many(job.tenant_id, reviews)

    except (RetryableScrapeError, TimeoutError) as exc:
        hint = exc.retry_after_s if isinstance(exc, RetryableScrapeError) else None
        if job_try >= settings.worker_max_tries:
            bound.error(
                "parse.failed_retries_exhausted", error=str(exc) or type(exc).__name__
            )
            raise
        delay = compute_backoff(
            job_try,
            base=settings.retry_base_delay_s,
            cap=settings.retry_max_delay_s,
            hint=hint,
        )
        bound.warning(
            "parse.retry", error=str(exc) or type(exc).__name__, defer_s=round(delay, 1)
        )
        raise Retry(defer=delay) from exc

    except PermanentScrapeError as exc:
        bound.error("parse.failed_permanent", error=str(exc))
        raise

    except asyncio.CancelledError:
        bound.warning("parse.cancelled")  # abort или job_timeout ARQ: пробрасываем
        raise

    except Exception:
        bound.exception("parse.unexpected_error")  # баг/БД: повторять вслепую не будем
        raise

    result = ParseResult(
        reviews_found=len(reviews),
        reviews_saved=saved,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    bound.info("parse.finished", **result.model_dump())
    return result.model_dump()
