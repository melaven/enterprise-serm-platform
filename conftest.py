"""pytest configuration for root-level test discovery."""

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

# Ensure project root is in sys.path for imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# These legacy scripts require a live API or modules that are no longer part of
# the application; they were moved into tests/ but are not runnable pytest tests.
collect_ignore = [
    "tests/test_auth_endpoints.py",
    "tests/test_dashboard_api.py",
    "tests/test_economics_service.py",
    "tests/test_protected_endpoints.py",
    "tests/test_schemas.py",
    "tests/test_scraping.py",
    "tests/test_telegram_alerts.py",
]


class _FakeRateLimitPipeline:
    def __init__(self, pool: "_FakeRateLimitPool") -> None:
        self.pool = pool
        self.commands: list[tuple[str, str, int | None]] = []

    def incr(self, key: str) -> "_FakeRateLimitPipeline":
        self.commands.append(("incr", key, None))
        return self

    def expire(self, key: str, seconds: int) -> "_FakeRateLimitPipeline":
        self.commands.append(("expire", key, seconds))
        return self

    async def execute(self) -> list[int | bool]:
        results: list[int | bool] = []
        for operation, key, seconds in self.commands:
            if operation == "incr":
                self.pool.values[key] = self.pool.values.get(key, 0) + 1
                results.append(self.pool.values[key])
            else:
                self.pool.expirations[key] = seconds or 0
                results.append(True)
        return results


class _FakeRateLimitPool:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    def pipeline(self, transaction: bool = True) -> _FakeRateLimitPipeline:
        assert transaction
        return _FakeRateLimitPipeline(self)


@pytest.fixture
def rate_limit_pool() -> _FakeRateLimitPool:
    return _FakeRateLimitPool()


@pytest.fixture
def company_id() -> UUID:
    return uuid4()


@pytest.fixture
def other_company_id() -> UUID:
    return uuid4()


@pytest_asyncio.fixture
async def review_assistant_connection(
    company_id: UUID, other_company_id: UUID
) -> AsyncIterator[AsyncConnection]:
    from app.core.database import Base
    from app.models.economics import Company, Platform

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as schema_connection:
            await schema_connection.run_sync(Base.metadata.create_all)

        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                ) as session:
                    for tenant_id in (company_id, other_company_id):
                        session.add(
                            Company(
                                id=tenant_id,
                                name="Test tenant",
                                average_check=0,
                                margin_percent=0,
                                cac=0,
                                base_ltv=0,
                            )
                        )
                        session.add(
                            Platform(
                                id=tenant_id,
                                company_id=tenant_id,
                                name=f"platform-{tenant_id}",
                            )
                        )
                    await session.commit()

                yield connection
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    review_assistant_connection: AsyncConnection,
) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(
        bind=review_assistant_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    ) as session:
        yield session


@pytest_asyncio.fixture
async def client(
    company_id: UUID,
    review_assistant_connection: AsyncConnection,
    rate_limit_pool: _FakeRateLimitPool,
) -> AsyncIterator[httpx.AsyncClient]:
    from app.core.auth import get_current_tenant
    from app.core.dependencies import get_tenant_db
    from app.main import app

    async def tenant_from_header(
        x_test_tenant: UUID = Header(alias="X-Test-Tenant"),
    ) -> UUID:
        return x_test_tenant

    async def test_database_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=review_assistant_connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    previous_tenant = app.dependency_overrides.get(get_current_tenant)
    previous_database = app.dependency_overrides.get(get_tenant_db)
    previous_redis_pool = app.state.redis_pool
    app.dependency_overrides[get_current_tenant] = tenant_from_header
    app.dependency_overrides[get_tenant_db] = test_database_session
    app.state.redis_pool = rate_limit_pool

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Test-Tenant": str(company_id)},
        ) as test_client:
            yield test_client
    finally:
        if previous_tenant is None:
            app.dependency_overrides.pop(get_current_tenant, None)
        else:
            app.dependency_overrides[get_current_tenant] = previous_tenant
        if previous_database is None:
            app.dependency_overrides.pop(get_tenant_db, None)
        else:
            app.dependency_overrides[get_tenant_db] = previous_database
        app.state.redis_pool = previous_redis_pool
