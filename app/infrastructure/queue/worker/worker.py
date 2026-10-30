"""
ARQ Worker настройки для SERM с enterprise-логированием и DLQ
"""

# Environment must load before application imports initialize settings.
# ruff: noqa: E402
import os
from datetime import timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from arq import create_pool, cron
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logger import configure_logging, get_logger, set_correlation_id
from app.core.redis import get_redis_settings
from app.core.review_privacy import safe_review_summary
from app.core.security import decrypt_token
from app.core.tenant_session import get_tenant_session
from app.domain.billing import (
    BillingService,
    QuotaExceededError,
    SubscriptionInactiveError,
)
from app.domain.reviews.fsm import ReviewFSM, ReviewState
from app.infrastructure.integrations.llm.review_analyzer import (
    clamp_threat_level,
    create_openai_analyzer,
)
from app.infrastructure.persistence.models.economics import Review
from app.infrastructure.persistence.models.review_analysis_payload import (
    ReviewAnalysisPayload,
)
from app.infrastructure.queue.worker.api_key_usage import flush_api_key_usage
from app.infrastructure.queue.worker.digest import (
    enqueue_weekly_digests,
    send_company_weekly_digest,
)
from app.workers.tasks.ingestion import process_review_ingestion

logger = get_logger(__name__)


async def process_review_task(
    ctx: dict[str, Any],
    review_id: str | UUID,
    tenant_id: str | UUID,
    correlation_id: str | None = None,
) -> dict[str, str]:
    """Analyze a tenant review while retaining its encrypted source for replies."""
    review_uuid = UUID(str(review_id))
    tenant_uuid = UUID(str(tenant_id))

    # Set correlation ID from HTTP request context for end-to-end tracing
    if correlation_id:
        set_correlation_id(correlation_id)

    session = await get_tenant_session(AsyncSessionLocal, tenant_uuid)
    try:
        result = await session.execute(
            select(Review)
            .where(
                Review.id == review_uuid,
                Review.company_id == tenant_uuid,
            )
            .with_for_update()
        )
        review = result.scalar_one_or_none()
        if review is None:
            await session.rollback()
            logger.warning(
                "review_task_skipped_not_found",
                review_id=str(review_uuid),
                tenant_id=str(tenant_uuid),
            )
            return {"review_id": str(review_uuid), "state": "not_found"}

        if review.state not in {ReviewState.NEW, ReviewState.ANALYZING}:
            state = review.state.value
            await session.rollback()
            logger.info(
                "review_task_skipped_wrong_state",
                review_id=str(review_uuid),
                state=state,
            )
            return {"review_id": str(review_uuid), "state": state}

        payload = await session.scalar(
            select(ReviewAnalysisPayload).where(
                ReviewAnalysisPayload.review_id == review_uuid,
                ReviewAnalysisPayload.company_id == tenant_uuid,
            )
        )
        if payload is None:
            await session.rollback()
            logger.error(
                "review_analysis_payload_missing",
                review_id=str(review_uuid),
                tenant_id=str(tenant_uuid),
            )
            raise RuntimeError(
                f"Encrypted analysis payload missing for review {review_uuid}"
            )

        review_text = decrypt_token(payload.encrypted_text)
        rating = review.rating
        if review.state == ReviewState.NEW:
            ReviewFSM.start_analysis(review)
        try:
            await BillingService(session).check_quota(tenant_uuid)
        except (QuotaExceededError, SubscriptionInactiveError) as exc:
            if review.state == ReviewState.ANALYZING:
                ReviewFSM.fail_analysis(review)
            review.ai_error = str(exc)
            logger.error(
                "review_analysis_blocked_by_billing",
                review_id=str(review_uuid),
                tenant_id=str(tenant_uuid),
                error=str(exc),
            )
            await session.commit()
            return {"review_id": str(review_uuid), "state": review.state.value}
        await session.commit()
    finally:
        await session.close()

    # Use OpenAI LLM for analysis
    analyzer = create_openai_analyzer()
    try:
        analysis = await analyzer.analyze_review(
            review_text,
            rating=rating,
            platform=None,
        )
    except Exception as exc:
        # If all retries exhausted, transition to ANALYSIS_FAILED
        session = await get_tenant_session(AsyncSessionLocal, tenant_uuid)
        try:
            result = await session.execute(
                select(Review)
                .where(
                    Review.id == review_uuid,
                    Review.company_id == tenant_uuid,
                )
                .with_for_update()
            )
            review = result.scalar_one_or_none()
            if review and review.state == ReviewState.ANALYZING:
                ReviewFSM.fail_analysis(review)
                review.ai_error = str(exc)
                await session.commit()
                logger.error(
                    "review_analysis_failed_after_retries",
                    review_id=str(review_uuid),
                    error=str(exc),
                    state=review.state.value,
                )
        finally:
            await session.close()
        raise
    finally:
        await analyzer.close()

    session = await get_tenant_session(AsyncSessionLocal, tenant_uuid)
    try:
        result = await session.execute(
            select(Review)
            .where(
                Review.id == review_uuid,
                Review.company_id == tenant_uuid,
            )
            .with_for_update()
        )
        review = result.scalar_one_or_none()
        if review is None:
            await session.rollback()
            logger.warning(
                "review_disappeared_during_analysis",
                review_id=str(review_uuid),
                tenant_id=str(tenant_uuid),
            )
            return {"review_id": str(review_uuid), "state": "not_found"}
        if review.state != ReviewState.ANALYZING:
            state = review.state.value
            await session.rollback()
            return {"review_id": str(review_uuid), "state": state}

        payload = await session.scalar(
            select(ReviewAnalysisPayload).where(
                ReviewAnalysisPayload.review_id == review_uuid,
                ReviewAnalysisPayload.company_id == tenant_uuid,
            )
        )
        if payload is None:
            await session.rollback()
            logger.error(
                "review_analysis_payload_missing_at_completion",
                review_id=str(review_uuid),
                tenant_id=str(tenant_uuid),
            )
            raise RuntimeError(
                f"Encrypted analysis payload missing for review {review_uuid}"
            )

        if not analysis.is_fallback:
            await BillingService(session).log_usage(
                tenant_uuid,
                analysis.model_used,
                analysis.input_tokens,
                analysis.output_tokens,
            )

        summary_sentiment = analysis.sentiment
        threat_level = clamp_threat_level(analysis.threat_level)
        review.text = safe_review_summary(rating, summary_sentiment)
        review.sentiment = analysis.sentiment
        review.threat_level = threat_level
        review.is_critical = threat_level >= 5
        review.is_analyzed = True
        review.tags = analysis.tags
        review.suggested_reply = None
        review.ai_error = None
        review.dlq_reason = None

        # FSM transitions based on threat_level
        if threat_level >= 5:
            # Critical threat: escalate to management
            ReviewFSM.escalate_threat(review)
        elif analysis.sentiment == "POSITIVE":
            # Positive sentiment: auto-approve
            ReviewFSM.approve_auto(review)
        elif threat_level >= 4:
            # Medium threat: require human draft
            ReviewFSM.require_human_draft(review)
        else:
            # Low threat: ignore
            ReviewFSM.ignore(review)

        await session.commit()
        logger.info(
            "review_analysis_completed",
            review_id=str(review_uuid),
            state=review.state.value,
        )
        return {"review_id": str(review_uuid), "state": review.state.value}
    finally:
        await session.close()


