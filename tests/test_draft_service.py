"""DraftService на in-memory двойнике БД: проверяем протокол транзакций, идемпотентность и инварианты набора.

Реальные RLS/индексы проверяет интеграционный прогон sql/028 на тестовой базе (см. conftest.py)."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.core.ai import (
    GenerationResult,
    GenerationSource,
    LLMPermanentError,
    TenantContext,
)
from app.core.ai.fallback import build_fallback_drafts
from app.core.ai.prompts import PROMPT_VERSION
from app.core.ai.schemas import DraftVariant, GeneratedDraft, Polarity, ReviewLike
from app.infrastructure.persistence.models.economics import Company
from app.services.draft_service import (
    DraftPersistenceError,
    DraftService,
    DraftsLockedError,
    ReviewNotFoundError,
)

TENANT = TenantContext(brand_name="Окна-Сервис")
REVIEW_ID = uuid4()
TEXTS = {
    DraftVariant.FORMAL: "Здравствуйте! Благодарим за обращение. Мы передали отзыв ответственному подразделению.",
    DraftVariant.EMPATHETIC: "Нам очень жаль, что визит оставил неприятное впечатление. Приносим извинения за неудобства.",
    DraftVariant.ACTION_ORIENTED: "Давайте разберёмся: опишите детали в ответном сообщении, и менеджер свяжется с вами.",
}


def llm_result() -> GenerationResult:
    return GenerationResult(
        drafts=tuple(GeneratedDraft(variant=v, text=t) for v, t in TEXTS.items()),
        source=GenerationSource.LLM,
        prompt_version=PROMPT_VERSION,
        attempts=1,
        latency_ms=5,
        model="test-model",
    )


def fallback_result() -> GenerationResult:
    return GenerationResult(
        drafts=build_fallback_drafts(TENANT, Polarity.NEGATIVE),
        source=GenerationSource.FALLBACK,
        prompt_version=PROMPT_VERSION,
        attempts=3,
        latency_ms=9,
        fallback_reason="llm_timeout",
        retryable=True,
    )


def test_tenant_context_uses_company_ai_settings() -> None:
    company = Company(
        name="Acme",
        average_check=0,
        margin_percent=0,
        cac=0,
        base_ltv=0,
        tone_of_voice="warm",
        compensation_policy="repeat service",
        support_channel="website form",
    )

    tenant = DraftService.tenant_context(company)

    assert tenant.brand_name == "Acme"
    assert tenant.tone_of_voice == "warm"
    assert tenant.compensation_policy == "repeat service"
    assert tenant.support_channel == "website form"


class FakeDb:
    def __init__(self, *, review_exists: bool = True) -> None:
        self.review_exists = review_exists
        self.rows: list[dict[str, Any]] = []
        self.open_sessions = 0
        self.insert_params: list[dict[str, Any]] = []
        self.drop_rows_on_insert: int | None = None  # эмуляция частичной вставки

    def row(self, **kw: Any) -> SimpleNamespace:
        return SimpleNamespace(**kw)

    def seed(
        self, status: str = "draft", generation: int = 1, source: str = "llm"
    ) -> None:
        for variant, content in TEXTS.items():
            self.rows.append(
                {
                    "id": uuid4(),
                    "review_id": REVIEW_ID,
                    "generation": generation,
                    "variant": variant.value,
                    "content": content,
                    "source": source,
                    "fallback_reason": None,
                    "model": "m",
                    "status": status,
                    "created_at": datetime.now(UTC),
                }
            )


class FakeResult:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def one_or_none(self) -> SimpleNamespace | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class FakeSession:
    def __init__(self, db: FakeDb) -> None:
        self.db = db

    async def execute(
        self, stmt: Any, params: dict[str, Any] | None = None
    ) -> FakeResult:
        sql = " ".join(str(stmt).split())
        params = params or {}
        db = self.db
        if "FROM public.reviews" in sql:
            if not db.review_exists:
                return FakeResult([])
            return FakeResult(
                [
                    SimpleNamespace(
                        id=REVIEW_ID,
                        rating=1,
                        body="Ждали два часа, никто не извинился.",
                        platform="yandex",
                        sentiment="NEGATIVE",
                        threat_level=2,
                    )
                ]
            )
        if sql.startswith("SELECT") and "ai_response_drafts" in sql:
            active = [r for r in db.rows if r["status"] in ("draft", "approved")]
            return FakeResult([SimpleNamespace(**r) for r in active])
        if sql.startswith("UPDATE"):
            for r in db.rows:
                if r["status"] == "draft":
                    r["status"] = "superseded"
            return FakeResult([])
        if sql.startswith("INSERT"):
            db.insert_params.append(params)
            if any(r["status"] in ("draft", "approved") for r in db.rows):
                return FakeResult(
                    []
                )  # конфликт уникального индекса: ON CONFLICT DO NOTHING
            generation = max((r["generation"] for r in db.rows), default=0) + 1
            created = []
            for variant, content in zip(
                params["variants"], params["contents"], strict=True
            ):
                created.append(
                    {
                        "id": uuid4(),
                        "review_id": params["review_id"],
                        "generation": generation,
                        "variant": variant,
                        "content": content,
                        "source": params["source"],
                        "fallback_reason": params["fallback_reason"],
                        "model": params["model"],
                        "status": "draft",
                        "created_at": datetime.now(UTC),
                    }
                )
            db.rows.extend(created)
            keep = (
                created
                if db.drop_rows_on_insert is None
                else created[: db.drop_rows_on_insert]
            )
            return FakeResult([SimpleNamespace(**r) for r in keep])
        raise AssertionError(f"неожиданный SQL: {sql[:80]}")


class FakeGenerator:
    def __init__(self, db: FakeDb, result: GenerationResult | Exception) -> None:
        self.db = db
        self.result = result
        self.calls = 0
        self.sessions_open_during_call: list[int] = []

    async def generate(
        self, review: ReviewLike, tenant: TenantContext
    ) -> GenerationResult:
        self.calls += 1
        self.sessions_open_during_call.append(self.db.open_sessions)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def make_service(
    db: FakeDb, result: GenerationResult | Exception
) -> tuple[DraftService, FakeGenerator]:
    @asynccontextmanager
    async def scope() -> Any:
        db.open_sessions += 1
        try:
            yield FakeSession(db)
        finally:
            db.open_sessions -= 1

    generator = FakeGenerator(db, result)
    return DraftService(generator, scope), generator  # type: ignore[arg-type]


async def test_creates_three_drafts_and_calls_llm_outside_db_transaction() -> None:
    db = FakeDb()
    service, generator = make_service(db, llm_result())
    saved = await service.generate_for_review(REVIEW_ID, TENANT)
    assert (
        saved.created and len(saved.drafts) == 3 and not saved.regeneration_recommended
    )
    assert [d.variant for d in saved.drafts] == list(DraftVariant)
    assert generator.sessions_open_during_call == [
        0
    ]  # соединение БД не удерживается во время вызова LLM
    assert (
        db.insert_params[0]["source"] == "llm"
        and db.insert_params[0]["model"] == "test-model"
    )


async def test_existing_set_is_returned_without_calling_llm() -> None:
    db = FakeDb()
    db.seed()
    service, generator = make_service(db, llm_result())
    saved = await service.generate_for_review(REVIEW_ID, TENANT)
    assert not saved.created and generator.calls == 0 and len(db.rows) == 3


async def test_parallel_worker_won_race_returns_its_set() -> None:
    db = FakeDb()
    service, generator = make_service(db, llm_result())
    original = generator.generate

    async def racing(review: ReviewLike, tenant: TenantContext) -> GenerationResult:
        result = await original(review, tenant)
        db.seed()  # другой воркер сохранил набор, пока мы ждали LLM
        return result

    generator.generate = racing  # type: ignore[method-assign]
    saved = await service.generate_for_review(REVIEW_ID, TENANT)
    assert not saved.created and len(saved.drafts) == 3 and len(db.rows) == 3


async def test_review_of_another_tenant_is_not_found() -> None:
    db = FakeDb(review_exists=False)
    service, generator = make_service(db, llm_result())
    with pytest.raises(ReviewNotFoundError):
        await service.generate_for_review(REVIEW_ID, TENANT)
    assert generator.calls == 0


async def test_regenerate_supersedes_drafts_and_bumps_generation() -> None:
    db = FakeDb()
    db.seed(source="fallback")
    service, generator = make_service(db, llm_result())
    saved = await service.generate_for_review(REVIEW_ID, TENANT, regenerate=True)
    assert saved.created and generator.calls == 1
    assert {r["generation"] for r in db.rows if r["status"] == "draft"} == {2}
    assert {r["status"] for r in db.rows if r["generation"] == 1} == {"superseded"}


async def test_approved_draft_blocks_regeneration() -> None:
    db = FakeDb()
    db.seed(status="approved")
    service, generator = make_service(db, llm_result())
    with pytest.raises(DraftsLockedError):
        await service.generate_for_review(REVIEW_ID, TENANT, regenerate=True)
    assert generator.calls == 0


async def test_fallback_set_is_saved_and_flagged_for_regeneration() -> None:
    db = FakeDb()
    service, _ = make_service(db, fallback_result())
    saved = await service.generate_for_review(REVIEW_ID, TENANT)
    assert saved.created and saved.regeneration_recommended
    assert (
        db.insert_params[0]["source"] == "fallback"
        and db.insert_params[0]["fallback_reason"] == "llm_timeout"
    )


async def test_permanent_llm_error_writes_nothing() -> None:
    db = FakeDb()
    service, _ = make_service(db, LLMPermanentError("HTTP 401"))
    with pytest.raises(LLMPermanentError):
        await service.generate_for_review(REVIEW_ID, TENANT)
    assert db.rows == [] and db.insert_params == []


async def test_partial_insert_is_an_error() -> None:
    db = FakeDb()
    db.drop_rows_on_insert = 2
    service, _ = make_service(db, llm_result())
    with pytest.raises(DraftPersistenceError):
        await service.generate_for_review(REVIEW_ID, TENANT)


async def test_get_active_returns_none_without_drafts() -> None:
    db = FakeDb()
    service, _ = make_service(db, llm_result())
    assert await service.get_active(REVIEW_ID) is None
    db.seed()
    found = await service.get_active(REVIEW_ID)
    assert found is not None and len(found.drafts) == 3
