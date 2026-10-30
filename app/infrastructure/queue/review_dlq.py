"""DLQ для «ядовитых» отзывов: изоляция от LLM-конвейера после исчерпания попыток.

Работает на сессии с tenant-контекстом (RLS): обновить можно только отзывы своего тенанта. Чистый SQL по
public.reviews: не зависит от того, в каком модуле лежит ORM-модель Review. Все операции атомарны (один UPDATE).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("review_dlq")

MAX_ANALYSIS_RETRIES = 3
MAX_REASON_LEN = 500

# retry_count: если не передан, остаётся как есть; GREATEST не даёт «откатить» счётчик назад.
_MOVE = text(
    """
    UPDATE public.reviews
       SET retry_count = GREATEST(retry_count, COALESCE(:retry_count, retry_count)),
           dlq_reason  = :reason,
           is_analyzed = false,
           ai_pending  = false
     WHERE id = :review_id
    RETURNING retry_count
    """
)

# Инкремент и решение «в DLQ или нет» в ОДНОМ запросе: параллельные воркеры не потеряют попытку.
# В SET все выражения видят СТАРОЕ значение retry_count, поэтому новое считаем как retry_count + 1 везде.
_RECORD_FAILURE = text(
    """
    UPDATE public.reviews
       SET retry_count = retry_count + 1,
           is_analyzed = false,
           dlq_reason  = CASE WHEN retry_count + 1 >= :max_retries THEN :reason END,
           ai_pending  = CASE WHEN retry_count + 1 >= :max_retries THEN false ELSE ai_pending END
     WHERE id = :review_id AND dlq_reason IS NULL
    RETURNING retry_count, (dlq_reason IS NOT NULL) AS in_dlq
    """
)

_RESET_ON_SUCCESS = text(
    "UPDATE public.reviews SET retry_count = 0 WHERE id = ANY(:ids) AND retry_count <> 0 AND dlq_reason IS NULL"
)

_REQUEUE = text(
    """
    UPDATE public.reviews
       SET retry_count = 0, dlq_reason = NULL, ai_pending = true, is_analyzed = false
     WHERE id = :review_id AND dlq_reason IS NOT NULL
    RETURNING id
    """
)


@dataclass(frozen=True, slots=True)
class FailureOutcome:
    retry_count: int
    moved_to_dlq: bool


def _clean_reason(reason: str) -> str:
    """Только короткий код/описание. Обрезаем и схлопываем пробелы: в колонку не попадёт ничего длинного."""
    cleaned = " ".join(reason.split())[:MAX_REASON_LEN]
    return cleaned or "unknown"


async def move_review_to_dlq(
    review_id: UUID,
    reason: str,
    db: AsyncSession,
    *,
    retry_count: int | None = None,
) -> bool:
    """Изолировать отзыв: dlq_reason, is_analyzed=False, ai_pending=False (+ retry_count не меньше переданного).

    True - отзыв найден (под RLS своего тенанта) и перемещён; False - не найден/чужой.
    """
    reason = _clean_reason(reason)
    row = (
        await db.execute(
            _MOVE,
            {"review_id": review_id, "reason": reason, "retry_count": retry_count},
        )
    ).one_or_none()
    if row is None:
        logger.warning("review_dlq_not_found review_id=%s", review_id)
        return False
    logger.critical(
        "review_moved_to_dlq review_id=%s retry_count=%s reason=%s",
        review_id,
        row.retry_count,
        reason,
    )
    return True


async def record_analysis_failure(
    review_id: UUID,
    reason: str,
    db: AsyncSession,
    *,
    max_retries: int = MAX_ANALYSIS_RETRIES,
) -> FailureOutcome | None:
    """Засчитать неудачу анализа. На max_retries-й раз отзыв уходит в DLQ (CRITICAL в лог).

    None - отзыв не найден, чужой или уже в DLQ (повторно не считаем).
    """
    reason = _clean_reason(reason)
    row = (
        await db.execute(
            _RECORD_FAILURE,
            {"review_id": review_id, "reason": reason, "max_retries": max_retries},
        )
    ).one_or_none()
    if row is None:
        return None
    outcome = FailureOutcome(
        retry_count=int(row.retry_count), moved_to_dlq=bool(row.in_dlq)
    )
    if outcome.moved_to_dlq:
        logger.critical(
            "review_moved_to_dlq review_id=%s retry_count=%s reason=%s",
            review_id,
            outcome.retry_count,
            reason,
        )
    else:
        logger.warning(
            "review_analysis_failed review_id=%s attempt=%s/%s reason=%s",
            review_id,
            outcome.retry_count,
            max_retries,
            reason,
        )
    return outcome


async def reset_retry_count(review_ids: list[UUID], db: AsyncSession) -> None:
    """Успешный анализ обнуляет счётчик: считаются только неудачи подряд."""
    if review_ids:
        await db.execute(_RESET_ON_SUCCESS, {"ids": review_ids})


async def requeue_review_from_dlq(review_id: UUID, db: AsyncSession) -> bool:
    """Ручной возврат оператором в конвейер (после исправления промпта/данных)."""
    row = (await db.execute(_REQUEUE, {"review_id": review_id})).one_or_none()
    if row is not None:
        logger.warning("review_requeued_from_dlq review_id=%s", review_id)
    return row is not None
