"""Distributed token-bucket rate limiting for external platform requests."""

import math
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

_TOKEN_BUCKET_SCRIPT = """
local capacity = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local rate_per_ms = capacity / window_ms
local now = redis.call('TIME')
local now_ms = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'updated_at')
local tokens = tonumber(bucket[1])
local updated_at = tonumber(bucket[2])

if not tokens or not updated_at then
    tokens = capacity
    updated_at = now_ms
else
    now_ms = math.max(now_ms, updated_at)
    tokens = math.min(capacity, tokens + math.max(0, now_ms - updated_at) * rate_per_ms)
end

local allowed = 0
local retry_after_ms = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    retry_after_ms = math.ceil((1 - tokens) / rate_per_ms)
end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated_at', now_ms)
redis.call('PEXPIRE', KEYS[1], math.ceil(window_ms * 2))
return {allowed, retry_after_ms}
"""


class _RedisEvalClient(Protocol):
    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        """Evaluate a Redis Lua script."""


class RedisRateLimiter:
    """Atomically limit requests per tenant and platform using a token bucket."""

    def __init__(
        self,
        redis_client: Redis | _RedisEvalClient,
        requests: int = 5,
        window: float = 1,
    ) -> None:
        if isinstance(requests, bool) or not isinstance(requests, int) or requests <= 0:
            raise ValueError("requests must be a positive integer")
        if isinstance(window, bool) or not math.isfinite(window) or window <= 0:
            raise ValueError("window must be a positive finite number")

        self._redis = redis_client
        self._requests = requests
        self._window_ms = window * 1000

    async def acquire(
        self, tenant_id: str | UUID, platform_name: str
    ) -> tuple[bool, float]:
        """Return whether a token is available and the denial delay in seconds."""
        tenant = str(tenant_id).strip()
        platform = platform_name.strip().lower()
        if not tenant or not platform:
            raise ValueError("tenant_id and platform_name must not be empty")

        result = await self._redis.eval(
            _TOKEN_BUCKET_SCRIPT,
            1,
            f"rate_limit:{tenant}:{platform}",
            self._requests,
            self._window_ms,
        )
        if (
            not isinstance(result, list | tuple)
            or len(result) != 2
            or isinstance(result[0], bool)
            or isinstance(result[1], bool)
        ):
            raise RuntimeError("Redis returned an invalid token-bucket result")

        try:
            allowed = int(result[0])
            retry_after_ms = int(result[1])
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Redis returned a non-numeric token-bucket result"
            ) from exc
        if allowed not in (0, 1) or retry_after_ms < 0:
            raise RuntimeError("Redis returned an invalid token-bucket result")
        if (allowed == 0 and retry_after_ms == 0) or (
            allowed == 1 and retry_after_ms != 0
        ):
            raise RuntimeError("Redis returned an inconsistent token-bucket result")
        return allowed == 1, retry_after_ms / 1000
