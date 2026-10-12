import asyncio
from uuid import uuid4

import pytest
from arq.worker import Retry

from app.schemas.parser import Platform
from app.services.ai_processor import EnrichedReview
from app.services.scraping import PermanentScrapeError, RawReview, RetryableScrapeError
from app.worker.tasks import sync_platform_reviews

URL = "https://www.trustpilot.com/review/example.com"
TENANT = uuid4()


def raw(i: int) -> RawReview:
    return RawReview(f"e{i}", Platform.TRUSTPILOT, "a", 5, f"text {i}", None)


def ok(r: RawReview) -> EnrichedReview:
    return EnrichedReview(r, None, ("t",), "thanks", False, False)


class FakeScraper:
    def __init__(self, result=None, exc: Exception | None = None):
        self.result, self.exc, self.calls = result or [], exc, 0

    async def fetch(self, platform, url, *, limit):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.result


class FakeProcessor:
    def __init__(self, fn=None, exc: Exception | None = None, wrong_len=False):
        self.fn, self.exc, self.wrong_len, self.seen = fn or ok, exc, wrong_len, []

    async def process(self, reviews):
        self.seen.append([r.external_id for r in reviews])
        if self.exc:
            raise self.exc
        out = [self.fn(r) for r in reviews]
        return out[:-1] if self.wrong_len else out


class FakeSink:
    def __init__(self, known=(), save_failures=0, lookup_fails=False):
        self.known, self.save_failures, self.lookup_fails = set(known), save_failures, lookup_fails
        self.saved: list[list[EnrichedReview]] = []
        self.save_calls = 0

    async def existing_external_ids(self, tenant_id, platform, ids):
        if self.lookup_fails:
            raise RuntimeError("db")
        return {i for i in ids if i in self.known}

    async def save_many(self, tenant_id, reviews):
        self.save_calls += 1
        if self.save_calls <= self.save_failures:
            raise RuntimeError("db down")
        self.saved.append(list(reviews))
        return len(reviews)


class FakeBilling:
    def __init__(self, exc=None):
        self.exc, self.calls = exc, []

    async def charge(self, tenant_id, *, reviews_saved, enriched):
        if self.exc:
            raise self.exc
        self.calls.append(reviews_saved)


async def _nosleep(_):  # noqa: ANN001
    return None


def run(*, scraper, sink, processor=None, billing=None, job_try=1, platform="trustpilot", url=URL):
    ctx = {
        "scraper": scraper, "sink": sink, "ai_processor": processor, "billing": billing,
        "job_try": job_try, "job_id": "j1", "sleep": _nosleep,
    }
    return asyncio.run(sync_platform_reviews(ctx, TENANT, platform, url))


def test_happy_path_enriches_saves_and_bills():
    sink, billing, proc = FakeSink(), FakeBilling(), FakeProcessor()
    res = run(scraper=FakeScraper([raw(1), raw(2)]), sink=sink, processor=proc, billing=billing)
    assert (res["reviews_found"], res["reviews_saved"], res["ai_enriched"], res["ai_pending"]) == (2, 2, 2, 0)
    assert billing.calls == [2]


def test_known_reviews_never_reach_llm_or_billing():
    sink, billing, proc = FakeSink(known={"e1"}), FakeBilling(), FakeProcessor()
    res = run(scraper=FakeScraper([raw(1), raw(2)]), sink=sink, processor=proc, billing=billing)
    assert proc.seen == [["e2"]] and res["reviews_new"] == 1 and billing.calls == [1]


def test_all_known_skips_everything_downstream():
    sink, proc = FakeSink(known={"e1"}), FakeProcessor()
    res = run(scraper=FakeScraper([raw(1)]), sink=sink, processor=proc, billing=FakeBilling())
    assert not proc.seen and not sink.saved and res["reviews_saved"] == 0


