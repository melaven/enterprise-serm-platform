"""Парсер 2GIS через HTTP API отзывов (httpx).

Архитектурный выбор: httpx, а не Playwright. Публичный JSON-эндпоинт отзывов
в десятки раз легче браузера (память, CPU, скорость) и не требует рендера.
Playwright имеет смысл как отдельная реализация BaseReviewParser, если
площадка начнёт отдавать данные только после JS-проверки.

ВАЖНО (проверь до выкладки, из песочницы 2GIS недоступен):
  * адрес API, имена полей ответа и параметр пагинации `offset_date`
    взяты из того, как работает веб-версия; они не документированы;
  * ключ API (`key`) выдаёт 2GIS: используй свой, лучше из партнёрской
    программы/официального API, и проверь условия использования данных.
Все допущения собраны в константах и `_map_review`.
"""

import asyncio
import re
from typing import Any, ClassVar
from urllib.parse import urlsplit

import httpx
import structlog
from pydantic import ValidationError

from app.schemas.parser import Platform, RawReview
from app.services.parsers.base import (
    BaseReviewParser,
    InvalidSourceUrlError,
    ParserDataError,
    ParserTransportError,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DEFAULT_API_URL = "https://public-api.reviews.2gis.com/3.0/branches"
SITE_DOMAINS = ("2gis.ru", "2gis.com", "2gis.kz", "2gis.kg", "2gis.ae")
_FIRM_ID = re.compile(r"/(?:firm|branches?)/(\d{5,20})(?:/|$)")
MAX_PAGES = 40  # предохранитель от бесконечной пагинации
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


def parse_branch_id(url: str) -> str:
    """Достаёт ID организации из ссылки 2GIS. Запросы идут ТОЛЬКО на наш API-хост
    по этому ID: URL пользователя никогда не запрашивается (нет SSRF)."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not any(
        host == d or host.endswith(f".{d}") for d in SITE_DOMAINS
    ):
        raise InvalidSourceUrlError(f"not a 2GIS https url: host={host!r}")
    match = _FIRM_ID.search(parts.path)
    if match is None:
        raise InvalidSourceUrlError("2GIS url has no /firm/<id> segment")
    return match.group(1)


def _parse_retry_after(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:  # формат HTTP-date не разбираем
        return None


class TwoGisParser(BaseReviewParser):
    platform: ClassVar[Platform] = Platform.TWOGIS

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        api_url: str = DEFAULT_API_URL,
        page_size: int = 50,
        timeout_s: float = 15.0,
        page_delay_s: float = 0.5,
    ) -> None:
        """client: общий httpx.AsyncClient (его закрывает владелец); если не
        передан, клиент создаётся и закрывается на каждый вызов fetch_reviews."""
        self._api_key = api_key
        self._client = client
        self._api_url = api_url.rstrip("/")
        self._page_size = max(1, min(page_size, 50))
        self._timeout_s = timeout_s
        self._page_delay_s = page_delay_s

    async def fetch_reviews(self, url: str, limit: int) -> list[RawReview]:
        branch_id = parse_branch_id(url)
        self._log_start(url, limit)

        if self._client is not None:
            return await self._collect(self._client, branch_id, limit)
        async with httpx.AsyncClient() as client:
            return await self._collect(client, branch_id, limit)

    # --- внутреннее -----------------------------------------------------------
    async def _collect(
        self, client: httpx.AsyncClient, branch_id: str, limit: int
    ) -> list[RawReview]:
        reviews: dict[str, RawReview] = {}
        skipped = 0
        pages = 0
        offset_date: str | None = None

        while len(reviews) < limit and pages < MAX_PAGES:
            want = min(self._page_size, limit - len(reviews))
            payload = await self._get_json(client, branch_id, want, offset_date)
            pages += 1

            items = payload.get("reviews")
            if not isinstance(items, list):
                self._log_selector_error("reviews", "key missing or not a list")
                raise ParserDataError("2GIS response has no 'reviews' list")
            if not items:
                break

            parsed_on_page = 0
            new_on_page = 0
            for item in items:
                review = self._map_review(item)
                if review is None:
                    skipped += 1
                    continue
                parsed_on_page += 1
                if review.platform_id not in reviews and len(reviews) < limit:
                    reviews[review.platform_id] = review
                    new_on_page += 1

            if parsed_on_page == 0:
                # Вся страница не разобралась: не «пустой филиал», а смена формата.
                raise ParserDataError("none of the 2GIS reviews could be parsed")
            last_date = (
                items[-1].get("date_created") if isinstance(items[-1], dict) else None
            )
            if new_on_page == 0 or len(items) < want or not isinstance(last_date, str):
                break
            offset_date = last_date
            await asyncio.sleep(self._page_delay_s)

        self._log_done(len(reviews), skipped=skipped, pages=pages)
        return list(reviews.values())

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        branch_id: str,
        limit: int,
        offset_date: str | None,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "limit": limit,
            "key": self._api_key,
            "locale": "ru_RU",
            "sort_by": "date_edited",
            "rated": "true",
        }
        if offset_date:
            params["offset_date"] = offset_date

        try:
            response = await client.get(
                f"{self._api_url}/{branch_id}/reviews",
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=self._timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise ParserTransportError("2GIS request timed out") from exc
        except httpx.TransportError as exc:
            raise ParserTransportError(f"2GIS network error: {exc!r}") from exc

        status = response.status_code
        if status in (403, 429) or status >= 500:
            # 403/429: антибот или лимит. Агрессивных обходов здесь нет:
            # отдаём ретраю ARQ с паузой (Retry-After, если прислан).
            logger.warning("parser_blocked_or_unavailable", status_code=status)
            raise ParserTransportError(
                f"2GIS responded {status}",
                status_code=status,
                retry_after=_parse_retry_after(response.headers.get("Retry-After")),
            )
        if status >= 400:
            raise ParserDataError(f"2GIS responded {status} (branch or key rejected)")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ParserDataError("2GIS returned non-JSON body") from exc
        if not isinstance(payload, dict):
            raise ParserDataError("2GIS JSON root is not an object")
        return payload

    def _map_review(self, item: object) -> RawReview | None:
        """Сопоставление полей ответа с RawReview; None, если запись не разобрать."""
        if not isinstance(item, dict):
            self._log_selector_error("review", "item is not an object")
            return None
        user = item.get("user")
        try:
            return RawReview.model_validate(
                {
                    "platform_id": item.get("id"),
                    "author_name": user.get("name") if isinstance(user, dict) else None,
                    "text": item.get("text"),
                    "rating": item.get("rating"),
                    "date": item.get("date_created"),
                    "platform": Platform.TWOGIS,
                }
            )
        except ValidationError as exc:
            self._log_selector_error(
                "review_fields",
                "validation failed",
                errors=exc.errors(
                    include_url=False, include_context=False, include_input=False
                ),
            )
            return None
