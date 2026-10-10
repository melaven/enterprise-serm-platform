"""Схемы подсистемы сбора отзывов."""

import datetime as dt
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_TEXT_CHARS = 10_000
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


class Platform(str, Enum):
    TWOGIS = "2gis"
    YANDEX = "yandex"
    GOOGLE = "google"


class RawReview(BaseModel):
    """Сырой отзыв до LLM-анализа."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    platform_id: str = Field(min_length=1, max_length=128)  # ID отзыва на площадке
    author_name: str = Field(default="Аноним", max_length=200)
    text: str = Field(default="", max_length=MAX_TEXT_CHARS)  # может быть пустым
    rating: float = Field(ge=0, le=5)
    date: dt.datetime  # всегда UTC, tz-aware
    platform: Platform

    @field_validator("platform_id", mode="before")
    @classmethod
    def _id_to_str(cls, value: object) -> object:
        return str(value) if isinstance(value, int) else value

    @field_validator("author_name", mode="before")
    @classmethod
    def _author_default(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "Аноним"
        return value

    @field_validator("text", mode="before")
    @classmethod
    def _clean_text(cls, value: object) -> object:
        if value is None:
            return ""
        if not isinstance(value, str):
            return value
        cleaned = _WS.sub(" ", value.replace(" ", " ").replace("​", ""))
        cleaned = _BLANK_LINES.sub("\n\n", cleaned).strip()
        return cleaned[:MAX_TEXT_CHARS]

    @field_validator("date")
    @classmethod
    def _to_utc(cls, value: dt.datetime) -> dt.datetime:
        # naive считаем UTC; aware приводим к UTC
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc)
