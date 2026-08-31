import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.database import get_db, LNRReviewLog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any

from app.app.schemas.reviews import ReviewWebhook


router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.post("/webhook", status_code=status.HTTP_201_CREATED)
async def receive_review(
    payload: ReviewWebhook,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    # Check if review already exists
    result = await db.execute(
        select(LNRReviewLog).where(
            LNRReviewLog.external_review_id == payload.external_review_id
        )
    )
    existing_review = result.scalar_one_or_none()
    
    if existing_review:
        return {
            "message": "Review already exists",
            "external_review_id": payload.external_review_id,
            "status": "skipped"
        }
    
    # Calculate sentiment
    sentiment = "negative" if payload.rating <= 3 else "positive"
    
    # Create new review log entry
    new_review = LNRReviewLog(
        company_id=payload.company_id,
        platform_id=payload.platform_id,
        external_review_id=payload.external_review_id,
        author_name=payload.author_name,
        rating=payload.rating,
        review_text=payload.review_text,
        sentiment=sentiment,
        processing_status="new"
    )
    
    db.add(new_review)
    await db.commit()
    await db.refresh(new_review)
    
    return {
        "message": "Review successfully saved",
        "review_id": new_review.id,
        "external_review_id": payload.external_review_id,
        "sentiment": sentiment,
        "processing_status": new_review.processing_status,
        "created_at": new_review.created_at.isoformat() if new_review.created_at else None
    }