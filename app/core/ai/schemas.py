"""Контракты AI-генерации черновиков: вход (отзыв, тенант), структурированный выход (ровно 3 варианта)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from typing import Any, Final, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MIN_DRAFT_CHARS: Final = 20
MAX_DRAFT_CHARS: Final = 1200
DRAFTS_PER_REVIEW: Final = 3
MAX_SIMILARITY: Final = 0.85  # выше: два «разных» варианта фактически одинаковы

# Контакты и ссылки запрещены в тексте: модель их выдумывает, а клиент может по ним пойти.
_CONTACT_RE: Final = re.compile(
    r"https?://|www\.|\S+@\S+|\+?\d[\d\s\-()]{8,}\d", re.IGNORECASE
)
# Неподставленные плейсхолдеры («[Имя клиента]», «{{brand}}», «<name>») и markdown не должны уходить на площадку.
_PLACEHOLDER_RE: Final = re.compile(
    r"\[[^\]\n]{1,60}\]|\{\{|\}\}|\{[a-z_]+\}|<[^>\n]{1,40}>", re.IGNORECASE
)
_FORMATTING_RE: Final = re.compile(r"```|\*\*|__|^\s*#|^\s*[-*•]\s", re.MULTILINE)
_CONTROL_RE: Final = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS_RE: Final = re.compile(r"\s+")
_LANG_RE: Final = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")


class DraftVariant(StrEnum):
    """Три стратегии ответа. Значения совпадают с ai_response_drafts.variant."""

    FORMAL = "FORMAL"  # формальный и профессиональный
    EMPATHETIC = "EMPATHETIC"  # эмпатичный (при негативе: с извинением)
    ACTION_ORIENTED = "ACTION_ORIENTED"  # ориентированный на решение


class GenerationSource(StrEnum):
    LLM = "llm"
    FALLBACK = "fallback"


class Polarity(StrEnum):
    NEGATIVE = "negative"
    MIXED = "mixed"
    POSITIVE = "positive"


# --------------------------------------------------------------------------- #
# Вход
# --------------------------------------------------------------------------- #
def _clean_line(value: str) -> str:
    """Контекст тенанта попадает в промпт: убираем управляющие символы и переводы строк."""
    return _WS_RE.sub(" ", _CONTROL_RE.sub("", value)).strip()


class TenantContext(BaseModel):
    """Настройки бренда арендатора, которые влияют на ответы."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    brand_name: str = Field(min_length=1, max_length=120)
    tone_of_voice: str = Field(
        default="вежливый, спокойный, уважительный, без канцелярита",
        min_length=1,
        max_length=300,
    )
    language: str = Field(
        default="ru", description="Язык по умолчанию, если язык отзыва не определён."
    )
    compensation_policy: str | None = Field(
        default=None,
        max_length=500,
        description="Что компания РАЗРЕШАЕТ предлагать (скидка, возврат, повторная услуга). None: компенсаций не обещаем.",
    )
    support_channel: str | None = Field(
        default=None,
        max_length=200,
        description="Словесное описание канала связи после слова «через», например «форму обратной связи на сайте».",
    )
    signature: str | None = Field(
        default=None,
        max_length=120,
        description="Подпись; по умолчанию команда бренда.",
    )

    @field_validator(
        "brand_name",
        "tone_of_voice",
        "compensation_policy",
        "support_channel",
        "signature",
    )
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return None if value is None else (_clean_line(value) or None)

    @field_validator("language")
    @classmethod
    def _language(cls, value: str) -> str:
        if not _LANG_RE.match(value):
            raise ValueError("language должен быть кодом вида 'ru' или 'en-US'")
        return value

    @field_validator("support_channel", "signature")
    @classmethod
    def _no_contacts(cls, value: str | None) -> str | None:
        if value is not None and _CONTACT_RE.search(value):
            raise ValueError(
                "контакты и ссылки в тексте ответов запрещены: опишите канал словами"
            )
        return value

    @model_validator(mode="after")
    def _brand_not_empty(self) -> Self:
        if not self.brand_name:
            raise ValueError("brand_name пуст после очистки")
        return self

    @property
    def effective_signature(self) -> str:
        if self.signature:
            return self.signature
        return (
            f"С уважением, команда {self.brand_name}."
            if self.language.startswith("ru")
            else (f"Best regards, the {self.brand_name} team.")
        )


