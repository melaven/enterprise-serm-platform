"""Сессия БД с передачей tenant-контекста в Postgres (для RLS)."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated
from uuid import uuid4

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.auth import get_jwt_payload
from app.schemas.auth import JWTPayload

# is_local = true: значение живёт до конца ТЕКУЩЕЙ транзакции и не протекает
# между запросами через пул/Supavisor.
_SET_CLAIMS = text("SELECT set_config('request.jwt.claims', :claims, true)")


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    from app.core.config import get_settings

    engine = create_async_engine(
        get_settings().database_url,  # роль app_tenant (NOBYPASSRLS), не postgres
        pool_pre_ping=True,
        connect_args={
            # Supavisor в transaction-режиме: без серверных prepared statements
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        },
    )
    return async_sessionmaker(engine, expire_on_commit=False)


def build_rls_claims(payload: JWTPayload) -> str:
    """JSON для request.jwt.claims. Собирается json.dumps, не конкатенацией,
    и уходит в БД bind-параметром: инъекция через claim невозможна."""
    return json.dumps(
        {"sub": str(payload.sub), "tenant_id": str(payload.tenant_id)},
        separators=(",", ":"),
    )


async def apply_rls_context(session: AsyncSession, payload: JWTPayload) -> None:
    """Должен быть ПЕРВЫМ запросом транзакции."""
    await session.execute(_SET_CLAIMS, {"claims": build_rls_claims(payload)})


@asynccontextmanager
async def tenant_session(
    factory: async_sessionmaker[AsyncSession], payload: JWTPayload
) -> AsyncIterator[AsyncSession]:
    """Одна транзакция под RLS арендатора; коммит при выходе без ошибки.

    Внутри блока не вызывай session.commit(): контекст set_config(..., true)
    умирает с транзакцией, и следующая пойдёт без tenant (0 строк / ошибка
    WITH CHECK). Используй session.flush().
    """
    async with factory() as session, session.begin():
        await apply_rls_context(session, payload)
        yield session


async def get_tenant_session(
    payload: Annotated[JWTPayload, Depends(get_jwt_payload)],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[AsyncSession]:
    """FastAPI-зависимость: сессия, в которой RLS уже знает tenant_id."""
    async with tenant_session(factory, payload) as session:
        yield session


TenantSession = Annotated[AsyncSession, Depends(get_tenant_session)]
