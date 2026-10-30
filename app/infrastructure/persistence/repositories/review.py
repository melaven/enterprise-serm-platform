"""
Репозиторий для работы с отзывами
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas.economics import ReviewStatus
from app.core.anonymizer import anonymize_author_name
from app.core.exceptions import DatabaseError
from app.core.review_privacy import safe_category, safe_review_summary, safe_sentiment
from app.infrastructure.persistence.models.economics import Platform, Review
from app.infrastructure.persistence.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ReviewRepository(BaseRepository[Review]):
    """Репозиторий для управления отзывами"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Review)

    async def create(self, **values: Any) -> Review:
        return await super().create(**self._sanitize_review_values(values))

    async def update(self, id: UUID, **values: Any) -> Review:
        return await super().update(id, **self._sanitize_review_values(values))

    async def create_for_tenant(self, tenant_id: UUID, **values: Any) -> Review:
        """Create a review with an immutable tenant key; transaction stays caller-owned."""
        values = self._sanitize_review_values(values)
        supplied_tenant = values.pop("tenant_id", tenant_id)
        supplied_company = values.pop("company_id", tenant_id)
        if supplied_tenant != tenant_id or supplied_company != tenant_id:
            raise ValueError("Review tenant cannot differ from the active tenant")

        allowed_fields = {column.key for column in Review.__table__.columns} - {
            "id",
            "company_id",
        }
        unexpected_fields = values.keys() - allowed_fields
        if unexpected_fields:
            raise ValueError(
                f"Unsupported review fields: {', '.join(sorted(unexpected_fields))}"
            )

        platform_id = values.get("platform_id")
        if platform_id is None:
            raise ValueError("platform_id is required")
        result = await self.db.execute(
            select(Platform.id).where(
                Platform.id == platform_id,
                Platform.company_id == tenant_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("Platform does not belong to the requested tenant")

        review = Review(company_id=tenant_id, **values)
        self.db.add(review)
        await self.db.flush()
        return review

    async def get_for_tenant(self, tenant_id: UUID, review_id: UUID) -> Review | None:
        result = await self.db.execute(
            select(Review).where(
                Review.id == review_id,
                Review.company_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_tenant(
        self, tenant_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Review]:
        if limit < 1 or offset < 0:
            raise ValueError("limit must be positive and offset must be non-negative")
        result = await self.db.execute(
            select(Review)
            .where(Review.company_id == tenant_id)
            .order_by(Review.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_for_tenant(
        self, tenant_id: UUID, review_id: UUID, **values: Any
    ) -> Review | None:
        values = self._sanitize_review_values(values)
        if not values:
            return await self.get_for_tenant(tenant_id, review_id)
        immutable_fields = {"id", "tenant_id", "company_id", "platform_id"}
        if immutable_fields.intersection(values):
            raise ValueError("Review identity and tenant fields cannot be updated")

        allowed_fields = {column.key for column in Review.__table__.columns} - {
            "id",
            "company_id",
            "platform_id",
        }
        unexpected_fields = values.keys() - allowed_fields
        if unexpected_fields:
            raise ValueError(
                f"Unsupported review fields: {', '.join(sorted(unexpected_fields))}"
            )

        result = await self.db.execute(
            update(Review)
            .where(Review.id == review_id, Review.company_id == tenant_id)
            .values(**values)
            .returning(Review.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        await self.db.flush()
        return await self.get_for_tenant(tenant_id, review_id)

    @staticmethod
    def _sanitize_review_values(values: dict[str, Any]) -> dict[str, Any]:
        sanitized = values.copy()
        sanitized["author_name"] = anonymize_author_name()
        if "text" in sanitized:
            sanitized["text"] = safe_review_summary(
                sanitized.get("rating", 0),
                safe_sentiment(sanitized.get("sentiment")),
            )
        if "sentiment" in sanitized:
            sanitized["sentiment"] = safe_sentiment(sanitized["sentiment"])
        for field in ("tags", "analysis_tags"):
            if field in sanitized:
                values = sanitized[field]
                sanitized[field] = (
                    [
                        category
                        for tag in values
                        if (category := safe_category(tag)) is not None
                    ]
                    if isinstance(values, list)
                    else []
                )
        for field in (
            "si_response",
            "auto_reply",
            "suggested_reply",
            "ai_error",
            "dlq_reason",
        ):
            if field in sanitized:
                sanitized[field] = None
        for field in (
            "external_review_id",
            "author_avatar_url",
            "author_profile_url",
            "raw_metadata",
            "reply_text",
        ):
            sanitized.pop(field, None)
        return sanitized

    async def delete_for_tenant(self, tenant_id: UUID, review_id: UUID) -> bool:
        result = await self.db.execute(
            delete(Review)
            .where(Review.id == review_id, Review.company_id == tenant_id)
            .returning(Review.id)
        )
        deleted = result.scalar_one_or_none() is not None
        if deleted:
            await self.db.flush()
        return deleted

    async def get_by_platform_id(
        self,
        platform_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: ReviewStatus | None = None,
    ) -> list[Review]:
        """Получить отзывы по платформе"""
        try:
            query = select(Review).where(Review.platform_id == platform_id)

            if status:
                query = query.where(Review.status == status)

            query = query.order_by(Review.created_at.desc()).limit(limit).offset(offset)
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError("Ошибка получения отзывов платформы", e)

    async def get_with_platform_and_company(self, review_id: UUID) -> Review | None:
        """Получить отзыв с данными платформы и компании"""
        try:
            query = (
                select(Review)
                .options(
                    selectinload(Review.platform_ref).selectinload(
                        Review.platform_ref.property.mapper.class_.company
                    )
                )
                .where(Review.id == review_id)
            )

            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError("Ошибка получения отзыва с полными данными", e)

    async def get_by_rating_range(
        self, platform_id: UUID, min_rating: int = 1, max_rating: int = 5
    ) -> list[Review]:
        """Получить отзывы в диапазоне рейтингов"""
        try:
            query = (
                select(Review)
                .where(
                    and_(
                        Review.platform_id == platform_id,
                        Review.rating >= min_rating,
                        Review.rating <= max_rating,
                    )
                )
                .order_by(Review.created_at.desc())
            )

            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError("Ошибка получения отзывов по рейтингу", e)

    async def get_negative_reviews_without_response(
        self, platform_id: UUID | None = None, days_ago: int = 30
    ) -> list[Review]:
        """Получить негативные отзывы без ответа за период"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_ago)

            query = select(Review).where(
                and_(
                    Review.rating <= 3,
                    Review.status == ReviewStatus.NEW,
                    Review.si_response.is_(None),
                    Review.created_at >= cutoff_date,
                )
            )

            if platform_id:
                query = query.where(Review.platform_id == platform_id)

            query = query.order_by(Review.created_at.asc())
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError("Ошибка получения негативных отзывов", e)

    async def get_reviews_stats(
        self, platform_id: UUID | None = None, days_ago: int = 30
    ) -> dict[str, Any]:
        """Получить статистику отзывов за период"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_ago)

            base_query = select(Review).where(Review.created_at >= cutoff_date)

            if platform_id:
                base_query = base_query.where(Review.platform_id == platform_id)

            # Общее количество
            total_query = select(func.count(Review.id)).select_from(
                base_query.subquery()
            )
            total_result = await self.db.execute(total_query)
            total_count = total_result.scalar() or 0

            # Статистика по рейтингам
            rating_stats_query = (
                select(Review.rating, func.count(Review.id).label("count"))
                .where(Review.created_at >= cutoff_date)
                .group_by(Review.rating)
            )

            if platform_id:
                rating_stats_query = rating_stats_query.where(
                    Review.platform_id == platform_id
                )

            rating_result = await self.db.execute(rating_stats_query)
            rating_stats = {
                int(row[0]): int(row[1]) for row in rating_result.fetchall()
            }

            # Статистика по статусам
            status_stats_query = (
                select(Review.status, func.count(Review.id).label("count"))
                .where(Review.created_at >= cutoff_date)
                .group_by(Review.status)
            )

            if platform_id:
                status_stats_query = status_stats_query.where(
                    Review.platform_id == platform_id
                )

            status_result = await self.db.execute(status_stats_query)
            status_stats = {
                row.status.value: row.count for row in status_result.fetchall()
            }

            # Финансовое влияние
            impact_query = select(
                func.sum(Review.financial_impact).label("total_impact"),
                func.avg(Review.financial_impact).label("avg_impact"),
            ).where(Review.created_at >= cutoff_date)

            if platform_id:
                impact_query = impact_query.where(Review.platform_id == platform_id)

            impact_result = await self.db.execute(impact_query)
            impact_row = impact_result.first()
            total_impact = float(impact_row.total_impact or 0) if impact_row else 0.0
            average_impact = float(impact_row.avg_impact or 0) if impact_row else 0.0

            return {
                "period_days": days_ago,
                "total_reviews": total_count,
                "rating_distribution": rating_stats,
                "status_distribution": status_stats,
                "financial_impact": {
                    "total": total_impact,
                    "average": average_impact,
                },
                "negative_reviews": (rating_stats.get(1) or 0)
                + (rating_stats.get(2) or 0)
                + (rating_stats.get(3) or 0),
                "positive_reviews": (rating_stats.get(4) or 0)
                + (rating_stats.get(5) or 0),
            }
        except Exception as e:
            raise DatabaseError("Ошибка получения статистики отзывов", e)

    async def update_status_and_response(
        self,
        review_id: UUID,
        status: ReviewStatus,
        si_response: str | None = None,
        financial_impact: float | None = None,
    ) -> Review:
        """Обновить статус отзыва и ответ SI"""
        updates: dict[str, Any] = {"status": status}

        if si_response is not None:
            updates["si_response"] = si_response

        if financial_impact is not None:
            updates["financial_impact"] = financial_impact

        return await self.update(review_id, **updates)

    async def search_by_content(
        self, search_term: str, platform_id: UUID | None = None, limit: int = 50
    ) -> list[Review]:
        """Поиск отзывов по содержимому текста"""
        try:
            query = select(Review).where(
                or_(
                    Review.text.ilike(f"%{search_term}%"),
                    Review.author_name.ilike(f"%{search_term}%"),
                )
            )

            if platform_id:
                query = query.where(Review.platform_id == platform_id)

            query = query.order_by(Review.created_at.desc()).limit(limit)
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError("Ошибка поиска отзывов по содержимому", e)

    async def get_reviews_requiring_attention(
        self, max_hours_without_response: int = 24
    ) -> list[Review]:
        """Получить отзывы, требующие внимания (негативные без ответа)"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(
                hours=max_hours_without_response
            )

            query = (
                select(Review)
                .options(
                    selectinload(Review.platform_ref).selectinload(
                        Review.platform_ref.property.mapper.class_.company
                    )
                )
                .where(
                    and_(
                        Review.rating <= 3,
                        Review.status == ReviewStatus.NEW,
                        Review.si_response.is_(None),
                        Review.created_at <= cutoff_time,
                    )
                )
                .order_by(Review.created_at.asc())
            )

            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError("Ошибка получения отзывов, требующих внимания", e)

    async def get_platform_statistics(
        self, platform_id: UUID, days: int
    ) -> dict[str, Any]:
        """
        Получение статистики по платформе за указанный период

        Args:
            platform_id: ID платформы
            days: Количество дней для анализа

        Returns:
            Словарь со статистикой
        """
        try:
            # Базовая статистика - количество отзывов
            query = select(func.count(Review.id)).where(
                Review.platform_id == platform_id
            )

            result = await self.db.execute(query)
            total_reviews = result.scalar() or 0

            # Заглушка для других метрик
            return {
                "total_reviews": total_reviews,
                "new_reviews_count": 0,  # За последние days дней
                "average_rating": 0.0,
                "financial_impact": 0.0,
            }

        except Exception as e:
            logger.error(f"Error getting platform statistics: {e}")
            return {
                "total_reviews": 0,
                "new_reviews_count": 0,
                "average_rating": 0.0,
                "financial_impact": 0.0,
            }

    async def get_sentiment_distribution(
        self, platform_id: UUID, start_date: date, end_date: date
    ) -> dict[str, int]:
        """
        Получение распределения тональности отзывов

        Returns:
            Словарь с количеством отзывов по тональности
        """
        try:
            # Базовая реализация - возвращаем заглушку
            # В реальной реализации здесь был бы анализ sentiment поля
            query = select(func.count(Review.id)).where(
                Review.platform_id == platform_id
            )

            result = await self.db.execute(query)
            total = result.scalar() or 0

            return {
                "positive": total // 3,
                "neutral": total // 3,
                "negative": total // 3,
                "total": total,
            }

        except Exception as e:
            logger.error(f"Error getting sentiment distribution: {e}")
            return {"positive": 0, "neutral": 0, "negative": 0, "total": 0}

    async def get_rating_distribution(
        self, platform_id: UUID, start_date: date, end_date: date
    ) -> dict[str, Any]:
        """
        Получение распределения рейтингов

        Returns:
            Словарь с распределением рейтингов и средним значением
        """
        try:
            # Получаем распределение рейтингов
            query = (
                select(Review.rating, func.count(Review.id))
                .where(Review.platform_id == platform_id)
                .group_by(Review.rating)
            )

            result = await self.db.execute(query)
            ratings_data = result.all()

            # Инициализируем распределение
            distribution: dict[str, int | float] = {
                "1": 0,
                "2": 0,
                "3": 0,
                "4": 0,
                "5": 0,
            }
            total_sum = 0
            total_count = 0

            # Заполняем реальными данными
            for rating, count in ratings_data:
                if 1 <= rating <= 5:
                    distribution[str(rating)] = count
                    total_sum += rating * count
                    total_count += count

            # Рассчитываем средний рейтинг
            average = 0.0
            if total_count > 0:
                average = total_sum / total_count

            distribution["average"] = round(average, 2)

            return distribution

        except Exception as e:
            logger.error(f"Error getting rating distribution: {e}")
            return {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "average": 0.0}
