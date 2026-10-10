"""
Enterprise middleware для Correlation ID и трассировки запросов
"""

import time
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .logger import get_logger, set_correlation_id, get_correlation_id


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware для автоматического добавления Correlation ID к каждому запросу
    
    Функциональность:
    - Извлекает Correlation ID из заголовка X-Correlation-ID
    - Генерирует новый ID если заголовок отсутствует
    - Устанавливает ID в контекст для использования в логах
    - Добавляет ID в заголовки ответа
    - Логирует начало и завершение каждого запроса
    """
    
    def __init__(
        self,
        app,
        header_name: str = "X-Correlation-ID",
        generate_if_missing: bool = True
    ):
        super().__init__(app)
        self.header_name = header_name
        self.generate_if_missing = generate_if_missing
        self.logger = get_logger("correlation_middleware")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Обработка запроса с Correlation ID"""
        
        # Извлекаем или генерируем Correlation ID
        correlation_id = request.headers.get(self.header_name)
        
        if not correlation_id and self.generate_if_missing:
            correlation_id = str(uuid4())
        
        # Устанавливаем в контекст
        if correlation_id:
            set_correlation_id(correlation_id)
            # Также сохраняем в state запроса для обратной совместимости
            request.state.correlation_id = correlation_id
        
        # Логируем начало запроса
        start_time = time.time()
        
        self.logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            query_params=dict(request.query_params),
            user_agent=request.headers.get("User-Agent"),
            client_ip=self._get_client_ip(request),
            correlation_id=correlation_id
        )
        
        try:
            # Выполняем запрос
            response = await call_next(request)
            
            # Вычисляем время выполнения
            duration = time.time() - start_time
            
            # Добавляем Correlation ID в заголовки ответа
            if correlation_id:
                response.headers[self.header_name] = correlation_id
            
            # Логируем успешное завершение
            self.logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
                response_size=response.headers.get("content-length"),
                correlation_id=correlation_id
            )
            
            return response
            
        except Exception as e:
            # Вычисляем время до ошибки
            duration = time.time() - start_time
            
            # Логируем ошибку
            self.logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration * 1000, 2),
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id
            )
            
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Получение IP адреса клиента с учетом прокси"""
        
        # Проверяем заголовки прокси
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Берем первый IP из списка
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback на прямое подключение
        if request.client:
            return request.client.host
        
        return "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Расширенное middleware для детального логирования запросов
    
    Дополнительные возможности:
    - Логирование тела запроса (для отладки)
    - Логирование заголовков
    - Метрики производительности
    - Фильтрация чувствительных данных
    """
    
    def __init__(
        self,
        app,
        log_request_body: bool = False,
        log_response_body: bool = False,
        log_headers: bool = True,
        sensitive_headers: list = None
    ):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.log_headers = log_headers
        
        # Заголовки которые нужно скрыть в логах
        self.sensitive_headers = (sensitive_headers or [
            "authorization", "cookie", "x-api-key", 
            "x-auth-token", "authorization"
        ])
        
        self.logger = get_logger("request_logging")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Детальное логирование запроса"""
        
        correlation_id = get_correlation_id()
        
        # Логирование деталей запроса
        request_data = {
            "correlation_id": correlation_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params)
        }
        
        # Добавляем заголовки если нужно
        if self.log_headers:
            request_data["headers"] = self._filter_headers(dict(request.headers))
        
        # Добавляем тело запроса если нужно
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    # Пытаемся декодировать как текст
                    try:
                        request_data["body"] = body.decode("utf-8")
                    except UnicodeDecodeError:
                        request_data["body"] = f"<binary data, {len(body)} bytes>"
            except Exception as e:
                request_data["body_error"] = str(e)
        
        self.logger.debug("Request details", **request_data)
        
        # Выполняем запрос
        response = await call_next(request)
        
        # Логирование ответа
        response_data = {
            "correlation_id": correlation_id,
            "status_code": response.status_code,
            "response_headers": dict(response.headers) if self.log_headers else None
        }
        
        self.logger.debug("Response details", **response_data)
        
        return response
    
    def _filter_headers(self, headers: dict) -> dict:
        """Фильтрация чувствительных заголовков"""
        filtered = {}
        
        for key, value in headers.items():
            if key.lower() in self.sensitive_headers:
                filtered[key] = "***HIDDEN***"
            else:
                filtered[key] = value
        
        return filtered


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware для мониторинга производительности
    
    Возможности:
    - Измерение времени выполнения по этапам
    - Мониторинг медленных запросов
    - Сбор метрик для аналитики
    """
    
    def __init__(
        self,
        app,
        slow_request_threshold: float = 1.0,  # секунды
        log_slow_requests: bool = True
    ):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
        self.log_slow_requests = log_slow_requests
        self.logger = get_logger("performance")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Мониторинг производительности запроса"""
        
        start_time = time.time()
        correlation_id = get_correlation_id()
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Классифицируем производительность
            if duration > self.slow_request_threshold and self.log_slow_requests:
                self.logger.warning(
                    "Slow request detected",
                    correlation_id=correlation_id,
                    method=request.method,
                    path=request.url.path,
                    duration_ms=round(duration * 1000, 2),
                    threshold_ms=round(self.slow_request_threshold * 1000, 2)
                )
            
            # Общие метрики производительности
            self.logger.debug(
                "Request performance metrics",
                correlation_id=correlation_id,
                duration_ms=round(duration * 1000, 2),
                status_code=response.status_code,
                is_slow=duration > self.slow_request_threshold
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            self.logger.error(
                "Request failed with performance data",
                correlation_id=correlation_id,
                duration_ms=round(duration * 1000, 2),
                error=str(e),
                error_type=type(e).__name__
            )
            
            raise