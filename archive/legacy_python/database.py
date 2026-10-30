"""Асинхронный движок SQLAlchemy и фабрика сессий (runtime приложения)."""

import os
from collections.abc import AsyncIterator
from typing import Final

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.url import get_database_url


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


DB_ECHO: Final[bool] = os.environ.get("DB_ECHO", "").lower() in {"1", "true", "yes"}

engine: AsyncEngine = create_async_engine(
    get_database_url("DATABASE_URL"),
    echo=DB_ECHO,
    pool_pre_ping=True,  # отбрасывает «мёртвые» соединения после рестарта БД
    pool_size=_int_env("DB_POOL_SIZE", 10),
    max_overflow=_int_env("DB_MAX_OVERFLOW", 5),
    pool_timeout=10,  # пул исчерпан: быстрый отказ вместо долгого ожидания
    pool_recycle=1800,
    connect_args={"timeout": 5, "command_timeout": 30},  # asyncpg: без вечных зависаний
)

# async_sessionmaker — асинхронный аналог sessionmaker в SQLAlchemy 2.0.
SessionFactory: Final[async_sessionmaker[AsyncSession]] = async_sessionmaker(
    engine,
    expire_on_commit=False,  # объекты остаются доступны после commit (нужно для ответа FastAPI)
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-зависимость: одна сессия на запрос; commit при успехе, rollback при исключении."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Вызывать в lifespan при остановке приложения."""
    await engine.dispose()
