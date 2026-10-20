"""
External B2B API Router for Pro/Enterprise clients
Endpoints for CRM integration with secure API key authentication and RLS isolation
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select

from ..core.api_keys import verify_api_key
from ..core.database import AsyncSessionLocal
from ..core.rate_limit import RateLimitDependency
from ..core.tenant_session import get_tenant_session
from ..models import Review
from ..schemas.economics import ReviewStatus
from ..services.entitlement import enforce_reviews_quota

router = APIRouter(prefix="/api/v1/external", tags=["External API"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class RawReview(BaseModel):
    """Raw review data from external CRM"""

    text: str = Field(..., description="Review text content")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    author_name: str = Field(..., description="Author name")
    platform: str = Field(
        ..., description="Platform name (e.g., google, yelp, trustpilot)"
    )
    external_review_id: str | None = Field(
        None, description="External review ID from platform"
    )


class ReviewsBatchRequest(BaseModel):
    """Batch of raw reviews for processing"""

    reviews: list[RawReview] = Field(
        ..., min_items=1, max_items=100, description="Batch of reviews (max 100)"
    )


class ReviewStatusResponse(BaseModel):
    """Analysis status of a single review"""

    review_id: str
    status: str
    sentiment: str | None
    threat_level: int | None
    suggested_reply: str | None
    created_at: datetime
    updated_at: datetime | None


class AnalyticsResponse(BaseModel):
    """Aggregated analytics for CRM integration"""

    total_reviews: int
    sentiment: dict[str, int]
    average_rating: float
    critical_reviews: int
    resolved_reviews: int
    period_days: int


# ============================================================================
# Dependencies
# ============================================================================


async def get_external_db_session(tenant_id: UUID = Depends(verify_api_key)):
    """
    Create RLS-aware database session for external API requests.
    Uses tenant_id from API key authentication.
    """
    session = await get_tenant_session(
        factory=AsyncSessionLocal,
        tenant_id=tenant_id,
        user_id=None,  # External API has no user context
    )
    try:
        yield session
    finally:
        await session.close()


# Rate limit for external API: 100 requests per minute per tenant
external_rate_limit = RateLimitDependency(limit=100, window=60, endpoint="external_api")


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/reviews",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict[str, Any],
    summary="Submit reviews for analysis",
    description="Submit a batch of raw reviews for AI analysis. Reviews are saved and queued for background processing.",
)
async def submit_reviews(
    body: ReviewsBatchRequest,
    request: Request,
    tenant_id: UUID = Depends(verify_api_key),
    _rate_limit: None = Depends(external_rate_limit),
    session=Depends(get_external_db_session),
):
    """
    Submit a batch of reviews for processing.

    - Validates quota before accepting reviews
    - Saves reviews to DB with is_analyzed=False
    - Enqueues background task for AI analysis
    - Returns 202 Accepted with list of review_ids

    Rate limit: 100 requests per minute per tenant
    """
    # Check quota before processing
    await enforce_reviews_quota(session, tenant_id)

    # Save reviews to database
    review_ids = []
    platform_id = None  # TODO: Resolve platform_id from platform name

    for raw_review in body.reviews:
        # Create review record
        review = Review(
            company_id=tenant_id,
            platform_id=platform_id
            or tenant_id,  # Fallback to tenant_id if no platform
            platform=raw_review.platform,
            external_review_id=raw_review.external_review_id,
            author_name=raw_review.author_name,
            rating=raw_review.rating,
            text=raw_review.text,
            status=ReviewStatus.NEW,
            sentiment=None,
            threat_level=None,
            tags=[],
            financial_impact=0.0,
            si_response=None,
            auto_reply=None,
            ai_pending=True,  # Mark as pending analysis
            is_critical=False,
        )

        session.add(review)
        await session.flush()  # Get the ID without committing
        review_ids.append(str(review.id))

    await session.commit()

    # Enqueue background task for batch processing
    arq_pool = getattr(request.app.state, "redis_pool", None)
    if arq_pool is not None:
        await arq_pool.enqueue_job(
            "process_reviews_batch",
            tenant_id=str(tenant_id),
            review_ids=review_ids,
        )

    return {
        "success": True,
        "message": "Reviews accepted for processing",
        "review_ids": review_ids,
        "count": len(review_ids),
        "tenant_id": str(tenant_id),
    }


@router.get(
    "/reviews/{review_id}",
    status_code=status.HTTP_200_OK,
    response_model=ReviewStatusResponse,
    summary="Get review analysis status",
    description="Retrieve the analysis status of a specific review including sentiment, threat level, and suggested reply.",
)
async def get_review_status(
    review_id: UUID,
    tenant_id: UUID = Depends(verify_api_key),
    _rate_limit: None = Depends(external_rate_limit),
    session=Depends(get_external_db_session),
):
    """
    Get the analysis status of a specific review.

    Returns sentiment, threat_level, and suggested_reply if analysis is complete.
    RLS ensures tenant can only access their own reviews.

    Rate limit: 100 requests per minute per tenant
    """
    # Query review with RLS isolation
    result = await session.execute(
        select(Review).where(
            Review.id == review_id,
            Review.company_id == tenant_id,  # RLS ensures this
        )
    )
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    return ReviewStatusResponse(
        review_id=str(review.id),
        status=review.status.value if review.status else "unknown",
        sentiment=review.sentiment,
        threat_level=review.threat_level,
        suggested_reply=None,  # TODO: Add suggested_reply field to Review model
        created_at=review.created_at,
        updated_at=review.updated_at if hasattr(review, "updated_at") else None,
    )


@router.get(
    "/analytics",
    status_code=status.HTTP_200_OK,
    response_model=AnalyticsResponse,
    summary="Get aggregated analytics",
    description="Retrieve aggregated analytics statistics for CRM integration (same data as dashboard).",
)
async def get_analytics(
    days: int = 30,
    tenant_id: UUID = Depends(verify_api_key),
    _rate_limit: None = Depends(external_rate_limit),
    session=Depends(get_external_db_session),
):
    """
    Get aggregated analytics for CRM integration.

    Returns the same statistics as the dashboard:
    - Total reviews count
    - Sentiment distribution
    - Average rating
    - Critical reviews count
    - Resolved reviews count

    Rate limit: 100 requests per minute per tenant
    """
    # Calculate date threshold
    date_threshold = datetime.now() - timedelta(days=days)

    # Query aggregated statistics
    result = await session.execute(
        select(
            func.count(Review.id).label("total"),
            func.avg(Review.rating).label("avg_rating"),
            func.sum(case((Review.is_critical.is_(True), 1), else_=0)).label(
                "critical"
            ),
            func.sum(case((Review.status == ReviewStatus.RESOLVED, 1), else_=0)).label(
                "resolved"
            ),
        ).where(
            Review.company_id == tenant_id,
            Review.created_at >= date_threshold,
        )
    )
    stats = result.one()

    # Query sentiment distribution
    sentiment_result = await session.execute(
        select(
            Review.sentiment,
            func.count(Review.id).label("count"),
        )
        .where(
            Review.company_id == tenant_id,
            Review.created_at >= date_threshold,
        )
        .group_by(Review.sentiment)
    )
    sentiment_rows = sentiment_result.all()

    # Build sentiment dict
    sentiment_dist = {
        "positive": 0,
        "negative": 0,
        "neutral": 0,
        "unclassified": 0,
    }
    for sentiment, count in sentiment_rows:
        key = sentiment.lower() if sentiment else "unclassified"
        if key in sentiment_dist:
            sentiment_dist[key] = count

    return AnalyticsResponse(
        total_reviews=stats.total or 0,
        sentiment=sentiment_dist,
        average_rating=float(stats.avg_rating) if stats.avg_rating else 0.0,
        critical_reviews=stats.critical or 0,
        resolved_reviews=stats.resolved or 0,
        period_days=days,
    )
