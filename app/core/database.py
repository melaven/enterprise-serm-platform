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

from app.core.tenant_session import track_session_writes

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


def _is_explicit_test_or_migration_context() -> bool:
    environment = os.getenv("ENVIRONMENT", "").lower()
    migration_mode = os.getenv("SERM_MIGRATION_MODE", "").lower() == "true"
    return environment in {"test", "testing", "migration", "migrate"} or migration_mode


def _runtime_database_url(
    tenant_dsn: str | None,
    admin_dsn: str,
    *,
    use_tenant_role: bool,
    allow_admin_runtime: bool,
) -> URL:
    if not tenant_dsn:
        raise RuntimeError("TENANT_DATABASE_URL must be configured explicitly.")

    tenant_url = _postgresql_url(tenant_dsn, "TENANT_DATABASE_URL")
    if tenant_url.username is None or tenant_url.username.lower() in {
        "postgres",
        "service_role",
    }:
        raise RuntimeError(
            "TENANT_DATABASE_URL must use a non-privileged runtime database role."
        )

    if not use_tenant_role:
        if not allow_admin_runtime:
            raise RuntimeError(
                "USE_TENANT_ROLE must be true outside explicit test or migration "
                "contexts."
            )
        return _postgresql_url(admin_dsn, "DATABASE_URL")

    return tenant_url


# Основная DATABASE_URL (для postgres роли - миграции)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("CRITICAL: DATABASE_URL is missing from the root .env file.")
_postgresql_url(DATABASE_URL, "DATABASE_URL")

# Runtime всегда требует явно заданный tenant DSN. Админский DSN разрешён
# только в явно обозначенном тестовом или миграционном контексте.
TENANT_DATABASE_URL = os.getenv("TENANT_DATABASE_URL")
USE_TENANT_ROLE = os.getenv("USE_TENANT_ROLE", "true").lower() == "true"
database_url = _runtime_database_url(
    TENANT_DATABASE_URL,
    DATABASE_URL,
    use_tenant_role=USE_TENANT_ROLE,
    allow_admin_runtime=_is_explicit_test_or_migration_context(),
)

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
            track_session_writes(session)
            yield session
            if (
                session.new
                or session.dirty
                or session.deleted
                or session.sync_session.info.get("has_writes")
            ):
                await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                logger.exception("Database rollback after request failure also failed")
            raise
