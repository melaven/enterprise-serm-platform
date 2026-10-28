from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.auth import JWTPayload, get_current_tenant, get_jwt_payload
from app.core.rate_limit import RateLimitExceeded, check_parser_limits
from app.main import app

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def cors_client() -> Iterator[TestClient]:
    async def tenant_id() -> UUID:
        return TENANT_ID

    async def jwt_payload() -> JWTPayload:
        return JWTPayload(sub=str(TENANT_ID), tenant_id=TENANT_ID, role="user")

    async def rate_limit() -> None:
        raise RateLimitExceeded(limit=1, window=60, retry_after=23, tenant_id=TENANT_ID)

    async def mock_session() -> Any:
        """Mock session dependency"""
        return None

    dependencies = {
        get_current_tenant: tenant_id,
        get_jwt_payload: jwt_payload,
        check_parser_limits: rate_limit,
    }

    # Try to override session dependency if it exists
    try:
        from session import get_tenant_session

        dependencies[get_tenant_session] = mock_session
    except ImportError:
        try:
            from app.core.tenant_session import get_tenant_session

            dependencies[get_tenant_session] = mock_session
        except ImportError:
            pass
    previous = {
        dependency: app.dependency_overrides.get(dependency)
        for dependency in dependencies
    }
    app.dependency_overrides.update(dependencies)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        for dependency, override in previous.items():
            if override is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = override


def test_cors_exposes_retry_after_and_correlation_id(cors_client: TestClient) -> None:
    response = cors_client.post(
        "/parser/jobs",
        json={"platform": "2gis", "url": "https://2gis.ru/example"},
        headers={"Origin": "https://frontend.example"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "23"
    assert response.headers.get("x-correlation-id")
    assert {
        header.strip().lower()
        for header in response.headers["access-control-expose-headers"].split(",")
    } == {"retry-after", "x-correlation-id"}
