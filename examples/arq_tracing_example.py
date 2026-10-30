"""Шпаргалка: сквозной correlation_id  FastAPI -> Redis -> ARQ worker.

Схема
-----
1. CorrelationIdMiddleware кладёт ID в ContextVar запроса.
2. Роутер ставит задачу через `enqueue_traced`: ID едет в Redis вместе с job
   (как служебный kwarg `correlation_id`).
3. Декоратор `traced_task` в воркере вынимает kwarg, биндит ID в ContextVar
   на время задачи. Все логи задачи получают тот же correlation_id,
   что и логи HTTP-запроса. Сигнатура самой задачи НЕ меняется.

Почему не просто contextvars: ContextVar живёт внутри одного процесса/задачи
asyncio, через Redis он сам не передаётся. Его нужно явно сериализовать
в job и восстановить в воркере.

Эти хелперы (`enqueue_traced`, `traced_task`) можно вынести в app/core/tracing.py.
"""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar
from uuid import UUID

import structlog
from arq.connections import ArqRedis
from arq.jobs import Job

from app.core.logger import (
    CORRELATION_ID_KEY,
    configure_logging,
    get_correlation_id,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

T = TypeVar("T")

log: structlog.stdlib.BoundLogger = structlog.get_logger("app.worker")


# --------------------------------------------------------------------------- #
# Сторона API: постановка задачи
# --------------------------------------------------------------------------- #
async def enqueue_traced(
    pool: ArqRedis, function: str, *args: Any, **kwargs: Any
) -> Job | None:
    """Как pool.enqueue_job, но добавляет текущий correlation_id в job."""
    correlation_id = get_correlation_id()
    if correlation_id is not None:
        kwargs[CORRELATION_ID_KEY] = correlation_id
    return await pool.enqueue_job(function, *args, **kwargs)


# --------------------------------------------------------------------------- #
# Сторона воркера: восстановление контекста
# --------------------------------------------------------------------------- #
def traced_task(
    func: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]:
    """Декоратор ARQ-задачи: биндит correlation_id из job в контекст логгера.

    Если ID не пришёл (cron, постановка вне HTTP), генерируем новый: логи задачи
    всё равно склеиваются между собой.
    """

    @wraps(func)  # arq берёт имя задачи из __name__
    async def wrapper(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> T:
        correlation_id = kwargs.pop(CORRELATION_ID_KEY, None) or new_correlation_id()
        token = set_correlation_id(str(correlation_id))
        try:
            log.info("job_started", task=func.__name__, job_id=ctx.get("job_id"))
            result = await func(ctx, *args, **kwargs)
            log.info("job_finished", task=func.__name__, job_id=ctx.get("job_id"))
            return result
        except Exception:
            log.exception("job_failed", task=func.__name__, job_id=ctx.get("job_id"))
            raise  # ARQ сам решает про retry; Retry тоже проходит здесь
        finally:
            reset_correlation_id(token)

    return wrapper


# --------------------------------------------------------------------------- #
# Пример использования
# --------------------------------------------------------------------------- #
# --- app/worker/tasks.py ------------------------------------------------------
@traced_task
async def fetch_reviews_task(
    ctx: dict[str, Any], company_id: UUID, platform: str, url: str
) -> int:
    log.info("fetching", platform=platform, url=url)  # correlation_id добавится сам
    return 0


# --- app/worker/worker.py -----------------------------------------------------
async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()  # ОБЯЗАТЕЛЬНО и в воркере: это отдельный процесс
    # ... твои проверки RLS-роли и остальное из startup


class WorkerSettings:
    functions = [fetch_reviews_task]
    on_startup = startup


# --- app/main.py --------------------------------------------------------------
#   from app.core.logger import configure_logging
#   from app.core.middleware import CorrelationIdMiddleware
#
#   configure_logging()
#   app = FastAPI()
#   app.add_middleware(CorrelationIdMiddleware)
#
# --- app/routers/parser.py ----------------------------------------------------
#   job = await enqueue_traced(arq, "fetch_reviews_task", company_id, platform, url)
#   # вместо: await arq.enqueue_job("fetch_reviews_task", company_id, platform, url)
#
# Итог в логах:
#   {"event": "request_finished", "correlation_id": "9f1c...", ...}
#   {"event": "job_started", "correlation_id": "9f1c...", "task": "fetch_reviews_task"}
#   {"event": "fetching", "correlation_id": "9f1c...", ...}
#
# Поиск по всей цепочке:  jq 'select(.correlation_id=="9f1c...")'
