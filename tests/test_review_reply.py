from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.core.auth import get_current_tenant
from app.core.dependencies import get_tenant_db
from app.models.economics import PlatformIntegration
from app.routers.reviews import router
from app.services.worker import reply_tasks


class FakeScalars:
    def __init__(self, items: list[object]) -> None:
        self.items = items

    def all(self) -> list[object]:
        return self.items


class FakeReplySession:
    def __init__(self, review: object, integrations: list[object]) -> None:
        self.review = review
        self.integrations = integrations

    async def scalar(self, statement: object) -> object:
        return self.review

    async def scalars(self, statement: object) -> FakeScalars:
        return FakeScalars(self.integrations)


@pytest_asyncio.fixture
async def reply_client() -> (
    AsyncIterator[tuple[httpx.AsyncClient, UUID, UUID, SimpleNamespace]]
):
    tenant_id = uuid4()
    review_id = uuid4()
    integration = PlatformIntegration(
        company_id=tenant_id,
        platform="google_business",
        encrypted_api_key="encrypted-token",
        external_account_id="account-id",
        external_location_id="location-id",
        is_active=True,
    )
    review = SimpleNamespace(
        id=review_id,
        company_id=tenant_id,
        platform="google",
        external_review_id="review-id",
    )
    session = FakeReplySession(review, [integration])
    pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()))
    app = FastAPI()
    app.state.arq_pool = pool
    app.include_router(router, prefix="/api/v1/reviews")

    async def current_tenant() -> UUID:
        return tenant_id

    async def tenant_db() -> AsyncIterator[FakeReplySession]:
        yield session

    app.dependency_overrides[get_current_tenant] = current_tenant
    app.dependency_overrides[get_tenant_db] = tenant_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, tenant_id, review_id, pool
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reply_endpoint_enqueues_tenant_scoped_job(
    reply_client: tuple[httpx.AsyncClient, UUID, UUID, SimpleNamespace],
) -> None:
    client, tenant_id, review_id, pool = reply_client
    response = await client.post(
        f"/api/v1/reviews/{review_id}/reply",
        json={"reply_text": "Thank you for your feedback."},
    )

    assert response.status_code == 202
    assert response.json() == {
        "review_id": str(review_id),
        "status": "queued",
        "job_id": f"review-reply-{review_id}",
    }
    pool.enqueue_job.assert_awaited_once_with(
        "publish_review_reply",
        str(tenant_id),
        str(review_id),
        "Thank you for your feedback.",
        _job_id=f"review-reply-{review_id}",
    )


@pytest.mark.asyncio
async def test_publish_worker_sends_google_reply_and_persists_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    review_id = uuid4()
    review = SimpleNamespace(
        id=review_id,
        company_id=tenant_id,
        platform="google_business",
        external_review_id="review/id",
        si_response=None,
        auto_reply=None,
        status=None,
        ai_pending=True,
    )
    integration = SimpleNamespace(
        platform="google_business",
        is_active=True,
        external_account_id="account",
        external_location_id="location",
        api_key="access-token",
    )

    class FakeSession:
        commits = 0

        async def scalar(self, statement: object) -> object:
            return review

        async def scalars(self, statement: object) -> FakeScalars:
            return FakeScalars([integration])

        async def commit(self) -> None:
            self.commits += 1

        async def rollback(self) -> None:
            raise AssertionError("unexpected rollback")

        async def close(self) -> None:
            return None

    session = FakeSession()
    monkeypatch.setattr(
        reply_tasks,
        "get_tenant_session",
        AsyncMock(return_value=session),
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def put(
            self,
            url: str,
            *,
            headers: dict[str, str],
            json: dict[str, str],
        ) -> FakeResponse:
            self.calls.append((url, headers, json))
            return FakeResponse()

    clients: list[FakeClient] = []

    def make_client(**kwargs: object) -> FakeClient:
        client = FakeClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(reply_tasks.httpx, "AsyncClient", make_client)
    result = await reply_tasks.publish_review_reply(
        {},
        str(tenant_id),
        str(review_id),
        "A response edited by the business.",
    )

    assert result == {"review_id": str(review_id), "status": "published"}
    assert clients[0].calls == [
        (
            "https://mybusiness.googleapis.com/v4/accounts/account/locations/"
            "location/reviews/review%2Fid/reply",
            {"Authorization": "Bearer access-token"},
            {"comment": "A response edited by the business."},
        )
    ]
    assert review.si_response == "A response edited by the business."
    assert session.commits == 1
