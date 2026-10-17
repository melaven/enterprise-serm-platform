"""Типы и контракт хранилища очереди AI-ретрая (без зависимости от SQLAlchemy)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.schemas.parser import RawReview
from app.services.ai_processor import EnrichedReview


@dataclass(frozen=True, slots=True)
class ClaimedReview:
    id: UUID
    attempts: int  # уже с учётом текущей попытки
    review: RawReview | None  # None: строка не собирается в RawReview (битые данные)


@dataclass(frozen=True, slots=True)
class Success:
    review_id: UUID
    enriched: EnrichedReview


@dataclass(frozen=True, slots=True)
class Failure:
    review_id: UUID
    error: str
    give_up: bool  # True: ai_pending=false, больше не пытаемся
    refund_attempt: bool  # True: сбой на стороне провайдера, попытку не засчитываем
    next_attempt_at: datetime


class PendingReviewStore(Protocol):
    async def tenants_with_pending(self, limit: int) -> list[UUID]: ...

    async def claim(
        self, tenant_id: UUID, *, limit: int, token: UUID
    ) -> list[ClaimedReview]: ...

    async def finalize(
        self,
        tenant_id: UUID,
        token: UUID,
        successes: list[Success],
        failures: list[Failure],
    ) -> int:
        """Возвращает число реально обновлённых строк (меньше ожидаемого = lease потерян)."""
        ...
