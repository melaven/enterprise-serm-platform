"""Route ARQ jobs through the task registry. Application code should use this module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.queues import Queue, TaskRoutingError, queue_for
from app.core.tracing import enqueue_traced

if TYPE_CHECKING:
    from arq.connections import ArqRedis
    from arq.jobs import Job


async def enqueue_routed(
    pool: ArqRedis,
    function: str,
    *args: Any,
    job_id: str | None = None,
    queue: Queue | None = None,
    **kwargs: Any,
) -> Job | None:
    """Enqueue a task in its registered queue, optionally validating an explicit queue."""
    if "_queue_name" in kwargs:
        raise TaskRoutingError("_queue_name is set by TASK_ROUTES, not by the caller")

    target = queue_for(function)
    if queue is not None and queue is not target:
        raise TaskRoutingError(
            f"{function!r} is registered for {target.name}, not {queue.name}"
        )

    kwargs["_queue_name"] = target.value
    if job_id is not None:
        kwargs["_job_id"] = job_id
    return await enqueue_traced(pool, function, *args, **kwargs)


async def enqueue_critical(
    pool: ArqRedis,
    function: str,
    *args: Any,
    job_id: str | None = None,
    **kwargs: Any,
) -> Job | None:
    """Enqueue a UI-critical task; reject task names registered to another queue."""
    return await enqueue_routed(
        pool, function, *args, job_id=job_id, queue=Queue.CRITICAL, **kwargs
    )


async def enqueue_bulk(
    pool: ArqRedis,
    function: str,
    *args: Any,
    job_id: str | None = None,
    **kwargs: Any,
) -> Job | None:
    """Enqueue a bulk task; reject task names registered to another queue."""
    return await enqueue_routed(
        pool, function, *args, job_id=job_id, queue=Queue.BULK, **kwargs
    )
