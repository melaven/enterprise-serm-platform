from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
    Uuid,
    func,
)
from sqlalchemy import (
    Enum as SQLAlchemyEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.reviews.publication import ReplyPublicationStatus


class ReviewReply(Base):
    __tablename__ = "review_replies"

    review_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReplyPublicationStatus | None] = mapped_column(
        SQLAlchemyEnum(
            ReplyPublicationStatus,
            name="reply_publication_status",
            native_enum=False,
            create_constraint=False,
            values_callable=lambda statuses: [status.value for status in statuses],
            length=32,
        ),
        nullable=True,
    )
    external_reply_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
            ["review_id", "company_id"],
            ["reviews.id", "reviews.company_id"],
            ondelete="CASCADE",
            name="fk_review_replies_review_tenant",
        ),
    )
