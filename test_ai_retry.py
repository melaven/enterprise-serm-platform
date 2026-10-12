import asyncio
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.repositories.pending_types import ClaimedReview, Failure, Success
from app.schemas.ai import Sentiment
from app.schemas.parser import Platform, RawReview
from app.services.ai_processor import EnrichedReview
from app.worker.ai_retry import (
    AIRetryConfig,
    classify,
    next_attempt_delay,
    retry_pending_ai_reviews,
)

CFG = AIRetryConfig(max_attempts=3, claim_batch=2, max_per_tenant=4, time_budget_s=30)
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def raw(i: int) -> RawReview:
    return RawReview(f"e{i}", Platform.TRUSTPILOT, "a", 5, f"t{i}", None)


def claimed(i: int, attempts: int = 1, *, bad: bool = False) -> ClaimedReview:
    return ClaimedReview(UUID(int=i), attempts, None if bad else raw(i))


def ok(r: RawReview) -> EnrichedReview:
    return EnrichedReview(r, Sentiment.POSITIVE, ("x",), "thanks", False, False)


def pending(r: RawReview, err: str) -> EnrichedReview:
    return EnrichedReview(r, None, (), None, False, True, err)


class FakeStore:
    def __init__(self, queues: dict[UUID, list[ClaimedReview]], *, fail_claim: set[UUID] | None = None):
        self.queues = queues
        self.fail_claim = fail_claim or set()
        self.finalized: list[tuple[UUID, UUID, list[Success], list[Failure]]] = []
        self.tokens: list[UUID] = []
        self.lost = 0

    async def tenants_with_pending(self, limit: int) -> list[UUID]:
        return [t for t, q in self.queues.items() if q][:limit]

    async def claim(self, tenant_id, *, limit, token):
        if tenant_id in self.fail_claim:
            raise RuntimeError("db down")
        self.tokens.append(token)
        q = self.queues[tenant_id]
        batch, self.queues[tenant_id] = q[:limit], q[limit:]
        return batch

    async def finalize(self, tenant_id, token, successes, failures):
        self.finalized.append((tenant_id, token, successes, failures))
        return len(successes) + len(failures) - self.lost


class FakeEnricher:
    def __init__(self, fn=None, delay: float = 0.0):
        self.fn, self.delay, self.calls = fn or (lambda r: ok(r)), delay, []

    async def process(self, reviews: Sequence[RawReview]) -> list[EnrichedReview]:
        self.calls.append(list(reviews))
        if self.delay:
            await asyncio.sleep(self.delay)
        return [self.fn(r) for r in reviews]


def run(store, enricher, cfg=CFG):
    ctx = {"pending_store": store, "ai_processor": enricher, "ai_retry_config": cfg}
    return asyncio.run(retry_pending_ai_reviews(ctx))


def test_happy_path_batches_and_respects_per_tenant_cap():
    t = uuid4()
    store = FakeStore({t: [claimed(i) for i in range(10)]})
    summary = run(store, FakeEnricher())
    assert summary["claimed"] == 4 and summary["enriched"] == 4  # max_per_tenant=4, claim_batch=2
    assert len(store.finalized) == 2
    assert len(set(store.tokens)) == 2  # новый lease-токен на каждый claim


def test_fair_across_tenants():
    a, b = uuid4(), uuid4()
    store = FakeStore({a: [claimed(i) for i in range(10)], b: [claimed(100 + i) for i in range(10)]})
    summary = run(store, FakeEnricher())
    assert summary["tenants"] == 2 and summary["claimed"] == 8


def test_disabled_without_processor():
    store = FakeStore({uuid4(): [claimed(1)]})
    ctx = {"pending_store": store, "ai_processor": None, "ai_retry_config": CFG}
    assert asyncio.run(retry_pending_ai_reviews(ctx))["stopped"] == "disabled"
    assert not store.finalized


def test_content_failure_counts_attempt_and_backs_off():
    t = uuid4()
    store = FakeStore({t: [claimed(1, attempts=1)]})
    run(store, FakeEnricher(lambda r: pending(r, "invalid_output:x")))
    f = store.finalized[0][3][0]
    assert not f.give_up and not f.refund_attempt and f.error.startswith("invalid_output")


