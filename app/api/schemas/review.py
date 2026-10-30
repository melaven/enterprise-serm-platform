"""
Pydantic schemas for Review API validation and serialization.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    """Schema for creating a new review."""

    platform_id: UUID = Field(
        ..., description="ID of the platform where the review was posted"
    )
    author_name: str = Field(
        ..., min_length=1, max_length=255, description="Name of the review author"
    )
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    text: str = Field(
        ..., min_length=1, max_length=10000, description="Review text content"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "platform_id": "123e4567-e89b-12d3-a456-426614174000",
                "author_name": "John Doe",
                "rating": 4,
                "text": "Great service, very professional staff!",
            }
        }


class ReviewResponse(BaseModel):
    """Schema for returning review data with single FSM state field."""

    id: UUID
    platform_id: UUID
    company_id: UUID
    branch_id: UUID | None
    platform: str | None
    author_name: str
    rating: int
    text: str
    state: str = Field(..., description="FSM state of the review")
    sentiment: str | None
    threat_level: int | None
    suggested_reply: str | None
    auto_reply: str | None
    financial_impact: float
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "platform_id": "123e4567-e89b-12d3-a456-426614174000",
                "company_id": "123e4567-e89b-12d3-a456-426614174000",
                "branch_id": None,
                "platform": "google",
                "author_name": "John Doe",
                "rating": 4,
                "text": "Great service, very professional staff!",
                "state": "new",
                "sentiment": "POSITIVE",
                "threat_level": None,
                "suggested_reply": None,
                "auto_reply": None,
                "financial_impact": 0.0,
                "created_at": "2026-10-25T19:00:00Z",
                "updated_at": None,
            }
        }
