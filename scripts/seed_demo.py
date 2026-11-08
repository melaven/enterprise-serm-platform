"""Seed seven realistic B2B SaaS reviews for the existing demo tenant with SI analysis."""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.schemas.economics import ReplyModerationStatus, ReviewStatus
from app.core.database import DATABASE_URL, AsyncSessionLocal, engine
from app.core.tenant_session import set_tenant_rls_context
from app.domain.reviews.state import ReviewState
from app.infrastructure.persistence.models.economics import Company, Review
from app.infrastructure.persistence.models.outbox_event import (
    OutboxEvent,
    OutboxEventType,
)

logger = logging.getLogger("seed_demo")

DEMO_TENANT_ID = UUID("d3b20001-0000-4000-8000-000000000001")
DEMO_COMPANY_NAME = "Демо: SentiGuard SaaS"
OUTBOX_SOURCE = "scripts.seed_demo"
LOCAL_DATABASE_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "db",
    "postgres",
    "host.docker.internal",
}


@dataclass(frozen=True)
class DemoReview:
    external_id: str
    author_name: str
    text: str
    rating: int
    reply_status: str
    moderation_status: ReplyModerationStatus
    state: ReviewState
    sentiment: str
    generated_reply: str | None = None


REVIEWS: tuple[DemoReview, ...] = (
    DemoReview(
        external_id="demo-b2b-support-001",
        author_name="Андрей М.",
        text=(
            "На тарифе Enterprise уже второй месяц не можем добиться нормального "
            "ответа по инциденту. Тикет сначала закрыли как решённый, хотя проблема "
            "с вебхуками никуда не делась, потом сутки тишины. Для продукта, который "
            "обещает SLA, это совсем не тот уровень поддержки."
        ),
        rating=1,
        reply_status="pending",
        moderation_status=ReplyModerationStatus.NEW,
        state=ReviewState.NEW,
        sentiment="NEGATIVE",
    ),
    DemoReview(
        external_id="demo-b2b-bug-002",
        author_name="Мария К.",
        text=(
            "После последнего релиза интеграция с нашей CRM стала дублировать "
            "сделки, а часть событий вообще теряется. Откатить изменения со своей "
            "стороны нельзя, саппорт попросил прислать логи и пропал. Мы потратили "
            "полдня на ручную сверку данных."
        ),
        rating=2,
        reply_status="pending",
        moderation_status=ReplyModerationStatus.NEW,
        state=ReviewState.NEW,
        sentiment="NEGATIVE",
    ),
    DemoReview(
        external_id="demo-b2b-onboarding-003",
        author_name="Илья С.",
        text=(
            "Онбординг прошёл без лишней бюрократии: за одну встречу настроили "
            "роли, импортировали команду и разобрали интеграцию по API. До идеала "
            "ещё есть что докрутить, но стартовали быстрее, чем планировали."
        ),
        rating=4,
        reply_status="draft",
        moderation_status=ReplyModerationStatus.DRAFTED,
        state=ReviewState.DRAFT_PENDING,
        sentiment="POSITIVE",
        generated_reply=(
            "Илья, спасибо за отзыв! Рады, что команда смогла быстро пройти "
            "онбординг и запустить интеграцию. Передадим ваши замечания по "
            "дальнейшей настройке продуктовой команде."
        ),
    ),
    DemoReview(
        external_id="demo-b2b-analytics-004",
        author_name="Екатерина Л.",
        text=(
            "Пользуемся платформой полгода. Отчёты по командам наконец собрали в "
            "одном месте, руководителям стало проще видеть просрочки. Иногда "
            "дашборд обновляется не мгновенно, но для наших процессов это не "
            "критично."
        ),
        rating=5,
        reply_status="draft",
        moderation_status=ReplyModerationStatus.DRAFTED,
        state=ReviewState.DRAFT_PENDING,
        sentiment="POSITIVE",
        generated_reply=(
            "Екатерина, благодарим за доверие и подробную обратную связь. "
            "Здорово, что отчёты помогают командам быстрее видеть статус задач. "
            "Проверим, как можно сократить задержку обновления дашборда."
        ),
    ),
    DemoReview(
        external_id="demo-b2b-api-005",
        author_name="Денис Р.",
        text=(
            "Документация по API понятная, большую часть подключения сделали сами. "
            "На тестовом контуре всё завелось с первого раза, а на боевом пришлось "
            "уточнить пару нюансов по лимитам. В целом хороший рабочий инструмент."
        ),
        rating=4,
        reply_status="draft",
        moderation_status=ReplyModerationStatus.DRAFTED,
        state=ReviewState.DRAFT_PENDING,
        sentiment="POSITIVE",
        generated_reply=(
            "Денис, спасибо, что поделились опытом интеграции. Рады, что "
            "документация помогла быстро запустить тестовый контур. Учтём замечание "
            "по лимитам и проверим, достаточно ли подробно этот раздел описан."
        ),
    ),
    DemoReview(
        external_id="demo-b2b-security-006",
        author_name="Ольга Н.",
        text=(
            "Внедряли сервис для нескольких подразделений. Понравились гибкие роли "
            "доступа и аудит действий — службе безопасности было проще согласовать "
            "запуск. Поддержка помогла с настройкой SSO без затяжной переписки."
        ),
        rating=5,
        reply_status="published",
        moderation_status=ReplyModerationStatus.PUBLISHED,
        state=ReviewState.PUBLISHED,
        sentiment="POSITIVE",
        generated_reply=(
            "Ольга, спасибо за высокую оценку! Нам важно, чтобы запуск в крупных "
            "командах проходил предсказуемо и с учётом требований безопасности. "
            "Рады, что коллеги помогли настроить SSO."
        ),
    ),
    DemoReview(
        external_id="demo-b2b-implementation-007",
        author_name="Павел В.",
        text=(
            "Работаем с платформой больше года. Внедрение заняло чуть дольше "
            "первоначального плана, зато после настройки процессы стали прозрачнее, "
            "а ручных сверок заметно меньше. Для B2B-команды решение себя оправдало."
        ),
        rating=4,
        reply_status="published",
        moderation_status=ReplyModerationStatus.PUBLISHED,
        state=ReviewState.PUBLISHED,
        sentiment="POSITIVE",
        generated_reply=(
            "Павел, благодарим за отзыв и за то, что остаетесь с нами. Рады, что "
            "после внедрения команде стало проще контролировать процессы и меньше "
            "времени тратить на ручные сверки."
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--create-tenant",
        action="store_true",
        help=(
            "Create the demo company with the configured DATABASE_URL before "
            "seeding. This option is restricted to local databases by default."
        ),
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow the configured database host to be remote.",
    )
    return parser.parse_args()


def admin_database_url() -> URL:
    url = make_url(DATABASE_URL)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("DATABASE_URL must use PostgreSQL for tenant setup.")
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+asyncpg")
    if url.drivername == "postgresql+asyncpg":
        return url
    raise RuntimeError("DATABASE_URL must use the asyncpg PostgreSQL driver.")


def verify_database_target(allow_remote: bool, create_tenant: bool) -> None:
    runtime_url = engine.url
    urls = [runtime_url]
    if create_tenant:
        admin_url = admin_database_url()
        urls.append(admin_url)
        if (
            admin_url.host,
            admin_url.port,
            admin_url.database,
        ) != (
            runtime_url.host,
            runtime_url.port,
            runtime_url.database,
        ):
            raise RuntimeError(
                "DATABASE_URL and TENANT_DATABASE_URL must point to the same "
                "database before creating the demo tenant."
            )

    if not allow_remote and any(url.host not in LOCAL_DATABASE_HOSTS for url in urls):
        raise RuntimeError(
            "Configured database host is not recognized as local. Seeding was "
            "stopped; use a local DATABASE_URL/TENANT_DATABASE_URL or pass "
            "--allow-remote only when the remote target is intentional."
        )


async def create_demo_tenant() -> None:
    url = admin_database_url()
    admin_engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__seed_demo_{uuid4()}__",
        },
    )
    session_factory = async_sessionmaker(admin_engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            try:
                await session.execute(
                    pg_insert(Company)
                    .values(
                        id=DEMO_TENANT_ID,
                        name=DEMO_COMPANY_NAME,
                        average_check=25000.0,
                        margin_percent=35.0,
                        cac=18000.0,
                        base_ltv=240000.0,
                    )
                    .on_conflict_do_nothing(index_elements=[Company.id])
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await admin_engine.dispose()

    logger.info("Demo company %s is ready.", DEMO_TENANT_ID)


def make_review(
    template: DemoReview,
    created_at: datetime,
    *,
    published_at: datetime | None = None,
) -> Review:
    review_id = uuid5(NAMESPACE_URL, f"{DEMO_TENANT_ID}/{template.external_id}")
    return Review(
        id=review_id,
        company_id=DEMO_TENANT_ID,
        platform="B2B SaaS",
        external_id=template.external_id,
        author_name=template.author_name,
        rating=template.rating,
        text=template.text,
        status=ReviewStatus.NEW,
        moderation_status=template.moderation_status,
        state=template.state,
        sentiment=template.sentiment,
        generated_reply=template.generated_reply,
        reply_status=template.reply_status,
        published_at=published_at,
        created_at=created_at,
        is_analyzed=template.generated_reply is not None,
        is_critical=template.rating <= 2,
        ai_pending=template.reply_status == "pending",  # Note: Internal field, kept as-is for DB compatibility
        analysis_tags=["support", "enterprise"]
        if template.rating <= 2
        else ["b2b", "saas"],
        tags=["support", "enterprise"] if template.rating <= 2 else ["b2b", "saas"],
    )


async def seed_demo_reviews() -> None:
    now = datetime.now(UTC)
    review_rows = [
        make_review(template, now - timedelta(days=14 - index))
        for index, template in enumerate(REVIEWS[:5])
    ]
    review_rows.extend(
        (
            make_review(
                REVIEWS[5],
                now - timedelta(days=75),
                published_at=now - timedelta(days=75),
            ),
            make_review(
                REVIEWS[6],
                now - timedelta(days=48),
                published_at=now - timedelta(days=48),
            ),
        )
    )

    async with AsyncSessionLocal() as session:
        try:
            await set_tenant_rls_context(session, DEMO_TENANT_ID)

            company_id = await session.scalar(
                select(Company.id).where(Company.id == DEMO_TENANT_ID)
            )
            if company_id is None:
                raise RuntimeError(
                    f"Demo company {DEMO_TENANT_ID} does not exist in the "
                    "configured database. Re-run with --create-tenant against "
                    "a local database to create it with DATABASE_URL."
                )

            stale_event_ids = await session.scalars(
                select(OutboxEvent.id).where(
                    OutboxEvent.status == "pending",
                    OutboxEvent.payload["source"].as_string() == OUTBOX_SOURCE,
                    OutboxEvent.payload["tenant_id"].as_string() == str(DEMO_TENANT_ID),
                )
            )
            for event_id in stale_event_ids:
                result = await session.scalar(
                    text(
                        "SELECT public.set_outbox_event_status("
                        ":event_id, 'processed')"
                    ),
                    {"event_id": event_id},
                )
                if result is not True:
                    raise RuntimeError(
                        f"Could not retire stale demo outbox event {event_id}."
                    )

            await session.execute(
                delete(Review).where(Review.company_id == DEMO_TENANT_ID)
            )
            session.add_all(review_rows)

            for review in review_rows[:2]:
                session.add(
                    OutboxEvent(
                        event_type=OutboxEventType.REVIEW_CREATED,
                        payload={
                            "review_id": str(review.id),
                            "tenant_id": str(DEMO_TENANT_ID),
                            "source": OUTBOX_SOURCE,
                        },
                        priority=1,
                    )
                )

            await session.commit()
        except Exception:
            await session.rollback()
            raise

    logger.info(
        "Seeded %d demo reviews for tenant %s (2 awaiting SI analysis, 3 drafts, "
        "2 published).",
        len(review_rows),
        DEMO_TENANT_ID,
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    verify_database_target(args.allow_remote, args.create_tenant)
    try:
        if args.create_tenant:
            await create_demo_tenant()
        await seed_demo_reviews()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
