from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.domain.billing import QuotaExceededError
from app.domain.reviews.state import ReviewState
from app.infrastructure.queue.worker import worker
from app.workers.tasks import ingestion


@pytest.mark.asyncio
async def test_process_review_ingestion_sanitizes_before_persisting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    session = AsyncMock()
    saved_batches: list[list[dict[str, object]]] = []

    class _Repository:
        def __init__(self, _session: object) -> None:
            pass

        async def bulk_upsert_reviews(self, batch: list[dict[str, object]]) -> int:
            saved_batches.append(batch)
            return len(batch)

    monkeypatch.setattr(
        ingestion, "get_tenant_session", AsyncMock(return_value=session)
    )
    monkeypatch.setattr(ingestion, "BulkReviewRepository", _Repository)

    result = await ingestion.process_review_ingestion(
        {},
        str(tenant_id),
        {
            "platform": "yandex",
            "external_id": "raw-review-id",
            "raw_author": "Иван Петров",
            "raw_text": "Мой телефон 89001234567",
            "rating": 5,
            "published_at": datetime(2026, 10, 30, tzinfo=timezone.utc).isoformat(),
        },
    )

    assert result == {"tenant_id": str(tenant_id), "processed": 1}
    sanitized = saved_batches[0][0]
    assert sanitized["author_display"] == "Клиент"
    assert str(sanitized["author_hash"]).startswith("usr_")
    assert str(sanitized["external_id"]).startswith("usr_")
    assert "Иван Петров" not in str(sanitized)
    assert "89001234567" not in str(sanitized["clean_text"])
    session.commit.assert_awaited_once()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_review_task_blocks_llm_when_quota_is_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    review_id = uuid4()
    review = SimpleNamespace(
        id=review_id,
        company_id=tenant_id,
        state=ReviewState.NEW,
        rating=3,
        ai_error=None,
    )
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: review)
    session.scalar.return_value = SimpleNamespace(encrypted_text="encrypted-review")
    analyzer_factory = Mock()
    quota_service = SimpleNamespace(
        check_quota=AsyncMock(side_effect=QuotaExceededError("Token quota exceeded"))
    )

    monkeypatch.setattr(worker, "get_tenant_session", AsyncMock(return_value=session))
    monkeypatch.setattr(worker, "BillingService", Mock(return_value=quota_service))
    monkeypatch.setattr(worker, "create_openai_analyzer", analyzer_factory)
    monkeypatch.setattr(worker, "decrypt_token", lambda _value: "review text")

    result = await worker.process_review_task({}, str(review_id), str(tenant_id))

    assert result == {
        "review_id": str(review_id),
        "state": ReviewState.ANALYSIS_FAILED.value,
    }
    assert review.state == ReviewState.ANALYSIS_FAILED
    assert review.ai_error == "Token quota exceeded"
    session.commit.assert_awaited_once()
    session.close.assert_awaited_once()
    analyzer_factory.assert_not_called()
    quota_service.check_quota.assert_awaited_once_with(tenant_id)
