"""Сохранение «мёртвых» задач в Supabase (таблица dead_letter_queue)."""

from typing import Any, Protocol

import structlog

from ..schemas.dlq import DLQRecord

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DLQ_TABLE = "dead_letter_queue"


class DLQStore(Protocol):
    """Абстракция хранилища: реализуй своё или используй SupabaseDLQStore."""

    async def insert(self, record: DLQRecord) -> None: ...


class SupabaseDLQStore:
    """Запись через async-клиент supabase-py (`acreate_client`).

    Нужен service_role ключ: таблица закрыта RLS без политик (см. SQL),
    anon/authenticated доступа к ней не имеют. Ключ держи только в воркере.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    async def insert(self, record: DLQRecord) -> None:
        # upsert + ignore_duplicates: повторная доставка той же job не плодит дубли
        # (job_id уникален).
        await (
            self._client.table(DLQ_TABLE)
            .upsert(
                record.model_dump(mode="json"),
                on_conflict="job_id",
                ignore_duplicates=True,
            )
            .execute()
        )


class InMemoryDLQStore:
    """Мок для тестов и локальной разработки без Supabase."""

    def __init__(self) -> None:
        self.records: dict[str, DLQRecord] = {}

    async def insert(self, record: DLQRecord) -> None:
        self.records.setdefault(record.job_id, record)


_default_store: DLQStore | None = None


def set_default_dlq_store(store: DLQStore | None) -> None:
    global _default_store
    _default_store = store


async def save_to_dlq(record: DLQRecord, *, store: DLQStore | None = None) -> None:
    """Сохраняет запись в DLQ. Исключения хранилища НЕ глушатся (решает вызывающий)."""
    target = store or _default_store
    if target is None:
        raise RuntimeError("DLQ store is not configured: call set_default_dlq_store()")
    await target.insert(record)
    logger.info("dlq_record_saved", job_id=record.job_id, job_name=record.job_name)