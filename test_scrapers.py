import random
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

import pytest

from app.services.parser import collect_reviews
from app.services.scrapers import (
    PLATFORMS,
    BaseReviewScraper,
    MockReviewScraper,
    RawReviewSchema,
    ScraperBlockedError,
    ScraperPermanentError,
    ScraperTransientError,
    get_scraper,
    register_scraper,
)
from app.services.scrapers.headers import USER_AGENTS, build_headers
from app.services.scrapers.http_scraper import HttpReviewScraper
from app.services.scrapers.mock import _map_otzovik
from app.services.scrapers.platforms import host_allowed
from app.services.scrapers.schemas import to_utc

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
URLS = {
    "google": "https://www.google.com/maps/place/Cafe/@55.7,37.6",
    "yandex": "https://yandex.ru/maps/org/cafe/1234567/reviews/",
    "2gis": "https://2gis.ru/moscow/firm/70000001/tab/reviews",
    "otzovik": "https://otzovik.com/reviews/cafe_moscow/",
}


def mock(platform: str, **kwargs: Any) -> MockReviewScraper:
    return MockReviewScraper(platform, latency=0, clock=lambda: NOW, **kwargs)


# --- MockReviewScraper -------------------------------------------------------
@pytest.mark.parametrize("platform", PLATFORMS)
async def test_mock_returns_valid_normalized_reviews(platform: str) -> None:
    reviews = await mock(platform).scrape(URLS[platform], limit=30)

    assert 1 <= len(reviews) <= 30
    assert all(isinstance(r, RawReviewSchema) for r in reviews)
    for r in reviews:
        assert r.published_at.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
        assert 1 <= r.rating <= 5
        # Мусор из «вёрстки» (NBSP, zero-width, края) вычищен схемой.
        for value in (r.author_name, r.text):
            assert value == value.strip()
            assert " " not in value
            assert "​" not in value
        assert r.metadata["source"] == platform
    dates = [r.published_at for r in reviews]
    assert dates == sorted(dates, reverse=True)  # от новых к старым


@pytest.mark.parametrize("platform", PLATFORMS)
async def test_mock_is_deterministic_for_same_url(platform: str) -> None:
    first = await mock(platform).scrape(URLS[platform], limit=25)
    second = await mock(platform).scrape(URLS[platform], limit=25)

    assert [r.external_id for r in first] == [r.external_id for r in second]
    assert len({r.external_id for r in first}) == len(first)  # уникальны
    assert first == second


async def test_mock_different_urls_give_different_ids() -> None:
    a = await mock("yandex").scrape(URLS["yandex"], limit=5)
    b = await mock("yandex").scrape(URLS["yandex"] + "?other", limit=5)

    assert {r.external_id for r in a}.isdisjoint({r.external_id for r in b})


async def test_mock_respects_limit_and_validates_it() -> None:
    assert len(await mock("google").scrape(URLS["google"], limit=3)) == 3
    with pytest.raises(ValueError, match="limit"):
        await mock("google").scrape(URLS["google"], limit=0)


async def test_mock_propagates_configured_failure() -> None:
    scraper = mock("google", fail_with=ScraperTransientError("boom"))

    with pytest.raises(ScraperTransientError, match="boom"):
        await scraper.scrape(URLS["google"])


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/maps",
        "https://yandex.ru.evil.com/maps",  # домен-двойник
        "http://169.254.169.254/latest/meta-data",  # SSRF в metadata-сервис
        "ftp://yandex.ru/x",
        "not a url",
    ],
)
async def test_foreign_url_rejected(url: str) -> None:
    with pytest.raises(ScraperPermanentError):
        await mock("yandex").scrape(url)


def test_otzovik_naive_moscow_time_converted_to_utc() -> None:
    mapped = _map_otzovik(
        {
            "id": "1",
            "nick": "a",
            "grade": "5",
            "body": "t",
            "date": "2026-10-09 15:00:00",
        }
    )

    assert to_utc(mapped["published_at"]) == datetime(
        2026, 10, 9, 12, 0, tzinfo=timezone.utc
    )


