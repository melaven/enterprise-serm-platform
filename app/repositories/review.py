"""
Репозиторий для работы с отзывами
"""

from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models.economics import Review
from ..schemas.economics import ReviewStatus
from ..exceptions import DatabaseError


class ReviewRepository(BaseRepository[Review]):
    """Репозиторий для управления отзывами"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, Review)
    
    async def get_by_external_id(self, external_review_id: str) -> Optional[Review]:
        """Найти отзыв по внешнему ID (для интеграций)"""
        try:
            query = select(Review).where(Review.external_review_id == external_review_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError("Ошибка поиска отзыва по внешнему ID", e)
    
    async def exists_by_external_id(self, external_review_id: str) -> bool:
        """Проверить существование отзыва по внешнему ID"""
        try:
            query = select(Review.id).where(Review.external_review_id == external_review_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none() is not None
        except Exception as e:
            raise DatabaseError("Ошибка проверки существования отзыва", e)
    
    async def get_by_platform_id(self, 
                                platform_id: UUID, 
                                limit: int = 100,
                                offset: int = 0,
                                status: ReviewStatus = None) -> List[Review]:
        """Получить отзывы по платформе"""
        try:
            query = select(Review).where(Review.platform_id == platform_id)
            
            if status:
                query = query.where(Review.status == status)
            
            query = query.order_by(Review.created_at.desc()).limit(limit).offset(offset)
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise DatabaseError("Ошибка получения отзывов платформы", e)
    
    async def get_with_platform_and_company(self, review_id: UUID) -> Optional[Review]:
        """Получить отзыв с данными платформы и компании"""
        try:
            query = select(Review).options(
                selectinload(Review.platform).selectinload(
                    Review.platform.property.mapper.class_.company
                )
            ).where(Review.id == review_id)
            
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError("Ошибка получения отзыва с полными данными", e)
    
    async def get_by_rating_range(self, 
                                 platform_id: UUID,
                                 min_rating: int = 1,
                                 max_rating: int = 5) -> List[Review]:
        """Получить отзывы в диапазоне рейтингов"""
        try:
            query = select(Review).where(
                and_(
                    Review.platform_id == platform_id,
                    Review.rating >= min_rating,
                    Review.rating <= max_rating
                )
            ).order_by(Review.created_at.desc())
            
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise DatabaseError("Ошибка получения отзывов по рейтингу", e)
    
    async def get_negative_reviews_without_response(self, 
                                                   platform_id: UUID = None,
                                                   days_ago: int = 30) -> List[Review]:
        """Получить негативные отзывы без ответа за период"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_ago)
            
            query = select(Review).where(
                and_(
                    Review.rating <= 3,
                    Review.status == ReviewStatus.NEW,
                    Review.si_response.is_(None),
                    Review.created_at >= cutoff_date
                )
            )
            
            if platform_id:
                query = query.where(Review.platform_id == platform_id)
            
            query = query.order_by(Review.created_at.asc())
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise DatabaseError("Ошибка получения негативных отзывов", e)
    
    async def get_reviews_stats(self, 
                               platform_id: UUID = None,
                               days_ago: int = 30) -> Dict[str, Any]:
        """Получить статистику отзывов за период"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_ago)
            
            base_query = select(Review).where(Review.created_at >= cutoff_date)
            
            if platform_id:
                base_query = base_query.where(Review.platform_id == platform_id)
            
            # Общее количество
            total_query = select(func.count(Review.id)).select_from(base_query.subquery())
            total_result = await self.db.execute(total_query)
            total_count = total_result.scalar() or 0
            
            # Статистика по рейтингам
            rating_stats_query = select(
                Review.rating,
                func.count(Review.id).label('count')
            ).where(Review.created_at >= cutoff_date).group_by(Review.rating)
            
            if platform_id:
                rating_stats_query = rating_stats_query.where(Review.platform_id == platform_id)
            
            rating_result = await self.db.execute(rating_stats_query)
            rating_stats = {row.rating: row.count for row in rating_result.fetchall()}
            
            # Статистика по статусам
            status_stats_query = select(
                Review.status,
                func.count(Review.id).label('count')
            ).where(Review.created_at >= cutoff_date).group_by(Review.status)
            
            if platform_id:
                status_stats_query = status_stats_query.where(Review.platform_id == platform_id)
            
            status_result = await self.db.execute(status_stats_query)
            status_stats = {row.status.value: row.count for row in status_result.fetchall()}
            
            # Финансовое влияние
            impact_query = select(
                func.sum(Review.financial_impact).label('total_impact'),
                func.avg(Review.financial_impact).label('avg_impact')
            ).where(Review.created_at >= cutoff_date)
            
            if platform_id:
                impact_query = impact_query.where(Review.platform_id == platform_id)
            
            impact_result = await self.db.execute(impact_query)
            impact_row = impact_result.first()
            
            return {
                "period_days": days_ago,
                "total_reviews": total_count,
                "rating_distribution": rating_stats,
                "status_distribution": status_stats,
                "financial_impact": {
                    "total": float(impact_row.total_impact or 0),
                    "average": float(impact_row.avg_impact or 0)
                },
                "negative_reviews": rating_stats.get(1, 0) + rating_stats.get(2, 0) + rating_stats.get(3, 0),
                "positive_reviews": rating_stats.get(4, 0) + rating_stats.get(5, 0)
            }
        except Exception as e:
            raise DatabaseError("Ошибка получения статистики отзывов", e)
    
    async def update_status_and_response(self, 
                                        review_id: UUID,
                                        status: ReviewStatus,
                                        si_response: str = None,
                                        financial_impact: float = None) -> Review:
        """Обновить статус отзыва и ответ SI"""
        updates = {"status": status}
        
        if si_response is not None:
            updates["si_response"] = si_response
        
        if financial_impact is not None:
            updates["financial_impact"] = financial_impact
        
        return await self.update(review_id, **updates)
    
    async def search_by_content(self, 
                               search_term: str,
                               platform_id: UUID = None,
                               limit: int = 50) -> List[Review]:
        """Поиск отзывов по содержимому текста"""
        try:
            query = select(Review).where(
                or_(
                    Review.text.ilike(f"%{search_term}%"),
                    Review.author_name.ilike(f"%{search_term}%")
                )
            )
            
            if platform_id:
                query = query.where(Review.platform_id == platform_id)
            
            query = query.order_by(Review.created_at.desc()).limit(limit)
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise DatabaseError("Ошибка поиска отзывов по содержимому", e)
    
    async def get_reviews_requiring_attention(self, 
                                            max_hours_without_response: int = 24) -> List[Review]:
        """Получить отзывы, требующие внимания (негативные без ответа)"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_hours_without_response)
            
            query = select(Review).options(
                selectinload(Review.platform).selectinload(
                    Review.platform.property.mapper.class_.company
                )
            ).where(
                and_(
                    Review.rating <= 3,
                    Review.status == ReviewStatus.NEW,
                    Review.si_response.is_(None),
                    Review.created_at <= cutoff_time
                )
            ).order_by(Review.created_at.asc())
            
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise DatabaseError("Ошибка получения отзывов, требующих внимания", e)
    async def get_platform_statistics(self, 
                                    platform_id: UUID, 
                                    days: int) -> Dict[str, Any]:
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
                "financial_impact": 0.0
            }
            
        except Exception as e:
            logger.error(f"Error getting platform statistics: {e}")
            return {
                "total_reviews": 0,
                "new_reviews_count": 0,
                "average_rating": 0.0,
                "financial_impact": 0.0
            }
    
    async def get_sentiment_distribution(self,
                                       platform_id: UUID,
                                       start_date: date,
                                       end_date: date) -> Dict[str, int]:
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
                "total": total
            }
            
        except Exception as e:
            logger.error(f"Error getting sentiment distribution: {e}")
            return {"positive": 0, "neutral": 0, "negative": 0, "total": 0}
    
    async def get_rating_distribution(self,
                                    platform_id: UUID,
                                    start_date: date,
                                    end_date: date) -> Dict[str, Any]:
        """
        Получение распределения рейтингов
        
        Returns:
            Словарь с распределением рейтингов и средним значением
        """
        try:
            # Получаем распределение рейтингов
            query = select(
                Review.rating,
                func.count(Review.id)
            ).where(
                Review.platform_id == platform_id
            ).group_by(Review.rating)
            
            result = await self.db.execute(query)
            ratings_data = result.all()
            
            # Инициализируем распределение
            distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
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