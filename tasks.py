import logging
from typing import Any
from uuid import UUID

from arq import Retry
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.tenant import tenant_session
from app.repositories.review_repository import ReviewRepository
from app.services.parser import DEFAULT_LIMIT, collect_reviews
from app.services.review_ingest_service import ReviewIngestService
from app.services.scrapers import ScraperPermanentError, ScraperTransientError

# Под "arq.*", чтобы записи были видны в логах воркера (arq настраивает только
# свой namespace).
logger = logging.getLogger("arq.reviews")


async def fetch_reviews_task(
    ctx: dict[str, Any], company_id: UUID, platform: str, url: str
) -> dict[str, Any]:
    """Собирает отзывы адаптером площадки и сохраняет их под RLS компании."""
    # 1) Сеть: БЕЗ открытой транзакции, чтобы не держать соединение из пула
    #    на время медленного сбора.
    try:
        reviews = await collect_reviews(platform, url, limit=DEFAULT_LIMIT)
    except ScraperTransientError as exc:
        # Таймаут / сеть / 5xx / блок: повтор с нарастающей паузой
        # (лимит попыток: max_tries в WorkerSettings).
        defer = ctx["job_try"] * 15  # 15с, 30с, 45с ...
        logger.warning(
            "company=%s platform=%s transient error, retry in %ss: %s",
            company_id,
            platform,
            defer,
            exc,
        )
        raise Retry(defer=defer) from exc
    except ScraperPermanentError as exc:
        # Повтор бесполезен: исключение уйдёт в job failed без ретраев.
        logger.error(
            "company=%s platform=%s permanent error: %s", company_id, platform, exc
        )
        raise

    # 2) БД: одна транзакция, первым statement set_config('app.company_id', ..., true),
    #    дальше INSERT проходит USING/WITH CHECK политики tenant_isolation.
    factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    async with tenant_session(factory, company_id) as session:
        inserted = await ReviewIngestService(ReviewRepository(session)).store(
            platform=platform, url=url, reviews=reviews
        )

    logger.info(
        "company=%s platform=%s collected=%d inserted=%d",
        company_id,
        platform,
        len(reviews),
        inserted,
    )
    return {
        "company_id": str(company_id),
        "platform": platform,
        "collected": len(reviews),
        "inserted": inserted,
    }
