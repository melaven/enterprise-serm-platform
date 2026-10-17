"""Контракты AI-разметки: схема, которую LLM обязана вернуть, и её жёсткая валидация."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_TAGS: Final = 5
MAX_REPLY_LEN: Final = 600
_LINK_RE: Final = re.compile(
    r"https?://|www\.|\b[\w.+-]+@[\w-]+\.[\w.]+", re.IGNORECASE
)


class Sentiment(str, Enum):
    """Sentiment classification for reviews (Python 3.10 compatible)."""

    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class ReviewInsight(BaseModel):
    """Один элемент ответа LLM. Всё, что не проходит валидацию, считается невалидным
    для ЭТОГО отзыва (остальные в пачке не страдают)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(description="Идентификатор отзыва из входных данных, без изменений")
    sentiment: Sentiment
    tags: list[str] = Field(
        description="1-5 коротких тематических тегов, нижний регистр"
    )
    is_critical: bool = Field(
        description="true: угроза судом/регулятором, вред здоровью, мошенничество, дискриминация"
    )
    reply: str = Field(
        description="Вежливый ответ бренда на языке отзыва, до 400 символов"
    )

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for tag in value:
            clean = " ".join(tag.lower().split())[:40]
            if clean:
                seen.setdefault(clean, None)
        if not seen:
            raise ValueError("tags must not be empty")
        return list(seen)[:MAX_TAGS]

    @field_validator("reply")
    @classmethod
    def _validate_reply(cls, value: str) -> str:
        reply = value.strip()
        if not reply:
            raise ValueError("reply must not be empty")
        if len(reply) > MAX_REPLY_LEN:
            raise ValueError("reply too long")
        # Автоответ уходит клиенту от имени бренда: ссылки/контакты — вектор prompt injection.
        if _LINK_RE.search(reply):
            raise ValueError("reply contains a link or contact")
        return reply


class AnalysisEnvelope(BaseModel):
    """Только для генерации JSON Schema (response_format). Парсим ответ мягче — см. процессор."""

    model_config = ConfigDict(extra="forbid")
    results: list[ReviewInsight]


_STRIP_KEYS: Final = frozenset(
    {
        "title",
        "default",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
    }
)


def _strictify(node: Any) -> Any:
    """Приводит pydantic-схему к subset OpenAI strict structured outputs."""
    if isinstance(node, dict):
        out = {k: _strictify(v) for k, v in node.items() if k not in _STRIP_KEYS}
        if out.get("type") == "object":
            out["additionalProperties"] = False
            out["required"] = list(out.get("properties", {}))
        return out
    if isinstance(node, list):
        return [_strictify(v) for v in node]
    return node


def build_response_schema() -> dict[str, Any]:
    schema: dict[str, Any] = _strictify(AnalysisEnvelope.model_json_schema())
    return schema