def test_content_failure_gives_up_on_last_attempt():
    t = uuid4()
    store = FakeStore({t: [claimed(1, attempts=3)]})
    summary = run(store, FakeEnricher(lambda r: pending(r, "invalid_output:x")))
    f = store.finalized[0][3][0]
    assert f.give_up and f.error.startswith("gave_up:") and summary["gave_up"] == 1


def test_provider_outage_refunds_attempts_and_stops_run():
    a, b = uuid4(), uuid4()
    store = FakeStore({a: [claimed(1, attempts=3)], b: [claimed(2)]})
    enricher = FakeEnricher(lambda r: pending(r, "llm_unavailable"))
    summary = run(store, enricher)
    f = store.finalized[0][3][0]
    assert f.refund_attempt and not f.give_up  # даже на последней попытке не «убиваем»
    assert summary["stopped"] == "provider_down"
    assert len(enricher.calls) == 1  # второй арендатор не тронут


def test_partial_success_does_not_stop_run():
    t = uuid4()
    store = FakeStore({t: [claimed(1), claimed(2)]})
    run(store, FakeEnricher(lambda r: ok(r) if r.external_id == "e1" else pending(r, "llm_unavailable")))
    _, _, succ, fail = store.finalized[0]
    assert len(succ) == 1 and len(fail) == 1


def test_bad_row_is_closed_without_llm_call():
    t = uuid4()
    store = FakeStore({t: [claimed(1, bad=True)]})
    enricher = FakeEnricher()
    run(store, enricher)
    f = store.finalized[0][3][0]
    assert f.give_up and f.error == "gave_up:bad_row" and not enricher.calls


def test_enricher_crash_is_contained():
    t = uuid4()

    def boom(r):
        raise RuntimeError("bug")

    store = FakeStore({t: [claimed(1)]})
    summary = run(store, FakeEnricher(boom))
    f = store.finalized[0][3][0]
    assert f.error == "internal_error" and not f.give_up
    assert summary["failed"] == 1


def test_timeout_is_provider_side():
    t = uuid4()
    cfg = AIRetryConfig(max_attempts=3, claim_batch=2, process_timeout_s=0.05, lease_s=1.0, time_budget_s=30)
    store = FakeStore({t: [claimed(1, attempts=3)]})
    run(store, FakeEnricher(delay=1.0), cfg)
    f = store.finalized[0][3][0]
    assert f.error == "processing_timeout" and f.refund_attempt and not f.give_up


def test_one_tenant_db_failure_does_not_block_others():
    a, b = uuid4(), uuid4()
    store = FakeStore({a: [claimed(1)], b: [claimed(2)]}, fail_claim={a})
    summary = run(store, FakeEnricher())
    assert summary["enriched"] == 1


def test_tenant_discovery_failure_returns_summary():
    class Broken(FakeStore):
        async def tenants_with_pending(self, limit):
            raise RuntimeError("db")

    assert run(Broken({}), FakeEnricher())["stopped"] == "db_error"


def test_lease_lost_is_reported():
    t = uuid4()
    store = FakeStore({t: [claimed(1), claimed(2)]})
    store.lost = 1
    assert run(store, FakeEnricher())["lease_lost"] >= 1


def test_time_budget_stops_run():
    t = uuid4()
    cfg = AIRetryConfig(max_attempts=3, claim_batch=1, max_per_tenant=100, time_budget_s=0.05, lease_s=10, process_timeout_s=5)
    store = FakeStore({t: [claimed(i) for i in range(50)]})
    t0 = time.monotonic()
    summary = run(store, FakeEnricher(delay=0.03), cfg)
    assert summary["claimed"] < 50 and time.monotonic() - t0 < 2


def test_skipped_empty_text_counts_as_success():
    t = uuid4()
    store = FakeStore({t: [claimed(1)]})
    run(store, FakeEnricher(lambda r: EnrichedReview(r, None, (), None, False, False, "empty_text")))
    assert len(store.finalized[0][2]) == 1


def test_backoff_schedule_and_classify_next_time():
    assert [next_attempt_delay(n, CFG) for n in (1, 2, 3)] == [3600, 7200, 14400]
    assert next_attempt_delay(30, CFG) == CFG.backoff_cap_s
    f = classify(claimed(1, 1), pending(raw(1), "invalid_output"), "invalid_output", CFG, NOW)
    assert isinstance(f, Failure) and (f.next_attempt_at - NOW).total_seconds() == 3600


def test_config_rejects_timeout_ge_lease():
    try:
        AIRetryConfig(process_timeout_s=900, lease_s=900)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
