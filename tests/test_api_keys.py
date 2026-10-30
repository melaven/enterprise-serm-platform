from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.routes.api_keys import router
from app.core import api_keys
from app.core.api_keys import hash_api_key, verify_api_key
from app.core.auth import get_current_tenant
from app.core.dependencies import get_tenant_db
from app.core.rate_limit import RateLimitDependency, add_rate_limit_headers
from app.infrastructure.persistence.models.api_key import APIKey
from app.infrastructure.persistence.models.economics import Company


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
                self.redis.counters[key] = self.redis.counters.get(key, 0) + 1
                results.append(self.redis.counters[key])
            else:
                self.redis.expirations[key] = seconds or 0
                results.append(True)
        return results


class FakeRedis:
    def __init__(self) -> None:
        self.cache: dict[str, str] = {}
        self.counters: dict[str, int] = {}
        self.expirations: dict[str, int] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}

    async def get(self, key: str) -> str | None:
        return self.cache.get(key)

    async def set(self, key: str, value: str, ex: int) -> bool:
        self.cache[key] = value
        self.expirations[key] = ex
        return True

    async def delete(self, key: str) -> int:
        return int(self.cache.pop(key, None) is not None)

    async def eval(self, script: str, numkeys: int, *args: object) -> int:
        if "redis.call('SET'" in script:
            marker_key, queue_key, timestamp, ttl, key_hash = args
            if marker_key in self.cache:
                return 0
            self.cache[str(marker_key)] = str(timestamp)
            self.expirations[str(marker_key)] = int(ttl)
            self.sorted_sets.setdefault(str(queue_key), {})[str(key_hash)] = float(
                timestamp
            )
            return 1

        if "redis.call('ZSCORE'" in script:
            queue_key = str(args[0])
            values = self.sorted_sets.setdefault(queue_key, {})
            for index in range(1, len(args), 2):
                key_hash = str(args[index])
                expected_score = float(args[index + 1])
                if values.get(key_hash) == expected_score:
                    del values[key_hash]
            return 1

        raise AssertionError(f"Unexpected Redis script: {script}")

    async def zrange(
        self,
        key: str,
        start: int,
        end: int,
        *,
        withscores: bool = False,
    ) -> list[tuple[str, float]]:
        entries = sorted(
            self.sorted_sets.get(key, {}).items(), key=lambda item: item[1]
        )
        selected = entries[start : end + 1]
        return selected if withscores else [member for member, _ in selected]

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        assert transaction
        return FakePipeline(self)


class FakeSessionContext:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest_asyncio.fixture
async def api_key_client() -> AsyncIterator[tuple[httpx.AsyncClient, FakeRedis, UUID]]:
    tenant_id = uuid4()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Company.__table__.create)
        await connection.run_sync(APIKey.__table__.create)
    async with session_factory.begin() as session:
        session.add(
            Company(
                id=tenant_id,
                name="API key test tenant",
                average_check=0,
                margin_percent=0,
                cac=0,
                base_ltv=0,
            )
        )

    async def current_tenant() -> UUID:
        return tenant_id

    async def tenant_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    test_app = FastAPI()
    test_app.include_router(router)
    redis = FakeRedis()
    test_app.state.redis_pool = redis
    test_app.dependency_overrides[get_current_tenant] = current_tenant
    test_app.dependency_overrides[get_tenant_db] = tenant_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        try:
            yield client, redis, tenant_id
        finally:
            test_app.dependency_overrides.clear()
            await engine.dispose()


