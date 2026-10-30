"""
External B2B API Router for Pro/Enterprise clients
Endpoints for CRM integration with secure API key authentication and RLS isolation
"""

from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import case, func, select

from app.api.schemas.economics import ReviewStatus
from app.application.entitlement import enforce_reviews_quota
from app.application.reviews.local_si import analyze_review_locally, build_reply_draft
from app.core.anonymizer import anonymize_author_name
from app.core.api_keys import verify_api_key
from app.core.database import AsyncSessionLocal
from app.core.rate_limit import RateLimitDependency
from app.core.tenant_session import get_tenant_session
from app.infrastructure.persistence.models import Platform, Review

router = APIRouter(prefix="/api/v1/external", tags=["External API"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class RawReview(BaseModel):
    """Authorized review input; source text is used only in local memory."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    text: str = Field(..., min_length=1, max_length=4000)
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    published_at: datetime
    platform: str = Field(
        ..., description="Authorized platform source (e.g., google_business)"
    )

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        platform = value.strip().lower()
        if platform not in {
            "2gis",
            "google",
            "google_business",
            "trustpilot",
            "yandex",
            "yelp",
        }:
            raise ValueError("Unsupported review platform")
        return platform


class ReviewsBatchRequest(BaseModel):
    """Reviews supplied by the tenant or fetched through an authorized API."""

    model_config = ConfigDict(extra="ignore")

    data_origin: Literal["customer_provided", "official_integration"]
    reviews: list[RawReview] = Field(
        ..., min_length=1, max_length=50, description="Batch of reviews (max 50)"
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
    status_code=status.HTTP_200_OK,
    response_model=dict[str, Any],
    summary="Analyze authorized reviews locally",
    description=(
        "Run local SI on customer-provided or officially integrated text. The source "
        "text is not sent to an external model or persisted."
    ),
)
async def submit_reviews(
    body: ReviewsBatchRequest,
    tenant_id: UUID = Depends(verify_api_key),
    _rate_limit: None = Depends(external_rate_limit),
    session=Depends(get_external_db_session),
):
    """Analyze authorized inputs locally; persist only fixed summaries and metrics."""
    await enforce_reviews_quota(session, tenant_id)

    review_ids = []
    review_results = []
    local_platforms: dict[str, Platform] = {}

    for raw_review in body.reviews:
        platform_name = raw_review.platform
        platform = local_platforms.get(platform_name)
        if platform is None:
            result = await session.execute(
                select(Platform).where(
                    Platform.company_id == tenant_id,
                    Platform.name == platform_name,
                )
            )
            platform = result.scalar_one_or_none()
            if platform is None:
                platform = Platform(
                    company_id=tenant_id,
                    name=platform_name,
                    monthly_views=0,
                    conversion_rate=0.0,
                    cac_on_platform=0.0,
                    average_rating=0.0,
                )
                session.add(platform)
                await session.flush()
            local_platforms[platform_name] = platform

        analysis = analyze_review_locally(raw_review.text, raw_review.rating)
        review = Review(
            company_id=tenant_id,
            platform_id=platform.id,
            platform=platform_name,
            author_name=anonymize_author_name(),
            rating=raw_review.rating,
            text=analysis.summary,
            status=ReviewStatus.NEW,
            sentiment=analysis.sentiment,
            threat_level=analysis.threat_level,
            tags=list(analysis.tags),
            analysis_tags=list(analysis.tags),
            financial_impact=0.0,
            si_response=None,
            auto_reply=None,
            suggested_reply=None,
            ai_pending=False,
            is_analyzed=True,
            is_critical=analysis.is_critical,
            ai_error=None,
            created_at=raw_review.published_at,
        )

        session.add(review)
        await session.flush()  # Get the ID without committing
        review_ids.append(str(review.id))
        review_results.append(
            {
                "review_id": str(review.id),
                "sentiment": analysis.sentiment,
                "threat_level": analysis.threat_level,
                "reply_draft": analysis.reply_draft,
            }
        )

    await session.commit()

    return {
        "success": True,
        "message": (
            "Authorized reviews analyzed locally; only non-source summaries "
            "and metrics were stored"
        ),
        "review_ids": review_ids,
        "results": review_results,
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
        suggested_reply=build_reply_draft(review.sentiment),
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
