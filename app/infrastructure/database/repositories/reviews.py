"""Persistence for sanitized platform reviews."""

from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pii import PIISanitizer, redact_text
from app.infrastructure.database.models.review import Review
from app.infrastructure.integrations.review_platforms.base import SanitizedReview
from app.infrastructure.persistence.models.economics import Platform


class ReviewRepository:
    """Insert sanitized reviews without committing the caller's transaction."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save_reviews(
        self, company_id: UUID, reviews: list[SanitizedReview]
    ) -> int:
        """Insert reviews once per tenant/platform/external ID and return insert count."""
        if not reviews:
            return 0

        platform_ids: dict[str, UUID] = {}
        for platform_name in {review.platform for review in reviews}:
            platform_ids[platform_name] = await self._get_or_create_platform(
                company_id, platform_name
            )

        rows: list[dict[str, object]] = []
        for review in reviews:
            rows.append(
                await run_in_threadpool(
                    self._prepare_review_row,
                    company_id,
                    platform_ids[review.platform],
                    review,
                )
            )
        statement = (
            insert(Review)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=[
                    Review.company_id,
                    Review.platform,
                    Review.external_id,
                ]
            )
            .returning(Review.id)
        )
        result = await self.db.execute(statement)
        return len(result.scalars().all())

    @staticmethod
    def _prepare_review_row(
        company_id: UUID, platform_id: UUID, review: SanitizedReview
    ) -> dict[str, object]:
        return {
            "company_id": company_id,
            "platform_id": platform_id,
            "external_id": PIISanitizer.hash_user_id(
                review.platform, review.external_id
            ),
            "platform": review.platform,
            "author_hash": (
                PIISanitizer.hash_user_id(review.platform, review.author_hash)
                if review.author_hash
                else None
            ),
            "author_display": (
                "Анонимный клиент"
                if review.author_display == "Анонимный клиент"
                else "Клиент"
            ),
            "author_name": "Автор отзыва",
            "text": redact_text(review.text),
            "rating": int(review.rating),
            "published_at": review.published_at,
        }

    async def _get_or_create_platform(
        self, company_id: UUID, platform_name: str
    ) -> UUID:
        statement = (
            insert(Platform)
            .values(company_id=company_id, name=platform_name)
            .on_conflict_do_nothing(index_elements=[Platform.company_id, Platform.name])
            .returning(Platform.id)
        )
        result = await self.db.execute(statement)
        platform_id = result.scalar_one_or_none()
        if platform_id is not None:
            return platform_id

        result = await self.db.execute(
            select(Platform.id).where(
                Platform.company_id == company_id,
                Platform.name == platform_name,
            )
        )
        platform_id = result.scalar_one_or_none()
        if platform_id is None:
            raise RuntimeError("Platform could not be created or retrieved")
        return platform_id
