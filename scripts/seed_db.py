"""Seed a deterministic demo tenant, reviews, platform statistics, and cache vectors."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_TENANT_ID = UUID("7c33fd02-49cc-5a27-b7e5-a283c9bb9a37")
DEMO_NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
EMBEDDING_DIMENSIONS = 1536

PLATFORM_DEFINITIONS = (
    {
        "key": "google",
        "name": "Google Maps",
        "url": "https://maps.google.com/",
        "monthly_views": 8200,
        "conversion_rate": 0.074,
        "cac_on_platform": 410.0,
        "rating_change": 0.12,
    },
    {
        "key": "2gis",
        "name": "2GIS",
        "url": "https://2gis.ru/moscow/",
        "monthly_views": 6100,
        "conversion_rate": 0.091,
        "cac_on_platform": 365.0,
        "rating_change": -0.04,
    },
    {
        "key": "trustpilot",
        "name": "Trustpilot",
        "url": "https://www.trustpilot.com/",
        "monthly_views": 3400,
        "conversion_rate": 0.052,
        "cac_on_platform": 520.0,
        "rating_change": 0.08,
    },
)

REVIEW_TEXTS = {
    "positive": (
        (
            "Зашла за кофе перед работой — капучино приготовили быстро, вкус отличный. "
            "Бариста был очень внимателен, обязательно вернусь.",
            "Очень уютное место: чисто, спокойно и приятная музыка. Фильтр-кофе "
            "сделали именно так, как попросил.",
            "Заказ собрали без задержки, напитки были горячими, а упаковка не "
            "протекла. "
            "Спасибо команде за заботу.",
            "Давно беру здесь зерно домой. Консультант помог подобрать обжарку под "
            "воронку, результат получился отличный.",
            "Удобно расположено, внутри аккуратно. Латте и десерт свежие, обслуживание "
            "доброжелательное.",
            "Быстро решили вопрос с заказом и сразу предложили замену. Остался доволен "
            "и сервисом, и качеством.",
        ),
        (5, 5, 4, 5, 4, 5),
    ),
    "neutral": (
        (
            "Кофе нормальный, без сюрпризов. Очередь двигалась не очень быстро, но "
            "заказ приготовили правильно.",
            "В целом обычная кофейня. Напиток хороший, столик пришлось немного "
            "подождать.",
            "Заказывал доставку: всё приехало целым, но курьер был позже указанного "
            "времени.",
            "Ассортимент достаточный, цены средние. Для короткой встречи место "
            "подходит.",
            "Вкус соответствует ожиданиям, обслуживание корректное. Ничего особенного, "
            "но и претензий нет.",
            "Зерно свежее, хотя хотелось бы больше вариантов помола. Покупкой в целом "
            "доволен.",
        ),
        (3, 3, 3, 4, 3, 3),
    ),
    "negative": (
        (
            "Ждал заказ почти двадцать минут, хотя людей было немного. Напиток "
            "принесли "
            "уже остывшим.",
            "В доставке перепутали позицию. Написал в поддержку, но ответ получил "
            "только "
            "на следующий день.",
            "Кофе оказался заметно горьким, а просьбу сделать помягче не учли. За "
            "эту цену "
            "ожидал большего.",
            "На столах были крошки, салфеток не оказалось. Персонал долго не замечал "
            "просьбу.",
            "Заказ отменили после оплаты, возврат пришлось отдельно уточнять. Процесс "
            "получился неудобным.",
            "В приложении указано одно время работы, а дверь оказалась закрыта. "
            "Расписание "
            "стоит обновить.",
        ),
        (1, 2, 2, 1, 2, 1),
    ),
}

AUTHOR_NAMES = (
    "Анна Смирнова",
    "Иван Кузнецов",
    "Мария Попова",
    "Алексей Васильев",
    "Елена Петрова",
    "Дмитрий Соколов",
    "Ольга Михайлова",
    "Сергей Новиков",
    "Наталья Фёдорова",
    "Михаил Морозов",
    "Татьяна Волкова",
    "Андрей Алексеев",
    "Ирина Лебедева",
    "Павел Семёнов",
    "Екатерина Павлова",
    "Роман Козлов",
    "Светлана Степанова",
    "Никита Николаев",
    "Юлия Орлова",
    "Виктор Андреев",
)

TOPICS = {
    "positive": ("обслуживание", "качество", "атмосфера"),
    "neutral": ("ожидание", "ассортимент", "цена"),
    "negative": ("обслуживание", "доставка", "качество"),
}

MOCK_CACHE_TEXTS = (
    "Клиент жалуется на длительное ожидание заказа",
    "Поблагодарить клиента за положительный отзыв о кофе",
    "Заказ доставлен с опозданием, нужно подготовить ответ",
    "Клиенту понравилось обслуживание и атмосфера кофейни",
    "В отзыве сообщается об ошибке в заказе",
    "Нейтральный отзыв о качестве напитка и времени ожидания",
)


def _sentiment_for(index: int) -> str:
    slot = index % 40
    if slot < 15:
        return "positive"
    if slot < 25:
        return "neutral"
    return "negative"


def _make_review(
    tenant_id: UUID,
    platform: dict[str, Any],
    platform_index: int,
    review_index: int,
) -> dict[str, Any]:
    sentiment = _sentiment_for(review_index)
    templates, ratings = REVIEW_TEXTS[sentiment]
    template_index = (review_index // 3 + platform_index) % len(templates)
    created_at = DEMO_NOW - timedelta(
        days=(review_index * 7 + platform_index * 11) % 120,
        hours=(review_index * 5 + platform_index * 3) % 24,
    )
    external_id = f"demo-{platform['key']}-{review_index + 1:03d}"
    review_id = uuid5(tenant_id, f"review/{platform['key']}/{external_id}")
    author = AUTHOR_NAMES[(review_index * 7 + platform_index * 3) % len(AUTHOR_NAMES)]
    text = templates[template_index]
    rating = ratings[template_index]
    critical = sentiment == "negative" and review_index % 17 == 0
    topics = list(TOPICS[sentiment])

    return {
        "id": str(review_id),
        "tenant_id": str(tenant_id),
        "company_id": str(tenant_id),
        "platform_id": platform["id"],
        "external_review_id": external_id,
        "platform": platform["key"],
        "source": platform["name"],
        "author_name": author,
        "author": author,
        "rating": rating,
        "text": text,
        "sentiment": sentiment.upper(),
        "tags": topics,
        "topics": topics,
        "is_critical": critical,
        "status": "new",
        "financial_impact": (-1800.0 if sentiment == "negative" else 0.0),
        "si_response": None,
        "auto_reply": (
            "Спасибо, что сообщили о ситуации. Мы проверим детали и постараемся "
            "исправить впечатление."
            if sentiment == "negative"
            else None
        ),
        "ai_pending": False,
        "url": platform["platform_url"],
        "date": created_at.isoformat(),
        "created_at": created_at.isoformat(),
    }


def generate_seed_data(tenant_id: UUID = DEFAULT_TENANT_ID) -> dict[str, Any]:
    """Build the same deterministic tenant and review records on every run."""
    tenant = {
        "id": str(tenant_id),
        "tenant_id": str(tenant_id),
        "name": "Кофейня «Север и зёрна» — демо",
        "average_check": 680.0,
        "margin_percent": 62.0,
        "cac": 390.0,
        "base_ltv": 12400.0,
        "created_at": DEMO_NOW.isoformat(),
    }

    platforms: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    statistics: list[dict[str, Any]] = []

    for platform_index, definition in enumerate(PLATFORM_DEFINITIONS):
        platform_id = uuid5(tenant_id, f"platform/{definition['key']}")
        platform = {
            "id": str(platform_id),
            "tenant_id": str(tenant_id),
            "company_id": str(tenant_id),
            "key": definition["key"],
            "name": definition["key"],
            "display_name": definition["name"],
            "platform_url": definition["url"],
            "monthly_views": definition["monthly_views"],
            "conversion_rate": definition["conversion_rate"],
            "cac_on_platform": definition["cac_on_platform"],
        }
        platform_reviews = [
            _make_review(tenant_id, platform, platform_index, i) for i in range(40)
        ]
        ratings = [review["rating"] for review in platform_reviews]
        average_rating = round(sum(ratings) / len(ratings), 2)
        platform["average_rating"] = average_rating
        platforms.append(platform)
        reviews.extend(platform_reviews)

        statistics.append(
            {
                "id": str(uuid5(tenant_id, f"statistics/{definition['key']}")),
                "tenant_id": str(tenant_id),
                "company_id": str(tenant_id),
                "platform_id": str(platform_id),
                "platform": definition["key"],
                "average_rating": average_rating,
                "rating_change": definition["rating_change"],
                "review_count": len(platform_reviews),
                "recorded_at": DEMO_NOW.isoformat(),
            }
        )

    sentiments = {
        key: sum(review["sentiment"] == key.upper() for review in reviews)
        for key in ("positive", "neutral", "negative")
    }
    rating_distribution = {
        str(rating): sum(review["rating"] == rating for review in reviews)
        for rating in range(1, 6)
    }
    summary = {
        "total_reviews": len(reviews),
        "total_platforms": len(platforms),
        "average_rating": round(
            sum(review["rating"] for review in reviews) / len(reviews), 2
        ),
        "sentiment_distribution": sentiments,
        "rating_distribution": rating_distribution,
    }

    return {
        "tenant": tenant,
        "platforms": platforms,
        "reviews": reviews,
        "platform_statistics": statistics,
        "summary": summary,
    }


def _fake_embedding(text: str) -> list[float]:
    """Create a deterministic, non-zero, unit-length demo vector."""
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest(), "big")
    rng = random.Random(seed)
    values = [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIMENSIONS)]
    norm = math.sqrt(sum(value * value for value in values))
    return [round(value / norm, 8) for value in values]


async def seed_database(data: dict[str, Any]) -> None:
    """Upsert demo rows inside a transaction with the active tenant RLS context."""
    load_dotenv(ROOT / ".env", override=False)
    database_url = os.getenv("SEED_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "Set SEED_DATABASE_URL or DATABASE_URL to a PostgreSQL migration/admin URL."
        )

    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.models.economics import Company, Platform, PlatformStatistic, Review
    from app.schemas.economics import ReviewStatus

    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    elif url.drivername != "postgresql+asyncpg":
        raise RuntimeError("The seed database URL must use PostgreSQL with asyncpg.")

    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: (
                f"__seed_asyncpg_{random.getrandbits(64):016x}__"
            ),
        },
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    tenant_id = UUID(data["tenant"]["id"])

    try:
        async with session_factory.begin() as session:
            await session.execute(
                text("SELECT set_config('app.company_id', :company_id, true)"),
                {"company_id": str(tenant_id)},
            )

            tenant_role_exists = await session.scalar(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM pg_roles WHERE rolname = 'app_tenant'"
                    ")"
                )
            )
            if not tenant_role_exists:
                raise RuntimeError(
                    "The app_tenant role is missing; apply the multitenancy "
                    "migration first."
                )

            await _verify_cache_schema(session)

            company_values = {
                key: (datetime.fromisoformat(value) if key == "created_at" else value)
                for key, value in data["tenant"].items()
                if key != "tenant_id"
            }
            company_values["id"] = tenant_id
            company_insert = pg_insert(Company)
            await session.execute(
                company_insert.values(company_values).on_conflict_do_update(
                    index_elements=[Company.id],
                    set_={
                        key: getattr(company_insert.excluded, key)
                        for key in (
                            "name",
                            "average_check",
                            "margin_percent",
                            "cac",
                            "base_ltv",
                            "created_at",
                        )
                    },
                )
            )

            await session.execute(text("SET LOCAL ROLE app_tenant"))

            platform_rows = [
                {
                    key: platform[key]
                    for key in (
                        "id",
                        "company_id",
                        "name",
                        "platform_url",
                        "monthly_views",
                        "conversion_rate",
                        "cac_on_platform",
                        "average_rating",
                    )
                }
                for platform in data["platforms"]
            ]
            for row in platform_rows:
                row["id"] = UUID(row["id"])
                row["company_id"] = tenant_id
            platform_insert = pg_insert(Platform)
            await session.execute(
                platform_insert.values(platform_rows).on_conflict_do_update(
                    index_elements=[Platform.id],
                    set_={
                        key: getattr(platform_insert.excluded, key)
                        for key in (
                            "name",
                            "platform_url",
                            "monthly_views",
                            "conversion_rate",
                            "cac_on_platform",
                            "average_rating",
                        )
                    },
                )
            )

            review_rows = [
                {
                    key: (ReviewStatus.NEW if key == "status" else review[key])
                    for key in (
                        "id",
                        "company_id",
                        "platform_id",
                        "external_review_id",
                        "platform",
                        "author_name",
                        "rating",
                        "text",
                        "status",
                        "financial_impact",
                        "si_response",
                        "sentiment",
                        "tags",
                        "is_critical",
                        "auto_reply",
                        "ai_pending",
                        "created_at",
                    )
                }
                for review in data["reviews"]
            ]
            for row in review_rows:
                row["id"] = UUID(row["id"])
                row["company_id"] = tenant_id
                row["platform_id"] = UUID(row["platform_id"])
                row["created_at"] = datetime.fromisoformat(row["created_at"])
            review_insert = pg_insert(Review)
            await session.execute(
                review_insert.values(review_rows).on_conflict_do_update(
                    index_elements=[Review.id],
                    set_={
                        key: getattr(review_insert.excluded, key)
                        for key in (
                            "external_review_id",
                            "platform",
                            "author_name",
                            "rating",
                            "text",
                            "status",
                            "financial_impact",
                            "si_response",
                            "sentiment",
                            "tags",
                            "is_critical",
                            "auto_reply",
                            "ai_pending",
                            "created_at",
                        )
                    },
                )
            )

            statistic_rows = [
                {
                    key: statistic[key]
                    for key in (
                        "id",
                        "company_id",
                        "platform_id",
                        "average_rating",
                        "rating_change",
                        "review_count",
                        "recorded_at",
                    )
                }
                for statistic in data["platform_statistics"]
            ]
            for row in statistic_rows:
                row["id"] = UUID(row["id"])
                row["company_id"] = tenant_id
                row["platform_id"] = UUID(row["platform_id"])
                row["recorded_at"] = datetime.fromisoformat(row["recorded_at"])
            statistic_insert = pg_insert(PlatformStatistic)
            await session.execute(
                statistic_insert.values(statistic_rows).on_conflict_do_update(
                    index_elements=[PlatformStatistic.id],
                    set_={
                        key: getattr(statistic_insert.excluded, key)
                        for key in (
                            "average_rating",
                            "rating_change",
                            "review_count",
                            "recorded_at",
                        )
                    },
                )
            )

            await _seed_cache(session)
    finally:
        await engine.dispose()


async def _verify_cache_schema(session: Any) -> None:
    """Fail clearly if the canonical pgvector migration has not been applied."""
    from sqlalchemy import text

    ready = await session.scalar(
        text(
            """
            SELECT
                EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
                AND EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relname = 'llm_cache'
                      AND a.attname = 'embedding'
                      AND format_type(a.atttypid, a.atttypmod) = 'vector(1536)'
                      AND NOT a.attisdropped
                )
            """
        )
    )
    if not ready:
        raise RuntimeError(
            "pgvector cache schema is missing. Run `python scripts/migrate.py` first."
        )


async def _seed_cache(session: Any) -> None:
    """Upsert a small set of cache examples with valid vectors."""
    from sqlalchemy import text

    for source_text in MOCK_CACHE_TEXTS:
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        embedding = _fake_embedding(source_text)
        if "положитель" in source_text or "понравилось" in source_text:
            sentiment = "POSITIVE"
            score = 0.91
            response = "Спасибо за тёплые слова — будем рады видеть вас снова!"
        elif "нейтральн" in source_text:
            sentiment = "NEUTRAL"
            score = 0.72
            response = "Спасибо, что поделились впечатлением. Учтём ваше мнение."
        else:
            sentiment = "NEGATIVE"
            score = 0.87
            response = (
                "Спасибо, что сообщили. Мы проверим ситуацию и постараемся её "
                "исправить."
            )
        values = {
            "text_hash": text_hash,
            "text": source_text,
            "embedding": json.dumps(embedding, separators=(",", ":")),
            "sentiment": sentiment,
            "sentiment_score": score,
            "tags": ["demo", "service"],
            "suggested_response": response,
            "metadata": json.dumps({"seed": "tenable-serm-demo"}, ensure_ascii=False),
            "created_at": DEMO_NOW,
            "expires_at": DEMO_NOW + timedelta(days=365),
        }
        await session.execute(
            text(
                """
                INSERT INTO public.llm_cache (
                    text_hash, text, embedding, sentiment, sentiment_score,
                    tags, suggested_response, metadata, created_at, expires_at
                ) VALUES (
                    :text_hash, :text, CAST(:embedding AS vector),
                    :sentiment, :sentiment_score, :tags,
                    :suggested_response, :metadata, :created_at, :expires_at
                )
                ON CONFLICT (text_hash) DO UPDATE SET
                    text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding,
                    sentiment = EXCLUDED.sentiment,
                    sentiment_score = EXCLUDED.sentiment_score,
                    tags = EXCLUDED.tags,
                    suggested_response = EXCLUDED.suggested_response,
                    metadata = EXCLUDED.metadata,
                    expires_at = EXCLUDED.expires_at
                """
            ),
            values,
        )


def write_mock_json(data: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tenant-id",
        type=UUID,
        default=DEFAULT_TENANT_ID,
        help="UUID to use for the deterministic demo tenant.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "mock_reputation_data.json",
        help="Path for the frontend JSON fixture.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Write the JSON fixture without connecting to PostgreSQL.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    data = generate_seed_data(args.tenant_id)
    write_mock_json(data, args.output)
    print(
        f"Wrote {len(data['reviews'])} reviews for {len(data['platforms'])} "
        f"platforms to {args.output}"
    )
    if not args.json_only:
        await seed_database(data)
        print("Seeded PostgreSQL demo tenant, reviews, statistics, and cache vectors.")


if __name__ == "__main__":
    load_dotenv(ROOT / ".env", override=False)
    asyncio.run(main())
