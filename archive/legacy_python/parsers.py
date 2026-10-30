"""Парсеры отзывов. СЕЙЧАС ЗАГЛУШКА: генерирует детерминированные фейковые отзывы.

Реальный парсер подменяет parse_reviews() (httpx/playwright), контракт тот же.
Для реального парсера: проверяй хост URL по allowlist (см. routers/parser.py),
иначе воркер превращается в SSRF-прокси во внутреннюю сеть.
"""

import asyncio
import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, get_args

Platform = Literal["yandex", "2gis", "google"]
PLATFORMS: tuple[str, ...] = get_args(Platform)

_AUTHORS = ["Анна К.", "Игорь П.", "Мария С.", "Дмитрий Л.", "Елена В."]
_TEXTS = {
    1: "Ужасный сервис, больше не вернусь.",
    2: "Ожидал большего, долго ждали.",
    3: "Нормально, но есть что улучшить.",
    4: "Хорошо, в целом доволен.",
    5: "Отлично! Рекомендую.",
}


class TransientParserError(Exception):
    """Временная ошибка источника (таймаут, 429, 5xx): задачу стоит повторить."""


@dataclass(frozen=True, slots=True)
class ParsedReview:
    external_id: str  # стабильный id отзыва на площадке (ключ дедупликации)
    author: str
    rating: int
    text: str
    published_at: datetime


async def parse_reviews(
    platform: str, url: str, *, count: int = 10
) -> list[ParsedReview]:
    await asyncio.sleep(0.2)  # имитация сетевого запроса

    digest = hashlib.sha256(f"{platform}|{url}".encode()).hexdigest()
    # Один и тот же URL -> те же external_id (идемпотентность при ретраях).
    rng = random.Random(digest)
    now = datetime.now(timezone.utc)

    reviews: list[ParsedReview] = []
    for i in range(count):
        rating = rng.randint(1, 5)
        reviews.append(
            ParsedReview(
                external_id=f"{platform}-{digest[:10]}-{i}",
                author=rng.choice(_AUTHORS),
                rating=rating,
                text=_TEXTS[rating],
                published_at=now - timedelta(days=i * 3),
            )
        )
    return reviews
