"""Каркас для реальных адаптеров: постраничный сбор по HTTP до `limit`.

Чтобы добавить площадку, наследуйся и реализуй три метода:

    class YandexMapsScraper(HttpReviewScraper):
        def __init__(self) -> None:
            super().__init__("yandex")

        def build_page_url(self, platform_url, page): ...   # URL JSON-эндпоинта
        def extract_items(self, payload): ...               # список сырых отзывов
        def map_item(self, item): ...                       # -> поля RawReviewSchema

и зарегистрируй: register_scraper("yandex", YandexMapsScraper).
Соблюдай ToS и robots.txt площадки; где есть официальный API, используй его.
"""

import asyncio
import random
from abc import abstractmethod
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from app.services.scrapers.base import BaseReviewScraper
from app.services.scrapers.schemas import RawReviewSchema

if TYPE_CHECKING:
    from app.services.scrapers.http import ScraperHttpClient

ClientFactory = Callable[[], "ScraperHttpClient"]


def _default_client() -> "ScraperHttpClient":
    # Ленивый импорт: httpx нужен только реальным адаптерам, а не Mock/тестам схем.
    from app.services.scrapers.http import ScraperHttpClient

    return ScraperHttpClient()


class HttpReviewScraper(BaseReviewScraper):
    max_pages: ClassVar[int] = 10
    # Человекоподобная пауза между страницами, сек (min, max).
    page_delay: ClassVar[tuple[float, float]] = (0.5, 1.5)

    def __init__(
        self, platform: str, *, client_factory: ClientFactory | None = None
    ) -> None:
        super().__init__(platform)
        self._client_factory: ClientFactory = client_factory or _default_client

    @abstractmethod
    def build_page_url(self, platform_url: str, page: int) -> str:
        """URL страницы отзывов; page начинается с 0."""

    @abstractmethod
    def extract_items(self, payload: Any) -> list[Mapping[str, Any]]:
        """Достаёт список сырых отзывов из ответа. Пустой список = конец выдачи."""

    @abstractmethod
    def map_item(self, item: Mapping[str, Any]) -> Mapping[str, Any]:
        """Сырой отзыв площадки -> поля RawReviewSchema."""

    async def scrape(self, platform_url: str, limit: int = 50) -> list[RawReviewSchema]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self.ensure_url_allowed(platform_url)

        collected: list[Mapping[str, Any]] = []
        async with self._client_factory() as client:
            for page in range(self.max_pages):
                payload = await client.get_json(
                    self.build_page_url(platform_url, page), referer=platform_url
                )
                items = self.extract_items(payload)
                if not items:
                    break
                collected.extend(items)
                if len(collected) >= limit:
                    break
                await asyncio.sleep(random.uniform(*self.page_delay))

        return self.normalize(collected, limit, mapper=self.map_item)
