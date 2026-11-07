"""Adapters for redis-py's sync/async union return annotations."""

from collections.abc import Awaitable
from inspect import isawaitable
from typing import cast


async def await_redis_eval(result: object) -> object:
    if not isawaitable(result):
        raise TypeError("Redis eval must return an awaitable")
    return await cast(Awaitable[object], result)
