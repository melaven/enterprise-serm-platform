from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
