import asyncio
import datetime as dt
import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx
import pytest
from arq.worker import Retry
from pydantic import ValidationError

from app.schemas.dlq import DLQRecord
from app.schemas.parser import Platform, RawReview
from app.services.llm_analyzer import AnalysisOutcome, fallback_result
from app.services.parsers.base import (
    InvalidSourceUrlError,
    ParserDataError,
    ParserTransportError,
    UnsupportedPlatformError,
)
from app.services.parsers.factory import ParserDeps, create_parser
from app.services.parsers.twogis import TwoGisParser, parse_branch_id
from app.worker.tasks import AnalyzedReview, fetch_reviews_task

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
    assert isinstance(create_parser("2gis", deps), TwoGisParser)
    for bad in ("yandex", "google", "nope"):
        with pytest.raises(UnsupportedPlatformError):
            create_parser(bad, deps)


# ---------------------------------------------------------------- задача
class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, str | None]] = []

    async def analyze_safe(
        self, text: str, *, rating: int | None = None, platform: str | None = None
    ) -> AnalysisOutcome:
        self.calls.append((text, rating, platform))
        return AnalysisOutcome(fallback_result(rating), is_fallback=text == "Отзыв 2")


class FakeSink:
    def __init__(self) -> None:
        self.saved: list[AnalyzedReview] = []

    async def save(self, company_id: UUID, items: Sequence[AnalyzedReview]) -> int:
        self.saved.extend(items)
        return len(items)


class Store:
    def __init__(self) -> None:
        self.records: list[DLQRecord] = []

    async def insert(self, record: DLQRecord) -> None:
        self.records.append(record)


def make_ctx(
    handler: Any, **extra: Any
) -> tuple[dict[str, Any], FakeLLM, FakeSink, Store]:
    llm, sink, store = FakeLLM(), FakeSink(), Store()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ctx = {
        "job_id": "j1",
        "job_try": 1,
        "parser_deps": ParserDeps(http_client=client, twogis_api_key="k"),
        "llm": llm,
        "review_sink": sink,
        "dlq_store": store,
        **extra,
    }
    return ctx, llm, sink, store


def test_task_happy_path() -> None:
    ctx, llm, sink, store = make_ctx(
        lambda r: httpx.Response(200, json={"reviews": [review(1), review(2)]})
    )
    result = run(fetch_reviews_task(ctx, CID, "2gis", URL, correlation_id="cid-1"))
    assert result == {"fetched": 2, "analyzed": 1, "fallbacks": 1, "saved": 2}
    assert {c[2] for c in llm.calls} == {"2gis"} and len(sink.saved) == 2
    assert store.records == []


def test_task_transport_error_retries_with_retry_after() -> None:
    ctx, _, sink, store = make_ctx(
        lambda r: httpx.Response(429, headers={"Retry-After": "60"})
    )
    with pytest.raises(Retry):
        run(fetch_reviews_task(ctx, CID, "2gis", URL))
    assert store.records == [] and sink.saved == []


def test_task_last_try_goes_to_dlq_with_correlation_id() -> None:
    ctx, _, _, store = make_ctx(lambda r: httpx.Response(403), job_try=3)
    with pytest.raises(Retry):
        run(fetch_reviews_task(ctx, CID, "2gis", URL, correlation_id="cid-9"))
    (rec,) = store.records
    assert rec.correlation_id == "cid-9" and rec.job_name == "fetch_reviews_task"
    assert rec.args == [str(CID), "2gis", URL]


def test_task_unsupported_platform_goes_straight_to_dlq() -> None:
    ctx, _, _, store = make_ctx(lambda r: httpx.Response(200, json={"reviews": []}))
    with pytest.raises(UnsupportedPlatformError):
        run(fetch_reviews_task(ctx, CID, "yandex", "https://yandex.ru/x"))
    assert len(store.records) == 1


def test_task_data_error_goes_straight_to_dlq() -> None:
    ctx, _, _, store = make_ctx(lambda r: httpx.Response(200, json={"oops": 1}))
    with pytest.raises(ParserDataError):
        run(fetch_reviews_task(ctx, CID, "2gis", URL))
    assert len(store.records) == 1
