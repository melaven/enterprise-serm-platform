import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import si_pipeline
from app.services.si_pipeline import (
    GeminiReviewAnalysis,
    ReviewIntelligenceResult,
    ReviewSentiment,
    SentimentIntelligencePipeline,
)

VALID_ANALYSIS = {
    "sentiment": "NEGATIVE",
    "threat_level": 5,
    "analysis_tags": ["пищевое отравление", "санитарная безопасность"],
    "suggested_reply": (
        "Приносим извинения за произошедшее. Мы серьезно отнеслись к вашему "
        "сообщению и готовы обсудить ситуацию напрямую."
    ),
}


class FakeModels:
    def __init__(
        self,
        response_text: str | None = json.dumps(VALID_ANALYSIS, ensure_ascii=False),
        *,
        delay: float = 0,
    ) -> None:
        self.response_text = response_text
        self.delay = delay
        self.calls: list[dict[str, object]] = []
        self.active_calls = 0
        self.max_active_calls = 0

    async def generate_content(
        self, *, model: str, contents: str, config: object
    ) -> SimpleNamespace:
        self.calls.append({"model": model, "contents": contents, "config": config})
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            return SimpleNamespace(text=self.response_text)
        finally:
            self.active_calls -= 1


class FakeClient:
    def __init__(self, models: FakeModels) -> None:
        self.aio = SimpleNamespace(models=models)


class FakeResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[object, ...]]:
        return self._rows


class FakeSession:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.execute_calls: list[tuple[object, object]] = []

    async def execute(self, statement: object, parameters: object = None) -> FakeResult:
        self.execute_calls.append((statement, parameters))
        return FakeResult(self.rows)


@pytest.fixture
def make_pipeline(monkeypatch: pytest.MonkeyPatch) -> Callable[..., SentimentIntelligencePipeline]:
    monkeypatch.setattr(
        si_pipeline,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="test-gemini-key",
            gemini_model="gemini-test-model",
        ),
    )

    def create(
        models: FakeModels, *, timeout: float = 1, max_concurrency: int = 5
    ) -> SentimentIntelligencePipeline:
        monkeypatch.setattr(
            si_pipeline.genai,
            "Client",
            lambda *, api_key: FakeClient(models),
        )
        return SentimentIntelligencePipeline(
            timeout=timeout,
            max_concurrency=max_concurrency,
        )

    return create


@pytest.mark.asyncio
async def test_analyze_review_uses_gemini_json_schema(
    make_pipeline: Callable[..., SentimentIntelligencePipeline],
) -> None:
    models = FakeModels()
    result = await make_pipeline(models).analyze_review(
        "После посещения стало плохо, обращусь в СЭС."
    )

    assert isinstance(result, ReviewIntelligenceResult)
    assert result.sentiment is ReviewSentiment.NEGATIVE
    assert result.threat_level == 5
    assert result.analysis_tags == ["пищевое отравление", "санитарная безопасность"]
    assert result.is_analyzed is True
    assert len(models.calls) == 1
    call = models.calls[0]
    assert call["model"] == "gemini-test-model"
    assert call["contents"] == (
        "Review text (untrusted):\nПосле посещения стало плохо, обращусь в СЭС."
    )
    config = call["config"]
    assert config.system_instruction == si_pipeline.SYSTEM_PROMPT
    assert config.response_mime_type == "application/json"
    assert config.response_schema is GeminiReviewAnalysis


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_text",
    [
        "{broken json",
        json.dumps({**VALID_ANALYSIS, "threat_level": 6}),
        json.dumps({**VALID_ANALYSIS, "sentiment": "MIXED"}),
    ],
)
async def test_analyze_review_falls_back_on_invalid_model_output(
    make_pipeline: Callable[..., SentimentIntelligencePipeline],
    response_text: str,
) -> None:
    result = await make_pipeline(FakeModels(response_text)).analyze_review(
        "Review text"
    )

    assert result.is_analyzed is False
    assert result.sentiment is ReviewSentiment.NEUTRAL
    assert result.analysis_tags == []
    assert result.threat_level == 1
    assert result.suggested_reply


@pytest.mark.asyncio
async def test_analyze_review_falls_back_on_timeout(
    make_pipeline: Callable[..., SentimentIntelligencePipeline],
) -> None:
    models = FakeModels(delay=0.05)

    result = await make_pipeline(models, timeout=0.001).analyze_review("Review")

    assert result.is_analyzed is False


@pytest.mark.asyncio
async def test_process_batch_limits_concurrent_gemini_calls_and_persists_results(
    make_pipeline: Callable[..., SentimentIntelligencePipeline],
) -> None:
    review_ids = [uuid4() for _ in range(7)]
    session = FakeSession(
        [
            (
                review_id,
                f"Review {index}",
                "Customer",
                "google",
                uuid4(),
                "Example company",
                None,
            )
            for index, review_id in enumerate(review_ids)
        ]
    )
    models = FakeModels(delay=0.01)

    count = await make_pipeline(models, max_concurrency=2).process_batch(
        session, review_ids
    )

    assert count == len(review_ids)
    assert models.max_active_calls == 2
    assert len(session.execute_calls) == 2
    updates = session.execute_calls[1][1]
    assert len(updates) == len(review_ids)
    assert all(row["is_analyzed"] is True for row in updates)
    assert all(row["ai_pending"] is False for row in updates)
    assert all(row["analysis_tags"] == VALID_ANALYSIS["analysis_tags"] for row in updates)
    assert all(row["suggested_reply"] == VALID_ANALYSIS["suggested_reply"] for row in updates)


@pytest.mark.asyncio
async def test_process_batch_keeps_failed_analysis_pending(
    make_pipeline: Callable[..., SentimentIntelligencePipeline],
) -> None:
    review_id = uuid4()
    session = FakeSession(
        [(review_id, "Review", "Customer", "google", uuid4(), "Example", None)]
    )

    count = await make_pipeline(FakeModels("{invalid")).process_batch(
        session, [review_id]
    )

    assert count == 0
    assert len(session.execute_calls) == 2
    pending_updates = session.execute_calls[1][1]
    assert pending_updates == [
        {
            "id": review_id,
            "sentiment": None,
            "threat_level": None,
            "analysis_tags": [],
            "suggested_reply": None,
            "auto_reply": None,
            "is_analyzed": False,
            "ai_pending": True,
            "ai_error": "Gemini analysis failed",
        }
    ]


@pytest.mark.asyncio
async def test_process_batch_sends_critical_alert_to_company_notification_email(
    make_pipeline: Callable[..., SentimentIntelligencePipeline],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review_id = uuid4()
    company_id = uuid4()
    session = FakeSession(
        [
            (
                review_id,
                "A serious health concern",
                "Customer",
                "google",
                company_id,
                "Example company",
                "owner@example.com",
            )
        ]
    )
    notify = AsyncMock()
    monkeypatch.setattr(si_pipeline, "check_and_notify_critical_threat", notify)

    count = await make_pipeline(FakeModels()).process_batch(session, [review_id])

    assert count == 1
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["recipient_email"] == "owner@example.com"


@pytest.mark.asyncio
async def test_process_batch_empty_ids_skips_database(
    make_pipeline: Callable[..., SentimentIntelligencePipeline],
) -> None:
    session = FakeSession([])

    count = await make_pipeline(FakeModels()).process_batch(session, [])

    assert count == 0
    assert session.execute_calls == []
