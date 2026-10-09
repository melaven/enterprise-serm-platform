"""Провайдеро-независимый контракт LLM для анализатора и генератора ответов.

Реальный клиент (Anthropic/OpenAI) пишется отдельно и реализует LLMClient.
Контракт: клиент САМ оборачивает ошибки SDK (таймаут, rate limit, 5xx, auth) в
LLMError, остальное сервисы считают багом и не глотают. Пример для Anthropic:

    class AnthropicLLMClient:
        def __init__(self, api_key: str, model: str) -> None:
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
            self._model = model

        async def complete(self, *, system, user, max_tokens=512, temperature=0.0):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
            except anthropic.APIError as exc:
                raise LLMError(type(exc).__name__) from exc
            return "".join(b.text for b in response.content if b.type == "text")

Приватность: в LLM уходят только оценка и текст отзыва. Имя автора не передаём.
"""

from typing import Protocol


class LLMError(Exception):
    """Любой сбой вызова LLM: сервисы откатываются на шаблоны/эвристику."""


class LLMUnavailableError(LLMError):
    """Провайдер не настроен или недоступен."""


class LLMClient(Protocol):
    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> str: ...


class UnconfiguredLLMClient:
    """Заглушка по умолчанию: любой вызов сразу даёт LLMUnavailableError."""

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> str:
        raise LLMUnavailableError("LLM provider is not configured")
