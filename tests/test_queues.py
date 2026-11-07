"""Маршрутизация очередей: реестр, постановка, согласованность пулов воркеров, запрет обхода dispatch."""

import ast
from pathlib import Path
from typing import Any

import pytest
from arq.constants import in_progress_key_prefix, result_key_prefix

from app.core.dispatch import enqueue_bulk, enqueue_critical, enqueue_routed
from app.core.queues import (
    LEGACY_QUEUE,
    TASK_CRITICAL_DRAFTS,
    TASK_PROCESS_INGESTION,
    TASK_PROCESS_REVIEW,
    TASK_PUBLISH_GENERATED_REPLY,
    TASK_PUBLISH_REPLY,
    TASK_ROUTES,
    TASK_SEND_WEEKLY_DIGEST,
    Queue,
    TaskRoutingError,
    UnroutableTaskError,
    functions_for,
    queue_for,
)

ROOT = Path(__file__).resolve().parents[1]
JOB = "fetch_reviews:t:yandex:abc"


class FakePool:
    """Модель ARQ: enqueue_job отказывает, пока жив ключ очереди/результата/выполнения; запоминает kwargs."""

    def __init__(self, *, result: bool = False, queued: bool = False) -> None:
        self.keys: set[str] = set()
        if result:
            self.keys.add(result_key_prefix + JOB)
        if queued:
            self.keys.add("queue:" + JOB)
        self.enqueued: list[tuple[str, dict[str, Any]]] = []

    async def enqueue_job(
        self, function: str, *args: Any, **kwargs: Any
    ) -> object | None:
        job_id = kwargs.get("_job_id")
        if (
            job_id
            and {
                "queue:" + job_id,
                result_key_prefix + job_id,
                in_progress_key_prefix + job_id,
            }
            & self.keys
        ):
            return None
        self.enqueued.append((function, kwargs))
        return object()

    async def exists(self, key: str) -> int:
        return int(key in self.keys)

    async def delete(self, key: str) -> None:
        self.keys.discard(key)


# --------------------------------------------------------------------------- #
# Реестр
# --------------------------------------------------------------------------- #
def test_queues_are_distinct_redis_keys_and_not_the_default() -> None:
    assert Queue.CRITICAL.value != Queue.BULK.value
    assert LEGACY_QUEUE not in {q.value for q in Queue}


def test_every_task_has_exactly_one_queue_and_unknown_task_fails_fast() -> None:
    assert queue_for(TASK_CRITICAL_DRAFTS) is Queue.CRITICAL
    assert queue_for(TASK_PUBLISH_REPLY) is Queue.CRITICAL
    assert queue_for(TASK_PUBLISH_GENERATED_REPLY) is Queue.CRITICAL
    assert queue_for(TASK_PROCESS_REVIEW) is Queue.BULK
    assert queue_for(TASK_PROCESS_INGESTION) is Queue.BULK
    assert queue_for(TASK_SEND_WEEKLY_DIGEST) is Queue.BULK
    assert functions_for(Queue.CRITICAL) | functions_for(Queue.BULK) == set(TASK_ROUTES)
    assert not functions_for(Queue.CRITICAL) & functions_for(Queue.BULK)
    with pytest.raises(UnroutableTaskError):
        queue_for("nope")


# --------------------------------------------------------------------------- #
# Постановка
# --------------------------------------------------------------------------- #
async def test_bulk_and_critical_use_queue_name() -> None:
    pool = FakePool()
    assert await enqueue_bulk(pool, TASK_PROCESS_INGESTION, 1, job_id=JOB) is not None  # type: ignore[arg-type]
    assert await enqueue_critical(pool, TASK_CRITICAL_DRAFTS, 1, 2, {}) is not None  # type: ignore[arg-type]
    (_, bulk_kwargs), (_, critical_kwargs) = pool.enqueued
    assert (
        bulk_kwargs["_queue_name"] == Queue.BULK.value and bulk_kwargs["_job_id"] == JOB
    )
    assert (
        critical_kwargs["_queue_name"] == Queue.CRITICAL.value
        and "_job_id" not in critical_kwargs
    )


async def test_routing_without_explicit_queue_uses_registry() -> None:
    pool = FakePool()
    await enqueue_routed(pool, TASK_PROCESS_REVIEW, 1, [])  # type: ignore[arg-type]
    assert pool.enqueued[0][1]["_queue_name"] == Queue.BULK.value


async def test_real_duplicate_is_still_none() -> None:
    pool = FakePool(queued=True)
    assert await enqueue_bulk(pool, TASK_PROCESS_INGESTION, 1, job_id=JOB) is None  # type: ignore[arg-type]
    assert pool.enqueued == []


async def test_job_id_with_a_retained_result_is_still_a_duplicate() -> None:
    pool = FakePool(result=True)
    assert await enqueue_bulk(pool, TASK_PROCESS_INGESTION, 1, job_id=JOB) is None  # type: ignore[arg-type]
    assert pool.enqueued == []


async def test_wrong_pool_is_rejected_before_redis() -> None:
    pool = FakePool()
    with pytest.raises(TaskRoutingError):
        await enqueue_critical(pool, TASK_PROCESS_INGESTION, 1)  # type: ignore[arg-type]
    with pytest.raises(TaskRoutingError):
        await enqueue_bulk(pool, TASK_CRITICAL_DRAFTS, 1)  # type: ignore[arg-type]
    with pytest.raises(TaskRoutingError):
        await enqueue_routed(
            pool, "fetch_reviews_task", 1, _queue_name="arq:queue:critical"
        )  # type: ignore[arg-type]
    with pytest.raises(UnroutableTaskError):
        await enqueue_routed(pool, "unknown_task")  # type: ignore[arg-type]
    assert pool.enqueued == []


# --------------------------------------------------------------------------- #
# Статические гейты (без импорта arq/sqlalchemy)
# --------------------------------------------------------------------------- #
def _worker_classes() -> dict[str, ast.ClassDef]:
    tree = ast.parse(
        (ROOT / "app/infrastructure/queue/worker/worker.py").read_text(encoding="utf8")
    )
    return {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


def _class_attr(cls: ast.ClassDef, name: str) -> ast.expr:
    for node in cls.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise AssertionError(f"{cls.name}.{name} не найден")


def test_worker_pools_register_exactly_their_routes() -> None:
    classes = _worker_classes()
    for class_name, queue in (
        ("CriticalWorkerSettings", Queue.CRITICAL),
        ("BulkWorkerSettings", Queue.BULK),
    ):
        functions = _class_attr(classes[class_name], "functions")
        assert isinstance(functions, ast.List)
        names = {e.id for e in functions.elts if isinstance(e, ast.Name)}
        assert names == functions_for(queue), class_name
        assert (
            ast.unparse(_class_attr(classes[class_name], "queue_name"))
            == f"Queue.{queue.name}.value"
        )


def test_no_direct_enqueue_job_outside_tracing() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "app").rglob("*.py")
        if ".enqueue_job(" in path.read_text(encoding="utf8")
        and path.name != "tracing.py"
    ]
    assert offenders == [], f"ставьте задачи через app.core.dispatch: {offenders}"
