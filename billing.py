"""ORM-модели биллинга поверх таблиц 013/015 (public.plans, public.subscriptions, public.tenant_quotas).

Модели ТОЛЬКО ДЛЯ ЧТЕНИЯ под ролью app_tenant: запись в эти таблицы закрыта грантами и RLS, план и статус
меняют исключительно SECURITY DEFINER-функции app.billing_* (вебхук провайдера, роль billing_service).
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Numeric, String, select
from sqlalchemy.orm import Mapped, column_property, mapped_column

from app.models.base import (
    Base,
)  # Declarative Base проекта (поправь импорт, если лежит в другом модуле)


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class BillingPlan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column("code", String, primary_key=True)  # 'free' | 'pro'
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    max_reviews_per_month: Mapped[int] = mapped_column(
        "reviews_parsed_limit", BigInteger, nullable=False
    )


class TenantQuota(Base):
    """Счётчик расхода (единственный источник истины); списывает воркер атомарно (app.consume_quota)."""

    __tablename__ = "tenant_quotas"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    reviews_used: Mapped[int] = mapped_column(
        "reviews_parsed_used", BigInteger, nullable=False
    )
    reviews_limit: Mapped[int] = mapped_column(
        "reviews_parsed_limit", BigInteger, nullable=False
    )
    reset_date: Mapped[date] = mapped_column(nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    id: Mapped[UUID] = mapped_column(unique=True)
    plan_id: Mapped[str] = mapped_column(
        "plan_code", ForeignKey("plans.code"), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # reviews_used — НЕ колонка subscriptions: коррелированный подзапрос в tenant_quotas (RLS применяется).
    reviews_used = column_property(
        select(TenantQuota.reviews_used)
        .where(TenantQuota.tenant_id == tenant_id)
        .scalar_subquery()
    )


class TenantAPIKey(Base):
    """Ключ внешнего API. Под app_tenant доступен только SELECT (без api_key_hash); выдача/отзыв — app.create_api_key / app.revoke_api_key."""

    __tablename__ = "tenant_api_keys"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, deferred=True
    )  # SHA-256 hex; не читается app_tenant
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
