import asyncio
import datetime as dt
import json
from typing import Any
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError

from app.schemas.parser import Platform, RawReview
from app.services.parsers.base import (
    InvalidSourceUrlError,
    ParserDataError,
    ParserTransportError,
    UnsupportedPlatformError,
)
from app.services.parsers.factory import ParserDeps, create_parser
from app.services.parsers.twogis import TwoGisParser, parse_branch_id
from app.services.worker.tasks import fetch_platform_reviews, fetch_reviews_task

URL = "https://2gis.ru/moscow/firm/70000001012345678/tab/reviews"
CID = UUID("11111111-1111-1111-1111-111111111111")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def review(i: int, **over: Any) -> dict[str, Any]:
    base = {
        "id": f"r{i}",
        "text": f"  Отзыв {i}  ",
        "rating": 4,
        "date_created": f"2026-09-{10 + i:02d}T12:00:00+07:00",
        "user": {"name": "Иван"},
    }
    return {**base, **over}


def parser_for(handler: Any, **kw: Any) -> TwoGisParser:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TwoGisParser(api_key="k", client=client, page_delay_s=0, **kw)


# ---------------------------------------------------------------- схема
def test_raw_review_normalizes() -> None:
    r = RawReview(
        platform_id=123,  # type: ignore[arg-type]
        author_name=None,  # type: ignore[arg-type]
        text="a  b\n\n\n\nc",
        rating=5,
        date=dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=7))),
        platform=Platform.TWOGIS,
    )
    assert r.platform_id == "123" and r.author_name == "Аноним"
    assert r.author_avatar_url is None
    assert r.author_profile_url is None
    assert r.text == "a b\n\nc"
    assert r.date.utcoffset() == dt.timedelta(0) and r.date.hour == 5


def test_raw_review_rejects_bad_rating_and_platform() -> None:
    with pytest.raises(ValidationError):
        RawReview(platform_id="1", rating=6, date=dt.datetime.now(), platform="2gis")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        RawReview(
            platform_id="1", rating=3, date=dt.datetime.now(), platform="tripadvisor"
        )  # type: ignore[arg-type]


# ---------------------------------------------------------------- URL
@pytest.mark.parametrize(
    "url",
    [
        "http://2gis.ru/moscow/firm/70000001012345678",  # не https
        "https://evil.com/firm/70000001012345678",
        "https://2gis.ru.evil.com/firm/70000001012345678",
        "https://2gis.ru/moscow/search/cafe",  # нет firm
        "https://2gis.ru/s/abc",
    ],
)
def test_parse_branch_id_rejects(url: str) -> None:
    with pytest.raises(InvalidSourceUrlError):
        parse_branch_id(url)


def test_parse_branch_id_ok() -> None:
    assert parse_branch_id(URL) == "70000001012345678"
    assert parse_branch_id("https://www.2gis.com/dubai/firm/70000001012345678") == (
        "70000001012345678"
    )


# ---------------------------------------------------------------- парсер
def test_fetch_maps_reviews_and_requests_only_api_host() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"reviews": [review(1), review(2)]})

    out = run(parser_for(handler).fetch_reviews(URL, 10))
    assert [r.platform_id for r in out] == ["r1", "r2"]
    assert out[0].text == "Отзыв 1" and out[0].platform is Platform.TWOGIS
    assert len(seen) == 1  # len(items) < want: страница последняя
    assert seen[0].url.host == "public-api.reviews.2gis.com"
    assert "70000001012345678" in seen[0].url.path


def test_pagination_dedup_and_limit() -> None:
    pages = [
        {"reviews": [review(i) for i in range(1, 4)]},
        {"reviews": [review(3), review(4), review(5)]},  # r3 — дубль
    ]
    offsets: list[str | None] = []

    def handler(req: httpx.Request) -> httpx.Response:
        offsets.append(req.url.params.get("offset_date"))
        return httpx.Response(200, json=pages[len(offsets) - 1])

    out = run(parser_for(handler, page_size=3).fetch_reviews(URL, 5))
    assert [r.platform_id for r in out] == ["r1", "r2", "r3", "r4", "r5"]
    assert offsets == [None, review(3)["date_created"]]


def test_malformed_items_skipped_but_not_all() -> None:
    items = [review(1), {"id": "x"}, "junk", review(2, rating=None)]

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"reviews": items})

    out = run(parser_for(handler).fetch_reviews(URL, 10))
    assert [r.platform_id for r in out] == ["r1"]


def test_all_items_unparseable_is_data_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"reviews": [{"id": "x"}]})

    with pytest.raises(ParserDataError):
        run(parser_for(handler).fetch_reviews(URL, 10))


@pytest.mark.parametrize("body", [{"nope": 1}, [], "text"])
def test_bad_shape_is_data_error(body: Any) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(body))

    with pytest.raises(ParserDataError):
        run(parser_for(handler).fetch_reviews(URL, 10))


def test_empty_reviews_is_ok() -> None:
    out = run(
        parser_for(lambda r: httpx.Response(200, json={"reviews": []})).fetch_reviews(
            URL, 10
        )
    )
    assert out == []


@pytest.mark.parametrize("status", [403, 429, 500, 503])
def test_blocking_statuses_are_transport_errors(status: int) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"Retry-After": "42"})

    with pytest.raises(ParserTransportError) as ei:
        run(parser_for(handler).fetch_reviews(URL, 10))
    assert ei.value.status_code == status and ei.value.retry_after == 42.0


def test_timeout_and_network_errors_are_transport_errors() -> None:
    def timeout(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    def refused(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    for handler in (timeout, refused):
        with pytest.raises(ParserTransportError):
            run(parser_for(handler).fetch_reviews(URL, 10))


def test_404_is_not_retryable() -> None:
    with pytest.raises(ParserDataError):
        run(parser_for(lambda r: httpx.Response(404)).fetch_reviews(URL, 10))


# ---------------------------------------------------------------- фабрика
def test_factory() -> None:
    deps = ParserDeps(twogis_api_key="k")
    with pytest.raises(
        UnsupportedPlatformError,
        match="Public-page review scraping is disabled",
    ):
        create_parser("2gis", deps)
    for bad in ("yandex", "google", "nope"):
        with pytest.raises(UnsupportedPlatformError):
            create_parser(bad, deps)


# ---------------------------------------------------------------- Disabled ingestion jobs
@pytest.mark.parametrize(
    "task,args",
    [
        (fetch_reviews_task, ({}, CID, "2gis", URL)),
        (fetch_platform_reviews, ({}, CID, "google_business")),
    ],
)
def test_legacy_review_ingestion_jobs_fail_closed(task: Any, args: tuple[Any, ...]) -> None:
    with pytest.raises(RuntimeError, match="disabled"):
        run(task(*args))
