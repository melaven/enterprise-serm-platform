from collections.abc import Callable
from functools import partial

from app.application.scrapers.base import BaseReviewScraper
from app.application.scrapers.errors import ScraperPermanentError
from app.application.scrapers.mock import MockReviewScraper
from app.application.scrapers.platforms import PLATFORMS

ScraperFactory = Callable[[], BaseReviewScraper]

# Пока реальных адаптеров нет, все площадки обслуживает Mock.
# Реальный адаптер подключается одной строкой:
#   register_scraper("yandex", YandexMapsScraper)
_FACTORIES: dict[str, ScraperFactory] = {
    platform: partial(MockReviewScraper, platform) for platform in PLATFORMS
}


def register_scraper(platform: str, factory: ScraperFactory) -> None:
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform: {platform!r}")
    _FACTORIES[platform] = factory


def get_scraper(platform: str) -> BaseReviewScraper:
    try:
        factory = _FACTORIES[platform]
    except KeyError:
        raise ScraperPermanentError(f"Unsupported platform: {platform!r}") from None
    return factory()
