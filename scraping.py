"""Скрейпинг отзывов через httpx: профили браузера, ручные редиректы, классификация ошибок.

Реализовано для Trustpilot (отзывы лежат в `<script id="__NEXT_DATA__">` как JSON,
HTML-вёрстку разбирать не нужно). Новая площадка = функция-парсер + запись в `_PARSERS`.

Принципы:
  * 429 и 5xx — RetryableScrapeError (с Retry-After), 401/403/404/410 — PermanentScrapeError.
    Блокировку (403, капча/challenge) НЕ обходим: ни ротации прокси «до победы», ни
    подбора заголовков под защиту — только вежливый трафик и честный отказ.
  * Редиректы идут вручную: каждый следующий хост проверяется на принадлежность площадке (SSRF).
  * Любая ошибка после ≥1 успешной страницы возвращает уже собранное (fetch.partial):
    прогресс не теряется, а sink идемпотентен.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Final, Protocol

import httpx
import structlog

from app.schemas.parser import Platform, host_allowed

log = structlog.get_logger(__name__)

MAX_TEXT_LEN: Final = 10_000
MAX_REDIRECTS: Final = 3
_NEXT_DATA_RE: Final = re.compile(
    r'<script[^>]*\bid="__NEXT_DATA__"[^>]*>(?P<json>.*?)</script>', re.DOTALL
)
_CHALLENGE_MARKERS: Final = (
    "captcha",
    "just a moment",
    "cf-challenge",
    "access denied",
    "are you a robot",
)


# ── Модели и ошибки ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RawReview:
    external_id: str  # стабильный ID на площадке: ключ дедупликации
    platform: Platform
    author_name: str | None
    rating: int | None
    text: str
    published_at: datetime | None


class ScrapeError(Exception):
    """База ошибок скрейпинга."""


class RetryableScrapeError(ScrapeError):
    """Временный сбой (сеть, 429, 5xx): задачу стоит повторить с задержкой."""

    def __init__(self, message: str, *, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class PermanentScrapeError(ScrapeError):
    """Повтор бессмысленен (403/404/410, challenge, изменилась вёрстка)."""


class ReviewScraper(Protocol):
    async def fetch(
        self, platform: Platform, url: str, *, limit: int
    ) -> list[RawReview]: ...


# ── Профили браузера ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class BrowserProfile:
    """Согласованный набор: UA и client-hints обязаны соответствовать друг другу."""

    name: str
    user_agent: str
    sec_ch_ua: str | None = None  # только Chromium
    sec_ch_ua_platform: str | None = None
    accept_language: str = "en-US,en;q=0.9"


DEFAULT_PROFILES: Final[tuple[BrowserProfile, ...]] = (
    BrowserProfile(
        "chrome-win",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36",
        '"Chromium";v="141", "Not?A_Brand";v="8", "Google Chrome";v="141"',
        '"Windows"',
    ),
    BrowserProfile(
        "chrome-mac",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36",
        '"Chromium";v="141", "Not?A_Brand";v="8", "Google Chrome";v="141"',
        '"macOS"',
    ),
    BrowserProfile(
        "firefox-win",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0",
    ),
    BrowserProfile(
        "safari-mac",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.5 Safari/605.1.15",
    ),
)


def build_headers(profile: BrowserProfile, *, referer: str | None) -> dict[str, str]:
    """Заголовки навигационного запроса обычного браузера."""
    headers = {
        "User-Agent": profile.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": profile.accept_language,
        # br не объявляем: без brotli-пакета httpx не распакует ответ.
        "Accept-Encoding": "gzip, deflate",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Sec-Fetch-User": "?1",
    }
    if referer:
        headers["Referer"] = referer
    if profile.sec_ch_ua:
        headers["Sec-CH-UA"] = profile.sec_ch_ua
        headers["Sec-CH-UA-Mobile"] = "?0"
        if profile.sec_ch_ua_platform:
            headers["Sec-CH-UA-Platform"] = profile.sec_ch_ua_platform
    return headers


# ── Конфигурация ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ScraperConfig:
    timeout_s: float = 30.0
    connect_timeout_s: float = 10.0
    proxy_url: str | None = None
    max_pages: int = 50
    page_delay_range_s: tuple[float, float] = (1.0, 2.5)  # пауза между страницами
    retry_after_cap_s: float = 600.0
    profiles: tuple[BrowserProfile, ...] = field(default=DEFAULT_PROFILES)


# ── Чистые функции разбора ───────────────────────────────────────────────────


def parse_retry_after(
    value: str | None, *, cap_s: float, now: datetime | None = None
) -> float | None:
    """Retry-After: секунды или HTTP-date → секунды, ограниченные cap_s."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return min(float(value), cap_s)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    delta = (when - (now or datetime.now(UTC))).total_seconds()
    return min(max(delta, 0.0), cap_s)


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _parse_rating(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    rating = int(value)
    return rating if 1 <= rating <= 5 else None


@dataclass(frozen=True, slots=True)
class ParsedPage:
    reviews: list[RawReview]
    has_next: bool


def looks_like_challenge(html: str) -> bool:
    head = html[:20_000].lower()
    return any(marker in head for marker in _CHALLENGE_MARKERS)


def parse_trustpilot_page(html: str, platform: Platform) -> ParsedPage:
    """Достаёт отзывы из __NEXT_DATA__. Нет блока → challenge или смена вёрстки."""
    match = _NEXT_DATA_RE.search(html)
    if match is None:
        if looks_like_challenge(html):
            raise PermanentScrapeError("anti-bot challenge page instead of content")
        raise PermanentScrapeError("__NEXT_DATA__ not found: page layout changed")
    try:
        page_props = json.loads(match.group("json"))["props"]["pageProps"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise PermanentScrapeError("unexpected __NEXT_DATA__ structure") from exc

    raw_reviews = page_props.get("reviews")
    if not isinstance(raw_reviews, list):
        raise PermanentScrapeError("pageProps.reviews missing: page layout changed")

    reviews: list[RawReview] = []
    for item in raw_reviews:
        if not isinstance(item, dict) or not item.get("id"):
            continue  # битая запись не должна ронять всю страницу
        consumer = item.get("consumer") or {}
        dates = item.get("dates") or {}
        text = item.get("text")
        title = item.get("title")
        body = " — ".join(
            p.strip() for p in (title, text) if isinstance(p, str) and p.strip()
        )
        reviews.append(
            RawReview(
                external_id=str(item["id"]),
                platform=platform,
                author_name=(consumer.get("displayName") or None),
                rating=_parse_rating(item.get("rating")),
                text=body.replace("\x00", "")[:MAX_TEXT_LEN],
                published_at=_parse_iso(dates.get("publishedDate")),
            )
        )

    pagination = (page_props.get("filters") or {}).get("pagination") or {}
    current, total = pagination.get("currentPage"), pagination.get("totalPages")
    has_next = bool(reviews) and (
        current < total if isinstance(current, int) and isinstance(total, int) else True
    )
    return ParsedPage(reviews=reviews, has_next=has_next)


_PARSERS: Final[dict[Platform, Callable[[str, Platform], ParsedPage]]] = {
    Platform.TRUSTPILOT: parse_trustpilot_page,
    # Яндекс.Карты/2ГИС: данные приходят из внутренних API под CSRF/капчей — подключайте
    # отдельным парсером (или официальным API), в этом классе не поддержаны.
}


# ── Скрейпер ─────────────────────────────────────────────────────────────────


def _with_page(url: str, page: int) -> str:
    return (
        str(httpx.URL(url).copy_merge_params({"page": str(page)})) if page > 1 else url
    )


class HttpxReviewScraper:
    """Свой httpx-клиент на каждый fetch: изолированный cookie-jar, один профиль браузера
    на всю сессию (UA не «прыгает» между страницами), Set-Cookie копится как в браузере."""

    def __init__(
        self,
        config: ScraperConfig | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,  # для тестов (MockTransport)
    ) -> None:
        self._cfg = config or ScraperConfig()
        self._transport = transport

    async def fetch(
        self, platform: Platform, url: str, *, limit: int
    ) -> list[RawReview]:
        parser = _PARSERS.get(platform)
        if parser is None:
            raise PermanentScrapeError(f"platform {platform.value} is not supported")
        if not host_allowed(url, platform):
            raise PermanentScrapeError("url host does not belong to platform")

        profile = random.choice(self._cfg.profiles)
        blog = log.bind(
            platform=platform.value, url=url, profile=profile.name, limit=limit
        )
        blog.info("fetch.started")

        collected: dict[str, RawReview] = {}
        referer: str | None = None
        started = time.perf_counter()

        async with self._client() as client:
            for page in range(1, self._cfg.max_pages + 1):
                page_url = _with_page(url, page)
                try:
                    html = await self._download(
                        client, platform, page_url, profile, referer
                    )
                    parsed = self._parse(platform, html)
                except ScrapeError as exc:
                    if not collected:
                        blog.error(
                            "fetch.failed",
                            page=page,
                            error=str(exc),
                            kind=type(exc).__name__,
                        )
                        raise
                    blog.warning(
                        "fetch.partial",
                        page=page,
                        collected=len(collected),
                        error=str(exc),
                        kind=type(exc).__name__,
                    )
                    break

                new = 0
                for review in parsed.reviews:
                    if review.external_id not in collected:
                        collected[review.external_id] = review
                        new += 1
                blog.info("page.parsed", page=page, found=len(parsed.reviews), new=new)

                if len(collected) >= limit or not parsed.has_next or new == 0:
                    break
                referer = page_url
                await asyncio.sleep(random.uniform(*self._cfg.page_delay_range_s))

        result = list(collected.values())[:limit]
        blog.info(
            "fetch.finished",
            reviews=len(result),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
        return result

    def _client(self) -> httpx.AsyncClient:
        cfg = self._cfg
        return httpx.AsyncClient(
            timeout=httpx.Timeout(cfg.timeout_s, connect=cfg.connect_timeout_s),
            follow_redirects=False,  # редиректы — вручную, с проверкой хоста
            proxy=cfg.proxy_url,
            transport=self._transport,
        )

    async def _download(
        self,
        client: httpx.AsyncClient,
        platform: Platform,
        url: str,
        profile: BrowserProfile,
        referer: str | None,
    ) -> str:
        headers = build_headers(profile, referer=referer)
        current = url

        for hop in range(MAX_REDIRECTS + 1):
            started = time.perf_counter()
            try:
                response = await client.get(current, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                log.warning("http.network_error", url=current, error=type(exc).__name__)
                raise RetryableScrapeError(
                    f"network error: {type(exc).__name__}"
                ) from exc

            code = response.status_code
            log.info(
                "http.response",
                url=current,
                status=code,
                bytes=len(response.content),
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                hop=hop,
            )

            if code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    raise PermanentScrapeError(f"redirect {code} without Location")
                current = str(response.url.join(location))
                if not host_allowed(current, platform):
                    log.warning(
                        "http.redirect_blocked", target_host=httpx.URL(current).host
                    )
                    raise PermanentScrapeError("redirect leaves platform domain")
                continue

            self._raise_for_status(response)
            return response.text

        raise PermanentScrapeError("too many redirects")

    def _raise_for_status(self, response: httpx.Response) -> None:
        code = response.status_code
        retry_after = parse_retry_after(
            response.headers.get("Retry-After"), cap_s=self._cfg.retry_after_cap_s
        )
        if code == 429:
            log.warning("http.rate_limited", retry_after_s=retry_after)
            raise RetryableScrapeError("rate limited (429)", retry_after_s=retry_after)
        if code == 403:
            # Блокировку не обходим: повтор того же трафика только ужесточит бан.
            log.warning("http.forbidden")
            raise PermanentScrapeError("access forbidden (403)")
        if code in (408, 425) or code >= 500:
            raise RetryableScrapeError(f"upstream {code}", retry_after_s=retry_after)
        if 400 <= code < 500:
            raise PermanentScrapeError(f"upstream {code}")
        if code != 200:
            raise PermanentScrapeError(f"unexpected status {code}")

    def _parse(self, platform: Platform, html: str) -> ParsedPage:
        parser = _PARSERS[platform]
        return parser(html, platform)
