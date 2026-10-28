"""
Главный файл FastAPI приложения SERM
с централизованной обработкой ошибок и enterprise-телеметрией
"""

import logging
import os
from asyncio import TimeoutError
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast

from fastapi import Depends, FastAPI, Request
from fastapi.security import HTTPBearer
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ExceptionHandler

from .core.audit_middleware import SecurityAuditMiddleware
from .core.database import engine, get_db
from .core.dependencies import (
    cleanup_dependencies,
    get_app_config,
    log_dependency_graph,
)
from .core.exceptions import SERMException
from .core.handlers import (
    general_exception_handler,
    http_exception_handler,
    serm_exception_handler,
    sqlalchemy_exception_handler,
    timeout_exception_handler,
    validation_exception_handler,
)
from .core.logger import configure_logging, get_logger
from .core.middleware import (
    CORRELATION_ID_HEADER,
    CorrelationIdMiddleware,
    PerformanceMiddleware,
    RequestLoggingMiddleware,
)
from .core.rate_limit import RateLimitDependency, add_rate_limit_headers
from .routers import (
    analytics,
    api_keys,
    auth,
    billing,
    companies,
    economics,
    external_api,
    parser,
    platforms,
    quotas,
    reputation,
    reviews,
    stripe_webhook,
    webhooks_config,
)
from .services.worker.worker import create_arq_pool

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
        service_name="serm-api",
    )

    global logger
    logger = get_logger(__name__)

    logger.info(
        "🚀 SERM API запускается...", service="serm-api", environment=environment
    )

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
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:
            logger.error(
                "PostgreSQL connection failed",
                database_driver=engine.url.drivername,
                error_type=type(exc).__name__,
            )
            raise RuntimeError(
                "Could not connect to the configured PostgreSQL database."
            ) from exc

        logger.info(
            "✅ Подключение к PostgreSQL установлено",
            database_driver=engine.url.drivername,
            connection="successful",
        )

        # Инициализация ARQ pool для отправки задач
        try:
            arq_pool = await create_arq_pool()
            app.state.arq_pool = arq_pool
            app.state.redis_pool = arq_pool
            logger.info(
                "✅ ARQ Redis pool инициализирован", component="arq", status="ready"
            )
        except Exception as e:
            logger.warning("⚠️ ARQ pool недоступен", component="arq", error=str(e))
            logger.warning("Фоновые задачи будут недоступны")
            app.state.arq_pool = None
            app.state.redis_pool = None

        logger.info("✅ Сервисы инициализированы", status="startup_complete")
        yield

    except Exception as e:
        logger.error(
            "❌ Ошибка инициализации", error=str(e), error_type=type(e).__name__
        )
        raise
    finally:
        # Очистка при остановке
        logger.info("🛑 SERM API завершает работу...", status="shutdown_initiated")

        # Закрываем ARQ pool
        if arq_pool:
            try:
                await arq_pool.close()
                logger.info("✅ ARQ pool закрыт", component="arq")
            except Exception as e:
                logger.error(
                    "❌ Ошибка закрытия ARQ pool", component="arq", error=str(e)
                )

        await cleanup_dependencies()
        logger.info("✅ Ресурсы очищены", status="shutdown_complete")


# Создание FastAPI приложения
app = FastAPI(
    title="SERM - Service & Economy Reputation Management",
    description="API для управления репутацией и расчета экономического влияния отзывов",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(RateLimitDependency())],
    # Отключаем автоматические docs в продакшене
    docs_url="/docs" if __debug__ else None,
    redoc_url="/redoc" if __debug__ else None,
)

app.state.redis_pool = None


# Настройка OpenAPI схемы безопасности для Swagger UI (Bearer Token)
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Добавляем схему безопасности Bearer Token
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Bearer Token (e.g., 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...')",
        }
    }
    # Применяем схему безопасности ко всем роутам (глобально)
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Enterprise Middleware Stack (порядок важен!)

