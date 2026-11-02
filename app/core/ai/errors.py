"""Ошибки LLM-слоя. Единая иерархия для всех провайдеров и воркеров.

Правило обработки:
  * LLMTransientError  - временный сбой (таймаут, 429, 5xx, обрыв): повтор позже имеет смысл;
  * LLMPermanentError  - повтор не поможет (ключ, модель, формат запроса): нужен алерт, не fallback;
  * LLMOutputRejected  - провайдер сам забраковал вывод модели как невалидный JSON.
"""

from __future__ import annotations


class LLMError(RuntimeError):
    """База для всех ошибок LLM-слоя."""


class LLMTransientError(LLMError):
    """Временный сбой провайдера (429, 5xx, таймаут, обрыв соединения)."""

    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class LLMPermanentError(LLMError):
    """Постоянная ошибка запроса (401/403/404/422, неверная модель): повтор не поможет."""


class LLMOutputRejected(LLMError):
    """Провайдер отклонил вывод модели как невалидный (например, Groq json_validate_failed)."""

    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw
