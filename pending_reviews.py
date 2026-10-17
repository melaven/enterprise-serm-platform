"""Очередь отзывов, ожидающих AI-разметки. Lease-паттерн поверх FOR UPDATE SKIP LOCKED.

Почему не «держать транзакцию с блокировкой на время LLM-вызовов»: это минуты
`idle in transaction` на соединении из пула, раздутый vacuum и обрыв при рестарте
Supavisor. Вместо этого:
  1. короткая транзакция: SELECT ... FOR UPDATE SKIP LOCKED + UPDATE (lease: token, until);
  2. LLM работает ВНЕ транзакции, строки защищены lease'ом (другие воркеры их не берут);
  3. короткая транзакция записи, guard `ai_claim_token = :token`: если lease истёк и строку
     забрал другой воркер, наша запись не перетрёт его результат.
Упавший воркер = lease истекает сам, строки возвращаются в работу.
"""

from __future__ import annotations

import json
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.worker_db import tenant_transaction
from app.repositories.pending_types import ClaimedReview, Failure, Success
from app.schemas.parser import Platform
from app.services.scraping import RawReview

log = structlog.get_logger(__name__)


_TENANTS: Final = text("SELECT * FROM app.tenants_with_pending_ai(:lim, :max_attempts)")

# Строки, исчерпавшие попытки без финализации (воркер падал на них), закрываем явно:
# иначе они навсегда остались бы ai_pending=true, но невидимыми для claim.
_GIVE_UP_EXHAUSTED: Final = text(
    """
    UPDATE public.reviews
    SET ai_pending = false,
        ai_last_error = 'gave_up:max_attempts_exceeded',
        ai_claim_token = NULL, ai_claimed_until = NULL
    WHERE company_id = CAST(:tenant AS uuid)
      AND ai_pending
      AND ai_attempts >= :max_attempts
      AND (ai_claimed_until IS NULL OR ai_claimed_until < now())
    """
)

_CLAIM: Final = text(
    """
    WITH picked AS (
      SELECT id
      FROM public.reviews
      WHERE company_id = CAST(:tenant AS uuid)
        AND ai_pending
        AND ai_attempts < :max_attempts
        AND (ai_next_attempt_at IS NULL OR ai_next_attempt_at <= now())
        AND (ai_claimed_until IS NULL OR ai_claimed_until < now())
      ORDER BY ai_next_attempt_at NULLS FIRST, id
      LIMIT :lim
      FOR UPDATE SKIP LOCKED
    )
    UPDATE public.reviews r
    SET ai_claim_token   = CAST(:token AS uuid),
        ai_claimed_until = now() + CAST(:lease_s AS double precision) * interval '1 second',
        ai_attempts      = r.ai_attempts + 1
    FROM picked
    WHERE r.id = picked.id
    RETURNING r.id, r.platform, r.external_id, r.author_name, r.rating, r.body,
              r.published_at, r.ai_attempts
    """
)

_SAVE_SUCCESS: Final = text(
    """
    UPDATE public.reviews r
    SET sentiment          = v.sentiment,
        ai_tags            = ARRAY(SELECT jsonb_array_elements_text(v.tags)),
        is_critical        = v.is_critical,
        ai_reply_draft     = v.reply,
        ai_pending         = false,
        ai_last_error      = NULL,
        ai_processed_at    = now(),
        ai_next_attempt_at = NULL,
        ai_claim_token     = NULL,
        ai_claimed_until   = NULL
    FROM jsonb_to_recordset(CAST(:payload AS jsonb))
         AS v(id uuid, sentiment text, tags jsonb, is_critical boolean, reply text)
    WHERE r.id = v.id
      AND r.company_id = CAST(:tenant AS uuid)
      AND r.ai_claim_token = CAST(:token AS uuid)
    """
)

