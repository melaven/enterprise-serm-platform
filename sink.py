"""Контракты слоя сохранения и биллинга для оркестратора.

PostgresReviewSink (ваша реализация) обязан:
  * save_many: идемпотентный INSERT ... ON CONFLICT (tenant, platform, external_id) DO NOTHING
    (существующие строки с готовой AI-разметкой НЕ перезаписываются); ai_pending и поля
    разметки берутся из EnrichedReview; вернуть число реально вставленных строк;
  * existing_external_ids: какие из id уже есть в БД (чтобы не платить за повторную разметку).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.schemas.parser import Platform
from app.services.ai_processor import EnrichedReview


class ReviewSink(Protocol):
    async def existing_external_ids(
        self, tenant_id: UUID, platform: Platform, external_ids: Sequence[str]
    ) -> set[str]: ...

    async def save_many(self, tenant_id: UUID, reviews: Sequence[EnrichedReview]) -> int: ...


class QuotaBilling(Protocol):
    """Списание за фактически сохранённое. Адаптер поверх QuotaService
    (consume_reviews_parsed / consume_llm_tokens). Может бросать любые исключения:
    оркестратор их логирует и не валит задачу."""

    async def charge(
        self, tenant_id: UUID, *, reviews_saved: int, enriched: Sequence[EnrichedReview]
    ) -> None: ...
