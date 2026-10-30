"""PostgreSQL batch upserts for sanitized reviews."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.economics import Platform

_UPSERT_REVIEWS = text(
    """
    INSERT INTO public.reviews (
        company_id,
        platform_id,
        external_id,
        platform,
        author_hash,
        author_display,
        author_name,
        text,
        rating,
        published_at
    )
    SELECT
        incoming.company_id,
        platforms.id,
        incoming.external_id,
        incoming.platform,
        incoming.author_hash,
        incoming.author_display,
        'Автор отзыва',
        incoming.clean_text,
        incoming.rating,
        incoming.published_at
    FROM UNNEST(
        CAST(:company_ids AS uuid[]),
        CAST(:platforms AS text[]),
        CAST(:external_ids AS text[]),
        CAST(:author_hashes AS text[]),
        CAST(:author_displays AS text[]),
        CAST(:clean_texts AS text[]),
        CAST(:ratings AS smallint[]),
        CAST(:published_ats AS timestamptz[])
    ) AS incoming(
        company_id,
        platform,
        external_id,
        author_hash,
        author_display,
        clean_text,
        rating,
        published_at
    )
    JOIN public.platforms AS platforms
      ON platforms.company_id = incoming.company_id
     AND platforms.name = incoming.platform
    ON CONFLICT (company_id, platform, external_id)
    DO UPDATE SET
        text = EXCLUDED.text,
        rating = EXCLUDED.rating,
        author_display = EXCLUDED.author_display,
        updated_at = NOW()
    RETURNING id
    """
)


class BulkReviewRepository:
    """Persist sanitized review batches with one PostgreSQL upsert statement."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_upsert_reviews(self, batch: list[dict[str, object]]) -> int:
        """Insert or update a batch and return the number of affected review rows."""
        if not batch:
            return 0

        company_ids = [self._as_uuid(row, "tenant_id") for row in batch]
        platforms = [self._as_string(row, "platform") for row in batch]

        unique_platforms = {
            (company_id, platform)
            for company_id, platform in zip(company_ids, platforms, strict=True)
        }
        platform_statement = (
            insert(Platform)
            .values(
                [
                    {"company_id": company_id, "name": platform}
                    for company_id, platform in unique_platforms
                ]
            )
            .on_conflict_do_nothing(index_elements=[Platform.company_id, Platform.name])
        )
        await self.session.execute(platform_statement)

        result = await self.session.execute(
            _UPSERT_REVIEWS,
            {
                "company_ids": company_ids,
                "platforms": platforms,
                "external_ids": [self._as_string(row, "external_id") for row in batch],
                "author_hashes": [
                    self._as_optional_string(row, "author_hash") for row in batch
                ],
                "author_displays": [
                    self._as_string(row, "author_display") for row in batch
                ],
                "clean_texts": [self._as_string(row, "clean_text") for row in batch],
                "ratings": [self._as_int(row, "rating") for row in batch],
                "published_ats": [
                    self._as_datetime(row, "published_at") for row in batch
                ],
            },
        )
        return len(result.fetchall())

    @staticmethod
    def _as_uuid(row: dict[str, object], key: str) -> UUID:
        value = row.get(key)
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            return UUID(value)
        raise ValueError(f"{key} must be a UUID")

    @staticmethod
    def _as_string(row: dict[str, object], key: str) -> str:
        value = row.get(key)
        if isinstance(value, str):
            return value
        raise ValueError(f"{key} must be a string")

    @staticmethod
    def _as_optional_string(row: dict[str, object], key: str) -> str | None:
        value = row.get(key)
        if value is None or isinstance(value, str):
            return value
        raise ValueError(f"{key} must be a string or None")

    @staticmethod
    def _as_int(row: dict[str, object], key: str) -> int:
        value = row.get(key)
        if isinstance(value, int):
            return value
        raise ValueError(f"{key} must be an integer")

    @staticmethod
    def _as_datetime(row: dict[str, object], key: str) -> datetime:
        value = row.get(key)
        if isinstance(value, datetime):
            return value
        raise ValueError(f"{key} must be a datetime")
