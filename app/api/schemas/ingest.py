"""Contracts for asynchronous review ingestion."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReviewIngestPayload(BaseModel):
    """Untrusted review data accepted for background sanitization."""

    model_config = ConfigDict(extra="forbid")

    platform: str = Field(min_length=1, max_length=255)
    external_id: str = Field(min_length=1, max_length=255)
    raw_author: str | None = Field(default=None, max_length=255)
    raw_text: str = Field(min_length=1, max_length=10000)
    rating: int = Field(ge=1, le=5)
    published_at: datetime


class ReviewIngestResponse(BaseModel):
    """Acknowledgement for a queued review-ingestion job."""

    status: Literal["accepted"] = "accepted"
    job_id: UUID
    tenant_id: UUID
    queued_at: datetime
