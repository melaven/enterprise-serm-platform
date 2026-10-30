"""
ARQ Worker с инициализацией Supabase service role для DLQ
и зависимостей Tenable SERM парсеров
"""

import asyncio
import os
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx
import structlog
from supabase import acreate_client

from app.core.logger import configure_logging
from app.infrastructure.parsers.factory import ParserDeps
from app.infrastructure.persistence.repositories.dlq import (
    SupabaseDLQStore,
    set_default_dlq_store,
)
from app.infrastructure.persistence.repositories.postgres_review_sink import (
    PostgresReviewSink,
)
from app.infrastructure.queue.worker.worker import WorkerSettings
from app.infrastructure.queue.worker.worker import on_shutdown as worker_shutdown
from app.infrastructure.queue.worker.worker import on_startup as worker_startup

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class MockReviewSink:
    """Заглушка для сохранения отзывов (заменить на реальную реализацию)."""

    async def save(self, company_id: UUID, items: Sequence[Any]) -> int:
        """Сохраняет проанализированные отзывы."""
        # Здесь должна быть реальная логика сохранения в БД
        logger.info("mock_reviews_saved", company_id=str(company_id), count=len(items))
        return len(items)


async def startup_with_dlq(ctx: dict[str, Any]) -> None:
    """Startup функция с инициализацией Supabase service role клиента для DLQ
    и зависимостей боевых парсеров."""

    # Сначала выполняем стандартный startup
    await worker_startup(ctx)

    logger.info("🔐 Initializing Supabase service role client for DLQ...")

    # Инициализация Supabase клиента с service_role ключом
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url:
        raise RuntimeError("SUPABASE_URL environment variable is required")

    if not service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY environment variable is required")

    try:
        # Создаем async клиент с service role ключом
        supabase_client = await acreate_client(supabase_url, service_role_key)

        # Создаем DLQ store с Supabase клиентом
        dlq_store = SupabaseDLQStore(supabase_client)

        # Устанавливаем как глобальный store
        set_default_dlq_store(dlq_store)

        # Добавляем store в контекст для задач
        ctx["dlq_store"] = dlq_store
        ctx["max_tries"] = getattr(WorkerSettings, "max_tries", 3)

        logger.info("✅ DLQ Supabase store initialized with service role access")

        # Тест соединения - пытаемся получить версию или выполнить простой запрос
        try:
            # Простая проверка доступности таблицы DLQ (только чтение схемы)
            (
                await supabase_client.table("dead_letter_queue")
                .select("id")
                .limit(1)
                .execute()
            )
            logger.info("✅ DLQ table access verified")
        except Exception as test_error:
            logger.warning(
                f"⚠️ DLQ table test failed (expected if table is empty): {test_error}"
            )

    except Exception as e:
        logger.error(f"❌ Failed to initialize DLQ Supabase client: {e}")
        logger.error("❌ DLQ functionality will be unavailable")
        # Не падаем полностью, но DLQ будет недоступен
        ctx["dlq_store"] = None

    # Инициализация зависимостей парсеров
    logger.info("🔧 Initializing parser dependencies...")

    try:
        # Создаем HTTP клиент для парсеров
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
        )

        # Получаем API ключи для парсеров
        twogis_api_key = os.getenv("TWOGIS_API_KEY", "")

        # Создаем зависимости парсеров
        parser_deps = ParserDeps(http_client=http_client, twogis_api_key=twogis_api_key)

        # === РЕАЛЬНЫЕ СЕРВИСЫ ВМЕСТО ЗАГЛУШЕК ===

        # 1. PostgresReviewSink для сохранения отзывов
        review_sink = PostgresReviewSink()
        logger.info("✅ PostgresReviewSink initialized")

        # 2. QuotaService - будет инициализирован в задаче с DB session
        # Здесь только помечаем что он доступен
        ctx["quota_service_enabled"] = True
        logger.info("✅ QuotaService factory configured")

        # Прокидываем зависимости в контекст задач
        ctx["parser_deps"] = parser_deps
        ctx["review_sink"] = review_sink
        ctx["http_client"] = http_client  # Для правильного закрытия

        logger.info("✅ Parser dependencies initialized")
        logger.info(
            f"✅ TwoGIS API key configured: {'Yes' if twogis_api_key else 'No'}"
        )

    except Exception as e:
        logger.error(f"❌ Failed to initialize parser dependencies: {e}")
        raise


async def shutdown_with_dlq(ctx: dict[str, Any]) -> None:
    """Shutdown функция с очисткой DLQ и parser ресурсов."""

    logger.info("🔐 Shutting down DLQ and parser resources...")

    try:
        # Закрываем HTTP клиент парсеров
        http_client = ctx.get("http_client")
        if http_client and hasattr(http_client, "aclose"):
            await http_client.aclose()
            logger.info("✅ Parser HTTP client closed")

        # Очищаем глобальный DLQ store
        set_default_dlq_store(None)

        # Закрываем Supabase клиент если он есть
        dlq_store = ctx.get("dlq_store")
        if dlq_store and hasattr(dlq_store, "_client"):
            client = dlq_store._client
            if hasattr(client, "close"):
                await client.close()

        logger.info("✅ DLQ and parser resources cleaned up")

    except Exception as e:
        logger.error(f"❌ Error during resource cleanup: {e}")

    # Выполняем стандартный shutdown
    await worker_shutdown(ctx)


# Обновляем настройки воркера с DLQ startup/shutdown
WorkerSettings.on_startup = startup_with_dlq
WorkerSettings.on_shutdown = shutdown_with_dlq


async def main():
    """Запуск ARQ worker с DLQ поддержкой."""
    from arq.worker import Worker

    environment = os.getenv("ENVIRONMENT", "development")
    debug_mode = environment.lower() in ("development", "dev")

    # Настройка логирования
    configure_logging(
        level="DEBUG" if debug_mode else "INFO",
        json_format=not debug_mode,
        include_caller_info=debug_mode,
        service_name="serm-worker-dlq",
    )

    logger.info("🚀 Starting ARQ Worker with DLQ support...")

    try:
        worker = Worker(
            settings=WorkerSettings,
            handle_signals=True,
        )
        await worker.main()
    except KeyboardInterrupt:
        logger.info("⚠️ Worker interrupted by user")
    except Exception as e:
        logger.error(f"❌ Worker failed: {e}")
        raise
    finally:
        logger.info("🛑 Worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
