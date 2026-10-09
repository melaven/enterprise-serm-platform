"""
ARQ фоновые задачи для парсинга отзывов
Сохраняет мультитенантность через RLS
"""

import logging
from typing import Dict, Any
from uuid import UUID

from arq import Retry

from ..db.tenant import tenant_session_factory
from ..repositories import ParserRepository, PlatformRepository, CompanyRepository, ReviewRepository
from ..services.parser import ParserService
from ..services.economics import EconomicsService
from ..services.llm import LLMService
from ..services.sentiment import SentimentService
from ..services.review_processor import ReviewProcessorService

logger = logging.getLogger(__name__)


async def fetch_reviews_task(ctx: dict, platform_url: str, company_id: str) -> Dict[str, Any]:
    """
    Фоновая задача парсинга отзывов для конкретной платформы
    
    Args:
        ctx: Контекст ARQ (job_id, и т.д.)
        platform_url: URL платформы для парсинга
        company_id: UUID компании в виде строки (для RLS)
        
    Returns:
        Словарь с результатами парсинга (количество обработанных, дубликатов, ошибок)
    """
    
    job_id = ctx.get('job_id', 'unknown')
    logger.info(f"🔄 Starting fetch_reviews_task: job_id={job_id}, platform_url={platform_url}, company_id={company_id}")
    
    try:
        # Шаг 1: Симуляция парсинга (в реальности здесь был бы внешний парсер)
        # TODO: Заменить на реальный парсер отзывов
        simulated_reviews = [
            {
                "external_id": f"sim_review_{i}_{job_id}",
                "author_name": f"Test User {i}",
                "rating": 4 if i % 2 == 0 else 3,
                "text": f"Тестовый отзыв {i} спарсен задачей {job_id}. Это симуляция парсинга.",
            }
            for i in range(1, 4)  # Создаем 3 тестовых отзыва
        ]
        
        logger.info(f"📊 Simulated parsing of {len(simulated_reviews)} reviews from {platform_url}")
        
        if not simulated_reviews:
            logger.info("✅ No reviews found - task completed")
            return {"parsed": 0, "processed": 0, "duplicates": 0, "failed": 0}
        
        # Шаг 2: Обработка через ParserService с tenant изоляцией
        company_uuid = UUID(company_id)
        
        # Используем tenant_session для RLS изоляции
        async with tenant_session_factory() as session_factory:
            async with session_factory(company_uuid) as session:
                
                # Инициализируем репозитории и сервисы
                parser_repo = ParserRepository(session)
                platform_repo = PlatformRepository(session) 
                company_repo = CompanyRepository(session)
                review_repo = ReviewRepository(session)
                
                # Инициализируем сервисы
                economics_service = EconomicsService(company_repo, platform_repo)
                llm_service = LLMService()
                sentiment_service = SentimentService()
                
                review_processor = ReviewProcessorService(
                    review_repo, platform_repo, company_repo,
                    economics_service, llm_service, sentiment_service
                )
                
                parser_service = ParserService(
                    review_repo, platform_repo, company_repo, review_processor
                )
                
                # Обработка спарсенных отзывов
                result = await parser_service.process_parsed_reviews(
                    platform_url=platform_url,
                    company_id=company_uuid,
                    parsed_reviews=simulated_reviews
                )
                
                await session.commit()
                
                logger.info(
                    f"✅ Task completed with LLM analytics: {result['statistics']['processed']} processed, "
                    f"{result['statistics']['duplicates']} duplicates, "
                    f"{result['statistics']['failed']} failed"
                )
                
                return {
                    "job_id": job_id,
                    "platform_url": platform_url,
                    "company_id": company_id,
                    "parsed": len(simulated_reviews),
                    "processed": result['statistics']['processed'],
                    "duplicates": result['statistics']['duplicates'], 
                    "failed": result['statistics']['failed'],
                    "total_financial_impact": result['statistics']['total_financial_impact']
                }
        
    except Exception as e:
        # Проверяем на транзиентные ошибки для retry
        if any(keyword in str(e).lower() for keyword in ["timeout", "connection", "network"]):
            logger.warning(f"⚠️ Transient error in task {job_id}: {e}")
            raise Retry(defer=30) from e  # Повтор через 30 секунд
        else:
            logger.error(f"❌ Permanent error in task {job_id}: {e}")
            raise Exception(f"Task failed: {e}") from e