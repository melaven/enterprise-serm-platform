from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Index, String, Uuid, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OutboxEventType(str, Enum):
    REVIEW_ANALYSIS_REQUESTED = "review.analysis.requested"
    TRIGGER_EMERGENCY_ALERT = "trigger_emergency_alert"
    PUBLISH_REVIEW_REPLY = "publish_review_reply"


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    event_type: Mapped[OutboxEventType] = mapped_column(
        SQLAlchemyEnum(
            OutboxEventType,
            name="outbox_event_type",
            native_enum=False,
            create_constraint=False,
            length=100,
            values_callable=lambda event_types: [
                event_type.value for event_type in event_types
            ],
        ),
        nullable=False,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "uq_outbox_events_idempotency_key",
            "idempotency_key",
            unique=True,
        ),
    )