# 1. Correlation ID Middleware (должен быть первым)
app.add_middleware(
    CorrelationIdMiddleware, header_name=CORRELATION_ID_HEADER, generate_if_missing=True
)
app.add_middleware(SecurityAuditMiddleware)

# 2. Performance Monitoring (после correlation ID)
app.add_middleware(
    PerformanceMiddleware,
    slow_request_threshold=2.0,  # 2 секунды для SERM API
    log_slow_requests=True,
)

# 3. Request Logging (в development режиме)
if debug_mode:
    app.add_middleware(
        RequestLoggingMiddleware,
        log_request_body=False,
        log_response_body=False,  # Может быть большим для аналитики
        log_headers=False,
    )

# 3.5. Rate Limit Headers (автоматическое добавление X-RateLimit-* заголовков)
app.middleware("http")(add_rate_limit_headers)

# CORS origins may be provided as a comma-separated FRONTEND_URL value.
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").strip()
allowed_origins = [
    origin.strip() for origin in frontend_url.split(",") if origin.strip()
] or ["http://localhost:3000"]

# 4. CORS (после всех custom middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-Correlation-ID"],
)


# Подключение глобальных обработчиков исключений
app.add_exception_handler(SERMException, cast(ExceptionHandler, serm_exception_handler))
app.add_exception_handler(HTTPException, cast(ExceptionHandler, http_exception_handler))
app.add_exception_handler(
    RequestValidationError, cast(ExceptionHandler, validation_exception_handler)
)
app.add_exception_handler(
    SQLAlchemyError, cast(ExceptionHandler, sqlalchemy_exception_handler)
)
app.add_exception_handler(
    TimeoutError, cast(ExceptionHandler, timeout_exception_handler)
)
app.add_exception_handler(Exception, cast(ExceptionHandler, general_exception_handler))


# Подключение роутеров
app.include_router(economics.router, prefix="/api/v1/economics", tags=["Economics"])

# Auth router (должен быть первым для документации)
app.include_router(auth.router, tags=["Authentication"])

app.include_router(api_keys.router)

app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Reviews"])

app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])

app.include_router(platforms.router, prefix="/api/v1/platforms", tags=["Platforms"])

# Подключаем parser router с LLM-аналитикой
app.include_router(parser.router)

# Подключаем analytics router
app.include_router(analytics.router, tags=["Analytics"])
app.include_router(reputation.router)

# Подключаем quotas router для биллинга
app.include_router(quotas.router, tags=["Quotas & Billing"])

# Подключаем billing router для Stripe интеграции
app.include_router(billing.router, prefix="/api/v1", tags=["Billing & Stripe"])

# Подключаем stripe webhook router
app.include_router(stripe_webhook.router, prefix="/api/v1", tags=["Stripe Webhooks"])

# Подключаем external API router для B2B клиентов
app.include_router(external_api.router, tags=["External API"])
app.include_router(webhooks_config.router, tags=["Webhooks"])

# Системные роутеры (только для разработки и тестирования)
if __debug__:
    from .routers import system

    app.include_router(system.router, prefix="/api/v1/system", tags=["System"])


# Healthcheck endpoint
@app.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Проверка состояния системы"""
    from .core.dependencies import get_health_checker

    health_checker = await get_health_checker()
    health_results = await health_checker.run_all_checks(db)

    all_healthy = all(health_results.values())
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "service": "SERM API",
            "version": "1.0.0",
            "checks": health_results,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.get("/health/redis", tags=["System"])
async def redis_health_check(request: Request) -> JSONResponse:
    """Проверяет доступность Redis через тот же ARQ pool, что использует API."""
    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "check": "redis"},
        )

    try:
        await arq_pool.ping()
    except RedisError:
        logging.getLogger(__name__).warning("Redis health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "check": "redis"},
        )

    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "check": "redis"},
    )


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """Корневой endpoint"""
    return {
        "message": "SERM API - Service & Economy Reputation Management",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
