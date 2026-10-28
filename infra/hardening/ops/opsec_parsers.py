"""OpSec-гигиена для Telegram-паука и парсеров. Цель — не выглядеть как бот и не ловить бан, не обходя защиту силой.

Ключевое про Telegram: аккаунт «привязывается» к устройству/IP-региону. РОТАЦИЯ прокси на одном аккаунте
повышает риск бана (скачки гео). Правильно: 1 аккаунт = 1 sticky-прокси (резидентный, страна аккаунта) = 1 набор
параметров устройства, неизменный навсегда. Ротация — между аккаунтами/парсерами, не внутри аккаунта.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AccountProfile:
    session_env: str
    proxy: tuple[str, str, int, str, str]  # (socks5, host, port, user, pass) — sticky
    device_model: str = "Desktop"
    system_version: str = "Windows 10"
    app_version: str = "5.5.2 x64"  # реалистичные значения, ФИКСИРОВАТЬ и не менять
    lang_code: str = "ru"
    system_lang_code: str = "ru-RU"


# TelegramClient(session, api_id, api_hash, proxy=profile.proxy, device_model=..., system_version=...,
#                app_version=..., lang_code=..., system_lang_code=...)


def jitter(base: float, spread: float = 0.4) -> float:
    """base ± spread, с редким длинным хвостом (человек иногда отвлекается)."""
    d = base * random.uniform(1 - spread, 1 + spread)
    if random.random() < 0.05:
        d *= random.uniform(3, 8)
    return d


@dataclass
class DomainThrottle:
    """Per-domain rate limit для веб-парсеров + экспоненциальный backoff на 429/403/captcha."""

    min_interval: float = 4.0
    _next: dict[str, float] = field(default_factory=dict)
    _strikes: dict[str, int] = field(default_factory=dict)

    async def wait(self, domain: str) -> None:
        now = time.monotonic()
        at = self._next.get(domain, 0.0)
        if at > now:
            await asyncio.sleep(at - now)
        self._next[domain] = time.monotonic() + jitter(
            self.min_interval * (2 ** self._strikes.get(domain, 0))
        )

    def strike(self, domain: str) -> bool:
        """Вернуть True, если домен надо поставить на паузу (3 подряд блокировки -> стоп на сутки + алерт)."""
        self._strikes[domain] = min(self._strikes.get(domain, 0) + 1, 6)
        return self._strikes[domain] >= 3

    def ok(self, domain: str) -> None:
        self._strikes[domain] = 0


# Лимиты паука (дополняют уже реализованный FloodWait-хендлинг)
SPIDER_LIMITS = {
    "joins_per_day": 3,  # только вручную
    "warmup_days_read_only": 7,
    "max_dialogs_monitored": 40,
    "dm_per_day_manual": 15,
    "flood_wait_stop_after": 2,  # 2 FloodWait за сутки -> автостоп паука на 24 ч + алерт
}
