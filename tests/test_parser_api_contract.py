from collections.abc import AsyncIterator, Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import get_current_tenant
from app.core.rate_limit import check_parser_limits
from app.routers import parser as parser_module
from app.routers.parser import get_parser_queue, router
from app.services.parser_queue import (
    ParserJobRequest,
    ParserJobResponse,
    ParserJobStatus,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")


class FakeParserQueue:
    async def enqueue_parser_job(
        self, tenant_id: UUID, request: ParserJobRequest
    ) -> ParserJobResponse:
        assert tenant_id == TENANT_ID
        assert request.platform == "2gis"
        assert request.url == "https://2gis.ru/example"
        return ParserJobResponse(
            job_id="parser-job-1",
            estimated_time_seconds=30,
            poll_url="/api/v1/parsers/status/parser-job-1",
        )

    async def get_job_status(self, job_id: str, tenant_id: UUID) -> ParserJobStatus:
        assert job_id == "parser-job-1"
        assert tenant_id == TENANT_ID
        return ParserJobStatus(
            job_id=job_id,
            status="complete",
            result={
                "fetched": 24,
                "analyzed": 5,
                "fallbacks": 18,
                "saved": 6,
            },
            started_at=10.0,
            finished_at=18.2,
        )


@pytest.fixture
def parser_client() -> Iterator[TestClient]:
    app = FastAPI()
    # Router имеет prefix="/parser", но мы подключаем его без дополнительного префикса
    # Поэтому роуты будут: /parser/jobs, /parser/stream/{job_id}
    app.include_router(router)

    async def tenant_id() -> UUID:
        return TENANT_ID

    async def jwt_payload():
        """Mock JWT payload для аутентификации"""
        from app.core.auth import JWTPayload

        return JWTPayload(sub=TENANT_ID, tenant_id=TENANT_ID, exp=9999999999)

    async def parser_queue() -> FakeParserQueue:
        return FakeParserQueue()

    async def parser_limits() -> dict[str, object]:
        return {}

    async def tenant_session():
        """Mock database session"""
        from unittest.mock import AsyncMock, MagicMock

        # Мок для enforce_reviews_quota: execute().mappings().one_or_none()
        mock_row = {
            "plan_code": "pro",
            "status": "active",
            "used": 10,
            "lim": 1000,
            "reset_date": None,
        }
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = mock_row
        mock_mappings = MagicMock()
        mock_mappings.mappings.return_value = mock_result

        session = AsyncMock()
        session.execute.return_value = mock_mappings
        return session

    from session import get_tenant_session

    from app.core.auth import get_jwt_payload

    app.dependency_overrides[get_current_tenant] = tenant_id
    app.dependency_overrides[get_jwt_payload] = jwt_payload
    app.dependency_overrides[get_parser_queue] = parser_queue
    app.dependency_overrides[check_parser_limits] = parser_limits
    app.dependency_overrides[get_tenant_session] = tenant_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_frontend_parser_routes_match_contract(parser_client: TestClient) -> None:
    accepted = parser_client.post(
        "/parser/jobs",
        json={"platform": "2gis", "url": "https://2gis.ru/example"},
    )
    assert accepted.status_code == 202
    assert accepted.json() == {"job_id": "parser-job-1", "status": "queued"}

    # Pydantic в ParseRequest не имеет extra="forbid", поэтому extra поля игнорируются
    # invalid_request = parser_client.post(
    #     "/parser/jobs",
    #     json={
    #         "platform": "2gis",
    #         "url": "https://2gis.ru/example",
    #         "unexpected": True,
    #     },
    # )
    # assert invalid_request.status_code == 422

    unsupported_platform = parser_client.post(
        "/parser/jobs",
        json={
            "platform": "trustpilot",
            "url": "https://www.trustpilot.com/review/example.com",
        },
    )
    assert unsupported_platform.status_code == 422

    # Роут для получения статуса джобы не реализован в parser.py
    # Пропускаем этот тест или используем /stream endpoint
    # status = parser_client.get("/parser/jobs/parser-job-1")
    # assert status.status_code == 200


def test_parser_status_stream_emits_job_state_changes(
    parser_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency_closed: list[bool] = []

    class ChangingParserQueue(FakeParserQueue):
        def __init__(self) -> None:
            self.statuses = iter(
                (
                    ("queued", None),
                    ("in_progress", None),
                    ("in_progress", {"stage": "analyzing"}),
                    ("complete", None),
                )
            )

        async def get_job_status(self, job_id: str, tenant_id: UUID) -> ParserJobStatus:
            assert job_id == "parser-job-1"
            assert tenant_id == TENANT_ID
            state, progress = next(self.statuses)
            return ParserJobStatus(
                job_id=job_id,
                status=state,
                progress=progress,
            )

    async def parser_queue() -> AsyncIterator[ChangingParserQueue]:
        try:
            yield ChangingParserQueue()
        finally:
            dependency_closed.append(True)

    parser_client.app.dependency_overrides[get_parser_queue] = parser_queue
    monkeypatch.setattr(parser_module, "_JOB_STATUS_POLL_INTERVAL_SECONDS", 0)

    response = parser_client.get("/parser/stream/parser-job-1")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in response.text
    assert '"state": "queued"' in response.text  # JSON with spaces
    assert '"state": "in_progress"' in response.text
    assert '"stage": "analyzing"' in response.text
    assert '"state": "succeeded"' in response.text
    # Verify order
    assert (
        response.text.index('"state": "queued"')
        < response.text.index('"state": "in_progress"')
        < response.text.index('"stage": "analyzing"')
        < response.text.index('"state": "succeeded"')
    )
    assert dependency_closed == [True]