class WorkerSettings:
    on_startup: Any
    on_shutdown: Any

    """Конфигурация ARQ Worker с Dead Letter Queue"""

    # Настройки Redis
    redis_settings = get_redis_settings()

    # Задачи для выполнения
    functions = [
        process_review_task,
        process_review_ingestion,
        send_company_weekly_digest,
        enqueue_weekly_digests,
        flush_api_key_usage,
    ]
    cron_jobs = [
        cron(enqueue_weekly_digests, weekday="mon", hour=9, minute=0),
        cron(flush_api_key_usage, second=0),
    ]
    timezone = timezone.utc

    # Настройки воркера
    max_jobs = 10
    job_timeout = 300  # 5 минут на задачу
    keep_result = 120  # Держим результаты 2 минуты
    max_tries = 5  # Максимальное количество попыток для DLQ

    # Логирование
    log_results = True

    # Обработка ошибок
    allow_abort_jobs = True


async def on_startup(ctx):
    """Инициализация воркера с настройкой логирования"""

    # Настройка логирования для воркера
    environment = os.getenv("ENVIRONMENT", "development")
    debug_mode = environment.lower() in ("development", "dev")

    configure_logging(
        level="DEBUG" if debug_mode else "INFO",
        json_format=not debug_mode,
        include_caller_info=debug_mode,
        service_name="serm-worker",
    )

    logger = get_logger(__name__)
    logger.info("=" * 60)
    logger.info(
        "🚀 ARQ Worker starting up...", service="serm-worker", environment=environment
    )

    try:
        # КРИТИЧЕСКАЯ ПРОВЕРКА: Если подключение не удалось с app_tenant ролью -
        # это может означать что используется fallback на суперюзера
        # В этом случае ЖЁСТКО падаем

        # Проверяем подключение через app_tenant URL
        tenant_url = os.getenv("TENANT_DATABASE_URL")
        if not tenant_url:
            logger.error("❌ FATAL: TENANT_DATABASE_URL not configured!")
            raise ValueError(
                "TENANT_DATABASE_URL is required for secure worker operation"
            )

        # Конвертируем URL для asyncpg (убираем +asyncpg)
        asyncpg_url = tenant_url.replace("postgresql+asyncpg://", "postgresql://")

        import asyncpg  # type: ignore[import-untyped]

        logger.info("🔒 SECURITY CHECK: Testing app_tenant role connection...")

        try:
            # КРИТИЧЕСКАЯ ПРОВЕРКА: Подключение ДОЛЖНО быть только через app_tenant
            # Подключаемся с отключенным кэшем prepared statements для Supabase
            conn = await asyncpg.connect(asyncpg_url, statement_cache_size=0)
        except Exception as db_error:
            logger.error("❌ CRITICAL FAILURE: Cannot connect with app_tenant role!")
            logger.error(f"❌ Database error: {db_error}")
            logger.error(
                "❌ This indicates app_tenant role is not properly "
                "configured in Supabase"
            )
            logger.error("❌ Worker CANNOT start without proper non-privileged role!")
            logger.error("❌ SECURITY HALT: Risk of using privileged role detected")
            raise ValueError(
                f"SECURITY FAILURE: app_tenant connection failed - {db_error}"
            )

        # Проверяем роль на предмет нарушения безопасности RLS
        role_info = await conn.fetchrow("""
            SELECT rolname, rolsuper, rolbypassrls
            FROM pg_roles WHERE rolname = current_user
        """)

        current_role = role_info["rolname"]
        is_superuser = role_info["rolsuper"]
        bypass_rls = role_info["rolbypassrls"]

        logger.info(f"🔒 Current database role: {current_role}")
        logger.info(f"🔒 Superuser: {is_superuser}")
        logger.info(f"🔒 Bypass RLS: {bypass_rls}")

        # ЖЁСТКАЯ ПРОВЕРКА БЕЗОПАСНОСТИ - НИ ОДНОГО ИСКЛЮЧЕНИЯ
        if is_superuser:
            logger.error("❌ CRITICAL SECURITY VIOLATION: Database role is SUPERUSER!")
            logger.error("❌ Superuser roles CANNOT be used in multi-tenant systems!")
            logger.error("❌ Worker startup TERMINATED to prevent data leakage!")
            raise ValueError(
                f"SECURITY VIOLATION: Role '{current_role}' is SUPERUSER - "
                f"multi-tenant isolation COMPROMISED"
            )

        if bypass_rls:
            logger.error(
                "❌ CRITICAL SECURITY VIOLATION: Database role has BYPASSRLS privilege!"
            )
            logger.error(
                "❌ BYPASSRLS completely destroys Row Level Security isolation!"
            )
            logger.error(
                "❌ Worker startup TERMINATED to prevent tenant data exposure!"
            )
            raise ValueError(
                f"SECURITY VIOLATION: Role '{current_role}' has BYPASSRLS - "
                f"multi-tenant isolation DESTROYED"
            )

        # Проверяем что это именно app_tenant роль
        if current_role != "app_tenant":
            logger.error(
                f"❌ SECURITY ERROR: Expected 'app_tenant' role, got '{current_role}'"
            )
            logger.error("❌ Only app_tenant role is authorized for worker operations!")
            raise ValueError(
                f"UNAUTHORIZED ROLE: Expected 'app_tenant', got '{current_role}'"
            )

        logger.info(
            "✅ SECURITY VERIFIED: app_tenant role with proper RLS restrictions"
        )

        await conn.close()

        logger.info("✅ Database connection verified - RLS security maintained")

        # Проверяем Redis подключение
        redis_settings = get_redis_settings()
        logger.info(
            f"🔗 Testing Redis connection at "
            f"{redis_settings.host}:{redis_settings.port}"
        )

        pool = await create_pool(redis_settings)
        await pool.close()

        logger.info("✅ Redis connection verified")

    except Exception as e:
        logger.error(f"❌ Worker startup failed: {e}")
        import traceback

        traceback.print_exc()
        raise

    logger.info("=" * 60)
    logger.info("✅ ARQ Worker startup completed successfully!")
    logger.info("=" * 60)


async def on_shutdown(ctx):
    """Завершение работы воркера"""
    logger.info("🛑 ARQ Worker shutting down...")
    logger.info("✅ Worker shutdown completed")


# Добавляем хуки в настройки
WorkerSettings.on_startup = on_startup
WorkerSettings.on_shutdown = on_shutdown


async def create_arq_pool():
    """Создание пула подключений к Redis для ARQ"""
    if os.getenv("REDIS_URL") == "dummy://skip":
        raise RuntimeError("Redis is disabled by local development configuration.")
    return await create_pool(get_redis_settings())
