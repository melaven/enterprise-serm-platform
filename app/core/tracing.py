"""Сквозной correlation_id через ARQ: постановка задачи и восстановление в воркере.

Заменяет вариант из arq_tracing_example.py: теперь декоратор принимает имя задачи
`@traced_task("fetch_reviews")` (голое `@traced_task` больше не поддерживается).
"""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

import structlog
from arq.connections import ArqRedis
from arq.jobs import Job

from .logger import (
    CORRELATION_ID_KEY,
    get_correlation_id,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

T = TypeVar("T")

logger: structlog.stdlib.BoundLogger = structlog.get_logger("app.worker")


async def enqueue_traced(
    pool: ArqRedis, function: str, *args: Any, **kwargs: Any
) -> Job | None:
    """pool.enqueue_job + текущий correlation_id (kwarg `correlation_id`)."""
    correlation_id = get_correlation_id()
    if correlation_id is not None:
        kwargs[CORRELATION_ID_KEY] = correlation_id
    return await pool.enqueue_job(function, *args, **kwargs)


def traced_task(
    name: str,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Биндит correlation_id из job в контекст логгера на время задачи."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> T:
            correlation_id = (
                kwargs.pop(CORRELATION_ID_KEY, None) or new_correlation_id()
            )
            token = set_correlation_id(str(correlation_id))
            job_id = ctx.get("job_id")
            try:
                logger.info("job_started", task=name, job_id=job_id)
                result = await func(ctx, *args, **kwargs)
                logger.info("job_finished", task=name, job_id=job_id)
                return result
            except Exception as exc:
                # Retry — штатный сигнал повтора, не ошибка
                level = (
                    logger.info if type(exc).__name__ == "Retry" else logger.exception
                )
                level("job_interrupted", task=name, job_id=job_id)
                raise
            finally:
                reset_correlation_id(token)

        return wrapper

    return decorator