"""Distributed circuit breaker state management backed by Redis."""

from typing import Protocol

from redis.asyncio import Redis

from app.infrastructure.redis.async_eval import await_redis_eval

_IS_ALLOWED_SCRIPT = """
local state = redis.call('GET', KEYS[1])
if not state or state == 'CLOSED' then
    return 1
end

if state == 'OPEN' then
    if redis.call('EXISTS', KEYS[2]) == 1 then
        return 0
    end
    redis.call('SET', KEYS[1], 'HALF_OPEN')
    redis.call('SET', KEYS[3], '1', 'EX', ARGV[1])
    return 1
end

if state == 'HALF_OPEN' then
    if redis.call('SET', KEYS[3], '1', 'EX', ARGV[1], 'NX') then
        return 1
    end
    return 0
end

return redis.error_reply('Unknown circuit breaker state: ' .. state)
"""

_RECORD_FAILURE_SCRIPT = """
local failures = redis.call('INCR', KEYS[2])
redis.call('EXPIRE', KEYS[2], ARGV[3])
local state = redis.call('GET', KEYS[1])

if failures >= tonumber(ARGV[1]) or state == 'HALF_OPEN' then
    redis.call('SET', KEYS[1], 'OPEN')
    redis.call('SET', KEYS[3], '1', 'EX', ARGV[2])
    redis.call('DEL', KEYS[4])
end

return failures
"""

_RECORD_SUCCESS_SCRIPT = """
redis.call('DEL', KEYS[1], KEYS[2], KEYS[3], KEYS[4])
return 1
"""


class _RedisEvalClient(Protocol):
    async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> object:
        """Evaluate a Redis Lua script."""


class RedisCircuitBreaker:
    """Share CLOSED, OPEN, and single-probe HALF_OPEN states across workers."""

    def __init__(
        self,
        redis_client: Redis | _RedisEvalClient,
        failure_threshold: int = 10,
        recovery_timeout: int = 60,
    ) -> None:
        if (
            isinstance(failure_threshold, bool)
            or not isinstance(failure_threshold, int)
            or failure_threshold <= 0
        ):
            raise ValueError("failure_threshold must be a positive integer")
        if (
            isinstance(recovery_timeout, bool)
            or not isinstance(recovery_timeout, int)
            or recovery_timeout <= 0
        ):
            raise ValueError("recovery_timeout must be a positive whole number")

        self._redis = redis_client
        self.failure_threshold = failure_threshold
        self.recovery_timeout = int(recovery_timeout)

    @staticmethod
    def _keys(platform_name: str) -> tuple[str, str, str, str]:
        platform = platform_name.strip().lower()
        if not platform:
            raise ValueError("platform_name must not be empty")
        prefix = f"circuit_breaker:{{{platform}}}"
        return (
            f"{prefix}:state",
            f"{prefix}:failures",
            f"{prefix}:recovery",
            f"{prefix}:half_open_probe",
        )

    @staticmethod
    def _result_as_int(result: object) -> int:
        if isinstance(result, bool) or not isinstance(result, str | bytes | int):
            raise RuntimeError("Redis returned an invalid circuit-breaker result")
        try:
            return int(result)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Redis returned a non-numeric circuit-breaker result"
            ) from exc

    async def is_allowed(self, platform_name: str) -> bool:
        """Allow normal calls or atomically claim the single half-open probe."""
        state_key, _, recovery_key, probe_key = self._keys(platform_name)
        result = self._result_as_int(
            await await_redis_eval(
                self._redis.eval(
                    _IS_ALLOWED_SCRIPT,
                    3,
                    state_key,
                    recovery_key,
                    probe_key,
                    str(self.recovery_timeout),
                )
            )
        )
        if result not in (0, 1):
            raise RuntimeError("Redis returned an invalid circuit-breaker state")
        return result == 1

    async def record_failure(self, platform_name: str) -> int:
        """Increment consecutive failures and open the circuit at the threshold."""
        state_key, failure_key, recovery_key, probe_key = self._keys(platform_name)
        failure_count = self._result_as_int(
            await await_redis_eval(
                self._redis.eval(
                    _RECORD_FAILURE_SCRIPT,
                    4,
                    state_key,
                    failure_key,
                    recovery_key,
                    probe_key,
                    str(self.failure_threshold),
                    str(self.recovery_timeout),
                    str(self.recovery_timeout),
                )
            )
        )
        if failure_count <= 0:
            raise RuntimeError("Redis returned an invalid failure count")
        return failure_count

    async def record_success(self, platform_name: str) -> None:
        """Reset the failure count and close the circuit after a successful call."""
        state_key, failure_key, recovery_key, probe_key = self._keys(platform_name)
        result = self._result_as_int(
            await await_redis_eval(
                self._redis.eval(
                    _RECORD_SUCCESS_SCRIPT,
                    4,
                    state_key,
                    failure_key,
                    recovery_key,
                    probe_key,
                )
            )
        )
        if result != 1:
            raise RuntimeError("Redis failed to reset circuit-breaker state")

    async def release_probe(self, platform_name: str) -> None:
        """Release a half-open probe when another gate prevents its HTTP call."""
        state_key, _, _, probe_key = self._keys(platform_name)
        result = self._result_as_int(
            await await_redis_eval(
                self._redis.eval(
                    """
                if redis.call('GET', KEYS[1]) == 'HALF_OPEN' then
                    return redis.call('DEL', KEYS[2])
                end
                return 1
                """,
                    2,
                    state_key,
                    probe_key,
                )
            )
        )
        if result not in (0, 1):
            raise RuntimeError("Redis failed to release circuit-breaker probe")
