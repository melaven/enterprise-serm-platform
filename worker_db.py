"""Engine воркера и транзакция под RLS арендатора (тот же контракт, что в API)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_SET_CLAIMS = text("SELECT set_config('request.jwt.claims', :claims, true)")


def create_worker_engine(database_url: str, *, pool_size: int) -> AsyncEngine:
    return create_async_engine(
        database_url,  # роль app_tenant (NOBYPASSRLS)
        pool_size=pool_size,
        pool_pre_ping=True,
        connect_args={
            # Supavisor в transaction-режиме: без серверных prepared statements
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        },
    )


async def assert_rls_applies(engine: AsyncEngine) -> None:
    """Падаем на старте, если роль обходит RLS: иначе изоляция арендаторов мнимая."""
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT current_user, rolsuper, rolbypassrls "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            )
        ).one_or_none()
    if row is None or row[1] or row[2]:
        raise RuntimeError(
            "Worker DB role bypasses RLS: use app_tenant in DATABASE_URL"
        )


@asynccontextmanager
async def tenant_transaction(
    factory: async_sessionmaker[AsyncSession], tenant_id: UUID
) -> AsyncIterator[AsyncSession]:
    """Одна транзакция под RLS арендатора. Контекст set_config(..., true) живёт до конца
    транзакции, поэтому внутри блока нельзя вызывать session.commit()."""
    async with factory() as session, session.begin():
        claims = json.dumps({"tenant_id": str(tenant_id)}, separators=(",", ":"))
        await session.execute(_SET_CLAIMS, {"claims": claims})
        yield session
