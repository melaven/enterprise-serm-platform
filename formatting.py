"""Разбор URL из сообщения и форматирование результата в Telegram-HTML.

Только stdlib. Всё, что пришло из бэкенда/LLM, экранируется (html.escape):
автоответ генерирует модель, и разметка Telegram из него попадать не должна.
Формат результата в ТЗ не зафиксирован, поэтому разбор терпим к названиям полей.
"""

import html
import json
import re
from collections import Counter
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

TELEGRAM_LIMIT = 4096
SAFE_LIMIT = 3800  # запас под HTML-сущности и заголовок
MAX_CARDS = 10
MAX_REPLY_CHARS = 1500
MAX_EXCERPT_CHARS = 200

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING = ".,;:!?)»]}"

_RATING_KEYS = ("rating", "stars", "score", "оценка")
_SENTIMENT_KEYS = ("sentiment", "tonality", "tone", "тональность")
_TAG_KEYS = ("tags", "topics", "keywords", "теги")
_REPLY_KEYS = (
    "suggested_reply", "auto_reply", "autoreply", "generated_reply", "reply",
    "response", "answer",
)  # fmt: skip
_TEXT_KEYS = ("text", "body", "review_text", "content")
_LIST_KEYS = ("reviews", "items", "results", "analysis", "data")

_SENTIMENTS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("pos", "позит", "хорош"), "😊", "Позитивная"),
    (("neg", "негат", "плох"), "😠", "Негативная"),
    (("neu", "нейтр"), "😐", "Нейтральная"),
)


def extract_url(text: str) -> str | None:
    """Первая http(s)-ссылка в тексте без хвостовой пунктуации."""
    match = _URL.search(text)
    if match is None:
        return None
    url = match.group(0).rstrip(_TRAILING)
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    return url


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def normalize_sentiment(raw: Any) -> tuple[str, str]:
    """Любое представление тональности -> (эмодзи, подпись по-русски)."""
    value = str(raw or "").strip().lower()
    for prefixes, emoji, label in _SENTIMENTS:
        if value.startswith(prefixes):
            return emoji, label
    return "❔", (str(raw).strip() if raw else "Не определена")


def _pick(data: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def format_rating(raw: Any) -> str | None:
    try:
        value = int(round(float(str(raw).replace(",", "."))))
    except (TypeError, ValueError):
        return None
    if not 1 <= value <= 5:
        return None
    return f"{'★' * value}{'☆' * (5 - value)} {value}/5"


def _tag_list(raw: Any) -> list[str]:
    if isinstance(raw, str):
        items: list[Any] = re.split(r"[,;]", raw)
    elif isinstance(raw, list):
        items = raw
    else:
        return []
    tags: list[str] = []
    for item in items:
        tag = re.sub(r"\W+", "_", str(item).strip().lower()).strip("_")
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def extract_reviews(result: Any) -> list[dict[str, Any]]:
    """Достаёт список отзывов из result: список, обёртка {"reviews": [...]} или один."""
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        for key in _LIST_KEYS:
            nested = result.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        if _pick(result, _SENTIMENT_KEYS) or _pick(result, _REPLY_KEYS):
            return [result]
    return []


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_review_card(index: int, review: dict[str, Any]) -> str:
    lines = [f"<b>Отзыв #{index}</b>"]

    emoji, label = normalize_sentiment(_pick(review, _SENTIMENT_KEYS))
    rating = format_rating(_pick(review, _RATING_KEYS))
    lines.append(
        f"{emoji} <b>{esc(label)}</b>" + (f"  ·  {esc(rating)}" if rating else "")
    )

    tags = _tag_list(_pick(review, _TAG_KEYS))
    if tags:
        lines.append("🏷 " + " ".join(f"#{esc(t)}" for t in tags[:8]))

    text = _pick(review, _TEXT_KEYS)
    if text:
        lines.append(f"💭 <i>{esc(_truncate(str(text), MAX_EXCERPT_CHARS))}</i>")

    reply = _pick(review, _REPLY_KEYS)
    if reply:
        lines.append("\n✍️ <b>Автоответ:</b>")
        lines.append(
            f"<blockquote>{esc(_truncate(str(reply), MAX_REPLY_CHARS))}</blockquote>"
        )
    return "\n".join(lines)


def _pack(blocks: list[str], limit: int = SAFE_LIMIT) -> list[str]:
    """Склеивает блоки в сообщения не длиннее limit."""
    messages: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit and current:
            messages.append(current)
            current = block
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def format_result(job_id: str, result: Any) -> list[str]:
    """Результат задачи -> одно или несколько сообщений (каждое < лимита Telegram)."""
    reviews = extract_reviews(result)
    if not reviews:
        # Формат не распознан: показываем сырой JSON, чтобы ничего не терять.
        raw = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        return [
            "✅ <b>Готово</b>, но структуру результата не удалось разобрать.\n"
            f"<pre>{esc(_truncate(raw, 3000))}</pre>"
        ]

    sentiments = Counter(
        normalize_sentiment(_pick(r, _SENTIMENT_KEYS))[0] for r in reviews
    )
    summary = "  ".join(f"{emoji} {count}" for emoji, count in sentiments.most_common())
    header = (
        f"✅ <b>Готово!</b> Проанализировано отзывов: {len(reviews)}\n"
        f"{summary}\n<code>{esc(job_id)}</code>"
    )

    cards = [
        format_review_card(i, review)
        for i, review in enumerate(reviews[:MAX_CARDS], start=1)
    ]
    if len(reviews) > MAX_CARDS:
        cards.append(f"…и ещё {len(reviews) - MAX_CARDS}")
    return _pack([header, *cards])
