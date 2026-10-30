from collections.abc import AsyncIterator
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.api.v1.routes.platforms import router
from app.core.auth import get_current_tenant
from app.core.dependencies import get_tenant_db
from app.infrastructure.persistence.models import economics


class FakeIntegrationSession:
    def __init__(self) -> None:
        self.record = None
        self.add = Mock(side_effect=self._add)

    def _add(self, record: object) -> None:
        self.record = record

    async def scalar(self, statement: object) -> None:
        return None

    async def flush(self) -> None:
        return None


@pytest_asyncio.fixture
async def integration_client() -> (
    AsyncIterator[tuple[httpx.AsyncClient, FakeIntegrationSession, UUID]]
):
    tenant_id = uuid4()
    session = FakeIntegrationSession()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/platforms")

    async def current_tenant() -> UUID:
        return tenant_id

    async def tenant_db() -> AsyncIterator[FakeIntegrationSession]:
        yield session

    app.dependency_overrides[get_current_tenant] = current_tenant
    app.dependency_overrides[get_tenant_db] = tenant_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, session, tenant_id
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_google_business_integration_encrypts_and_hides_token(
    integration_client: tuple[httpx.AsyncClient, FakeIntegrationSession, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, tenant_id = integration_client
    monkeypatch.setattr(
        economics,
        "encrypt_token",
        lambda token: f"encrypted:{token}",
    )

    response = await client.put(
        "/api/v1/platforms/integrations/google-business",
        json={
            "access_token": "oauth-access-token",
            "refresh_token": "oauth-refresh-token",
            "external_account_id": "account-123",
            "external_location_id": "location-456",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "platform": "google_business",
        "external_account_id": "account-123",
        "external_location_id": "location-456",
        "is_active": True,
    }
    assert "oauth-access-token" not in response.text
    assert session.record.company_id == tenant_id
    assert session.record.encrypted_api_key == "encrypted:oauth-access-token"
    assert session.record.encrypted_refresh_token == "encrypted:oauth-refresh-token"
    assert "oauth-refresh-token" not in response.text


@pytest.mark.asyncio
async def test_google_business_integration_rejects_blank_location_id(
    integration_client: tuple[httpx.AsyncClient, FakeIntegrationSession, UUID],
) -> None:
    client, session, _ = integration_client

    response = await client.put(
        "/api/v1/platforms/integrations/google-business",
        json={
            "access_token": "oauth-access-token",
            "external_account_id": "account-123",
            "external_location_id": "   ",
        },
    )

    assert response.status_code == 422
    assert session.record is None
