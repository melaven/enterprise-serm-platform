import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

# Local runs must use the checked-in configuration file rather than inherited
# shell variables. Test processes keep their isolated database configuration.
_is_testing = os.getenv("ENVIRONMENT", "").lower() in {"test", "testing"}
load_dotenv(
    dotenv_path=Path(__file__).resolve().parents[2] / ".env",
    override=not _is_testing,
)


def _postgresql_url(value: str, setting_name: str) -> URL:
    """Parse a PostgreSQL URL and reject unsupported database backends."""
    try:
        url = make_url(value)
    except ArgumentError as exc:
        raise RuntimeError(f"{setting_name} must be a valid PostgreSQL URL.") from exc

    if url.get_backend_name() != "postgresql":
        raise RuntimeError(
            f"{setting_name} must use PostgreSQL; SQLite and other databases "
            "are disabled."
        )

    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+asyncpg")
    if url.drivername == "postgresql+asyncpg":
        return url

    raise RuntimeError(f"{setting_name} must use the asyncpg PostgreSQL driver.")


# Основная DATABASE_URL (для postgres роли - миграции)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("CRITICAL: DATABASE_URL is missing from the root .env file.")
_postgresql_url(DATABASE_URL, "DATABASE_URL")

# Tenant DATABASE_URL (для app_tenant роли - runtime)
TENANT_DATABASE_URL = os.getenv("TENANT_DATABASE_URL", DATABASE_URL)
_postgresql_url(TENANT_DATABASE_URL, "TENANT_DATABASE_URL")

# Определяем какую URL использовать для runtime.
USE_TENANT_ROLE = os.getenv("USE_TENANT_ROLE", "true").lower() == "true"
runtime_database_url = TENANT_DATABASE_URL if USE_TENANT_ROLE else DATABASE_URL
database_url = _postgresql_url(runtime_database_url, "Runtime database URL")

# Pgbouncer/Supavisor compatibility: disable prepared statement cache
# to prevent "prepared statement already exists" errors in transaction pooling mode
connect_args = {
    "statement_cache_size": 0,
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
}

engine = create_async_engine(
    database_url,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    poolclass=NullPool,
    connect_args=connect_args,
)


@event.listens_for(engine.sync_engine, "handle_error")
def _log_database_error(exception_context) -> None:
    logger.exception(
        "Database operation failed (driver=%s, host=%s, port=%s): %s",
        database_url.drivername,
        database_url.host or "local",
        database_url.port if database_url.port is not None else "default",
        exception_context.original_exception,
    )


# Асинхронная фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

Base = declarative_base()


# Наш главный мост — Dependency Injection для FastAPI роутеров
# Используется только для health checks и не-tenant операций
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                logger.exception("Database rollback after request failure also failed")
            raise
