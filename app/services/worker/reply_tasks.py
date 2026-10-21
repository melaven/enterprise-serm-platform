from typing import NoReturn


async def publish_review_reply(
    ctx: dict[str, object],
    tenant_id: str,
    review_id: str,
    reply_text: str,
) -> NoReturn:
    raise RuntimeError(
        "Review reply publishing is disabled because external review IDs are not stored"
    )
