"""
Dependency Injection для FastAPI
Фабрики репозиториев и сервисов для трехслойной архитектуры SERM с мультитенантностью
"""

from typing import AsyncGenerator
from functools import lru_cache
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .auth import AuthContext, JWTHandler
from .auth.jwt_handler import get_jwt_handler
from .auth.tenant_session import get_db_with_tenant
from .repositories import CompanyRepository, PlatformRepository, ReviewRepository, ParserRepository
from .services import EconomicsService, LLMService, SentimentService, ReviewProcessorService, ParserService

logger = logging.getLogger(__name__)
security = HTTPBearer()


# === AUTHENTICATION DEPENDENCIES ===

async def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    jwt_handler: JWTHandler = Depends(get_jwt_handler)
) -> AuthContext:
    """
    Извлечение и проверка JWT токена, получение контекста аутентификации
    """
    try:
        token = credentials.credentials
        auth_context = await jwt_handler.verify_token(token)
        
        logger.info(f"User authenticated: {auth_context.user_id}, company: {auth_context.company_id}")
        return auth_context
        
    except ValueError as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Ошибка аутентификации: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка аутентификации"
        )


# === TENANT-AWARE DATABASE DEPENDENCIES ===

async def get_tenant_db(
    auth_context: AuthContext = Depends(get_auth_context)
) -> AsyncGenerator[AsyncSession, None]:
    """
    Получение БД сессии с установленным tenant context для RLS
    """
    async for session in get_db_with_tenant(auth_context):
        yield session


# === REPOSITORY DEPENDENCIES ===

async def get_company_repository(
    db: AsyncSession = Depends(get_tenant_db)
) -> CompanyRepository:
    """Фабрика для CompanyRepository с tenant изоляцией"""
    return CompanyRepository(db)


async def get_platform_repository(
    db: AsyncSession = Depends(get_tenant_db)  
) -> PlatformRepository:
    """Фабрика для PlatformRepository с tenant изоляцией"""
    return PlatformRepository(db)


async def get_parser_repository(
    db: AsyncSession = Depends(get_tenant_db)
) -> ParserRepository:
    """Фабрика для ParserRepository с tenant изоляцией"""
    return ParserRepository(db)


async def get_review_repository(
    db: AsyncSession = Depends(get_tenant_db)
) -> ReviewRepository:
    """Фабрика для ReviewRepository с tenant изоляцией"""
    return ReviewRepository(db)


# === SERVICE DEPENDENCIES ===