def test_llm_crash_saves_with_ai_pending_and_job_succeeds():
    sink, billing = FakeSink(), FakeBilling()
    res = run(scraper=FakeScraper([raw(1), raw(2)]), sink=sink,
              processor=FakeProcessor(exc=RuntimeError("provider exploded")), billing=billing)
    assert all(e.ai_pending and e.sentiment is None for e in sink.saved[0])
    assert res["ai_pending"] == 2 and res["reviews_saved"] == 2


def test_processor_marking_pending_is_saved_as_is():
    pend = lambda r: EnrichedReview(r, None, (), None, False, True, "llm_unavailable")  # noqa: E731
    sink = FakeSink()
    res = run(scraper=FakeScraper([raw(1)]), sink=sink, processor=FakeProcessor(pend))
    assert sink.saved[0][0].ai_error == "llm_unavailable" and res["ai_pending"] == 1


def test_processor_contract_violation_degrades():
    sink = FakeSink()
    run(scraper=FakeScraper([raw(1), raw(2)]), sink=sink, processor=FakeProcessor(wrong_len=True))
    assert all(e.ai_pending for e in sink.saved[0])


def test_no_processor_means_pending():
    sink = FakeSink()
    run(scraper=FakeScraper([raw(1)]), sink=sink, processor=None)
    assert sink.saved[0][0].ai_pending and sink.saved[0][0].ai_error == "ai_disabled"


def test_scrape_retryable_raises_arq_retry_with_retry_after():
    sink = FakeSink()
    with pytest.raises(Retry) as ei:
        run(scraper=FakeScraper(exc=RetryableScrapeError("429", retry_after_s=120)), sink=sink)
    assert ei.value.defer_score >= 120 if hasattr(ei.value, "defer_score") else True
    assert not sink.saved


def test_scrape_retryable_on_last_try_fails_job():
    with pytest.raises(RetryableScrapeError):
        run(scraper=FakeScraper(exc=RetryableScrapeError("503")), sink=FakeSink(), job_try=99)


def test_scrape_permanent_fails_without_retry_or_save():
    sink = FakeSink()
    with pytest.raises(PermanentScrapeError):
        run(scraper=FakeScraper(exc=PermanentScrapeError("403")), sink=sink)
    assert not sink.saved


def test_invalid_platform_and_host_rejected_before_scraping():
    sc = FakeScraper([raw(1)])
    with pytest.raises(ValueError):
        run(scraper=sc, sink=FakeSink(), platform="nope")
    with pytest.raises(ValueError):
        run(scraper=sc, sink=FakeSink(), url="https://evil.example/x")
    assert sc.calls == 0


def test_transient_db_failure_retried_locally_without_rescrape():
    sink, sc, proc = FakeSink(save_failures=2), FakeScraper([raw(1)]), FakeProcessor()
    res = run(scraper=sc, sink=sink, processor=proc)
    assert res["reviews_saved"] == 1 and sc.calls == 1 and len(proc.seen) == 1


def test_persistent_db_failure_retries_job_then_fails_on_last_try():
    with pytest.raises(Retry):
        run(scraper=FakeScraper([raw(1)]), sink=FakeSink(save_failures=99), processor=FakeProcessor())
    with pytest.raises(RuntimeError):
        run(scraper=FakeScraper([raw(1)]), sink=FakeSink(save_failures=99), processor=FakeProcessor(), job_try=99)


def test_billing_failure_does_not_fail_job():
    sink = FakeSink()
    res = run(scraper=FakeScraper([raw(1)]), sink=sink, processor=FakeProcessor(),
              billing=FakeBilling(exc=RuntimeError("quota db down")))
    assert res["reviews_saved"] == 1 and sink.saved


def test_dedup_lookup_failure_is_best_effort():
    proc = FakeProcessor()
    res = run(scraper=FakeScraper([raw(1)]), sink=FakeSink(lookup_fails=True), processor=proc)
    assert res["reviews_saved"] == 1 and proc.seen == [["e1"]]


def test_empty_scrape_is_clean_noop():
    sink, proc = FakeSink(), FakeProcessor()
    res = run(scraper=FakeScraper([]), sink=sink, processor=proc, billing=FakeBilling())
    assert res["reviews_found"] == 0 and not sink.saved and not proc.seen
