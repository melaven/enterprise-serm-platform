from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_tenant
from app.core.rate_limit import RateLimitExceeded, check_parser_limits
from app.main import app
from app.routers.parser import get_parser_queue


TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def cors_client() -> Iterator[TestClient]:
    async def tenant_id() -> UUID:
        return TENANT_ID

    async def parser_queue() -> None:
        return None

    async def rate_limit() -> None:
        raise RateLimitExceeded(limit=1, window=60, retry_after=23, tenant_id=TENANT_ID)

    dependencies = {
        get_current_tenant: tenant_id,
        get_parser_queue: parser_queue,
        check_parser_limits: rate_limit,
    }
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
        "/api/v1/parser/start",
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
