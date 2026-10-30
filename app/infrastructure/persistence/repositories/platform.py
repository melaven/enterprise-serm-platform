"""
Репозиторий для работы с платформами
"""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DatabaseError
from app.infrastructure.persistence.models.economics import Platform
from app.infrastructure.persistence.repositories.base import BaseRepository


class PlatformRepository(BaseRepository[Platform]):
    """Репозиторий для управления данными платформ"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Platform)

    async def get_by_company_id(self, company_id: UUID) -> list[Platform]:
        """Получить все платформы компании"""
        try:
            query = select(Platform).where(Platform.company_id == company_id)
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError("Ошибка получения платформ компании", e)

    async def get_with_reviews(self, platform_id: UUID) -> Platform | None:
        """Получить платформу со всеми отзывами"""
        try:
            query = (
                select(Platform)
                .options(selectinload(Platform.reviews), selectinload(Platform.company))
                .where(Platform.id == platform_id)
            )

            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError("Ошибка получения платформы с отзывами", e)

    async def get_by_name_and_company(
        self, name: str, company_id: UUID
    ) -> Platform | None:
        """Найти платформу по названию в рамках компании"""
        try:
            query = select(Platform).where(
                Platform.name == name, Platform.company_id == company_id
            )
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError("Ошибка поиска платформы по названию", e)

    async def get_by_url(self, platform_url: str) -> Platform | None:
        """Найти платформу по URL"""
        try:
            query = (
                select(Platform)
                .options(selectinload(Platform.company))
                .where(Platform.platform_url == platform_url)
            )
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError("Ошибка поиска платформы по URL", e)

    async def update_rating(self, platform_id: UUID) -> Platform:
        """Пересчитать средний рейтинг платформы на основе отзывов"""
        try:
            from app.infrastructure.persistence.models.economics import Review

            # Получаем средний рейтинг из отзывов
            query = select(func.avg(Review.rating)).where(
                Review.platform_id == platform_id
            )
            result = await self.db.execute(query)
            average_rating = result.scalar() or 0.0

            # Обновляем платформу
            return await self.update(platform_id, average_rating=float(average_rating))
        except Exception as e:
            raise DatabaseError("Ошибка обновления рейтинга платформы", e)

    async def get_platforms_with_stats(
        self, company_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        """Получить платформы со статистикой отзывов"""
        try:
            from app.infrastructure.persistence.models.economics import Review

            # Базовый запрос для подсчета статистики
            query = (
                select(
                    Platform.id,
                    Platform.name,
                    Platform.company_id,
                    Platform.monthly_views,
                    Platform.conversion_rate,
                    Platform.average_rating,
                    func.count(Review.id).label("reviews_count"),
                    func.avg(Review.rating).label("calculated_rating"),
                    func.sum(Review.financial_impact).label("total_impact"),
                )
                .outerjoin(Review)
                .group_by(Platform.id)
            )

            if company_id:
                query = query.where(Platform.company_id == company_id)

            result = await self.db.execute(query)

            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "company_id": row.company_id,
                    "monthly_views": row.monthly_views,
                    "conversion_rate": row.conversion_rate,
                    "average_rating": row.average_rating,
                    "reviews_count": row.reviews_count,
                    "calculated_rating": float(row.calculated_rating or 0),
                    "total_financial_impact": float(row.total_impact or 0),
                }
                for row in result.fetchall()
            ]
        except Exception as e:
            raise DatabaseError("Ошибка получения статистики платформ", e)

    async def get_top_platforms_by_impact(
        self, limit: int = 10, company_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        """Получить топ платформ по финансовому влиянию"""
        try:
            from app.infrastructure.persistence.models.economics import Review

            query = (
                select(
                    Platform.id,
                    Platform.name,
                    Platform.company_id,
                    func.sum(Review.financial_impact).label("total_impact"),
                    func.count(Review.id).label("reviews_count"),
                )
                .join(Review)
                .group_by(Platform.id)
                .order_by(func.sum(Review.financial_impact).desc())
                .limit(limit)
            )

            if company_id:
                query = query.where(Platform.company_id == company_id)

            result = await self.db.execute(query)

            return [
                {
                    "platform_id": row.id,
                    "platform_name": row.name,
                    "company_id": row.company_id,
                    "total_impact": float(row.total_impact),
                    "reviews_count": row.reviews_count,
                }
                for row in result.fetchall()
            ]
        except Exception as e:
            raise DatabaseError("Ошибка получения топ платформ по влиянию", e)

    async def update_metrics(
        self,
        platform_id: UUID,
        monthly_views: int | None = None,
        conversion_rate: float | None = None,
        cac_on_platform: float | None = None,
    ) -> Platform:
        """Обновить метрики платформы"""
        updates: dict[str, int | float] = {}
        if monthly_views is not None:
            updates["monthly_views"] = monthly_views
        if conversion_rate is not None:
            updates["conversion_rate"] = conversion_rate
        if cac_on_platform is not None:
            updates["cac_on_platform"] = cac_on_platform

        if not updates:
            return await self.get_by_id_or_404(platform_id)

        return await self.update(platform_id, **updates)
