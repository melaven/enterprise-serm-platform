import asyncio
import datetime as dt
import json
from typing import Any
from uuid import UUID

import pytest
from arq.worker import Retry

from app.db.dlq_repository import (
    InMemoryDLQStore,
    SupabaseDLQStore,
    save_to_dlq,
    set_default_dlq_store,
)
from app.schemas.dlq import DLQRecord, DLQStatus
from app.worker.hooks import dlq_protected, on_job_end

CID = UUID("11111111-1111-1111-1111-111111111111")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _ctx(store: Any, **extra: Any) -> dict[str, Any]:
    return {"job_id": "job-1", "job_try": 1, "dlq_store": store, **extra}


class Boom(Exception):
    pass


def test_on_job_end_saves_record_for_exception() -> None:
    store = InMemoryDLQStore()
    try:
        raise Boom("bad parse")
    except Boom as exc:
        err = exc
    kwargs = {"url": "http://x", "correlation_id": "cid-1", "when": dt.date(2026, 1, 2)}
    run(on_job_end(_ctx(store), "fetch", (CID, 5), kwargs, err))
    rec = store.records["job-1"]
    assert rec.correlation_id == "cid-1" and rec.job_name == "fetch"
    assert rec.args == [str(CID), 5]
    assert rec.kwargs["when"] == "2026-01-02"
    assert rec.status is DLQStatus.PENDING_REVIEW
    assert rec.error_message == "Boom: bad parse" and "Boom" in rec.traceback
    json.dumps(rec.model_dump(mode="json"))  # сериализуется


def test_on_job_end_ignores_non_exception() -> None:
    store = InMemoryDLQStore()
    run(on_job_end(_ctx(store), "fetch", (), {}, 42))
    assert store.records == {}


def test_missing_correlation_id_is_unknown() -> None:
    store = InMemoryDLQStore()
    run(on_job_end(_ctx(store), "fetch", (), {}, Boom("x")))
    assert store.records["job-1"].correlation_id == "unknown"


class _FailingStore:
    async def insert(self, record: DLQRecord) -> None:
        raise ConnectionError("supabase down")


def test_dlq_failure_does_not_raise() -> None:
    run(on_job_end(_ctx(_FailingStore()), "fetch", (), {}, Boom("x")))


def test_decorator_final_failure_goes_to_dlq_and_reraises() -> None:
    store = InMemoryDLQStore()

    @dlq_protected()
    async def job(ctx: dict[str, Any], x: int, **kw: Any) -> int:
        raise Boom("nope")

    with pytest.raises(Boom):
        run(job(_ctx(store), 1, correlation_id="c"))
    assert store.records["job-1"].correlation_id == "c"
    assert job.__name__ == "job"


def test_retry_with_attempts_left_is_not_dlq() -> None:
    store = InMemoryDLQStore()

    @dlq_protected()
    async def job(ctx: dict[str, Any]) -> None:
        raise Retry(defer=1)

    with pytest.raises(Retry):
        run(job(_ctx(store, job_try=2, max_tries=5)))
    assert store.records == {}


def test_retry_on_last_attempt_goes_to_dlq() -> None:
    store = InMemoryDLQStore()

    @dlq_protected()
    async def job(ctx: dict[str, Any]) -> None:
        raise Retry(defer=1)

    with pytest.raises(Retry):
        run(job(_ctx(store, job_try=5, max_tries=5)))
    assert "job-1" in store.records


def test_per_task_max_tries_override() -> None:
    store = InMemoryDLQStore()

    @dlq_protected(max_tries=2)
    async def job(ctx: dict[str, Any]) -> None:
        raise Retry(defer=1)

    with pytest.raises(Retry):
        run(job(_ctx(store, job_try=2, max_tries=5)))
    assert "job-1" in store.records


def test_success_passes_through() -> None:
    store = InMemoryDLQStore()

    @dlq_protected()
    async def job(ctx: dict[str, Any]) -> str:
        return "ok"

    assert run(job(_ctx(store))) == "ok" and store.records == {}


def test_save_without_store_raises_and_default_store_works() -> None:
    rec = DLQRecord(
        job_id="j", job_name="n", correlation_id="c", error_message="e", traceback="t"
    )
    set_default_dlq_store(None)
    with pytest.raises(RuntimeError):
        run(save_to_dlq(rec))
    store = InMemoryDLQStore()
    set_default_dlq_store(store)
    run(save_to_dlq(rec))
    set_default_dlq_store(None)
    assert "j" in store.records


class _Q:
    def __init__(self, log: list[Any]) -> None:
        self.log = log

    def upsert(self, payload: dict[str, Any], **kw: Any) -> "_Q":
        self.log.append((payload, kw))
        return self

    async def execute(self) -> None:
        return None


class _Client:
    def __init__(self) -> None:
        self.log: list[Any] = []

    def table(self, name: str) -> _Q:
        self.log.append(name)
        return _Q(self.log)


def test_supabase_store_payload() -> None:
    client = _Client()
    rec = DLQRecord(
        job_id="j", job_name="n", correlation_id="c", error_message="e", traceback="t"
    )
    run(SupabaseDLQStore(client).insert(rec))
    assert client.log[0] == "dead_letter_queue"
    payload, kw = client.log[1]
    assert payload["status"] == "pending_review" and payload["job_id"] == "j"
    assert kw == {"on_conflict": "job_id", "ignore_duplicates": True}