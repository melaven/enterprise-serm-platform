"""DLQ для ARQ: перехват окончательно упавших задач.

ВАЖНО про ARQ: его хуки `on_job_start` / `after_job_end` получают только `ctx`
(без имени задачи, args, kwargs и результата) и вызываются после КАЖДОЙ попытки,
включая ретраи. Поэтому сигнатура `on_job_end(ctx, job_name, args, kwargs, outcome)`
вызывается не самим ARQ, а декоратором `dlq_protected`, который оборачивает задачу
и зовёт её только когда попытки реально исчерпаны.

Что считается окончательным падением:
  * любое исключение, кроме arq.Retry: ARQ такую задачу не повторяет;
  * arq.Retry на последней попытке (job_try >= max_tries): ARQ помечает failed.
"""

import traceback as tb
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

import structlog
from arq.worker import Retry
from pydantic_core import to_jsonable_python

from app.db.dlq_repository import DLQStore, save_to_dlq
from app.schemas.dlq import DLQRecord, DLQStatus

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

T = TypeVar("T")

CORRELATION_ID_KEY = "correlation_id"
DEFAULT_MAX_TRIES = 5  # дефолт ARQ для WorkerSettings.max_tries
MAX_ERROR_CHARS = 2_000
MAX_TRACEBACK_CHARS = 20_000


def _jsonable(value: Any) -> Any:
    """Приводит args/kwargs к JSON (UUID, datetime, Decimal...); неизвестное -> repr."""
    return to_jsonable_python(value, fallback=repr)


async def on_job_end(
    ctx: dict[str, Any],
    job_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    outcome: Any,
) -> None:
    """Если outcome - исключение: пишет задачу в DLQ и логирует.

    Никогда не бросает исключений наружу: сбой самой DLQ не должен подменять
    исходную ошибку задачи (она пробрасывается декоратором).
    """
    if not isinstance(outcome, Exception):
        return

    correlation_id = str(kwargs.get(CORRELATION_ID_KEY) or "unknown")
    job_id = str(ctx.get("job_id") or "unknown")
    record = DLQRecord(
        job_id=job_id,
        job_name=job_name,
        correlation_id=correlation_id,
        args=list(_jsonable(list(args))),
        kwargs=dict(_jsonable(kwargs)),
        error_message=f"{type(outcome).__name__}: {outcome}"[:MAX_ERROR_CHARS],
        traceback="".join(tb.format_exception(outcome))[-MAX_TRACEBACK_CHARS:],
        status=DLQStatus.PENDING_REVIEW,
    )

    store: DLQStore | None = ctx.get("dlq_store")
    try:
        await save_to_dlq(record, store=store)
    except Exception:
        # Данные задачи остаются в логах: хотя бы там их можно найти.
        logger.error(
            "dlq_save_failed",
            job_id=job_id,
            job_name=job_name,
            correlation_id=correlation_id,
            exc_info=True,
        )
        return

    # correlation_id передаём явно: к этому моменту ContextVar уже может быть сброшен.
    logger.error(
        "job_moved_to_dlq",
        job_id=job_id,
        job_name=job_name,
        correlation_id=correlation_id,
        job_try=ctx.get("job_try"),
        error_type=type(outcome).__name__,
        error_message=record.error_message,
        status=record.status.value,
    )


def dlq_protected(
    *, max_tries: int | None = None
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Декоратор ARQ-задачи. Должен быть САМЫМ ВНЕШНИМ (выше @traced_task).

    max_tries: если у задачи свой лимит (`func(coro, max_tries=3)`), передай его
    сюда; иначе берётся ctx["max_tries"] (кладётся в on_startup) или 5.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)  # ARQ берёт имя задачи из __name__
        async def wrapper(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> T:
            try:
                return await func(ctx, *args, **kwargs)
            except Retry as exc:
                limit = max_tries or int(ctx.get("max_tries", DEFAULT_MAX_TRIES))
                if int(ctx.get("job_try", 1)) < limit:
                    raise  # попытки остались: пусть ARQ повторит
                await on_job_end(ctx, func.__name__, args, kwargs, exc)
                raise
            except Exception as exc:
                await on_job_end(ctx, func.__name__, args, kwargs, exc)
                raise

        return wrapper

    return decorator
