import csv
import io
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.api.v1.routes import analytics
from app.api.v1.routes.analytics import router
from app.core.auth import get_current_tenant


class FakeResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[object, ...]]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.statement: object | None = None

    async def execute(self, statement: object) -> FakeResult:
        self.statement = statement
        return FakeResult(self.rows)


@pytest_asyncio.fixture
async def analytics_export_client() -> (
    AsyncIterator[tuple[httpx.AsyncClient, FakeSession, UUID]]
):
    tenant_id = uuid4()
    session = FakeSession(
        [
            (
                datetime(2026, 10, 19, 10, 30, tzinfo=timezone.utc),
                "google",
                2,
                "NEGATIVE",
                4,
                "Review text, with comma",
            ),
            (None, "yelp", 5, "POSITIVE", None, "Positive review"),
        ]
    )
    app = FastAPI()
    app.include_router(router)

    async def current_tenant() -> UUID:
        return tenant_id

    async def tenant_session() -> AsyncIterator[FakeSession]:
        yield session

    app.dependency_overrides[get_current_tenant] = current_tenant
    app.dependency_overrides[analytics.get_analytics_tenant_session] = tenant_session

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, session, tenant_id

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_reviews_returns_tenant_scoped_csv(
    analytics_export_client: tuple[httpx.AsyncClient, FakeSession, UUID],
) -> None:
    client, session, tenant_id = analytics_export_client

    response = await client.get("/api/v1/analytics/export")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == (
        'attachment; filename="serm_report.csv"'
    )
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows == [
        ["date", "platform", "rating", "sentiment", "threat_level", "text"],
        [
            "2026-10-19T10:30:00+00:00",
            "google",
            "2",
            "NEGATIVE",
            "4",
            "Review text, with comma",
        ],
        ["", "yelp", "5", "POSITIVE", "", "Positive review"],
    ]

    assert session.statement is not None
    statement = str(session.statement)
    assert "reviews.company_id" in statement
    assert tenant_id in session.statement.compile().params.values()
