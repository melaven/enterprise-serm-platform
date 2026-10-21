from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.routers import external_api


class _ReviewSession:
    def __init__(self) -> None:
        self.reviews = []

    def add(self, review: object) -> None:
        self.reviews.append(review)

    async def execute(self, _statement: object) -> SimpleNamespace:
        return SimpleNamespace(scalar_one_or_none=lambda: None)

    async def flush(self) -> None:
        for review in self.reviews:
            if getattr(review, "id", None) is None:
                review.id = uuid4()
        return None

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_external_ingest_persists_only_safe_review_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    session = _ReviewSession()

    async def verify_key() -> UUID:
        return tenant_id

    async def db_session() -> AsyncIterator[_ReviewSession]:
        yield session

    async def no_op_quota(db: object, active_tenant: UUID) -> None:
        assert active_tenant == tenant_id

    monkeypatch.setattr(external_api, "enforce_reviews_quota", no_op_quota)

    app = FastAPI()
    app.include_router(external_api.router)
    app.dependency_overrides[external_api.verify_api_key] = verify_key
    app.dependency_overrides[external_api.get_external_db_session] = db_session
    app.dependency_overrides[external_api.external_rate_limit] = lambda: None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/external/reviews",
            json={
                "data_origin": "customer_provided",
                "reviews": [
                    {
                        "text": "Ivanov called from +7 999 123-45-67",
                        "rating": 2,
                        "platform": "google",
                        "published_at": "2026-01-01T12:00:00Z",
                    }
                ]
            },
        )

    assert response.status_code == 200
    saved = session.reviews[-1]
    assert saved.text == "Негативный отзыв; оценка 2/5."
    assert saved.author_name == "Автор отзыва"
    assert saved.tags == ["OTHER"]
    assert not hasattr(saved, "external_review_id")
    assert not hasattr(saved, "author_avatar_url")
    assert not hasattr(saved, "author_profile_url")
    assert saved.suggested_reply is None
    assert saved.auto_reply is None
    assert saved.ai_pending is False
    assert "+7 999 123-45-67" not in response.text
    assert "Ivanov" not in response.text
