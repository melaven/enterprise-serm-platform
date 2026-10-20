from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.worker import digest
from app.services.worker.worker import WorkerSettings


class FakeResult:
    def __init__(self, row: object) -> None:
        self.row = row

    def one_or_none(self) -> object:
        return self.row

    def one(self) -> object:
        return self.row


class FakeDigestSession:
    def __init__(self, results: list[object]) -> None:
        self.results = iter(results)
        self.closed = 0
        self.statements: list[object] = []

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        return next(self.results)

    async def close(self) -> None:
        self.closed += 1


@pytest.mark.asyncio
async def test_company_digest_aggregates_and_sends_weekly_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    session = FakeDigestSession(
        [
            FakeResult(("Demo <Company>", "owner@example.test")),
            FakeResult((12, 10, 4.2, 2.3, 2)),
            FakeResult((8, 7, 4.0, 1.8, 1)),
        ]
    )
    monkeypatch.setattr(
        digest,
        "get_tenant_session",
        AsyncMock(return_value=session),
    )
    send_email = AsyncMock()
    monkeypatch.setattr(digest, "send_html_email", send_email)

    result = await digest.send_company_weekly_digest(
        {},
        str(tenant_id),
        datetime(2026, 10, 19, 9, tzinfo=timezone.utc).isoformat(),
    )

    assert result == {"tenant_id": str(tenant_id), "status": "sent"}
    assert len(session.statements) == 3
    assert session.closed == 1
    send_email.assert_awaited_once()
    recipient, subject, html_content = send_email.await_args.args
    assert recipient == "owner@example.test"
    assert "Demo &lt;Company&gt;" in html_content
    assert "Получено отзывов: 12" in html_content
    assert "Обработано: 10" in html_content
    assert "Высоких угроз (уровень 4–5): 2" in html_content
    assert "рост на 0.5 балла" in html_content
    assert "Еженедельный отчет SERM" in subject


@pytest.mark.asyncio
async def test_weekly_digest_enqueue_uses_one_deduplicated_job_per_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    sql_session = FakeDigestSession([SimpleNamespace(all=lambda: [(tenant_id,)])])

    class SessionFactory:
        async def __aenter__(self) -> FakeDigestSession:
            return sql_session

        async def __aexit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(digest, "AsyncSessionLocal", SessionFactory)
    redis = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()))

    result = await digest.enqueue_weekly_digests({"redis": redis})

    assert result == {"recipients": 1, "queued": 1, "duplicates": 0}
    redis.enqueue_job.assert_awaited_once()
    args = redis.enqueue_job.await_args.args
    kwargs = redis.enqueue_job.await_args.kwargs
    assert args[0] == "send_company_weekly_digest"
    assert args[1] == str(tenant_id)
    assert kwargs["_job_id"].startswith(f"weekly-digest-{tenant_id}-")


def test_weekly_digest_is_scheduled_for_monday_0900_utc() -> None:
    cron_job = WorkerSettings.cron_jobs[0]

    assert WorkerSettings.timezone == timezone.utc
    assert cron_job.weekday == "mon"
    assert cron_job.hour == 9
    assert cron_job.minute == 0
