"""Middleware: уникальный Correlation ID на каждый HTTP-запрос."""

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logger import (
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

CORRELATION_ID_HEADER = "X-Correlation-ID"

log: structlog.stdlib.BoundLogger = structlog.get_logger("app.http")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Генерирует UUID4, кладёт в ContextVar и возвращает в X-Correlation-ID.

    ID всегда генерируется на сервере: входящему заголовку от клиента не доверяем
    (иначе им можно подделывать/засорять логи).

    Заголовок не добавляется только к 500 от необработанных исключений: такой
    ответ формирует ServerErrorMiddleware снаружи этого слоя. ID при этом
    есть в логе записи об ошибке.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = new_correlation_id()
        token = set_correlation_id(correlation_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            log.info(
                "request_finished",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return response
        except Exception:
            log.exception(
                "request_failed", method=request.method, path=request.url.path
            )
            raise
        finally:
            reset_correlation_id(token)
