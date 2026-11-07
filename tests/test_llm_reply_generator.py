from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from openai import RateLimitError
from tenacity import wait_none

from app.core.exceptions import LLMServiceError
from app.core.llm_reply_generator import MAX_RETRIES, LLMReplyGenerator


@pytest_asyncio.fixture
async def llm_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[LLMReplyGenerator, AsyncMock]:
    generator = LLMReplyGenerator(api_key="test-api-key", model="test-model")
    create_completion = AsyncMock()
    monkeypatch.setattr(generator.client.chat.completions, "create", create_completion)
    yield generator, create_completion
    await generator.close()


def _completion_response(reply: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
    )


@pytest.mark.asyncio
async def test_generate_reply_success(
    llm_generator: tuple[LLMReplyGenerator, AsyncMock],
) -> None:
    generator, create_completion = llm_generator
    create_completion.return_value = _completion_response("Спасибо за отзыв")

    reply = await generator.generate_reply("Отличное обслуживание", rating=5)

    assert reply == "Спасибо за отзыв"
    create_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_reply_tone(
    llm_generator: tuple[LLMReplyGenerator, AsyncMock],
) -> None:
    generator, create_completion = llm_generator
    create_completion.return_value = _completion_response("Спасибо за отзыв")

    await generator.generate_reply("Отличное обслуживание", rating=5)
    await generator.generate_reply("Плохое обслуживание", rating=1)

    positive_prompt = create_completion.await_args_list[0].kwargs["messages"][0][
        "content"
    ]
    negative_prompt = create_completion.await_args_list[1].kwargs["messages"][0][
        "content"
    ]
    assert "positive review" in positive_prompt
    assert "apology for a negative review" in negative_prompt
    assert positive_prompt != negative_prompt


@pytest.mark.asyncio
async def test_generate_reply_retries(
    llm_generator: tuple[LLMReplyGenerator, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator, create_completion = llm_generator
    response = httpx.Response(
        429,
        request=httpx.Request("POST", "https://api.example.test/chat/completions"),
    )
    create_completion.side_effect = RateLimitError(
        "Rate limit exceeded", response=response, body=None
    )
    monkeypatch.setattr(generator.generate_reply.retry, "wait", wait_none())

    with pytest.raises(LLMServiceError, match="Failed to generate reply"):
        await generator.generate_reply("Отличное обслуживание", rating=5)

    assert create_completion.await_count == MAX_RETRIES
