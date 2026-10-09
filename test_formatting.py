import asyncio
from typing import Any

import pytest
from tg_bot.formatting import (
    TELEGRAM_LIMIT,
    extract_reviews,
    extract_url,
    format_rating,
    format_result,
    normalize_sentiment,
)
from tg_bot.jobs import JobRef, JobRegistry


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "https://yandex.ru/maps/org/cafe/123/",
            "https://yandex.ru/maps/org/cafe/123/",
        ),
        ("глянь https://2gis.ru/moscow/firm/1.", "https://2gis.ru/moscow/firm/1"),
        ("(https://google.com/maps/place/X)", "https://google.com/maps/place/X"),
        ("HTTP://Example.com/a?b=1&c=2, ок", "HTTP://Example.com/a?b=1&c=2"),
        ("привет", None),
        ("ftp://x.com/a", None),
        ("https://", None),
        ("", None),
    ],
)
def test_extract_url(text: str, expected: str | None) -> None:
    assert extract_url(text) == expected


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ("positive", "Позитивная"),
        ("POSITIVE", "Позитивная"),
        ("позитивная", "Позитивная"),
        ("Negative", "Негативная"),
        ("негативный", "Негативная"),
        ("neutral", "Нейтральная"),
        ("нейтральный", "Нейтральная"),
        ("mixed", "mixed"),
        (None, "Не определена"),
    ],
)
def test_normalize_sentiment(raw: Any, label: str) -> None:
    assert normalize_sentiment(raw)[1] == label


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(5, "★★★★★ 5/5"), ("4", "★★★★☆ 4/5"), (3.6, "★★★★☆ 4/5"), ("2,0", "★★☆☆☆ 2/5")],
)
def test_format_rating(raw: Any, expected: str) -> None:
    assert format_rating(raw) == expected


@pytest.mark.parametrize("raw", [0, 6, "abc", None, [5]])
def test_format_rating_invalid(raw: Any) -> None:
    assert format_rating(raw) is None


def test_extract_reviews_shapes() -> None:
    review = {"sentiment": "positive", "rating": 5}
    assert extract_reviews([review, "junk"]) == [review]
    assert extract_reviews({"reviews": [review]}) == [review]
    assert extract_reviews({"items": [review]}) == [review]
    assert extract_reviews(review) == [review]
    assert extract_reviews({"status": "ok"}) == []
    assert extract_reviews(None) == []


def test_format_result_card_contents() -> None:
    result = [
        {
            "rating": 2,
            "sentiment": "negative",
            "tags": ["сервис", "Цена"],
            "text": "Долго ждали",
            "suggested_reply": "Нам жаль, что так вышло.",
        }
    ]

    (message,) = format_result("job-1", result)

    assert "Готово" in message
    assert "😠" in message and "Негативная" in message
    assert "★★☆☆☆ 2/5" in message
    assert "#сервис" in message and "#цена" in message
    assert "<blockquote>Нам жаль, что так вышло.</blockquote>" in message
    assert "job-1" in message


def test_untrusted_text_is_escaped() -> None:
    result = {
        "sentiment": "positive",
        "suggested_reply": '<b>x</b> & <a href="http://evil">y</a>',
        "tags": ["<script>"],
    }

    (message,) = format_result("j<1>", result)

    assert "<a href" not in message and "<script>" not in message
    assert "&lt;b&gt;x&lt;/b&gt; &amp;" in message
    assert "j&lt;1&gt;" in message


def test_long_result_is_split_under_telegram_limit() -> None:
    reviews = [
        {
            "rating": 5,
            "sentiment": "positive",
            "text": "т" * 500,
            "suggested_reply": "о" * 3000,
            "tags": ["a"],
        }
        for _ in range(25)
    ]

    messages = format_result("job", {"reviews": reviews})

    assert len(messages) > 1
    assert all(len(m) <= TELEGRAM_LIMIT for m in messages)
    assert "…и ещё 15" in messages[-1]


def test_unrecognized_result_falls_back_to_raw_json() -> None:
    (message,) = format_result("job", {"weird": {"a": 1}})

    assert (
        "<pre>" in message and "&quot;" not in message
    )  # quote=False: кавычки не ломаем
    assert "weird" in message


def test_job_registry_returns_ref_and_evicts_oldest() -> None:
    registry = JobRegistry(max_size=2)
    refs = [JobRef(job_id=f"j{i}", chat_id=1, user_id=1, url="u") for i in range(3)]
    tokens = [registry.add(r) for r in refs]

    assert registry.get(tokens[0]) is None  # вытеснен
    assert registry.get(tokens[1]) is refs[1]
    assert registry.get(tokens[2]) is refs[2]
    assert registry.get("nope") is None
    assert all(len(f"st:{t}") <= 64 for t in tokens)  # лимит callback_data


def test_jobref_lock_is_per_job() -> None:
    async def scenario() -> None:
        a = JobRef(job_id="a", chat_id=1, user_id=1, url="u")
        b = JobRef(job_id="b", chat_id=1, user_id=1, url="u")
        async with a.lock:
            assert not b.lock.locked()

    asyncio.run(scenario())
