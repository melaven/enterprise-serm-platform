"""Оркестрация сбора: выбор адаптера площадки + постобработка выдачи."""

from app.services.scrapers import BaseReviewScraper, RawReviewSchema, get_scraper

DEFAULT_LIMIT = 50


async def collect_reviews(
    platform: str,
    url: str,
    *,
    limit: int = DEFAULT_LIMIT,
    scraper: BaseReviewScraper | None = None,
) -> list[RawReviewSchema]:
    """Адаптер площадки -> нормализованные отзывы без дублей, не больше `limit`.

    Ошибки адаптера пробрасываются как есть (ScraperTransientError / Permanent):
    решение о повторе принимает ARQ-задача.
    """
    adapter = scraper or get_scraper(platform)
    reviews = await adapter.scrape(url, limit)

    seen: set[str] = set()
    unique: list[RawReviewSchema] = []
    for review in reviews:
        # Площадки иногда повторяют отзыв на стыке страниц.
        if review.external_id in seen:
            continue
        seen.add(review.external_id)
        unique.append(review)
    return unique[:limit]
