"""Отдельное подключение под ролью apikey_service: резолв ключа ДО появления tenant-контекста.

Роль умеет только app.resolve_api_key(hash). Пул маленький: БД трогаем лишь при промахе кэша Redis.
"""

from functools import lru_cache
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.engine_args import asyncpg_connect_args


class ApiKeysNotConfigured(RuntimeError):
    pass


@lru_cache
def _factory() -> async_sessionmaker[AsyncSession]:
    url = get_settings().apikey_database_url
    if not url:
        raise ApiKeysNotConfigured("APIKEY_DATABASE_URL is not set")
    engine = create_async_engine(
        url,
        pool_size=3,
        max_overflow=0,
        pool_timeout=5,
        pool_pre_ping=True,
        pool_recycle=get_settings().db_pool_recycle,
        connect_args=asyncpg_connect_args(),
    )
    return async_sessionmaker(engine, expire_on_commit=False)


async def resolve_api_key_in_db(key_hash: str) -> UUID | None:
    async with _factory()() as session, session.begin():
        value = (
            await session.execute(
                text("SELECT app.resolve_api_key(:h)"), {"h": key_hash}
            )
        ).scalar_one_or_none()
    return UUID(str(value)) if value is not None else None
