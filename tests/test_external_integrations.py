import json
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from app.domain.reviews.publication import ReplyPublicationStatus
from app.infrastructure.integrations.review_platforms.base import (
    PermanentAPIError,
    TransientAPIError,
)
from app.infrastructure.integrations.review_platforms.yandex import (
    YandexBusinessAdapter,
)
from app.infrastructure.queue.worker import reply_tasks


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
        "app.infrastructure.integrations.review_platforms.yandex.httpx.AsyncClient",
        lambda **kwargs: original_async_client(
            transport=httpx.MockTransport(handle_request),
            **kwargs,
        ),
    )

    reply_id = await YandexBusinessAdapter("secret-token", {}).publish_reply(
        "review-123",
        "Thank you",
    )

    assert reply_id == "reply-123"
    assert requests[0].method == "POST"
    assert requests[0].headers["Authorization"] == "OAuth secret-token"
    assert json.loads(requests[0].content) == {"text": "Thank you"}


@pytest.mark.asyncio
async def test_yandex_adapter_refreshes_token_once_after_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    reply_url = "https://api.business.yandex.ru/v1/reviews/review-123/replies"

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == "https://oauth.yandex.com/1/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "refresh_token": "rotated-refresh-token",
                    "expires_in": 3600,
                },
            )
        if request.headers["Authorization"] == "OAuth old-access-token":
            return httpx.Response(401)
        return httpx.Response(200, json={"external_reply_id": "reply-123"})

    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.infrastructure.integrations.review_platforms.yandex.httpx.AsyncClient",
        lambda **kwargs: original_async_client(
            transport=httpx.MockTransport(handle_request),
            **kwargs,
        ),
    )
    monkeypatch.setattr(
        "app.infrastructure.integrations.review_platforms.yandex.get_settings",
        lambda: SimpleNamespace(
            yandex_oauth_client_id="client-id",
            yandex_oauth_client_secret=SecretStr("client-secret"),
        ),
    )

    adapter = YandexBusinessAdapter(
        "old-access-token",
        {},
        refresh_token="old-refresh-token",
    )

    assert await adapter.publish_reply("review-123", "Thanks") == "reply-123"
    assert [str(request.url) for request in requests] == [
        reply_url,
        "https://oauth.yandex.com/1/token",
        reply_url,
    ]
    assert requests[2].headers["Authorization"] == "OAuth new-access-token"
    assert adapter.refresh_token == "rotated-refresh-token"
    assert adapter.expires_at is not None


@pytest.mark.asyncio
async def test_yandex_adapter_does_not_refresh_without_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(401)

    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.infrastructure.integrations.review_platforms.yandex.httpx.AsyncClient",
        lambda **kwargs: original_async_client(
            transport=httpx.MockTransport(handle_request),
            **kwargs,
        ),
    )

    with pytest.raises(PermanentAPIError, match="refresh token is not configured"):
        await YandexBusinessAdapter("expired-token", {}).publish_reply(
            "review-123",
            "Thanks",
        )

    assert len(requests) == 1


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
        "app.infrastructure.integrations.review_platforms.yandex.httpx.AsyncClient",
        lambda **kwargs: original_async_client(
            transport=httpx.MockTransport(handle_request),
            **kwargs,
        ),
    )

    with pytest.raises(error_type) as caught:
        await YandexBusinessAdapter("secret-token", {}).publish_reply(
            "review-123",
            "Thank you",
        )

    if status_code == 429:
        assert isinstance(caught.value, TransientAPIError)
        assert caught.value.retry_after == 12.0


def _publication() -> reply_tasks.ReplyPublication:
    return reply_tasks.ReplyPublication(
        integration_id=UUID("44444444-4444-4444-4444-444444444444"),
        review_external_id="external-review-123",
        reply_text="Thank you",
        platform="yandex",
        api_key="secret-token",
        encrypted_api_key="encrypted-secret-token",
        refresh_token=None,
        encrypted_refresh_token=None,
        expires_at=None,
        meta_config={},
    )


@pytest.mark.asyncio
async def test_reply_task_runs_db_http_db_phases_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    async def load(_tenant_id, _review_id):
        events.append("phase-1-db")
        return _publication()

    class _Adapter:
        api_key = "secret-token"
        refresh_token = None
        expires_at = None

        async def publish_reply(self, _review_id: str, _text: str) -> str:
            events.append("phase-2-http")
            return "external-reply-123"

    def get_adapter(*_args, **_kwargs):
        return _Adapter()

    async def record(_tenant_id, _review_id, **kwargs):
        assert kwargs["status"] is ReplyPublicationStatus.PUBLISHED
        assert kwargs["external_reply_id"] == "external-reply-123"
        events.append("phase-3-db")
        return True

    monkeypatch.setattr(reply_tasks, "_load_reply_publication", load)
    monkeypatch.setattr(reply_tasks.PlatformAdapterFactory, "get_adapter", get_adapter)
    monkeypatch.setattr(reply_tasks, "_record_publish_result", record)

    tenant_id = "11111111-1111-1111-1111-111111111111"
    review_id = "22222222-2222-2222-2222-222222222222"
    await reply_tasks.publish_review_reply(
        {},
        "33333333-3333-3333-3333-333333333333",
        tenant_id,
        {"tenant_id": tenant_id, "review_id": review_id},
    )

    assert events == ["phase-1-db", "phase-2-http", "phase-3-db"]


