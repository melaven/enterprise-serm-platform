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

    async def get_job_status(
        self, job_id: str, tenant_id: UUID
    ) -> ParserJobStatus:
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
    app.include_router(router)

    async def tenant_id() -> UUID:
        return TENANT_ID

    async def parser_queue() -> FakeParserQueue:
        return FakeParserQueue()

    async def parser_limits() -> dict[str, object]:
        return {}

    app.dependency_overrides[get_current_tenant] = tenant_id
    app.dependency_overrides[get_parser_queue] = parser_queue
    app.dependency_overrides[check_parser_limits] = parser_limits
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_frontend_parser_routes_match_contract(parser_client: TestClient) -> None:
    accepted = parser_client.post(
        "/api/v1/parser/start",
        json={"platform": "2gis", "url": "https://2gis.ru/example"},
    )
    assert accepted.status_code == 202
    assert accepted.json() == {"job_id": "parser-job-1"}

    invalid_request = parser_client.post(
        "/api/v1/parser/start",
        json={
            "platform": "2gis",
            "url": "https://2gis.ru/example",
            "unexpected": True,
        },
    )
    assert invalid_request.status_code == 422

    unsupported_platform = parser_client.post(
        "/api/v1/parser/start",
        json={
            "platform": "trustpilot",
            "url": "https://www.trustpilot.com/review/example.com",
        },
    )
    assert unsupported_platform.status_code == 422

    status = parser_client.get("/api/v1/parser/jobs/parser-job-1")
    assert status.status_code == 200
    assert status.json() == {
        "job_id": "parser-job-1",
        "state": "succeeded",
        "result": {
            "reviews_found": 24,
            "reviews_new": 6,
            "reviews_saved": 6,
            "ai_enriched": 5,
            "ai_pending": 1,
            "duration_ms": 8200,
        },
        "error": None,
    }


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

        async def get_job_status(
            self, job_id: str, tenant_id: UUID
        ) -> ParserJobStatus:
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

    response = parser_client.get("/api/v1/parser/stream/parser-job-1")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in response.text
    assert '"state":"queued"' in response.text
    assert '"state":"in_progress"' in response.text
    assert '"state":"analyzing"' in response.text
    assert '"state":"succeeded"' in response.text
    assert (
        response.text.index('"state":"queued"')
        < response.text.index('"state":"in_progress"')
        < response.text.index('"state":"analyzing"')
        < response.text.index('"state":"succeeded"')
    )
    assert dependency_closed == [True]
