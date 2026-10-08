"""
Центральный сервис обработки отзывов - координирует все операции
"""

from typing import Dict, Any, Optional
from uuid import UUID

from ..repositories import ReviewRepository, PlatformRepository, CompanyRepository
from .economics import EconomicsService
from .llm import LLMService  
from .sentiment import SentimentService
from ..schemas.economics import ReviewStatus, ReviewBase
from ..exceptions import BusinessLogicError, NotFoundError


class ReviewProcessorService:
    """Центральный сервис обработки отзывов"""
    
    def __init__(self,
                 review_repo: ReviewRepository,
                 platform_repo: PlatformRepository,
                 company_repo: CompanyRepository,
                 economics_service: EconomicsService,
                 llm_service: LLMService,
                 sentiment_service: SentimentService,
                 auth_context: "AuthContext" = None):
        self.review_repo = review_repo
        self.platform_repo = platform_repo  
        self.company_repo = company_repo
        self.economics_service = economics_service
        self.llm_service = llm_service
        self.sentiment_service = sentiment_service
        self.auth_context = auth_context
    
    async def process_new_review(self, review_data: ReviewBase) -> Dict[str, Any]:
        """
        Полная обработка нового отзыва:
        1. Проверка на дубликаты (по external_review_id)
        2. Анализ тональности
        3. Расчет финансового влияния
        4. Генерация ответа (для негативных)
        5. Сохранение в БД
        """
        try:
            # 1. Проверяем на дубликаты по внешнему ID (если указан)
            if review_data.external_review_id:
                existing_review = await self.review_repo.get_by_external_id(review_data.external_review_id)
                if existing_review:
                    return {
                        "status": "duplicate",
                        "message": "Отзыв уже существует в системе",
                        "review_id": str(existing_review.id),
                        "external_review_id": review_data.external_review_id,
                        "duplicate": True
                    }
            
            # 2. Проверяем существование платформы
            platform = await self.platform_repo.get_with_reviews(review_data.platform_id)
            if not platform:
                raise NotFoundError("Платформа", str(review_data.platform_id))
            
            company = platform.company
            
            # 3. Анализ тональности
            sentiment_analysis = self.sentiment_service.analyze_sentiment(
                rating=review_data.rating,
                review_text=review_data.text
            )
            
            # 4. Расчет финансового влияния
            financial_impact_data = await self.economics_service.calculate_review_financial_impact(
                platform_id=review_data.platform_id,
                rating=review_data.rating,
                status=review_data.status
            )
            
            # 5. Определяем нужно ли генерировать ответ
            should_generate_response = (
                review_data.rating <= 3 and 
                sentiment_analysis["priority"] in ["critical", "high"]
            )
            
            generated_response = None
            updated_status = review_data.status
            
            if should_generate_response:
                try:
                    # Генерируем ответ через LLM
                    generated_response = await self.llm_service.generate_review_response(
                        review_text=review_data.text,
                        rating=review_data.rating,
                        author_name=review_data.author_name,
                        company_name=company.name
                    )
                    updated_status = ReviewStatus.SI_PROCESSING
                    
                    # Пересчитываем финансовое влияние с учетом генерации ответа
                    if generated_response:
                        updated_status = ReviewStatus.RESOLVED
                        financial_impact_data = await self.economics_service.calculate_review_financial_impact(
                            platform_id=review_data.platform_id,
                            rating=review_data.rating,
                            status=ReviewStatus.RESOLVED
                        )
                
                except Exception as e:
                    # Если генерация не удалась, продолжаем без ответа
                    generated_response = None
                    updated_status = ReviewStatus.NEW
            
            # 6. Создаем отзыв в БД
            created_review = await self.review_repo.create(
                platform_id=review_data.platform_id,
                author_name=review_data.author_name,
                rating=review_data.rating,
                text=review_data.text,
                external_review_id=review_data.external_review_id,  # Добавляем внешний ID
                company_id=self.auth_context.company_id if self.auth_context else review_data.platform_id,  # Автозаполнение tenant
                status=updated_status,
                financial_impact=financial_impact_data["financial_impact"],
                si_response=generated_response
            )
            
            # 7. Обновляем средний рейтинг платформы
            await self.platform_repo.update_rating(review_data.platform_id)
            
            # 8. Формируем результат
            result = {
                "review_id": str(created_review.id),
                "status": updated_status.value,
                "sentiment_analysis": sentiment_analysis,
                "financial_impact": financial_impact_data,
                "generated_response": generated_response,
                "processing_recommendations": sentiment_analysis.get("recommendations", []),
                "created_at": created_review.created_at.isoformat(),
                "platform_name": platform.name,
                "company_name": company.name
            }
            
            return result
            
        except Exception as e:
            if isinstance(e, (NotFoundError, BusinessLogicError)):
                raise
            raise BusinessLogicError(f"Ошибка обработки отзыва: {str(e)}")
    
    async def simulate_review_impact(self, review_data: ReviewBase) -> Dict[str, Any]:
        """
        Симуляция влияния отзыва без сохранения в БД
        (для endpoint /simulate)
        """
        try:
            # Проверяем платформу
            platform = await self.platform_repo.get_with_reviews(review_data.platform_id)
            if not platform:
                raise NotFoundError("Платформа", str(review_data.platform_id))
            
            company = platform.company
            
            # Анализ тональности
            sentiment_analysis = self.sentiment_service.analyze_sentiment(
                rating=review_data.rating,
                review_text=review_data.text
            )
            
            # Расчет финансового влияния для разных сценариев
            scenarios = {}
            
            # Сценарий 1: Без ответа (статус NEW)
            scenarios["without_response"] = await self.economics_service.calculate_review_financial_impact(
                platform_id=review_data.platform_id,
                rating=review_data.rating,
                status=ReviewStatus.NEW
            )
            
            # Сценарий 2: С ответом (статус RESOLVED) - только для негативных
            if review_data.rating <= 3:
                scenarios["with_response"] = await self.economics_service.calculate_review_financial_impact(
                    platform_id=review_data.platform_id,
                    rating=review_data.rating,
                    status=ReviewStatus.RESOLVED
                )
                
                # Возможная экономия
                scenarios["potential_savings"] = (
                    scenarios["with_response"]["financial_impact"] - 
                    scenarios["without_response"]["financial_impact"]
                )
            
            # Генерируем пример ответа
            sample_response = None
            if review_data.rating <= 3:
                try:
                    sample_response = await self.llm_service.generate_review_response(
                        review_text=review_data.text,
                        rating=review_data.rating,
                        author_name=review_data.author_name,
                        company_name=company.name
                    )
                except Exception:
                    sample_response = "Не удалось сгенерировать ответ"
            
            return {
                "simulation": True,
                "review_data": review_data.model_dump(),
                "sentiment_analysis": sentiment_analysis, 
                "financial_scenarios": scenarios,
                "sample_si_response": sample_response,
                "platform_info": {
                    "name": platform.name,
                    "current_rating": platform.average_rating,
                    "monthly_views": platform.monthly_views
                },
                "company_info": {
                    "name": company.name,
                    "base_ltv": company.base_ltv,
                    "average_check": company.average_check
                },
                "recommendations": sentiment_analysis.get("recommendations", [])
            }
        
        except Exception as e:
            if isinstance(e, (NotFoundError, BusinessLogicError)):
                raise
            raise BusinessLogicError(f"Ошибка симуляции отзыва: {str(e)}")
    
    async def bulk_process_reviews(self, reviews_data: list[ReviewBase]) -> Dict[str, Any]:
        """Массовая обработка отзывов"""
        
        results = {
            "processed": [],
            "failed": [],
            "summary": {
                "total": len(reviews_data),
                "success": 0,
                "failed": 0,
                "total_financial_impact": 0.0
            }
        }
        
        for review_data in reviews_data:
            try:
                result = await self.process_new_review(review_data)
                results["processed"].append(result)
                results["summary"]["success"] += 1
                results["summary"]["total_financial_impact"] += result["financial_impact"]["financial_impact"]
            
            except Exception as e:
                results["failed"].append({
                    "review_data": review_data.model_dump(),
                    "error": str(e)
                })
                results["summary"]["failed"] += 1
        
        return results
    
    async def get_review_processing_queue(self, priority_filter: str = None) -> Dict[str, Any]:
        """Получить очередь отзывов для обработки"""
        
        # Получаем отзывы требующие внимания
        reviews_needing_attention = await self.review_repo.get_reviews_requiring_attention()
        
        queue = []
        for review in reviews_needing_attention:
            sentiment_analysis = self.sentiment_service.analyze_sentiment(
                rating=review.rating,
                review_text=review.text
            )
            
            if not priority_filter or sentiment_analysis["priority"] == priority_filter:
                queue.append({
                    "review_id": str(review.id),
                    "platform_name": review.platform.name,
                    "company_name": review.platform.company.name,
                    "rating": review.rating,
                    "author_name": review.author_name,
                    "created_at": review.created_at.isoformat(),
                    "priority": sentiment_analysis["priority"],
                    "recommended_response_time": sentiment_analysis["recommended_response_time"]
                })
        
        # Сортируем по приоритету
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        queue.sort(key=lambda x: (priority_order.get(x["priority"], 4), x["created_at"]))
        
        return {
            "queue_length": len(queue),
            "reviews": queue,
            "priority_breakdown": {
                "critical": len([r for r in queue if r["priority"] == "critical"]),
                "high": len([r for r in queue if r["priority"] == "high"]),
                "medium": len([r for r in queue if r["priority"] == "medium"]),
                "low": len([r for r in queue if r["priority"] == "low"])
            }
        }