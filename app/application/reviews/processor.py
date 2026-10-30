"""
Центральный сервис обработки отзывов - координирует все операции
"""

from typing import Any

from app.api.schemas.economics import ReviewBase, ReviewStatus
from app.application.economics import EconomicsService
from app.application.reviews.local_si import analyze_review_locally
from app.core.exceptions import BusinessLogicError, NotFoundError
from app.domain.reviews.sentiment import SentimentService
from app.infrastructure.persistence.repositories import (
    CompanyRepository,
    PlatformRepository,
    ReviewRepository,
)


class ReviewProcessorService:
    """Центральный сервис обработки отзывов"""

    def __init__(
        self,
        review_repo: ReviewRepository,
        platform_repo: PlatformRepository,
        company_repo: CompanyRepository,
        economics_service: EconomicsService,
        sentiment_service: SentimentService,
        auth_context: Any = None,
    ):
        self.review_repo = review_repo
        self.platform_repo = platform_repo
        self.company_repo = company_repo
        self.economics_service = economics_service
        self.sentiment_service = sentiment_service
        self.auth_context = auth_context

    async def process_new_review(self, review_data: ReviewBase) -> dict[str, Any]:
        """
        Полная обработка нового отзыва:
        Проверка платформы, анализ тональности, расчет финансового влияния,
        генерация ответа и сохранение обезличенной выжимки.
        """
        try:
            # 1. Проверяем существование платформы
            platform = await self.platform_repo.get_with_reviews(
                review_data.platform_id
            )
            if not platform:
                raise NotFoundError("Платформа", str(review_data.platform_id))

            company = platform.company

            # 2. Local SI; source text remains in request memory only.
            sentiment_analysis = self.sentiment_service.analyze_sentiment(
                rating=review_data.rating, review_text=review_data.text
            )

            # 3. Расчет финансового влияния
            financial_impact_data = (
                await self.economics_service.calculate_review_financial_impact(
                    platform_id=review_data.platform_id,
                    rating=review_data.rating,
                    status=review_data.status,
                )
            )

            analysis = analyze_review_locally(review_data.text, review_data.rating)
            updated_status = review_data.status

            # 5. Создаем отзыв в БД
            created_review = await self.review_repo.create(
                platform_id=review_data.platform_id,
                author_name="Автор отзыва",
                rating=review_data.rating,
                text=analysis.summary,
                company_id=self.auth_context.company_id
                if self.auth_context
                else review_data.platform_id,  # Автозаполнение tenant
                status=updated_status,
                financial_impact=financial_impact_data["financial_impact"],
                sentiment=analysis.sentiment,
                threat_level=analysis.threat_level,
                is_critical=analysis.is_critical,
                is_analyzed=True,
                tags=[],
                analysis_tags=[],
                si_response=None,
                suggested_reply=None,
                auto_reply=None,
            )

            # 6. Обновляем средний рейтинг платформы
            await self.platform_repo.update_rating(review_data.platform_id)

            # 7. Формируем результат
            result = {
                "review_id": str(created_review.id),
                "status": updated_status.value,
                "sentiment_analysis": sentiment_analysis,
                "financial_impact": financial_impact_data,
                "reply_draft": analysis.reply_draft,
                "processing_recommendations": sentiment_analysis.get(
                    "recommendations", []
                ),
                "created_at": created_review.created_at.isoformat(),
                "platform_name": platform.name,
                "company_name": company.name,
            }

            return result

        except Exception as e:
            if isinstance(e, NotFoundError | BusinessLogicError):
                raise
            raise BusinessLogicError(f"Ошибка обработки отзыва: {str(e)}")

    async def simulate_review_impact(self, review_data: ReviewBase) -> dict[str, Any]:
        """
        Симуляция влияния отзыва без сохранения в БД
        (для endpoint /simulate)
        """
        try:
            # Проверяем платформу
            platform = await self.platform_repo.get_with_reviews(
                review_data.platform_id
            )
            if not platform:
                raise NotFoundError("Платформа", str(review_data.platform_id))

            company = platform.company

            # Анализ тональности
            sentiment_analysis = self.sentiment_service.analyze_sentiment(
                rating=review_data.rating, review_text=review_data.text
            )

            # Расчет финансового влияния для разных сценариев
            scenarios = {}

            # Сценарий 1: Без ответа (статус NEW)
            scenarios[
                "without_response"
            ] = await self.economics_service.calculate_review_financial_impact(
                platform_id=review_data.platform_id,
                rating=review_data.rating,
                status=ReviewStatus.NEW,
            )

            # Сценарий 2: С ответом (статус RESOLVED) - только для негативных
            if review_data.rating <= 3:
                scenarios[
                    "with_response"
                ] = await self.economics_service.calculate_review_financial_impact(
                    platform_id=review_data.platform_id,
                    rating=review_data.rating,
                    status=ReviewStatus.RESOLVED,
                )

                # Возможная экономия
                scenarios["potential_savings"] = (
                    scenarios["with_response"]["financial_impact"]
                    - scenarios["without_response"]["financial_impact"]
                )

            analysis = analyze_review_locally(review_data.text, review_data.rating)

            return {
                "simulation": True,
                "review_data": {
                    "platform_id": str(review_data.platform_id),
                    "rating": review_data.rating,
                    "status": review_data.status.value,
                },
                "sentiment_analysis": sentiment_analysis,
                "financial_scenarios": scenarios,
                "reply_draft": analysis.reply_draft,
                "platform_info": {
                    "name": platform.name,
                    "current_rating": platform.average_rating,
                    "monthly_views": platform.monthly_views,
                },
                "company_info": {
                    "name": company.name,
                    "base_ltv": company.base_ltv,
                    "average_check": company.average_check,
                },
                "recommendations": sentiment_analysis.get("recommendations", []),
            }

        except Exception as e:
            if isinstance(e, NotFoundError | BusinessLogicError):
                raise
            raise BusinessLogicError(f"Ошибка симуляции отзыва: {str(e)}")

    async def bulk_process_reviews(
        self, reviews_data: list[ReviewBase]
    ) -> dict[str, Any]:
        """Массовая обработка отзывов"""

        results: dict[str, Any] = {
            "processed": [],
            "failed": [],
            "summary": {
                "total": len(reviews_data),
                "success": 0,
                "failed": 0,
                "total_financial_impact": 0.0,
            },
        }

        for review_data in reviews_data:
            try:
                result = await self.process_new_review(review_data)
                results["processed"].append(result)
                results["summary"]["success"] += 1
                results["summary"]["total_financial_impact"] += result[
                    "financial_impact"
                ]["financial_impact"]

            except Exception as e:
                results["failed"].append(
                    {
                        "index": len(results["processed"]) + len(results["failed"]),
                        "error_type": type(e).__name__,
                    }
                )
                results["summary"]["failed"] += 1

        return results

    async def get_review_processing_queue(
        self, priority_filter: str | None = None
    ) -> dict[str, Any]:
        """Получить очередь отзывов для обработки"""

        # Получаем отзывы требующие внимания
        reviews_needing_attention = (
            await self.review_repo.get_reviews_requiring_attention()
        )

        queue = []
        for review in reviews_needing_attention:
            sentiment_analysis = self.sentiment_service.analyze_sentiment(
                rating=review.rating, review_text=review.text
            )

            if not priority_filter or sentiment_analysis["priority"] == priority_filter:
                queue.append(
                    {
                        "review_id": str(review.id),
                        "platform_name": (
                            review.platform_ref.name
                            if review.platform_ref
                            else review.platform or "Unknown"
                        ),
                        "company_name": review.company.name,
                        "rating": review.rating,
                        "author_name": review.author_name,
                        "created_at": review.created_at.isoformat(),
                        "priority": sentiment_analysis["priority"],
                        "recommended_response_time": sentiment_analysis[
                            "recommended_response_time"
                        ],
                    }
                )

        # Сортируем по приоритету
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        queue.sort(
            key=lambda x: (priority_order.get(x["priority"], 4), x["created_at"])
        )

        return {
            "queue_length": len(queue),
            "reviews": queue,
            "priority_breakdown": {
                "critical": len([r for r in queue if r["priority"] == "critical"]),
                "high": len([r for r in queue if r["priority"] == "high"]),
                "medium": len([r for r in queue if r["priority"] == "medium"]),
                "low": len([r for r in queue if r["priority"] == "low"]),
            },
        }