def test_unknown_platform_rejected_by_constructor() -> None:
    with pytest.raises(ValueError, match="Unknown platform"):
        MockReviewScraper("tripadvisor")


# --- normalize ---------------------------------------------------------------
GOOD: dict[str, Any] = {
    "external_id": "1",
    "rating": 5,
    "published_at": "2026-01-01T00:00:00Z",
}


def test_normalize_skips_bad_items_but_keeps_good() -> None:
    scraper = mock("google")
    items = [
        GOOD,
        {"external_id": "2"},
        {**GOOD, "external_id": "3", "rating": 9},
        {**GOOD, "external_id": "4"},
    ]

    result = scraper.normalize(items, limit=10)

    assert [r.external_id for r in result] == ["1", "4"]


def test_normalize_raises_when_nothing_parses() -> None:
    with pytest.raises(ScraperPermanentError, match="format probably changed"):
        mock("google").normalize([{"junk": 1}, {"junk": 2}], limit=10)


def test_normalize_empty_input_is_not_an_error() -> None:
    assert mock("google").normalize([], limit=10) == []


# --- реестр ------------------------------------------------------------------
def test_registry_returns_mock_for_all_platforms_and_rejects_unknown() -> None:
    for platform in PLATFORMS:
        scraper = get_scraper(platform)
        assert isinstance(scraper, MockReviewScraper)
        assert scraper.platform == platform
    with pytest.raises(ScraperPermanentError, match="Unsupported"):
        get_scraper("tripadvisor")


def test_register_scraper_swaps_implementation() -> None:
    from app.services.scrapers import registry

    original = registry._FACTORIES["otzovik"]
    try:
        register_scraper("otzovik", lambda: mock("otzovik", fail_with=None))
        assert get_scraper("otzovik")._clock() == NOW  # type: ignore[attr-defined]
    finally:
        registry._FACTORIES["otzovik"] = original
    with pytest.raises(ValueError):
        register_scraper("tripadvisor", lambda: mock("google"))


# --- collect_reviews (сервис) -------------------------------------------------
class StubScraper(BaseReviewScraper):
    def __init__(self, reviews: list[RawReviewSchema]) -> None:
        super().__init__("google")
        self._reviews = reviews
        self.received: tuple[str, int] | None = None

    async def scrape(self, platform_url: str, limit: int = 50) -> list[RawReviewSchema]:
        self.received = (platform_url, limit)
        return self._reviews


def raw(external_id: str) -> RawReviewSchema:
    return RawReviewSchema(**{**GOOD, "external_id": external_id})


async def test_collect_reviews_dedupes_preserving_order_and_applies_limit() -> None:
    stub = StubScraper([raw("a"), raw("b"), raw("a"), raw("c"), raw("d")])

    result = await collect_reviews("google", URLS["google"], limit=3, scraper=stub)

    assert [r.external_id for r in result] == ["a", "b", "c"]
    assert stub.received == (URLS["google"], 3)


async def test_collect_reviews_uses_registry_by_default() -> None:
    result = await collect_reviews("yandex", URLS["yandex"], limit=5)

    assert 1 <= len(result) <= 5


async def test_collect_reviews_unknown_platform_is_permanent_error() -> None:
    with pytest.raises(ScraperPermanentError):
        await collect_reviews("tripadvisor", "https://tripadvisor.com/x")


# --- каркас HttpReviewScraper (пагинация) ---------------------------------------
class FakeClient:
    def __init__(self, pages: Sequence[Any]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, str | None]] = []

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get_json(
        self, url: str, *, referer: str | None = None, params: Any = None
    ) -> Any:
        self.calls.append((url, referer))
        page = int(url.rsplit("=", 1)[1])
        value = self.pages[page] if page < len(self.pages) else {"items": []}
        if isinstance(value, Exception):
            raise value
        return value


