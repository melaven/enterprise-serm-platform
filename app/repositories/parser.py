"""
Репозиторий для операций парсинга отзывов
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, desc, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models.economics import Review, Platform, Company
from ..schemas.economics import ReviewStatus
from ..exceptions import DatabaseError


class ParserRepository(BaseRepository[Review]):
    """Репозиторий для операций парсинга и массовой обработки отзывов"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, Review)
    
    async def bulk_create_reviews(self, reviews_data: List[Dict[str, Any]]) -> List[Review]:
        """
        Массовое создание отзывов с оптимизацией
        
        Args:
            reviews_data: Список данных для создания отзывов
            
        Returns:
            Список созданных отзывов
        """
        try:
            reviews = []
            for data in reviews_data:
                review = Review(
                    platform_id=data["platform_id"],
                    author_name=data["author_name"],
                    rating=data["rating"],
                    text=data["text"],
                    external_review_id=data.get("external_review_id"),
                    company_id=data["company_id"],
                    status=data.get("status", ReviewStatus.NEW),
                    financial_impact=data.get("financial_impact", 0.0),
                    si_response=data.get("si_response")
                )
                reviews.append(review)
            
            self.db.add_all(reviews)
            await self.db.flush()  # Получаем ID без коммита
            
            return reviews
            
        except Exception as e:
            raise DatabaseError("Ошибка массового создания отзывов", e)
    
    async def get_existing_external_ids(self, 
                                      platform_id: UUID, 
                                      external_ids: List[str]) -> List[str]:
        """
        Получить список существующих external_id для платформы
        (для проверки дубликатов перед массовой загрузкой)
        
        Args:
            platform_id: ID платформы
            external_ids: Список внешних ID для проверки
            
        Returns:
            Список существующих external_id
        """
        try:
            if not external_ids:
                return []
                
            query = select(Review.external_review_id).where(
                and_(
                    Review.platform_id == platform_id,
                    Review.external_review_id.in_(external_ids)
                )
            )
            result = await self.db.execute(query)
            return [row[0] for row in result.fetchall() if row[0] is not None]
            
        except Exception as e:
            raise DatabaseError("Ошибка проверки дубликатов по external_id", e)
    
    async def get_platform_by_url(self, platform_url: str) -> Optional[Platform]:
        """
        Найти платформу по URL с данными компании
        
        Args:
            platform_url: URL платформы
            
        Returns:
            Платформа с данными компании или None
        """
        try:
            query = select(Platform).options(
                selectinload(Platform.company)
            ).where(Platform.platform_url == platform_url)
            
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            raise DatabaseError("Ошибка поиска платформы по URL", e)
    
    async def get_platform_statistics(self, 
                                    platform_id: UUID,
                                    days: int = 30) -> Dict[str, Any]:
        """
        Получить статистику платформы за указанный период
        
        Args:
            platform_id: ID платформы
            days: Количество дней для анализа
            
        Returns:
            Статистика платформы
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Общая статистика
            total_reviews_query = select(func.count(Review.id)).where(
                Review.platform_id == platform_id
            )
            total_reviews_result = await self.db.execute(total_reviews_query)
            total_reviews = total_reviews_result.scalar() or 0
            
            # Новые отзывы за период
            new_reviews_query = select(func.count(Review.id)).where(
                and_(
                    Review.platform_id == platform_id,
                    Review.created_at >= cutoff_date
                )
            )
            new_reviews_result = await self.db.execute(new_reviews_query)
            new_reviews_count = new_reviews_result.scalar() or 0
            
            # Средний рейтинг
            avg_rating_query = select(func.avg(Review.rating)).where(
                Review.platform_id == platform_id
            )
            avg_rating_result = await self.db.execute(avg_rating_query)
            average_rating = float(avg_rating_result.scalar() or 0)
            
            # Финансовое влияние за период
            financial_impact_query = select(func.sum(Review.financial_impact)).where(
                and_(
                    Review.platform_id == platform_id,
                    Review.created_at >= cutoff_date
                )
            )
            financial_impact_result = await self.db.execute(financial_impact_query)
            financial_impact = float(financial_impact_result.scalar() or 0)
            
            return {
                "total_reviews": total_reviews,
                "new_reviews_count": new_reviews_count,
                "average_rating": round(average_rating, 2),
                "financial_impact": financial_impact
            }
            
        except Exception as e:
            raise DatabaseError("Ошибка получения статистики платформы", e)
    
    async def get_parsing_candidates(self, 
                                   company_id: UUID = None,
                                   min_last_parsed_hours: int = 24,
                                   limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получить список платформ-кандидатов для парсинга
        
        Args:
            company_id: ID компании (опционально)
            min_last_parsed_hours: Минимум часов с последнего парсинга
            limit: Максимальное количество результатов
            
        Returns:
            Список платформ с информацией о последнем парсинге
        """
        try:
            # Подзапрос для получения даты последнего отзыва по каждой платформе
            last_review_subquery = select(
                Review.platform_id,
                func.max(Review.created_at).label('last_review_date')
            ).group_by(Review.platform_id).subquery()
            
            # Основной запрос с данными платформ
            query = select(
                Platform.id,
                Platform.name,
                Platform.platform_url,
                Platform.company_id,
                Company.name.label('company_name'),
                Platform.average_rating,
                func.count(Review.id).label('total_reviews'),
                last_review_subquery.c.last_review_date
            ).select_from(
                Platform
            ).join(
                Company, Platform.company_id == Company.id
            ).outerjoin(
                Review, Platform.id == Review.platform_id
            ).outerjoin(
                last_review_subquery, Platform.id == last_review_subquery.c.platform_id
            ).group_by(
                Platform.id, 
                Company.name,
                last_review_subquery.c.last_review_date
            )
            
            if company_id:
                query = query.where(Platform.company_id == company_id)
            
            # Фильтр по времени последнего парсинга
            cutoff_time = datetime.utcnow() - timedelta(hours=min_last_parsed_hours)
            query = query.where(
                or_(
                    last_review_subquery.c.last_review_date.is_(None),
                    last_review_subquery.c.last_review_date < cutoff_time
                )
            )
            
            query = query.order_by(
                last_review_subquery.c.last_review_date.asc().nulls_first()
            ).limit(limit)
            
            result = await self.db.execute(query)
            
            return [
                {
                    "platform_id": str(row.id),
                    "platform_name": row.name,
                    "platform_url": row.platform_url,
                    "company_id": str(row.company_id),
                    "company_name": row.company_name,
                    "average_rating": row.average_rating,
                    "total_reviews": row.total_reviews,
                    "last_review_date": row.last_review_date.isoformat() if row.last_review_date else None,
                    "hours_since_last_review": (
                        int((datetime.utcnow() - row.last_review_date).total_seconds() / 3600)
                        if row.last_review_date else None
                    )
                }
                for row in result.fetchall()
            ]
            
        except Exception as e:
            raise DatabaseError("Ошибка получения кандидатов для парсинга", e)
    
    async def mark_reviews_as_parsed(self, 
                                   platform_id: UUID,
                                   external_ids: List[str]) -> int:
        """
        Пометить отзывы как обработанные парсером
        (можно использовать для отслеживания источника данных)
        
        Args:
            platform_id: ID платформы
            external_ids: Список внешних ID обработанных отзывов
            
        Returns:
            Количество помеченных отзывов
        """
        try:
            if not external_ids:
                return 0
                
            # Обновляем метку времени последнего обновления
            query = text("""
                UPDATE reviews 
                SET updated_at = :updated_at
                WHERE platform_id = :platform_id 
                AND external_review_id = ANY(:external_ids)
            """)
            
            result = await self.db.execute(
                query,
                {
                    "updated_at": datetime.utcnow(),
                    "platform_id": platform_id,
                    "external_ids": external_ids
                }
            )
            
            return result.rowcount
            
        except Exception as e:
            raise DatabaseError("Ошибка отметки отзывов как обработанных", e)
    
    async def get_parsing_performance_stats(self, 
                                          company_id: UUID = None,
                                          days: int = 7) -> Dict[str, Any]:
        """
        Получить статистику производительности парсинга
        
        Args:
            company_id: ID компании (опционально)
            days: Период для анализа в днях
            
        Returns:
            Статистика производительности парсинга
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Базовый запрос
            base_condition = Review.created_at >= cutoff_date
            if company_id:
                base_condition = and_(base_condition, Review.company_id == company_id)
            
            # Общее количество новых отзывов
            total_new_reviews_query = select(func.count(Review.id)).where(base_condition)
            total_new_result = await self.db.execute(total_new_reviews_query)
            total_new_reviews = total_new_result.scalar() or 0
            
            # Отзывы с external_review_id (спарсенные)
            parsed_reviews_query = select(func.count(Review.id)).where(
                and_(base_condition, Review.external_review_id.isnot(None))
            )
            parsed_result = await self.db.execute(parsed_reviews_query)
            parsed_reviews = parsed_result.scalar() or 0
            
            # Статистика по дням
            daily_stats_query = select(
                func.date(Review.created_at).label('date'),
                func.count(Review.id).label('reviews_count'),
                func.count(Review.external_review_id).label('parsed_count')
            ).where(base_condition).group_by(func.date(Review.created_at)).order_by('date')
            
            daily_result = await self.db.execute(daily_stats_query)
            daily_stats = [
                {
                    "date": row.date.isoformat(),
                    "total_reviews": row.reviews_count,
                    "parsed_reviews": row.parsed_count,
                    "parsing_rate": round((row.parsed_count / row.reviews_count) * 100, 2) if row.reviews_count > 0 else 0
                }
                for row in daily_result.fetchall()
            ]
            
            # Статистика по платформам
            platform_stats_query = select(
                Platform.id,
                Platform.name,
                func.count(Review.id).label('reviews_count'),
                func.count(Review.external_review_id).label('parsed_count')
            ).select_from(
                Platform
            ).join(
                Review, Platform.id == Review.platform_id
            ).where(base_condition).group_by(
                Platform.id, Platform.name
            ).order_by(desc('reviews_count'))
            
            if company_id:
                platform_stats_query = platform_stats_query.where(Platform.company_id == company_id)
            
            platform_result = await self.db.execute(platform_stats_query)
            platform_stats = [
                {
                    "platform_id": str(row.id),
                    "platform_name": row.name,
                    "total_reviews": row.reviews_count,
                    "parsed_reviews": row.parsed_count,
                    "parsing_rate": round((row.parsed_count / row.reviews_count) * 100, 2) if row.reviews_count > 0 else 0
                }
                for row in platform_result.fetchall()
            ]
            
            return {
                "period_days": days,
                "company_id": str(company_id) if company_id else None,
                "summary": {
                    "total_new_reviews": total_new_reviews,
                    "parsed_reviews": parsed_reviews,
                    "manual_reviews": total_new_reviews - parsed_reviews,
                    "parsing_rate": round((parsed_reviews / total_new_reviews) * 100, 2) if total_new_reviews > 0 else 0
                },
                "daily_breakdown": daily_stats,
                "platform_breakdown": platform_stats
            }
            
        except Exception as e:
            raise DatabaseError("Ошибка получения статистики производительности парсинга", e)
    
    async def cleanup_old_failed_reviews(self, 
                                       days_old: int = 30,
                                       batch_size: int = 1000) -> int:
        """
        Очистка старых неудачных попыток парсинга
        (отзывы без external_review_id и текста)
        
        Args:
            days_old: Возраст записей в днях
            batch_size: Размер пакета для удаления
            
        Returns:
            Количество удаленных записей
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Находим записи для удаления (без external_id и с пустым текстом)
            query = select(Review.id).where(
                and_(
                    Review.created_at < cutoff_date,
                    Review.external_review_id.is_(None),
                    or_(
                        Review.text.is_(None),
                        Review.text == "",
                        func.length(Review.text) < 10
                    )
                )
            ).limit(batch_size)
            
            result = await self.db.execute(query)
            ids_to_delete = [row.id for row in result.fetchall()]
            
            if not ids_to_delete:
                return 0
            
            # Удаляем записи
            delete_query = text("DELETE FROM reviews WHERE id = ANY(:ids)")
            delete_result = await self.db.execute(delete_query, {"ids": ids_to_delete})
            
            return delete_result.rowcount
            
        except Exception as e:
            raise DatabaseError("Ошибка очистки старых записей", e)