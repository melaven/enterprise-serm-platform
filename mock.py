"""MockReviewScraper: правдоподобные «грязные» отзывы в диалектах площадок.

Для разработки и тестов без сети. Данные детерминированы по (platform, url):
повторный вызов даёт те же external_id, поэтому идемпотентность вставки в БД
проверяется по-настоящему. Каждая площадка отдаёт сырой формат со своими
именами полей, форматом даты и мусором в тексте, а нормализация идёт через тот
же BaseReviewScraper.normalize(), что и у реальных адаптеров.
"""

import asyncio
import hashlib
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.scrapers.base import BaseReviewScraper, ItemMapper
from app.services.scrapers.errors import ScraperError
from app.services.scrapers.schemas import RawReviewSchema

_MSK = timezone(timedelta(hours=3))
_EKB = timezone(timedelta(hours=5))

_AUTHORS = (
    "Анна К.", "Игорь Петров", "Мария С.", "Дмитрий Л.", "Елена Воронова",
    "Сергей М.", "Ольга Н.", "Алексей Т.", "Наталья Б.", "Павел Ж.",
    "Юлия Р.", "Андрей Ф.", "Татьяна Ш.", "Виктор Д.", "Ксения А.",
)  # fmt: skip
_TEXTS: dict[int, tuple[str, ...]] = {
    1: (
        "Ужасное обслуживание, ждали заказ больше часа. Больше не вернёмся.",
        "Грубый персонал и грязно в зале. Деньги за такой сервис платить не хочется.",
        "Обманули с ценой: на кассе вышло дороже, чем в меню. Разочарован.",
    ),
    2: (
        "Ожидал большего. Еда пришла холодной, администратор только развёл руками.",
        "Долго ждали, персонал не извинился. Место так себе.",
        "Шумно и душно, обслуживание медленное.",
    ),
    3: (
        "Нормально, но ничего особенного. За такие деньги можно найти лучше.",
        "Кухня неплохая, а вот сервис хромает.",
        "В целом сойдёт, но очередь на входе была долгой.",
    ),
    4: (
        "Хорошее место, вкусно и недорого. Немного шумновато по вечерам.",
        "Приятный персонал, быстро обслужили. Снизил балл за парковку.",
        "Были с семьёй, всем понравилось. Вернёмся ещё.",
    ),
    5: (
        "Отлично! Лучший сервис в городе, всем рекомендую.",
        "Прекрасная атмосфера, вежливый персонал, всё свежее и вкусное.",
        "Очень доволен, обслужили быстро и с улыбкой. Твёрдая пятёрка!",
    ),
}
_REPLIES = (
    "Спасибо за отзыв! Нам очень приятно, что вам понравилось.",
    "Благодарим за обратную связь, мы уже разбираемся с ситуацией.",
    "Приносим извинения за неудобства. Свяжитесь с нами, мы всё исправим.",
)
_VISITS = ("Обед", "Ужин", "Завтрак", "Кофе", "Доставка")


@dataclass(frozen=True, slots=True)
class _Draft:
    """Нейтральное представление отзыва до подгонки под диалект площадки."""

    key: str
    author: str
    rating: int
    text: str
    published_at: datetime  # aware UTC
    reply: str | None
    likes: int
    visit: str


def _dirty(text: str, rng: random.Random) -> str:
    """Типичный мусор из вёрстки: лишние пробелы, NBSP, переносы, zero-width."""
    variants = (
        lambda s: f"  {s}  ",
        lambda s: s.replace(" ", "  ", 1),
        lambda s: f"\n{s}\n\n\n",
        lambda s: s.replace(" ", " ", 1),
        lambda s: f"{s}​",
        lambda s: s,
    )
    return rng.choice(variants)(text)


# ---- Диалекты: draft -> сырой формат площадки ------------------------------
def _google_raw(d: _Draft, rng: random.Random) -> dict[str, Any]:
    return {
        "review_id": d.key,
        "author": _dirty(d.author, rng),
        "stars": d.rating,
        "snippet": _dirty(d.text, rng),
        "time": int(d.published_at.timestamp()),  # epoch, секунды
        "owner_response": {"text": d.reply} if d.reply else None,
        "likes": d.likes,
        "trip": d.visit,
    }


def _yandex_raw(d: _Draft, rng: random.Random) -> dict[str, Any]:
    return {
        "reviewId": d.key,
        "author": {"name": _dirty(d.author, rng)},
        "rating": float(d.rating),
        "text": _dirty(d.text, rng),
        "updatedTime": d.published_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "businessComment": {"text": d.reply} if d.reply else None,
        "reactions": {"likes": d.likes},
        "tag": d.visit,
    }


def _2gis_raw(d: _Draft, rng: random.Random) -> dict[str, Any]:
    return {
        "id": d.key,
        "user": {"name": _dirty(d.author, rng)},
        "rating": d.rating,
        "text": _dirty(d.text, rng),
        "date_created": d.published_at.astimezone(_EKB).isoformat(),  # +05:00
        "official_answer": {"text": d.reply} if d.reply else None,
        "likes_count": d.likes,
        "category": d.visit,
    }


