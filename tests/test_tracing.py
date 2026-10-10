import asyncio
import uuid
from typing import Any

import structlog
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.logger import get_correlation_id
from app.core.middleware import CORRELATION_ID_HEADER, CorrelationIdMiddleware
from arq_tracing_example import enqueue_traced, traced_task


async def whoami(request: Request) -> JSONResponse:
    return JSONResponse({"cid": get_correlation_id()})


def _client() -> TestClient:
    app = Starlette(routes=[Route("/", whoami)])
    app.add_middleware(CorrelationIdMiddleware)
    return TestClient(app)


def test_header_matches_context_and_is_unique() -> None:
    c = _client()
    r1, r2 = c.get("/"), c.get("/")
    for r in (r1, r2):
        assert r.headers[CORRELATION_ID_HEADER] == r.json()["cid"]
        assert uuid.UUID(r.headers[CORRELATION_ID_HEADER]).version == 4
    assert r1.headers[CORRELATION_ID_HEADER] != r2.headers[CORRELATION_ID_HEADER]
    assert get_correlation_id() is None  # контекст очищен


def test_client_supplied_header_is_ignored() -> None:
    r = _client().get("/", headers={CORRELATION_ID_HEADER: "evil"})
    assert r.headers[CORRELATION_ID_HEADER] != "evil"


class _Pool:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    async def enqueue_job(self, fn: str, *a: Any, **kw: Any) -> None:
        self.kwargs = kw


def test_cid_travels_api_to_worker() -> None:
    seen: list[Any] = []

    @traced_task
    async def job(ctx: dict[str, Any], x: int) -> int:
        seen.append(get_correlation_id())
        structlog.get_logger().info("inside")
        return x

    async def scenario() -> None:
        pool = _Pool()
        from app.core.logger import reset_correlation_id, set_correlation_id

        tok = set_correlation_id("abc")
        await enqueue_traced(pool, "job", 1)  # type: ignore[arg-type]
        reset_correlation_id(tok)
        assert pool.kwargs == {"correlation_id": "abc"}
        assert await job({"job_id": "j"}, 1, **pool.kwargs) == 1
        assert get_correlation_id() is None

    structlog.EVENTS.clear()  # type: ignore[attr-defined]
    asyncio.run(scenario())
    assert seen == ["abc"]
    assert {e["correlation_id"] for e in structlog.EVENTS} == {"abc"}  # type: ignore[attr-defined]
    assert job.__name__ == "job"


def test_job_without_cid_gets_generated() -> None:
    @traced_task
    async def job(ctx: dict[str, Any]) -> str | None:
        return get_correlation_id()

    cid = asyncio.run(job({}))
    assert cid is not None and uuid.UUID(cid)
