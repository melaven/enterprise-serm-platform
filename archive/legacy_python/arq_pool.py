from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Depends, FastAPI, Request

from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI(lifespan=lifespan): один пул ARQ на процесс API."""
    pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    app.state.arq_pool = pool
    try:
        yield
    finally:
        await pool.aclose()


def get_arq_pool(request: Request) -> ArqRedis:
    return request.app.state.arq_pool


ArqPool = Annotated[ArqRedis, Depends(get_arq_pool)]
