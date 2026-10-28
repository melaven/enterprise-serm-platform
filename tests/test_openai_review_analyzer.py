from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.services.openai_review_analyzer import (
    OpenAIReviewAnalyzer,
    ReviewAnalysisSchema,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 1), (1, 1), (3, 3), (5, 5), (10, 5)],
)
def test_review_analysis_schema_clamps_threat_level(
    value: int, expected: int
) -> None:
    result = ReviewAnalysisSchema(
        sentiment="NEUTRAL",
        threat_level=value,
        tags=[],
        suggested_reply="Благодарим за отзыв. Мы изучим замечания и проверим описанную ситуацию.",
    )

    assert result.threat_level == expected


def test_review_analysis_schema_accepts_only_privacy_safe_tags() -> None:
    result = ReviewAnalysisSchema(
        sentiment="NEUTRAL",
        threat_level=3,
        tags=["SERVICE", "PRICING", "SERVICE"],
        suggested_reply="Благодарим за отзыв. Мы изучим замечания и проверим описанную ситуацию.",
    )

    assert result.tags == ["SERVICE", "PRICING"]


def test_review_analysis_schema_is_compatible_with_groq_strict_outputs() -> None:
    schema = ReviewAnalysisSchema.model_json_schema()

    assert schema["additionalProperties"] is False
    assert "tags" in schema["required"]


@pytest.mark.parametrize("tag", ["service", "QUALITY", "STAFF", "unknown"])
def test_review_analysis_schema_rejects_tags_outside_allowlist(tag: str) -> None:
    with pytest.raises(ValidationError):
        ReviewAnalysisSchema(
            sentiment="NEUTRAL",
            threat_level=3,
            tags=[tag],
            suggested_reply="Благодарим за отзыв. Мы изучим замечания и проверим описанную ситуацию.",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rating", "expected"),
    [(1, 5), (2, 4), (3, 1), (5, 1), (None, 1)],
)
async def test_fallback_analysis_respects_database_threat_range(
    rating: int | None, expected: int
) -> None:
    analyzer = OpenAIReviewAnalyzer(api_key="test-key")
    try:
        result = analyzer._fallback_analysis("Отзыв о платформе.", rating)
    finally:
        await analyzer.close()

    assert 1 <= result.threat_level <= 5
    assert result.threat_level == expected


@pytest.mark.asyncio
async def test_fallback_analysis_uses_only_database_allowed_tags() -> None:
    analyzer = OpenAIReviewAnalyzer(api_key="test-key")
    try:
        result = analyzer._fallback_analysis("Отзыв о платформе.", 3)
    finally:
        await analyzer.close()

    assert result.tags == []


@pytest.mark.asyncio
async def test_generate_reply_uses_review_context_and_returns_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyzer = OpenAIReviewAnalyzer(api_key="test-key")
    create_completion = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="  Благодарим за подробный отзыв.  "
                    )
                )
            ]
        )
    )
    monkeypatch.setattr(analyzer.client.chat.completions, "create", create_completion)

    try:
        reply = await analyzer.generate_reply(
            "Поддержка помогла быстро.", ["SERVICE"], 5
        )
    finally:
        await analyzer.close()

    assert reply == "Благодарим за подробный отзыв."
    call = create_completion.await_args.kwargs
    assert call["model"] == analyzer.model
    assert "Review rating: 5/5" in call["messages"][1]["content"]
    assert "SERVICE" in call["messages"][1]["content"]
    assert "Поддержка помогла быстро." in call["messages"][1]["content"]
