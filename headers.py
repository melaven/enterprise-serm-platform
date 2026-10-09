"""Ротация User-Agent и браузерные заголовки для HTTP-адаптеров."""

import random

# Актуальные десктопные браузеры. Пул нужно периодически обновлять.
USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 "
    "Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
)

ACCEPT_LANGUAGES: tuple[str, ...] = (
    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "ru,en-US;q=0.9,en;q=0.8",
    "en-US,en;q=0.9,ru;q=0.8",
)


def build_headers(
    *, referer: str | None = None, rng: random.Random | None = None
) -> dict[str, str]:
    """Свежий набор заголовков на каждый запрос (UA и язык выбираются случайно).

    Accept-Encoding без br: httpx распаковывает brotli только при установленном
    пакете brotli, иначе получим мусор вместо тела.
    """
    pick = rng or random
    headers = {
        "User-Agent": pick.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/json;q=0.8,*/*;q=0.7",
        "Accept-Language": pick.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    return headers
