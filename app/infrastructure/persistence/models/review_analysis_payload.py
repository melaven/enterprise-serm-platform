from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReviewAnalysisPayload(Base):
    __tablename__ = "review_analysis_payloads"

    review_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        primary_key=True,
    )
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encrypted_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
