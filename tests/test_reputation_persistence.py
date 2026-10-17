from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers

from app.models.economics import PlatformStatistic, Review
from app.repositories.postgres_review_sink import PostgresReviewSink
from app.repositories.review import ReviewRepository
from app.schemas.economics import ReviewStatus
from app.schemas.parser import Platform as ReviewPlatform


class _InsertResult:
    def __init__(self, values: list[UUID]) -> None:
        self._values = values

    def scalar_one_or_none(self) -> UUID | None:
        return self._values[0] if self._values else None

    def scalars(self) -> _InsertResult:
        return self

    def all(self) -> list[UUID]:
        return self._values


class _Session:
    def __init__(self) -> None:
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        # Advisory lock statement (first call after entering save_many)
        if len(self.statements) == 1:
            # Advisory lock doesn't return results
            return _InsertResult([])
        # Platform insert/select (second call)
        if len(self.statements) == 2:
            return _InsertResult([uuid4()])
        # Review insert (third call)
        return _InsertResult([uuid4()])


class _TenantFactory:
    def __init__(self, session: _Session) -> None:
        self.session = session
        self.tenant_id: UUID | None = None

    @asynccontextmanager
    async def __call__(self, tenant_id: UUID) -> AsyncIterator[_Session]:
        self.tenant_id = tenant_id
        yield self.session


def _analyzed_review() -> SimpleNamespace:
    raw = SimpleNamespace(
        platform_id="source-review-1",
        author_name="Reviewer",
        text="Good service",
        rating=4,
        date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        platform=ReviewPlatform.TWOGIS,
    )
    result = SimpleNamespace(
        sentiment=SimpleNamespace(value="POSITIVE"),
        issue_category=SimpleNamespace(value="SERVICE"),
        extracted_entities=["staff"],
        is_critical=False,
        suggested_reply="Thank you",
    )
    return SimpleNamespace(
        raw=raw,
        analysis=SimpleNamespace(result=result, is_fallback=False),
    )


def test_reputation_models_bind_rows_to_tenant_and_configure_relationships() -> None:
    configure_mappers()

    assert Review.__table__.c.company_id.nullable is False
    assert Review.tenant_id.property.columns[0].name == "company_id"
    assert PlatformStatistic.__table__.c.company_id.nullable is False
    assert PlatformStatistic.tenant_id.property.columns[0].name == "company_id"
    assert any(
        constraint.name == "fk_platform_statistics_platform_tenant"
        for constraint in PlatformStatistic.__table__.foreign_key_constraints
    )
    assert any(
        constraint.name == "ck_reviews_rating_range"
        for constraint in Review.__table__.constraints
    )


def test_sink_inserts_reviews_with_explicit_tenant_and_idempotency() -> None:
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    session = _Session()

    inserted = asyncio.run(
        PostgresReviewSink().save_many(session, tenant_id, [_analyzed_review()])
    )

    assert inserted == 1
    # Advisory lock is statement[0], platform is statement[1], review insert is statement[2]
    compiled = session.statements[2].compile(dialect=postgresql.dialect())
    assert "ON CONFLICT" in str(compiled)
    assert compiled.params["company_id_m0"] == tenant_id
    assert compiled.params["status_m0"] == ReviewStatus.NEW.value
    assert compiled.params["sentiment_m0"] == "POSITIVE"


def test_sink_worker_entry_point_uses_tenant_session() -> None:
    tenant_id = uuid4()
    factory = _TenantFactory(_Session())

    inserted = asyncio.run(
        PostgresReviewSink(factory).save(tenant_id, [_analyzed_review()])  # type: ignore[arg-type]
    )

    assert inserted == 1
    assert factory.tenant_id == tenant_id


def test_review_crud_rejects_cross_tenant_assignment_before_database_write() -> None:
    repository = ReviewRepository(None)  # type: ignore[arg-type]

    async def create_cross_tenant() -> None:
        await repository.create_for_tenant(
            uuid4(),
            company_id=uuid4(),
            platform_id=uuid4(),
            text="Review",
            rating=4,
        )

    with pytest.raises(ValueError, match="tenant"):
        asyncio.run(create_cross_tenant())
