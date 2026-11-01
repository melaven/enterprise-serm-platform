from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.infrastructure.queue.worker import worker


class _FakeSession:
    def __init__(
        self,
        tenant_ids: list[object] | None = None,
        events: list[dict[str, object]] | None = None,
        calls: list[str] | None = None,
    ) -> None:
        self.tenant_ids = tenant_ids or []
        self.events = events or []
        self.calls = calls if calls is not None else []
        self.rolled_back = False

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.rolled_back = exc is not None

    def begin(self) -> "_FakeSession":
        return self

    async def scalars(self, _query):
        return SimpleNamespace(all=lambda: self.tenant_ids)

    async def execute(self, _query, _params):
        return SimpleNamespace(mappings=lambda: self.events)

    async def scalar(self, _query, _params):
        self.calls.append("status")
        return True


@pytest.mark.asyncio
async def test_outbox_relay_marks_event_processed_after_enqueue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    review_id = uuid4()
    calls: list[str] = []
    tenant_scan = _FakeSession(tenant_ids=[tenant_id])
    event_session = _FakeSession(
        events=[
            {
                "id": uuid4(),
                "event_type": "review.analysis.requested",
                "payload": {
                    "review_id": str(review_id),
                    "tenant_id": str(tenant_id),
                    "correlation_id": "request-123",
                },
            }
        ],
        calls=calls,
    )
    sessions = iter([tenant_scan, event_session])
    queue = SimpleNamespace(
        enqueue_job=AsyncMock(
            side_effect=lambda *args, **kwargs: calls.append("enqueue")
        )
    )
    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: next(sessions))
    monkeypatch.setattr(worker, "set_tenant_rls_context", AsyncMock())

    result = await worker.relay_outbox_events({"redis": queue})

    assert result == {"delivered": 1, "failed": 0}
    assert calls == ["enqueue", "status"]
    queue.enqueue_job.assert_awaited_once_with(
        "process_review_task",
        str(review_id),
        str(tenant_id),
        correlation_id="request-123",
        _job_id=f"process-review-{review_id}",
    )


@pytest.mark.asyncio
async def test_outbox_relay_rolls_back_when_enqueue_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    event_session = _FakeSession(
        events=[
            {
                "id": uuid4(),
                "event_type": "review.analysis.requested",
                "payload": {
                    "review_id": str(uuid4()),
                    "tenant_id": str(tenant_id),
                    "correlation_id": None,
                },
            }
        ]
    )
    sessions = iter([_FakeSession(tenant_ids=[tenant_id]), event_session])
    queue = SimpleNamespace(
        enqueue_job=AsyncMock(side_effect=RuntimeError("Redis unavailable"))
    )
    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: next(sessions))
    monkeypatch.setattr(worker, "set_tenant_rls_context", AsyncMock())

    with pytest.raises(RuntimeError, match="Redis unavailable"):
        await worker.relay_outbox_events({"redis": queue})

    assert event_session.rolled_back
