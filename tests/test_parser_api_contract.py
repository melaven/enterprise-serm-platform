from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import check_parser_limits
from app.routers.parser import router


@pytest.fixture
def parser_client() -> Iterator[TestClient]:
    app = FastAPI()
    # Router имеет prefix="/parser", но мы подключаем его без дополнительного префикса
    # Поэтому роуты будут: /parser/jobs, /parser/stream/{job_id}
    app.include_router(router)

    async def jwt_payload():
        """Mock JWT payload для аутентификации"""
        from app.core.auth import JWTPayload

        tenant_id = UUID("11111111-1111-1111-1111-111111111111")
        return JWTPayload(sub=tenant_id, tenant_id=tenant_id, exp=9999999999)

    async def parser_limits() -> dict[str, object]:
        return {}

    from app.core.auth import get_jwt_payload

    app.dependency_overrides[get_jwt_payload] = jwt_payload
    app.dependency_overrides[check_parser_limits] = parser_limits
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_frontend_parser_routes_match_contract(parser_client: TestClient) -> None:
    disabled = parser_client.post(
        "/parser/jobs",
        json={"platform": "2gis", "url": "https://2gis.ru/example"},
    )
    assert disabled.status_code == 410
    assert disabled.json()["detail"].startswith("Public-page scraping is disabled")


def test_parser_status_stream_is_disabled(parser_client: TestClient) -> None:
    response = parser_client.get("/parser/stream/parser-job-1")

    assert response.status_code == 410
    assert response.json()["detail"] == "Public-page scraping jobs are disabled"
