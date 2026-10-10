"""Базовый интерфейс парсеров отзывов и иерархия исключений."""

from abc import ABC, abstractmethod
from typing import ClassVar

import structlog

from app.schemas.parser import Platform, RawReview

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Исключения: что ретраить, а что нет
# --------------------------------------------------------------------------- #
class ParserError(Exception):
    """Базовая ошибка парсинга. Сама по себе НЕ повторяется."""


class ParserTransportError(ParserError):
    """Таймаут, сетевой сбой, 403/429 от антибота, 5xx. ARQ-задача делает Retry."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after  # секунды, если площадка прислала Retry-After


class ParserDataError(ParserError):
    """Ответ получен, но формат не тот (сменился API/вёрстка). Ретрай бесполезен."""


class InvalidSourceUrlError(ParserError):
    """URL не принадлежит площадке или не содержит идентификатор организации."""


class UnsupportedPlatformError(ParserError):
    """Для площадки нет реализации парсера."""


# --------------------------------------------------------------------------- #
# Интерфейс
# --------------------------------------------------------------------------- #
class BaseReviewParser(ABC):
    platform: ClassVar[Platform]

    @abstractmethod
    async def fetch_reviews(self, url: str, limit: int) -> list[RawReview]:
        """Собирает до `limit` отзывов по ссылке на организацию.

        Raises:
            InvalidSourceUrlError: ссылка неверна (не ретраить)
            ParserTransportError:  временный сбой (ретраить)
            ParserDataError:       формат ответа изменился (не ретраить, в DLQ)
        """

    # --- единообразная телеметрия для всех реализаций -----------------------
    def _log_start(self, url: str, limit: int) -> None:
        logger.info(
            "parsing_started", platform=self.platform.value, url=url, limit=limit
        )

    def _log_done(self, collected: int, *, skipped: int = 0, pages: int = 1) -> None:
        logger.info(
            "parsing_finished",
            platform=self.platform.value,
            collected=collected,
            skipped=skipped,
            pages=pages,
        )

    def _log_selector_error(self, field: str, detail: str, **extra: object) -> None:
        """Поле не найдено/не разобрано: ранний сигнал смены формата площадки."""
        logger.warning(
            "parser_selector_error",
            platform=self.platform.value,
            field=field,
            detail=detail,
            **extra,
        )