class ReviewLike(Protocol):
    """Минимум полей отзыва: подходит ORM-модель Review и ReviewSnapshot (только чтение)."""

    @property
    def id(self) -> UUID: ...
    @property
    def rating(self) -> int: ...
    @property
    def body(self) -> str: ...
    @property
    def platform(self) -> str: ...
    @property
    def sentiment(self) -> str | None: ...
    @property
    def threat_level(self) -> int | None: ...


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    """Неизменяемая копия нужных полей: безопасно передавать между транзакциями и тасками."""

    id: UUID
    rating: int
    body: str
    platform: str
    sentiment: str | None = None
    threat_level: int | None = None

    @classmethod
    def from_review(cls, review: ReviewLike) -> Self:
        return cls(
            id=review.id,
            rating=int(review.rating),
            body=review.body or "",
            platform=review.platform,
            sentiment=review.sentiment,
            threat_level=review.threat_level,
        )


# --------------------------------------------------------------------------- #
# Выход
# --------------------------------------------------------------------------- #
class GeneratedDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    variant: DraftVariant
    text: str = Field(min_length=MIN_DRAFT_CHARS, max_length=MAX_DRAFT_CHARS)

    @field_validator("text")
    @classmethod
    def _safe_text(cls, value: str) -> str:
        if _CONTACT_RE.search(value):
            raise ValueError("текст содержит контакт или ссылку")
        if _PLACEHOLDER_RE.search(value):
            raise ValueError("текст содержит неподставленный плейсхолдер")
        if _FORMATTING_RE.search(value):
            raise ValueError("текст содержит markdown-разметку")
        return value


class DraftBatch(BaseModel):
    """Ответ модели: ровно три варианта, по одному на стратегию."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    drafts: list[GeneratedDraft] = Field(
        min_length=DRAFTS_PER_REVIEW, max_length=DRAFTS_PER_REVIEW
    )

    @model_validator(mode="after")
    def _complete_and_distinct(self) -> Self:
        variants = [d.variant for d in self.drafts]
        if (
            set(variants) != set(DraftVariant)
            or len(set(variants)) != DRAFTS_PER_REVIEW
        ):
            raise ValueError(
                "нужен ровно один вариант каждой стратегии: FORMAL, EMPATHETIC, ACTION_ORIENTED"
            )
        for i, left in enumerate(self.drafts):
            for right in self.drafts[i + 1 :]:
                if (
                    SequenceMatcher(None, left.text.lower(), right.text.lower()).ratio()
                    > MAX_SIMILARITY
                ):
                    raise ValueError(
                        f"варианты {left.variant} и {right.variant} почти не отличаются"
                    )
        return self

    def ordered(self) -> tuple[GeneratedDraft, ...]:
        """Стабильный порядок для UI: как в DraftVariant."""
        by_variant = {d.variant: d for d in self.drafts}
        return tuple(by_variant[v] for v in DraftVariant)


@dataclass(frozen=True, slots=True)
class GenerationResult:
    drafts: tuple[GeneratedDraft, ...]
    source: GenerationSource
    prompt_version: str
    attempts: int
    latency_ms: int
    model: str | None = None
    fallback_reason: str | None = None
    # True: шаблон поставлен из-за сбоя, перегенерация позже имеет смысл. False: отзыв без текста, LLM не нужна.
    retryable: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None

    def to_log(self) -> dict[str, Any]:
        """Поля для лога: без текста отзыва и черновиков (персональные данные)."""
        return {
            "source": self.source.value,
            "model": self.model,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
            "fallback_reason": self.fallback_reason,
        }
