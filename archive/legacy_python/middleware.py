"""Сквозной Correlation ID для HTTP: чистый ASGI-middleware (без BaseHTTPMiddleware).

Порядок: X-Correlation-ID → X-Request-ID → новый UUID4. ID кладётся в ContextVar
(попадает во все логи запроса), в scope["state"] (для обработчика 500) и в заголовок
ответа X-Correlation-ID.
"""

import time
from typing import Any

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.correlation import (
    CORRELATION_ID_HEADER,
    reset_correlation_id,
    resolve_correlation_id,
    set_correlation_id,
)

log: structlog.stdlib.BoundLogger = structlog.get_logger("app.http")

# Пробы живости не засоряют логи (пишутся на DEBUG).
_QUIET_PATHS = frozenset({"/health", "/healthz", "/ready"})


class CorrelationIdMiddleware:
    def __init__(
        self, app: ASGIApp, quiet_paths: frozenset[str] = _QUIET_PATHS
    ) -> None:
        self.app = app
        self.quiet_paths = quiet_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        correlation_id = resolve_correlation_id(Headers(scope=scope))
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        token = set_correlation_id(correlation_id)

        status_code = 500  # если приложение упало до отправки ответа
        started = time.perf_counter()

        async def send_with_header(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[CORRELATION_ID_HEADER] = correlation_id
            await send(message)

        path = scope.get("path", "")
        method = scope.get("method", "WS")
        try:
            await self.app(scope, receive, send_with_header)
        except Exception:
            log.exception("request_failed", method=method, path=path)
            raise
        finally:
            if scope["type"] == "http":
                emit = log.debug if path in self.quiet_paths else log.info
                emit(
                    "request_finished",
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )
            reset_correlation_id(token)


async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    """500 формирует ServerErrorMiddleware СНАРУЖИ нашего слоя: заголовок добавляем здесь.

    ID берём из scope["state"]: ContextVar к этому моменту уже сброшен. Текст исключения
    наружу не отдаём (может содержать внутренние детали), клиенту хватает ID для поддержки.
    """
    state: Any = request.scope.get("state", {})
    correlation_id = state.get("correlation_id")
    headers = {CORRELATION_ID_HEADER: correlation_id} if correlation_id else None
    return JSONResponse(
        {"detail": "Internal Server Error", "correlation_id": correlation_id},
        status_code=500,
        headers=headers,
    )
