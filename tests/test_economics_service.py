from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.services.economics_service import (
    BusinessMetrics,
    EconomicsService,
    ReviewInput,
    calculate_lost_profit,
)

D = Decimal


@pytest.fixture
def metrics() -> BusinessMetrics:
    return BusinessMetrics(avg_check=D("5000"), conversion_rate=D("0.02"))


# views=1000, conversion=0.02 -> 20 потенциальных клиентов, чек 5000.
@pytest.mark.parametrize(
    ("rating", "expected"),
    [
        (1, D("30000.00")),  # 20 * 0.30 * 5000
        (2, D("20000.00")),  # 20 * 0.20 * 5000
        (3, D("10000.00")),  # 20 * 0.10 * 5000
        (4, D("0.00")),
        (5, D("0.00")),
    ],
)
def test_loss_by_rating(
    metrics: BusinessMetrics, rating: int, expected: Decimal
) -> None:
    result = calculate_lost_profit(ReviewInput(rating=rating, views=1000), metrics)

    assert result == expected


def test_zero_views_gives_zero_loss(metrics: BusinessMetrics) -> None:
    assert calculate_lost_profit(ReviewInput(rating=1, views=0), metrics) == D("0.00")


def test_result_is_decimal_rounded_to_cents() -> None:
    # 1 * 0.015 * 0.10 * 333.33 = 0.499995 -> 0.50 (ROUND_HALF_UP)
    metrics = BusinessMetrics(avg_check=D("333.33"), conversion_rate=D("0.015"))

    result = calculate_lost_profit(ReviewInput(rating=3, views=1), metrics)

    assert isinstance(result, Decimal)
    assert result == D("0.50")


def test_lower_rating_never_loses_less(metrics: BusinessMetrics) -> None:
    losses = [
        calculate_lost_profit(ReviewInput(rating=r, views=500), metrics)
        for r in (1, 2, 3, 4, 5)
    ]

    assert losses == sorted(losses, reverse=True)


@pytest.mark.parametrize("rating", [-1, 0, 6])
def test_invalid_rating_rejected(metrics: BusinessMetrics, rating: int) -> None:
    with pytest.raises(ValueError, match="rating"):
        calculate_lost_profit(ReviewInput(rating=rating, views=10), metrics)


def test_negative_views_rejected(metrics: BusinessMetrics) -> None:
    with pytest.raises(ValueError, match="views"):
        calculate_lost_profit(ReviewInput(rating=1, views=-1), metrics)


@pytest.mark.parametrize("conversion", [D("-0.01"), D("1.01")])
def test_invalid_conversion_rejected(conversion: Decimal) -> None:
    bad = BusinessMetrics(avg_check=D("100"), conversion_rate=conversion)

    with pytest.raises(ValueError, match="conversion_rate"):
        calculate_lost_profit(ReviewInput(rating=1, views=10), bad)


async def test_service_uses_tenant_metrics_from_repository(
    metrics: BusinessMetrics,
) -> None:
    repo = AsyncMock()
    repo.get_business_metrics.return_value = metrics
    service = EconomicsService(repo)

    result = await service.estimate_review_loss(ReviewInput(rating=1, views=1000))

    assert result == D("30000.00")
    repo.get_business_metrics.assert_awaited_once_with()


async def test_service_propagates_validation_error(
    metrics: BusinessMetrics,
) -> None:
    repo = AsyncMock()
    repo.get_business_metrics.return_value = metrics
    service = EconomicsService(repo)

    with pytest.raises(ValueError, match="rating"):
        await service.estimate_review_loss(ReviewInput(rating=9, views=10))
