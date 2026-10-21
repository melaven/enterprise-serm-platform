"""
Глобальные обработчики исключений для FastAPI
"""

import logging
from asyncio import TimeoutError
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from .exceptions import SERMException
from .logger import get_correlation_id
from .middleware import CORRELATION_ID_HEADER

logger = logging.getLogger(__name__)


def create_error_response(
    status_code: int,
    message: str,
    error_type: str,
    details: Mapping[str, Any] | None = None,
    request_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Создает стандартизированный JSON-ответ для ошибок."""
    correlation_id = request_id or get_correlation_id() or "unknown"

    error_data: dict[str, Any] = {
        "success": False,
        "error": {
            "type": error_type,
            "message": message,
            "status_code": status_code,
        },
        "correlation_id": correlation_id,
    }

    if details:
        error_data["error"]["details"] = details

    merged_headers = dict(headers or {})
    merged_headers[CORRELATION_ID_HEADER] = correlation_id

    return JSONResponse(
        status_code=status_code,
        content=error_data,
        headers=merged_headers,
    )


async def serm_exception_handler(request: Request, exc: SERMException) -> JSONResponse:
    """Обработчик кастомных исключений SERM."""
    logger.error(
        "SERM exception",
        extra={"error_type": type(exc).__name__, "status_code": exc.status_code},
    )

    return create_error_response(
        status_code=exc.status_code,
        message="Business operation failed",
        error_type=type(exc).__name__,
        request_id=getattr(request.state, "correlation_id", None)
        or get_correlation_id(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Обработчик стандартных HTTP исключений FastAPI."""
    logger.warning("HTTP exception", extra={"status_code": exc.status_code})

    message_map = {
        404: "Ресурс не найден",
        403: "Доступ запрещен",
        401: "Требуется авторизация",
        405: "Метод не поддерживается",
        410: "Операция отключена",
        500: "Внутренняя ошибка сервера",
    }

    message = message_map.get(exc.status_code, "HTTP request failed")

    return create_error_response(
        status_code=exc.status_code,
        message=message,
        error_type="HTTPException",
        request_id=getattr(request.state, "correlation_id", None)
        or get_correlation_id(),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Обработчик ошибок валидации Pydantic."""
    validation_errors = exc.errors()
    logger.warning(
        "Validation Error",
        extra={
            "fields": [
                {
                    "field": " -> ".join(str(part) for part in error["loc"]),
                    "type": error["type"],
                }
                for error in validation_errors
            ]
        },
    )

    safe_validation_errors = [
        {
            "field": " -> ".join(str(part) for part in error["loc"]),
            "type": error["type"],
        }
        for error in validation_errors
    ]

    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Ошибка валидации входных данных",
        error_type="ValidationError",
        details={"validation_errors": safe_validation_errors},
        request_id=getattr(request.state, "correlation_id", None)
        or get_correlation_id(),
    )


async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Обработчик ошибок SQLAlchemy/Базы данных."""
    logger.error("Database error", extra={"error_type": type(exc).__name__})

    if isinstance(exc, IntegrityError):
        message = "Нарушение целостности данных"
        error_type = "IntegrityError"
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, OperationalError):
        message = "Ошибка подключения к базе данных"
        error_type = "OperationalError"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        message = "Ошибка базы данных"
        error_type = "DatabaseError"
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    details = None
    if hasattr(exc, "orig") and exc.orig is not None:
        orig = exc.orig
        # exc.orig может быть dict или Exception object
        if isinstance(orig, dict):
            details = {"error_code": orig.get("pgcode")}
        elif hasattr(orig, "pgcode"):
            details = {"error_code": getattr(orig, "pgcode", None)}

    return create_error_response(
        status_code=status_code,
        message=message,
        error_type=error_type,
        details=details,
        request_id=getattr(request.state, "correlation_id", None)
        or get_correlation_id(),
    )


async def timeout_exception_handler(
    request: Request, exc: TimeoutError
) -> JSONResponse:
    """Обработчик таймаутов."""
    logger.error("Timeout error")

    return create_error_response(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        message="Превышено время ожидания операции",
        error_type="TimeoutError",
        request_id=getattr(request.state, "correlation_id", None)
        or get_correlation_id(),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обработчик всех непредвиденных исключений."""
    logger.critical("Unhandled exception", extra={"error_type": type(exc).__name__})

    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Внутренняя ошибка сервера",
        error_type="InternalServerError",
        details={"exception_type": type(exc).__name__},
        request_id=getattr(request.state, "correlation_id", None)
        or get_correlation_id(),
    )
