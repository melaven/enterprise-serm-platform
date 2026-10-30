"""Tenant-сессия вне HTTP-запроса (ARQ-воркер, скрипты, cron).

В воркере нет JWT и get_auth_context: company_id приходит аргументом задачи, а
доверие к нему обеспечивает API (он ставит задачу уже после проверки токена) и
закрытый Redis. Дальше всё как в запросе: одна транзакция, set_config(..., true)
первым statement, остальные запросы идут под RLS.
"""

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

SET_TENANT = text(
    "SELECT set_config('app.company_id', :company_id, true), "
    "set_config('app.user_id', :user_id, true)"
)


def build_engine(url: str, *, pool_size: int = 5) -> AsyncEngine:
    # Supavisor в transaction-режиме: без серверных prepared statements.
    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        },
    )


@asynccontextmanager
async def tenant_session(
    factory: async_sessionmaker[AsyncSession],
    company_id: UUID,
    user_id: UUID | None = None,
) -> AsyncIterator[AsyncSession]:
    """Транзакция под RLS компании `company_id`; коммит при выходе без ошибки.

    Внутри блока не вызывай session.commit(): set_config(..., true) живёт до
    конца транзакции, и следующая транзакция пойдёт без контекста (0 строк /
    ошибка WITH CHECK). Используй flush().
    """
    async with factory() as session, session.begin():
        await session.execute(
            SET_TENANT,
            {
                "company_id": str(company_id),
                # '' -> NULLIF в app.current_user_id() даёт NULL (системное действие)
                "user_id": str(user_id) if user_id else "",
            },
        )
        yield session
