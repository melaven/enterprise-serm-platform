from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.api.dependencies.tenant import get_current_user
from app.api.schemas.auth import AuthContext, JWTPayload
from app.api.v1.routes.reviews import router as reviews_router
from app.core.auth import get_jwt_payload
from app.core.dependencies import get_review_queue


class _FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    async def enqueue_job(
        self, function_name: str, *args: object, **kwargs: object
    ) -> object:
        self.calls.append((function_name, args, kwargs))
        return object()


def _create_app(
    company_id: UUID | None = None,
    queue: _FakeQueue | None = None,
    *,
    missing_tenant_context: bool = False,
) -> FastAPI:
    app = FastAPI()
    app.include_router(reviews_router, prefix="/api/v1/reviews")
    if company_id is not None:
        app.dependency_overrides[get_current_user] = lambda: AuthContext(
            user_id=uuid4(), company_id=company_id
        )
    if missing_tenant_context:
        app.dependency_overrides[get_jwt_payload] = lambda: JWTPayload(sub=uuid4())
    if queue is not None:
        app.dependency_overrides[get_review_queue] = lambda: queue
    return app


def _payload() -> dict[str, object]:
    return {
        "platform": "yandex",
        "external_id": "review-123",
        "raw_author": "Иван Петров",
        "raw_text": "Позвоните мне: 89001234567",
        "rating": 4,
        "published_at": datetime(2026, 10, 30, tzinfo=timezone.utc).isoformat(),
    }


@pytest.mark.asyncio
async def test_ingest_returns_202_and_enqueues_job() -> None:
    tenant_id = uuid4()
    queue = _FakeQueue()
    app = _create_app(tenant_id, queue)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/reviews/ingest", json=_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert UUID(body["job_id"])
    assert body["tenant_id"] == str(tenant_id)
    assert datetime.fromisoformat(body["queued_at"])
    assert len(queue.calls) == 1
    function_name, args, kwargs = queue.calls[0]
    assert function_name == "process_review_ingestion"
    assert args[0] == str(tenant_id)
    assert args[1]["raw_author"] == "Иван Петров"
    assert kwargs["_job_id"] == body["job_id"]


@pytest.mark.asyncio
async def test_ingest_rejects_a_different_tenant() -> None:
    queue = _FakeQueue()
    app = _create_app(uuid4(), queue)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/reviews/ingest",
            params={"company_id": str(uuid4())},
            json=_payload(),
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied to this tenant"
    assert queue.calls == []


@pytest.mark.asyncio
async def test_ingest_rejects_token_without_tenant_context() -> None:
    queue = _FakeQueue()
    app = _create_app(queue=queue, missing_tenant_context=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/reviews/ingest", json=_payload())

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Invalid authentication token: missing tenant context"
    )
    assert queue.calls == []
