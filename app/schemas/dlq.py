"""Схема записи Dead Letter Queue."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DLQStatus(str, Enum):
    PENDING_REVIEW = "pending_review"  # ждёт разбора человеком
    REQUEUED = "requeued"  # поставлена в очередь заново
    DISCARDED = "discarded"  # осознанно отброшена


class DLQRecord(BaseModel):
    """Строка таблицы dead_letter_queue (id/created_at проставляет БД)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    job_name: str
    correlation_id: str
    args: list[Any] = Field(default_factory=list)  # JSON-совместимые значения
    kwargs: dict[str, Any] = Field(default_factory=dict)  # JSON-совместимые значения
    error_message: str
    traceback: str
    status: DLQStatus = DLQStatus.PENDING_REVIEW
