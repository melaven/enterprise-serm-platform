"""Генерация, хеширование и кэшированная валидация API-ключей (без FastAPI: тестируется изолированно).

Кэш Redis: ключ `apikey:v1:<sha256>` -> tenant_id (60 с) либо "-" (ключ невалиден).
  * промах кэша -> resolve в БД -> SET NX EX 60 (NX: не затираем надгробие, поставленное отзывом);
  * неизвестный ключ кэшируется на 10 с: перебор случайных ключей не превращается в нагрузку на БД;
  * отзыв ставит надгробие "-" на 60 с СРАЗУ (до/независимо от коммита), так что отозванный ключ перестаёт
    работать мгновенно, а не через TTL; параллельный verify не может вернуть ключ в кэш (NX);
  * Redis недоступен -> деградация к БД (fail-open по доступности, не по безопасности: источник истины БД).
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from uuid import UUID

import structlog

log = structlog.get_logger(__name__)

KEY_PREFIX = "tnb_"
CACHE_TTL_S = 60
NEGATIVE_TTL_S = 10
MAX_ACTIVE_KEYS = 20
_INVALID = b"-"
_FORMAT = re.compile(r"^tnb_[A-Za-z0-9_-]{43}$")  # token_urlsafe(32) = 43 символа


class RedisLike(Protocol):
    async def get(self, name: str) -> Any: ...
    async def set(
        self, name: str, value: Any, ex: int | None = None, nx: bool = False
    ) -> Any: ...


def generate_api_key() -> tuple[str, str, str]:
    """-> (plain_key, display_prefix, sha256_hex). plain_key показывается клиенту один раз."""
    plain = KEY_PREFIX + secrets.token_urlsafe(32)
    return plain, plain[:8], hash_api_key(plain)


def hash_api_key(plain: str) -> str:
    # 256 бит энтропии: быстрый хеш достаточен (брутфорс невозможен), медленный KDF только добавил бы нагрузку.
    return hashlib.sha256(plain.encode()).hexdigest()


def is_well_formed(plain: str) -> bool:
    """Отсев мусора до Redis и БД."""
    return bool(_FORMAT.fullmatch(plain))


def cache_key(key_hash: str) -> str:
    return f"apikey:v1:{key_hash}"


async def resolve_tenant(
    redis: RedisLike,
    key_hash: str,
    db_resolve: Callable[[str], Awaitable[UUID | None]],
) -> UUID | None:
    ck = cache_key(key_hash)
    try:
        cached = await redis.get(ck)
    except Exception:  # noqa: BLE001 - Redis лёг: идём в БД
        log.warning("api_key_cache_read_failed", exc_info=True)
        cached = None
    if cached is not None:
        raw = cached if isinstance(cached, bytes) else str(cached).encode()
        if raw == _INVALID:
            return None
        try:
            return UUID(raw.decode())
        except ValueError:
            log.warning("api_key_cache_corrupt")  # битое значение: перепроверим в БД

    tenant = await db_resolve(key_hash)
    try:
        if tenant is None:
            await redis.set(ck, _INVALID, ex=NEGATIVE_TTL_S, nx=True)
        else:
            await redis.set(ck, str(tenant), ex=CACHE_TTL_S, nx=True)
    except Exception:  # noqa: BLE001
        log.warning("api_key_cache_write_failed", exc_info=True)
    return tenant


async def invalidate(redis: RedisLike, key_hash: str) -> None:
    """Надгробие после отзыва. Ошибка Redis не отменяет отзыв (он уже в БД): худший случай — устаревание до 60 с."""
    try:
        await redis.set(cache_key(key_hash), _INVALID, ex=CACHE_TTL_S)
    except Exception:  # noqa: BLE001
        log.error("api_key_invalidate_failed", exc_info=True)
