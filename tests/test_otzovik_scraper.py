import logging

import pytest

from app.infrastructure.integrations.review_platforms.scraper import (
    OtzovikScraperAdapter,
)


@pytest.mark.asyncio
async def test_otzovik_publish_reply_logs_manual_publication_and_succeeds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    adapter = OtzovikScraperAdapter("unused", {})

    assert await adapter.publish_reply("123", "Thanks for your feedback") is True
    assert (
        "Режим SI-Ассистента: текст готов для ручной публикации на площадке Отзовик"
    ) in caplog.text
