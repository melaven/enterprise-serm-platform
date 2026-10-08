"""
Глобальные обработчики исключений для FastAPI
"""

import logging
import traceback
from typing import Dict, Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from asyncio import TimeoutError

from .exceptions import SERMException, DatabaseTimeoutError, DatabaseError

logger = logging.getLogger(__name__)


def create_error_response(
    status_code: int,
    message: str,
    error_type: str,
    details: Dict[str, Any] = None,
    request_id: str = None,
) -> JSONResponse:
    """Создает стандартизированный JSON-ответ для ошибок"""
    
    error_data = {
        "success": False,
        "error": {
            "type": error_type,
            "message": message,
            "status_code": status_code,
        }
    }
    
    if details:
        error_data["error"]["details"] = details
        
    if request_id:
        error_data["request_id"] = request_id
        
    return JSONResponse(
        status_code=status_code,
        content=error_data
    )


async def serm_exception_handler(request: Request, exc: SERMException) -> JSONResponse:
    """Обработчик кастомных исключений SERM"""
    
    logger.error(f"SERM Exception: {exc.message}", exc_info=True)
    
    return create_error_response(
        status_code=exc.status_code,
        message=exc.message,
        error_type=type(exc).__name__,
        details=exc.details,
        request_id=getattr(request.state, 'request_id', None)
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Обработчик стандартных HTTP исключений FastAPI"""
    
    logger.warning(f"HTTP Exception {exc.status_code}: {exc.detail}")
    
    # Локализация стандартных ошибок
    message_map = {
        404: "Ресурс не найден",
        403: "Доступ запрещен", 
        401: "Требуется авторизация",
        405: "Метод не поддерживается",
        500: "Внутренняя ошибка сервера"
    }
    
    message = message_map.get(exc.status_code, str(exc.detail))
    
    return create_error_response(
        status_code=exc.status_code,
        message=message,
        error_type="HTTPException",
        details={"original_detail": exc.detail} if exc.detail != message else None,
        request_id=getattr(request.state, 'request_id', None)
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Обработчик ошибок валидации Pydantic"""
    
    logger.warning(f"Validation Error: {exc.errors()}")
    
    validation_errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(x) for x in error["loc"])
        validation_errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input")
        })
    
    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Ошибка валидации входных данных",
        error_type="ValidationError",
        details={"validation_errors": validation_errors},
        request_id=getattr(request.state, 'request_id', None)
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Обработчик ошибок SQLAlchemy/Базы данных"""
    
    logger.error(f"Database Error: {str(exc)}", exc_info=True)
    
    # Определяем тип ошибки БД
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
    
    # В продакшене не показываем технические детали
    details = {"error_code": getattr(exc, 'orig', {}).get('pgcode')} if hasattr(exc, 'orig') else None
    
    return create_error_response(
        status_code=status_code,
        message=message,
        error_type=error_type,
        details=details,
        request_id=getattr(request.state, 'request_id', None)
    )


async def timeout_exception_handler(request: Request, exc: TimeoutError) -> JSONResponse:
    """Обработчик таймаутов"""
    
    logger.error(f"Timeout Error: {str(exc)}", exc_info=True)
    
    return create_error_response(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        message="Превышено время ожидания операции",
        error_type="TimeoutError",
        request_id=getattr(request.state, 'request_id', None)
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обработчик всех непредвиденных исключений"""
    
    logger.critical(f"Unhandled Exception: {str(exc)}", exc_info=True)
    
    # В продакшене не показываем stack trace
    details = {
        "exception_type": type(exc).__name__,
        "traceback": traceback.format_exc()  # Убрать в продакшене
    }
    
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Внутренняя ошибка сервера",
        error_type="InternalServerError",
        details=details,
        request_id=getattr(request.state, 'request_id', None)
    )