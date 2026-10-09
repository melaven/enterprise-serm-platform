"""Нормализованная схема сырого отзыва. Все адаптеры приводят данные к ней."""

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_INVISIBLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​⁠﻿]")
_INLINE_SPACES = re.compile(r"[^\S\n]+")  # любые пробельные, кроме \n (вкл. NBSP, \t)
_AROUND_NEWLINE = re.compile(r" ?\n ?")
_BLANK_LINES = re.compile(r"\n{3,}")
_EPOCH = re.compile(r"\d{9,13}(\.\d+)?")

ANONYMOUS = "Аноним"
MAX_METADATA_BYTES = 10_000


def clean_text(value: str) -> str:
    """NFC, без управляющих и zero-width символов, схлопнутые пробелы/пустые строки."""
    text = unicodedata.normalize("NFC", value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE.sub("", text)
    text = _INLINE_SPACES.sub(" ", text)
    text = _AROUND_NEWLINE.sub("\n", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def _from_epoch(value: float) -> datetime:
    if value > 1e11:  # миллисекунды
        value /= 1000
    return datetime.fromtimestamp(value, tz=timezone.utc)


def to_utc(value: Any) -> datetime:
    """datetime | epoch (с/мс) | ISO-8601 строка -> aware datetime в UTC.

    Naive-значения считаются UTC: если площадка отдаёт локальное время, адаптер
    сам должен привязать к нему часовой пояс до валидации.
    """
    if isinstance(value, bool):
        raise ValueError("published_at must not be a bool")
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = _from_epoch(float(value))
    elif isinstance(value, str):
        raw = value.strip()
        if _EPOCH.fullmatch(raw):
            parsed = _from_epoch(float(raw))
        else:
            parsed = datetime.fromisoformat(re.sub(r"[Zz]$", "+00:00", raw))
    else:
        raise ValueError(f"unsupported published_at type: {type(value).__name__}")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class RawReviewSchema(BaseModel):
    """Единый формат отзыва после адаптера, до записи в БД."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    external_id: str = Field(min_length=1, max_length=255)
    author_name: str = Field(default=ANONYMOUS, min_length=1, max_length=255)
    rating: int = Field(ge=1, le=5)
    text: str = Field(default="", max_length=20_000)
    published_at: datetime  # всегда aware, UTC
    reply_text: str | None = Field(default=None, max_length=20_000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("external_id", mode="before")
    @classmethod
    def _external_id(cls, value: Any) -> Any:
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return str(value).strip()
        return value

    @field_validator("author_name", mode="before")
    @classmethod
    def _author(cls, value: Any) -> Any:
        if value is None:
            return ANONYMOUS
        if isinstance(value, str):
            return clean_text(value) or ANONYMOUS
        return value

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, value: Any) -> Any:
        if value is None:
            return ""
        return clean_text(value) if isinstance(value, str) else value

    @field_validator("reply_text", mode="before")
    @classmethod
    def _reply(cls, value: Any) -> Any:
        if isinstance(value, str):
            return clean_text(value) or None
        return value

    @field_validator("rating", mode="before")
    @classmethod
    def _rating(cls, value: Any) -> Any:
        """4, 4.0, "4", "4,5" -> int по правилу half-up (4.5 -> 5)."""
        if isinstance(value, bool):
            raise ValueError("rating must not be a bool")
        if isinstance(value, (int, float, str)):
            try:
                number = Decimal(str(value).strip().replace(",", "."))
                return int(number.quantize(Decimal(1), rounding=ROUND_HALF_UP))
            except InvalidOperation as exc:
                raise ValueError(f"invalid rating: {value!r}") from exc
        return value

    @field_validator("published_at", mode="before")
    @classmethod
    def _published_at(cls, value: Any) -> datetime:
        return to_utc(value)

    @field_validator("published_at", mode="after")
    @classmethod
    def _sane_date(cls, value: datetime) -> datetime:
        if value > datetime.now(timezone.utc) + timedelta(days=1):
            raise ValueError("published_at is in the future")
        if value.year < 2000:
            raise ValueError("published_at is implausibly old")
        return value

    @field_validator("metadata", mode="after")
    @classmethod
    def _json_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            size = len(json.dumps(value, ensure_ascii=False).encode())
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be JSON-serializable") from exc
        if size > MAX_METADATA_BYTES:
            raise ValueError(f"metadata is too large ({size} bytes)")
        return value
