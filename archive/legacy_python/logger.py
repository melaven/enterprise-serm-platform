"""Структурированное JSON-логирование (structlog) со сквозным Correlation ID.

Идея: correlation_id лежит в ContextVar. Процессор `add_correlation_id` добавляет
его в КАЖДУЮ запись: и из structlog, и из stdlib `logging` (uvicorn, arq, SQLAlchemy),
потому что stdlib-логи тоже идут через structlog-форматтер.

Использование:
    configure_logging()                      # один раз при старте API и воркера
    log = structlog.get_logger(__name__)
    log.info("review_saved", review_id=...)  # -> {"correlation_id": "...", ...}
"""

import logging
import os
import sys
from collections.abc import Iterable

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

from app.core.correlation import (  # noqa: F401  (реэкспорт: единая точка импорта)
    CORRELATION_ID_KEY,
    get_correlation_id,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

# Логгеры сторонних библиотек со своими обработчиками: забираем их в общий формат.
_CAPTURED_LOGGERS: tuple[str, ...] = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "arq",
)


# --------------------------------------------------------------------------- #
# Процессор structlog
# --------------------------------------------------------------------------- #
def add_correlation_id(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Добавляет correlation_id из контекста; явно переданное значение не затирает."""
    correlation_id = get_correlation_id()
    if correlation_id is not None:
        event_dict.setdefault(CORRELATION_ID_KEY, correlation_id)
    return event_dict


# --------------------------------------------------------------------------- #
# Конфигурация
# --------------------------------------------------------------------------- #
def configure_logging(
    *,
    level: str = "INFO",
    json_logs: bool = True,
    captured_loggers: Iterable[str] = _CAPTURED_LOGGERS,
) -> None:
    """Настраивает structlog и корневой stdlib-логгер. Безопасно вызывать повторно.

    json_logs=False даёт цветной консольный вывод для локальной разработки.
    """
    # Общая цепочка: применяется и к structlog-логам, и к stdlib-логам.
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # bind_contextvars() тоже работает
        add_correlation_id,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer: Processor = (
        structlog.processors.JSONRenderer(
            ensure_ascii=False
        )  # русский текст читаем в docker logs
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.dict_tracebacks if json_logs else _passthrough,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn/arq ставят собственные обработчики: убираем, чтобы не было дублей
    # и чтобы их записи тоже получили JSON и correlation_id.
    for name in captured_loggers:
        captured = logging.getLogger(name)
        captured.handlers.clear()
        captured.propagate = True


def _passthrough(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    return event_dict


def configure_logging_from_env() -> None:
    """LOG_LEVEL (INFO) и LOG_FORMAT (json | console) из окружения. Для api и воркера."""
    configure_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        json_logs=os.getenv("LOG_FORMAT", "json").lower() != "console",
    )
