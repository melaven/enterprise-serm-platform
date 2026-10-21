"""ARQ-задача пакетного анализа отзывов: process_reviews_batch(tenant_id, review_ids)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from arq import Retry
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.tracing import traced_task
from app.db.tenant import tenant_session
from app.models.economics import Review
from app.services.review_dlq import (
    MAX_ANALYSIS_RETRIES,
    record_analysis_failure,
    reset_retry_count,
)
from app.services.review_insights import (
    InsightsTransientError,
    ReviewForInsights,
    ReviewInsight,
    ReviewInsightsService,
)

logger = logging.getLogger("arq.analysis")

MAX_BATCH = 200  # тот же потолок, что в API: аргументы приходят из Redis, доверять размеру нельзя


@traced_task
async def process_reviews_batch(
    ctx: dict[str, Any], tenant_id: UUID, review_ids: list[UUID]
) -> dict[str, int]:
    """Читает отзывы под RLS -> анализ БЕЗ открытой транзакции -> массовое обновление под RLS.

    Идемпотентна: повторный запуск перезаписывает те же поля. Транзакции короткие: медленная аналитика
    (LLM) не держит соединение пула. Чужие/удалённые id RLS скрывает: они просто не попадают в выборку.
    """
    ids = list(dict.fromkeys(review_ids))
    if len(ids) > MAX_BATCH:
        raise ValueError(f"batch too large: {len(ids)} > {MAX_BATCH}")

    factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]
    service: ReviewInsightsService = ctx["insights_service"]

    # 1) Чтение. В воркере нет FastAPI-зависимости get_tenant_session (она требует JWT запроса):
    #    её эквивалент вне HTTP — tenant_session(factory, company_id): та же транзакция + set_config.
    async with tenant_session(factory, tenant_id) as session:
        rows = (
            await session.execute(
                # dlq_reason IS NULL: отзывы в DLQ изолированы от конвейера (вернуть может только оператор).
                select(Review.id, Review.text, Review.rating).where(Review.id.in_(ids), Review.dlq_reason.is_(None))
            )
        ).all()
    reviews = [ReviewForInsights(id=r.id, text=r.text or "", rating=r.rating) for r in rows]
    raw_text: dict[UUID, str | None] = {r.id: r.text for r in rows}
    if len(reviews) != len(ids):
        logger.warning(
            "tenant=%s requested=%d visible=%d (остальные не найдены или чужие)",
            tenant_id, len(ids), len(reviews),
        )
    if not reviews:
        return {"requested": len(ids), "found": 0, "analyzed": 0, "dlq": 0}

    # 2) Аналитика вне транзакции. Временный сбой -> повтор с нарастающей паузой (max_tries в WorkerSettings).
    try:
        insights = await service.analyze_many(reviews)
    except InsightsTransientError as exc:
        defer = ctx["job_try"] * 15
        logger.warning("tenant=%s insights transient error, retry in %ss: %s", tenant_id, defer, exc)
        raise Retry(defer=defer) from exc

    by_id: dict[UUID, ReviewInsight] = {i.review_id: i for i in insights}
    if set(by_id) != {r.id for r in reviews}:
        raise RuntimeError("insights service must return exactly one insight per review")

    # 3) Массовое обновление: ORM bulk UPDATE по первичному ключу. Сортировка по id даёт одинаковый порядок
    #    блокировок у параллельных батчей (защита от deadlock 40P01).
    payload = [
        {
            "id": i.review_id,
            "sentiment": i.sentiment.value,
            "threat_level": i.threat_level,
            "suggested_reply": i.suggested_reply,
            "analysis_tags": list(i.tags),
            "is_analyzed": i.complete,
            # 152-ФЗ: оригинал с ПДн заменяется очищенным текстом (LLM-версия после проверок либо детерминированная
            # очистка). Необратимо: исходный текст нигде не сохраняется. None -> тело не меняем.
            "text": i.sanitized_text if i.sanitized_text is not None else raw_text[i.review_id],
        }
        for i in sorted(by_id.values(), key=lambda x: str(x.review_id))
    ]
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(update(Review), payload)

        # DLQ: та же транзакция, что и результат анализа. Успех обнуляет счётчик, постоянная ошибка засчитывается;
        # на MAX_ANALYSIS_RETRIES-й раз отзыв изолируется (dlq_reason, ai_pending=false) с CRITICAL в логе.
        await reset_retry_count([i.review_id for i in by_id.values() if i.complete], session)
        in_dlq = 0
        for insight in sorted(by_id.values(), key=lambda x: str(x.review_id)):
            if insight.failure is None:
                continue
            outcome = await record_analysis_failure(
                insight.review_id, insight.failure, session, max_retries=MAX_ANALYSIS_RETRIES
            )
            in_dlq += int(outcome is not None and outcome.moved_to_dlq)

    analyzed = sum(1 for p in payload if p["is_analyzed"])
    logger.info("tenant=%s batch done found=%d analyzed=%d dlq=%d", tenant_id, len(payload), analyzed, in_dlq)
    return {"requested": len(ids), "found": len(payload), "analyzed": analyzed, "dlq": in_dlq}
