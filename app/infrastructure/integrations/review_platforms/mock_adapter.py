"""Mock adapter for testing review platform integrations."""

from datetime import datetime, timezone

from app.infrastructure.integrations.review_platforms.base import (
    BaseReviewAdapter,
    RawPlatformReview,
)


class YandexMockAdapter(BaseReviewAdapter):
    """Mock Yandex Maps adapter for testing and development."""

    @property
    def platform_name(self) -> str:
        return "yandex"

    async def fetch_reviews(
        self, company_id: str, access_token: str
    ) -> list[RawPlatformReview]:
        """Return 3 fake reviews for testing."""
        return [
            RawPlatformReview(
                platform_review_id="yandex_001",
                author_raw_id="user_12345",
                author_raw_name="Иван Петров",
                text="Отличный сервис, быстро доставили заказ. Рекомендую!",
                rating=5.0,
                published_at=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            ),
            RawPlatformReview(
                platform_review_id="yandex_002",
                author_raw_id="user_67890",
                author_raw_name="Мария Сидорова",
                text="Доставка задержалась на 2 часа, еда остыла. Не рекомендую.",
                rating=2.0,
                published_at=datetime(2024, 1, 16, 14, 45, tzinfo=timezone.utc),
            ),
            RawPlatformReview(
                platform_review_id="yandex_003",
                author_raw_id=None,
                author_raw_name=None,
                text="Нормально, но можно лучше.",
                rating=3.0,
                published_at=datetime(2024, 1, 17, 9, 15, tzinfo=timezone.utc),
            ),
        ]
