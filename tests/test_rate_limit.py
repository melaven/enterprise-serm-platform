from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import rate_limit
from app.core.auth import AuthConfig


class FakePipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self.redis = redis
        self.commands: list[tuple[str, str, int | None]] = []

    def incr(self, key: str) -> "FakePipeline":
        self.commands.append(("incr", key, None))
        return self

    def expire(self, key: str, seconds: int) -> "FakePipeline":
        self.commands.append(("expire", key, seconds))
        return self

    async def execute(self) -> list[int | bool]:
        results: list[int | bool] = []
        for operation, key, seconds in self.commands:
            if operation == "incr":
                self.redis.values[key] = self.redis.values.get(key, 0) + 1
                results.append(self.redis.values[key])
            else:
                self.redis.expirations[key] = seconds
                results.append(True)
        return results


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, int] = {}
        self.pipeline_calls = 0

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        assert transaction is True
        self.pipeline_calls += 1
        return FakePipeline(self)


def make_request(redis_pool: FakeRedis, token: str | None = None) -> Request:
    headers = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "query_string": b"",
        "headers": headers,
        "client": ("203.0.113.12", 54321),
        "server": ("testserver", 80),
        "scheme": "http",
        "state": {},
        "app": SimpleNamespace(state=SimpleNamespace(redis_pool=redis_pool)),
    }
    return Request(scope)


def make_token(tenant_id: str, secret: str) -> str:
    return jwt.encode(
        {
            "sub": str(uuid4()),
            "tenant_id": tenant_id,
            "aud": "authenticated",
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "time", SimpleNamespace(time=lambda: 120.25))


@pytest.mark.asyncio
async def test_authenticated_limit_is_100_per_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "test-secret-for-rate-limit-tests-32-bytes"
    tenant_id = str(uuid4())
    redis = FakeRedis()
    monkeypatch.setattr(
        rate_limit,
        "get_auth_config",
        lambda: AuthConfig(secret=secret, jwks_url=None),
    )
    request = make_request(redis, make_token(tenant_id, secret))
    dependency = rate_limit.RateLimitDependency()

    for _ in range(100):
        await dependency(request)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(request)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}
    assert request.state.rate_limit_headers["X-RateLimit-Limit"] == "100"
    assert next(iter(redis.values)).startswith(f"rate_limit:{tenant_id}:dashboard:2")
    assert redis.expirations[next(iter(redis.values))] == 61
    assert redis.pipeline_calls == 101


@pytest.mark.asyncio
async def test_anonymous_limit_is_20_per_ip() -> None:
    redis = FakeRedis()
    request = make_request(redis)
    dependency = rate_limit.RateLimitDependency()

    for _ in range(20):
        await dependency(request)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(request)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}
    assert request.state.rate_limit_headers["X-RateLimit-Limit"] == "20"
    assert next(iter(redis.values)).startswith("rate_limit:203.0.113.12:anon:2")


@pytest.mark.asyncio
async def test_api_key_and_dashboard_use_separate_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    secret = "test-secret-for-rate-limit-tests-32-bytes"
    redis = FakeRedis()
    monkeypatch.setattr(
        rate_limit,
        "get_auth_config",
        lambda: AuthConfig(secret=secret, jwks_url=None),
    )

    async def resolve_api_tenant(_: Request) -> object:
        return tenant_id

    monkeypatch.setattr(rate_limit, "resolve_api_key_tenant_id", resolve_api_tenant)
    dependency = rate_limit.RateLimitDependency()
    dashboard_request = make_request(redis, make_token(str(tenant_id), secret))
    api_request = make_request(redis)
    api_request.scope["headers"].append((b"x-api-key", b"test-api-key"))

    await dependency(dashboard_request)
    await dependency(api_request)

    assert set(redis.values) == {
        f"rate_limit:{tenant_id}:dashboard:2",
        f"rate_limit:{tenant_id}:api:2",
    }
