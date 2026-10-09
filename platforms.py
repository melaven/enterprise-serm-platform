"""Список поддерживаемых площадок и их доменов (единый источник правды).

Домены используются и в роутере (валидация входящего URL), и в адаптерах
(защита от SSRF в воркере, если задачу поставил не наш роутер).
"""

from typing import Literal, get_args
from urllib.parse import urlsplit

Platform = Literal["google", "yandex", "2gis", "otzovik"]
PLATFORMS: tuple[str, ...] = get_args(Platform)

PLATFORM_DOMAINS: dict[str, tuple[str, ...]] = {
    "google": ("google.com", "google.ru", "goo.gl", "g.page"),
    "yandex": ("yandex.ru", "yandex.com"),
    "2gis": ("2gis.ru", "2gis.com"),
    "otzovik": ("otzovik.com",),
}


def host_allowed(url: str, platform: str) -> bool:
    """http(s) + хост равен домену площадки или является его поддоменом."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not host:
        return False
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in PLATFORM_DOMAINS.get(platform, ())
    )
