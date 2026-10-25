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
from app.core.security import EncryptionError, decrypt_token, encrypt_token
from app.review_state import ReviewState
from app.schemas.economics import ReplyModerationStatus, ReviewStatus


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
    notification_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
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
    # Branch identifier for multi-location businesses
    branch_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    # Добавляем поле для названия платформы как строки (для упрощения парсинга)
    platform: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    original_text = synonym("text")
    status: Mapped[ReviewStatus] = mapped_column(
        SQLAlchemyEnum(
            ReviewStatus,
            name="review_status",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=ReviewStatus.NEW,
    )
    # FSM статус модерации ответа
    moderation_status: Mapped[ReplyModerationStatus] = mapped_column(
        SQLAlchemyEnum(
            ReplyModerationStatus,
            name="reply_moderation_status",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=ReplyModerationStatus.NEW,
    )
    # FSM состояние отзыва (единое поле для управления жизненным циклом)
    state: Mapped[ReviewState] = mapped_column(
        SQLAlchemyEnum(
            ReviewState,
            name="review_state",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=ReviewState.NEW,
        index=True,
    )
    financial_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    si_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    threat_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_response = synonym("suggested_reply")
    analysis_tags: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default=sql_text("'[]'"),
    )
    is_analyzed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
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
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sql_text("0")
    )
    dlq_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tenant_id = synonym("company_id")

    platform_ref: Mapped[Platform] = relationship(
        back_populates="reviews", foreign_keys=[platform_id]
    )
    company: Mapped[Company] = relationship(foreign_keys=[company_id])

    __table_args__ = (
        Index("ix_reviews_company_id", "company_id"),
        Index("idx_reviews_tenant_branch", "company_id", "branch_id"),
        Index("ix_reviews_platform_company", "platform_id", "company_id"),
        Index("ix_reviews_status_company", "status", "company_id"),
        Index(
            "uq_reviews_analytics_dedup",
            "company_id",
            "platform_id",
            "created_at",
            "rating",
            "text",
            unique=True,
        ),
        ForeignKeyConstraint(
            ["platform_id", "company_id"],
            ["platforms.id", "platforms.company_id"],
            name="fk_reviews_platform_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("rating >= 0 AND rating <= 5", name="ck_reviews_rating_range"),
        CheckConstraint(
            "threat_level IS NULL OR threat_level BETWEEN 1 AND 5",
            name="ck_reviews_threat_level_range",
        ),
    )


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret_key: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sql_text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_webhook_endpoints_company_active", "company_id", "is_active"),
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


class PlatformIntegration(Base):
    """Модель для хранения интеграций с платформами (Google Business, Trustpilot, Yelp)"""

    __tablename__ = "platform_integrations"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'google_business', 'trustpilot', 'yelp'
    encrypted_api_key: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Encrypted API token
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meta_config: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default=sql_text("'{}'"),
    )
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_location_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sql_text("true")
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
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

    company: Mapped[Company] = relationship()

    # Property for transparent encryption/decryption
    @property
    def api_key(self) -> str:
        """Decrypt and return the API key"""
        try:
            return decrypt_token(self.encrypted_api_key)
        except EncryptionError as e:
            from app.core.logger import get_logger

            logger = get_logger("platform_integration")
            logger.error(
                "Failed to decrypt API key",
                integration_id=str(self.id),
                platform=self.platform,
                error=str(e),
            )
            raise

    @api_key.setter
    def api_key(self, plain_token: str) -> None:
        """Encrypt and store the API key"""
        try:
            self.encrypted_api_key = encrypt_token(plain_token)
        except EncryptionError as e:
            from app.core.logger import get_logger

            logger = get_logger("platform_integration")
            logger.error(
                "Failed to encrypt API key",
                integration_id=str(self.id),
                platform=self.platform,
                error=str(e),
            )
            raise

    @property
    def refresh_token(self) -> str | None:
        """Decrypt and return the OAuth refresh token."""
        if self.encrypted_refresh_token is None:
            return None
        try:
            return decrypt_token(self.encrypted_refresh_token)
        except EncryptionError as e:
            from app.core.logger import get_logger

            logger = get_logger("platform_integration")
            logger.error(
                "Failed to decrypt refresh token",
                integration_id=str(self.id),
                platform=self.platform,
                error=str(e),
            )
            raise

    @refresh_token.setter
    def refresh_token(self, plain_token: str | None) -> None:
        """Encrypt and store the OAuth refresh token."""
        if plain_token is None:
            self.encrypted_refresh_token = None
            return
        try:
            self.encrypted_refresh_token = encrypt_token(plain_token)
        except EncryptionError as e:
            from app.core.logger import get_logger

            logger = get_logger("platform_integration")
            logger.error(
                "Failed to encrypt refresh token",
                integration_id=str(self.id),
                platform=self.platform,
                error=str(e),
            )
            raise

    __table_args__ = (
        Index("ix_platform_integrations_company_id", "company_id"),
        UniqueConstraint(
            "company_id", "platform", name="uq_platform_integrations_company_platform"
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_logs_tenant_timestamp", "tenant_id", "timestamp"),
    )
