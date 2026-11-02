"""Провайдеры LLM за единым интерфейсом LLMProvider: OpenAI-совместимые (OpenAI, Groq, vLLM, ...) и Anthropic.

Генератор знает только протокол LLMProvider: смена вендора = другая реализация в build_provider().
SDK импортируются лениво, клиенты внедряются снаружи (тесты подставляют фейки).
Ошибки SDK сводятся к LLMTransientError / LLMPermanentError / LLMOutputRejected по duck-typing
(`status_code`, имя класса), поэтому код одинаково работает с openai и anthropic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

from app.core.ai.errors import (
    LLMError,
    LLMOutputRejected,
    LLMPermanentError,
    LLMTransientError,
)

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic
    from openai import AsyncOpenAI

Role = Literal["user", "assistant"]
JsonMode = Literal["json_object", "json_schema", "none"]

_TRANSIENT_STATUSES: Final = frozenset({408, 409, 425, 429})
_TRANSIENT_CLASS_NAMES: Final = frozenset(
    {"APITimeoutError", "APIConnectionError", "TimeoutError", "ReadTimeout"}
)
_MAX_RETRY_AFTER_S: Final = 30.0

TOOL_NAME: Final = "submit_drafts"

# Схема для структурированного вывода (OpenAI json_schema strict / Anthropic tool input_schema).
# Ограничения длины и количества проверяет Pydantic: strict-режим не поддерживает minItems/maxLength.
RESPONSE_JSON_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["drafts"],
    "properties": {
        "drafts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["variant", "text"],
                "properties": {
                    "variant": {
                        "type": "string",
                        "enum": ["FORMAL", "EMPATHETIC", "ACTION_ORIENTED"],
                    },
                    "text": {"type": "string"},
                },
            },
        }
    },
}


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class LLMRequest:
    system: str
    messages: tuple[ChatMessage, ...]
    max_tokens: int
    temperature: float
    timeout_s: float


@dataclass(frozen=True, slots=True)
class LLMCompletion:
    text: str  # сырой JSON-текст: разбор и валидация на стороне генератора
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    async def complete(self, request: LLMRequest) -> LLMCompletion:
        """Один запрос к модели. Бросает только LLMError и его наследников."""
        ...


# --------------------------------------------------------------------------- #
# Сведение ошибок SDK
# --------------------------------------------------------------------------- #
def _retry_after(exc: BaseException) -> float | None:
    headers = getattr(getattr(exc, "response", None), "headers", None)
    value = headers.get("retry-after") if headers is not None else None
    try:
        seconds = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return None if seconds is None or seconds < 0 else min(seconds, _MAX_RETRY_AFTER_S)


def _error_code(exc: BaseException) -> str | None:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            code = error.get("code") or error.get("type")
            return str(code) if code else None
    return None


def map_sdk_error(exc: Exception) -> LLMError:
    """Сводит исключение SDK к типизированной ошибке. Неизвестное считается временным сбоем сети."""
    if isinstance(exc, LLMError):
        return exc
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)

    if status == 400 and _error_code(exc) == "json_validate_failed":
        body = getattr(exc, "body", None)
        failed = ""
        if isinstance(body, dict):
            error = body.get("error", body)
            failed = (
                str(error.get("failed_generation", ""))
                if isinstance(error, dict)
                else ""
            )
        return LLMOutputRejected(
            f"{name}: провайдер отклонил вывод как невалидный JSON", failed[:2000]
        )

    if isinstance(status, int):
        if (
            status in _TRANSIENT_STATUSES or status >= 500
        ):  # 529 (Anthropic overloaded) тоже здесь
            return LLMTransientError(f"{name}: HTTP {status}", _retry_after(exc))
        return LLMPermanentError(f"{name}: HTTP {status}")
    if name in _TRANSIENT_CLASS_NAMES or isinstance(
        exc, TimeoutError | ConnectionError
    ):
        return LLMTransientError(f"{name}: сеть или таймаут")
    return LLMTransientError(f"{name}: неизвестная ошибка провайдера")


# --------------------------------------------------------------------------- #
# OpenAI-совместимые
# --------------------------------------------------------------------------- #
class OpenAICompatibleProvider:
    """OpenAI, Groq и любой сервер с Chat Completions API.

    json_mode: "json_schema" — строгий structured output (OpenAI, часть моделей Groq),
    "json_object" — JSON-режим (универсально), "none" — без response_format (разбор терпимый).
    """

    def __init__(
        self, client: AsyncOpenAI, model: str, *, json_mode: JsonMode = "json_object"
    ) -> None:
        self._client = client
        self._model = model
        self._json_mode = json_mode

    def _response_format(self) -> dict[str, Any] | None:
        if self._json_mode == "json_schema":
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": TOOL_NAME,
                    "strict": True,
                    "schema": RESPONSE_JSON_SCHEMA,
                },
            }
        if self._json_mode == "json_object":
            return {"type": "json_object"}
        return None

    async def complete(self, request: LLMRequest) -> LLMCompletion:
        messages: list[dict[str, str]] = [{"role": "system", "content": request.system}]
        messages.extend(
            {"role": m.role, "content": m.content} for m in request.messages
        )
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": request.temperature,
            "max_completion_tokens": request.max_tokens,
            "timeout": request.timeout_s,
        }
        response_format = self._response_format()
        if response_format is not None:
            kwargs["response_format"] = response_format
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise map_sdk_error(exc) from exc

        choice = response.choices[0] if response.choices else None
        content = choice.message.content if choice is not None else None
        if not content:
            reason = getattr(choice, "finish_reason", "no_choices")
            raise LLMOutputRejected(f"пустой ответ модели (finish_reason={reason})")
        usage = getattr(response, "usage", None)
        return LLMCompletion(
            text=content,
            model=getattr(response, "model", self._model) or self._model,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
        )


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #
class AnthropicProvider:
    """Claude через принудительный tool_use: SDK возвращает уже разобранный объект по input_schema."""

    def __init__(self, client: AsyncAnthropic, model: str) -> None:
        self._client = client
        self._model = model

    async def complete(self, request: LLMRequest) -> LLMCompletion:
        try:
            response = await self._client.messages.create(
                model=self._model,
                system=request.system,
                messages=[
                    {"role": m.role, "content": m.content} for m in request.messages
                ],
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                timeout=request.timeout_s,
                tools=[
                    {
                        "name": TOOL_NAME,
                        "description": "Отправить три варианта ответа на отзыв.",
                        "input_schema": RESPONSE_JSON_SCHEMA,
                    }
                ],
                tool_choice={"type": "tool", "name": TOOL_NAME},
            )
        except Exception as exc:
            raise map_sdk_error(exc) from exc

        for block in response.content:
            if block.type == "tool_use":
                usage = getattr(response, "usage", None)
                return LLMCompletion(
                    text=json.dumps(block.input, ensure_ascii=False),
                    model=getattr(response, "model", self._model) or self._model,
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                )
        raise LLMOutputRejected(
            f"модель не вызвала инструмент (stop_reason={getattr(response, 'stop_reason', None)})"
        )


# --------------------------------------------------------------------------- #
# Фабрика
# --------------------------------------------------------------------------- #
def build_provider(
    name: Literal["openai", "groq", "anthropic"],
    *,
    api_key: str,
    model: str,
    base_url: str | None = None,
    json_mode: JsonMode = "json_object",
) -> LLMProvider:
    """Единая точка выбора вендора. Ключ приходит из настроек (env/secret manager), в коде его нет."""
    if not api_key:
        raise LLMPermanentError(f"не задан API-ключ провайдера {name}")
    if name == "anthropic":
        from anthropic import AsyncAnthropic

        return AnthropicProvider(
            AsyncAnthropic(api_key=api_key, base_url=base_url, max_retries=0), model
        )

    from openai import AsyncOpenAI

    if name == "groq" and base_url is None:
        base_url = "https://api.groq.com/openai/v1"
    # max_retries=0: повторы и backoff делает генератор, иначе тайм-бюджет не контролируется.
    return OpenAICompatibleProvider(
        AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=0),
        model,
        json_mode=json_mode,
    )
