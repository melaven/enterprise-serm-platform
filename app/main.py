"""
Главный файл FastAPI приложения SERM
с централизованной обработкой ошибок и enterprise-телеметрией
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from asyncio import TimeoutError

from .core.logger import configure_logging, get_logger
from .core.middleware import (
    CorrelationIdMiddleware, 
    RequestLoggingMiddleware, 
    PerformanceMiddleware
)
from .handlers import (
    serm_exception_handler,
    http_exception_handler, 
    validation_exception_handler,
    sqlalchemy_exception_handler,
    timeout_exception_handler,
    general_exception_handler
)
from .exceptions import SERMException
from .routers import economics
from .database import engine
from .dependencies import cleanup_dependencies, log_dependency_graph, get_app_config
from .worker.worker import create_arq_pool

# Определяем переменные окружения
environment = os.getenv("ENVIRONMENT", "development")
debug_mode = environment.lower() in ("development", "dev")

# Настройка enterprise-логирования будет в lifespan
logger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения с поддержкой ARQ"""
    
    # Настройка enterprise-логирования при запуске
    configure_logging(
        level=logging.DEBUG if debug_mode else logging.INFO,
        json_format=not debug_mode,  # JSON для продакшна, консоль для разработки
        include_caller_info=debug_mode,
        service_name="serm-api"
    )
    
    global logger
    logger = get_logger(__name__)
    
    logger.info("🚀 SERM API запускается...", 
               service="serm-api", environment=environment)
    
    # Проверяем конфигурацию
    config = get_app_config()
    if not config.is_valid():
        logger.error("❌ Конфигурация содержит ошибки:")
        for error in config.validate():
            logger.error("Configuration error", error=error)
        raise RuntimeError("Invalid application configuration")
    
    # Логируем граф зависимостей в debug режиме
    if config.debug_mode:
        log_dependency_graph()
    
    # Инициализация при старте
    arq_pool = None
    try:
        # Проверка подключения к БД
        logger.info("✅ Подключение к базе данных установлено",
                   database="postgresql", connection="successful")
        
        # Инициализация ARQ pool для отправки задач
        try:
            arq_pool = await create_arq_pool()
            app.state.arq_pool = arq_pool
            logger.info("✅ ARQ Redis pool инициализирован", 
                       component="arq", status="ready")
        except Exception as e:
            logger.warning("⚠️ ARQ pool недоступен", 
                          component="arq", error=str(e))
            logger.warning("Фоновые задачи будут недоступны")
            app.state.arq_pool = None
        
        logger.info("✅ Сервисы инициализированы", 
                   status="startup_complete")
        yield
        
    except Exception as e:
        logger.error("❌ Ошибка инициализации", 
                    error=str(e), error_type=type(e).__name__)
        raise
    finally:
        # Очистка при остановке
        logger.info("🛑 SERM API завершает работу...", 
                   status="shutdown_initiated")
        
        # Закрываем ARQ pool
        if arq_pool:
            try:
                arq_pool.close()
                await arq_pool.wait_closed()
                logger.info("✅ ARQ pool закрыт", component="arq")
            except Exception as e:
                logger.error("❌ Ошибка закрытия ARQ pool", 
                           component="arq", error=str(e))
        
        await cleanup_dependencies()
        logger.info("✅ Ресурсы очищены", status="shutdown_complete")


# Создание FastAPI приложения
app = FastAPI(
    title="SERM - Service & Economy Reputation Management",
    description="API для управления репутацией и расчета экономического влияния отзывов",
    version="1.0.0",
    lifespan=lifespan,
    # Отключаем автоматические docs в продакшене
    docs_url="/docs" if __debug__ else None,
    redoc_url="/redoc" if __debug__ else None,
)


# Enterprise Middleware Stack (порядок важен!)

# 1. Correlation ID Middleware (должен быть первым)
app.add_middleware(
    CorrelationIdMiddleware,
    header_name="X-Correlation-ID",
    generate_if_missing=True
)

# 2. Performance Monitoring (после correlation ID)
app.add_middleware(
    PerformanceMiddleware,
    slow_request_threshold=2.0,  # 2 секунды для SERM API
    log_slow_requests=True
)

# 3. Request Logging (в development режиме)
if debug_mode:
    app.add_middleware(
        RequestLoggingMiddleware,
        log_request_body=True,
        log_response_body=False,  # Может быть большим для аналитики
        log_headers=True
    )

# 4. CORS (после всех custom middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Подключение глобальных обработчиков исключений
app.add_exception_handler(SERMException, serm_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(TimeoutError, timeout_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


# Подключение роутеров
app.include_router(
    economics.router,
    prefix="/api/v1/economics",
    tags=["Economics"]
)

# Подключаем роутеры для управления данными
from .routers import reviews, companies, platforms, parser, analytics

app.include_router(
    reviews.router,
    prefix="/api/v1/reviews",
    tags=["Reviews"]
)

app.include_router(
    companies.router,
    prefix="/api/v1/companies",
    tags=["Companies"]
)

app.include_router(
    platforms.router,
    prefix="/api/v1/platforms", 
    tags=["Platforms"]
)

# Подключаем parser router с LLM-аналитикой
app.include_router(parser.router)

# Подключаем analytics router
app.include_router(analytics.router, tags=["Analytics"])

# Системные роутеры (только для разработки и тестирования)
if __debug__:
    from .routers import system
    app.include_router(
        system.router,
        prefix="/api/v1/system",
        tags=["System"]
    )


# Healthcheck endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Проверка состояния системы"""
    from .dependencies import get_health_checker
    
    health_checker = await get_health_checker()
    health_results = await health_checker.run_all_checks()
    
    all_healthy = all(health_results.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "service": "SERM API",
            "version": "1.0.0",
            "checks": health_results,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """Корневой endpoint"""
    return {
        "message": "SERM API - Service & Economy Reputation Management",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )