"""
Схемы данных для LLM-аналитики отзывов
"""

from pydantic import BaseModel, Field


class ReviewAnalytics(BaseModel):
    """Результат LLM-анализа отзыва"""

    sentiment: str = Field(..., description="Тональность: Positive, Neutral, Negative")
    tags: list[str] = Field(default_factory=list, description="Ключевые теги из текста")
    suggested_reply: str | None = Field(
        None, description="Сгенерированный черновик ответа"
    )


class EnrichedReviewSchema(BaseModel):
    """Расширенная схема отзыва с аналитикой"""

    text: str
    rating: int
    platform: str
    analytics: ReviewAnalytics | None = None
