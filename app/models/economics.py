from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum as SQLAlchemyEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
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
    monthly_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cac_on_platform: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    company: Mapped[Company] = relationship(back_populates="platforms")
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="platform",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Индекс для мультитенантности
    __table_args__ = (
        Index("ix_platforms_company_id", "company_id"),
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
    # Добавляем поле для внешнего ID (интеграция с Google Maps, 2GIS и др.)
    external_review_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    platform: Mapped[Platform] = relationship(back_populates="reviews")
    company: Mapped[Company] = relationship()

    # Индексы для мультитенантности и производительности
    __table_args__ = (
        Index("ix_reviews_company_id", "company_id"),
        Index("ix_reviews_platform_company", "platform_id", "company_id"),
        Index("ix_reviews_status_company", "status", "company_id"),
        Index("ix_reviews_external_id", "external_review_id"),
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
