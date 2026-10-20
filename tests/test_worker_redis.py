from types import SimpleNamespace

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.main import redis_health_check
from app.services.worker.worker import get_redis_settings


def test_worker_redis_settings_preserve_password_and_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://:test-password@redis:6379/2")

    settings = get_redis_settings()

    assert settings.host == "redis"
    assert settings.port == 6379
    assert settings.database == 2
    assert settings.password == "test-password"


@pytest.mark.asyncio
async def test_redis_health_check_pings_api_pool() -> None:
    class RedisPool:
        async def ping(self) -> bool:
            return True

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(arq_pool=RedisPool()))
    )

    response = await redis_health_check(request)

    assert response.status_code == 200
    assert response.body == b'{"status":"healthy","check":"redis"}'


@pytest.mark.asyncio
async def test_redis_health_check_reports_missing_pool() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    response = await redis_health_check(request)

    assert response.status_code == 503
    assert response.body == b'{"status":"unhealthy","check":"redis"}'


@pytest.mark.asyncio
async def test_redis_health_check_reports_connection_error() -> None:
    class RedisPool:
        async def ping(self) -> bool:
            raise RedisConnectionError("Redis unavailable")

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(arq_pool=RedisPool()))
    )

    response = await redis_health_check(request)

    assert response.status_code == 503
    assert response.body == b'{"status":"unhealthy","check":"redis"}'
