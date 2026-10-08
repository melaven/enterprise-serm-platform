from datetime import datetime
import os
from pathlib import Path
from typing import AsyncGenerator
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    create_async_engine, 
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

# Load only the repository-root .env; keep process environment variables authoritative.
load_dotenv(
    dotenv_path=Path(__file__).resolve().parents[1] / ".env",
    override=False,
)

# Основная DATABASE_URL (для postgres роли - миграции)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("CRITICAL: DATABASE_URL variable is missing in .env file.")

# Tenant DATABASE_URL (для app_tenant роли - runtime)
TENANT_DATABASE_URL = os.getenv("TENANT_DATABASE_URL", DATABASE_URL)

# Определяем какую URL использовать для runtime
# По умолчанию используем tenant URL, если не указано иное
USE_TENANT_ROLE = os.getenv("USE_TENANT_ROLE", "true").lower() == "true"
runtime_database_url = TENANT_DATABASE_URL if USE_TENANT_ROLE else DATABASE_URL

database_url = make_url(runtime_database_url)
if database_url.drivername in {"postgres", "postgresql"}:
    database_url = database_url.set(drivername="postgresql+asyncpg")
elif database_url.drivername != "postgresql+asyncpg":
    raise RuntimeError(
        "DATABASE_URL must use PostgreSQL with the asyncpg driver."
    )

# Supabase transaction poolers can reuse PostgreSQL connections across clients.
engine = create_async_engine(
    database_url,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    },
)

# Асинхронная фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
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
        except Exception as error:
            await session.rollback()
            raise error
