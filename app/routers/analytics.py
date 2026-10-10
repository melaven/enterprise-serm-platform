"""
Analytics API Router
Эндпоинты для получения аналитики по отзывам и платформам
"""

from datetime import date
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from ..auth import AuthContext
from ..auth.tenant_session import TenantSession 
from ..dependencies import get_auth_context, get_db_with_tenant
from ..services.analytics import AnalyticsService
from ..repositories import ReviewRepository, PlatformRepository, CompanyRepository
from ..schemas.analytics import (
    AnalyticsRequest, DetailedAnalyticsResponse, TimeRange
)
from ..exceptions import BusinessLogicError, NotFoundError

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


async def get_analytics_service(
    db: TenantSession = Depends(get_db_with_tenant)
) -> AnalyticsService:
    """Dependency для получения AnalyticsService"""
    
    review_repo = ReviewRepository(db)
    platform_repo = PlatformRepository(db) 
    company_repo = CompanyRepository(db)
    
    return AnalyticsService(
        review_repo=review_repo,
        platform_repo=platform_repo,
        company_repo=company_repo
    )


@router.get("/company", 
           response_model=DetailedAnalyticsResponse,
           summary="Аналитика компании",
           description="Получение детальной аналитики по отзывам для компании")
async def get_company_analytics(
    time_range: TimeRange = Query(..., description="Временной диапазон для аналитики"),
    start_date: Optional[date] = Query(None, description="Начальная дата (для custom периода)"),
    end_date: Optional[date] = Query(None, description="Конечная дата (для custom периода)"),
    platform_ids: Optional[List[str]] = Query(None, description="Фильтр по ID платформ"),
    include_trends: bool = Query(False, description="Включать анализ трендов"),
    auth: AuthContext = Depends(get_auth_context),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Получение детальной аналитики для компании пользователя
    
    Возвращает:
    - Общую статистику по компании
    - Аналитику по каждой платформе
    - Распределение тональности и рейтингов
    - Финансовое влияние отзывов
    - Тренды (опционально)
    """
    try:
        request = AnalyticsRequest(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            platform_ids=platform_ids,
            include_trends=include_trends
        )
        
        result = await analytics_service.get_company_analytics(
            company_id=UUID(auth.company_id),
            request=request
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Ошибка валидации: {str(e)}")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get("/company/summary",
           summary="Краткая аналитика компании", 
           description="Получение краткой сводки аналитики для дашборда")
async def get_company_summary(
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    auth: AuthContext = Depends(get_auth_context),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Краткая сводка аналитики компании за указанный период
    
    Оптимизированный эндпоинт для дашбордов и быстрого просмотра
    """
    try:
        # Создаем запрос для указанного количества дней
        end_date = date.today()
        start_date = date.fromordinal(end_date.toordinal() - days + 1)
        
        request = AnalyticsRequest(
            time_range=TimeRange.CUSTOM,
            start_date=start_date,
            end_date=end_date,
            include_trends=False  # Для summary не включаем тренды
        )
        
        result = await analytics_service.get_company_analytics(
            company_id=UUID(auth.company_id),
            request=request
        )
        
        # Возвращаем только основные метрики для summary
        summary = {
            "company_id": result.company_analytics.company_id,
            "period": {
                "days": days,
                "start_date": result.company_analytics.period_start.date(),
                "end_date": result.company_analytics.period_end.date()
            },
            "totals": {
                "reviews": result.company_analytics.total_reviews,
                "platforms": result.company_analytics.total_platforms,
                "financial_impact": result.company_analytics.total_financial_impact,
                "average_rating": result.company_analytics.overall_rating.average
            },
            "sentiment": {
                "positive": result.company_analytics.overall_sentiment.positive,
                "neutral": result.company_analytics.overall_sentiment.neutral, 
                "negative": result.company_analytics.overall_sentiment.negative
            },
            "top_platforms": [
                {
                    "name": p.platform_name,
                    "reviews": p.total_reviews,
                    "rating": p.rating_distribution.average,
                    "financial_impact": p.financial_impact
                }
                for p in sorted(
                    result.company_analytics.platforms,
                    key=lambda x: x.total_reviews,
                    reverse=True
                )[:5]  # Топ 5 платформ
            ]
        }
        
        return JSONResponse(content=summary)
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Ошибка валидации: {str(e)}")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get("/platforms/{platform_id}",
           summary="Аналитика платформы",
           description="Детальная аналитика для конкретной платформы")
async def get_platform_analytics(
    platform_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    auth: AuthContext = Depends(get_auth_context),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Получение детальной аналитики для конкретной платформы
    """
    try:
        # Создаем запрос для конкретной платформы
        end_date = date.today()
        start_date = date.fromordinal(end_date.toordinal() - days + 1)
        
        request = AnalyticsRequest(
            time_range=TimeRange.CUSTOM,
            start_date=start_date,
            end_date=end_date,
            platform_ids=[str(platform_id)],
            include_trends=True
        )
        
        result = await analytics_service.get_company_analytics(
            company_id=UUID(auth.company_id),
            request=request
        )
        
        # Ищем платформу в результатах
        platform_analytics = None
        for platform in result.company_analytics.platforms:
            if platform.platform_id == str(platform_id):
                platform_analytics = platform
                break
        
        if not platform_analytics:
            raise HTTPException(
                status_code=404, 
                detail=f"Платформа {platform_id} не найдена или не принадлежит компании"
            )
        
        return JSONResponse(content={
            "platform": platform_analytics.dict(),
            "period": {
                "days": days,
                "start_date": start_date,
                "end_date": end_date
            },
            "trends": result.trends or []
        })
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Ошибка валидации: {str(e)}")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get("/health",
           summary="Проверка состояния аналитики",
           description="Health check для модуля аналитики")
async def analytics_health_check(
    auth: AuthContext = Depends(get_auth_context),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Проверка работоспособности модуля аналитики
    """
    try:
        # Простая проверка - получаем краткую статистику за последний день
        end_date = date.today()
        start_date = end_date
        
        request = AnalyticsRequest(
            time_range=TimeRange.CUSTOM,
            start_date=start_date,
            end_date=end_date,
            include_trends=False
        )
        
        # Пытаемся получить аналитику
        await analytics_service.get_company_analytics(
            company_id=UUID(auth.company_id),
            request=request
        )
        
        return JSONResponse(content={
            "status": "healthy",
            "module": "analytics",
            "timestamp": end_date.isoformat(),
            "company_id": auth.company_id
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=503, 
            detail=f"Модуль аналитики недоступен: {str(e)}"
        )