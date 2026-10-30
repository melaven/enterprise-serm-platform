"""Логика DLQ на фейковой сессии (SQL проверяется отдельно на PostgreSQL) + интеграция с пайплайном."""

import asyncio
import sys
import types
from types import SimpleNamespace
from uuid import uuid4

if "sqlalchemy" not in sys.modules:
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        sa = types.ModuleType("sqlalchemy")
        sa.text = lambda s: s
        ext = types.ModuleType("sqlalchemy.ext")
        asy = types.ModuleType("sqlalchemy.ext.asyncio")
        asy.AsyncSession = object
        sys.modules.update(
            {"sqlalchemy": sa, "sqlalchemy.ext": ext, "sqlalchemy.ext.asyncio": asy}
        )

import logging

import app.infrastructure.queue.review_dlq as review_dlq


class Result:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


class FakeDb:
    """Эмулирует _RECORD_FAILURE: retry_count + 1, DLQ на пороге; уже изолированный отзыв не трогает."""

    def __init__(self, retry=0, in_dlq=False, exists=True):
        self.retry, self.in_dlq, self.exists, self.params = retry, in_dlq, exists, []

    async def execute(self, stmt, params):
        self.params.append(params)
        if not self.exists:
            return Result(None)
        if stmt is review_dlq._RECORD_FAILURE:
            if self.in_dlq:
                return Result(None)
            self.retry += 1
            self.in_dlq = self.retry >= params["max_retries"]
            return Result(SimpleNamespace(retry_count=self.retry, in_dlq=self.in_dlq))
        if stmt is review_dlq._MOVE:
            self.retry = max(self.retry, params["retry_count"] or self.retry)
            self.in_dlq = True
            return Result(SimpleNamespace(retry_count=self.retry))
        raise AssertionError(stmt)


def run(c):
    return asyncio.run(c)


def test_third_failure_moves_to_dlq_with_critical_log(caplog):
    db, rid = FakeDb(), uuid4()
    with caplog.at_level(logging.WARNING, logger="review_dlq"):
        outs = [
            run(review_dlq.record_analysis_failure(rid, "bad_json", db))
            for _ in range(3)
        ]
    assert [o.moved_to_dlq for o in outs] == [False, False, True] and outs[
        -1
    ].retry_count == 3
    crit = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert len(crit) == 1 and "review_moved_to_dlq" in crit[0].getMessage()


def test_already_in_dlq_or_missing_not_counted():
    assert (
        run(review_dlq.record_analysis_failure(uuid4(), "x", FakeDb(in_dlq=True)))
        is None
    )
    assert (
        run(review_dlq.record_analysis_failure(uuid4(), "x", FakeDb(exists=False)))
        is None
    )


def test_move_review_to_dlq_sets_retry_and_cleans_reason():
    db = FakeDb(retry=1)
    assert (
        run(
            review_dlq.move_review_to_dlq(
                uuid4(), "  bad \n json " + "я" * 900, db, retry_count=3
            )
        )
        is True
    )
    p = db.params[0]
    assert db.retry == 3 and db.in_dlq and p["retry_count"] == 3
    assert len(p["reason"]) == review_dlq.MAX_REASON_LEN and "\n" not in p["reason"]
    assert (
        run(review_dlq.move_review_to_dlq(uuid4(), "x", FakeDb(exists=False))) is False
    )


def test_empty_reason_gets_placeholder():
    db = FakeDb()
    run(review_dlq.move_review_to_dlq(uuid4(), "   ", db))
    assert db.params[0]["reason"] == "unknown"
