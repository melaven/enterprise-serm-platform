from collections.abc import AsyncIterator
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routes import analytics, reviews
from app.core.auth import get_current_tenant
from app.core.dependencies import get_tenant_db


@pytest.fixture
def dashboard_client() -> tuple[TestClient, UUID, AsyncMock]:
    tenant_id = uuid4()
    session = AsyncMock()
    app = FastAPI()
    app.include_router(analytics.router)
    app.include_router(reviews.router, prefix="/api/v1/reviews")

    async def current_tenant() -> UUID:
        return tenant_id

    async def tenant_session() -> AsyncIterator[AsyncMock]:
        yield session

    app.dependency_overrides[get_current_tenant] = current_tenant
    app.dependency_overrides[get_tenant_db] = tenant_session
    return TestClient(app), tenant_id, session


def test_analytics_dashboard_returns_frontend_metrics(
    dashboard_client: tuple[TestClient, UUID, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _tenant_id, _session = dashboard_client
    today = date.today()
    metrics = {
        "total_reviews": 2,
        "average_rating": 4.5,
        "sentiment": {
            "positive": 1,
            "neutral": 0,
            "negative": 1,
            "unclassified": 0,
            "total": 2,
        },
        "timeline": [{"date": today, "reviews": 2}],
        "critical_reviews": 1,
        "ai_pending": 0,
        "period": {"date_from": today, "date_to": today},
    }
    monkeypatch.setattr(
        analytics, "get_dashboard_metrics", AsyncMock(return_value=metrics)
    )

    response = client.get("/api/v1/analytics/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            **metrics,
            "timeline": [{"date": today.isoformat(), "reviews": 2}],
            "period": {
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
        },
    }


def test_archive_marks_only_tenant_review(
    dashboard_client: tuple[TestClient, UUID, AsyncMock],
) -> None:
    client, _tenant_id, session = dashboard_client
    review_id = uuid4()
    review = SimpleNamespace(id=review_id, is_archived=False)
    result = SimpleNamespace(scalar_one_or_none=Mock(return_value=review))
    session.execute.return_value = result

    response = client.post(f"/api/v1/reviews/{review_id}/archive")

    assert response.status_code == 204
    assert review.is_archived is True
    session.flush.assert_awaited_once()


def test_archive_returns_not_found_for_other_tenant_review(
    dashboard_client: tuple[TestClient, UUID, AsyncMock],
) -> None:
    client, _tenant_id, session = dashboard_client
    result = SimpleNamespace(scalar_one_or_none=Mock(return_value=None))
    session.execute.return_value = result

    response = client.post(f"/api/v1/reviews/{uuid4()}/archive")

    assert response.status_code == 404
    assert response.json()["detail"] == "Review not found"
