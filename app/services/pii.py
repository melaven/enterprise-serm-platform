"""Service for deterministic removal of personal data from review text.

Это НЕ «нейросеть на всякий случай», а первая и последняя линия обороны: работает без сети и LLM, одинаково на
каждом вызове, покрыта тестами. LLM-слой в si_pipeline добавляет то, что регулярками не поймать (ФИО без контекста).

Принцип: лучше лишнее срезать, чем пропустить. Любая цифровая последовательность из 9+ цифр считается идентификатором.
Известные ограничения (смотри тесты): числа прописью («восемь девять...»), цифры, разбитые словами, имена без
контекста и без участия LLM.
"""

from __future__ import annotations

import re
import unicodedata

PLACEHOLDER = "[ДАННЫЕ СКРЫТЫ]"
_P = PLACEHOLDER

_RE_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", re.IGNORECASE)
_RE_SOCIAL = re.compile(
    r"(?:https?://)?(?:www\.)?(?:vk\.com|vk\.ru|t\.me|telegram\.me|instagram\.com|wa\.me|ok\.ru|facebook\.com)/\S+",
    re.IGNORECASE,
)
_RE_HANDLE = re.compile(r"(?<![\w@])@[A-Za-z][A-Za-z0-9_]{4,31}\b")
# Номер договора/заказа/счёта/карты ПОСЛЕ слова-маркера: заменяем только номер (в нём обязана быть цифра).
_RE_DOC_NUMBER = re.compile(
    r"((?i:договор|контракт|заказ|счет|счёт|накладн|полис|карт|абонент|лицевой\s+счет|лицевой\s+счёт)[а-яё]*"
    r"\s*(?i:№|n[o°]?\.?|#|номер(?:ом|а)?)\s*)([A-Za-zА-Яа-яЁё0-9\-/]*\d[A-Za-zА-Яа-яЁё0-9\-/]*)"
)
_RE_BIRTH = re.compile(
    r"(?i:дат[аы]\s+рождения|д\.\s?р\.|родил(?:ся|ась)|год\s+рождения)[\s:]*\d{1,2}[./]\d{1,2}[./]\d{2,4}|"
    r"(?i:дат[аы]\s+рождения|д\.\s?р\.|родил(?:ся|ась))[\s:]*\d{4}"
)
_RE_PLATE = re.compile(
    r"(?<![\w])[АВЕКМНОРСТУХABEKMHOPCTYX]\d{3}[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\d{2,3}(?![\w])"
)
_RE_PHONE_RU = re.compile(
    r"(?<![\d\w])(?:\+?7|8)[\s\-.]*\(?\d{3}\)?[\s\-.]*\d{3}[\s\-.]*\d{2}[\s\-.]*\d{2}(?!\d)"
)
_RE_PHONE_INTL = re.compile(
    r"(?<![\d\w])\+\d{1,3}[\s\-.]*\(?\d{2,4}\)?(?:[\s\-.]*\d{2,4}){2,4}(?!\d)"
)
_RE_CARD = re.compile(r"(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)")
# Любой «идентификатор»: 9+ цифр подряд (допускаются одиночные пробелы/дефисы между цифрами).
_RE_LONG_DIGITS = re.compile(r"(?<!\d)\d(?:[\s\-]?\d){8,}(?!\d)")
_RE_APARTMENT = re.compile(
    r"(?i:\bкв(?:артира|артиры|артире|\.)?)\s*(?i:№|no\.?)?\s*\d+[а-яa-z]?"
)
# «серия 45 10 номер 123456»: слова между блоками цифр ломают общее правило «9+ цифр».
_RE_PASSPORT = re.compile(
    r"(?i:сери[яи])\s*\d{2}\s?\d{2}[\s,;]*(?i:номер|№|no\.?)?\s*\d{6}(?!\d)"
)
# Имена: только после слова-маркера (роль или «меня зовут»), следом 1-3 слова с заглавной.
_RE_NAME = re.compile(
    r"(?i:\b(?:меня\s+зовут|моё\s+имя|мое\s+имя|зовут|фио|ф\.и\.о\.|официант(?:ка|ки|у|ом)?|"
    r"администратор(?:а|у|ом)?|менеджер(?:а|у|ом)?|врач(?:а|у|ом)?|доктор(?:а|у|ом)?|директор(?:а|у|ом)?|"
    r"продавец|продавц[а-я]+|консультант(?:а|у|ом)?|кассир(?:а|у|ом)?|повар(?:а|у|ом)?|бармен(?:а|у|ом)?|"
    r"курьер(?:а|у|ом)?|водител[ьяюем]+|мастер(?:а|у|ом)?|хостес[а-я]*|сотрудни[а-я]+|парикмахер[а-я]*)\b)"
    r"([\s:,\-—]+)([А-ЯЁ][а-яё]+(?:[\s\-]+[А-ЯЁ][а-яё]+){0,2})(?=[\s,.;:!?)\"»]|$)"
)


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _card_sub(m: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", m.group(0))
    return _P if 13 <= len(digits) <= 19 and _luhn_ok(digits) else m.group(0)


def redact(text: str) -> tuple[str, int]:
    """-> (текст без ПДн, число сделанных замен). Идемпотентна: повторный вызов ничего не меняет."""
    if not text:
        return "", 0
    out = unicodedata.normalize(
        "NFKC", text
    )  # fullwidth/«красивые» цифры и тире -> обычные
    n = 0

    def sub(pattern: re.Pattern[str], repl: str | object) -> None:
        nonlocal out, n
        out, k = pattern.subn(repl, out)  # type: ignore[arg-type]
        n += k

    sub(_RE_EMAIL, _P)
    sub(_RE_SOCIAL, _P)
    sub(_RE_HANDLE, _P)
    sub(_RE_DOC_NUMBER, lambda m: m.group(1) + _P)
    sub(_RE_PASSPORT, _P)
    sub(_RE_BIRTH, _P)
    sub(_RE_PLATE, _P)
    sub(_RE_PHONE_RU, _P)
    sub(_RE_PHONE_INTL, _P)
    sub(_RE_CARD, _card_sub)
    sub(_RE_LONG_DIGITS, _P)
    sub(_RE_APARTMENT, _P)
    sub(_RE_NAME, lambda m: m.group(0)[: m.start(2) - m.start(0)] + _P)
    # _card_sub не меняет не-карты, но subn считает их как замены: пересчитываем честно.
    n = out.count(_P) - text.count(_P)
    return out, max(n, 0)


def redact_text(text: str) -> str:
    return redact(text)[0]


def contains_pii(text: str) -> bool:
    """True, если в тексте ещё остаётся то, что redact() вырезал бы."""
    redacted, _ = redact(text)
    return redacted != unicodedata.normalize("NFKC", text)
