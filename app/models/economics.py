from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import (
    Enum as SQLAlchemyEnum,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.core.database import Base
from app.schemas.economics import ReviewStatus


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    average_check: Mapped[float] = mapped_column(Float, nullable=False)
    margin_percent: Mapped[float] = mapped_column(Float, nullable=False)
    cac: Mapped[float] = mapped_column(Float, nullable=False)
    base_ltv: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    platforms: Mapped[list["Platform"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Мультитенантность: каждая компания видит только свои данные через RLS
    # company_id не добавляем - сама Company и является tenant


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, index=True
    )
    monthly_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cac_on_platform: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    company: Mapped[Company] = relationship(back_populates="platforms")
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="platform_ref",
        foreign_keys=lambda: [Review.platform_id],
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Индексы создаются в миграциях
    __table_args__ = (
        Index("ix_platforms_company_id", "company_id"),
        UniqueConstraint("company_id", "name", name="uq_platforms_company_name"),
        UniqueConstraint("id", "company_id", name="uq_platforms_id_company"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    platform_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platforms.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Добавляем company_id для прямой изоляции через RLS
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = synonym("company_id")
    # Добавляем поле для внешнего ID (интеграция с Google Maps, 2GIS и др.)
    external_review_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Добавляем поле для названия платформы как строки (для упрощения парсинга)
    platform: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        SQLAlchemyEnum(
            ReviewStatus,
            name="review_status",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=ReviewStatus.NEW,
    )
    financial_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    si_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default=sql_text("'[]'"),
    )
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
    auto_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_pending: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
    ai_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tenant_id = synonym("company_id")

    platform_ref: Mapped[Platform] = relationship(
        back_populates="reviews", foreign_keys=[platform_id]
    )
    company: Mapped[Company] = relationship(foreign_keys=[company_id])

    __table_args__ = (
        Index("ix_reviews_company_id", "company_id"),
        Index("ix_reviews_platform_company", "platform_id", "company_id"),
        Index("ix_reviews_status_company", "status", "company_id"),
        Index(
            "uq_reviews_tenant_platform_external_id",
            "company_id",
            "platform",
            "external_review_id",
            unique=True,
        ),
        ForeignKeyConstraint(
            ["platform_id", "company_id"],
            ["platforms.id", "platforms.company_id"],
            name="fk_reviews_platform_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("rating >= 0 AND rating <= 5", name="ck_reviews_rating_range"),
    )


class PlatformStatistic(Base):
    """Срез агрегированного рейтинга площадки в рамках одного tenant."""

    __tablename__ = "platform_statistics"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    platform_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platforms.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = synonym("company_id")
    average_rating: Mapped[float] = mapped_column(Float, nullable=False)
    rating_change: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    platform_ref: Mapped[Platform] = relationship(foreign_keys=[platform_id])
    company: Mapped[Company] = relationship(foreign_keys=[company_id])

    __table_args__ = (
        Index(
            "ix_platform_statistics_tenant_platform_recorded",
            "company_id",
            "platform_id",
            "recorded_at",
        ),
        ForeignKeyConstraint(
            ["platform_id", "company_id"],
            ["platforms.id", "platforms.company_id"],
            name="fk_platform_statistics_platform_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "average_rating >= 0 AND average_rating <= 5",
            name="ck_platform_statistics_rating_range",
        ),
        CheckConstraint(
            "review_count >= 0", name="ck_platform_statistics_review_count"
        ),
    )


class CompanyMember(Base):
    """Модель для связи пользователей с компаниями"""

    __tablename__ = "company_members"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped[Company] = relationship()

    __table_args__ = (
        Index("ix_company_members_user_company", "user_id", "company_id"),
        Index("ix_company_members_company_id", "company_id"),
    )
