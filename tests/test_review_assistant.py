"""
Tests for SI Assistant API endpoints.
Tests cover tenant isolation, reply generation, and moderation status transitions.
"""

from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.economics import ReplyModerationStatus, ReviewStatus
from app.application.reviews.service import ReviewApplicationService
from app.infrastructure.persistence.models.economics import Review
from app.infrastructure.persistence.models.review_reply import ReviewReply


@pytest.mark.asyncio
async def test_review_service_uses_injected_session() -> None:
    session = AsyncMock()
    result = Mock()
    result.all.return_value = []
    session.execute.return_value = result
    service = ReviewApplicationService(
        session=session,
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    reviews = await service.list_assistant_reviews("all", None, 50, 0)

    assert reviews == []
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_assistant_reviews_rls_isolation(
    client: AsyncClient,
    company_id,
    other_company_id,
    db_session: AsyncSession,
):
    """Test that assistant reviews endpoint respects RLS tenant isolation."""
    # Create a review for the first company
    review1 = Review(
        company_id=company_id,
        platform_id=company_id,  # Simplified - in real test would create platform
        platform="google",
        author_name="Customer 1",
        rating=5,
        text="Great service!",
        moderation_status=ReplyModerationStatus.NEW,
    )
    db_session.add(review1)

    # Create a review for the other company
    review2 = Review(
        company_id=other_company_id,
        platform_id=other_company_id,
        platform="google",
        author_name="Customer 2",
        rating=3,
        text="Average experience",
        moderation_status=ReplyModerationStatus.NEW,
    )
    db_session.add(review2)
    await db_session.commit()

    # First company should only see their own review
    response = await client.get("/api/v1/reviews/assistant")
    assert response.status_code == 200
    reviews = response.json()
    assert len(reviews) == 1
    assert reviews[0]["text"] == "Great service!"

    # Other company should only see their own review
    # Note: This would require a separate client with other_company_id auth


@pytest.mark.asyncio
async def test_get_assistant_reviews_filter_negative(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    """Test filtering reviews by negative sentiment."""
    # Create negative review
    review_neg = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=2,
        text="Terrible service",
        sentiment="NEGATIVE",
        moderation_status=ReplyModerationStatus.NEW,
    )
    db_session.add(review_neg)

    # Create positive review
    review_pos = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=5,
        text="Great service",
        sentiment="POSITIVE",
        moderation_status=ReplyModerationStatus.NEW,
    )
    db_session.add(review_pos)
    await db_session.commit()

    # Filter by negative
    response = await client.get("/api/v1/reviews/assistant?filter=negative")
    assert response.status_code == 200
    reviews = response.json()
    assert len(reviews) == 1
    assert reviews[0]["sentiment"] == "NEGATIVE"


@pytest.mark.asyncio
async def test_get_assistant_reviews_filter_unanswered(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    """Test filtering reviews by unanswered status."""
    # Create unanswered review
    review_unanswered = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Average",
        moderation_status=ReplyModerationStatus.NEW,
    )
    db_session.add(review_unanswered)

    # A drafted reply is still awaiting moderation, so it remains unanswered.
    review_answered = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=4,
        text="Good",
        moderation_status=ReplyModerationStatus.DRAFTED,
    )
    db_session.add(review_answered)
    await db_session.flush()
    db_session.add(
        ReviewReply(
            review_id=review_answered.id,
            company_id=company_id,
            reply_text="Thank you!",
        )
    )
    await db_session.commit()

    # Filter by unanswered
    response = await client.get("/api/v1/reviews/assistant?filter=unanswered")
    assert response.status_code == 200
    reviews = response.json()
    assert {review["status"] for review in reviews} == {
        ReplyModerationStatus.NEW.value,
        ReplyModerationStatus.DRAFTED.value,
    }