class FakeHttpScraper(HttpReviewScraper):
    page_delay = (0.0, 0.0)

    def __init__(self, client: FakeClient) -> None:
        super().__init__("yandex", client_factory=lambda: client)  # type: ignore[arg-type, return-value]

    def build_page_url(self, platform_url: str, page: int) -> str:
        return f"{platform_url}?page={page}"

    def extract_items(self, payload: Any) -> list[Mapping[str, Any]]:
        return list(payload["items"])

    def map_item(self, item: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "external_id": item["id"],
            "rating": item["r"],
            "text": item["t"],
            "published_at": "2026-01-01T00:00:00Z",
        }


def page(*ids: str) -> dict[str, Any]:
    return {"items": [{"id": i, "r": 5, "t": f" text {i} "} for i in ids]}


async def test_http_scraper_paginates_until_empty_page() -> None:
    client = FakeClient([page("1", "2"), page("3"), {"items": []}, page("never")])

    result = await FakeHttpScraper(client).scrape(URLS["yandex"], limit=50)

    assert [r.external_id for r in result] == ["1", "2", "3"]
    assert result[0].text == "text 1"  # очистка применена
    assert len(client.calls) == 3
    assert all(referer == URLS["yandex"] for _, referer in client.calls)


async def test_http_scraper_stops_when_limit_reached() -> None:
    client = FakeClient([page("1", "2"), page("3", "4"), page("5", "6")])

    result = await FakeHttpScraper(client).scrape(URLS["yandex"], limit=3)

    assert [r.external_id for r in result] == ["1", "2", "3"]
    assert len(client.calls) == 2  # третью страницу не запрашивали


@pytest.mark.parametrize(
    "error_type", [ScraperTransientError, ScraperBlockedError, ScraperPermanentError]
)
async def test_http_scraper_propagates_client_errors(
    error_type: type[Exception],
) -> None:
    client = FakeClient([page("1"), error_type("fail")])

    with pytest.raises(error_type, match="fail"):
        await FakeHttpScraper(client).scrape(URLS["yandex"], limit=50)


async def test_http_scraper_checks_url_before_any_request() -> None:
    client = FakeClient([page("1")])

    with pytest.raises(ScraperPermanentError):
        await FakeHttpScraper(client).scrape("https://evil.example.com/x")
    assert client.calls == []


def test_blocked_is_a_transient_error() -> None:
    assert issubclass(ScraperBlockedError, ScraperTransientError)
    assert not issubclass(ScraperPermanentError, ScraperTransientError)


# --- заголовки и домены ------------------------------------------------------------
def test_headers_rotate_user_agent_and_set_browser_basics() -> None:
    rng = random.Random(1)
    seen = {build_headers(rng=rng)["User-Agent"] for _ in range(60)}

    assert len(seen) > 1
    assert seen <= set(USER_AGENTS)
    headers = build_headers(referer="https://yandex.ru/maps")
    assert headers["Referer"] == "https://yandex.ru/maps"
    assert "Accept-Language" in headers
    assert "br" not in headers["Accept-Encoding"]  # httpx без brotli не распакует
    assert "Referer" not in build_headers()


@pytest.mark.parametrize(
    ("url", "platform", "allowed"),
    [
        ("https://maps.google.com/x", "google", True),
        ("https://goo.gl/maps/abc", "google", True),
        ("https://yandex.ru/maps", "yandex", True),
        ("https://yandex.ru/maps", "google", False),
        ("https://notyandex.ru/maps", "yandex", False),
        ("https://google.com.evil.com", "google", False),
        ("javascript:alert(1)", "google", False),
    ],
)
def test_host_allowed(url: str, platform: str, allowed: bool) -> None:
    assert host_allowed(url, platform) is allowed
