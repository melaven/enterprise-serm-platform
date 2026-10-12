"""
Схемы данных для аналитики отзывов и платформ
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from enum import Enum

from .economics import ReviewStatus


class DashboardReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_review_id: str | None
    platform: str | None
    author_name: str
    rating: int
    text: str
    sentiment: str | None
    is_critical: bool
    status: ReviewStatus
    financial_impact: float
    si_response: str | None
    created_at: datetime


class DashboardReviewsPage(BaseModel):
    items: list[DashboardReview]
    total: int
    page: int
    page_size: int
    total_pages: int


class DashboardReviewsResponse(BaseModel):
    success: bool
    data: DashboardReviewsPage


class DashboardMetrics(BaseModel):
    total_reviews: int
    positive_reviews: int
    negative_reviews: int
    critical_reviews: int


class DashboardMetricsResponse(BaseModel):
    success: bool
    data: DashboardMetrics


# Legacy схема для обратной совместимости с analyzer service
class ReviewAnalytics(BaseModel):
    """Результат LLM-анализа отзыва"""
    sentiment: str = Field(..., description="Тональность: Positive, Neutral, Negative")
    tags: List[str] = Field(default_factory=list, description="Ключевые теги из текста")
    suggested_reply: Optional[str] = Field(None, description="Сгенерированный черновик ответа")


class TimeRange(str, Enum):
    """Временные диапазоны для аналитики"""
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class SentimentDistribution(BaseModel):
    """Распределение тональности"""
    positive: int = Field(ge=0, description="Количество позитивных отзывов")
    neutral: int = Field(ge=0, description="Количество нейтральных отзывов") 
    negative: int = Field(ge=0, description="Количество негативных отзывов")
    total: int = Field(ge=0, description="Общее количество отзывов")


class RatingDistribution(BaseModel):
    """Распределение рейтингов"""
    rating_1: int = Field(ge=0, description="Количество отзывов с рейтингом 1")
    rating_2: int = Field(ge=0, description="Количество отзывов с рейтингом 2")
    rating_3: int = Field(ge=0, description="Количество отзывов с рейтингом 3")
    rating_4: int = Field(ge=0, description="Количество отзывов с рейтингом 4")
    rating_5: int = Field(ge=0, description="Количество отзывов с рейтингом 5")
    average: float = Field(ge=1.0, le=5.0, description="Средний рейтинг")


class PlatformAnalytics(BaseModel):
    """Аналитика по платформе"""
    platform_id: str
    platform_name: str
    platform_url: str
    total_reviews: int = Field(ge=0)
    sentiment_distribution: SentimentDistribution
    rating_distribution: RatingDistribution
    financial_impact: float = Field(description="Финансовое влияние в рублях")
    trends: Dict[str, Any] = Field(default_factory=dict, description="Тренды за период")


class CompanyAnalytics(BaseModel):
    """Общая аналитика по компании"""
    company_id: str
    period_start: datetime
    period_end: datetime
    total_reviews: int = Field(ge=0)
    total_platforms: int = Field(ge=0)
    overall_sentiment: SentimentDistribution
    overall_rating: RatingDistribution
    total_financial_impact: float
    platforms: List[PlatformAnalytics]


class AnalyticsRequest(BaseModel):
    """Запрос аналитики"""
    time_range: TimeRange
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    platform_ids: Optional[List[str]] = Field(None, description="Фильтр по платформам")
    include_trends: bool = Field(False, description="Включать анализ трендов")


class TrendPoint(BaseModel):
    """Точка данных для тренда"""
    date: date
    value: float
    reviews_count: int


class AnalyticsTrend(BaseModel):
    """Тренд для аналитики"""
    metric_name: str
    period: str
    data_points: List[TrendPoint]
    trend_direction: str = Field(description="up, down, stable")
    change_percentage: float = Field(description="Изменение в процентах")


class DetailedAnalyticsResponse(BaseModel):
    """Детальный ответ аналитики"""
    company_analytics: CompanyAnalytics
    trends: Optional[List[AnalyticsTrend]] = None
    generated_at: datetime = Field(default_factory=datetime.now)
    period_description: str