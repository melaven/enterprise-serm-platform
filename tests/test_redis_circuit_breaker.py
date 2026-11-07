import pytest

from app.infrastructure.redis.circuit_breaker import (
    _IS_ALLOWED_SCRIPT,
    _RECORD_FAILURE_SCRIPT,
    _RECORD_SUCCESS_SCRIPT,
    RedisCircuitBreaker,
)


class _CircuitStateRedis:
    def __init__(self) -> None:
        self.state = "CLOSED"
        self.failures = 0
        self.recovery_active = False
        self.probe_active = False
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        self.calls.append((script, (numkeys, *keys_and_args)))
        if script == _IS_ALLOWED_SCRIPT:
            if self.state == "CLOSED":
                return 1
            if self.state == "OPEN":
                if self.recovery_active:
                    return 0
                self.state = "HALF_OPEN"
                self.recovery_active = False
                self.probe_active = True
                return 1
            if self.state == "HALF_OPEN":
                if self.probe_active:
                    return 0
                self.probe_active = True
                return 1
        elif script == _RECORD_FAILURE_SCRIPT:
            threshold = int(keys_and_args[-3])
            self.failures += 1
            if self.failures >= threshold or self.state == "HALF_OPEN":
                self.state = "OPEN"
                self.recovery_active = True
                self.probe_active = False
            return self.failures
        elif script == _RECORD_SUCCESS_SCRIPT:
            self.state = "CLOSED"
            self.failures = 0
            self.recovery_active = False
            self.probe_active = False
            return 1
        raise AssertionError(f"Unexpected Redis script: {script}")


@pytest.mark.asyncio
async def test_breaker_opens_and_allows_only_one_half_open_probe() -> None:
    redis = _CircuitStateRedis()
    breaker = RedisCircuitBreaker(redis, failure_threshold=2, recovery_timeout=60)

    assert await breaker.is_allowed("Yandex")
    assert await breaker.record_failure("yandex") == 1
    assert await breaker.is_allowed("yandex")
    assert await breaker.record_failure("yandex") == 2
    assert redis.state == "OPEN"
    assert not await breaker.is_allowed("yandex")

    redis.recovery_active = False
    assert await breaker.is_allowed("yandex")
    assert redis.state == "HALF_OPEN"
    assert not await breaker.is_allowed("yandex")

    await breaker.record_success("yandex")
    assert redis.state == "CLOSED"
    assert redis.failures == 0
    assert await breaker.is_allowed("yandex")


@pytest.mark.asyncio
async def test_failed_half_open_probe_reopens_circuit() -> None:
    redis = _CircuitStateRedis()
    breaker = RedisCircuitBreaker(redis, failure_threshold=1, recovery_timeout=30)

    await breaker.record_failure("google")
    redis.recovery_active = False
    assert await breaker.is_allowed("google")
    assert redis.state == "HALF_OPEN"

    await breaker.record_failure("google")
    assert redis.state == "OPEN"
    assert not await breaker.is_allowed("google")


@pytest.mark.asyncio
async def test_breaker_uses_atomic_redis_keys_and_expiring_counter() -> None:
    redis = _CircuitStateRedis()
    breaker = RedisCircuitBreaker(redis, failure_threshold=3, recovery_timeout=45)

    await breaker.is_allowed("OpenAI")
    await breaker.record_failure("OpenAI")

    is_allowed_script, allowed_args = redis.calls[0]
    assert is_allowed_script == _IS_ALLOWED_SCRIPT
    assert allowed_args == (
        3,
        "circuit_breaker:{openai}:state",
        "circuit_breaker:{openai}:recovery",
        "circuit_breaker:{openai}:half_open_probe",
        "45",
    )
    failure_script, failure_args = redis.calls[1]
    assert failure_script == _RECORD_FAILURE_SCRIPT
    assert "redis.call('INCR'" in failure_script
    assert "redis.call('EXPIRE'" in failure_script
    assert failure_args[-3:] == ("3", "45", "45")


@pytest.mark.parametrize(
    ("failure_threshold", "recovery_timeout"),
    [(0, 60), (1, 0), (1, 1.5)],
)
def test_breaker_rejects_invalid_configuration(
    failure_threshold: int,
    recovery_timeout: int,
) -> None:
    with pytest.raises(ValueError):
        RedisCircuitBreaker(
            _CircuitStateRedis(),
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
