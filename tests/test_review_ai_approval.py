from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import get_current_tenant
from app.core.dependencies import get_tenant_db
from app.main import app
from app.models.economics import Company, Platform, Review
from app.schemas.economics import ReviewStatus


@pytest.mark.asyncio
async def test_approve_ai_response_is_disabled_without_changing_review(
    rate_limit_pool,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Company.metadata.create_all)

    tenant_id = uuid4()
    review_id = uuid4()

    async with session_factory.begin() as session:
        session.add_all(
            [
                Company(
                    id=tenant_id,
                    name="Tenant",
                    average_check=0,
                    margin_percent=0,
                    cac=0,
                    base_ltv=0,
                ),
            ]
        )
        await session.flush()
        platform = Platform(id=uuid4(), company_id=tenant_id, name="test")
        session.add(platform)
        await session.flush()
        session.add(
            Review(
                id=review_id,
                platform_id=platform.id,
                company_id=tenant_id,
                author_name="Reviewer",
                rating=3,
                text="Test review",
                auto_reply="AI draft",
                ai_pending=True,
                status=ReviewStatus.NEW,
            )
        )

    async def tenant_from_header(x_test_tenant: UUID = Header()) -> UUID:
        return x_test_tenant

    async def database_session() -> AsyncIterator[AsyncSession]:
        async with session_factory.begin() as session:
            yield session

    previous_tenant_override = app.dependency_overrides.get(get_current_tenant)
    previous_db_override = app.dependency_overrides.get(get_tenant_db)
    previous_redis_pool = app.state.redis_pool
    app.dependency_overrides[get_current_tenant] = tenant_from_header
    app.dependency_overrides[get_tenant_db] = database_session
    app.state.redis_pool = rate_limit_pool

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/reviews/{review_id}/approve-ai-response",
                headers={"x-test-tenant": str(tenant_id)},
            )
            assert response.status_code == 410

            async with session_factory() as session:
                updated = await session.scalar(
                    select(Review).where(Review.id == review_id)
                )
                assert updated is not None
                assert updated.status is ReviewStatus.NEW
                assert updated.ai_pending is True
    finally:
        if previous_tenant_override is None:
            app.dependency_overrides.pop(get_current_tenant, None)
        else:
            app.dependency_overrides[get_current_tenant] = previous_tenant_override
        if previous_db_override is None:
            app.dependency_overrides.pop(get_tenant_db, None)
        else:
            app.dependency_overrides[get_tenant_db] = previous_db_override
        app.state.redis_pool = previous_redis_pool
        await engine.dispose()
