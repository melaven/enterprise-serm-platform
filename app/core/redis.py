import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from arq.connections import ArqRedis, RedisSettings, create_pool
from fastapi import Depends, FastAPI, Request

from app.core.config import get_settings


def get_redis_settings() -> RedisSettings:
    redis_url = os.getenv("REDIS_URL")
    if redis_url is None:
        redis_url = get_settings().redis_url
    if redis_url == "dummy://skip":
        return RedisSettings(host="127.0.0.1", port=6379)

    settings = RedisSettings.from_dsn(redis_url)
    if settings.host == "localhost":
        settings.host = "127.0.0.1"
    return settings


@asynccontextmanager
async def arq_lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = await create_pool(get_redis_settings())
    app.state.redis_pool = pool
    app.state.arq_pool = pool
    try:
        yield
    finally:
        await pool.aclose()


def get_redis_pool(request: Request) -> ArqRedis:
    pool: ArqRedis = request.app.state.redis_pool
    return pool


RedisPool = Annotated[ArqRedis, Depends(get_redis_pool)]
get_arq_pool = get_redis_pool
ArqPool = RedisPool
