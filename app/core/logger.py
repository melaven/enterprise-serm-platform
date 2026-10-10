"""
Enterprise-уровень логирования с structlog + Correlation ID
Централизованная настройка для FastAPI и ARQ Worker
"""

import logging
import os
import sys
from contextvars import ContextVar
from typing import Any, Dict, Optional, Union
from uuid import uuid4

import structlog
from structlog.types import Processor


# Контекстная переменная для Correlation ID
correlation_id_context: ContextVar[Optional[str]] = ContextVar(
    'correlation_id', default=None
)

# Константы для совместимости с tracing.py
CORRELATION_ID_KEY = "correlation_id"


def get_correlation_id() -> Optional[str]:
    """Получить текущий Correlation ID из контекста"""
    return correlation_id_context.get()


def set_correlation_id(correlation_id: str) -> Any:
    """Установить Correlation ID в контекст и вернуть токен для reset"""
    token = correlation_id_context.set(correlation_id)
    return token


def reset_correlation_id(token: Any) -> None:
    """Сбросить Correlation ID используя токен"""
    correlation_id_context.reset(token)


def new_correlation_id() -> str:
    """Генерация нового Correlation ID (алиас для generate_correlation_id)"""
    return generate_correlation_id()


def generate_correlation_id() -> str:
    """Генерация нового Correlation ID"""
    return str(uuid4())


def add_correlation_id_processor(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Structlog processor для автоматического добавления correlation_id
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def add_service_info_processor(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Structlog processor для добавления информации о сервисе
    """
    event_dict.setdefault("service", "serm-api")
    event_dict.setdefault("version", "1.0.0")
    return event_dict


def add_caller_info_processor(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Structlog processor для добавления информации о вызывающем коде
    """
    # Получаем информацию из стека вызовов
    import inspect
    frame = inspect.currentframe()
    try:
        # Идем вверх по стеку чтобы найти реальный вызывающий код
        # (пропускаем фреймы structlog)
        caller_frame = frame
        while caller_frame:
            caller_frame = caller_frame.f_back
            if caller_frame and not any(
                structlog_path in str(caller_frame.f_code.co_filename)
                for structlog_path in ['structlog', 'logging']
            ):
                break
        
        if caller_frame:
            event_dict["caller"] = {
                "module": caller_frame.f_code.co_filename.split('/')[-1],
                "function": caller_frame.f_code.co_name,
                "line": caller_frame.f_lineno
            }
    finally:
        del frame
        
    return event_dict


def configure_logging(
    *,
    level: Union[str, int] = logging.INFO,
    json_format: bool = True,
    include_caller_info: bool = False,
    service_name: str = "serm-api"
) -> None:
    """
    Настройка enterprise-логирования с structlog
    
    Args:
        level: Уровень логирования (INFO, DEBUG, etc.)
        json_format: Использовать JSON формат для продакшна
        include_caller_info: Включать информацию о вызывающем коде (для дебага)
        service_name: Имя сервиса для логов
    """
    
    import structlog.contextvars
    import structlog.processors
    import structlog.dev
    import structlog.stdlib
    
    # Определяем режим работы
    is_production = os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod")
    is_development = not is_production
    
    # Настройка процессоров structlog
    processors: list[Processor] = [
        # Базовые процессоры
        structlog.contextvars.merge_contextvars,
        add_correlation_id_processor,
        add_service_info_processor,
        
        # Стандартные процессоры structlog
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
    ]
    
    # Добавляем caller info только для разработки или если явно запрошено
    if include_caller_info or is_development:
        processors.append(add_caller_info_processor)
    
    # Процессор для exception handling
    if is_development:
        processors.append(structlog.dev.set_exc_info)
    else:
        processors.append(structlog.processors.format_exc_info)
    
    # Финальный процессор форматирования
    if json_format or is_production:
        # JSON формат для продакшна и централизованного логирования
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Красивый консольный вывод для разработки
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Настройка structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=False,  # Для возможности динамической перенастройки
    )
    
    # Настройка стандартного logging для интеграции с библиотеками
    logging.basicConfig(
        level=level,
        format="%(message)s" if json_format else "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    
    # Перенаправляем стандартные логи в structlog
    logging.getLogger().handlers.clear()
    
    # В новых версиях structlog используется ProcessorFormatter
    import structlog.stdlib
    handler = logging.StreamHandler()
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer() if json_format else structlog.dev.ConsoleRenderer(colors=True)
    ))
    logging.getLogger().addHandler(handler)
    
    # Настройка логгеров сторонних библиотек
    library_loggers = [
        'uvicorn',
        'uvicorn.access', 
        'uvicorn.error',
        'fastapi',
        'sqlalchemy.engine',
        'arq.worker',
        'redis',
        'httpx'
    ]
    
    for logger_name in library_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        # Отключаем дублирование логов
        logger.propagate = True
    
    # Специальная настройка для ARQ
    arq_logger = logging.getLogger('arq')
    arq_logger.setLevel(level)
    
    # Получаем настроенный structlog logger
    logger = structlog.get_logger()
    
    logger.info(
        "Enterprise logging configured",
        level=logging.getLevelName(level),
        json_format=json_format,
        include_caller_info=include_caller_info,
        service_name=service_name,
        environment=os.getenv("ENVIRONMENT", "development")
    )


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Получить настроенный structlog logger
    
    Args:
        name: Имя логгера (опционально)
        
    Returns:
        Настроенный structlog logger
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


# Декоратор для автоматического логирования функций
def traced_function(func_name: Optional[str] = None):
    """
    Декоратор для автоматического логирования вызовов функций с correlation ID
    """
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger()
            actual_func_name = func_name or func.__name__
            
            # Устанавливаем correlation ID если его нет
            if not get_correlation_id():
                set_correlation_id(generate_correlation_id())
            
            logger.info(
                f"Function {actual_func_name} started",
                function=actual_func_name,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )
            
            try:
                result = await func(*args, **kwargs)
                logger.info(
                    f"Function {actual_func_name} completed",
                    function=actual_func_name,
                    success=True
                )
                return result
            except Exception as e:
                logger.error(
                    f"Function {actual_func_name} failed",
                    function=actual_func_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    success=False
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger()
            actual_func_name = func_name or func.__name__
            
            # Устанавливаем correlation ID если его нет
            if not get_correlation_id():
                set_correlation_id(generate_correlation_id())
            
            logger.info(
                f"Function {actual_func_name} started",
                function=actual_func_name,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )
            
            try:
                result = func(*args, **kwargs)
                logger.info(
                    f"Function {actual_func_name} completed",
                    function=actual_func_name,
                    success=True
                )
                return result
            except Exception as e:
                logger.error(
                    f"Function {actual_func_name} failed",
                    function=actual_func_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    success=False
                )
                raise
        
        # Возвращаем соответствующий wrapper
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Алиас для ARQ задач
traced_task = traced_function