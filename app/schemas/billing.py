"""Pydantic схемы для биллинга и квот мультитенантной системы.

Модели для работы с tenant_quotas таблицей: лимиты, использование, проверки.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuotaLimits(BaseModel):
    """Лимиты ресурсов для tenant'а (устанавливаются администратором)."""

    model_config = ConfigDict(frozen=True, strict=True)

    max_llm_tokens: int = Field(
        gt=0, description="Максимальное количество LLM токенов для tenant'а"
    )
    max_reviews: int = Field(
        gt=0, description="Максимальное количество отзывов для обработки"
    )


class QuotaUsage(BaseModel):
    """Текущее использование ресурсов tenant'ом."""

    model_config = ConfigDict(frozen=True, strict=True)

    used_llm_tokens: int = Field(
        ge=0, description="Фактически использовано LLM токенов"
    )
    used_reviews: int = Field(ge=0, description="Количество обработанных отзывов")
    reserved_llm_tokens: int = Field(
        ge=0,
        description="Зарезервированные токены (оценочное списание до точного подсчёта)",
    )


class QuotaStatus(BaseModel):
    """Полная информация о квотах tenant'а: лимиты + использование."""

    model_config = ConfigDict(frozen=True, strict=True)

    tenant_id: UUID
    limits: QuotaLimits
    usage: QuotaUsage
    created_at: datetime
    updated_at: datetime

    @property
    def total_tokens_committed(self) -> int:
        """Общее количество токенов (использованные + зарезервированные)."""
        return self.usage.used_llm_tokens + self.usage.reserved_llm_tokens

    @property
    def tokens_available(self) -> int:
        """Доступное количество токенов."""
        return max(0, self.limits.max_llm_tokens - self.total_tokens_committed)

    @property
    def reviews_available(self) -> int:
        """Доступное количество отзывов."""
        return max(0, self.limits.max_reviews - self.usage.used_reviews)

    @property
    def tokens_usage_percent(self) -> float:
        """Процент использования токенов (0-100)."""
        if self.limits.max_llm_tokens == 0:
            return 0.0
        return (self.total_tokens_committed / self.limits.max_llm_tokens) * 100

    @property
    def reviews_usage_percent(self) -> float:
        """Процент использования отзывов (0-100)."""
        if self.limits.max_reviews == 0:
            return 0.0
        return (self.usage.used_reviews / self.limits.max_reviews) * 100


class QuotaCheck(BaseModel):
    """Результат проверки доступности квоты для операции."""

    model_config = ConfigDict(frozen=True, strict=True)

    available: bool = Field(
        description="True если квота доступна, False если превышен лимит"
    )
    reason: str | None = Field(
        default=None, description="Причина отказа, если available=False"
    )
    tokens_requested: int = Field(ge=0, description="Запрошено токенов")
    reviews_requested: int = Field(ge=0, description="Запрошено отзывов")
    tokens_available: int = Field(ge=0, description="Доступно токенов")
    reviews_available: int = Field(ge=0, description="Доступно отзывов")


class QuotaReservation(BaseModel):
    """Запрос на резервирование токенов (оценочное списание)."""

    model_config = ConfigDict(frozen=True, strict=True)

    tokens: int = Field(
        gt=0, description="Количество токенов для резервирования (оценка)"
    )


class QuotaCommit(BaseModel):
    """Точное списание токенов после получения usage_metadata от LLM."""

    model_config = ConfigDict(frozen=True, strict=True)

    reserved_tokens: int = Field(
        ge=0, description="Количество зарезервированных токенов (оценка)"
    )
    actual_tokens: int = Field(
        ge=0, description="Фактически использованные токены (из usage_metadata)"
    )

    @field_validator("actual_tokens")
    @classmethod
    def actual_not_negative(cls, v: int, info: "ValidationInfo") -> int:  # type: ignore[name-defined]
        """Валидация: actual_tokens должен быть >= 0."""
        if v < 0:
            raise ValueError("actual_tokens cannot be negative")
        return v


class QuotaRelease(BaseModel):
    """Возврат зарезервированных токенов (при ошибке или отмене операции)."""

    model_config = ConfigDict(frozen=True, strict=True)

    tokens: int = Field(gt=0, description="Количество токенов для возврата")


class QuotaConsumeReviews(BaseModel):
    """Списание отзывов после успешного сохранения."""

    model_config = ConfigDict(frozen=True, strict=True)

    count: int = Field(gt=0, description="Количество обработанных отзывов")


class QuotaExceededError(BaseModel):
    """Структура ошибки для HTTP 402 Payment Required."""

    model_config = ConfigDict(frozen=True, strict=True)

    error: Literal["quota_exceeded"] = "quota_exceeded"
    message: str = Field(description="Человекочитаемое описание проблемы")
    quota_status: QuotaStatus = Field(description="Текущее состояние квот")
    requested: dict[str, int] = Field(
        description="Что было запрошено (tokens/reviews)"
    )


class QuotaUpdateLimits(BaseModel):
    """Запрос на обновление лимитов (только для администратора)."""

    model_config = ConfigDict(strict=True)

    max_llm_tokens: int | None = Field(
        default=None, gt=0, description="Новый лимит токенов (если нужно изменить)"
    )
    max_reviews: int | None = Field(
        default=None, gt=0, description="Новый лимит отзывов (если нужно изменить)"
    )

    @field_validator("max_llm_tokens", "max_reviews")
    @classmethod
    def at_least_one_field(cls, v: int | None, info: "ValidationInfo") -> int | None:  # type: ignore[name-defined]
        """Хотя бы одно поле должно быть заполнено."""
        return v


# Экспорт для удобного импорта
__all__ = [
    "QuotaLimits",
    "QuotaUsage",
    "QuotaStatus",
    "QuotaCheck",
    "QuotaReservation",
    "QuotaCommit",
    "QuotaRelease",
    "QuotaConsumeReviews",
    "QuotaExceededError",
    "QuotaUpdateLimits",
]
