"""Общие фикстуры.

БД-тесты идут в изолированной тестовой базе (TEST_DATABASE_URL, имя должно
заканчиваться на `_test`). Схема создаётся один раз за сессию из ORM-метаданных,
затем применяется sql/001_multitenancy_rls.sql, то есть тесты гоняют ту же
RLS-политику, что и прод. Каждый тест выполняется во внешней транзакции,
которая откатывается в конце.

Чистые unit-тесты (services) БД не трогают: фикстуры ленивые, соединение
открывается только у тестов, которые их запрашивают.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import make_url, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

# app.db.session создаёт engine при импорте и читает Settings: задаём заглушки
# ДО первого импорта app.* (сами импорты ниже сделаны лениво, внутри фикстур).
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://app_tenant:test@localhost:5432/tenable_test"
)
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/tenable_test",
)
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"

# Тестовая авторизация передаётся заголовками, поэтому в одном тесте можно
# держать клиентов разных компаний одновременно.
HDR_COMPANY = "X-Test-Company-Id"
HDR_USER = "X-Test-User-Id"
HDR_ROLE = "X-Test-Role"

_STUB_AUTH_SQL = """
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY);
"""
_SET_TENANT = text(
    "SELECT set_config('app.company_id', :company_id, true), "
    "set_config('app.user_id', :user_id, true)"
)

ClientFactory = Callable[..., httpx.AsyncClient]
TenantDb = Callable[..., AbstractAsyncContextManager[AsyncSession]]


# --------------------------------------------------------------------------- #
# База данных
# --------------------------------------------------------------------------- #
async def _run_script(conn: AsyncConnection, script: str) -> None:
    """Многостатейный SQL-скрипт через simple-протокол asyncpg."""
    raw = await conn.get_raw_connection()
    await raw.driver_connection.execute(script)  # type: ignore[union-attr]


async def _prepare_schema() -> None:
    import app.models  # noqa: F401  (регистрирует все модели в Base.metadata)
    from app.db.base import Base  # ← Declarative Base проекта

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            for schema in ("public", "app", "auth"):
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.commit()

            await _run_script(conn, _STUB_AUTH_SQL)  # заглушка Supabase auth.users
            await conn.run_sync(Base.metadata.create_all)
            await conn.commit()

            await _run_script(conn, (SQL_DIR / "001_multitenancy_rls.sql").read_text())
            # SET ROLE app_tenant из теста
            await conn.execute(text("GRANT app_tenant TO CURRENT_USER"))
            await conn.commit()
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def database_schema() -> Iterator[None]:
    database = make_url(TEST_DATABASE_URL).database or ""
    if not database.endswith("_test"):
        # Схема public дропается, поэтому чужую БД не трогаем.
        pytest.exit(
            f"TEST_DATABASE_URL must point to a *_test database, got {database!r}",
            returncode=2,
        )
    try:
        asyncio.run(_prepare_schema())
    except (OSError, SQLAlchemyError) as exc:
        if os.environ.get("CI"):
            raise  # в CI недоступная БД это падение, а не skip
        pytest.skip(f"PostgreSQL is not available at TEST_DATABASE_URL: {exc}")
    yield


@pytest_asyncio.fixture
async def db_connection(database_schema: None) -> AsyncIterator[AsyncConnection]:
    """Одно соединение на тест + внешняя транзакция с откатом в конце."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                yield conn
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """Привилегированная сессия (владелец, RLS обходится): seed и проверки в БД.

    commit() здесь освобождает savepoint, а не транзакцию: откат остаётся за тестом.
    """
    async with AsyncSession(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    ) as session:
        yield session


@asynccontextmanager
async def _tenant_session(
    conn: AsyncConnection, company_id: UUID, user_id: UUID
) -> AsyncIterator[AsyncSession]:
    """Зеркало app.db.session.get_tenant_session: роль app_tenant + GUC контекста."""
    session = AsyncSession(
        bind=conn,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        await session.execute(text("SET LOCAL ROLE app_tenant"))
        await session.execute(
            _SET_TENANT, {"company_id": str(company_id), "user_id": str(user_id)}
        )
        yield session
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    finally:
        await session.close()
        await conn.exec_driver_sql("RESET ROLE")


@pytest.fixture
def tenant_db(db_connection: AsyncConnection) -> TenantDb:
    """Сессия под RLS для тестов репозиториев без HTTP.

    async with tenant_db(company_id) as session:
        rows = await ReviewRepository(session).get_many(limit=10, offset=0)
    """

    def make(
        company_id: UUID, user_id: UUID | None = None
    ) -> AbstractAsyncContextManager[AsyncSession]:
        return _tenant_session(db_connection, company_id, user_id or uuid4())

    return make


# --------------------------------------------------------------------------- #
# Идентичности
# --------------------------------------------------------------------------- #
@pytest.fixture
def company_id() -> UUID:
    return uuid4()


@pytest.fixture
def other_company_id() -> UUID:
    return uuid4()


@pytest.fixture
def user_id() -> UUID:
    return uuid4()


# --------------------------------------------------------------------------- #
# FastAPI + HTTP-клиент
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def app(db_connection: AsyncConnection) -> AsyncIterator[FastAPI]:
    """Приложение с подменёнными auth и tenant-сессией."""
    from app.core.security import AuthContext, get_auth_context
    from app.db.session import get_tenant_session
    from app.main import app as fastapi_app  # ← точка входа приложения

    async def fake_auth(request: Request) -> AuthContext:
        """Вместо проверки Supabase JWT: AuthContext из тестовых заголовков."""
        company = request.headers.get(HDR_COMPANY)
        if company is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthContext(
            user_id=UUID(request.headers.get(HDR_USER) or str(uuid4())),
            company_id=UUID(company),
            role=request.headers.get(HDR_ROLE, "member"),
        )

    async def tenant_session(
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AsyncIterator[AsyncSession]:
        async with _tenant_session(db_connection, auth.company_id, auth.user_id) as s:
            yield s

    fastapi_app.dependency_overrides[get_auth_context] = fake_auth
    fastapi_app.dependency_overrides[get_tenant_session] = tenant_session
    try:
        yield fastapi_app
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_factory(app: FastAPI) -> AsyncIterator[ClientFactory]:
    """Фабрика httpx.AsyncClient. Без company_id клиент анонимный (-> 401)."""
    created: list[httpx.AsyncClient] = []

    def make(
        company_id: UUID | None = None,
        *,
        user_id: UUID | None = None,
        role: str = "member",
    ) -> httpx.AsyncClient:
        headers: dict[str, str] = {}
        if company_id is not None:
            headers[HDR_COMPANY] = str(company_id)
            headers[HDR_USER] = str(user_id or uuid4())
            headers[HDR_ROLE] = role
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers=headers,
        )
        created.append(client)
        return client

    yield make
    for client in created:
        await client.aclose()


@pytest.fixture
def client(
    client_factory: ClientFactory, company_id: UUID, user_id: UUID
) -> httpx.AsyncClient:
    """Клиент, авторизованный как `company_id`."""
    return client_factory(company_id, user_id=user_id)


@pytest.fixture
def anon_client(client_factory: ClientFactory) -> httpx.AsyncClient:
    """Клиент без авторизации."""
    return client_factory()
