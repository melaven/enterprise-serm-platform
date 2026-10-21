from uuid import uuid4

from app.core.anonymizer import anonymize_author_name
from app.core.review_privacy import safe_review_summary
from app.schemas.economics import ReviewBase


def test_author_label_is_constant_and_does_not_encode_identity() -> None:
    assert anonymize_author_name("Jane Doe", "author-123") == "Автор отзыва"
    assert anonymize_author_name("Иван") == "Автор отзыва"


def test_economics_review_schema_defaults_profile_urls_to_null() -> None:
    review = ReviewBase(
        platform_id=uuid4(),
        author_name="Клиент #123456",
        rating=4,
        text="Review text",
    )

    assert review.author_avatar_url is None
    assert review.author_profile_url is None


def test_review_summary_uses_only_controlled_analytics_values() -> None:
    summary = safe_review_summary(2, "NEGATIVE", "SERVICE")

    assert summary == "Негативный отзыв о теме «обслуживание»; оценка 2/5."
    assert "Иван" not in summary
    assert "79991234567" not in summary


def test_review_summary_ignores_unknown_free_text_categories() -> None:
    assert safe_review_summary(4, "NEUTRAL", "Jane Doe") == (
        "Нейтральный отзыв; оценка 4/5."
    )


def test_review_summary_ignores_unknown_free_text_sentiment() -> None:
    assert safe_review_summary(4, "Jane Doe") == "Отзыв; оценка 4/5."
