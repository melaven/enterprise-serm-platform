from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routes.parser import router
from app.core.rate_limit import check_parser_limits


@pytest.fixture
def parser_client() -> Iterator[TestClient]:
    app = FastAPI()
    # Router имеет prefix="/parser", но мы подключаем его без дополнительного префикса
    # Поэтому роуты будут: /parser/jobs, /parser/stream/{job_id}
    app.include_router(router)
    app.include_router(router, prefix="/api/v1")

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


def test_mock_parser_endpoints_match_frontend_contract(
    parser_client: TestClient,
) -> None:
    started = parser_client.post(
        "/api/v1/parser/start",
        json={"platform": "2gis", "url": "https://2gis.ru/example"},
    )

    assert started.status_code == 202
    job_id = started.json()["job_id"]

    status_response = parser_client.get(f"/api/v1/parser/jobs/{job_id}")

    assert status_response.status_code == 200
    assert status_response.json() == {
        "job_id": job_id,
        "state": "succeeded",
        "result": {
            "reviews_found": 0,
            "reviews_new": 0,
            "reviews_saved": 0,
            "ai_enriched": 0,
            "ai_pending": 0,
            "duration_ms": 0,
        },
        "error": None,
    }
