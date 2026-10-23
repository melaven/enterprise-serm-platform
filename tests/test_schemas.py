from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from app.services.scrapers.schemas import RawReviewSchema, clean_text, to_utc

UTC = timezone.utc


def make(**overrides: Any) -> RawReviewSchema:
    data: dict[str, Any] = {
        "external_id": "r-1",
        "rating": 5,
        "published_at": "2026-01-15T10:00:00Z",
    }
    return RawReviewSchema(**{**data, **overrides})


# --- очистка текста ---------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  привет  ", "привет"),
        ("a b\tc   d", "a b c d"),  # NBSP, tab, повторные пробелы
        ("zero​width﻿", "zerowidth"),
        ("a\r\nb\rc", "a\nb\nc"),
        ("a \n\n\n\n b", "a\n\nb"),  # лишние пустые строки и пробелы у переноса
        ("é", "é"),  # NFC: e + combining acute -> é
        ("\x00bad\x07", "bad"),
    ],
)
def test_clean_text(raw: str, expected: str) -> None:
    assert clean_text(raw) == expected


def test_schema_cleans_text_author_reply() -> None:
    review = make(
        author_name="  Анна К. ", text="\n Отлично!  \n", reply_text=" Спасибо "
    )

    assert review.author_name == "Анна К."
    assert review.text == "Отлично!"
    assert review.reply_text == "Спасибо"


def test_defaults_for_missing_author_text_reply() -> None:
    review = make(author_name="   ", text=None, reply_text="  ")

    assert review.author_name == "Аноним"
    assert review.text == ""
    assert review.reply_text is None


# --- рейтинг -----------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [(4, 4), (4.0, 4), ("4", 4), (" 5 ", 5), ("4,5", 5), (4.4, 4), (3.5, 4), (1, 1)],
)
def test_rating_normalized(raw: Any, expected: int) -> None:
    assert make(rating=raw).rating == expected


@pytest.mark.parametrize("raw", [0, 6, -1, "abc", "nan", True, None, [5]])
def test_invalid_rating_rejected(raw: Any) -> None:
    with pytest.raises(ValidationError):
        make(rating=raw)


# --- даты --------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw",
    [
        1768471200,  # epoch, секунды
        1768471200000,  # epoch, миллисекунды
        "1768471200",
        "2026-01-15T10:00:00Z",
        "2026-01-15T15:00:00+05:00",
        "2026-01-15 10:00:00",  # naive -> UTC
        datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
        datetime(2026, 1, 15, 13, 0, tzinfo=timezone(timedelta(hours=3))),
    ],
)
def test_published_at_normalized_to_utc(raw: Any) -> None:
    result = make(published_at=raw).published_at

    assert result == datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    assert result.utcoffset() == timedelta(0)


def test_to_utc_attaches_utc_to_naive() -> None:
    assert to_utc(datetime(2026, 1, 1, 12)).tzinfo == UTC


@pytest.mark.parametrize(
    "raw", [None, "yesterday", "", True, "1999-12-31T00:00:00Z", [1], {}]
)
def test_invalid_published_at_rejected(raw: Any) -> None:
    with pytest.raises(ValidationError):
        make(published_at=raw)


def test_future_date_rejected() -> None:
    future = datetime.now(UTC) + timedelta(days=30)

    with pytest.raises(ValidationError, match="future"):
        make(published_at=future)


# --- остальное ---------------------------------------------------------------
def test_external_id_int_becomes_str_and_empty_rejected() -> None:
    assert make(external_id=12345).external_id == "12345"
    with pytest.raises(ValidationError):
        make(external_id="   ")


def test_unknown_fields_forbidden_and_model_frozen() -> None:
    with pytest.raises(ValidationError):
        make(unexpected="x")
    with pytest.raises(ValidationError):
        make().rating = 1  # type: ignore[misc]


def test_metadata_must_be_json_serializable_and_small() -> None:
    assert make(metadata={"likes": 3, "tags": ["a"]}).metadata == {
        "likes": 3,
        "tags": ["a"],
    }
    with pytest.raises(ValidationError, match="JSON"):
        make(metadata={"bad": object()})
    with pytest.raises(ValidationError, match="too large"):
        make(metadata={"blob": "x" * 20_000})
