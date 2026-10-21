"""Build persistence-safe review summaries from controlled analytics values."""

_CATEGORY_LABELS = {
    "SERVICE": "обслуживание",
    "PRODUCT_QUALITY": "качество продукта",
    "DELIVERY": "доставка",
    "PRICING": "цены",
    "OTHER": "другие вопросы",
}

_SENTIMENT_LABELS = {
    "POSITIVE": "Положительный отзыв",
    "NEUTRAL": "Нейтральный отзыв",
    "NEGATIVE": "Негативный отзыв",
}

_ALLOWED_CATEGORIES = frozenset(_CATEGORY_LABELS)
_ALLOWED_SENTIMENTS = frozenset(_SENTIMENT_LABELS)


def safe_category(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    category = value.upper()
    return category if category in _ALLOWED_CATEGORIES else None


def safe_sentiment(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    sentiment = value.upper()
    return sentiment if sentiment in _ALLOWED_SENTIMENTS else None


def safe_review_summary(
    rating: int | float,
    sentiment: str | None = None,
    category: str | None = None,
) -> str:
    """Return a short summary containing no source text or model-generated entities."""
    sentiment_key = safe_sentiment(sentiment) or ""
    sentiment_label = _SENTIMENT_LABELS.get(
        sentiment_key,
        "Отзыв",
    )
    category_key = safe_category(category)
    category_label = _CATEGORY_LABELS.get(category_key or "")
    category_part = f" о теме «{category_label}»" if category_label else ""
    return f"{sentiment_label}{category_part}; оценка {rating:g}/5."