_SAVE_FAILURE: Final = text(
    """
    UPDATE public.reviews r
    SET ai_pending         = NOT v.give_up,
        ai_attempts        = GREATEST(r.ai_attempts - v.refund, 0),
        ai_next_attempt_at = v.next_at,
        ai_last_error      = left(v.error, 200),
        ai_claim_token     = NULL,
        ai_claimed_until   = NULL
    FROM jsonb_to_recordset(CAST(:payload AS jsonb))
         AS v(id uuid, error text, give_up boolean, refund integer, next_at timestamptz)
    WHERE r.id = v.id
      AND r.company_id = CAST(:tenant AS uuid)
      AND r.ai_claim_token = CAST(:token AS uuid)
    """
)


def _to_raw_review(row: object) -> RawReview | None:
    r = row._mapping  # type: ignore[attr-defined]
    try:
        platform = Platform(r["platform"])
    except ValueError:
        return None
    return RawReview(
        external_id=r["external_id"] or f"db:{r['id']}",
        platform=platform,
        author_name=r["author_name"],
        rating=r["rating"],
        text=r["body"] or "",
        published_at=r["published_at"],
    )


class SqlPendingReviewStore:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        *,
        max_attempts: int,
        lease_s: float,
    ) -> None:
        self._factory = factory
        self._max_attempts = max_attempts
        self._lease_s = lease_s

    async def tenants_with_pending(self, limit: int) -> list[UUID]:
        async with self._factory() as session, session.begin():
            result = await session.execute(
                _TENANTS, {"lim": limit, "max_attempts": self._max_attempts}
            )
            return [row[0] for row in result]

    async def claim(
        self, tenant_id: UUID, *, limit: int, token: UUID
    ) -> list[ClaimedReview]:
        async with tenant_transaction(self._factory, tenant_id) as session:
            exhausted = await session.execute(
                _GIVE_UP_EXHAUSTED,
                {"tenant": str(tenant_id), "max_attempts": self._max_attempts},
            )
            if exhausted.rowcount:
                log.warning(
                    "ai_retry.gave_up_exhausted",
                    tenant_id=str(tenant_id),
                    rows=exhausted.rowcount,
                )
            result = await session.execute(
                _CLAIM,
                {
                    "tenant": str(tenant_id),
                    "max_attempts": self._max_attempts,
                    "lim": limit,
                    "token": str(token),
                    "lease_s": self._lease_s,
                },
            )
            return [
                ClaimedReview(
                    id=row._mapping["id"],
                    attempts=row._mapping["ai_attempts"],
                    review=_to_raw_review(row),
                )
                for row in result
            ]

    async def finalize(
        self,
        tenant_id: UUID,
        token: UUID,
        successes: list[Success],
        failures: list[Failure],
    ) -> int:
        updated = 0
        async with tenant_transaction(self._factory, tenant_id) as session:
            if successes:
                payload = [
                    {
                        "id": str(s.review_id),
                        "sentiment": s.enriched.sentiment.value
                        if s.enriched.sentiment
                        else None,
                        "tags": list(s.enriched.tags),
                        "is_critical": s.enriched.is_critical,
                        "reply": s.enriched.reply,
                    }
                    for s in successes
                ]
                res = await session.execute(
                    _SAVE_SUCCESS,
                    {
                        "payload": json.dumps(payload),
                        "tenant": str(tenant_id),
                        "token": str(token),
                    },
                )
                updated += res.rowcount
            if failures:
                payload_f = [
                    {
                        "id": str(f.review_id),
                        "error": f.error,
                        "give_up": f.give_up,
                        "refund": int(f.refund_attempt),
                        "next_at": f.next_attempt_at.isoformat(),
                    }
                    for f in failures
                ]
                res = await session.execute(
                    _SAVE_FAILURE,
                    {
                        "payload": json.dumps(payload_f),
                        "tenant": str(tenant_id),
                        "token": str(token),
                    },
                )
                updated += res.rowcount
        return updated
