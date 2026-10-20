"""Контракт сервиса аналитики отзывов для воркера + временная заглушка.

Реальный сервис (LLM, промпты, генерация ответа) подключается через ctx["insights_service"]
в app/worker/worker.py; воркер зависит только от протокола ReviewInsightsService.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

MIN_THREAT, MAX_THREAT = 1, 5


class ReviewSentiment(StrEnum):
    """Значения колонки reviews.sentiment (верхний регистр, как в схеме БД)."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


class InsightsTransientError(Exception):
    """Временный сбой аналитики (LLM недоступна, таймаут): воркер повторит задачу."""


@dataclass(frozen=True, slots=True)
class ReviewForInsights:
    id: UUID
    text: str
    rating: int | None


@dataclass(frozen=True, slots=True)
class ReviewInsight:
    review_id: UUID
    sentiment: ReviewSentiment
    threat_level: int  # 1 (безопасный) .. 5 (репутационная угроза)
    suggested_reply: str
    tags: tuple[str, ...]
    complete: (
        bool  # True -> reviews.is_analyzed = true (анализ полный, ответ сгенерирован)
    )

    def __post_init__(self) -> None:
        if not MIN_THREAT <= self.threat_level <= MAX_THREAT:
            raise ValueError(f"threat_level must be in [{MIN_THREAT}, {MAX_THREAT}]")


class ReviewInsightsService(Protocol):
    async def analyze_many(
        self, reviews: Sequence[ReviewForInsights]
    ) -> list[ReviewInsight]:
        """Вернуть ровно один ReviewInsight на каждый отзыв (порядок не важен, ключ — review_id)."""
        ...


class RatingBasedInsightsService:
    """ЗАГЛУШКА: оценка только по рейтингу, без LLM и без ответа.

    Намеренно возвращает complete=False: пока нет настоящей аналитики, отзывы не помечаются как
    проанализированные (is_analyzed остаётся false), а sentiment/threat_level заполняются приблизительно.
    """

    async def analyze_many(
        self, reviews: Sequence[ReviewForInsights]
    ) -> list[ReviewInsight]:
        return [self._one(r) for r in reviews]

    @staticmethod
    def _one(review: ReviewForInsights) -> ReviewInsight:
        rating = review.rating
        if rating is None or rating == 3:
            sentiment, threat = ReviewSentiment.NEUTRAL, 2
        elif rating >= 4:
            sentiment, threat = ReviewSentiment.POSITIVE, 1
        else:
            sentiment, threat = ReviewSentiment.NEGATIVE, 4 if rating <= 1 else 3
        return ReviewInsight(
            review_id=review.id,
            sentiment=sentiment,
            threat_level=threat,
            suggested_reply="",
            tags=(),
            complete=False,
        )
