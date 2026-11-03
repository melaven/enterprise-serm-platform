from uuid import UUID

import pytest

from app.infrastructure.redis.rate_limiter import (
    _TOKEN_BUCKET_SCRIPT,
    RedisRateLimiter,
)


class _FakeRedis:
    def __init__(self, result: object) -> None:
        self.result = result
        self.eval_args: tuple[object, ...] | None = None

    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        self.eval_args = (script, numkeys, *keys_and_args)
        return self.result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "expected"),
    [([1, 0], (True, 0.0)), ([0, 1250], (False, 1.25))],
)
async def test_acquire_uses_tenant_platform_key_and_redis_script(
    result: object,
    expected: tuple[bool, float],
) -> None:
    redis = _FakeRedis(result)
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")

    acquired = await RedisRateLimiter(redis).acquire(tenant_id, "Yandex")

    assert acquired == expected
    assert redis.eval_args is not None
    assert redis.eval_args[0] == _TOKEN_BUCKET_SCRIPT
    assert redis.eval_args[1:] == (
        1,
        f"rate_limit:{tenant_id}:yandex",
        5,
        1000,
    )
    assert "redis.call('TIME')" in _TOKEN_BUCKET_SCRIPT
    assert "redis.call('HMGET'" in _TOKEN_BUCKET_SCRIPT
    assert "redis.call('HSET'" in _TOKEN_BUCKET_SCRIPT


@pytest.mark.asyncio
async def test_acquire_rejects_malformed_redis_response() -> None:
    limiter = RedisRateLimiter(_FakeRedis([0, 0]))

    with pytest.raises(RuntimeError, match="inconsistent token-bucket result"):
        await limiter.acquire("tenant", "google")


def test_limiter_rejects_invalid_configuration() -> None:
    redis = _FakeRedis([1, 0])

    with pytest.raises(ValueError, match="requests"):
        RedisRateLimiter(redis, requests=0)

    with pytest.raises(ValueError, match="window"):
        RedisRateLimiter(redis, window=0)
