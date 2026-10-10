"""
Сервис парсинга отзывов для фоновых задач ARQ
Включает LLM-аналитику: тональность, теги, генерация ответов
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID

from ..repositories import ReviewRepository, PlatformRepository, CompanyRepository
from .review_processor import ReviewProcessorService
from ..schemas.economics import ReviewBase, ReviewStatus
from ..exceptions import BusinessLogicError, NotFoundError, ValidationError


logger = logging.getLogger(__name__)


class ParserService:
    """Сервис для обработки данных парсинга отзывов в фоновых задачах с LLM-аналитикой"""
    
    def __init__(self,
                 review_repo: ReviewRepository,
                 platform_repo: PlatformRepository,
                 company_repo: CompanyRepository,
                 review_processor: ReviewProcessorService):
        self.review_repo = review_repo
        self.platform_repo = platform_repo
        self.company_repo = company_repo
        self.review_processor = review_processor
    
    async def process_parsed_reviews(self, 
                                   platform_url: str,
                                   company_id: UUID,
                                   parsed_reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Обработка спарсенных отзывов из фоновой задачи
        
        Args:
            platform_url: URL платформы для парсинга
            company_id: ID компании (для tenant isolation)
            parsed_reviews: Список спарсенных отзывов
            
        Returns:
            Результат обработки с статистикой
        """
        logger.info(f"Processing {len(parsed_reviews)} parsed reviews for company {company_id}")
        
        try:
            # Находим платформу по URL
            platform = await self.platform_repo.get_by_url(platform_url)
            if not platform:
                raise NotFoundError("Платформа", platform_url)
            
            # Проверяем что платформа принадлежит компании
            if platform.company_id != company_id:
                raise ValidationError(f"Платформа не принадлежит компании {company_id}")
            
            results = {
                "platform_url": platform_url,
                "platform_name": platform.name,
                "company_id": str(company_id),
                "processed_reviews": [],
                "failed_reviews": [],
                "duplicates": [],
                "statistics": {
                    "total_parsed": len(parsed_reviews),
                    "processed": 0,
                    "duplicates": 0,
                    "failed": 0,
                    "new_reviews": 0,
                    "total_financial_impact": 0.0
                }
            }
            
            for review_data in parsed_reviews:
                try:
                    # 1. LLM-анализ отзыва ПЕРЕД обработкой
                    analytics = await self._analyze_review_with_llm(review_data, platform.name)
                    
                    # 2. Валидируем и преобразуем данные отзыва
                    review_base = self._validate_parsed_review(review_data, platform.id)
                    
                    # 3. Обрабатываем отзыв через основной процессор с LLM-данными
                    processed_result = await self.review_processor.process_new_review_with_analytics(
                        review_base, analytics
                    )
                    
                    if processed_result.get("duplicate"):
                        results["duplicates"].append({
                            "external_id": review_data.get("external_id"),
                            "existing_review_id": processed_result.get("review_id"),
                            "message": processed_result.get("message")
                        })
                        results["statistics"]["duplicates"] += 1
                    else:
                        # Добавляем LLM-данные в результат
                        processed_result["llm_analytics"] = {
                            "sentiment": analytics.sentiment,
                            "tags": analytics.tags,
                            "has_suggested_reply": analytics.suggested_reply is not None
                        }
                        
                        results["processed_reviews"].append(processed_result)
                        results["statistics"]["processed"] += 1
                        results["statistics"]["new_reviews"] += 1
                        
                        # Добавляем к общему финансовому влиянию
                        financial_impact = processed_result.get("financial_impact", {})
                        impact_value = financial_impact.get("financial_impact", 0.0)
                        results["statistics"]["total_financial_impact"] += impact_value
                
                except Exception as e:
                    logger.error(f"Failed to process review {review_data.get('external_id', 'unknown')}: {str(e)}")
                    results["failed_reviews"].append({
                        "review_data": review_data,
                        "error": str(e)
                    })
                    results["statistics"]["failed"] += 1
            
            # Обновляем средний рейтинг платформы после обработки всех отзывов
            if results["statistics"]["new_reviews"] > 0:
                await self.platform_repo.update_rating(platform.id)
            
            logger.info(f"Completed processing: {results['statistics']['processed']} processed, "
                       f"{results['statistics']['duplicates']} duplicates, "
                       f"{results['statistics']['failed']} failed")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing parsed reviews for platform {platform_url}: {str(e)}")
            if isinstance(e, (NotFoundError, ValidationError, BusinessLogicError)):
                raise
            raise BusinessLogicError(f"Ошибка обработки спарсенных отзывов: {str(e)}")
    
    def _validate_parsed_review(self, review_data: Dict[str, Any], platform_id: UUID) -> ReviewBase:
        """
        Валидация и преобразование спарсенных данных отзыва в ReviewBase
        
        Args:
            review_data: Сырые данные отзыва от парсера
            platform_id: ID платформы
            
        Returns:
            Валидированный объект ReviewBase
        """
        try:
            # Обязательные поля
            required_fields = ["rating", "text", "author_name"]
            missing_fields = [field for field in required_fields if not review_data.get(field)]
            
            if missing_fields:
                raise ValidationError(f"Отсутствуют обязательные поля: {', '.join(missing_fields)}")
            
            # Валидация рейтинга
            rating = review_data.get("rating")
            if not isinstance(rating, (int, float)) or not (1 <= rating <= 5):
                raise ValidationError(f"Рейтинг должен быть числом от 1 до 5, получено: {rating}")
            
            # Валидация текста
            text = review_data.get("text", "").strip()
            if len(text) < 10:
                raise ValidationError("Текст отзыва слишком короткий (минимум 10 символов)")
            
            # Валидация имени автора
            author_name = review_data.get("author_name", "").strip()
            if len(author_name) < 2:
                raise ValidationError("Имя автора слишком короткое (минимум 2 символа)")
            
            # Создаем объект ReviewBase
            return ReviewBase(
                platform_id=platform_id,
                author_name=author_name,
                rating=int(rating),  # Приводим к int для консистентности
                text=text,
                external_review_id=review_data.get("external_id"),  # Может быть None
                status=ReviewStatus.NEW  # Новые отзывы всегда начинают со статуса NEW
            )
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Ошибка валидации данных отзыва: {str(e)}")
    
    async def get_parsing_statistics(self, company_id: UUID, days: int = 30) -> Dict[str, Any]:
        """
        Получение статистики парсинга для компании за указанный период
        
        Args:
            company_id: ID компании
            days: Количество дней для анализа (по умолчанию 30)
            
        Returns:
            Статистика парсинга
        """
        try:
            # Получаем все платформы компании
            platforms = await self.platform_repo.get_by_company_id(company_id)
            
            statistics = {
                "company_id": str(company_id),
                "period_days": days,
                "platforms": [],
                "totals": {
                    "platforms_count": len(platforms),
                    "total_reviews": 0,
                    "new_reviews_last_period": 0,
                    "average_rating": 0.0,
                    "total_financial_impact": 0.0
                }
            }
            
            total_rating_sum = 0
            total_reviews_count = 0
            
            for platform in platforms:
                # Получаем статистику по платформе
                platform_stats = await self.review_repo.get_platform_statistics(
                    platform_id=platform.id,
                    days=days
                )
                
                platform_info = {
                    "platform_id": str(platform.id),
                    "platform_name": platform.name,
                    "platform_url": platform.platform_url,
                    "total_reviews": platform_stats["total_reviews"],
                    "new_reviews_last_period": platform_stats["new_reviews_count"],
                    "average_rating": platform_stats["average_rating"],
                    "financial_impact_last_period": platform_stats["financial_impact"]
                }
                
                statistics["platforms"].append(platform_info)
                
                # Обновляем общие показатели
                statistics["totals"]["total_reviews"] += platform_stats["total_reviews"]
                statistics["totals"]["new_reviews_last_period"] += platform_stats["new_reviews_count"]
                statistics["totals"]["total_financial_impact"] += platform_stats["financial_impact"]
                
                # Для расчета средневзвешенного рейтинга
                if platform_stats["total_reviews"] > 0:
                    total_rating_sum += platform_stats["average_rating"] * platform_stats["total_reviews"]
                    total_reviews_count += platform_stats["total_reviews"]
            
            # Рассчитываем общий средний рейтинг
            if total_reviews_count > 0:
                statistics["totals"]["average_rating"] = round(total_rating_sum / total_reviews_count, 2)
            
            return statistics
            
        except Exception as e:
            logger.error(f"Error getting parsing statistics for company {company_id}: {str(e)}")
            raise BusinessLogicError(f"Ошибка получения статистики парсинга: {str(e)}")
    
    async def schedule_platform_parsing(self, 
                                      platform_id: UUID, 
                                      company_id: UUID,
                                      priority: str = "normal") -> Dict[str, Any]:
        """
        Планирование парсинга для конкретной платформы
        
        Args:
            platform_id: ID платформы
            company_id: ID компании (для проверки доступа)
            priority: Приоритет задачи ("high", "normal", "low")
            
        Returns:
            Информация о запланированной задаче
        """
        try:
            # Проверяем существование платформы и доступ
            platform = await self.platform_repo.get_by_id(platform_id)
            if not platform:
                raise NotFoundError("Платформа", str(platform_id))
            
            if platform.company_id != company_id:
                raise ValidationError(f"Платформа не принадлежит компании {company_id}")
            
            # Здесь бы отправлялась задача в ARQ, но для демонстрации возвращаем информацию
            return {
                "platform_id": str(platform_id),
                "platform_name": platform.name,
                "platform_url": platform.platform_url,
                "company_id": str(company_id),
                "priority": priority,
                "status": "scheduled",
                "message": f"Парсинг платформы {platform.name} запланирован с приоритетом {priority}"
            }
            
        except Exception as e:
            logger.error(f"Error scheduling parsing for platform {platform_id}: {str(e)}")
            if isinstance(e, (NotFoundError, ValidationError)):
                raise
            raise BusinessLogicError(f"Ошибка планирования парсинга: {str(e)}")