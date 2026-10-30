from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, Header, HTTPException, status

from app.api.v1.routes import external_api
from app.core.anonymizer import anonymize_author_name
from app.core.api_keys import verify_api_key


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.add = Mock(side_effect=self.added.append)
        self.flush = AsyncMock(side_effect=self._assign_ids)
        self.commit = AsyncMock()
        self.close = AsyncMock()
        self.execute = AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: None)
        )

    async def _assign_ids(self) -> None:
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid4()


class FakeArqPool:
    def __init__(self) -> None:
        self.enqueue_job = AsyncMock(return_value=object())


@pytest_asyncio.fixture
async def external_client() -> (
    AsyncIterator[tuple[httpx.AsyncClient, FakeSession, FakeArqPool, UUID]]
):
    tenant_id = uuid4()
    session = FakeSession()
    arq_pool = FakeArqPool()
    app = FastAPI()
    app.include_router(external_api.router)
    app.state.redis_pool = arq_pool

    async def authenticate(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> UUID:
        if x_api_key != "valid-test-key":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
            )
        return tenant_id

    async def mock_session() -> AsyncIterator[FakeSession]:
        yield session

    async def allow_rate_limit() -> None:
        return None

    app.dependency_overrides[verify_api_key] = authenticate
    app.dependency_overrides[external_api.get_external_db_session] = mock_session
    app.dependency_overrides[external_api.external_rate_limit] = allow_rate_limit

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, session, arq_pool, tenant_id


@pytest.mark.asyncio
async def test_submit_reviews_analyzes_locally_and_persists_safe_metrics(
    external_client: tuple[httpx.AsyncClient, FakeSession, FakeArqPool, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, arq_pool, tenant_id = external_client
    monkeypatch.setattr(
        external_api,
        "enforce_reviews_quota",
        AsyncMock(return_value=None),
    )

    response = await client.post(
        "/api/v1/external/reviews",
        headers={"X-API-Key": "valid-test-key"},
        json={
            "data_origin": "customer_provided",
            "reviews": [
                {
                    "text": "Great service",
                    "rating": 5,
                    "platform": "google",
                    "published_at": "2026-01-01T12:00:00Z",
                }
            ],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["tenant_id"] == str(tenant_id)
    saved_review = session.added[-1]
    assert payload["review_ids"] == [str(saved_review.id)]
    assert saved_review.author_name == anonymize_author_name()
    assert saved_review.text == "Положительный отзыв; оценка 5/5."
    assert saved_review.tags == ["SERVICE"]
    assert not hasattr(saved_review, "external_review_id")
    assert not hasattr(saved_review, "author_avatar_url")
    assert not hasattr(saved_review, "author_profile_url")
    session.flush.assert_awaited()
    session.commit.assert_awaited_once()
    arq_pool.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [{}, {"X-API-Key": "invalid-test-key"}],
    ids=["missing-key", "invalid-key"],
)
async def test_submit_reviews_rejects_missing_or_invalid_api_key(
    external_client: tuple[httpx.AsyncClient, FakeSession, FakeArqPool, UUID],
    headers: dict[str, str],
) -> None:
    client, session, arq_pool, _ = external_client

    response = await client.post(
        "/api/v1/external/reviews",
        headers=headers,
        json={
            "data_origin": "customer_provided",
            "reviews": [
                {
                    "text": "Review",
                    "rating": 4,
                    "platform": "google",
                    "published_at": "2026-01-01T12:00:00Z",
                }
            ],
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    session.add.assert_not_called()
    arq_pool.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_reviews_returns_payment_required_when_quota_is_exceeded(
    external_client: tuple[httpx.AsyncClient, FakeSession, FakeArqPool, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session, arq_pool, tenant_id = external_client
    monkeypatch.setattr(
        external_api,
        "enforce_reviews_quota",
        AsyncMock(
            side_effect=HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Review quota exceeded",
            )
        ),
    )

    response = await client.post(
        "/api/v1/external/reviews",
        headers={"X-API-Key": "valid-test-key"},
        json={
            "data_origin": "customer_provided",
            "reviews": [
                {
                    "text": "Review",
                    "rating": 4,
                    "platform": "google",
                    "published_at": "2026-01-01T12:00:00Z",
                }
            ],
        },
    )

    assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
    assert response.json()["detail"] == "Review quota exceeded"
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    arq_pool.enqueue_job.assert_not_awaited()
    external_api.enforce_reviews_quota.assert_awaited_once_with(session, tenant_id)


@pytest.mark.asyncio
async def test_get_review_returns_404_when_review_is_not_visible_to_tenant(
    external_client: tuple[httpx.AsyncClient, FakeSession, FakeArqPool, UUID],
) -> None:
    client, session, _, _ = external_client
    result = Mock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    response = await client.get(
        f"/api/v1/external/reviews/{uuid4()}",
        headers={"X-API-Key": "valid-test-key"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Review not found"
    statement = session.execute.await_args.args[0]
    assert "reviews.company_id" in str(statement)


@pytest.mark.asyncio
async def test_get_analytics_returns_tenant_aggregates(
    external_client: tuple[httpx.AsyncClient, FakeSession, FakeArqPool, UUID],
) -> None:
    client, session, _, _ = external_client
    aggregate_result = Mock()
    aggregate_result.one.return_value = SimpleNamespace(
        total=3,
        avg_rating=4.5,
        critical=1,
        resolved=2,
    )
    sentiment_result = Mock()
    sentiment_result.all.return_value = [("positive", 2), (None, 1)]
    session.execute.side_effect = [aggregate_result, sentiment_result]

    response = await client.get(
        "/api/v1/external/analytics?days=14",
        headers={"X-API-Key": "valid-test-key"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "total_reviews": 3,
        "sentiment": {
            "positive": 2,
            "negative": 0,
            "neutral": 0,
            "unclassified": 1,
        },
        "average_rating": 4.5,
        "critical_reviews": 1,
        "resolved_reviews": 2,
        "period_days": 14,
    }
    assert session.execute.await_count == 2
