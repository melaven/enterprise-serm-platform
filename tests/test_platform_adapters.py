from datetime import datetime, timezone

import httpx
import pytest
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
    ("status_code", "expected"), [(204, True), (400, False), (500, False)]
)
async def test_yandex_publish_reply_sends_request_and_reports_http_status(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected: bool,
) -> None:
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status_code)

    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.platforms.yandex.httpx.AsyncClient",
        lambda: original_async_client(transport=httpx.MockTransport(handle_request)),
    )

    adapter = YandexBusinessAdapter(
        "test-token",
        {"yandex_org_id": "org-123"},
    )
    result = await adapter.publish_reply("review-456", "Thanks for your feedback")

    assert result is expected
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == (
        "https://api.yandex.ru/v1/orgs/org-123/reviews/" "review-456/replies"
    )
    assert request.headers["Authorization"] == "OAuth test-token"
    assert request.read() == b'{"text":"Thanks for your feedback"}'


@pytest.mark.asyncio
async def test_yandex_publish_reply_requires_organization_id() -> None:
    adapter = YandexBusinessAdapter("test-token", {})

    with pytest.raises(
        ValueError,
        match="^Missing yandex_org_id in meta_config$",
    ):
        await adapter.publish_reply("review-456", "reply")
