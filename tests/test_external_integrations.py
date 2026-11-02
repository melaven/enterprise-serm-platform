import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.infrastructure.external.base import (
    BasePlatformAdapter,
    PermanentAPIError,
    PlatformAdapterRegistry,
    TransientAPIError,
)
from app.infrastructure.external.yandex import YandexBusinessAdapter
from app.infrastructure.queue.worker import integration_tasks


def test_platform_adapter_registry_normalizes_and_creates_adapters() -> None:
    registry = PlatformAdapterRegistry()
    registry.register("yandex", YandexBusinessAdapter)

    assert isinstance(registry.get_adapter(" YANDEX "), YandexBusinessAdapter)
    with pytest.raises(ValueError, match="Unsupported platform"):
        registry.get_adapter("unknown")


@pytest.mark.asyncio
async def test_yandex_adapter_publishes_reply_and_returns_external_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"external_reply_id": "reply-123"})

    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.infrastructure.external.yandex.httpx.AsyncClient",
        lambda **kwargs: original_async_client(
            transport=httpx.MockTransport(handle_request),
            **kwargs,
        ),
    )

    reply_id = await YandexBusinessAdapter().publish_reply(
        "review-123",
        "Thank you",
        {"access_token": "secret-token"},
    )

    assert reply_id == "reply-123"
    assert requests[0].method == "POST"
    assert requests[0].headers["Authorization"] == "OAuth secret-token"
    assert json.loads(requests[0].content) == {"text": "Thank you"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "headers", "error_type"),
    [
        (429, {"Retry-After": "12"}, TransientAPIError),
        (503, {}, TransientAPIError),
        (400, {}, PermanentAPIError),
        (401, {}, PermanentAPIError),
        (403, {}, PermanentAPIError),
        (404, {}, PermanentAPIError),
    ],
)
async def test_yandex_adapter_maps_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    headers: dict[str, str],
    error_type: type[Exception],
) -> None:
    def handle_request(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, headers=headers)

    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.infrastructure.external.yandex.httpx.AsyncClient",
        lambda **kwargs: original_async_client(
            transport=httpx.MockTransport(handle_request),
            **kwargs,
        ),
    )

    with pytest.raises(error_type) as caught:
        await YandexBusinessAdapter().publish_reply(
            "review-123",
            "Thank you",
            {"access_token": "secret-token"},
        )

    if status_code == 429:
        assert isinstance(caught.value, TransientAPIError)
        assert caught.value.retry_after == 12.0


class _FakeSession:
    def __init__(self) -> None:
        self.queries: list[tuple[object, object]] = []

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback) -> None:
        return None

    async def execute(self, query: object, params: object) -> SimpleNamespace:
        self.queries.append((query, params))
        return SimpleNamespace(scalar_one_or_none=lambda: "encrypted-token")


class _RecordingAdapter(BasePlatformAdapter):
    def __init__(self, calls: list[tuple[str, str, dict[str, object]]]) -> None:
        self.calls = calls

    async def publish_reply(
        self,
        review_external_id: str,
        text: str,
        credentials: dict[str, object],
    ) -> str:
        self.calls.append((review_external_id, text, credentials))
        return "reply-123"


@pytest.mark.asyncio
async def test_integration_job_restores_tenant_context_and_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    session = _FakeSession()
    context_calls: list[object] = []
    adapter_calls: list[tuple[str, str, dict[str, object]]] = []
    registry = PlatformAdapterRegistry()
    registry.register("yandex", lambda: _RecordingAdapter(adapter_calls))

    async def set_context(_session: object, actual_tenant_id: object) -> None:
        context_calls.append(actual_tenant_id)

    monkeypatch.setattr(integration_tasks, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(integration_tasks, "set_tenant_rls_context", set_context)
    monkeypatch.setattr(
        integration_tasks,
        "decrypt_token",
        lambda _ciphertext: json.dumps({"access_token": "secret-token"}),
    )
    monkeypatch.setattr(integration_tasks, "PLATFORM_ADAPTER_REGISTRY", registry)

    await integration_tasks.process_outbox_integration_job(
        {},
        str(uuid4()),
        str(tenant_id),
        {
            "tenant_id": str(tenant_id),
            "platform": " YANDEX ",
            "review_external_id": "review-123",
            "text": "Thank you",
        },
    )

    assert context_calls == [tenant_id]
    assert adapter_calls == [
        ("review-123", "Thank you", {"access_token": "secret-token"})
    ]


@pytest.mark.asyncio
async def test_integration_job_retries_transient_platform_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    registry = PlatformAdapterRegistry()

    class _RetryingAdapter(BasePlatformAdapter):
        async def publish_reply(
            self,
            _review_external_id: str,
            _text: str,
            _credentials: dict[str, object],
        ) -> str:
            raise TransientAPIError("temporary failure", retry_after=17)

    registry.register("yandex", _RetryingAdapter)
    monkeypatch.setattr(integration_tasks, "AsyncSessionLocal", _FakeSession)
    monkeypatch.setattr(integration_tasks, "set_tenant_rls_context", AsyncMock())
    monkeypatch.setattr(
        integration_tasks,
        "decrypt_token",
        lambda _ciphertext: json.dumps({"access_token": "secret-token"}),
    )
    monkeypatch.setattr(integration_tasks, "PLATFORM_ADAPTER_REGISTRY", registry)

    from arq import Retry

    with pytest.raises(Retry):
        await integration_tasks.process_outbox_integration_job(
            {},
            str(uuid4()),
            str(tenant_id),
            {
                "tenant_id": str(tenant_id),
                "platform": "yandex",
                "review_external_id": "review-123",
                "text": "Thank you",
            },
        )
