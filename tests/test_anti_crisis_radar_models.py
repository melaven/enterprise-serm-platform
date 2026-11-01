from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.schemas.auth import JWTPayload
from app.core.database import Base
from app.core.tenant_session import tenant_session
from app.domain.reviews.risk import ResponseStrategyType, RiskLevel
from app.infrastructure.persistence.models import (
    AIResponseDraft,
    Company,
    OutboxEventType,
    Review,
)


@pytest.mark.asyncio
async def test_ai_response_draft_and_review_defaults_use_tenant_context() -> None:
    applied_settings: list[tuple[str, str, bool]] = []
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    def set_config(name: str, value: str, is_local: bool) -> str:
        applied_settings.append((name, value, is_local))
        return value

    @event.listens_for(engine.sync_engine, "connect")
    def register_set_config(connection, _record) -> None:
        connection.run_async(
            lambda raw_connection: raw_connection.create_function(
                "set_config", 3, set_config
            )
        )

    tenant_id = uuid4()
    user_id = uuid4()
    review_id = uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        payload = JWTPayload(sub=user_id, tenant_id=tenant_id)
        async with tenant_session(session_factory, payload) as session:
            session.add(
                Company(
                    id=tenant_id,
                    name="Test tenant",
                    average_check=0,
                    margin_percent=0,
                    cac=0,
                    base_ltv=0,
                )
            )
            session.add(
                Review(
                    id=review_id,
                    company_id=tenant_id,
                    author_name="Test reviewer",
                    rating=5,
                    text="Test review",
                )
            )
            draft = AIResponseDraft(
                tenant_id=tenant_id,
                review_id=review_id,
                strategy_type=ResponseStrategyType.APPEASEMENT,
                content="We are sorry about your experience.",
            )
            session.add(draft)
            await session.flush()

            review = await session.get(Review, review_id)
            assert review is not None
            assert review.risk_level is RiskLevel.SAFE
            assert draft.is_approved is False
            assert draft.created_at is not None
            assert draft.updated_at is not None
            assert draft.tenant_id == tenant_id
            assert draft.review_id == review_id

        assert [name for name, _, _ in applied_settings] == [
            "request.jwt.claims",
            "app.company_id",
            "app.user_id",
        ]
        assert all(is_local for _, _, is_local in applied_settings)
        assert applied_settings[1][1] == str(tenant_id)

        async with session_factory() as session:
            persisted_draft = await session.scalar(
                select(AIResponseDraft).where(AIResponseDraft.review_id == review_id)
            )
            assert persisted_draft is not None
            assert persisted_draft.strategy_type is ResponseStrategyType.APPEASEMENT
    finally:
        await engine.dispose()


def test_outbox_emergency_event_type_is_available() -> None:
    assert OutboxEventType.TRIGGER_EMERGENCY_ALERT.value == "trigger_emergency_alert"


def test_ai_response_draft_has_tenant_index_and_review_foreign_key() -> None:
    table = AIResponseDraft.__table__

    assert table.c.tenant_id.nullable is False
    assert table.c.review_id.nullable is False
    assert table.c.tenant_id.index is True
    assert table.c.review_id.index is True
    assert {
        foreign_key.target_fullname for foreign_key in table.c.review_id.foreign_keys
    } == {"reviews.id"}
