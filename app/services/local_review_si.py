"""Local-only review analysis; source text must never leave this process."""

from dataclasses import dataclass

from app.core.review_privacy import safe_review_summary
from app.services.sentiment import SentimentService

_SENTIMENT_MAP = {
    "very_positive": "POSITIVE",
    "positive": "POSITIVE",
    "neutral": "NEUTRAL",
    "negative": "NEGATIVE",
    "very_negative": "NEGATIVE",
}
_THREAT_LEVEL_MAP = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 1,
}
_TOPIC_RULES = (
    ("DELIVERY", ("достав", "курьер", "опоздал", "привез", "delivery", "courier")),
    (
        "PRODUCT_QUALITY",
        ("качеств", "продукт", "товар", "блюдо", "сломал", "quality", "product"),
    ),
    (
        "SERVICE",
        ("обслуж", "сотрудник", "персонал", "кассир", "поддерж", "service", "staff"),
    ),
    ("PRICING", ("цен", "дорог", "стоим", "оплат", "счет", "price", "payment")),
)


def build_reply_draft(sentiment: str | None) -> str:
    if sentiment == "NEGATIVE":
        return (
            "Спасибо за обратную связь. Мы разберём ситуацию и учтём ваши замечания. "
            "Пожалуйста, свяжитесь с нашей службой поддержки для уточнения деталей."
        )
    if sentiment == "NEUTRAL":
        return "Спасибо за оценку и обратную связь. Мы учтём ваши замечания в работе."
    return "Спасибо за высокую оценку. Будем рады видеть вас снова."


@dataclass(frozen=True)
class LocalReviewAnalysis:
    sentiment: str
    threat_level: int
    is_critical: bool
    tags: tuple[str, ...]
    summary: str
    reply_draft: str


def analyze_review_locally(text: str, rating: int) -> LocalReviewAnalysis:
    """Analyze in memory and return only allowlisted, non-source-derived fields."""
    result = SentimentService().analyze_sentiment(rating=rating, review_text=text)
    sentiment = _SENTIMENT_MAP[result["sentiment"].value]
    priority = result["priority"]
    normalized_text = text.casefold()
    category = next(
        (
            category
            for category, markers in _TOPIC_RULES
            if any(marker in normalized_text for marker in markers)
        ),
        "OTHER",
    )

    return LocalReviewAnalysis(
        sentiment=sentiment,
        threat_level=_THREAT_LEVEL_MAP[priority],
        is_critical=priority == "critical",
        tags=(category,),
        summary=safe_review_summary(rating, sentiment),
        reply_draft=build_reply_draft(sentiment),
    )
