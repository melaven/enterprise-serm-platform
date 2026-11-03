import pytest

from app.infrastructure.redis.deduplicator import RedisDeduplicator


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int, bool]] = []

    async def set(
        self,
        name: str,
        value: str,
        *,
        ex: int,
        nx: bool,
    ) -> bool | None:
        self.set_calls.append((name, value, ex, nx))
        if nx and name in self.values:
            return None
        self.values[name] = value
        return True


@pytest.mark.asyncio
async def test_is_duplicate_uses_expiring_nx_key_and_detects_second_event() -> None:
    redis = _FakeRedis()
    deduplicator = RedisDeduplicator(redis)

    assert not await deduplicator.is_duplicate("Yandex", "review-123")
    assert await deduplicator.is_duplicate("Yandex", "review-123")

    assert redis.set_calls == [
        ("dedup:review:yandex:review-123", "1", 300, True),
        ("dedup:review:yandex:review-123", "1", 300, True),
    ]


@pytest.mark.asyncio
async def test_is_duplicate_uses_custom_ttl() -> None:
    redis = _FakeRedis()

    assert not await RedisDeduplicator(redis).is_duplicate(
        "google", "location-review-1", ttl_seconds=900
    )
    assert redis.set_calls == [
        ("dedup:review:google:location-review-1", "1", 900, True)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("platform", "external_id", "ttl_seconds"),
    [("", "review", 300), ("yandex", " ", 300), ("yandex", "review", 0)],
)
async def test_is_duplicate_rejects_invalid_key_components_and_ttl(
    platform: str,
    external_id: str,
    ttl_seconds: int,
) -> None:
    with pytest.raises(ValueError):
        await RedisDeduplicator(_FakeRedis()).is_duplicate(
            platform,
            external_id,
            ttl_seconds=ttl_seconds,
        )
