from datetime import datetime, timezone

import pytest

from app.core.pii import PIISanitizer
from app.infrastructure.integrations.review_platforms.base import (
    BaseReviewAdapter,
    RawPlatformReview,
)


class _FakeReviewAdapter(BaseReviewAdapter):
    @property
    def platform_name(self) -> str:
        return "google"

    async def fetch_reviews(
        self, company_id: str, access_token: str
    ) -> list[RawPlatformReview]:
        assert company_id == "company-1"
        assert access_token == "token"
        return [
            RawPlatformReview(
                platform_review_id="review-1",
                author_raw_id="user-1",
                author_raw_name="Иван Петров",
                text="Напишите ivan@example.com, телефон 89001234567",
                rating=5,
                published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            RawPlatformReview(
                platform_review_id="review-2",
                text="Хорошее обслуживание",
                rating=4,
                published_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        ]


@pytest.mark.asyncio
async def test_get_sanitized_reviews_removes_author_and_text_pii() -> None:
    reviews = await _FakeReviewAdapter().get_sanitized_reviews("company-1", "token")

    assert len(reviews) == 2
    assert reviews[0].external_id == "review-1"
    assert reviews[0].platform == "google"
    assert reviews[0].author_hash == PIISanitizer.hash_user_id("google", "user-1")
    assert reviews[0].author_display == "Клиент"
    assert "Иван Петров" not in str(reviews[0].model_dump())
    assert "ivan@example.com" not in reviews[0].text
    assert "89001234567" not in reviews[0].text
    assert reviews[1].author_hash is None
    assert reviews[1].author_display == "Анонимный клиент"
