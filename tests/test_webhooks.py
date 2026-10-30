import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.api.v1.routes import webhooks_config
from app.core.auth import get_current_tenant
from app.infrastructure.integrations import webhooks_sender
from app.infrastructure.persistence.models.economics import WebhookEndpoint
from app.infrastructure.queue.worker import analysis_tasks


class FakeScalars:
    def __init__(self, records: list[WebhookEndpoint]) -> None:
        self.records = records

    def all(self) -> list[WebhookEndpoint]:
        return self.records


class FakeWebhookSession:
    def __init__(self, records: list[WebhookEndpoint] | None = None) -> None:
        self.records = records or []
        self.added: list[WebhookEndpoint] = []
        self.add = Mock(side_effect=self.added.append)
        self.flush = AsyncMock(side_effect=self._flush)
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.close = AsyncMock()
        self.scalars = AsyncMock(return_value=FakeScalars(self.records))
        self.scalar = AsyncMock(return_value=None)
        self.deleted: list[WebhookEndpoint] = []
        self.delete = AsyncMock(side_effect=self.deleted.append)

    async def _flush(self) -> None:
        for record in self.added:
            if record.id is None:
                record.id = uuid4()
            if record.created_at is None:
                record.created_at = datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def webhook_config_client() -> (
    AsyncIterator[tuple[httpx.AsyncClient, FakeWebhookSession, UUID]]
):
    tenant_id = uuid4()
    session = FakeWebhookSession()
    app = FastAPI()
    app.include_router(webhooks_config.router)

    async def current_tenant() -> UUID:
        return tenant_id

    async def tenant_session():
        yield session
        await session.commit()

    app.dependency_overrides[get_current_tenant] = current_tenant
    app.dependency_overrides[webhooks_config.get_webhook_session] = tenant_session
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, session, tenant_id
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_endpoint_create_returns_secret_once(
    webhook_config_client: tuple[httpx.AsyncClient, FakeWebhookSession, UUID],
) -> None:
    client, session, tenant_id = webhook_config_client

    response = await client.post(
        "/api/v1/webhooks",
        json={"url": "https://crm.example.test/hooks/reviews"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["url"] == "https://crm.example.test/hooks/reviews"
    assert payload["is_active"] is True
    assert len(payload["secret_key"]) >= 32
    assert session.added[0].company_id == tenant_id
    assert session.commit.await_count == 1


class FakeHttpxClient:
    def __init__(self, **kwargs: object) -> None:
        self.options = kwargs
        self.requests: list[tuple[str, bytes, dict[str, str]]] = []

    async def __aenter__(self) -> "FakeHttpxClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(
        self, url: str, *, content: bytes, headers: dict[str, str]
    ) -> SimpleNamespace:
        self.requests.append((url, content, headers))
        return SimpleNamespace(raise_for_status=Mock())


@pytest.mark.asyncio
async def test_dispatch_sends_hmac_signed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    endpoint = WebhookEndpoint(
        id=uuid4(),
        company_id=tenant_id,
        url="https://crm.example.test/hooks",
        secret_key="client-secret",
        is_active=True,
    )
    session = FakeWebhookSession([endpoint])
    session.scalars.return_value = FakeScalars([endpoint])
    monkeypatch.setattr(
        webhooks_sender,
        "get_tenant_session",
        AsyncMock(return_value=session),
    )
    clients: list[FakeHttpxClient] = []

    def make_client(**kwargs: object) -> FakeHttpxClient:
        client = FakeHttpxClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(webhooks_sender.httpx, "AsyncClient", make_client)
    monkeypatch.setattr(
        webhooks_sender,
        "_assert_public_https_destination",
        AsyncMock(return_value=None),
    )
    event_data = {"review_id": str(uuid4()), "sentiment": "NEGATIVE"}

    result = await webhooks_sender.dispatch_review_analyzed_event(tenant_id, event_data)

    assert result == {"sent": 1, "failed": 0}
    assert session.close.await_count == 1
    client = clients[0]
    assert client.options["trust_env"] is False
    assert client.options["follow_redirects"] is False
    url, body, headers = client.requests[0]
    assert url == endpoint.url
    decoded_body = json.loads(body)
    assert decoded_body == {
        "event": "review.analyzed",
        "tenant_id": str(tenant_id),
        "data": event_data,
    }
    expected = hmac.new(
        endpoint.secret_key.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    assert headers["X-Tenable-Signature"] == f"sha256={expected}"


@pytest.mark.asyncio
async def test_sender_rejects_private_webhook_destinations() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        await webhooks_sender._assert_public_https_destination(
            "http://crm.example.test/hooks"
        )
    with pytest.raises(ValueError, match="public IPs"):
        await webhooks_sender._assert_public_https_destination(
            "https://127.0.0.1/hooks"
        )


@pytest.mark.asyncio
async def test_worker_dispatches_only_after_database_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(RuntimeError, match="disabled"):
        await analysis_tasks.process_reviews_batch({}, uuid4(), [uuid4()])
