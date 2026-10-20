"""Кэш валидации API-ключей: fake Redis, без БД и FastAPI."""

import asyncio
import sys
import types
from uuid import uuid4

if "structlog" not in sys.modules:
    try:
        import structlog  # noqa: F401
    except ImportError:
        m = types.ModuleType("structlog")
        m.get_logger = lambda *_a, **_k: types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
        )
        sys.modules["structlog"] = m

from app.services.api_keys import (  # noqa: E402
    CACHE_TTL_S,
    NEGATIVE_TTL_S,
    generate_api_key,
    hash_api_key,
    invalidate,
    is_well_formed,
    resolve_tenant,
)


class FakeRedis:
    def __init__(self, broken=False):
        self.d, self.ttl, self.broken = {}, {}, broken

    async def get(self, k):
        if self.broken:
            raise ConnectionError
        return self.d.get(k)

    async def set(self, k, v, ex=None, nx=False):
        if self.broken:
            raise ConnectionError
        if nx and k in self.d:
            return None
        self.d[k] = v if isinstance(v, bytes) else str(v).encode()
        self.ttl[k] = ex
        return True


def run(c):
    return asyncio.run(c)


def test_generate_format_and_hash():
    plain, prefix, h = generate_api_key()
    assert (
        is_well_formed(plain)
        and plain.startswith(prefix)
        and h == hash_api_key(plain)
        and len(h) == 64
    )
    assert (
        not is_well_formed("x")
        and not is_well_formed(plain + "!")
        and not is_well_formed("")
    )


def test_cache_hit_skips_db_and_miss_caches_60s():
    r, t, calls = FakeRedis(), uuid4(), []

    async def db(h):
        calls.append(h)
        return t

    assert run(resolve_tenant(r, "h1", db)) == t and len(calls) == 1
    assert r.ttl["apikey:v1:h1"] == CACHE_TTL_S
    assert run(resolve_tenant(r, "h1", db)) == t and len(calls) == 1  # из кэша


def test_unknown_key_negative_cached_short():
    r, calls = FakeRedis(), []

    async def db(h):
        calls.append(h)

    assert (
        run(resolve_tenant(r, "bad", db)) is None
        and run(resolve_tenant(r, "bad", db)) is None
    )
    assert len(calls) == 1 and r.ttl["apikey:v1:bad"] == NEGATIVE_TTL_S


def test_revoke_tombstone_beats_concurrent_cache_write():
    r, t = FakeRedis(), uuid4()

    async def db(h):
        await invalidate(r, h)  # отзыв случился между чтением БД и записью в кэш
        return t

    run(resolve_tenant(r, "h2", db))  # NX не затирает надгробие

    async def never(h):
        raise AssertionError("db must not be called")

    assert run(resolve_tenant(r, "h2", never)) is None


def test_redis_down_falls_back_to_db():
    t = uuid4()

    async def db(h):
        return t

    assert run(resolve_tenant(FakeRedis(broken=True), "h3", db)) == t
    run(invalidate(FakeRedis(broken=True), "h3"))  # не бросает
