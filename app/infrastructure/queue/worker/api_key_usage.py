"""Batch deferred API-key usage timestamps from Redis into PostgreSQL."""

from typing import Any

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.logger import get_logger

logger = get_logger(__name__)

_USAGE_QUEUE_KEY = "apikey:last_used:pending"
_BATCH_SIZE = 500
_ACK_USAGE_SCRIPT = """
for index = 1, #ARGV, 2 do
    local score = redis.call('ZSCORE', KEYS[1], ARGV[index])
    if score and tonumber(score) == tonumber(ARGV[index + 1]) then
        redis.call('ZREM', KEYS[1], ARGV[index])
    end
end
return 1
"""


async def flush_api_key_usage(ctx: dict[str, Any]) -> dict[str, int]:
    """Persist a bounded batch and acknowledge only timestamps actually written."""
    redis = ctx.get("redis")
    if redis is None:
        raise RuntimeError("ARQ Redis connection is unavailable")

    pending = await redis.zrange(
        _USAGE_QUEUE_KEY,
        0,
        _BATCH_SIZE - 1,
        withscores=True,
    )
    if not pending:
        return {"processed": 0}

    key_hashes = [
        key_hash.decode("ascii") if isinstance(key_hash, bytes) else key_hash
        for key_hash, _ in pending
    ]
    timestamps = [float(timestamp) for _, timestamp in pending]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT public.record_api_key_usage_batch("
                "CAST(:key_hashes AS text[]), "
                "CAST(:used_at AS double precision[]))"
            ),
            {"key_hashes": key_hashes, "used_at": timestamps},
        )
        updated = int(result.scalar_one())
        await session.commit()

    await redis.eval(
        _ACK_USAGE_SCRIPT,
        1,
        _USAGE_QUEUE_KEY,
        *(
            argument
            for key_hash, timestamp in zip(key_hashes, timestamps, strict=True)
            for argument in (key_hash, str(timestamp))
        ),
    )
    logger.info(
        "api_key_usage_batch_flushed",
        queued=len(key_hashes),
        updated=updated,
    )
    return {"processed": len(key_hashes), "updated": updated}
