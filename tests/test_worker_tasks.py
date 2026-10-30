"""Tests for ARQ worker tasks."""

from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.infrastructure.integrations.review_platforms.base import SanitizedReview
from app.infrastructure.queue.worker.tasks import process_company_reviews


@pytest.mark.asyncio
async def test_process_company_reviews_success():
    """Test that process_company_reviews fetches and logs reviews."""
    # Mock the adapter
    mock_adapter = MagicMock()
    mock_adapter.platform_name = "yandex"
    
    # Create mock sanitized reviews
    mock_reviews = [
        SanitizedReview(
            external_id="yandex_001",
            platform="yandex",
            author_hash="usr_abc123",
            author_display="Клиент",
            text="Отличный сервис",
            rating=5.0,
            published_at=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        ),
        SanitizedReview(
            external_id="yandex_002",
            platform="yandex",
            author_hash="usr_def456",
            author_display="Клиент",
            text="Хорошо",
            rating=4.0,
            published_at=datetime(2024, 1, 16, 14, 45, tzinfo=timezone.utc),
        ),
    ]
    
    mock_adapter.get_sanitized_reviews = AsyncMock(return_value=mock_reviews)
    
    # Mock get_adapter to return our mock adapter
    with patch(
        "app.infrastructure.queue.worker.tasks.get_adapter",
        return_value=mock_adapter
    ):
        result = await process_company_reviews(
            ctx={},
            company_id="test_company",
            platform="yandex",
            access_token="fake_token"
        )
    
    # Verify the adapter was called correctly
    mock_adapter.get_sanitized_reviews.assert_called_once_with(
        "test_company",
        "fake_token"
    )
    
    # Verify the result
    assert result["processed"] == 2
    assert result["company_id"] == "test_company"
    assert result["platform"] == "yandex"


@pytest.mark.asyncio
async def test_process_company_reviews_unsupported_platform():
    """Test that process_company_reviews raises error for unsupported platform."""
    with patch(
        "app.infrastructure.queue.worker.tasks.get_adapter",
        side_effect=ValueError("Unsupported platform 'unknown'")
    ):
        with pytest.raises(ValueError, match="Unsupported platform"):
            await process_company_reviews(
                ctx={},
                company_id="test_company",
                platform="unknown",
                access_token="fake_token"
            )


@pytest.mark.asyncio
async def test_process_company_reviews_adapter_error():
    """Test that process_company_reviews handles adapter errors gracefully."""
    # Mock the adapter to raise an error
    mock_adapter = MagicMock()
    mock_adapter.get_sanitized_reviews = AsyncMock(
        side_effect=Exception("API error")
    )
    
    with patch(
        "app.infrastructure.queue.worker.tasks.get_adapter",
        return_value=mock_adapter
    ):
        with pytest.raises(Exception, match="API error"):
            await process_company_reviews(
                ctx={},
                company_id="test_company",
                platform="yandex",
                access_token="fake_token"
            )
