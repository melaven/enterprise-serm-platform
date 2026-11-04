from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.infrastructure.queue.worker import worker


class _FakeTransaction:
    def __init__(
        self,
        label: str,
        calls: list[str],
        active_transactions: set[str],
    ) -> None:
        self.label = label
        self.calls = calls
        self.active_transactions = active_transactions

    async def __aenter__(self) -> "_FakeTransaction":
        self.active_transactions.add(self.label)
        self.calls.append(f"{self.label}:begin")
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.active_transactions.remove(self.label)
        self.calls.append(f"{self.label}:{'rollback' if exc else 'commit'}")


class _FakeSession:
    def __init__(
        self,
        label: str,
        calls: list[str],
        active_transactions: set[str],
        tenant_ids: list[object] | None = None,
        events: list[dict[str, object]] | None = None,
    ) -> None:
        self.label = label
        self.calls = calls
        self.active_transactions = active_transactions
        self.tenant_ids = tenant_ids or []
        self.events = events or []

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction(self.label, self.calls, self.active_transactions)

    async def scalars(self, _query):
        return SimpleNamespace(all=lambda: self.tenant_ids)

    async def execute(self, _query, _params):
        return SimpleNamespace(
            mappings=lambda: SimpleNamespace(all=lambda: self.events)
        )

    async def scalar(self, _query, params):
        self.calls.append(f"status:{params['status']}")
        return True


def _session_factory(
    tenant_id,
    event,
    calls: list[str],
    active_transactions: set[str],
):
    sessions = iter(
        [
            _FakeSession(
                "tenant-scan",
                calls,
                active_transactions,
                tenant_ids=[tenant_id],
            ),
            _FakeSession(
                "claim",
                calls,
                active_transactions,
                events=[event],
            ),
            _FakeSession("ack", calls, active_transactions),
        ]
    )
    return lambda: next(sessions)


@pytest.mark.asyncio
async def test_outbox_relay_commits_claim_before_enqueue_and_acknowledges_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    review_id = uuid4()
    event_id = uuid4()
    calls: list[str] = []
    active_transactions: set[str] = set()
    event = {
        "id": event_id,
        "event_type": "review.analysis.requested",
        "payload": {
            "review_id": str(review_id),
            "tenant_id": str(tenant_id),
            "correlation_id": "request-123",
        },
    }

    async def enqueue_job(*args, **kwargs):
        assert not active_transactions
        calls.append("enqueue")

    queue = SimpleNamespace(enqueue_job=AsyncMock(side_effect=enqueue_job))
    monkeypatch.setattr(
        worker,
        "AsyncSessionLocal",
        _session_factory(tenant_id, event, calls, active_transactions),
    )
    monkeypatch.setattr(worker, "set_tenant_rls_context", AsyncMock())

    result = await worker.relay_outbox_events({"redis": queue})

    assert result == {"delivered": 1, "failed": 0}
    assert calls == [
        "claim:begin",
        "claim:commit",
        "enqueue",
        "ack:begin",
        "status:processed",
        "ack:commit",
    ]
    queue.enqueue_job.assert_awaited_once_with(
        "process_review_task",
        str(review_id),
        str(tenant_id),
        correlation_id="request-123",
        _job_id=f"process-review-{review_id}",
    )


@pytest.mark.asyncio
async def test_outbox_relay_requeues_event_when_enqueue_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    calls: list[str] = []
    active_transactions: set[str] = set()
    event = {
        "id": uuid4(),
        "event_type": "review.analysis.requested",
        "payload": {
            "review_id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "correlation_id": None,
        },
    }

    async def enqueue_job(*_args, **_kwargs):
        assert not active_transactions
        calls.append("enqueue")
        raise RuntimeError("Redis unavailable")

    queue = SimpleNamespace(enqueue_job=AsyncMock(side_effect=enqueue_job))
    monkeypatch.setattr(
        worker,
        "AsyncSessionLocal",
        _session_factory(tenant_id, event, calls, active_transactions),
    )
    monkeypatch.setattr(worker, "set_tenant_rls_context", AsyncMock())

    result = await worker.relay_outbox_events({"redis": queue})

    assert result == {"delivered": 0, "failed": 1}
    assert calls == [
        "claim:begin",
        "claim:commit",
        "enqueue",
    ]
    queue.enqueue_job.assert_awaited_once()


@pytest.mark.asyncio
async def test_outbox_relay_enqueues_platform_reply_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    event_id = uuid4()
    payload = {
        "tenant_id": str(tenant_id),
        "review_id": str(uuid4()),
    }
    calls: list[str] = []
    active_transactions: set[str] = set()
    event = {
        "id": event_id,
        "event_type": "publish_review_reply",
        "payload": payload,
    }

    async def enqueue_job(*args, **kwargs):
        assert not active_transactions
        calls.append("enqueue")

    queue = SimpleNamespace(enqueue_job=AsyncMock(side_effect=enqueue_job))
    monkeypatch.setattr(
        worker,
        "AsyncSessionLocal",
        _session_factory(tenant_id, event, calls, active_transactions),
    )
    monkeypatch.setattr(worker, "set_tenant_rls_context", AsyncMock())

    result = await worker.relay_outbox_events({"redis": queue})

    assert result == {"delivered": 1, "failed": 0}
    assert calls == [
        "claim:begin",
        "claim:commit",
        "enqueue",
        "ack:begin",
        "status:processed",
        "ack:commit",
    ]
    queue.enqueue_job.assert_awaited_once_with(
        "publish_review_reply",
        str(event_id),
        str(tenant_id),
        payload,
        _job_id=f"publish-review-reply-{event_id}",
    )


@pytest.mark.asyncio
async def test_outbox_relay_marks_invalid_event_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    calls: list[str] = []
    active_transactions: set[str] = set()
    event = {
        "id": uuid4(),
        "event_type": "unknown.event",
        "payload": {},
    }
    queue = SimpleNamespace(enqueue_job=AsyncMock())
    monkeypatch.setattr(
        worker,
        "AsyncSessionLocal",
        _session_factory(tenant_id, event, calls, active_transactions),
    )
    monkeypatch.setattr(worker, "set_tenant_rls_context", AsyncMock())

    result = await worker.relay_outbox_events({"redis": queue})

    assert result == {"delivered": 0, "failed": 1}
    assert "status:failed" in calls
    queue.enqueue_job.assert_not_awaited()
