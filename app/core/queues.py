"""ARQ queue names and the single task-to-queue routing registry."""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Final


class Queue(StrEnum):
    CRITICAL = "arq:queue:critical"  # человек ждёт ответа в UI: секунды
    BULK = "arq:queue:bulk"  # импорт и синхронизация тысяч записей: минуты, допустима задержка


# Стандартная очередь ARQ до разделения. Только для дренажа хвоста при выкате (LegacyWorkerSettings).
LEGACY_QUEUE: Final = "arq:queue"

TASK_CRITICAL_DRAFTS: Final = "generate_drafts_task"
TASK_PUBLISH_REPLY: Final = "publish_review_reply"
TASK_PROCESS_REVIEW: Final = "process_review_task"
TASK_PROCESS_INGESTION: Final = "process_review_ingestion"
TASK_SEND_WEEKLY_DIGEST: Final = "send_company_weekly_digest"

TASK_ROUTES: Final = MappingProxyType(
    {
        TASK_CRITICAL_DRAFTS: Queue.CRITICAL,
        TASK_PUBLISH_REPLY: Queue.CRITICAL,
        TASK_PROCESS_REVIEW: Queue.BULK,
        TASK_PROCESS_INGESTION: Queue.BULK,
        TASK_SEND_WEEKLY_DIGEST: Queue.BULK,
    }
)


class UnroutableTaskError(LookupError):
    """Задача не внесена в TASK_ROUTES. Молчаливого «default queue» нет: так критичная и тяжёлая работа не смешаются."""


class TaskRoutingError(ValueError):
    """Явно запрошенная очередь противоречит реестру (задача зарегистрирована в другом пуле воркеров)."""


def queue_for(function: str) -> Queue:
    try:
        return TASK_ROUTES[function]
    except KeyError:
        raise UnroutableTaskError(
            f"задача {function!r} не внесена в TASK_ROUTES (app/core/queues.py)"
        ) from None


def functions_for(queue: Queue) -> frozenset[str]:
    return frozenset(name for name, target in TASK_ROUTES.items() if target is queue)
