from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.domain.reviews.risk import ResponseStrategyType, RiskLevel


class CrisisDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_type: ResponseStrategyType
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, content: str) -> str:
        normalized = content.strip()
        if not normalized:
            raise ValueError("Draft content must not be blank")
        return normalized


class CrisisEscalationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_level: RiskLevel
    drafts: list[CrisisDraftInput] = Field(min_length=3, max_length=3)
    risk_signals: list[str] = Field(default_factory=list)
    risk_metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )

    @field_validator("risk_signals")
    @classmethod
    def signals_must_not_be_blank(cls, signals: list[str]) -> list[str]:
        normalized = [signal.strip() for signal in signals]
        if any(not signal for signal in normalized):
            raise ValueError("Risk signals must not be blank")
        return normalized

    @field_validator("drafts")
    @classmethod
    def drafts_must_cover_each_strategy(
        cls, drafts: list[CrisisDraftInput]
    ) -> list[CrisisDraftInput]:
        strategies = [draft.strategy_type for draft in drafts]
        if set(strategies) != set(ResponseStrategyType) or len(strategies) != len(
            set(strategies)
        ):
            raise ValueError("Exactly one draft for each response strategy is required")
        return drafts


class DraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    strategy: ResponseStrategyType
    body: str
    is_approved: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("strategy")
    def serialize_strategy(self, strategy: ResponseStrategyType) -> str:
        return strategy.name


class ApproveDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edited_text: str = Field(min_length=1, max_length=4000)

    @field_validator("edited_text")
    @classmethod
    def edited_text_must_not_be_blank(cls, edited_text: str) -> str:
        normalized = edited_text.strip()
        if not normalized:
            raise ValueError("Edited text must not be blank")
        return normalized


class ApproveDraftResponse(BaseModel):
    draft: DraftResponse
    idempotent: bool
    publication_status: Literal["outbox_pending"] = "outbox_pending"


class CrisisEscalationResponse(BaseModel):
    risk_level: RiskLevel
    drafts: list[DraftResponse]
    outbox_event_id: UUID
    idempotency_key: str