@pytest.mark.asyncio
async def test_generate_reply_uses_encrypted_source_without_persisting_reply(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Generate from encrypted source and mark a draft without storing its text."""
    from app.application.reviews import service as review_service
    from app.core import dependencies
    from app.infrastructure.persistence.models.review_analysis_payload import (
        ReviewAnalysisPayload,
    )

    source_text = "Поддержка ответила быстро и помогла решить проблему."
    review = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Нейтральный отзыв; оценка 3/5.",
        tags=["SERVICE"],
        is_analyzed=True,
        moderation_status=ReplyModerationStatus.NEW,
    )
    db_session.add(review)
    await db_session.flush()
    payload = ReviewAnalysisPayload(
        review_id=review.id,
        company_id=company_id,
        encrypted_text="encrypted-review",
    )
    db_session.add(payload)
    await db_session.commit()

    class FakeAnalyzer:
        def __init__(self) -> None:
            self.arguments = None
            self.closed = False

        async def generate_reply(
            self, review_text: str, tags: list[str], rating: int
        ) -> str:
            self.arguments = (review_text, tags, rating)
            return (
                "Благодарим за отзыв. Рады, что наша поддержка помогла решить вопрос."
            )

        async def close(self) -> None:
            self.closed = True

    analyzer = FakeAnalyzer()
    monkeypatch.setattr(dependencies, "create_openai_analyzer", lambda: analyzer)
    monkeypatch.setattr(review_service, "decrypt_token", lambda encrypted: source_text)

    response = await client.post(f"/api/v1/reviews/{review.id}/generate-reply")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "review_id": str(review.id),
        "suggested_reply": (
            "Благодарим за отзыв. Рады, что наша поддержка помогла решить вопрос."
        ),
    }
    assert analyzer.arguments == (source_text, ["SERVICE"], 3)
    assert analyzer.closed

    await db_session.refresh(review)
    assert review.moderation_status == ReplyModerationStatus.DRAFTED
    assert review.suggested_reply is None
    assert review.text == "Нейтральный отзыв; оценка 3/5."
    assert await db_session.get(ReviewAnalysisPayload, review.id) is not None
    assert await db_session.get(ReviewReply, review.id) is None


@pytest.mark.asyncio
async def test_generate_reply_requires_retained_encrypted_source(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Do not generate a low-quality response from the safe summary."""
    from app.core import dependencies

    review = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Average service",
        is_analyzed=True,
        moderation_status=ReplyModerationStatus.PENDING_MODERATION,
    )
    db_session.add(review)
    await db_session.commit()

    class UnusedAnalyzer:
        closed = False

        async def generate_reply(
            self, review_text: str, tags: list[str], rating: int
        ) -> str:
            pytest.fail("Analyzer must not generate a reply without source text")

        async def close(self) -> None:
            self.closed = True

    analyzer = UnusedAnalyzer()
    monkeypatch.setattr(dependencies, "create_openai_analyzer", lambda: analyzer)

    response = await client.post(f"/api/v1/reviews/{review.id}/generate-reply")
    assert response.status_code == 409
    assert response.json()["error"]["status_code"] == 409
    assert review.suggested_reply is None
    assert analyzer.closed


