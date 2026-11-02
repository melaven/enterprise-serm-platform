"""DraftService: генерация и сохранение трёх черновиков ответа в public.ai_response_drafts.

Транзакции короткие и разделены вокруг вызова LLM (25+ секунд): соединение БД (и серверное соединение
Supavisor в transaction-режиме) не удерживается, пока модель думает.

    tx1 (RLS): прочитать отзыв и активные черновики     -> если уже есть, вернуть их, LLM не вызываем
    LLM      : AIResponseGenerator.generate()           -> всегда 3 варианта (LLM или шаблон)
    tx2 (RLS): INSERT ... ON CONFLICT DO NOTHING        -> идемпотентно при повторе ARQ-задачи и гонке воркеров

Изоляцию арендаторов делает RLS (migration 046): company_id устанавливается текущим tenant-контекстом.
Сессии приходят через session_scope: контекстный менеджер, который открывает транзакцию с tenant-контекстом
(например, `lambda: tenant_session(factory, payload)`), коммитит при выходе и сам откатывает при исключении.
Внутри блоков commit() не вызывается: только flush/execute.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai.errors import LLMPermanentError
from app.core.ai.generator import AIResponseGenerator
from app.core.ai.providers import build_provider
from app.core.ai.schemas import (
    DRAFTS_PER_REVIEW,
    DraftVariant,
    GenerationResult,
    GenerationSource,
    ReviewSnapshot,
    TenantContext,
)
from app.core.config import get_settings
from app.infrastructure.persistence.models.economics import Company

log = logging.getLogger(__name__)

SessionScope = Callable[[], AbstractAsyncContextManager[AsyncSession]]

STATUS_DRAFT: Final = "draft"
STATUS_APPROVED: Final = "approved"

_COLUMNS: Final = "id, review_id, generation, variant, content, source, fallback_reason, model, status, created_at"

_SELECT_REVIEW = text(
    "SELECT id, rating, text AS body, platform, sentiment, threat_level "
    "FROM public.reviews WHERE id = :review_id"
)

_SELECT_ACTIVE = text(
    f"""
    SELECT {_COLUMNS}
      FROM public.ai_response_drafts
     WHERE review_id = :review_id AND status IN ('draft', 'approved')
     ORDER BY generation DESC, variant
    """
)

# Перегенерация: заменяются только неподтверждённые варианты. Подтверждённый ответ трогать нельзя.
_SUPERSEDE = text(
    """
    UPDATE public.ai_response_drafts
       SET status = 'superseded'
     WHERE review_id = :review_id AND status = 'draft'
    """
)

# Номер поколения считается в самом INSERT; конфликт любого уникального индекса (повтор задачи, гонка
# воркеров) тихо отбрасывает строку, а вызывающий код сверяет число вставленных строк.
_INSERT = text(
    f"""
    INSERT INTO public.ai_response_drafts
           (review_id, generation, variant, content, source, fallback_reason, model, prompt_version)
    SELECT :review_id, g.next_generation, v.variant, v.content,
           :source, :fallback_reason, :model, :prompt_version
      FROM unnest(CAST(:variants AS text[]), CAST(:contents AS text[])) AS v(variant, content)
     CROSS JOIN (
           SELECT COALESCE(MAX(generation), 0) + 1 AS next_generation
             FROM public.ai_response_drafts WHERE review_id = :review_id
           ) AS g
    ON CONFLICT DO NOTHING
    RETURNING {_COLUMNS}
    """
)


class ReviewNotFoundError(LookupError):
    """Отзыв не найден или скрыт RLS (чужой тенант). Роутер отвечает 404, факт существования не раскрываем."""


class DraftsLockedError(RuntimeError):
    """Перегенерация запрещена: один из вариантов уже подтверждён. Роутер отвечает 409."""


class DraftPersistenceError(RuntimeError):
    """Вставка дала не 0 и не 3 строки: нарушен инвариант набора, транзакция откатывается."""


@dataclass(frozen=True, slots=True)
class StoredDraft:
    id: UUID
    review_id: UUID
    generation: int
    variant: DraftVariant
    content: str
    source: GenerationSource
    fallback_reason: str | None
    model: str | None
    status: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: Any) -> StoredDraft:
        return cls(
            id=row.id,
            review_id=row.review_id,
            generation=row.generation,
            variant=DraftVariant(row.variant),
            content=row.content,
            source=GenerationSource(row.source),
            fallback_reason=row.fallback_reason,
            model=row.model,
            status=row.status,
            created_at=row.created_at,
        )


@dataclass(frozen=True, slots=True)
class DraftSet:
    review_id: UUID
    drafts: tuple[StoredDraft, ...]
    created: bool  # False: набор уже существовал, LLM не вызывалась
    # True: сейчас стоят шаблоны из-за сбоя LLM; вызовите generate_for_review(..., regenerate=True) позже.
    regeneration_recommended: bool


class DraftService:
    def __init__(
        self, generator: AIResponseGenerator, session_scope: SessionScope
    ) -> None:
        self._generator = generator
        self._session_scope = session_scope

    @classmethod
    def from_groq(cls, session_scope: SessionScope) -> DraftService:
        settings = get_settings()
        if settings.groq_api_key is None:
            raise LLMPermanentError("GROQ_API_KEY is not configured")
        provider = build_provider(
            "groq",
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
        )
        return cls(AIResponseGenerator(provider), session_scope)

    async def generate_for_review(
        self, review_id: UUID, tenant: TenantContext, *, regenerate: bool = False
    ) -> DraftSet:
        """Идемпотентно создаёт набор из 3 черновиков для отзыва.

        Raises:
            ReviewNotFoundError: отзыва нет или он принадлежит другому тенанту.
            DraftsLockedError: regenerate=True, но вариант уже подтверждён.
            LLMPermanentError: ошибка конфигурации провайдера (ключ, модель): шаблоном не маскируется.
        """
        async with self._session_scope() as session:
            row = (
                await session.execute(_SELECT_REVIEW, {"review_id": review_id})
            ).one_or_none()
            if row is None:
                raise ReviewNotFoundError(str(review_id))
            snapshot = ReviewSnapshot(
                id=row.id,
                rating=int(row.rating),
                body=row.body or "",
                platform=row.platform,
                sentiment=row.sentiment,
                threat_level=row.threat_level,
            )
            existing = await self._load_active(session, review_id)

        if existing:
            if not regenerate:
                return self._as_set(review_id, existing, created=False)
            if any(d.status == STATUS_APPROVED for d in existing):
                raise DraftsLockedError(str(review_id))

        result = await self._generator.generate(snapshot, tenant)  # вне транзакции БД

        async with self._session_scope() as session:
            if regenerate:
                await session.execute(_SUPERSEDE, {"review_id": review_id})
            inserted = await self._insert(session, review_id, result)
            if len(inserted) == 0:
                # Параллельный воркер успел раньше: отдаём его набор, свой результат выбрасываем.
                active = await self._load_active(session, review_id)
                log.info("draft_set_exists", extra={"review_id": str(review_id)})
                return self._as_set(review_id, active, created=False)
            if len(inserted) != DRAFTS_PER_REVIEW:
                raise DraftPersistenceError(
                    f"вставлено {len(inserted)} из {DRAFTS_PER_REVIEW} вариантов"
                )

        log.info(
            "draft_set_saved",
            extra={
                "review_id": str(review_id),
                "generation": inserted[0].generation,
                **result.to_log(),
            },
        )
        return self._as_set(review_id, inserted, created=True)

    async def get_active(self, review_id: UUID) -> DraftSet | None:
        """Текущие варианты для UI (AntiCrisisRadar и список отзывов); None, если ещё не сгенерированы."""
        async with self._session_scope() as session:
            drafts = await self._load_active(session, review_id)
        return self._as_set(review_id, drafts, created=False) if drafts else None

    @staticmethod
    def tenant_context(company: Company) -> TenantContext:
        values: dict[str, str] = {"brand_name": company.name}
        if company.tone_of_voice is not None:
            values["tone_of_voice"] = company.tone_of_voice
        if company.compensation_policy is not None:
            values["compensation_policy"] = company.compensation_policy
        if company.support_channel is not None:
            values["support_channel"] = company.support_channel
        return TenantContext.model_validate(values)

    # ------------------------------------------------------------------ #
    @staticmethod
    async def _load_active(session: AsyncSession, review_id: UUID) -> list[StoredDraft]:
        rows = (await session.execute(_SELECT_ACTIVE, {"review_id": review_id})).all()
        return [StoredDraft.from_row(r) for r in rows]

    @staticmethod
    async def _insert(
        session: AsyncSession, review_id: UUID, result: GenerationResult
    ) -> list[StoredDraft]:
        rows = (
            await session.execute(
                _INSERT,
                {
                    "review_id": review_id,
                    "variants": [d.variant.value for d in result.drafts],
                    "contents": [d.text for d in result.drafts],
                    "source": result.source.value,
                    "fallback_reason": result.fallback_reason,
                    "model": result.model,
                    "prompt_version": result.prompt_version,
                },
            )
        ).all()
        return sorted(
            (StoredDraft.from_row(r) for r in rows),
            key=lambda d: list(DraftVariant).index(d.variant),
        )

    @staticmethod
    def _as_set(
        review_id: UUID, drafts: Sequence[StoredDraft], *, created: bool
    ) -> DraftSet:
        latest = max((d.generation for d in drafts), default=0)
        current = tuple(
            sorted(
                (d for d in drafts if d.generation == latest),
                key=lambda d: list(DraftVariant).index(d.variant),
            )
        )
        fallback = any(
            d.source is GenerationSource.FALLBACK
            and d.fallback_reason != "review_has_no_text"
            for d in current
        )
        return DraftSet(
            review_id=review_id,
            drafts=current,
            created=created,
            regeneration_recommended=fallback
            and all(d.status == STATUS_DRAFT for d in current),
        )
