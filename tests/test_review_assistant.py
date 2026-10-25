"""
Tests for SI Assistant API endpoints.
Tests cover RLS validation and FSM status transitions.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.economics import Review
from app.schemas.economics import ReplyModerationStatus


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

    # Create answered review (drafted)
    review_answered = Review(
        company_id=company_id,
        platform_id=company_id,
        platform="google",
        author_name="Customer",
        rating=4,
        text="Good",
        suggested_reply="Thank you!",
        moderation_status=ReplyModerationStatus.DRAFTED,
    )
    db_session.add(review_answered)
    await db_session.commit()

    # Filter by unanswered
    response = await client.get("/api/v1/reviews/assistant?filter=unanswered")
    assert response.status_code == 200
    reviews = response.json()
    assert len(reviews) == 1
    assert reviews[0]["status"] == ReplyModerationStatus.NEW.value


@pytest.mark.asyncio
async def test_generate_reply_fsm_transition_new_to_drafted(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    """Test FSM transition: new -> drafted when generating reply."""
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

    # Generate reply
    response = await client.post(
        f"/api/v1/reviews/{review.id}/generate-reply",
        json={"tone": "official"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "draft_text" in data

    # Verify status transition
    await db_session.refresh(review)
    assert review.moderation_status == ReplyModerationStatus.DRAFTED
    assert review.suggested_reply is not None


@pytest.mark.asyncio
async def test_generate_reply_fails_from_non_new_status(
    client: AsyncClient,
    company_id,
    db_session: AsyncSession,
):
    """Test that generate reply fails from non-new status (FSM validation)."""
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

    # Try to generate reply from drafted status
    response = await client.post(
        f"/api/v1/reviews/{review.id}/generate-reply",
        json={"tone": "official"},
    )
    assert response.status_code == 400
    assert "Cannot generate reply" in response.json()["detail"]


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

    # Try to generate reply for other company's review
    response = await client.post(
        f"/api/v1/reviews/{review.id}/generate-reply",
        json={"tone": "official"},
    )
    assert response.status_code == 404


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
        suggested_reply="Draft reply",
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
    assert review.suggested_reply == "Final reply text"


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
    assert "Cannot submit moderation" in response.json()["detail"]


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
