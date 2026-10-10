"""Пример подключения DLQ к WorkerSettings (перенеси в свой worker.py)."""

from typing import Any
from uuid import UUID

from supabase import acreate_client  # pip install supabase

from app.db.dlq_repository import SupabaseDLQStore, set_default_dlq_store
from app.worker.hooks import dlq_protected

MAX_TRIES = 5


# Порядок декораторов: dlq_protected снаружи, traced_task внутри.
@dlq_protected()
async def fetch_reviews_task(
    ctx: dict[str, Any], company_id: UUID, platform: str, url: str
) -> int:
    ...  # твоя логика; для временных сбоев: raise arq.Retry(defer=30)
    return 0


async def startup(ctx: dict[str, Any]) -> None:
    # ... твои проверки RLS-роли и configure_logging() остаются здесь
    client = await acreate_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    store = SupabaseDLQStore(client)
    ctx["dlq_store"] = store
    ctx["max_tries"] = MAX_TRIES  # читает dlq_protected
    set_default_dlq_store(store)


class WorkerSettings:
    functions = [fetch_reviews_task]
    on_startup = startup
    max_tries = MAX_TRIES  # то же число, что в ctx["max_tries"]
    # on_job_end сюда НЕ подключается: у хуков ARQ другая сигнатура (см. hooks.py)


SUPABASE_URL = "https://<ref>.supabase.co"  # из settings
SUPABASE_SERVICE_ROLE_KEY = "<service-role-key>"  # из settings/секретов, не в git
