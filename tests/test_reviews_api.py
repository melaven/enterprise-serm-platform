import asyncio
import os
from collections.abc import AsyncIterator, Callable, Iterator
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import Header
from sqlalchemy import make_url
from sqlalchemy import text as sa_text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api.schemas.auth import AuthContext
from app.api.schemas.economics import ReviewStatus
from app.core.database import Base
from app.infrastructure.persistence.models.economics import Company, Platform, Review

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/tenable_test"
)
TENANT_HEADER = "X-Test-Tenant"
ClientFactory = Callable[[UUID], httpx.AsyncClient]


async def _prepare_test_database() -> None:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            # asyncpg doesn't support multiple commands in one statement
            # Execute DROP and CREATE separately
            await connection.execute(sa_text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(sa_text("CREATE SCHEMA public"))
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def reviews_api_schema() -> Iterator[None]:
    database_name = make_url(TEST_DATABASE_URL).database or ""
    # Проверяем, что используется тестовая база (имя должно содержать test)
    if not (database_name.endswith("_test") or database_name.startswith("test_")):
        pytest.exit(
            f"TEST_DATABASE_URL must point to a test database (*_test or test_*), got {database_name!r}",
            returncode=2,
        )

    try:
        asyncio.run(_prepare_test_database())
    except (OSError, SQLAlchemyError) as error:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"PostgreSQL is not available at TEST_DATABASE_URL: {error}")
    yield


@pytest_asyncio.fixture
async def db_connection(reviews_api_schema: None) -> AsyncIterator[AsyncConnection]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                yield connection
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def review_tenants(db_connection: AsyncConnection) -> dict[str, UUID]:
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    platform_id = uuid4()

    async with AsyncSession(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    ) as session:
        tenant_a = Company(
            id=tenant_a_id,
            name="Tenant A",
            average_check=0,
            margin_percent=0,
            cac=0,
            base_ltv=0,
        )
        tenant_b = Company(
            id=tenant_b_id,
            name="Tenant B",
            average_check=0,
            margin_percent=0,
            cac=0,
            base_ltv=0,
        )
        session.add_all([tenant_a, tenant_b])
        await session.flush()

        session.add(
            Platform(
                id=platform_id,
                company_id=tenant_a_id,
                name="google",
            )
        )
        session.add_all(
            [
                Review(
                    id=uuid4(),
                    company_id=tenant_a_id,
                    platform_id=platform_id,
                    platform="google",
                    author_name="Автор отзыва",
                    rating=5,
                    text="Положительный отзыв; оценка 5/5.",
                    status=ReviewStatus.NEW,
                    sentiment="POSITIVE",
                    is_critical=False,
                ),
                Review(
                    id=uuid4(),
                    company_id=tenant_a_id,
                    platform_id=platform_id,
                    platform="google",
                    author_name="Автор отзыва",
                    rating=4,
                    text="Положительный отзыв; оценка 4/5.",
                    status=ReviewStatus.NEW,
                    sentiment="POSITIVE",
                    is_critical=False,
                ),
                Review(
                    id=uuid4(),
                    company_id=tenant_a_id,
                    platform_id=platform_id,
                    platform="google",
                    author_name="Автор отзыва",
                    rating=1,
                    text="Негативный отзыв; оценка 1/5.",
                    status=ReviewStatus.NEW,
                    sentiment="NEGATIVE",
                    is_critical=True,
                ),
            ]
        )
        await session.commit()

    return {"tenant_a": tenant_a_id, "tenant_b": tenant_b_id}


