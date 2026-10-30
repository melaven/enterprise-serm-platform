"""Generate demo reviews and seed them into the configured tenant database."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

logger = logging.getLogger("seed_demo_reviews")

PlatformName = Literal["yandex", "2gis", "google", "zoon"]
Sentiment = Literal["negative", "neutral", "positive"]
ModerationStatus = Literal["new", "drafted", "pending_moderation", "published"]

ROOT = Path(__file__).resolve().parents[1]
MOCK_PATH = ROOT / "frontend" / "src" / "mocks" / "reviews_mock.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class ReviewRecord:
    id: UUID
    branch_id: UUID
    author_name: str
    text: str
    rating: int
    platform: PlatformName
    created_at: datetime
    sentiment: Sentiment
    moderation_status: ModerationStatus


@dataclass(frozen=True)
class ReviewTemplate:
    branch: str
    author_name: str
    text: str
    rating: int
    moderation_status: ModerationStatus


BRANCHES: tuple[tuple[str, str], ...] = (
    ("Автосервис «Мотор»", "Автосервис"),
    ("Ресторан «Север»", "Ресторан"),
    ("Стоматология «Улыбка»", "Стоматология"),
)

TEMPLATES: tuple[ReviewTemplate, ...] = (
    ReviewTemplate(
        "Автосервис «Мотор»",
        "Алексей В.",
        "Приехал на замену масла по записи, но мастер разговаривал откровенно "
        "по-хамски и на вопросы отвечал с раздражением. Работу сделали быстро, "
        "но возвращаться после такого общения не хочется.",
        1,
        "new",
    ),
    ReviewTemplate(
        "Автосервис «Мотор»",
        "Марина С.",
        "После замены тормозных колодок появился скрип и машину стало уводить "
        "вправо. На повторном визите проблему признали, но предложили снова "
        "оплатить диагностику. Очень неприятный опыт.",
        1,
        "new",
    ),
    ReviewTemplate(
        "Автосервис «Мотор»",
        "Дмитрий К.",
        "Записали на 10 утра, машину приняли только через полтора часа. "
        "Никаких извинений, администратор просто сказал, что «все ждут». "
        "О сроках ремонта тоже сообщили уже после начала работ.",
        2,
        "drafted",
    ),
    ReviewTemplate(
        "Автосервис «Мотор»",
        "Олег Н.",
        "После ремонта подвески обнаружил незакреплённую защиту двигателя. "
        "Позвонил — обещали разобраться, но за три дня так и не перезвонили. "
        "Пришлось ехать в другой сервис.",
        1,
        "pending_moderation",
    ),
    ReviewTemplate(
        "Автосервис «Мотор»",
        "Ирина П.",
        "Цена в заказ-наряде в итоге оказалась почти на треть выше озвученной "
        "по телефону. Дополнительные работы согласовали уже перед выдачей "
        "машины, когда отказаться было неудобно.",
        2,
        "new",
    ),
    ReviewTemplate(
        "Автосервис «Мотор»",
        "Павел Р.",
        "Мастер внимательно объяснил, что действительно нужно менять, а что "
        "может подождать. Сделали диагностику и ремонт в тот же день, стоимость "
        "совпала с предварительной оценкой. Спасибо за честный подход.",
        5,
        "published",
    ),
    ReviewTemplate(
        "Автосервис «Мотор»",
        "Сергей Л.",
        "Замена аккумулятора прошла без проблем: приняли вовремя, проверили "
        "генератор и показали результаты замеров. Вежливый персонал и понятный "
        "заказ-наряд.",
        4,
        "published",
    ),
    ReviewTemplate(
        "Автосервис «Мотор»",
        "Виктория Д.",
        "Обычное ТО без сюрпризов: записали по телефону, управились примерно "
        "за два часа. Комната ожидания небольшая, но чистая.",
        3,
        "new",
    ),
    ReviewTemplate(
        "Ресторан «Север»",
        "Екатерина М.",
        "Ждали горячее больше часа, хотя зал был заполнен примерно наполовину. "
        "Официант несколько раз проходил мимо и на вопрос о заказе ответил "
        "довольно грубо. Блюда принесли остывшими.",
        1,
        "new",
    ),
    ReviewTemplate(
        "Ресторан «Север»",
        "Антон Б.",
        "В салате попался кусок пластика. Позвали администратора — он извинился "
        "без особого желания и просто убрал блюдо из счёта. Ситуация опасная, "
        "а реакции заведения недостаточно.",
        1,
        "pending_moderation",
    ),
    ReviewTemplate(
        "Ресторан «Север»",
        "Наталья Е.",
        "Бронировали столик на день рождения, но по приезде свободного места "
        "не оказалось. Предложили подождать у входа без конкретного времени. "
        "Праздник пришлось перенести в другое место.",
        1,
        "drafted",
    ),
    ReviewTemplate(
        "Ресторан «Север»",
        "Роман Т.",
        "Заказ приняли быстро, а потом про нас забыли. Через 50 минут выяснилось, "
        "что блюда ещё даже не начали готовить. Извинений не услышали, хотя "
        "добавили позиции в счёт полностью.",
        2,
        "new",
    ),
    ReviewTemplate(
        "Ресторан «Север»",
        "Ольга Ф.",
        "В меню указана одна цена, в счёте оказалось дороже — объяснили, что "
        "меню давно не обновляли. Персонал отвечал резко, вопрос решить на месте "
        "не удалось.",
        2,
        "pending_moderation",
    ),
    ReviewTemplate(
        "Ресторан «Север»",
        "Михаил З.",
        "Очень внимательный официант помог подобрать блюда для гостей с "
        "ограничениями по питанию. Подача красивая, всё горячее и вкусное. "
        "Обязательно придём ещё.",
        5,
        "published",
    ),
    ReviewTemplate(
        "Ресторан «Север»",
        "Юлия А.",
        "Уютный зал, быстрое обслуживание и вкусный бизнес-ланч. Особенно "
        "понравилось, что официант уточнил, когда принести десерт, чтобы не "
        "торопить встречу.",
        5,
        "published",
    ),
    ReviewTemplate(
        "Ресторан «Север»",
        "Кирилл Г.",
        "Еда в целом хорошая, но пришлось попросить счёт дважды и долго ждать "
        "оплату. Для обеда в рабочий день хотелось бы чуть быстрее.",
        3,
        "new",
    ),
    ReviewTemplate(
        "Стоматология «Улыбка»",
        "Светлана И.",
        "Врач начал приём почти на 40 минут позже, а администратор даже не "
        "предупредил о задержке. На вопросы о плане лечения доктор отвечал "
        "резко и торопился. Больше записываться не буду.",
        1,
        "new",
    ),
    ReviewTemplate(
        "Стоматология «Улыбка»",
        "Андрей Ч.",
        "После установки пломбы она мешает прикусу, больно жевать. Позвонил "
        "в клинику — ближайшую коррекцию предложили только через неделю. "
        "Ожидал более внимательного отношения после лечения.",
        1,
        "drafted",
    ),
    ReviewTemplate(
        "Стоматология «Улыбка»",
        "Татьяна О.",
        "До визита назвали одну стоимость, а на приёме добавили несколько "
        "обязательных услуг. Объяснение было непонятным, на просьбу показать "
        "расчёт администратор ответила с раздражением.",
        2,
        "pending_moderation",
    ),
    ReviewTemplate(
        "Стоматология «Улыбка»",
        "Елена Р.",
        "Записалась на консультацию, но врач уделил мне меньше десяти минут и "
        "сразу предложил дорогое лечение. На вопросы о других вариантах ответил "
        "неохотно.",
        2,
        "new",
    ),
    ReviewTemplate(
        "Стоматология «Улыбка»",
        "Владимир П.",
        "Лечение прошло спокойно и практически безболезненно. Врач заранее "
        "объяснял каждый этап, администратор напомнил о визите и помог подобрать "
        "удобное время.",
        5,
        "published",
    ),
    ReviewTemplate(
        "Стоматология «Улыбка»",
        "Алёна К.",
        "Чистая клиника, приветливый ресепшен, приём начался вовремя. Доктор "
        "подробно ответил на вопросы и составил понятный план без навязывания "
        "дополнительных процедур.",
        4,
        "published",
    ),
    ReviewTemplate(
        "Стоматология «Улыбка»",
        "Галина М.",
        "На первичном осмотре всё прошло корректно, оборудование современное. "
        "Окончательную стоимость лечения хотелось бы узнать заранее, до "
        "дополнительных снимков.",
        3,
        "new",
    ),
    ReviewTemplate(
        "Стоматология «Улыбка»",
        "Игорь С.",
        "Был на профгигиене: врач работал аккуратно, рассказал, как ухаживать "
        "за зубами дома, и не навязывал лишнее. Персонал вежливый, клиника "
        "оставила хорошее впечатление.",
        5,
        "published",
    ),
)

PLATFORMS: tuple[PlatformName, ...] = ("yandex", "2gis", "google", "zoon")


def _branch_id(branch_name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"tenable-demo-branch:{branch_name}")


def generate_reviews(rng: random.Random | None = None) -> list[ReviewRecord]:
    """Generate 24 varied reviews, with more than half rated one or two stars."""
    generator = rng if rng is not None else random.Random()
    templates = list(TEMPLATES)
    generator.shuffle(templates)
    now = datetime.now(timezone.utc)

    reviews: list[ReviewRecord] = []
    for index, template in enumerate(templates):
        rating = template.rating
        sentiment: Sentiment
        if rating <= 2:
            sentiment = "negative"
        elif rating == 3:
            sentiment = "neutral"
        else:
            sentiment = "positive"

        created_at = now - timedelta(
            days=generator.randint(1, 90),
            hours=generator.randint(0, 23),
            minutes=generator.randint(0, 59),
        )
        reviews.append(
            ReviewRecord(
                id=uuid4(),
                branch_id=_branch_id(template.branch),
                author_name=template.author_name,
                text=template.text,
                rating=rating,
                platform=PLATFORMS[index % len(PLATFORMS)],
                created_at=created_at,
                sentiment=sentiment,
                moderation_status=template.moderation_status,
            )
        )

    return reviews


def write_mock_dump(reviews: list[ReviewRecord]) -> None:
    MOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            **asdict(review),
            "id": str(review.id),
            "branch_id": str(review.branch_id),
            "created_at": review.created_at.isoformat().replace("+00:00", "Z"),
        }
        for review in reviews
    ]
    MOCK_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


async def seed_database(reviews: list[ReviewRecord]) -> bool:
    """Insert reviews for an explicitly selected, visible tenant."""
    try:
        from sqlalchemy import select, text
        from sqlalchemy.exc import SQLAlchemyError

        from app.core.database import AsyncSessionLocal, engine
        from app.infrastructure.persistence.models.economics import Company, Platform, ReplyModerationStatus, Review, ReviewStatus

        company_id_value = os.getenv("DEMO_COMPANY_ID")
        if not company_id_value:
            logger.warning(
                "DEMO_COMPANY_ID is not set; writing reviews to the frontend JSON "
                "mock instead of selecting a tenant implicitly."
            )
            await engine.dispose()
            return False

        company_id = UUID(company_id_value)
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("SELECT set_config('app.company_id', :company_id, true)"),
                {"company_id": str(company_id)},
            )
            company = await session.scalar(
                select(Company).where(Company.id == company_id)
            )
            if company is None:
                raise RuntimeError(
                    "The configured DEMO_COMPANY_ID is not visible in this database."
                )

            platform_rows = (
                await session.scalars(
                    select(Platform).where(Platform.company_id == company_id)
                )
            ).all()
            platform_by_name = {
                platform.name.casefold(): platform for platform in platform_rows
            }
            platform_ids: dict[PlatformName, UUID] = {}
            platform_aliases: dict[PlatformName, tuple[str, ...]] = {
                "yandex": ("yandex", "yandex maps"),
                "2gis": ("2gis",),
                "google": ("google", "google reviews", "google maps"),
                "zoon": ("zoon",),
            }
            for platform_name in PLATFORMS:
                platform = next(
                    (
                        platform_by_name[alias]
                        for alias in platform_aliases[platform_name]
                        if alias in platform_by_name
                    ),
                    None,
                )
                if platform is None:
                    platform = Platform(
                        company_id=company_id,
                        name=platform_name,
                        monthly_views=0,
                        conversion_rate=0.0,
                        cac_on_platform=0.0,
                        average_rating=0.0,
                    )
                    session.add(platform)
                    await session.flush()
                    platform_by_name[platform_name] = platform
                platform_ids[platform_name] = platform.id

            for review in reviews:
                session.add(
                    Review(
                        id=review.id,
                        company_id=company_id,
                        platform_id=platform_ids[review.platform],
                        branch_id=review.branch_id,
                        platform=review.platform,
                        author_name=review.author_name,
                        text=review.text,
                        rating=review.rating,
                        status=ReviewStatus.NEW,
                        moderation_status=ReplyModerationStatus(
                            review.moderation_status
                        ),
                        sentiment=review.sentiment,
                        created_at=review.created_at,
                        financial_impact=0.0,
                    )
                )
            await session.commit()
        await engine.dispose()
        return True
    except (ImportError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        logger.warning("Database seeding unavailable; using JSON mock: %s", exc)
        return False
    except SQLAlchemyError as exc:
        logger.warning("Database seeding failed; using JSON mock: %s", exc)
        return False


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    reviews = generate_reviews()
    if await seed_database(reviews):
        logger.info("Seeded %s demo reviews into the database.", len(reviews))
        return

    write_mock_dump(reviews)
    logger.info("Wrote %s demo reviews to %s.", len(reviews), MOCK_PATH)


if __name__ == "__main__":
    asyncio.run(main())
