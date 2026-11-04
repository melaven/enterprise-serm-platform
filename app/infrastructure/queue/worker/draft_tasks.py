"""Critical-задача: черновики ответа на отзыв (кнопка в UI, AntiCrisisRadar). Выполняется только пулом `critical`."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from arq import Retry
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.ai import AIResponseGenerator, TenantContext
from app.core.tenant_session import set_tenant_rls_context
from app.core.tracing import traced_task
from app.services.draft_service import (
    DraftService,
    DraftsLockedError,
    ReviewNotFoundError,
)

logger = logging.getLogger("arq.drafts")

MAX_DB_RETRIES = 2


@asynccontextmanager
async def _tenant_session(
    factory: async_sessionmaker[AsyncSession], tenant_id: UUID
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        async with session.begin():
            await set_tenant_rls_context(session, tenant_id)
            yield session


@traced_task("generate_drafts_task")
async def generate_drafts_task(
    ctx: dict[str, Any],
    tenant_id: UUID,
    review_id: UUID,
    tenant_settings: dict[str, Any],
    regenerate: bool = False,
) -> dict[str, Any]:
    """Идемпотентно создаёт 3 черновика (повтор задачи возвращает уже созданный набор, LLM не вызывается).

    tenant_settings приходит из Redis, поэтому проходит ту же валидацию Pydantic, что и любой внешний ввод.
    Ошибки конфигурации LLM (LLMPermanentError) не ловятся: задача падает громко, и срабатывает алерт.
    """
    factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    generator: AIResponseGenerator = ctx["draft_generator"]
    tenant = TenantContext.model_validate(tenant_settings)
    service = DraftService(generator, lambda: _tenant_session(factory, tenant_id))
    try:
        saved = await service.generate_for_review(
            review_id, tenant, regenerate=regenerate
        )
    except ReviewNotFoundError:
        logger.warning("review_id=%s not found for tenant=%s", review_id, tenant_id)
        return {"status": "not_found"}
    except DraftsLockedError:
        return {"status": "locked"}
    except OperationalError as exc:
        # Временный сбой БД (обрыв соединения, Supavisor): повтор с нарастающей паузой.
        if int(ctx.get("job_try", 1)) > MAX_DB_RETRIES:
            raise
        raise Retry(defer=2 * int(ctx.get("job_try", 1))) from exc

    return {
        "status": "created" if saved.created else "exists",
        "drafts": len(saved.drafts),
        "source": saved.drafts[0].source.value,
        "regeneration_recommended": saved.regeneration_recommended,
    }
