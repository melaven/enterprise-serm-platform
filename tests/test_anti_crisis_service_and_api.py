from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import Depends, Header
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.schemas.anti_crisis import CrisisDraftInput
from app.api.schemas.auth import JWTPayload
from app.api.schemas.economics import ReplyModerationStatus
from app.application.reviews.anti_crisis import AntiCrisisService
from app.core.auth import get_current_tenant, get_jwt_payload
from app.core.database import Base
from app.core.dependencies import get_tenant_db
from app.core.exceptions import SERMException
from app.core.tenant_session import set_rls_context, set_tenant_rls_context
from app.domain.reviews.risk import ResponseStrategyType, RiskLevel
from app.infrastructure.persistence.models.ai_response_draft import AIResponseDraft
from app.infrastructure.persistence.models.economics import Company, Review
from app.infrastructure.persistence.models.outbox_event import (
    OutboxEvent,
    OutboxEventType,
)
from app.infrastructure.persistence.models.review_reply import ReviewReply
from app.main import app

STRATEGY_CONTENT = {
    ResponseStrategyType.LEGAL_STRICT: "Legal response draft",
    ResponseStrategyType.APPEASEMENT: "Apology response draft",
    ResponseStrategyType.INFO_REQUEST: "Information request draft",
}


def _crisis_drafts() -> list[CrisisDraftInput]:
    return [
        CrisisDraftInput(strategy_type=strategy, content=content)
        for strategy, content in STRATEGY_CONTENT.items()
    ]


def _register_set_config(engine) -> None:
    def set_config(name: str, value: str, is_local: bool) -> str:
        return value

    @event.listens_for(engine.sync_engine, "connect")
    def register_set_config(connection, _record) -> None:
        connection.run_async(
            lambda raw_connection: raw_connection.create_function(
                "set_config", 3, set_config
            )
        )


@pytest.fixture
def anti_crisis_database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _register_set_config(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close() -> None:
        await engine.dispose()

    return engine, factory, create_schema, close


async def _create_review(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    review_id: UUID | None = None,
) -> UUID:
    review_uuid = review_id or uuid4()
    async with factory.begin() as session:
        session.add(
            Company(
                id=tenant_id,
                name="Test company",
                average_check=0,
                margin_percent=0,
                cac=0,
                base_ltv=0,
            )
        )
        await session.flush()
        session.add(
            Review(
                id=review_uuid,
                company_id=tenant_id,
                author_name="Test reviewer",
                rating=1,
                text="Critical review",
            )
        )
    return review_uuid


@pytest.mark.asyncio
async def test_crisis_escalation_commits_risk_drafts_and_outbox_atomically(
    anti_crisis_database,
) -> None:
    _, factory, create_schema, close = anti_crisis_database
    await create_schema()
    tenant_id = uuid4()
    review_id = await _create_review(factory, tenant_id)

    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        result = await AntiCrisisService(session).escalate_crisis(
            tenant_id=tenant_id,
            review_id=review_id,
            risk_level=RiskLevel.CRITICAL_RISK,
            drafts=_crisis_drafts(),
            risk_signals=["lawsuit", "personal data"],
            risk_metadata={"source": "radar", "confidence": 0.98},
        )

    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        retried_result = await AntiCrisisService(session).escalate_crisis(
            tenant_id=tenant_id,
            review_id=review_id,
            risk_level=RiskLevel.CRITICAL_RISK,
            drafts=_crisis_drafts(),
            risk_signals=["lawsuit", "personal data"],
            risk_metadata={"source": "radar", "confidence": 0.98},
        )

    async with factory() as session:
        review = await session.get(Review, review_id)
        drafts = list(
            (
                await session.scalars(
                    select(AIResponseDraft).where(
                        AIResponseDraft.tenant_id == tenant_id,
                        AIResponseDraft.review_id == review_id,
                    )
                )
            ).all()
        )
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent).where(
                        OutboxEvent.idempotency_key
                        == f"emergency-alert:{tenant_id}:{review_id}"
                    )
                )
            ).all()
        )

    assert review is not None
    assert review.risk_level is RiskLevel.CRITICAL_RISK
    assert len(drafts) == 3
    assert len(events) == 1
    assert events[0].event_type is OutboxEventType.TRIGGER_EMERGENCY_ALERT
    assert set(events[0].payload["draft_ids"]) == {str(draft.id) for draft in drafts}
    assert result.outbox_event_id == events[0].id
    assert result.idempotency_key == events[0].idempotency_key
    assert {draft.id for draft in result.drafts} == {
        draft.id for draft in retried_result.drafts
    }
    await close()


