"""
Dependency Injection для FastAPI
Фабрики репозиториев и сервисов для трехслойной архитектуры SERM с мультитенантностью
"""

from typing import AsyncGenerator
from functools import lru_cache
import logging
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .core.auth import get_current_tenant, CurrentTenant, CurrentPayload
from .db.session import get_tenant_session
from .repositories import CompanyRepository, PlatformRepository, ReviewRepository, ParserRepository
from .services import EconomicsService, LLMService, SentimentService, ReviewProcessorService, ParserService
from .schemas.auth import JWTPayload

logger = logging.getLogger(__name__)


# === TENANT-AWARE DATABASE DEPENDENCIES ===

async def get_tenant_db(
    tenant_id: UUID = Depends(get_current_tenant),
    db_factory: AsyncSession = Depends(get_db)
) -> AsyncSession:
    """
    Получение БД сессии с установленным tenant context для RLS
    """
    # Создаем фабрику для get_tenant_session
    def session_factory():
        return db_factory
    
    return await get_tenant_session(session_factory, tenant_id)


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
    tenant_id: UUID = Depends(get_current_tenant)
) -> ReviewProcessorService:
    """Фабрика для ReviewProcessorService с tenant context"""
    return ReviewProcessorService(
        review_repo, platform_repo, company_repo,
        economics_service, llm_service, sentiment_service,
        tenant_id  # Передаем tenant_id для автозаполнения company_id
    )


# === COMBINED DEPENDENCIES ===

class RepositoryBundle:
    """Бандл всех репозиториев для удобства"""
    
    def __init__(self,
                 companies: CompanyRepository,
                 platforms: PlatformRepository, 
                 reviews: ReviewRepository,
                 tenant_id: UUID):
        self.companies = companies
        self.platforms = platforms
        self.reviews = reviews
        self.tenant_id = tenant_id
    
    def get_all(self) -> tuple[CompanyRepository, PlatformRepository, ReviewRepository]:
        """Получить все репозитории как кортеж"""
        return self.companies, self.platforms, self.reviews


async def get_repository_bundle(
    companies: CompanyRepository = Depends(get_company_repository),
    platforms: PlatformRepository = Depends(get_platform_repository),
    reviews: ReviewRepository = Depends(get_review_repository),
    tenant_id: UUID = Depends(get_current_tenant)
) -> RepositoryBundle:
    """Получить все репозитории одним вызовом с tenant context"""
    return RepositoryBundle(companies, platforms, reviews, tenant_id)


class ServiceBundle:
    """Бандл всех сервисов для удобства"""
    
    def __init__(self,
                 economics: EconomicsService,
                 llm: LLMService,
                 sentiment: SentimentService,
                 review_processor: ReviewProcessorService,
                 tenant_id: UUID):
        self.economics = economics
        self.llm = llm
        self.sentiment = sentiment
        self.review_processor = review_processor
        self.tenant_id = tenant_id
    
    def get_all(self) -> tuple[EconomicsService, LLMService, SentimentService, ReviewProcessorService]:
        """Получить все сервисы как кортеж"""
        return self.economics, self.llm, self.sentiment, self.review_processor


async def get_service_bundle(
    economics: EconomicsService = Depends(get_economics_service),
    llm: LLMService = Depends(get_llm_service),
    sentiment: SentimentService = Depends(get_sentiment_service),
    review_processor: ReviewProcessorService = Depends(get_review_processor_service),
    tenant_id: UUID = Depends(get_current_tenant)
) -> ServiceBundle:
    """Получить все сервисы одним вызовом с tenant context"""
    return ServiceBundle(economics, llm, sentiment, review_processor, tenant_id)


# === HEALTH CHECK DEPENDENCIES ===

class HealthChecker:
    """Проверка состояния зависимостей"""
    
    def __init__(self):
        self.checks = []
    
    async def check_database(self, db: AsyncSession = Depends(get_db)) -> bool:
        """Проверка подключения к базе данных"""
        try:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def check_llm_service(self, llm: LLMService = Depends(get_llm_service)) -> bool:
        """Проверка доступности LLM сервиса"""
        try:
            # Простая проверка существования сервиса
            return llm is not None
        except Exception as e:
            logger.error(f"LLM service health check failed: {e}")
            return False
    
    async def check_auth_config(self) -> bool:
        """Проверка настроек аутентификации"""
        try:
            from .core.auth import get_auth_config
            config = get_auth_config()
            return bool(config.secret)
        except Exception as e:
            logger.error(f"Auth config check failed: {e}")
            return False
    
    async def run_all_checks(self, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
        """Запуск всех проверок состояния"""
        results = {}
        
        try:
            results["database"] = await self.check_database(db)
        except Exception as e:
            logger.error(f"Database check error: {e}")
            results["database"] = False
        
        try:
            llm = await get_llm_service()
            results["llm_service"] = await self.check_llm_service(llm)
        except Exception as e:
            logger.error(f"LLM service check error: {e}")
            results["llm_service"] = False
        
        try:
            results["auth_config"] = await self.check_auth_config()
        except Exception as e:
            logger.error(f"Auth config check error: {e}")
            results["auth_config"] = False
        
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
        self.supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        self.jwt_audience = os.getenv("JWT_AUDIENCE", "authenticated")
        
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
        
        if not self.supabase_jwt_secret:
            errors.append("SUPABASE_JWT_SECRET not configured")
        
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
    logger.info("=== DEPENDENCY GRAPH (Multi-tenant with RLS) ===")
    logger.info("Authentication: JWT -> JWTPayload -> tenant_id")
    logger.info("Database: get_tenant_db -> RLS Context -> AsyncSession")
    logger.info("Repositories: Company, Platform, Review, Parser (with RLS)")
    logger.info("Services: Economics, LLM, Sentiment, ReviewProcessor, Parser")
    logger.info("Singletons: LLMService, SentimentService, AppConfig")
    logger.info("Bundles: RepositoryBundle, ServiceBundle (with tenant_id)")
    logger.info("Health: HealthChecker + Auth + LLM + Database")
    logger.info("===============================================")