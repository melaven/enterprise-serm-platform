import pytest

from app.core.pii import PLACEHOLDER as P
from app.core.pii import PIISanitizer, contains_pii, redact, redact_text


def test_hash_user_id_is_stable_platform_scoped_and_pseudonymous() -> None:
    user_hash = PIISanitizer.hash_user_id("google", "raw-user-123")

    assert user_hash.startswith("usr_")
    assert len(user_hash) == 28
    assert user_hash == PIISanitizer.hash_user_id("google", "raw-user-123")
    assert user_hash != PIISanitizer.hash_user_id("yandex", "raw-user-123")
    assert "raw-user-123" not in user_hash


def test_mask_author_name_returns_only_generic_labels() -> None:
    assert PIISanitizer.mask_author_name("Иван Петров") == "Клиент"
    assert PIISanitizer.mask_author_name(None) == "Анонимный клиент"
    assert PIISanitizer.mask_author_name("  ") == "Анонимный клиент"


def test_task_example():
    assert (
        redact_text("Мой телефон 89001234567, официант хамил")
        == f"Мой телефон {P}, официант хамил"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "звоните +7 (900) 123-45-67 срочно",
        "8 900 123 45 67",
        "+79001234567",
        "8-900-123-45-67",
        "9001234567",
        "+7(900)1234567",
        "телефон: 8.900.123.45.67",
        "+44 20 7946 0958",
        "+375 29 123 45 67",
        "8 9 0 0 1 2 3 4 5 6 7",
        "８９００１２３４５６７",  # fullwidth-цифры
    ],
)
def test_phones_removed(raw):
    assert not any(c.isdigit() for c in redact_text(raw)), redact_text(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "пишите ivan.petrov+spam@mail.ru пожалуйста",
        "mail: A_B@sub.domain.co.uk",
        "tg @ivan_petrov77 и vk.com/id12345",
        "https://t.me/someuser",
        "паспорт 4510 123456",
        "паспорт серия 45 10 номер 123456",
        "СНИЛС 123-456-789 01",
        "договор № А-123/45",
        "заказ №12345",
        "счёт N 77-1",
        "карта 4276 3800 1234 5678",
        "дата рождения 01.02.1990",
        "я родился 1990",
        "машина А123ВС77",
        "кв. 12",
        "квартира №45",
    ],
)
def test_identifiers_removed(raw):
    out = redact_text(raw)
    assert P in out and not contains_pii(out)
    assert not any(c.isdigit() for c in out)


@pytest.mark.parametrize(
    "raw,kept",
    [
        ("Меня зовут Иван Петров, я был в зале", "я был в зале"),
        ("официант Анна хамила", "хамила"),
        ("Администратор Мария Ивановна не помогла", "не помогла"),
        ("обслуживал менеджер: Сергей Ким.", "обслуживал"),
    ],
)
def test_names_in_context(raw, kept):
    out = redact_text(raw)
    assert P in out and kept in out
    for name in ("Иван", "Петров", "Анна", "Мария", "Сергей", "Ким"):
        assert name not in out


@pytest.mark.parametrize(
    "clean",
    [
        "Официант был вежлив, заказ принесли быстро",
        "Ждали 40 минут, счёт 1500 рублей",
        "оценка 5 из 5, всё отлично",
        "Были 12.03.2024, цена 1 500 000 не оправдана",
        "менеджер вежливый и быстрый",
        "Заказ холодный",
        "договор оказания услуг расторгнут",
    ],
)
def test_no_false_positives(clean):
    assert redact_text(clean) == clean


def test_card_luhn_only():
    assert redact_text("номер 4111 1111 1111 1111") == f"номер {P}"  # валидный Luhn
    # 16 цифр без Luhn всё равно режутся общим правилом «9+ цифр»
    assert P in redact_text("1234 5678 9012 3456")


def test_idempotent_and_counts():
    once, n = redact("тел 89001234567 и a@b.ru")
    twice, n2 = redact(once)
    assert once == twice and n == 2 and n2 == 0
    assert redact("") == ("", 0)


def test_known_limitations_documented():
    # Числа прописью регулярками не ловятся: на них рассчитан LLM-слой.
    assert redact_text("восемь девять ноль ноль") == "восемь девять ноль ноль"
