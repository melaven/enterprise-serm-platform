"""
Сервис для экономических расчетов SERM
Все математика LTV, CAC, конверсий, упущенной выгоды
"""

from typing import Dict, Any, Optional
from uuid import UUID

from ..repositories import CompanyRepository, PlatformRepository
from ..models.economics import Company, Platform, Review
from ..schemas.economics import ReviewStatus
from ..exceptions import EconomicsCalculationError, NotFoundError


class EconomicsService:
    """Сервис экономических расчетов для SERM"""
    
    def __init__(self, 
                 company_repo: CompanyRepository,
                 platform_repo: PlatformRepository):
        self.company_repo = company_repo
        self.platform_repo = platform_repo
    
    async def calculate_review_financial_impact(self,
                                               platform_id: UUID,
                                               rating: int,
                                               status: ReviewStatus = ReviewStatus.NEW,
                                               custom_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Основная функция расчета финансового влияния отзыва
        """
        # Получаем данные платформы с компанией
        platform = await self.platform_repo.get_with_reviews(platform_id)
        if not platform:
            raise NotFoundError("Платформа", str(platform_id))
        
        company = platform.company
        if not company:
            raise NotFoundError("Компания для платформы", str(platform_id))
        
        # Параметры для расчета (с возможностью переопределения)
        params = {
            "lost_leads_coefficient": 5,  # Количество потерянных лидов на негативный отзыв
            "positive_boost_coefficient": 0.5,  # Коэффициент буста от позитивного отзыва
            "ltv_save_coefficient": 1.0,  # Коэффициент спасения LTV при решении конфликта
            **(custom_params or {})
        }
        
        result = {
            "platform_id": platform_id,
            "rating": rating,
            "status": status,
            "financial_impact": 0.0,
            "calculation_details": {},
            "recommendation": ""
        }
        
        try:
            if rating <= 3:  # Негативный отзыв
                if status == ReviewStatus.RESOLVED:
                    # SI-ядро отработало конфликт - спасли LTV клиента
                    result["financial_impact"] = company.base_ltv * params["ltv_save_coefficient"]
                    result["calculation_details"] = {
                        "base_ltv": company.base_ltv,
                        "ltv_save_coefficient": params["ltv_save_coefficient"],
                        "saved_ltv": result["financial_impact"]
                    }
                    result["recommendation"] = "✅ Конфликт улажен. LTV клиента успешно защищен."
                
                else:
                    # Негатив висит без ответа - считаем упущенную выгоду
                    lost_revenue = self._calculate_lost_revenue_from_negative(
                        company, platform, params["lost_leads_coefficient"]
                    )
                    result["financial_impact"] = -lost_revenue
                    result["calculation_details"] = {
                        "average_check": company.average_check,
                        "lost_leads": params["lost_leads_coefficient"],
                        "lost_revenue": lost_revenue,
                        "margin_percent": company.margin_percent
                    }
                    result["recommendation"] = "⚠️ Обнаружен негатив! Идет утечка лидов. Требуется ответ SI-ядра."
            
            else:  # Позитивный отзыв (4-5 звезд)
                positive_boost = self._calculate_positive_impact(
                    company, platform, params["positive_boost_coefficient"]
                )
                result["financial_impact"] = positive_boost
                result["calculation_details"] = {
                    "average_check": company.average_check,
                    "positive_boost_coefficient": params["positive_boost_coefficient"],
                    "organic_boost": positive_boost
                }
                result["recommendation"] = "📈 Позитивный отзыв. Органическая конверсия растет."
            
            return result
        
        except Exception as e:
            raise EconomicsCalculationError(
                "финансового влияния отзыва",
                f"Ошибка при расчете для platform_id={platform_id}: {str(e)}"
            )
    
    def _calculate_lost_revenue_from_negative(self,
                                            company: Company,
                                            platform: Platform,
                                            lost_leads_coefficient: int) -> float:
        """Расчет потерянной выручки от негативного отзыва"""
        
        if company.average_check <= 0:
            raise EconomicsCalculationError(
                "потерянной выручки", 
                "Средний чек должен быть больше 0"
            )
        
        # Базовый расчет: средний чек * количество потерянных лидов
        base_loss = company.average_check * lost_leads_coefficient
        
        # Учитываем конверсию платформы (если есть данные)
        if platform.conversion_rate > 0:
            # Потерянные лиды с учетом конверсии платформы
            adjusted_loss = base_loss * platform.conversion_rate
            return adjusted_loss
        
        return base_loss
    
    def _calculate_positive_impact(self,
                                 company: Company,
                                 platform: Platform,  
                                 boost_coefficient: float) -> float:
        """Расчет положительного влияния позитивного отзыва"""
        
        if company.average_check <= 0:
            raise EconomicsCalculationError(
                "положительного влияния",
                "Средний чек должен быть больше 0"
            )
        
        # Базовый буст от позитивного отзыва
        base_boost = company.average_check * boost_coefficient
        
        # Учитываем показы платформы для масштабирования эффекта
        if platform.monthly_views > 1000:
            # Масштабируем положительный эффект для популярных платформ
            popularity_multiplier = min(1.5, 1 + (platform.monthly_views / 10000))
            return base_boost * popularity_multiplier
        
        return base_boost
    
    async def calculate_platform_roi(self, platform_id: UUID) -> Dict[str, Any]:
        """Расчет ROI платформы на основе отзывов"""
        
        platform = await self.platform_repo.get_with_reviews(platform_id)
        if not platform:
            raise NotFoundError("Платформа", str(platform_id))
        
        company = platform.company
        total_impact = sum(review.financial_impact for review in platform.reviews)
        investment = platform.cac_on_platform
        
        if investment <= 0:
            roi_percent = float('inf') if total_impact > 0 else 0
        else:
            roi_percent = ((total_impact - investment) / investment) * 100
        
        return {
            "platform_id": platform_id,
            "platform_name": platform.name,
            "total_financial_impact": total_impact,
            "investment_cac": investment,
            "roi_percent": roi_percent,
            "reviews_count": len(platform.reviews),
            "average_impact_per_review": total_impact / len(platform.reviews) if platform.reviews else 0
        }
    
    async def calculate_ltv_risk_assessment(self, 
                                          platform_id: UUID,
                                          time_without_response_hours: int = 24) -> Dict[str, Any]:
        """Оценка риска потери LTV из-за негативных отзывов без ответа"""
        
        platform = await self.platform_repo.get_with_reviews(platform_id)
        if not platform:
            raise NotFoundError("Платформа", str(platform_id))
        
        company = platform.company
        
        # Считаем негативные отзывы без ответа
        negative_without_response = [
            review for review in platform.reviews
            if review.rating <= 3 
            and review.status == ReviewStatus.NEW
            and not review.si_response
        ]
        
        # Риск потери LTV
        ltv_at_risk = len(negative_without_response) * company.base_ltv
        
        # Потенциальная упущенная выгода
        potential_lost_revenue = sum(
            abs(review.financial_impact) for review in negative_without_response
        )
        
        # Уровень риска
        risk_level = "low"
        if len(negative_without_response) > 5:
            risk_level = "high"
        elif len(negative_without_response) > 2:
            risk_level = "medium"
        
        return {
            "platform_id": platform_id,
            "risk_assessment": {
                "level": risk_level,
                "negative_reviews_count": len(negative_without_response),
                "ltv_at_risk": ltv_at_risk,
                "potential_lost_revenue": potential_lost_revenue,
                "time_threshold_hours": time_without_response_hours
            },
            "recommendations": self._get_risk_recommendations(risk_level, len(negative_without_response))
        }
    
    def _get_risk_recommendations(self, risk_level: str, negative_count: int) -> list[str]:
        """Получить рекомендации по управлению рисками"""
        
        recommendations = []
        
        if risk_level == "high":
            recommendations.extend([
                "🚨 КРИТИЧЕСКИЙ РИСК: Немедленно активировать SI-ядро",
                "📞 Персональный контакт с недовольными клиентами",
                "🎁 Рассмотреть компенсационные предложения"
            ])
        
        elif risk_level == "medium":
            recommendations.extend([
                "⚠️ Повышенное внимание к негативным отзывам",
                "🤖 Запустить автоматическую генерацию ответов",
                "📊 Мониторить изменения конверсии"
            ])
        
        else:
            recommendations.extend([
                "✅ Ситуация под контролем",
                "📈 Продолжить работу по улучшению сервиса"
            ])
        
        return recommendations