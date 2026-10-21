"""Neutral label for review authors whose names are not persisted."""


def anonymize_author_name(real_name: str = "", author_id: str | None = None) -> str:
    """Return the same non-identifying label regardless of supplied identifiers."""
    return "Автор отзыва"
