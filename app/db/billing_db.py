"""Отдельное подключение вебхука под ролью billing_service (не app_tenant, без tenant-контекста).

Роль может только вызывать app.billing_* (SECURITY DEFINER). Даже при компрометации обработчика
через неё нельзя читать отзывы или менять чужие данные напрямую.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


class BillingNotConfigured(RuntimeError):
    pass


@lru_cache
def _factory() -> async_sessionmaker[AsyncSession]:
    url = get_settings().billing_database_url
    if not url:
        raise BillingNotConfigured("BILLING_DATABASE_URL is not set")
    engine = create_async_engine(
        url,
        pool_size=3,
        max_overflow=0,
        pool_timeout=5,
        pool_pre_ping=True,
        pool_recycle=1_800,
        connect_args={
            "statement_cache_size": 0,  # Supavisor transaction mode
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
            "server_settings": {"statement_timeout": "10000"},
        },
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def billing_session() -> AsyncIterator[AsyncSession]:
    """Одна транзакция: запись event_id + применение события коммитятся атомарно."""
    async with _factory()() as session, session.begin():
        yield session


class SqlGateway:
    """Реализация Gateway (см. stripe_events.py) поверх SQL-функций 013."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record_event(self, event_id: str, event_type: str) -> bool:
        r = await self._s.execute(
            text("SELECT app.billing_record_event(:i, :t)"), {"i": event_id, "t": event_type}
        )
        return bool(r.scalar_one())

    async def activate_pro(self, tenant_id: UUID, customer: str, subscription: str) -> None:
        await self._s.execute(
            text("SELECT app.billing_activate_pro(CAST(:t AS uuid), :c, :s)"),
            {"t": str(tenant_id), "c": customer, "s": subscription},
        )

    async def period_paid(
        self,
        subscription: str,
        start: datetime | None,
        end: datetime | None,
        reset_usage: bool,
    ) -> bool:
        r = await self._s.execute(
            text(
                "SELECT app.billing_period_paid(:s, CAST(:a AS timestamptz), "
                "CAST(:b AS timestamptz), :r)"
            ),
            {"s": subscription, "a": start, "b": end, "r": reset_usage},
        )
        return bool(r.scalar_one())

    async def cancel(self, subscription: str) -> bool:
        r = await self._s.execute(text("SELECT app.billing_cancel(:s)"), {"s": subscription})
        return bool(r.scalar_one())
