"""
Analytics API Router
Эндпоинты для получения аналитики по отзывам и платформам с RLS изоляцией
"""

import csv
from collections.abc import AsyncIterator
from io import StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import get_current_tenant
from ..core.database import AsyncSessionLocal
from ..core.dependencies import (
    get_company_repository,
    get_platform_repository,
    get_review_repository,
)
from ..core.exceptions import BusinessLogicError, NotFoundError
from ..core.tenant_session import get_tenant_session
from ..models.economics import Review
from ..repositories import CompanyRepository, PlatformRepository, ReviewRepository
from ..schemas.analytics import AnalyticsRequest, DetailedAnalyticsResponse
from ..services.analytics import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


async def get_analytics_tenant_session(
    tenant_id: UUID = Depends(get_current_tenant),
) -> AsyncIterator[AsyncSession]:
    session = await get_tenant_session(
        factory=AsyncSessionLocal,
        tenant_id=tenant_id,
    )
    try:
        yield session
    finally:
        await session.close()


async def get_analytics_service(
    review_repo: ReviewRepository = Depends(get_review_repository),
    platform_repo: PlatformRepository = Depends(get_platform_repository),
    company_repo: CompanyRepository = Depends(get_company_repository),
) -> AnalyticsService:
    """Dependency для получения AnalyticsService с RLS изоляцией"""
    return AnalyticsService(review_repo, platform_repo, company_repo)


@router.get(
    "/export",
    status_code=200,
    summary="Экспорт отзывов в CSV",
    description="Выгрузка отзывов текущей компании для бизнес-отчетов",
)
async def export_reviews_csv(
    tenant_id: UUID = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_analytics_tenant_session),
) -> StreamingResponse:
    result = await session.execute(
        select(
            Review.created_at,
            Review.platform,
            Review.rating,
            Review.sentiment,
            Review.threat_level,
            Review.text,
        )
        .where(Review.company_id == tenant_id)
        .order_by(Review.created_at)
    )

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["date", "platform", "rating", "sentiment", "threat_level", "text"])
    for (
        created_at,
        platform,
        rating,
        sentiment,
        threat_level,
        review_text,
    ) in result.all():
        writer.writerow(
            [
                created_at.isoformat() if created_at else "",
                platform or "",
                rating if rating is not None else "",
                sentiment or "",
                threat_level if threat_level is not None else "",
                review_text or "",
            ]
        )

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="serm_report.csv"',
        },
    )


@router.post(
    "/detailed",
    status_code=200,
    response_model=DetailedAnalyticsResponse,
    summary="Подробная аналитика по отзывам",
    description="Получение детальной аналитики с возможностью фильтрации по платформам и временным диапазонам",
)
async def get_detailed_analytics(
    request: AnalyticsRequest,
    company_ids: list[UUID] | None = Query(None, description="Фильтр по ID компаний"),
    platform_ids: list[str] | None = Query(None, description="Фильтр по ID платформ"),
    include_trends: bool = Query(False, description="Включать анализ трендов"),
    tenant_id: UUID = Depends(get_current_tenant),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Подробная аналитика отзывов с фильтрацией и трендами:
    - Статистика по оценкам и сентименту
    - Распределение по платформам
    - Временные тренды (опционально)
    - Топ негативных и позитивных отзывов
    """

    try:
        if company_ids and any(company_id != tenant_id for company_id in company_ids):
            raise HTTPException(
                status_code=403, detail="Access to requested company is denied"
            )

        effective_request = request.model_copy(
            update={
                "platform_ids": (
                    platform_ids if platform_ids is not None else request.platform_ids
                ),
                "include_trends": include_trends or request.include_trends,
            }
        )
        analytics_data = await analytics_service.get_company_analytics(
            tenant_id, effective_request
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": analytics_data,
                "tenant_id": str(tenant_id),
                "message": "Аналитика успешно получена",
            },
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Данные не найдены: {str(e)}")
    except BusinessLogicError as e:
        raise HTTPException(status_code=400, detail=f"Ошибка бизнес-логики: {str(e)}")


@router.get(
    "/company-summary",
    status_code=200,
    summary="Сводка по компании",
    description="Получение сводной информации по компании за указанный период",
)
async def get_company_summary(
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    tenant_id: UUID = Depends(get_current_tenant),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Сводка по компании:
    - Общее количество отзывов за период
    - Средняя оценка и тренды
    - Распределение по платформам
    - Ключевые метрики сентимента
    """

    try:
        # Используем tenant_id как company_id для RLS изоляции
        summary = await analytics_service.get_company_summary(
            company_id=tenant_id, days=days
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": summary,
                "company_id": str(tenant_id),
                "period_days": days,
                "message": f"Сводка по компании за {days} дней",
            },
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Компания не найдена: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения сводки: {str(e)}"
        )


@router.get(
    "/platform/{platform_id}",
    status_code=200,
    summary="Аналитика по платформе",
    description="Статистика отзывов по конкретной платформе",
)
async def get_platform_analytics(
    platform_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    tenant_id: UUID = Depends(get_current_tenant),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Аналитика по конкретной платформе:
    - Статистика отзывов на платформе
    - Сравнение с общими показателями компании
    - Временные тренды по платформе
    - Специфичные для платформы метрики
    """

    try:
        platform_data = await analytics_service.get_platform_analytics(
            platform_id=platform_id,
            company_id=tenant_id,  # RLS изоляция
            days=days,
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": platform_data,
                "platform_id": str(platform_id),
                "company_id": str(tenant_id),
                "period_days": days,
                "message": f"Аналитика по платформе за {days} дней",
            },
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Платформа не найдена: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения аналитики по платформе: {str(e)}"
        )


@router.get(
    "/health",
    status_code=200,
    summary="Health check аналитики",
    description="Health check для модуля аналитики",
)
async def analytics_health_check(
    tenant_id: UUID = Depends(get_current_tenant),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Health check для аналитических сервисов:
    - Проверка доступности БД
    - Проверка доступности аналитических функций
    - Статус RLS изоляции
    """

    try:
        health_status = await analytics_service.health_check(tenant_id)

        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": "analytics",
                "tenant_id": str(tenant_id),
                "checks": health_status,
                "message": "Модуль аналитики работает корректно",
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "analytics",
                "tenant_id": str(tenant_id),
                "error": str(e),
                "message": "Модуль аналитики недоступен",
            },
        )