@pytest.mark.asyncio
async def test_approval_edits_reply_and_is_idempotent_for_same_draft(
    anti_crisis_database,
) -> None:
    _, factory, create_schema, close = anti_crisis_database
    await create_schema()
    tenant_id = uuid4()
    review_id = await _create_review(factory, tenant_id)
    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        escalation = await AntiCrisisService(session).escalate_crisis(
            tenant_id,
            review_id,
            RiskLevel.CRITICAL_RISK,
            _crisis_drafts(),
            [],
            {},
        )
    selected = next(
        draft
        for draft in escalation.drafts
        if draft.strategy is ResponseStrategyType.LEGAL_STRICT
    )

    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        service = AntiCrisisService(session)
        first_result = await service.approve_draft(
            tenant_id,
            review_id,
            selected.id,
            "  Manager-edited response  ",
        )

    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        second_result = await AntiCrisisService(session).approve_draft(
            tenant_id,
            review_id,
            selected.id,
            "Different text from a retry",
        )

    async with factory() as session:
        draft = await session.get(AIResponseDraft, selected.id)
        reply = await session.get(ReviewReply, review_id)
        review = await session.get(Review, review_id)
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent).where(
                        OutboxEvent.idempotency_key
                        == f"publish-review-reply:{tenant_id}:{review_id}"
                    )
                )
            ).all()
        )

    assert first_result.idempotent is False
    assert first_result.draft.body == "Manager-edited response"
    assert second_result.idempotent is True
    assert second_result.draft.body == "Manager-edited response"
    assert draft is not None and draft.is_approved
    assert reply is not None and reply.reply_text == "Manager-edited response"
    assert review is not None
    assert review.moderation_status is ReplyModerationStatus.APPROVED
    assert len(events) == 1
    assert events[0].event_type is OutboxEventType.PUBLISH_REVIEW_REPLY
    await close()


@pytest.mark.asyncio
async def test_approval_conflicts_when_another_draft_was_approved(
    anti_crisis_database,
) -> None:
    _, factory, create_schema, close = anti_crisis_database
    await create_schema()
    tenant_id = uuid4()
    review_id = await _create_review(factory, tenant_id)
    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        escalation = await AntiCrisisService(session).escalate_crisis(
            tenant_id,
            review_id,
            RiskLevel.CRITICAL_RISK,
            _crisis_drafts(),
            [],
            {},
        )

    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        service = AntiCrisisService(session)
        await service.approve_draft(
            tenant_id,
            review_id,
            escalation.drafts[0].id,
            "First approved response",
        )

    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        with pytest.raises(SERMException) as error:
            await AntiCrisisService(session).approve_draft(
                tenant_id,
                review_id,
                escalation.drafts[1].id,
                "Another response",
            )

    assert getattr(error.value, "status_code", None) == 409
    await close()


@pytest.mark.asyncio
async def test_approval_cannot_access_another_tenants_draft(
    anti_crisis_database,
) -> None:
    _, factory, create_schema, close = anti_crisis_database
    await create_schema()
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    review_id = await _create_review(factory, tenant_id)
    await _create_review(factory, other_tenant_id)
    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        escalation = await AntiCrisisService(session).escalate_crisis(
            tenant_id,
            review_id,
            RiskLevel.CRITICAL_RISK,
            _crisis_drafts(),
            [],
            {},
        )

    async with factory() as session:
        await set_tenant_rls_context(session, other_tenant_id)
        with pytest.raises(SERMException) as error:
            await AntiCrisisService(session).approve_draft(
                other_tenant_id,
                review_id,
                escalation.drafts[0].id,
                "Attempted cross-tenant response",
            )

    assert getattr(error.value, "status_code", None) == 404
    await close()


