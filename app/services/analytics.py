"""
Сервис аналитики отзывов и платформ
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..repositories import ReviewRepository, PlatformRepository, CompanyRepository
from ..schemas.analytics import (
    CompanyAnalytics, PlatformAnalytics, SentimentDistribution, 
    RatingDistribution, TimeRange, AnalyticsRequest,
    DetailedAnalyticsResponse, AnalyticsTrend, TrendPoint
)
from ..exceptions import BusinessLogicError, NotFoundError

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Сервис для получения аналитики по отзывам и платформам"""
    
    def __init__(self,
                 review_repo: ReviewRepository,
                 platform_repo: PlatformRepository,
                 company_repo: CompanyRepository):
        self.review_repo = review_repo
        self.platform_repo = platform_repo
        self.company_repo = company_repo
    
    async def get_company_analytics(self, 
                                  company_id: UUID,
                                  request: AnalyticsRequest) -> DetailedAnalyticsResponse:
        """
        Получение детальной аналитики для компании
        
        Args:
            company_id: ID компании
            request: Параметры запроса аналитики
            
        Returns:
            Детальная аналитика компании
        """
        try:
            # Проверяем существование компании
            company = await self.company_repo.get_by_id(company_id)
            if not company:
                raise NotFoundError("Компания", str(company_id))
            
            # Рассчитываем период
            start_date, end_date = self._calculate_date_range(request)
            
            # Получаем платформы компании
            platforms = await self.platform_repo.get_by_company_id(company_id)
            
            # Фильтруем платформы если указан фильтр
            if request.platform_ids:
                platform_ids_set = set(request.platform_ids)
                platforms = [p for p in platforms if str(p.id) in platform_ids_set]
            
            # Собираем аналитику по платформам
            platform_analytics_list = []
            total_reviews = 0
            total_financial_impact = 0.0
            overall_sentiment = SentimentDistribution(positive=0, neutral=0, negative=0, total=0)
            overall_ratings = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            
            for platform in platforms:
                platform_analytics = await self._get_platform_analytics(
                    platform, start_date, end_date, request.include_trends
                )
                platform_analytics_list.append(platform_analytics)
                
                # Агрегируем общие показатели
                total_reviews += platform_analytics.total_reviews
                total_financial_impact += platform_analytics.financial_impact
                
                overall_sentiment.positive += platform_analytics.sentiment_distribution.positive
                overall_sentiment.neutral += platform_analytics.sentiment_distribution.neutral
                overall_sentiment.negative += platform_analytics.sentiment_distribution.negative
                overall_sentiment.total += platform_analytics.sentiment_distribution.total
                
                overall_ratings[1] += platform_analytics.rating_distribution.rating_1
                overall_ratings[2] += platform_analytics.rating_distribution.rating_2
                overall_ratings[3] += platform_analytics.rating_distribution.rating_3
                overall_ratings[4] += platform_analytics.rating_distribution.rating_4
                overall_ratings[5] += platform_analytics.rating_distribution.rating_5
            
            # Рассчитываем общий средний рейтинг
            total_ratings = sum(overall_ratings.values())
            average_rating = 0.0
            if total_ratings > 0:
                weighted_sum = sum(rating * count for rating, count in overall_ratings.items())
                average_rating = weighted_sum / total_ratings
            
            overall_rating_dist = RatingDistribution(
                rating_1=overall_ratings[1],
                rating_2=overall_ratings[2],
                rating_3=overall_ratings[3],
                rating_4=overall_ratings[4],
                rating_5=overall_ratings[5],
                average=round(average_rating, 2)
            )
            
            # Создаем объект аналитики компании
            company_analytics = CompanyAnalytics(
                company_id=str(company_id),
                period_start=datetime.combine(start_date, datetime.min.time()),
                period_end=datetime.combine(end_date, datetime.min.time()),
                total_reviews=total_reviews,
                total_platforms=len(platforms),
                overall_sentiment=overall_sentiment,
                overall_rating=overall_rating_dist,
                total_financial_impact=total_financial_impact,
                platforms=platform_analytics_list
            )
            
            # Генерируем тренды если запрошены
            trends = None
            if request.include_trends:
                trends = await self._generate_trends(company_id, start_date, end_date, request.platform_ids)
            
            return DetailedAnalyticsResponse(
                company_analytics=company_analytics,
                trends=trends,
                period_description=self._get_period_description(request, start_date, end_date)
            )
            
        except Exception as e:
            logger.error(f"Error getting company analytics for {company_id}: {str(e)}")
            if isinstance(e, (NotFoundError, BusinessLogicError)):
                raise
            raise BusinessLogicError(f"Ошибка получения аналитики: {str(e)}")
    
    async def _get_platform_analytics(self, 
                                    platform, 
                                    start_date: date, 
                                    end_date: date,
                                    include_trends: bool) -> PlatformAnalytics:
        """Получение аналитики для конкретной платформы"""
        
        # Получаем статистику по платформе за период
        days_count = (end_date - start_date).days + 1
        stats = await self.review_repo.get_platform_statistics(
            platform_id=platform.id,
            days=days_count
        )
        
        # Получаем распределение тональности
        sentiment_stats = await self.review_repo.get_sentiment_distribution(
            platform_id=platform.id,
            start_date=start_date,
            end_date=end_date
        )
        
        sentiment_dist = SentimentDistribution(
            positive=sentiment_stats.get('positive', 0),
            neutral=sentiment_stats.get('neutral', 0), 
            negative=sentiment_stats.get('negative', 0),
            total=sentiment_stats.get('total', 0)
        )
        
        # Получаем распределение рейтингов
        rating_stats = await self.review_repo.get_rating_distribution(
            platform_id=platform.id,
            start_date=start_date,
            end_date=end_date
        )
        
        rating_dist = RatingDistribution(
            rating_1=rating_stats.get('1', 0),
            rating_2=rating_stats.get('2', 0),
            rating_3=rating_stats.get('3', 0),
            rating_4=rating_stats.get('4', 0),
            rating_5=rating_stats.get('5', 0),
            average=rating_stats.get('average', 0.0)
        )
        
        # Генерируем тренды для платформы
        trends = {}
        if include_trends:
            trends = await self._generate_platform_trends(platform.id, start_date, end_date)
        
        return PlatformAnalytics(
            platform_id=str(platform.id),
            platform_name=platform.name,
            platform_url=platform.platform_url,
            total_reviews=stats.get('total_reviews', 0),
            sentiment_distribution=sentiment_dist,
            rating_distribution=rating_dist,
            financial_impact=stats.get('financial_impact', 0.0),
            trends=trends
        )
    
    def _calculate_date_range(self, request: AnalyticsRequest) -> tuple[date, date]:
        """Рассчитывает диапазон дат на основе запроса"""
        
        if request.time_range == TimeRange.CUSTOM:
            if not request.start_date or not request.end_date:
                raise BusinessLogicError("Для custom периода необходимо указать start_date и end_date")
            return request.start_date, request.end_date
        
        end_date = date.today()
        
        if request.time_range == TimeRange.WEEK:
            start_date = end_date - timedelta(days=7)
        elif request.time_range == TimeRange.MONTH:
            start_date = end_date - timedelta(days=30)
        elif request.time_range == TimeRange.QUARTER:
            start_date = end_date - timedelta(days=90)
        elif request.time_range == TimeRange.YEAR:
            start_date = end_date - timedelta(days=365)
        else:
            raise BusinessLogicError(f"Неподдерживаемый временной диапазон: {request.time_range}")
        
        return start_date, end_date
    
    def _get_period_description(self, request: AnalyticsRequest, start_date: date, end_date: date) -> str:
        """Генерирует описание периода для аналитики"""
        
        if request.time_range == TimeRange.CUSTOM:
            return f"Период с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}"
        
        descriptions = {
            TimeRange.WEEK: "Последние 7 дней",
            TimeRange.MONTH: "Последние 30 дней", 
            TimeRange.QUARTER: "Последние 90 дней",
            TimeRange.YEAR: "Последние 365 дней"
        }
        
        return descriptions.get(request.time_range, f"Период {request.time_range}")
    
    async def _generate_trends(self, 
                             company_id: UUID,
                             start_date: date,
                             end_date: date, 
                             platform_ids: Optional[List[str]]) -> List[AnalyticsTrend]:
        """Генерирует тренды для компании"""
        
        # Базовая реализация - возвращаем пустой список
        # В реальной реализации здесь был бы сложный анализ трендов
        logger.info(f"Generating trends for company {company_id} from {start_date} to {end_date}")
        return []
    
    async def _generate_platform_trends(self,
                                      platform_id: UUID,
                                      start_date: date,
                                      end_date: date) -> Dict[str, Any]:
        """Генерирует тренды для платформы"""
        
        # Базовая реализация - возвращаем пустой словарь
        # В реальной реализации здесь был бы анализ трендов платформы
        logger.info(f"Generating platform trends for {platform_id} from {start_date} to {end_date}")
        return {}