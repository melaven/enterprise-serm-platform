"""Контракт результата анализа отзыва (Sentiment Intelligence). Pydantic v2.

Порядок полей — порядок генерации моделью: сначала решение о валидности и флаги, потом тональность и теги,
черновик ответа в самом конце (модель не «оправдывает» тональность уже написанным ответом).
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

MAX_TAGS: Final = 3
MIN_REPLY_CHARS: Final = 20
MAX_REPLY_CHARS: Final = 900
PII_PLACEHOLDER: Final = "[ДАННЫЕ СКРЫТЫ]"

# Единая заглушка для невалидных отзывов: UI не должен предлагать её к публикации (is_valid=false).
INVALID_REPLY_STUB: Final = (
    "Отзыв не содержит информации для ответа. Черновик не сформирован."
)

_TAG_RE: Final = re.compile(r"^[a-zа-яё0-9]+(?:_[a-zа-яё0-9]+){0,2}$")
_CONTACT_RE: Final = re.compile(
    r"https?://|www\.|\S+@\S+|\+?\d[\d\s\-()]{8,}\d", re.IGNORECASE
)
_FORMATTING_RE: Final = re.compile(r"```|\*\*|__|^\s*#", re.MULTILINE)


class Sentiment(str, Enum):
    """Значения reviews.sentiment (верхний регистр, как в БД)."""

    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class ReviewFlag(str, Enum):
    SPAM = "spam"  # реклама, ссылки, предложения заработка
    EMPTY = "empty"  # нет содержательного текста
    GIBBERISH = "gibberish"  # бессвязный набор символов
    OFFENSIVE = (
        "offensive"  # мат/оскорбления (при отсутствии конструктива отзыв невалиден)
    )
    NEEDS_ESCALATION = "needs_escalation"  # угроза судом/надзором, вред здоровью, мошенничество, насилие
    ANALYSIS_FAILED = "analysis_failed"  # ставится только кодом: модель не смогла выдать валидный JSON


# is_valid=true несовместим с этими флагами.
HARD_INVALID_FLAGS: Final = frozenset(
    {
        ReviewFlag.SPAM,
        ReviewFlag.EMPTY,
        ReviewFlag.GIBBERISH,
        ReviewFlag.ANALYSIS_FAILED,
    }
)


class ReviewAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    is_valid: bool = Field(
        description="false: пусто, бессмыслица, спам или брань без конструктива."
    )
    flags: list[ReviewFlag] = Field(description="Подтипы проблем; [] если проблем нет.")
    sentiment: Sentiment
    confidence: float = Field(
        ge=0.0, le=1.0, description="Уверенность модели в своей классификации."
    )
    tags: list[str] = Field(
        max_length=MAX_TAGS, description="1-3 тега при is_valid=true, иначе []."
    )
    draft_reply: str = Field(min_length=1, max_length=MAX_REPLY_CHARS)

    # --- нормализация ------------------------------------------------------------------
    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: Any) -> Any:
        """lowercase + snake_case, без дублей; лишние теги сверх трёх отбрасываются (порядок = значимость)."""
        if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
            return value
        tags: list[str] = []
        for raw in value:
            tag = re.sub(r"[\s\-]+", "_", raw.strip().lower()).strip("_")
            if tag and tag not in tags:
                tags.append(tag)
        return tags[:MAX_TAGS]

    @field_validator("flags")
    @classmethod
    def _unique_flags(cls, flags: list[ReviewFlag]) -> list[ReviewFlag]:
        return list(dict.fromkeys(flags))

    @field_validator("draft_reply")
    @classmethod
    def _safe_reply(cls, reply: str) -> str:
        if reply == INVALID_REPLY_STUB:
            return reply
        if _CONTACT_RE.search(reply):
            raise ValueError(
                "draft_reply содержит контакты (телефон, e-mail, ссылка): запрещено"
            )
        if PII_PLACEHOLDER in reply:
            raise ValueError("draft_reply повторяет служебную метку скрытых данных")
        if _FORMATTING_RE.search(reply):
            raise ValueError("draft_reply содержит markdown-разметку")
        return reply

    # --- согласованность -----------------------------------------------------------------
    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.is_valid:
            if HARD_INVALID_FLAGS & set(self.flags):
                raise ValueError(
                    "is_valid=true несовместим с флагами spam/empty/gibberish/analysis_failed"
                )
            if not 1 <= len(self.tags) <= MAX_TAGS:
                raise ValueError("при is_valid=true нужно от 1 до 3 тегов")
            if not all(_TAG_RE.fullmatch(t) for t in self.tags):
                raise ValueError(
                    "тег: строчные буквы/цифры, слова через _, не более 3 слов"
                )
            if (
                self.draft_reply == INVALID_REPLY_STUB
                or len(self.draft_reply) < MIN_REPLY_CHARS
            ):
                raise ValueError("при is_valid=true нужен содержательный draft_reply")
        else:
            if not self.flags:
                raise ValueError("is_valid=false требует хотя бы один флаг")
            # Для невалидного отзыва тональность/теги/ответ бессмысленны: приводим к канону.
            self.sentiment = Sentiment.NEUTRAL
            self.tags = []
            self.draft_reply = INVALID_REPLY_STUB
        return self

    # --- конструкторы и помощники ------------------------------------------------------------
    @classmethod
    def invalid(
        cls, flags: list[ReviewFlag], confidence: float = 1.0
    ) -> ReviewAnalysisResult:
        return cls(
            is_valid=False,
            flags=flags,
            sentiment=Sentiment.NEUTRAL,
            confidence=confidence,
            tags=[],
            draft_reply=INVALID_REPLY_STUB,
        )

    @classmethod
    def failed(cls) -> ReviewAnalysisResult:
        """Fallback при невалидном ответе модели: ничего не выдумываем, помечаем analysis_failed."""
        return cls.invalid([ReviewFlag.ANALYSIS_FAILED], confidence=0.0)

    @property
    def analysis_failed(self) -> bool:
        return ReviewFlag.ANALYSIS_FAILED in self.flags

    def requires_moderation(self, min_confidence: float = 0.6) -> bool:
        """Валидный отзыв, который нельзя отдавать без внимательной проверки менеджером."""
        return self.is_valid and (
            self.confidence < min_confidence
            or bool(
                {ReviewFlag.NEEDS_ESCALATION, ReviewFlag.OFFENSIVE} & set(self.flags)
            )
        )