@pytest.mark.asyncio
async def test_api_key_create_list_and_revoke(
    api_key_client: tuple[httpx.AsyncClient, FakeRedis, UUID],
) -> None:
    client, redis, _ = api_key_client

    created = await client.post("/api/v1/api-keys", json={"name": "nightly sync"})
    assert created.status_code == 201
    created_data = created.json()
    assert created_data["name"] == "nightly sync"
    assert created_data["key"].startswith("serm_live_")
    assert "key_hash" not in created_data

    key_id = created_data["id"]
    cache_key = f"api_key:tenant:{hash_api_key(created_data['key'])}"
    redis.cache[cache_key] = "cached-tenant-id"

    listed = await client.get("/api/v1/api-keys")
    assert listed.status_code == 200
    listed_keys = listed.json()
    assert len(listed_keys) == 1
    assert listed_keys[0]["id"] == key_id
    assert listed_keys[0]["name"] == "nightly sync"
    assert "key" not in listed_keys[0]
    assert "key_hash" not in listed_keys[0]

    revoked = await client.delete(f"/api/v1/api-keys/{key_id}")
    assert revoked.status_code == 204
    assert cache_key not in redis.cache

    listed_after_revoke = await client.get("/api/v1/api-keys")
    assert listed_after_revoke.status_code == 200
    assert listed_after_revoke.json()[0]["revoked_at"] is not None

    repeated_revoke = await client.delete(f"/api/v1/api-keys/{key_id}")
    assert repeated_revoke.status_code == 404


@pytest.mark.asyncio
async def test_verify_api_key_uses_redis_after_first_database_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    api_key_value = "serm_live_test-client-key"
    redis = FakeRedis()
    db = AsyncMock()
    db.scalar.return_value = tenant_id
    monkeypatch.setattr(api_keys, "AsyncSessionLocal", lambda: FakeSessionContext(db))

    test_app = FastAPI(dependencies=[Depends(RateLimitDependency())])
    test_app.middleware("http")(add_rate_limit_headers)
    test_app.state.redis_pool = redis

    @test_app.get("/api/v1/protected")
    async def protected(verified_tenant: UUID = Depends(verify_api_key)) -> dict:
        return {"tenant_id": str(verified_tenant)}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
        headers={"X-API-Key": api_key_value},
    ) as client:
        first = await client.get("/api/v1/protected")
        second = await client.get("/api/v1/protected")

    assert first.status_code == second.status_code == 200
    assert first.json()["tenant_id"] == second.json()["tenant_id"] == str(tenant_id)
    assert first.headers["x-ratelimit-limit"] == "100"
    db.scalar.assert_awaited_once()
    assert redis.cache[f"api_key:tenant:{hash_api_key(api_key_value)}"] == str(
        tenant_id
    )
    assert redis.expirations[f"api_key:tenant:{hash_api_key(api_key_value)}"] == 300
    assert len(redis.counters) == 1
    assert next(iter(redis.counters)).startswith(f"rate_limit:{tenant_id}:api:")
    key_hash = hash_api_key(api_key_value)
    assert redis.cache[f"apikey:last_used:{key_hash}"]
    assert redis.expirations[f"apikey:last_used:{key_hash}"] == 60
    assert redis.sorted_sets["apikey:last_used:pending"].keys() == {key_hash}


@pytest.mark.asyncio
async def test_api_key_usage_is_flushed_in_a_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infrastructure.queue.worker import api_key_usage

    redis = FakeRedis()
    key_hash = "a" * 64
    redis.sorted_sets["apikey:last_used:pending"] = {key_hash: 1234.5}
    result = Mock()
    result.scalar_one.return_value = 1
    session = AsyncMock()
    session.execute.return_value = result
    monkeypatch.setattr(
        api_key_usage,
        "AsyncSessionLocal",
        lambda: FakeSessionContext(session),
    )

    flushed = await api_key_usage.flush_api_key_usage({"redis": redis})

    assert flushed == {"processed": 1, "updated": 1}
    session.execute.assert_awaited_once()
    statement, params = session.execute.await_args.args
    assert "record_api_key_usage_batch" in str(statement)
    assert params == {"key_hashes": [key_hash], "used_at": [1234.5]}
    session.commit.assert_awaited_once()
    assert redis.sorted_sets["apikey:last_used:pending"] == {}
