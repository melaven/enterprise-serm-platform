from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    NEW = "new"
    SI_PROCESSING = "si_processing"  # Ядро анализирует и генерирует ответ
    RESOLVED = "resolved"  # Клиент сохранен (LTV защищен)
    LOST = "lost"  # Негатив не отработан (убыток)


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
    author_name: str
    rating: int = Field(..., ge=1, le=5)
    text: str
    external_review_id: Optional[str] = Field(
        None, description="Внешний ID отзыва (от Google Maps, 2GIS и др.)"
    )
    status: ReviewStatus = ReviewStatus.NEW
    financial_impact: float = Field(
        default=0.0,
        description=(
            "Рассчитанная сумма. Минус - если негатив отпугнул лидов. "
            "Плюс - если SI спас LTV."
        ),
    )
    si_response: Optional[str] = Field(
        None, description="Ответ, сгенерированный SI-ядром"
    )


class ReviewResponse(ReviewBase):
    id: UUID
    created_at: datetime
    external_review_id: Optional[str] = None
