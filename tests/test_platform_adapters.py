import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.dialects import postgresql

from app.models.economics import PlatformIntegration
from app.services.platforms import BasePlatformAdapter, PlatformAdapterFactory
from app.services.platforms.avito import AvitoAdapter
from app.services.platforms.google import GoogleBusinessAdapter
from app.services.platforms.scraper import OtzovikScraperAdapter
from app.services.platforms.twogis import TwoGisAdapter
from app.services.platforms.yandex import YandexBusinessAdapter


@pytest.mark.parametrize(
    ("platform", "adapter_type"),
    [
        ("google", GoogleBusinessAdapter),
        ("yandex", YandexBusinessAdapter),
        ("2gis", TwoGisAdapter),
        ("avito", AvitoAdapter),
        ("otzovik", OtzovikScraperAdapter),
    ],
)
def test_factory_creates_fresh_adapter_with_isolated_config(
    platform: str,
    adapter_type: type[BasePlatformAdapter],
) -> None:
    config: dict[str, object] = {"organization": {"id": "org-1"}}

    first = PlatformAdapterFactory.get_adapter(platform, "token-1", config)
    second = PlatformAdapterFactory.get_adapter(platform, "token-2", config)

    assert isinstance(first, adapter_type)
    assert first is not second
    assert first.api_key == "token-1"
    assert second.api_key == "token-2"
    assert first.meta_config == config
    assert first.meta_config is not config
    assert first.meta_config["organization"] is not config["organization"]


def test_factory_normalizes_platform_name() -> None:
    adapter = PlatformAdapterFactory.get_adapter(" YANDEX ", "token", {})

    assert isinstance(adapter, YandexBusinessAdapter)


def test_factory_rejects_unsupported_platform() -> None:
    with pytest.raises(ValueError, match="Unsupported platform"):
        PlatformAdapterFactory.get_adapter("trustpilot", "token", {})


def test_platform_adapter_base_is_abstract() -> None:
    with pytest.raises(TypeError):
        BasePlatformAdapter("token", {})


def test_platform_integration_metadata_is_non_null_jsonb_with_empty_default() -> None:
    column = PlatformIntegration.__table__.c.meta_config

    assert column.type.compile(dialect=postgresql.dialect()) == "JSONB"
    assert column.nullable is False
    assert column.default is not None
    assert column.default.is_callable
    assert column.server_default is not None
    assert str(column.server_default.arg) == "'{}'"


@pytest.mark.asyncio
async def test_provider_fetch_methods_fail_explicitly_until_implemented() -> None:
    adapter = YandexBusinessAdapter("token", {})
    since = datetime.now(timezone.utc)

    with pytest.raises(NotImplementedError, match="fetching is not implemented"):
        await adapter.fetch_reviews(since)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_type", "platform"),
    [
        (YandexBusinessAdapter, "Яндекс Бизнес"),
        (TwoGisAdapter, "2ГИС"),
        (AvitoAdapter, "Авито"),
        (OtzovikScraperAdapter, "Отзовик"),
    ],
)
async def test_manual_assistant_adapters_log_ready_reply_and_succeed(
    adapter_type: type[BasePlatformAdapter],
    platform: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    adapter = adapter_type("test-token", {})

    assert await adapter.publish_reply("review-456", "Thanks") is True
    assert (
        "Режим SI-Ассистента: текст готов для ручной публикации на площадке "
        f"{platform}"
    ) in caplog.text


@pytest.mark.asyncio
async def test_oauth_adapters_refresh_after_401_and_retry_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter_type = GoogleBusinessAdapter
    meta_config: dict[str, object] = {
        "external_account_id": "account-123",
        "external_location_id": "loc-456",
    }
    token_url = "https://oauth2.googleapis.com/token"
    auth_header = "Bearer"
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == token_url:
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "refresh_token": "rotated-refresh-token",
                    "expires_in": 3600,
                },
            )
        if request.headers["Authorization"] == f"{auth_header} old-access-token":
            return httpx.Response(401)
        return httpx.Response(200, json={"reviews": []})

    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.platforms.google.httpx.AsyncClient",
        lambda **kwargs: original_async_client(
            transport=httpx.MockTransport(handle_request),
            **kwargs,
        ),
    )
    monkeypatch.setattr(
        "app.services.platforms.google.get_settings",
        lambda: SimpleNamespace(
            **{
                "google_oauth_client_id": "client-id",
                "google_oauth_client_secret": SecretStr("client-secret"),
            }
        ),
    )

    adapter = adapter_type(
        "old-access-token",
        meta_config,
        refresh_token="old-refresh-token",
    )

    assert await adapter.fetch_reviews(datetime.now(timezone.utc)) == []
    assert len(requests) == 3
    assert str(requests[1].url) == token_url
    assert requests[1].method == "POST"
    assert requests[2].headers["Authorization"] == f"{auth_header} new-access-token"
    assert adapter.api_key == "new-access-token"
    assert adapter.refresh_token == "rotated-refresh-token"
    assert adapter.expires_at is not None
