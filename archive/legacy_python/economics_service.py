"""Расчёт упущенной выгоды от отзыва.

РЕФЕРЕНСНАЯ РЕАЛИЗАЦИЯ под тесты. Если в проекте сервис уже есть, этот файл
не копируй, а подстрой импорты и сигнатуры в tests/services/test_economics_service.py.

Формула:
    lost = views * conversion_rate * RATING_PENALTY[rating] * avg_check
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

# Доля конверсии, которую теряет бизнес из-за отзыва с данной оценкой.
RATING_PENALTY: dict[int, Decimal] = {
    1: Decimal("0.30"),
    2: Decimal("0.20"),
    3: Decimal("0.10"),
    4: Decimal("0"),
    5: Decimal("0"),
}
_CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class ReviewInput:
    rating: int  # 1..5
    views: int  # оценка охвата отзыва (просмотры карточки)


@dataclass(frozen=True, slots=True)
class BusinessMetrics:
    avg_check: Decimal  # средний чек, в валюте компании
    conversion_rate: Decimal  # 0..1


class MetricsRepository(Protocol):
    async def get_business_metrics(self) -> BusinessMetrics: ...


def calculate_lost_profit(review: ReviewInput, metrics: BusinessMetrics) -> Decimal:
    if review.rating not in RATING_PENALTY:
        raise ValueError(f"rating must be in 1..5, got {review.rating}")
    if review.views < 0:
        raise ValueError(f"views must be >= 0, got {review.views}")
    if not Decimal(0) <= metrics.conversion_rate <= Decimal(1):
        raise ValueError("conversion_rate must be in 0..1")
    if metrics.avg_check < 0:
        raise ValueError("avg_check must be >= 0")

    raw = (
        Decimal(review.views)
        * metrics.conversion_rate
        * RATING_PENALTY[review.rating]
        * metrics.avg_check
    )
    return raw.quantize(_CENT, rounding=ROUND_HALF_UP)


class EconomicsService:
    def __init__(self, repo: MetricsRepository) -> None:
        self._repo = repo

    async def estimate_review_loss(self, review: ReviewInput) -> Decimal:
        # Метрики читаются через tenant-сессию: RLS отдаёт только данные компании.
        metrics = await self._repo.get_business_metrics()
        return calculate_lost_profit(review, metrics)
