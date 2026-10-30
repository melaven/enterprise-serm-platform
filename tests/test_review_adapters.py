"""Tests for review platform adapters with PII sanitization."""

import pytest

from app.infrastructure.integrations.review_platforms.mock_adapter import (
    YandexMockAdapter,
)


@pytest.mark.asyncio
async def test_yandex_mock_adapter_returns_sanitized_reviews():
    """Test that YandexMockAdapter returns reviews with hashed IDs and masked names."""
    adapter = YandexMockAdapter()

    sanitized_reviews = await adapter.get_sanitized_reviews(
        company_id="test_company", access_token="fake_token"
    )

    assert len(sanitized_reviews) == 3

    # First review: should have hashed author ID and masked name
    review1 = sanitized_reviews[0]
    assert review1.external_id == "yandex_001"
    assert review1.platform == "yandex"
    assert review1.author_hash is not None
    assert review1.author_hash.startswith("usr_")
    assert review1.author_display == "Клиент"
    assert review1.rating == 5.0
    assert "[ДАННЫЕ СКРЫТЫ]" not in review1.text  # No PII in this review

    # Second review: should have hashed author ID and masked name
    review2 = sanitized_reviews[1]
    assert review2.external_id == "yandex_002"
    assert review2.author_hash is not None
    assert review2.author_hash.startswith("usr_")
    assert review2.author_display == "Клиент"
    assert review2.rating == 2.0

    # Third review: no author ID or name, should be anonymous
    review3 = sanitized_reviews[2]
    assert review3.external_id == "yandex_003"
    assert review3.author_hash is None
    assert review3.author_display == "Анонимный клиент"
    assert review3.rating == 3.0


@pytest.mark.asyncio
async def test_yandex_mock_adapter_platform_name():
    """Test that platform_name returns correct identifier."""
    adapter = YandexMockAdapter()
    assert adapter.platform_name == "yandex"


@pytest.mark.asyncio
async def test_yandex_mock_adapter_fetch_reviews_raw():
    """Test that fetch_reviews returns raw reviews with PII."""
    adapter = YandexMockAdapter()

    raw_reviews = await adapter.fetch_reviews(
        company_id="test_company", access_token="fake_token"
    )

    assert len(raw_reviews) == 3

    # Raw reviews should contain original PII
    assert raw_reviews[0].author_raw_id == "user_12345"
    assert raw_reviews[0].author_raw_name == "Иван Петров"
    assert raw_reviews[0].text == "Отличный сервис, быстро доставили заказ. Рекомендую!"