@pytest.mark.asyncio
async def test_api_lists_drafts_and_rejects_non_admin_approval(
    anti_crisis_database,
    rate_limit_pool,
) -> None:
    _, factory, create_schema, close = anti_crisis_database
    await create_schema()
    tenant_id = uuid4()
    review_id = await _create_review(factory, tenant_id)
    async with factory() as session:
        await set_tenant_rls_context(session, tenant_id)
        escalation = await AntiCrisisService(session).escalate_crisis(
            tenant_id,
            review_id,
            RiskLevel.CRITICAL_RISK,
            _crisis_drafts(),
            [],
            {},
        )

    async def payload_from_headers(
        x_test_tenant: UUID = Header(),
        x_test_role: str = Header(default="member"),
    ) -> JWTPayload:
        return JWTPayload(
            sub=x_test_tenant,
            tenant_id=x_test_tenant,
            company_role=x_test_role,
        )

    async def tenant_from_headers(
        x_test_tenant: UUID = Header(alias="X-Test-Tenant"),
    ) -> UUID:
        return x_test_tenant

    async def database_session(
        payload: JWTPayload = Depends(get_jwt_payload),
    ) -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            await set_rls_context(session, payload)
            try:
                yield session
                if session.new or session.dirty or session.deleted:
                    await session.commit()
            except Exception:
                await session.rollback()
                raise

    previous_payload = app.dependency_overrides.get(get_jwt_payload)
    previous_tenant = app.dependency_overrides.get(get_current_tenant)
    previous_database = app.dependency_overrides.get(get_tenant_db)
    previous_redis_pool = app.state.redis_pool
    app.dependency_overrides[get_jwt_payload] = payload_from_headers
    app.dependency_overrides[get_current_tenant] = tenant_from_headers
    app.dependency_overrides[get_tenant_db] = database_session
    app.state.redis_pool = rate_limit_pool

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            headers = {"x-test-tenant": str(tenant_id)}
            listing = await client.get(
                f"/api/v1/reviews/{review_id}/drafts",
                headers=headers,
            )
            denied = await client.post(
                f"/api/v1/reviews/{review_id}/drafts/{escalation.drafts[0].id}/approve",
                headers=headers,
                json={"edited_text": "Member is not allowed"},
            )
            admin_headers = {**headers, "x-test-role": "admin"}
            approved = await client.post(
                f"/api/v1/reviews/{review_id}/drafts/{escalation.drafts[0].id}/approve",
                headers=admin_headers,
                json={"edited_text": "Manager approved response"},
            )
            retried = await client.post(
                f"/api/v1/reviews/{review_id}/drafts/{escalation.drafts[0].id}/approve",
                headers=admin_headers,
                json={"edited_text": "Changed text on retry"},
            )
            assert listing.status_code == 200, listing.text
            assert len(listing.json()) == 3
            assert listing.json()[0]["strategy"] in {
                strategy.name for strategy in ResponseStrategyType
            }
            assert "body" in listing.json()[0]
            assert denied.status_code == 403
            assert approved.status_code == 200, approved.text
            assert approved.json()["draft"]["body"] == "Manager approved response"
            assert approved.json()["idempotent"] is False
            assert approved.json()["publication_status"] == "outbox_pending"
            assert retried.status_code == 200
            assert retried.json()["idempotent"] is True
    finally:
        if previous_payload is None:
            app.dependency_overrides.pop(get_jwt_payload, None)
        else:
            app.dependency_overrides[get_jwt_payload] = previous_payload
        if previous_database is None:
            app.dependency_overrides.pop(get_tenant_db, None)
        else:
            app.dependency_overrides[get_tenant_db] = previous_database
        if previous_tenant is None:
            app.dependency_overrides.pop(get_current_tenant, None)
        else:
            app.dependency_overrides[get_current_tenant] = previous_tenant
        app.state.redis_pool = previous_redis_pool
        await close()
