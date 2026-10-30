from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.core.pii import PIISanitizer
from app.infrastructure.database.repositories.reviews import ReviewRepository
from app.infrastructure.integrations.review_platforms.base import SanitizedReview


class _Result:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[object]:
        return [self.value]


async def test_save_reviews_hashes_external_id_and_inserts_conflict_safe_values() -> (
    None
):
    company_id = uuid4()
    platform_id = uuid4()
    review_id = uuid4()
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_Result(platform_id), _Result(review_id)])
    repository = ReviewRepository(db)
    review = SanitizedReview(
        external_id="source-review-123",
        platform="google",
        author_hash=PIISanitizer.hash_user_id("google", "source-user-1"),
        author_display="Иван Петров",
        text="Свяжитесь: user@example.com или 89001234567",
        rating=5,
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    inserted = await repository.save_reviews(company_id, [review])

    assert inserted == 1
    statement = db.execute.await_args_list[1].args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert "ON CONFLICT (company_id, platform, external_id)" in str(compiled)
    assert "DO NOTHING" in str(compiled)
    assert compiled.params["external_id_m0"] == PIISanitizer.hash_user_id(
        "google", "source-review-123"
    )
    assert review.author_hash is not None
    assert compiled.params["author_hash_m0"] == PIISanitizer.hash_user_id(
        "google", review.author_hash
    )
    assert compiled.params["author_display_m0"] == "Клиент"
    assert compiled.params["author_name_m0"] == "Автор отзыва"
    assert "user@example.com" not in compiled.params["text_m0"]
    assert "89001234567" not in compiled.params["text_m0"]


async def test_save_reviews_empty_batch_skips_database() -> None:
    db = AsyncMock()

    assert await ReviewRepository(db).save_reviews(uuid4(), []) == 0
    db.execute.assert_not_awaited()
