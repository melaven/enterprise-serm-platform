"""ARQ-воркер. Запуск: arq app.worker.worker.WorkerSettings"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import get_settings
from app.core.logger import configure_logging_from_env
from app.core.redis import get_redis_settings
from app.db.tenant import build_engine
from app.services.si_pipeline import build_insights_service
from app.worker.analysis_tasks import process_reviews_batch
from app.worker.tasks import fetch_reviews_task

MAX_JOBS = 10


async def _assert_rls_applies(engine: AsyncEngine) -> None:
    """Защита от неверного DATABASE_URL: под postgres/service_role RLS обходится,
    и задача «работала бы», нарушая изоляцию. Лучше упасть на старте."""
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT current_user, rolsuper, rolbypassrls "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            )
        ).one_or_none()

    if row is None:
        raise RuntimeError("Cannot resolve the worker DB role in pg_roles")

    role, is_superuser, bypasses_rls = row
    if is_superuser or bypasses_rls:
        raise RuntimeError(
            f"Worker DB role {role!r} bypasses RLS "
            f"(rolsuper={is_superuser}, rolbypassrls={bypasses_rls}); "
            "use the app_tenant role in DATABASE_URL"
        )


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging_from_env()  # воркер — отдельный процесс: JSON-логи с correlation_id
    # Свой engine воркера: создаётся в event loop ARQ и закрывается в shutdown.
    engine = build_engine(get_settings().database_url, pool_size=MAX_JOBS)
    try:
        # Блокирует старт воркера, если роль обходит RLS (BYPASSRLS / superuser).
        await _assert_rls_applies(engine)
    except BaseException:
        await engine.dispose()
        raise
    ctx["engine"] = engine
    ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    # Любой объект с протоколом ReviewInsightsService. Есть GEMINI_API_KEY -> LLM-пайплайн, иначе эвристика.
    ctx["insights_service"] = build_insights_service()


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].dispose()


class WorkerSettings:
    functions = [fetch_reviews_task, process_reviews_batch]
    redis_settings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown

    max_jobs = MAX_JOBS  # параллельных задач; pool_size БД = max_jobs
    job_timeout = 300  # сек на задачу (батч до 200 отзывов через LLM при ограниченной параллельности)
    max_tries = 3  # лимит попыток (Retry и перезапуски после падения воркера)
    keep_result = 120  # сек хранить результат; пока он жив, тот же _job_id не поставить
    health_check_interval = 30
