import asyncio

import httpx
import pytest

from app.services.ai_processor import AIProcessorConfig, ReviewAIProcessor


def test_review_ai_processor_does_not_send_source_text_outbound() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    processor = ReviewAIProcessor(
        client,
        AIProcessorConfig(api_key="test-key"),
    )
    try:
        with pytest.raises(RuntimeError, match="disabled"):
            asyncio.run(processor.process([]))
    finally:
        asyncio.run(client.aclose())

    assert requests == []
