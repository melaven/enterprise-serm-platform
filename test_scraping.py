import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.schemas.parser import Platform
from app.services.scraping import (
    DEFAULT_PROFILES,
    HttpxReviewScraper,
    PermanentScrapeError,
    RetryableScrapeError,
    ScraperConfig,
    build_headers,
    parse_retry_after,
    parse_trustpilot_page,
)

URL = "https://www.trustpilot.com/review/example.com"
FAST = ScraperConfig(page_delay_range_s=(0.0, 0.0), max_pages=5)


def page_html(ids: list[str], *, current: int = 1, total: int = 1) -> str:
    reviews = [
        {
            "id": i,
            "title": "Great",
            "text": f"text {i}",
            "rating": 5,
            "dates": {"publishedDate": "2026-03-01T10:00:00.000Z"},
            "consumer": {"displayName": f"user {i}"},
        }
        for i in ids
    ]
    data = {
        "props": {
            "pageProps": {
                "reviews": reviews,
                "filters": {
                    "pagination": {"currentPage": current, "totalPages": total}
                },
            }
        }
    }
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


def scraper(handler) -> HttpxReviewScraper:
    return HttpxReviewScraper(FAST, transport=httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


def test_parse_fields():
    page = parse_trustpilot_page(page_html(["a1"]), Platform.TRUSTPILOT)
    r = page.reviews[0]
    assert (r.external_id, r.author_name, r.rating) == ("a1", "user a1", 5)
    assert r.text == "Great — text a1"
    assert r.published_at == datetime(2026, 3, 1, 10, tzinfo=UTC)
    assert page.has_next is False


def test_layout_change_is_permanent():
    with pytest.raises(PermanentScrapeError, match="layout"):
        parse_trustpilot_page("<html>nothing</html>", Platform.TRUSTPILOT)


def test_challenge_page_is_permanent():
    with pytest.raises(PermanentScrapeError, match="challenge"):
        parse_trustpilot_page("<title>Just a moment...</title>", Platform.TRUSTPILOT)


def test_pagination_collects_and_dedups():
    pages = {
        "1": page_html(["a", "b"], current=1, total=2),
        "2": page_html(["b", "c"], current=2, total=2),
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=pages[req.url.params.get("page", "1")])

    result = run(scraper(handler).fetch(Platform.TRUSTPILOT, URL, limit=100))
    assert [r.external_id for r in result] == ["a", "b", "c"]


def test_limit_truncates():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=page_html(["a", "b", "c"], total=9))

    result = run(scraper(handler).fetch(Platform.TRUSTPILOT, URL, limit=2))
    assert len(result) == 2


def test_429_is_retryable_with_retry_after():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "42"})

    with pytest.raises(RetryableScrapeError) as ei:
        run(scraper(handler).fetch(Platform.TRUSTPILOT, URL, limit=10))
    assert ei.value.retry_after_s == 42.0


def test_403_is_permanent():
    with pytest.raises(PermanentScrapeError, match="403"):
        run(
            scraper(lambda r: httpx.Response(403)).fetch(
                Platform.TRUSTPILOT, URL, limit=10
            )
        )


def test_503_is_retryable():
    with pytest.raises(RetryableScrapeError):
        run(
            scraper(lambda r: httpx.Response(503)).fetch(
                Platform.TRUSTPILOT, URL, limit=10
            )
        )


def test_network_error_is_retryable():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=req)

    with pytest.raises(RetryableScrapeError):
        run(scraper(handler).fetch(Platform.TRUSTPILOT, URL, limit=10))


def test_redirect_off_domain_blocked():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302, headers={"Location": "http://169.254.169.254/latest"}
        )

    with pytest.raises(PermanentScrapeError, match="leaves platform"):
        run(scraper(handler).fetch(Platform.TRUSTPILOT, URL, limit=10))


def test_redirect_on_domain_followed():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/review/example.com":
            return httpx.Response(301, headers={"Location": "/review/www.example.com"})
        return httpx.Response(200, text=page_html(["a"]))

    result = run(scraper(handler).fetch(Platform.TRUSTPILOT, URL, limit=10))
    assert len(result) == 1


def test_error_after_first_page_returns_partial():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("page") == "2":
            return httpx.Response(429)
        return httpx.Response(200, text=page_html(["a", "b"], current=1, total=3))

    result = run(scraper(handler).fetch(Platform.TRUSTPILOT, URL, limit=100))
    assert [r.external_id for r in result] == ["a", "b"]


def test_ssrf_host_rejected_before_request():
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError("must not be requested")

    with pytest.raises(PermanentScrapeError):
        run(
            scraper(handler).fetch(
                Platform.TRUSTPILOT, "https://evil.example/x", limit=1
            )
        )


def test_unsupported_platform():
    with pytest.raises(PermanentScrapeError, match="not supported"):
        run(
            scraper(lambda r: httpx.Response(200)).fetch(
                Platform.YANDEX, "https://yandex.ru/maps/org/1", limit=1
            )
        )


def test_session_uses_one_consistent_profile_and_cookies():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        pg = req.url.params.get("page", "1")
        return httpx.Response(
            200,
            headers={"Set-Cookie": "sid=abc; Path=/"} if pg == "1" else {},
            text=page_html([f"id{pg}"], current=int(pg), total=2),
        )

    run(scraper(handler).fetch(Platform.TRUSTPILOT, URL, limit=10))
    assert len({r.headers["user-agent"] for r in seen}) == 1
    assert "sid=abc" in seen[1].headers.get("cookie", "")
    assert seen[1].headers["referer"] == URL
    assert seen[1].headers["sec-fetch-site"] == "same-origin"


def test_chromium_profiles_send_client_hints_others_do_not():
    for p in DEFAULT_PROFILES:
        h = build_headers(p, referer=None)
        assert ("Sec-CH-UA" in h) == ("Chrome/" in p.user_agent)


def test_retry_after_forms():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert parse_retry_after("30", cap_s=600) == 30
    assert parse_retry_after("99999", cap_s=600) == 600
    assert parse_retry_after("Thu, 01 Jan 2026 00:01:00 GMT", cap_s=600, now=now) == 60
    assert parse_retry_after("garbage", cap_s=600) is None
    assert parse_retry_after(None, cap_s=600) is None