@pytest.mark.asyncio
async def test_reply_task_retries_transient_errors_after_recording_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arq import Retry

    recorded_results = []
    monkeypatch.setattr(reply_tasks, "_load_reply_publication", _load_publication)

    class _RetryingAdapter:
        api_key = "secret-token"
        refresh_token = None
        expires_at = None

        async def publish_reply(self, _review_id: str, _text: str) -> str:
            raise TransientAPIError("temporary failure", retry_after=17)

    monkeypatch.setattr(
        reply_tasks.PlatformAdapterFactory,
        "get_adapter",
        lambda *_args, **_kwargs: _RetryingAdapter(),
    )

    async def record(_tenant_id, _review_id, **kwargs):
        recorded_results.append(kwargs)
        return True

    monkeypatch.setattr(reply_tasks, "_record_publish_result", record)
    tenant_id = "11111111-1111-1111-1111-111111111111"
    review_id = "22222222-2222-2222-2222-222222222222"

    with pytest.raises(Retry):
        await reply_tasks.publish_review_reply(
            {},
            "33333333-3333-3333-3333-333333333333",
            tenant_id,
            {"tenant_id": tenant_id, "review_id": review_id},
        )

    assert recorded_results[0]["status"] is ReplyPublicationStatus.QUEUED_OUTBOX
    assert recorded_results[0]["failure_reason"] == "temporary failure"


@pytest.mark.asyncio
async def test_reply_task_marks_permanent_error_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = []
    monkeypatch.setattr(reply_tasks, "_load_reply_publication", _load_publication)

    class _PermanentAdapter:
        api_key = "secret-token"
        refresh_token = None
        expires_at = None

        async def publish_reply(self, _review_id: str, _text: str) -> str:
            raise PermanentAPIError("Yandex returned 401", status_code=401)

    monkeypatch.setattr(
        reply_tasks.PlatformAdapterFactory,
        "get_adapter",
        lambda *_args, **_kwargs: _PermanentAdapter(),
    )

    async def record(_tenant_id, _review_id, **kwargs):
        results.append(kwargs)
        return True

    monkeypatch.setattr(reply_tasks, "_record_publish_result", record)
    tenant_id = "11111111-1111-1111-1111-111111111111"
    review_id = "22222222-2222-2222-2222-222222222222"
    await reply_tasks.publish_review_reply(
        {},
        "33333333-3333-3333-3333-333333333333",
        tenant_id,
        {"tenant_id": tenant_id, "review_id": review_id},
    )

    assert results[0]["status"] is ReplyPublicationStatus.PUBLISH_FAILED
    assert results[0]["failure_reason"] == "Токен доступа истёк или недействителен."


@pytest.mark.asyncio
async def test_reply_task_persists_rotated_credentials_and_does_not_retry_published_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_results = []
    monkeypatch.setattr(reply_tasks, "_load_reply_publication", _load_publication)

    class _RetryingAdapter:
        api_key = "secret-token"
        refresh_token = None
        expires_at = None

        async def publish_reply(self, _review_id: str, _text: str) -> str:
            self.api_key = "rotated-access-token"
            self.refresh_token = "rotated-refresh-token"
            raise TransientAPIError("temporary failure", retry_after=17)

    monkeypatch.setattr(
        reply_tasks.PlatformAdapterFactory,
        "get_adapter",
        lambda *_args, **_kwargs: _RetryingAdapter(),
    )

    async def record(_tenant_id, _review_id, **kwargs):
        recorded_results.append(kwargs)
        return False

    monkeypatch.setattr(reply_tasks, "_record_publish_result", record)
    tenant_id = "11111111-1111-1111-1111-111111111111"
    review_id = "22222222-2222-2222-2222-222222222222"

    await reply_tasks.publish_review_reply(
        {},
        "33333333-3333-3333-3333-333333333333",
        tenant_id,
        {"tenant_id": tenant_id, "review_id": review_id},
    )

    credentials = recorded_results[0]["refreshed_credentials"]
    assert credentials.api_key == "rotated-access-token"
    assert credentials.refresh_token == "rotated-refresh-token"


@pytest.mark.asyncio
async def test_publish_result_does_not_overwrite_already_published_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    review_id = UUID("22222222-2222-2222-2222-222222222222")

    class _Transaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    class _Session:
        def begin(self):
            return _Transaction()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, statement, _parameters):
            assert "status IS DISTINCT FROM :published_status" in str(statement)
            return type("UpdateResult", (), {"rowcount": 0})()

        async def scalar(self, _statement, _parameters):
            return ReplyPublicationStatus.PUBLISHED.value

    monkeypatch.setattr(reply_tasks, "AsyncSessionLocal", _Session)

    async def set_tenant_context(_session, _tenant_id):
        return None

    monkeypatch.setattr(reply_tasks, "set_tenant_rls_context", set_tenant_context)

    updated = await reply_tasks._record_publish_result(
        tenant_id,
        review_id,
        status=ReplyPublicationStatus.QUEUED_OUTBOX,
        failure_reason="late timeout",
    )

    assert updated is False


async def _load_publication(_tenant_id, _review_id):
    return _publication()
