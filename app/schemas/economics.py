from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    NEW = "new"
    SI_PROCESSING = "si_processing"  # Ядро анализирует и генерирует ответ
    RESOLVED = "resolved"  # Клиент сохранен (LTV защищен)
    LOST = "lost"  # Негатив не отработан (убыток)


class ReplyModerationStatus(str, Enum):
    """FSM статусы модерации ответа на отзыв."""

    NEW = "new"  # Новый отзыв без ответа
    DRAFTED = "drafted"  # Черновик ответа сгенерирован
    PENDING_MODERATION = "pending_moderation"  # Отправлен на модерацию
    APPROVED = "approved"  # Одобрен модератором
    PUBLISHED = "published"  # Ответ опубликован на площадке


class CompanyBase(BaseModel):
    name: str = Field(..., description="Название бизнеса")
    average_check: float = Field(..., description="Средний чек (L3: Экономика)")
    margin_percent: float = Field(
        ..., description="Маржинальность в % (для расчета чистой прибыли)"
    )
    cac: float = Field(..., description="CAC: Стоимость привлечения одного клиента")
    base_ltv: float = Field(..., description="LTV: Пожизненная ценность клиента")


class CompanyResponse(CompanyBase):
    id: UUID
    created_at: datetime


class PlatformBase(BaseModel):
    company_id: UUID
    name: str = Field(
        ..., description="Название площадки (Google Maps, 2GIS, Trustpilot)"
    )
    monthly_views: int = Field(0, description="Уровень 1: Показы карточки")
    conversion_rate: float = Field(
        0.0, description="Уровень 2: Конверсия в звонок/переход"
    )
    cac_on_platform: float = Field(
        0.0, description="Стоимость лида конкретно с этой площадки"
    )


class PlatformResponse(PlatformBase):
    id: UUID
    average_rating: float


class ReviewBase(BaseModel):
    platform_id: UUID
    rating: int = Field(..., ge=1, le=5)
    text: str
    status: ReviewStatus = ReviewStatus.NEW
    financial_impact: float = Field(
        default=0.0,
        description=(
            "Рассчитанная сумма. Минус - если негатив отпугнул лидов. "
            "Плюс - если SI спас LTV."
        ),
    )
    si_response: str | None = Field(None, description="Ответ, сгенерированный SI-ядром")


# Assistant schemas
class AssistantReviewSchema(BaseModel):
    """Схема для списка отзывов в рабочем месте ассистента."""

    id: UUID
    platform: str | None
    text: str
    rating: int
    created_at: datetime
    sentiment: str | None
    status: ReplyModerationStatus
    has_reply: bool = Field(
        default=False, description="Есть ли черновик или опубликованный ответ"
    )


class GenerateReplyRequest(BaseModel):
    """Запрос на генерацию ответа."""

    tone: Literal["official", "friendly", "crisis"]


class GenerateReplyResponse(BaseModel):
    """Ответ с сгенерированным черновиком."""

    draft_text: str


class SubmitModerationRequest(BaseModel):
    """Запрос на отправку на модерацию."""

    reply_text: str | None = Field(None, max_length=4000)
    text: str | None = Field(None, max_length=4000)
    tone: str | None = Field(None)

    @property
    def resolved_text(self) -> str:
        """Разрешить текст ответа из любого поля."""
        val = self.reply_text or self.text
        if not val or not val.strip():
            raise ValueError("Текст ответа обязателен")
        return val.strip()