@pytest.mark.asyncio
async def test_generate_reply_rls_denies_access(
    client: AsyncClient,
    other_company_id,
    db_session: AsyncSession,
):
    """Test that generate reply denies access to other tenant's review."""
    # Create review for other company
    review = Review(
        company_id=other_company_id,
        platform_id=other_company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Average service",
        moderation_status=ReplyModerationStatus.NEW,
    )
    db_session.add(review)
    await db_session.commit()

    response = await client.post(f"/api/v1/reviews/{review.id}/generate-reply")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_review_encrypts_source_and_enqueues_analysis(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.application.reviews import service as review_service
    from app.infrastructure.persistence.models.review_analysis_payload import (
        ReviewAnalysisPayload,
    )
    from app.main import app

    source_text = "A confidential customer review."
    monkeypatch.setattr(
        review_service, "encrypt_token", lambda text: "encrypted-source"
    )

    class FakeQueue:
        def __init__(self) -> None:
            self.job = None

        async def enqueue_job(self, function_name: str, *args, **kwargs) -> None:
            self.job = (function_name, args, kwargs)

    queue = FakeQueue()
    monkeypatch.setattr(app.state, "arq_pool", queue, raising=False)

    response = await client.post(
        "/api/v1/reviews/",
        json={
            "platform_id": str(company_id),
            "rating": 2,
            "text": source_text,
            "author_name": "Customer",
        },
    )

    assert response.status_code == 201
    review_id = UUID(response.json()["id"])
    stored_review = await db_session.get(Review, review_id)
    assert stored_review is not None
    assert source_text not in stored_review.text
    payload = await db_session.get(ReviewAnalysisPayload, review_id)
    assert payload is not None
    assert payload.encrypted_text == "encrypted-source"
    assert queue.job is not None
    assert queue.job[0] == "process_review_task"
    assert queue.job[1] == (str(review_id), str(company_id))


@pytest.mark.asyncio
async def test_submit_moderation_fsm_transition_drafted_to_pending(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    """Test FSM transition: drafted -> pending_moderation when submitting."""
    review = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Average service",
        moderation_status=ReplyModerationStatus.DRAFTED,
    )
    db_session.add(review)
    await db_session.commit()

    # Submit for moderation
    response = await client.post(
        f"/api/v1/reviews/{review.id}/submit-moderation",
        json={"reply_text": "Final reply text"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == ReplyModerationStatus.PENDING_MODERATION.value

    # Verify status transition
    await db_session.refresh(review)
    assert review.moderation_status == ReplyModerationStatus.PENDING_MODERATION
    assert review.suggested_reply is None
    saved_reply = await db_session.get(ReviewReply, review.id)
    assert saved_reply is not None
    assert saved_reply.reply_text == "Final reply text"
    assert data["reply_text"] == "Final reply text"


@pytest.mark.asyncio
async def test_approve_moderation_updates_status_without_writing_to_review(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    review = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Average service",
        moderation_status=ReplyModerationStatus.PENDING_MODERATION,
    )
    db_session.add(review)
    await db_session.flush()
    db_session.add(
        ReviewReply(
            review_id=review.id,
            company_id=company_id,
            reply_text="Thank you for your feedback.",
        )
    )
    await db_session.commit()

    response = await client.post(f"/api/v1/reviews/{review.id}/approve-moderation")

    assert response.status_code == 200
    assert response.json()["status"] == ReplyModerationStatus.APPROVED.value
    assert response.json()["reply_text"] == "Thank you for your feedback."
    await db_session.refresh(review)
    assert review.moderation_status == ReplyModerationStatus.APPROVED
    assert review.suggested_reply is None


@pytest.mark.asyncio
async def test_update_review_status_stores_response_outside_reviews(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    review = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Average service",
        status=ReviewStatus.NEW,
    )
    db_session.add(review)
    await db_session.commit()

    response = await client.put(
        f"/api/v1/reviews/{review.id}/status",
        params={
            "new_status": ReviewStatus.RESOLVED.value,
            "si_response": "We have resolved the issue.",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["has_response"] is True
    await db_session.refresh(review)
    assert review.status == ReviewStatus.RESOLVED
    assert review.si_response is None
    saved_reply = await db_session.get(ReviewReply, review.id)
    assert saved_reply is not None
    assert saved_reply.reply_text == "We have resolved the issue."


@pytest.mark.asyncio
async def test_submit_moderation_fails_from_non_drafted_status(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    """Test that submit moderation fails from non-drafted status (FSM validation)."""
    review = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Average service",
        moderation_status=ReplyModerationStatus.NEW,
    )
    db_session.add(review)
    await db_session.commit()

    # Try to submit from new status
    response = await client.post(
        f"/api/v1/reviews/{review.id}/submit-moderation",
        json={"reply_text": "Reply text"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "BusinessLogicError"


@pytest.mark.asyncio
async def test_submit_moderation_validates_text_length(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    """Test that submit moderation validates reply text length."""
    review = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Average service",
        moderation_status=ReplyModerationStatus.DRAFTED,
    )
    db_session.add(review)
    await db_session.commit()

    # Empty text should fail
    response = await client.post(
        f"/api/v1/reviews/{review.id}/submit-moderation",
        json={"reply_text": ""},
    )
    assert response.status_code == 422  # Validation error

    # Text too long should fail
    response = await client.post(
        f"/api/v1/reviews/{review.id}/submit-moderation",
        json={"reply_text": "a" * 4001},
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_submit_moderation_rls_denies_access(
    client: AsyncClient,
    other_company_id,
    db_session: AsyncSession,
):
    """Test that submit moderation denies access to other tenant's review."""
    review = Review(
        company_id=other_company_id,
        platform_id=other_company_id,
        platform="google",
        author_name="Customer",
        rating=3,
        text="Average service",
        moderation_status=ReplyModerationStatus.DRAFTED,
    )
    db_session.add(review)
    await db_session.commit()

    # Try to submit for other company's review
    response = await client.post(
        f"/api/v1/reviews/{review.id}/submit-moderation",
        json={"reply_text": "Reply text"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_assistant_prompts_prevent_injection(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    """Test that system prompts are server-side and prevent injection."""
    from app.core.assistant_prompts import get_system_prompt

    # Valid tones should work
    for tone in ["official", "friendly", "crisis"]:
        prompt = get_system_prompt(tone)
        assert prompt is not None
        assert "You are" in prompt  # System prompt starts with role definition

    # Invalid tone should raise ValueError
    with pytest.raises(ValueError, match="Invalid tone"):
        get_system_prompt("malicious_tone")
