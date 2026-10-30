from app.application.reviews.local_si import analyze_review_locally


def test_local_si_returns_only_allowlisted_analytics() -> None:
    result = analyze_review_locally(
        "Иванов звонил по номеру +7 999 123-45-67. Доставка опоздала.",
        rating=2,
    )

    assert result.sentiment == "NEGATIVE"
    assert result.tags == ("DELIVERY",)
    assert result.summary == "Негативный отзыв; оценка 2/5."
    assert "Иванов" not in result.summary
    assert "+7 999 123-45-67" not in result.summary
