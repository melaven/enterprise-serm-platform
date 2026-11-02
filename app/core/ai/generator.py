"""AIResponseGenerator: три варианта ответа на отзыв с жёсткой валидацией и безопасным fallback.

Конвейер одной генерации:
  1. отзыв без текста (только оценка) -> шаблоны без вызова LLM (retryable=False);
  2. System Prompt под тенанта и полярность отзыва; отзыв передаётся как данные внутри <review>;
  3. вызов провайдера под жёстким дедлайном (asyncio.timeout) + backoff на временных сбоях;
  4. разбор JSON и проверка DraftBatch (ровно 3 разных варианта, без контактов/плейсхолдеров/markdown);
     при невалидном выводе модель видит, что именно не так (repair-сообщение), без значений полей;
  5. попытки исчерпаны -> шаблоны (source=FALLBACK, retryable=True, причина в fallback_reason);
  6. LLMPermanentError (ключ, модель) НЕ маскируется шаблоном: пробрасывается, чтобы сработал алерт.

В логи не попадают текст отзыва и черновики (персональные данные, 152-ФЗ): только id, коды и метрики.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Final

from pydantic import ValidationError

from app.core.ai.errors import LLMOutputRejected, LLMPermanentError, LLMTransientError
from app.core.ai.fallback import build_fallback_drafts
from app.core.ai.prompts import (
    PROMPT_VERSION,
    build_repair_message,
    build_system_prompt,
    build_user_message,
    classify_polarity,
    has_meaningful_text,
    is_high_risk,
    sanitize_review_text,
    summarize_validation_error,
)
from app.core.ai.providers import ChatMessage, LLMCompletion, LLMProvider, LLMRequest
from app.core.ai.schemas import (
    DraftBatch,
    GenerationResult,
    GenerationSource,
    Polarity,
    ReviewLike,
    ReviewSnapshot,
    TenantContext,
)

log = logging.getLogger(__name__)

REASON_NO_TEXT: Final = "review_has_no_text"
REASON_TIMEOUT: Final = "llm_timeout"
REASON_UNAVAILABLE: Final = "llm_unavailable"
REASON_MALFORMED: Final = "malformed_output"

_MAX_BACKOFF_S: Final = 5.0
_FENCE_RE: Final = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_RAW_ECHO_LIMIT: Final = 1500

Sleeper = Callable[[float], Awaitable[None]]


def parse_batch(raw: str) -> DraftBatch:
    """Достаёт JSON-объект из ответа (терпимо к markdown-обёртке и тексту вокруг) и валидирует контракт.

    Бросает ValueError (включая pydantic.ValidationError и json.JSONDecodeError).
    """
    candidate = _FENCE_RE.sub("", raw).strip()
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("в ответе нет JSON-объекта")
    return DraftBatch.model_validate_json(candidate[start : end + 1])


class AIResponseGenerator:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        max_attempts: int = 3,
        timeout_s: float = 25.0,
        temperature: float = 0.5,
        max_output_tokens: int = 1600,
        deadline_grace_s: float = 2.0,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts должен быть >= 1")
        if timeout_s <= 0:
            raise ValueError("timeout_s должен быть > 0")
        self._provider = provider
        self._max_attempts = max_attempts
        self._timeout_s = timeout_s
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._deadline_grace_s = deadline_grace_s
        self._sleep = sleep

    async def generate(
        self, review: ReviewLike, tenant: TenantContext
    ) -> GenerationResult:
        """Всегда возвращает 3 валидных варианта либо бросает LLMPermanentError (ошибка конфигурации)."""
        started = time.monotonic()
        snapshot = ReviewSnapshot.from_review(review)
        text = sanitize_review_text(snapshot.body)
        polarity = classify_polarity(snapshot)

        if not has_meaningful_text(text):
            return self._fallback(
                snapshot, tenant, polarity, REASON_NO_TEXT, 0, started, retryable=False
            )

        system = build_system_prompt(
            tenant, polarity, high_risk=is_high_risk(snapshot, text)
        )
        messages: list[ChatMessage] = [
            ChatMessage("user", build_user_message(snapshot, text))
        ]
        reason = REASON_UNAVAILABLE

        for attempt in range(1, self._max_attempts + 1):
            request = LLMRequest(
                system=system,
                messages=tuple(messages),
                max_tokens=self._max_output_tokens,
                temperature=self._temperature,
                timeout_s=self._timeout_s,
            )
            try:
                completion = await self._call(request)
            except TimeoutError:
                reason = REASON_TIMEOUT
                await self._backoff(attempt, None)
                continue
            except LLMTransientError as exc:
                reason = REASON_UNAVAILABLE
                await self._backoff(attempt, exc.retry_after_s)
                continue
            except LLMOutputRejected as exc:
                reason = REASON_MALFORMED
                messages = self._with_repair(
                    messages, exc.raw, "ответ не является валидным JSON"
                )
                continue
            except LLMPermanentError:
                log.error(
                    "draft_generation_permanent_error",
                    extra={"review_id": str(snapshot.id)},
                )
                raise

            try:
                batch = parse_batch(completion.text)
            except (
                ValueError,
                ValidationError,
            ) as exc:  # ValidationError наследует ValueError
                reason = REASON_MALFORMED
                log.warning(
                    "draft_generation_invalid_output",
                    extra={
                        "review_id": str(snapshot.id),
                        "attempt": attempt,
                        "problem": summarize_validation_error(exc),
                    },
                )
                messages = self._with_repair(
                    messages, completion.text, summarize_validation_error(exc)
                )
                continue

            result = GenerationResult(
                drafts=batch.ordered(),
                source=GenerationSource.LLM,
                prompt_version=PROMPT_VERSION,
                attempts=attempt,
                latency_ms=_elapsed_ms(started),
                model=completion.model,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
            )
            log.info(
                "draft_generation_ok",
                extra={"review_id": str(snapshot.id), **result.to_log()},
            )
            return result

        return self._fallback(
            snapshot,
            tenant,
            polarity,
            reason,
            self._max_attempts,
            started,
            retryable=True,
        )

    # ------------------------------------------------------------------ #
    async def _call(self, request: LLMRequest) -> LLMCompletion:
        # Жёсткий дедлайн поверх SDK-таймаута: защита от зависшего соединения. TimeoutError ловит generate().
        async with asyncio.timeout(self._timeout_s + self._deadline_grace_s):
            return await self._provider.complete(request)

    async def _backoff(self, attempt: int, retry_after_s: float | None) -> None:
        if attempt >= self._max_attempts:
            return
        delay = retry_after_s if retry_after_s is not None else 0.5 * 2 ** (attempt - 1)
        await self._sleep(min(delay, _MAX_BACKOFF_S))

    @staticmethod
    def _with_repair(
        messages: list[ChatMessage], raw: str, problem: str
    ) -> list[ChatMessage]:
        """Добавляет в диалог невалидный ответ модели и просьбу исправить. Историю не накапливаем: только последний."""
        head = messages[:1]
        echoed = raw[:_RAW_ECHO_LIMIT]
        repair = [
            ChatMessage("assistant", echoed or "{}"),
            ChatMessage("user", build_repair_message(problem)),
        ]
        return [*head, *repair]

    def _fallback(
        self,
        snapshot: ReviewSnapshot,
        tenant: TenantContext,
        polarity: Polarity,
        reason: str,
        attempts: int,
        started: float,
        *,
        retryable: bool,
    ) -> GenerationResult:
        result = GenerationResult(
            drafts=build_fallback_drafts(tenant, polarity),
            source=GenerationSource.FALLBACK,
            prompt_version=PROMPT_VERSION,
            attempts=attempts,
            latency_ms=_elapsed_ms(started),
            fallback_reason=reason,
            retryable=retryable,
        )
        log.warning(
            "draft_generation_fallback",
            extra={"review_id": str(snapshot.id), **result.to_log()},
        )
        return result


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


__all__ = [
    "AIResponseGenerator",
    "parse_batch",
    "REASON_NO_TEXT",
    "REASON_TIMEOUT",
    "REASON_UNAVAILABLE",
    "REASON_MALFORMED",
]
