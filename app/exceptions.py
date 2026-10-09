"""
Централизованная система обработки ошибок для SERM API
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class SERMException(Exception):
    """Базовый класс для всех исключений SERM"""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(SERMException):
    """Ресурс не найден (404)"""
    
    def __init__(self, resource: str, identifier: str = None):
        message = f"{resource} не найден"
        if identifier:
            message += f": {identifier}"
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class AccessDeniedError(SERMException):
    """Недостаточно прав доступа (403)"""
    
    def __init__(self, message: str = "Недостаточно прав доступа"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class ValidationError(SERMException):
    """Ошибка валидации данных (422)"""
    
    def __init__(self, field: str, value: Any, message: str):
        error_message = f"Некорректное значение для поля '{field}': {message}"
        details = {"field": field, "value": value, "validation_error": message}
        super().__init__(error_message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class DatabaseError(SERMException):
    """Ошибки работы с базой данных"""
    
    def __init__(self, message: str = "Ошибка базы данных", original_error: Exception = None):
        details = {}
        if original_error:
            details["original_error"] = str(original_error)
            details["error_type"] = type(original_error).__name__
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR, details)


class DatabaseTimeoutError(DatabaseError):
    """Таймаут базы данных"""
    
    def __init__(self, operation: str = "операции с базой данных"):
        message = f"Превышено время ожидания {operation}"
        super().__init__(message)
        self.status_code = status.HTTP_504_GATEWAY_TIMEOUT


class ExternalServiceError(SERMException):
    """Ошибки внешних сервисов (LLM, Supabase, etc.)"""
    
    def __init__(self, service: str, message: str = None):
        error_message = f"Ошибка внешнего сервиса {service}"
        if message:
            error_message += f": {message}"
        super().__init__(error_message, status.HTTP_502_BAD_GATEWAY)


class LLMServiceError(ExternalServiceError):
    """Ошибки LLM сервиса (Google Gemini)"""
    
    def __init__(self, message: str = "Ошибка генерации ответа"):
        super().__init__("LLM", message)


class BusinessLogicError(SERMException):
    """Ошибки бизнес-логики"""
    
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class EconomicsCalculationError(BusinessLogicError):
    """Ошибки экономических расчетов SERM"""
    
    def __init__(self, calculation_type: str, reason: str):
        message = f"Ошибка расчета {calculation_type}: {reason}"
        super().__init__(message)