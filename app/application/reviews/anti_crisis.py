from datetime import datetime, timezone
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.anti_crisis import (
    ApproveDraftResponse,
    CrisisDraftInput,
    CrisisEscalationResponse,
    DraftResponse,
)
from app.api.schemas.economics import ReplyModerationStatus
from app.core.exceptions import NotFoundError, SERMException
from app.core.tenant_session import RLS_CONTEXT_INFO_KEY, set_tenant_rls_context
from app.domain.reviews.risk import ResponseStrategyType, RiskLevel
from app.infrastructure.persistence.models.ai_response_draft import AIResponseDraft
from app.infrastructure.persistence.models.economics import Review
from app.infrastructure.persistence.models.outbox_event import (
    OutboxEvent,
    OutboxEventType,
)
from app.infrastructure.persistence.models.review_reply import ReviewReply


class AntiCrisisService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def escalate_crisis(
        self,
        tenant_id: UUID,
        review_id: UUID,
        risk_level: RiskLevel,
        drafts: list[CrisisDraftInput],
        risk_signals: list[str],
        risk_metadata: dict[str, str | int | float | bool | None],
    ) -> CrisisEscalationResponse:
        if risk_level is not RiskLevel.CRITICAL_RISK:
            raise SERMException(
                "Crisis escalation requires critical_risk",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        self._validate_strategy_set(drafts)
        await self._ensure_tenant_context(tenant_id)

        idempotency_key = f"emergency-alert:{tenant_id}:{review_id}"
        async with self.session.begin():
            review = await self._lock_review(tenant_id, review_id)
            review.risk_level = risk_level

            existing_drafts = list(
                (
                    await self.session.scalars(
                        select(AIResponseDraft)
                        .where(
                            AIResponseDraft.tenant_id == tenant_id,
                            AIResponseDraft.review_id == review_id,
                        )
                        .with_for_update()
                    )
                ).all()
            )
            by_strategy = {draft.strategy_type: draft for draft in existing_drafts}
            for draft_input in drafts:
                draft = by_strategy.get(draft_input.strategy_type)
                if draft is None:
                    draft = AIResponseDraft(
                        tenant_id=tenant_id,
                        review_id=review_id,
                        strategy_type=draft_input.strategy_type,
                        content=draft_input.content,
                    )
                    self.session.add(draft)
                    by_strategy[draft_input.strategy_type] = draft
                elif not draft.is_approved:
                    draft.content = draft_input.content

            await self.session.flush()
            for draft in by_strategy.values():
                await self.session.refresh(draft)
            draft_ids = [
                str(by_strategy[strategy].id) for strategy in ResponseStrategyType
            ]

            event = await self.session.scalar(
                select(OutboxEvent)
                .where(OutboxEvent.idempotency_key == idempotency_key)
                .with_for_update()
            )
            if event is None:
                event = OutboxEvent(
                    event_type=OutboxEventType.TRIGGER_EMERGENCY_ALERT,
                    idempotency_key=idempotency_key,
                    payload={
                        "tenant_id": str(tenant_id),
                        "review_id": str(review_id),
                        "draft_ids": draft_ids,
                        "risk_level": risk_level.value,
                        "risk_signals": risk_signals,
                        "risk_metadata": risk_metadata,
                        "idempotency_key": idempotency_key,
                    },
                )
                self.session.add(event)
                await self.session.flush()

            response_drafts = [
                self._draft_response(by_strategy[strategy])
                for strategy in ResponseStrategyType
            ]
            return CrisisEscalationResponse(
                risk_level=risk_level,
                drafts=response_drafts,
                outbox_event_id=event.id,
                idempotency_key=idempotency_key,
            )

    async def list_drafts(
        self, tenant_id: UUID, review_id: UUID
    ) -> list[DraftResponse]:
        await self._ensure_tenant_context(tenant_id)
        review = await self.session.scalar(
            select(Review.id).where(
                Review.id == review_id,
                Review.company_id == tenant_id,
            )
        )
        if review is None:
            raise NotFoundError("Review", str(review_id))

        drafts = await self.session.scalars(
            select(AIResponseDraft)
            .where(
                AIResponseDraft.tenant_id == tenant_id,
                AIResponseDraft.review_id == review_id,
            )
            .order_by(AIResponseDraft.created_at, AIResponseDraft.id)
        )
        return [self._draft_response(draft) for draft in drafts.all()]

    async def approve_draft(
        self,
        tenant_id: UUID,
        review_id: UUID,
        draft_id: UUID,
        edited_text: str,
        approved_by: str,
    ) -> ApproveDraftResponse:
        normalized_text = edited_text.strip()
        if not normalized_text or len(normalized_text) > 4000:
            raise SERMException(
                "Edited response must contain 1 to 4000 characters",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        await self._ensure_tenant_context(tenant_id)

        async with self.session.begin():
            review = await self._lock_review(tenant_id, review_id)
            drafts = list(
                (
                    await self.session.scalars(
                        select(AIResponseDraft)
                        .where(
                            AIResponseDraft.tenant_id == tenant_id,
                            AIResponseDraft.review_id == review_id,
                        )
                        .with_for_update()
                    )
                ).all()
            )
            draft = next((item for item in drafts if item.id == draft_id), None)
            if draft is None:
                raise NotFoundError("AI response draft", str(draft_id))

            if draft.is_approved:
                response_draft = self._draft_response(draft)
                return ApproveDraftResponse(
                    draft=response_draft,
                    idempotent=True,
                    approved_by=response_draft.approved_by,
                    approved_at=response_draft.approved_at,
                )

            approved_other = next(
                (item for item in drafts if item.is_approved and item.id != draft_id),
                None,
            )
            if approved_other is not None:
                raise SERMException(
                    "Another response draft for this review has already been approved",
                    status.HTTP_409_CONFLICT,
                    details=self._approval_details(approved_other),
                )

            existing_reply = await self.session.get(ReviewReply, review_id)
            if existing_reply is not None:
                raise SERMException(
                    "A reply for this review already exists",
                    status.HTTP_409_CONFLICT,
                )

            draft.content = normalized_text
            draft.is_approved = True
            draft.approved_by = approved_by
            draft.approved_at = datetime.now(timezone.utc)
            review.moderation_status = ReplyModerationStatus.APPROVED
            self.session.add(
                ReviewReply(
                    review_id=review_id,
                    company_id=tenant_id,
                    reply_text=normalized_text,
                )
            )
            idempotency_key = f"publish-review-reply:{tenant_id}:{review_id}"
            self.session.add(
                OutboxEvent(
                    event_type=OutboxEventType.PUBLISH_REVIEW_REPLY,
                    idempotency_key=idempotency_key,
                    payload={
                        "tenant_id": str(tenant_id),
                        "review_id": str(review_id),
                        "draft_id": str(draft_id),
                        "reply_text": normalized_text,
                        "idempotency_key": idempotency_key,
                    },
                )
            )
            await self.session.flush()
            await self.session.refresh(draft)
            response_draft = self._draft_response(draft)
            return ApproveDraftResponse(
                draft=response_draft,
                idempotent=False,
                approved_by=response_draft.approved_by,
                approved_at=response_draft.approved_at,
            )

    async def _lock_review(self, tenant_id: UUID, review_id: UUID) -> Review:
        review = await self.session.scalar(
            select(Review)
            .where(
                Review.id == review_id,
                Review.company_id == tenant_id,
            )
            .with_for_update()
        )
        if review is None:
            raise NotFoundError("Review", str(review_id))
        return review

    async def _ensure_tenant_context(self, tenant_id: UUID) -> None:
        context = self.session.sync_session.info.get(RLS_CONTEXT_INFO_KEY)
        if context is not None:
            if context["company_id"] != str(tenant_id):
                raise SERMException(
                    "Tenant context does not match the requested tenant",
                    status.HTTP_403_FORBIDDEN,
                )
            return
        await set_tenant_rls_context(self.session, tenant_id)

    @staticmethod
    def _validate_strategy_set(drafts: list[CrisisDraftInput]) -> None:
        strategies = [draft.strategy_type for draft in drafts]
        if set(strategies) != set(ResponseStrategyType) or len(strategies) != len(
            set(strategies)
        ):
            raise SERMException(
                "Exactly one draft for each response strategy is required",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    @staticmethod
    def _draft_response(draft: AIResponseDraft) -> DraftResponse:
        approved_at = draft.approved_at
        if approved_at is not None and approved_at.tzinfo is None:
            approved_at = approved_at.replace(tzinfo=timezone.utc)
        return DraftResponse(
            id=draft.id,
            strategy=draft.strategy_type,
            body=draft.content,
            is_approved=draft.is_approved,
            approved_by=draft.approved_by,
            approved_at=approved_at,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )

    @staticmethod
    def _approval_details(draft: AIResponseDraft) -> dict[str, str | None]:
        approved_at = draft.approved_at
        if approved_at is not None and approved_at.tzinfo is None:
            approved_at = approved_at.replace(tzinfo=timezone.utc)
        return {
            "approved_draft_id": str(draft.id),
            "approved_by": draft.approved_by,
            "approved_at": approved_at.isoformat() if approved_at is not None else None,
        }
