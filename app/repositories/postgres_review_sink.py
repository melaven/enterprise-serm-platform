"""Tenant-scoped PostgreSQL persistence for parsed and analyzed reviews."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantSessionFactory
from app.models.economics import Platform, Review
from app.schemas.economics import ReviewStatus


class _EnumValue(Protocol):
    value: str


class _RawReview(Protocol):
    platform_id: str
    author_name: str
    text: str
    rating: float
    date: datetime
    platform: _EnumValue


class _AnalysisResult(Protocol):
    sentiment: _EnumValue
    issue_category: _EnumValue
    extracted_entities: list[str]
    is_critical: bool
    suggested_reply: str


class _AnalysisOutcome(Protocol):
    result: _AnalysisResult
    is_fallback: bool


class _AnalyzedReview(Protocol):
    raw: _RawReview
    analysis: _AnalysisOutcome


class PostgresReviewSink:
    """Persist reviews without committing outside the tenant transaction."""

    def __init__(self, session_factory: TenantSessionFactory | None = None) -> None:
        self._session_factory = (
            session_factory if session_factory is not None else TenantSessionFactory()
        )

    async def save(self, tenant_id: UUID, reviews: Sequence[_AnalyzedReview]) -> int:
        """Worker entry point; opens a session with RLS set to ``tenant_id``."""
        async with self._session_factory(tenant_id) as db:
            return await self.save_many(db, tenant_id, reviews)

    async def save_many(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        reviews: Sequence[_AnalyzedReview],
        platform_id: UUID | None = None,
    ) -> int:
        """Insert a batch idempotently and return only rows inserted by this call.

        SECURITY FIX: Advisory lock prevents race conditions when multiple workers
        process reviews for the same tenant simultaneously.
        """
        if not reviews:
            return 0

        # ✅ CRITICAL FIX: Advisory lock for tenant isolation during concurrent writes
        # Prevents race conditions: two workers inserting same review → IntegrityError
        lock_key = int(
            tenant_id.int % (2**31)
        )  # PostgreSQL advisory lock requires int32
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)").bindparams(
                lock_key=lock_key
            )
        )

        platform_names = {str(review.raw.platform.value) for review in reviews}
        if len(platform_names) != 1:
            raise ValueError("A review batch must contain exactly one platform")
        platform_name = platform_names.pop()

        if platform_id is None:
            platform_id = await self._get_or_create_platform(
                db, tenant_id, platform_name
            )
        else:
            result = await db.execute(
                select(Platform.id, Platform.name).where(
                    Platform.id == platform_id,
                    Platform.company_id == tenant_id,
                )
            )
            owned_platform = result.one_or_none()
            if owned_platform is None or owned_platform.name != platform_name:
                raise ValueError("Platform does not belong to the requested tenant")

        rows = [
            {
                "company_id": tenant_id,
                "platform_id": platform_id,
                "external_review_id": review.raw.platform_id,
                "platform": platform_name,
                "author_name": review.raw.author_name,
                "rating": int(review.raw.rating),
                "text": review.raw.text,
                "status": ReviewStatus.NEW.value,
                "financial_impact": 0.0,
                "created_at": review.raw.date,
                "sentiment": review.analysis.result.sentiment.value,
                "tags": [
                    review.analysis.result.issue_category.value,
                    *review.analysis.result.extracted_entities,
                ],
                "is_critical": review.analysis.result.is_critical,
                "auto_reply": review.analysis.result.suggested_reply,
                "ai_pending": review.analysis.is_fallback,
            }
            for review in reviews
        ]

        stmt = (
            insert(Review)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=[
                    Review.company_id,
                    Review.platform,
                    Review.external_review_id,
                ]
            )
            .returning(Review.id)
        )
        result = await db.execute(stmt)
        return len(result.scalars().all())

    async def _get_or_create_platform(
        self, db: AsyncSession, tenant_id: UUID, platform_name: str
    ) -> UUID:
        stmt = (
            insert(Platform)
            .values(
                company_id=tenant_id,
                name=platform_name,
                monthly_views=0,
                conversion_rate=0.0,
                cac_on_platform=0.0,
                average_rating=0.0,
            )
            .on_conflict_do_nothing(index_elements=[Platform.company_id, Platform.name])
            .returning(Platform.id)
        )
        result = await db.execute(stmt)
        platform_id = result.scalar_one_or_none()
        if platform_id is not None:
            return platform_id

        result = await db.execute(
            select(Platform.id).where(
                Platform.company_id == tenant_id,
                Platform.name == platform_name,
            )
        )
        platform_id = result.scalar_one_or_none()
        if platform_id is None:
            raise RuntimeError("Tenant platform could not be created or retrieved")
        return platform_id

    async def existing_external_ids(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        platform: str,
        ids: list[str],
    ) -> set[str]:
        """Return known source IDs only within the requested tenant and platform."""
        if not ids:
            return set()

        stmt = select(Review.external_review_id).where(
            Review.company_id == tenant_id,
            Review.platform == platform,
            Review.external_review_id.in_(ids),
        )
        result = await db.execute(stmt)
        return {
            external_id
            for external_id in result.scalars().all()
            if external_id is not None
        }
