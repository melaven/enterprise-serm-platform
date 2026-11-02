from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy import (
    Enum as SQLAlchemyEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.reviews.risk import ResponseStrategyType


class AIResponseDraft(Base):
    __tablename__ = "anti_crisis_response_drafts"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    strategy_type: Mapped[ResponseStrategyType] = mapped_column(
        SQLAlchemyEnum(
            ResponseStrategyType,
            name="response_strategy_type",
            values_callable=lambda strategies: [
                strategy.value for strategy in strategies
            ],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    approved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "tenant_id"],
            ["reviews.id", "reviews.company_id"],
            ondelete="CASCADE",
            name="fk_anti_crisis_response_drafts_review_tenant",
        ),
        Index(
            "uq_anti_crisis_response_drafts_tenant_review_strategy",
            "tenant_id",
            "review_id",
            "strategy_type",
            unique=True,
        ),
    )
