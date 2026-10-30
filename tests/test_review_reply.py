from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1.routes.reviews import router


@pytest.mark.asyncio
async def test_reply_endpoint_is_disabled_without_persisted_source_ids() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/reviews")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(f"/api/v1/reviews/{uuid4()}/reply")

    assert response.status_code == 501
    assert response.json()["detail"] == (
        "Reply publishing is disabled because external review IDs are not stored"
    )
