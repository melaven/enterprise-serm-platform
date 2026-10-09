"""Схемы аналитического слоя: тональность, теги, предложенный ответ."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.scrapers.schemas import RawReviewSchema

MAX_TAGS = 5
NEUTRAL_SCORE_LIMIT = 0.5


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ReviewTag(str, Enum):
    """Закрытый словарь тем: аналитика по тегам не расползается на синонимы."""

    SERVICE = "service"
    STAFF = "staff"
    PRICE = "price"
    DELIVERY = "delivery"
    QUALITY = "quality"
    CLEANLINESS = "cleanliness"
    ATMOSPHERE = "atmosphere"
    WAIT_TIME = "wait_time"
    LOCATION = "location"


TAG_LABELS_RU: dict[ReviewTag, str] = {
    ReviewTag.SERVICE: "сервис",
    ReviewTag.STAFF: "персонал",
    ReviewTag.PRICE: "цена",
    ReviewTag.DELIVERY: "доставка",
    ReviewTag.QUALITY: "качество",
    ReviewTag.CLEANLINESS: "чистота",
    ReviewTag.ATMOSPHERE: "атмосфера",
    ReviewTag.WAIT_TIME: "время ожидания",
    ReviewTag.LOCATION: "расположение",
}


class ReplyScenario(str, Enum):
    APOLOGY = "apology"  # извинение (негатив, 1-2★)
    THANKS = "thanks"  # благодарность (позитив, 4-5★)
    CLARIFY = "clarify"  # запрос деталей (нейтрал, 3★, противоречивый отзыв)


def _unique_tags(tags: tuple[ReviewTag, ...]) -> tuple[ReviewTag, ...]:
    if len(set(tags)) != len(tags):
        raise ValueError("tags must be unique")
    return tags


class ReviewAnalysis(BaseModel):
    """Результат анализа текста отзыва (без привязки к самому отзыву)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sentiment: Sentiment
    score: float = Field(ge=-1.0, le=1.0)  # -1 крайний негатив ... +1 крайний позитив
    tags: tuple[ReviewTag, ...] = Field(default=(), max_length=MAX_TAGS)
    analyzer: str = Field(
        min_length=1, max_length=64
    )  # кто посчитал: heuristic-v1, llm:...

    _tags_unique = field_validator("tags")(_unique_tags)

    @model_validator(mode="after")
    def _sentiment_matches_score(self) -> "ReviewAnalysis":
        ok = (
            (self.sentiment is Sentiment.POSITIVE and self.score > 0)
            or (self.sentiment is Sentiment.NEGATIVE and self.score < 0)
            or (
                self.sentiment is Sentiment.NEUTRAL
                and abs(self.score) <= NEUTRAL_SCORE_LIMIT
            )
        )
        if not ok:
            raise ValueError(
                f"sentiment {self.sentiment.value!r} contradicts score {self.score}"
            )
        return self


class SuggestedReply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1, max_length=4000)
    scenario: ReplyScenario
    source: Literal["template", "llm"]


class EnrichedReviewSchema(RawReviewSchema):
    """RawReviewSchema + аналитика. Это то, что уходит в репозиторий."""

    sentiment: Sentiment
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    tags: tuple[ReviewTag, ...] = Field(default=(), max_length=MAX_TAGS)
    analyzer: str = Field(min_length=1, max_length=64)
    # None: владелец уже ответил (reply_text) или ответ не нужен.
    suggested_reply: str | None = Field(default=None, min_length=1, max_length=4000)
    reply_scenario: ReplyScenario | None = None

    _tags_unique = field_validator("tags")(_unique_tags)

    @model_validator(mode="after")
    def _reply_has_scenario(self) -> "EnrichedReviewSchema":
        if (self.suggested_reply is None) != (self.reply_scenario is None):
            raise ValueError("suggested_reply and reply_scenario go together")
        return self

    @classmethod
    def from_raw(
        cls,
        raw: RawReviewSchema,
        analysis: ReviewAnalysis,
        reply: SuggestedReply | None = None,
    ) -> "EnrichedReviewSchema":
        extra: dict[str, Any] = {
            "sentiment": analysis.sentiment,
            "sentiment_score": analysis.score,
            "tags": analysis.tags,
            "analyzer": analysis.analyzer,
            "suggested_reply": reply.text if reply else None,
            "reply_scenario": reply.scenario if reply else None,
        }
        return cls(**raw.model_dump(), **extra)
