from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review  # подставь свою модель


class ReviewRepository:
    """Фильтр по company_id намеренно отсутствует: изоляцию делает RLS."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_many(self, *, limit: int, offset: int) -> Sequence[Review]:
        stmt = (
            select(Review)
            .order_by(Review.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return (await self._session.scalars(stmt)).all()

    async def get(self, review_id: UUID) -> Review | None:
        # Чужая строка скрыта RLS -> None -> 404, без утечки факта существования.
        return await self._session.get(Review, review_id)

    async def add_many_ignore_duplicates(
        self, rows: Sequence[Mapping[str, Any]]
    ) -> int:
        """Идемпотентная пакетная вставка: повтор задачи не плодит дубли.

        Нужен уникальный индекс (company_id, platform, external_id), см.
        sql/004_reviews_dedup.sql. company_id не передаём: его проставит
        DEFAULT app.current_company_id(), а WITH CHECK не даст подменить.
        """
        if not rows:
            return 0
        stmt = (
            pg_insert(Review)
            .values(list(rows))
            .on_conflict_do_nothing(
                index_elements=["company_id", "platform", "external_id"]
            )
            .returning(Review.id)
        )
        result = await self._session.execute(stmt)
        return len(result.all())

    async def add(self, review: Review) -> Review:
        # company_id: DEFAULT app.current_company_id(); WITH CHECK не даст подменить.
        self._session.add(review)
        await self._session.flush()
        return review