def _otzovik_raw(d: _Draft, rng: random.Random) -> dict[str, Any]:
    return {
        "id": d.key,
        "nick": _dirty(d.author, rng),
        "grade": str(d.rating),  # строка
        "body": _dirty(d.text, rng),
        # без часового пояса, время московское
        "date": d.published_at.astimezone(_MSK).strftime("%Y-%m-%d %H:%M:%S"),
        "admin_reply": d.reply,
        "useful": d.likes,
        "period": d.visit,
    }


# ---- Мапперы: сырой формат площадки -> поля RawReviewSchema -----------------
def _meta(platform: str, likes: Any, visit: Any) -> dict[str, Any]:
    return {"source": platform, "likes": likes, "visit": visit, "lang": "ru"}


def _map_google(i: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "external_id": i["review_id"],
        "author_name": i["author"],
        "rating": i["stars"],
        "text": i["snippet"],
        "published_at": i["time"],
        "reply_text": (i.get("owner_response") or {}).get("text"),
        "metadata": _meta("google", i.get("likes"), i.get("trip")),
    }


def _map_yandex(i: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "external_id": i["reviewId"],
        "author_name": i["author"]["name"],
        "rating": i["rating"],
        "text": i["text"],
        "published_at": i["updatedTime"],
        "reply_text": (i.get("businessComment") or {}).get("text"),
        "metadata": _meta(
            "yandex", (i.get("reactions") or {}).get("likes"), i.get("tag")
        ),
    }


def _map_2gis(i: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "external_id": i["id"],
        "author_name": i["user"]["name"],
        "rating": i["rating"],
        "text": i["text"],
        "published_at": i["date_created"],
        "reply_text": (i.get("official_answer") or {}).get("text"),
        "metadata": _meta("2gis", i.get("likes_count"), i.get("category")),
    }


def _map_otzovik(i: Mapping[str, Any]) -> dict[str, Any]:
    # Отзовик отдаёт naive-время по Москве: привязываем пояс ДО приведения к UTC.
    local = datetime.fromisoformat(i["date"]).replace(tzinfo=_MSK)
    return {
        "external_id": i["id"],
        "author_name": i["nick"],
        "rating": i["grade"],
        "text": i["body"],
        "published_at": local,
        "reply_text": i.get("admin_reply"),
        "metadata": _meta("otzovik", i.get("useful"), i.get("period")),
    }


_DIALECTS: dict[
    str, tuple[Callable[[_Draft, random.Random], dict[str, Any]], ItemMapper]
] = {
    "google": (_google_raw, _map_google),
    "yandex": (_yandex_raw, _map_yandex),
    "2gis": (_2gis_raw, _map_2gis),
    "otzovik": (_otzovik_raw, _map_otzovik),
}

MOCK_MIN_AVAILABLE = 20
MOCK_MAX_AVAILABLE = 120


class MockReviewScraper(BaseReviewScraper):
    def __init__(
        self,
        platform: str,
        *,
        latency: float = 0.2,
        fail_with: ScraperError | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """
        latency   имитация сетевой задержки, сек (в тестах 0)
        fail_with исключение, которое scrape() бросит (проверка retry-веток)
        clock     источник «сейчас» для дат (в тестах фиксируется)
        """
        super().__init__(platform)
        self._latency = latency
        self._fail_with = fail_with
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def scrape(self, platform_url: str, limit: int = 50) -> list[RawReviewSchema]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self.ensure_url_allowed(platform_url)
        await asyncio.sleep(self._latency)
        if self._fail_with is not None:
            raise self._fail_with

        build_raw, mapper = _DIALECTS[self.platform]
        digest = hashlib.sha256(f"{self.platform}|{platform_url}".encode()).hexdigest()
        rng = random.Random(digest)
        available = rng.randint(MOCK_MIN_AVAILABLE, MOCK_MAX_AVAILABLE)

        now = self._clock()
        published = now - timedelta(hours=rng.randint(1, 48))
        raw_items: list[dict[str, Any]] = []
        for index in range(min(limit, available)):
            rating = rng.choices((1, 2, 3, 4, 5), weights=(8, 6, 10, 28, 48))[0]
            draft = _Draft(
                key=f"{self.platform[:2]}-{digest[:10]}-{index:04d}",
                author=rng.choice(_AUTHORS),
                rating=rating,
                text=rng.choice(_TEXTS[rating]),
                published_at=published,
                reply=rng.choice(_REPLIES) if rng.random() < 0.3 else None,
                likes=rng.randint(0, 40),
                visit=rng.choice(_VISITS),
            )
            raw_items.append(build_raw(draft, rng))
            # Выдача идёт от новых к старым.
            published -= timedelta(hours=rng.randint(6, 96))

        return self.normalize(raw_items, limit, mapper=mapper)
