import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Review(Base):
    """Отзыв с площадки. Имена колонок совпадают с public.reviews основного проекта."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("company_id", "platform", "external_id", name="uq_reviews_company_platform_external"),
        CheckConstraint("rating BETWEEN 0 AND 5", name="rating_range"),
        CheckConstraint("threat_level IS NULL OR threat_level BETWEEN 1 AND 5", name="threat_level_range"),
        CheckConstraint(
            "sentiment IS NULL OR sentiment IN ('POSITIVE', 'NEUTRAL', 'NEGATIVE')",
            name="sentiment_valid",
        ),
        Index("ix_reviews_company_published", "company_id", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Результат анализа Sentiment Intelligence (SI)
    sentiment: Mapped[str | None] = mapped_column(String(16))
    threat_level: Mapped[int | None] = mapped_column(SmallInteger)
    analysis_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    is_analyzed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