async def get_economics_service(
    company_repo: CompanyRepository = Depends(get_company_repository),
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> EconomicsService:
    """Фабрика для EconomicsService"""
    return EconomicsService(company_repo, platform_repo)


@lru_cache()
def get_llm_service_singleton() -> LLMService:
    """Синглтон для LLMService (переиспользуем Gemini клиент)"""
    return LLMService()


async def get_llm_service() -> LLMService:
    """Фабрика для LLMService"""
    return get_llm_service_singleton()


@lru_cache()
def get_sentiment_service_singleton() -> SentimentService:
    """Синглтон для SentimentService (без состояния)"""
    return SentimentService()


async def get_sentiment_service() -> SentimentService:
    """Фабрика для SentimentService"""
    return get_sentiment_service_singleton()


async def get_parser_service(
    review_repo: ReviewRepository = Depends(get_review_repository),
    platform_repo: PlatformRepository = Depends(get_platform_repository),
    company_repo: CompanyRepository = Depends(get_company_repository)
) -> ParserService:
    """Фабрика для ParserService"""
    return ParserService(review_repo, platform_repo, company_repo)


async def get_review_processor_service(
    review_repo: ReviewRepository = Depends(get_review_repository),
    platform_repo: PlatformRepository = Depends(get_platform_repository), 
    company_repo: CompanyRepository = Depends(get_company_repository),
    economics_service: EconomicsService = Depends(get_economics_service),
    llm_service: LLMService = Depends(get_llm_service),
    sentiment_service: SentimentService = Depends(get_sentiment_service),
    auth_context: AuthContext = Depends(get_auth_context)
) -> ReviewProcessorService:
    """Фабрика для ReviewProcessorService с tenant context"""
    return ReviewProcessorService(
        review_repo, platform_repo, company_repo,
        economics_service, llm_service, sentiment_service,
        auth_context  # Передаем контекст для автозаполнения company_id
    )


# === COMBINED DEPENDENCIES ===

class RepositoryBundle:
    """Бандл всех репозиториев для удобства"""
    
    def __init__(self,
                 companies: CompanyRepository,
                 platforms: PlatformRepository, 
                 reviews: ReviewRepository,
                 auth_context: AuthContext):
        self.companies = companies
        self.platforms = platforms
        self.reviews = reviews
        self.auth_context = auth_context
    
    def get_all(self) -> tuple[CompanyRepository, PlatformRepository, ReviewRepository]:
        """Получить все репозитории как кортеж"""
        return self.companies, self.platforms, self.reviews


async def get_repository_bundle(
    companies: CompanyRepository = Depends(get_company_repository),
    platforms: PlatformRepository = Depends(get_platform_repository),
    reviews: ReviewRepository = Depends(get_review_repository),
    auth_context: AuthContext = Depends(get_auth_context)
) -> RepositoryBundle:
    """Получить все репозитории одним вызовом с tenant context"""
    return RepositoryBundle(companies, platforms, reviews, auth_context)


class ServiceBundle:
    """Бандл всех сервисов для удобства"""
    
    def __init__(self,
                 economics: EconomicsService,
                 llm: LLMService,
                 sentiment: SentimentService,
                 review_processor: ReviewProcessorService,
                 auth_context: AuthContext):
        self.economics = economics
        self.llm = llm
        self.sentiment = sentiment
        self.review_processor = review_processor
        self.auth_context = auth_context
    
    def get_all(self) -> tuple[EconomicsService, LLMService, SentimentService, ReviewProcessorService]:
        """Получить все сервисы как кортеж"""
        return self.economics, self.llm, self.sentiment, self.review_processor


async def get_service_bundle(
    economics: EconomicsService = Depends(get_economics_service),
    llm: LLMService = Depends(get_llm_service),
    sentiment: SentimentService = Depends(get_sentiment_service),
    review_processor: ReviewProcessorService = Depends(get_review_processor_service),
    auth_context: AuthContext = Depends(get_auth_context)
) -> ServiceBundle:
    """Получить все сервисы одним вызовом с tenant context"""
    return ServiceBundle(economics, llm, sentiment, review_processor, auth_context)


# === HEALTH CHECK DEPENDENCIES ===

class HealthChecker:
    """Проверка состояния зависимостей"""
    
    def __init__(self):
        self.checks = []
    
    async def check_database(self, db: AsyncSession = Depends(get_db)) -> bool:
        """Проверка подключения к базе данных"""
        try:
            await db.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def check_llm_service(self, llm: LLMService = Depends(get_llm_service)) -> bool:
        """Проверка доступности LLM сервиса"""
        try:
            return llm.validate_api_connection()
        except Exception as e:
            logger.error(f"LLM service health check failed: {e}")
            return False
    
    async def check_jwt_handler(self, jwt_handler: JWTHandler = Depends(get_jwt_handler)) -> bool:
        """Проверка JWT handler (JWKS доступность)"""
        try:
            # Простая проверка настроек
            return bool(jwt_handler.settings.jwks_url or jwt_handler.settings.jwt_secret)
        except Exception as e:
            logger.error(f"JWT handler check failed: {e}")
            return False
    
    async def run_all_checks(self,
                           db: AsyncSession = Depends(get_db),
                           llm: LLMService = Depends(get_llm_service),
                           jwt_handler: JWTHandler = Depends(get_jwt_handler)) -> dict[str, bool]:
        """Запуск всех проверок состояния"""
        results = {}
        
        try:
            results["database"] = await self.check_database(db)
        except Exception as e:
            logger.error(f"Database check error: {e}")
            results["database"] = False
        
        try:
            results["llm_service"] = await self.check_llm_service(llm)
        except Exception as e:
            logger.error(f"LLM service check error: {e}")
            results["llm_service"] = False
        
        try:
            results["jwt_handler"] = await self.check_jwt_handler(jwt_handler)
        except Exception as e:
            logger.error(f"JWT handler check error: {e}")
            results["jwt_handler"] = False
        
        return results


async def get_health_checker() -> HealthChecker:
    """Фабрика для HealthChecker"""
    return HealthChecker()


# === CONFIGURATION DEPENDENCIES ===

class AppConfig:
    """Конфигурация приложения"""
    
    def __init__(self):
        import os
        
        # Database
        self.database_url = os.getenv("DATABASE_URL")
        
        # Google Gemini API
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
        # Authentication
        self.auth_jwt_secret = os.getenv("AUTH_JWT_SECRET")
        self.auth_jwks_url = os.getenv("AUTH_JWKS_URL")
        self.auth_jwt_algorithm = os.getenv("AUTH_JWT_ALGORITHM", "RS256")
        
        # Application settings
        self.debug_mode = os.getenv("DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # SERM specific
        self.default_lost_leads_coefficient = int(os.getenv("DEFAULT_LOST_LEADS_COEFFICIENT", "5"))
        self.default_positive_boost_coefficient = float(os.getenv("DEFAULT_POSITIVE_BOOST_COEFFICIENT", "0.5"))
    
    def validate(self) -> list[str]:
        """Валидация конфигурации"""
        errors = []
        
        if not self.database_url:
            errors.append("DATABASE_URL not configured")
        
        if not self.gemini_api_key:
            errors.append("GEMINI_API_KEY not configured")
        
        # Проверка auth настроек
        if self.auth_jwt_algorithm == "RS256" and not self.auth_jwks_url:
            errors.append("AUTH_JWKS_URL required for RS256 algorithm")
        
        if self.auth_jwt_algorithm == "HS256" and not self.auth_jwt_secret:
            errors.append("AUTH_JWT_SECRET required for HS256 algorithm")
        
        return errors
    
    def is_valid(self) -> bool:
        """Проверка валидности конфигурации"""
        return len(self.validate()) == 0


@lru_cache()
def get_app_config() -> AppConfig:
    """Синглтон конфигурации приложения"""
    config = AppConfig()
    
    # Логируем ошибки конфигурации
    errors = config.validate()
    if errors:
        for error in errors:
            logger.warning(f"Configuration warning: {error}")
    
    return config


# === UTILITY FUNCTIONS ===

async def cleanup_dependencies():
    """Очистка ресурсов при завершении приложения"""
    try:
        # Очищаем кэш синглтонов
        get_llm_service_singleton.cache_clear()
        get_sentiment_service_singleton.cache_clear()
        get_app_config.cache_clear()
        
        logger.info("Dependencies cleanup completed")
    except Exception as e:
        logger.error(f"Error during dependencies cleanup: {e}")


def log_dependency_graph():
    """Логирование графа зависимостей для отладки"""
    logger.info("=== DEPENDENCY GRAPH (Multi-tenant) ===")
    logger.info("Authentication: JWT -> AuthContext -> TenantSession")
    logger.info("Repositories: Company, Platform, Review (with RLS)")
    logger.info("Services: Economics, LLM, Sentiment, ReviewProcessor")
    logger.info("Singletons: LLMService, SentimentService, AppConfig")
    logger.info("Bundles: RepositoryBundle, ServiceBundle")
    logger.info("Health: HealthChecker + JWT")
    logger.info("=========================================")