@pytest_asyncio.fixture
async def client_factory(
    db_connection: AsyncConnection,
    rate_limit_pool,
) -> AsyncIterator[ClientFactory]:
    from app.api.dependencies.tenant import get_current_user
    from app.core.auth import get_current_tenant
    from app.core.dependencies import get_tenant_db
    from app.main import app

    async def tenant_from_header(
        x_test_tenant: UUID = Header(alias=TENANT_HEADER),
    ) -> UUID:
        return x_test_tenant

    async def user_from_header(
        x_test_tenant: UUID = Header(alias=TENANT_HEADER),
    ) -> AuthContext:
        return AuthContext(user_id=x_test_tenant, company_id=x_test_tenant)

    async def test_database_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=db_connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            yield session

    app.dependency_overrides[get_current_tenant] = tenant_from_header
    app.dependency_overrides[get_current_user] = user_from_header
    app.dependency_overrides[get_tenant_db] = test_database_session
    previous_redis_pool = app.state.redis_pool
    app.state.redis_pool = rate_limit_pool
    clients: list[httpx.AsyncClient] = []

    def make(tenant_id: UUID) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={TENANT_HEADER: str(tenant_id)},
        )
        clients.append(client)
        return client

    try:
        yield make
    finally:
        for client in clients:
            await client.aclose()
        app.dependency_overrides.pop(get_current_tenant, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_tenant_db, None)
        app.state.redis_pool = previous_redis_pool


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reviews_list_is_isolated_by_tenant(
    client_factory: ClientFactory,
    review_tenants: dict[str, UUID],
) -> None:
    tenant_a_client = client_factory(review_tenants["tenant_a"])
    tenant_b_client = client_factory(review_tenants["tenant_b"])

    tenant_b_response = await tenant_b_client.get("/api/v1/reviews")
    tenant_a_response = await tenant_a_client.get("/api/v1/reviews")

    assert tenant_b_response.status_code == 200
    assert tenant_b_response.json()["data"]["items"] == []
    assert tenant_b_response.json()["data"]["total"] == 0

    assert tenant_a_response.status_code == 200
    tenant_a_data = tenant_a_response.json()["data"]
    assert tenant_a_data["total"] == 3
    assert len(tenant_a_data["items"]) == 3
    assert {item["sentiment"] for item in tenant_a_data["items"]} == {
        "POSITIVE",
        "NEGATIVE",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reviews_list_rejects_another_company_id(
    client_factory: ClientFactory,
    review_tenants: dict[str, UUID],
) -> None:
    tenant_a_client = client_factory(review_tenants["tenant_a"])

    response = await tenant_a_client.get(
        "/api/v1/reviews",
        params={"company_id": str(review_tenants["tenant_b"])},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied to this tenant"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reviews_summary_is_isolated_by_tenant(
    client_factory: ClientFactory,
    review_tenants: dict[str, UUID],
) -> None:
    tenant_a_client = client_factory(review_tenants["tenant_a"])
    tenant_b_client = client_factory(review_tenants["tenant_b"])

    tenant_b_response = await tenant_b_client.get("/api/v1/reviews/summary")
    tenant_a_response = await tenant_a_client.get("/api/v1/reviews/summary")

    assert tenant_b_response.status_code == 200
    tenant_b_summary = tenant_b_response.json()["data"]
    assert tenant_b_summary["total_reviews"] == 0
    assert tenant_b_summary["average_rating"] is None
    assert tenant_b_summary["sentiment"] == {
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "unclassified": 0,
        "total": 0,
    }
    assert tenant_b_summary["critical_reviews"] == 0
    assert tenant_b_summary["ai_pending"] == 0
    assert len(tenant_b_summary["timeline"]) == 30

    assert tenant_a_response.status_code == 200
    tenant_a_summary = tenant_a_response.json()["data"]
    assert tenant_a_summary["total_reviews"] == 3
    assert tenant_a_summary["average_rating"] == 3.33
    assert tenant_a_summary["sentiment"] == {
        "positive": 2,
        "neutral": 0,
        "negative": 1,
        "unclassified": 0,
        "total": 3,
    }
    assert tenant_a_summary["critical_reviews"] == 1
    assert sum(point["reviews"] for point in tenant_a_summary["timeline"]) == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reputation_statistics_match_frontend_contract(
    client_factory: ClientFactory,
    review_tenants: dict[str, UUID],
) -> None:
    tenant_a_client = client_factory(review_tenants["tenant_a"])
    tenant_b_client = client_factory(review_tenants["tenant_b"])

    tenant_a_response = await tenant_a_client.get(
        "/api/v1/reputation/statistics", params={"period_days": 30}
    )
    tenant_b_response = await tenant_b_client.get(
        "/api/v1/reputation/statistics", params={"period_days": 30}
    )

    assert tenant_a_response.status_code == 200
    tenant_a_stats = tenant_a_response.json()
    assert tenant_a_stats["period_days"] == 30
    assert tenant_a_stats["updated_at"]
    assert tenant_a_stats["platforms"] == [
        {
            "platform": "google",
            "average_rating": 3.33,
            "rating_delta": None,
            "total_reviews": 3,
            "new_reviews": 3,
        }
    ]
    assert tenant_b_response.status_code == 200
    assert tenant_b_response.json()["platforms"] == []
