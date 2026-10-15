"""
Глобальные обработчики исключений для FastAPI
"""

import logging
from asyncio import TimeoutError
from typing import Any, Mapping

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from .exceptions import SERMException, DatabaseTimeoutError, DatabaseError
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
    logger.error("SERM Exception: %s", exc.message, exc_info=True)

    return create_error_response(
        status_code=exc.status_code,
        message=exc.message,
        error_type=type(exc).__name__,
        details=exc.details,
        request_id=getattr(request.state, "correlation_id", None) or get_correlation_id(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Обработчик стандартных HTTP исключений FastAPI."""
    logger.warning("HTTP Exception %s: %s", exc.status_code, exc.detail)

    message_map = {
        404: "Ресурс не найден",
        403: "Доступ запрещен",
        401: "Требуется авторизация",
        405: "Метод не поддерживается",
        500: "Внутренняя ошибка сервера",
    }

    message = message_map.get(exc.status_code, str(exc.detail))

    return create_error_response(
        status_code=exc.status_code,
        message=message,
        error_type="HTTPException",
        details={"original_detail": exc.detail} if exc.detail != message else None,
        request_id=getattr(request.state, "correlation_id", None) or get_correlation_id(),
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Обработчик ошибок валидации Pydantic."""
    logger.warning("Validation Error: %s", exc.errors())

    validation_errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(x) for x in error["loc"])
        validation_errors.append(
            {
                "field": field_path,
                "message": error["msg"],
                "type": error["type"],
                "input": error.get("input"),
            }
        )

    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Ошибка валидации входных данных",
        error_type="ValidationError",
        details={"validation_errors": validation_errors},
        request_id=getattr(request.state, "correlation_id", None) or get_correlation_id(),
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Обработчик ошибок SQLAlchemy/Базы данных."""
    logger.error("Database Error: %s", str(exc), exc_info=True)

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

    details = {"error_code": getattr(exc, "orig", {}).get("pgcode")} if hasattr(exc, "orig") else None

    return create_error_response(
        status_code=status_code,
        message=message,
        error_type=error_type,
        details=details,
        request_id=getattr(request.state, "correlation_id", None) or get_correlation_id(),
    )


async def timeout_exception_handler(request: Request, exc: TimeoutError) -> JSONResponse:
    """Обработчик таймаутов."""
    logger.error("Timeout Error: %s", str(exc), exc_info=True)

    return create_error_response(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        message="Превышено время ожидания операции",
        error_type="TimeoutError",
        request_id=getattr(request.state, "correlation_id", None) or get_correlation_id(),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обработчик всех непредвиденных исключений."""
    logger.critical("Unhandled Exception: %s", str(exc), exc_info=True)

    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Внутренняя ошибка сервера",
        error_type="InternalServerError",
        details={"exception_type": type(exc).__name__},
        request_id=getattr(request.state, "correlation_id", None) or get_correlation_id(),
    )