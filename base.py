import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from app.services.scrapers.errors import ScraperPermanentError
from app.services.scrapers.platforms import PLATFORM_DOMAINS, host_allowed
from app.services.scrapers.schemas import RawReviewSchema

logger = logging.getLogger("arq.scrapers")

ItemMapper = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class BaseReviewScraper(ABC):
    """Контракт адаптера площадки: URL карточки -> список нормализованных отзывов.

    Ошибки только из app.services.scrapers.errors:
      ScraperTransientError / ScraperBlockedError  -> воркер повторит задачу
      ScraperPermanentError                        -> без повторов
    """

    def __init__(self, platform: str) -> None:
        if platform not in PLATFORM_DOMAINS:
            raise ValueError(f"Unknown platform: {platform!r}")
        self.platform = platform

    @abstractmethod
    async def scrape(
        self, platform_url: str, limit: int = 50
    ) -> list[RawReviewSchema]: ...

    def ensure_url_allowed(self, platform_url: str) -> None:
        """SSRF-защита: воркер ходит только на домены своей площадки."""
        if not host_allowed(platform_url, self.platform):
            raise ScraperPermanentError(
                f"URL does not belong to platform {self.platform!r}"
            )

    def normalize(
        self,
        items: Iterable[Mapping[str, Any]],
        limit: int,
        mapper: ItemMapper | None = None,
    ) -> list[RawReviewSchema]:
        """Сырые элементы площадки -> RawReviewSchema.

        Битые элементы пропускаются (одна кривая запись не должна ронять сбор),
        но если не прошёл НИ ОДИН, значит поменялась вёрстка/формат: это
        ScraperPermanentError, чтобы заметить поломку, а не сохранять пустоту.
        """
        reviews: list[RawReviewSchema] = []
        total = skipped = 0
        for item in items:
            total += 1
            try:
                data = mapper(item) if mapper else item
                reviews.append(RawReviewSchema.model_validate(data))
            # pydantic.ValidationError является подклассом ValueError
            except (KeyError, TypeError, ValueError) as exc:
                skipped += 1
                logger.warning(
                    "%s: skipped invalid review: %s", self.platform, type(exc).__name__
                )
            if len(reviews) >= limit:
                break

        if total and not reviews:
            raise ScraperPermanentError(
                f"{self.platform}: none of {total} items could be parsed "
                "(page format probably changed)"
            )
        if skipped:
            logger.info(
                "%s: parsed=%d skipped=%d", self.platform, len(reviews), skipped
            )
        return reviews
