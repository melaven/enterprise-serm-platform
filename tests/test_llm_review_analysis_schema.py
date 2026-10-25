import pytest
from pydantic import ValidationError

from app.schemas.ai import LLMReviewAnalysisResult, Sentiment, system_prompt


def test_llm_review_analysis_result_validates_and_normalizes_output() -> None:
    result = LLMReviewAnalysisResult(
        sentiment="NEGATIVE",
        threat_level=8,
        is_critical=True,
        tags=["  доставка  ", "доставка", "хамство"],
        suggested_reply="  Благодарим за обратную связь. Мы разберёмся.  ",
    )

    assert result.sentiment is Sentiment.NEGATIVE
    assert result.threat_level == 8
    assert result.tags == ["доставка", "хамство"]
    assert result.suggested_reply == "Благодарим за обратную связь. Мы разберёмся."


@pytest.mark.parametrize("threat_level", [0, 11])
def test_llm_review_analysis_result_rejects_invalid_threat_level(
    threat_level: int,
) -> None:
    with pytest.raises(ValidationError):
        LLMReviewAnalysisResult(
            sentiment=Sentiment.NEUTRAL,
            threat_level=threat_level,
            is_critical=False,
            tags=["другое"],
        )


def test_llm_review_analysis_result_rejects_extra_fields_and_reply_contacts() -> None:
    with pytest.raises(ValidationError):
        LLMReviewAnalysisResult(
            sentiment=Sentiment.POSITIVE,
            threat_level=1,
            is_critical=False,
            tags=["цена"],
            extra="unexpected",
        )

    with pytest.raises(ValidationError):
        LLMReviewAnalysisResult(
            sentiment=Sentiment.POSITIVE,
            threat_level=1,
            is_critical=False,
            tags=["цена"],
            suggested_reply="Напишите нам на support@example.com",
        )


def test_system_prompt_requires_schema_and_untrusted_review_handling() -> None:
    assert "LLMReviewAnalysisResult" in system_prompt
    assert "только один JSON-объект" in system_prompt
    assert "недоверенными данными" in system_prompt
