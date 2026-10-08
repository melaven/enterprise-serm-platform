"""
Роутеры для управления платформами
HTTP-обработка, валидация, делегирование в репозитории
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..schemas.economics import PlatformBase, PlatformResponse
from ..dependencies import get_platform_repository
from ..repositories import PlatformRepository


router = APIRouter()


@router.post("/",
             status_code=201,
             summary="Создать платформу",
             description="Добавление новой платформы размещения отзывов")
async def create_platform(
    platform_data: PlatformBase,
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> JSONResponse:
    """
    Создание новой платформы для размещения отзывов:
    - Google Maps, 2GIS, Trustpilot, Яндекс.Карты и др.
    - Привязка к компании
    - Метрики показов и конверсии
    """
    
    # Проверяем на дубликаты в рамках компании
    existing_platform = await platform_repo.get_by_name_and_company(
        platform_data.name, platform_data.company_id
    )
    if existing_platform:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "type": "ValidationError",
                    "message": f"Платформа '{platform_data.name}' уже существует для данной компании"
                }
            }
        )
    
    created_platform = await platform_repo.create(**platform_data.model_dump())
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "Платформа успешно создана",
            "data": {
                "id": str(created_platform.id),
                "name": created_platform.name,
                "company_id": str(created_platform.company_id)
            }
        }
    )


@router.get("/{platform_id}",
            summary="Получить платформу",
            description="Детальная информация о платформе")
async def get_platform(
    platform_id: UUID,
    include_reviews: bool = Query(False, description="Включить отзывы"),
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> JSONResponse:
    """
    Получение информации о платформе
    с возможностью включения отзывов
    """
    
    if include_reviews:
        platform = await platform_repo.get_with_reviews(platform_id)
    else:
        platform = await platform_repo.get_by_id(platform_id)
    
    if not platform:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "type": "NotFoundError",
                    "message": f"Платформа с ID {platform_id} не найдена"
                }
            }
        )
    
    platform_data = {
        "id": str(platform.id),
        "company_id": str(platform.company_id),
        "name": platform.name,
        "monthly_views": platform.monthly_views,
        "conversion_rate": platform.conversion_rate,
        "cac_on_platform": platform.cac_on_platform,
        "average_rating": platform.average_rating
    }
    
    if include_reviews and platform.reviews:
        platform_data["reviews"] = [
            {
                "id": str(review.id),
                "author_name": review.author_name,
                "rating": review.rating,
                "status": review.status.value,
                "financial_impact": review.financial_impact,
                "created_at": review.created_at.isoformat()
            }
            for review in platform.reviews
        ]
        platform_data["reviews_count"] = len(platform.reviews)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": platform_data
        }
    )


@router.get("/company/{company_id}/platforms",
            summary="Платформы компании",
            description="Получить все платформы конкретной компании")
async def get_company_platforms(
    company_id: UUID,
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> JSONResponse:
    """
    Список всех платформ компании
    """
    
    platforms = await platform_repo.get_by_company_id(company_id)
    
    platforms_data = []
    for platform in platforms:
        platforms_data.append({
            "id": str(platform.id),
            "name": platform.name,
            "monthly_views": platform.monthly_views,
            "conversion_rate": platform.conversion_rate,
            "average_rating": platform.average_rating,
            "cac_on_platform": platform.cac_on_platform
        })
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "company_id": str(company_id),
                "platforms": platforms_data,
                "count": len(platforms_data)
            }
        }
    )


@router.put("/{platform_id}",
            summary="Обновить платформу",
            description="Изменение данных платформы")
async def update_platform(
    platform_id: UUID,
    platform_data: PlatformBase,
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> JSONResponse:
    """
    Обновление данных платформы
    """
    
    updated_platform = await platform_repo.update(platform_id, **platform_data.model_dump())
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Данные платформы обновлены",
            "data": {
                "id": str(updated_platform.id),
                "name": updated_platform.name
            }
        }
    )


@router.put("/{platform_id}/metrics",
            summary="Обновить метрики платформы",
            description="Изменение показов, конверсии и CAC")
async def update_platform_metrics(
    platform_id: UUID,
    monthly_views: Optional[int] = Query(None, ge=0, description="Ежемесячные показы"),
    conversion_rate: Optional[float] = Query(None, ge=0, le=1, description="Конверсия (0-1)"),
    cac_on_platform: Optional[float] = Query(None, ge=0, description="CAC на платформе"),
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> JSONResponse:
    """
    Обновление метрик платформы
    """
    
    updated_platform = await platform_repo.update_metrics(
        platform_id=platform_id,
        monthly_views=monthly_views,
        conversion_rate=conversion_rate,
        cac_on_platform=cac_on_platform
    )
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Метрики платформы обновлены",
            "data": {
                "id": str(updated_platform.id),
                "name": updated_platform.name,
                "monthly_views": updated_platform.monthly_views,
                "conversion_rate": updated_platform.conversion_rate,
                "cac_on_platform": updated_platform.cac_on_platform
            }
        }
    )


@router.put("/{platform_id}/recalculate-rating",
            summary="Пересчитать средний рейтинг",
            description="Обновление среднего рейтинга на основе отзывов")
async def recalculate_platform_rating(
    platform_id: UUID,
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> JSONResponse:
    """
    Пересчет среднего рейтинга платформы
    на основе всех отзывов
    """
    
    updated_platform = await platform_repo.update_rating(platform_id)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Средний рейтинг пересчитан",
            "data": {
                "platform_id": str(platform_id),
                "new_average_rating": updated_platform.average_rating
            }
        }
    )


@router.get("/stats",
            summary="Статистика платформ",
            description="Статистика всех или выбранных платформ")
async def get_platforms_stats(
    company_id: Optional[UUID] = Query(None, description="Фильтр по компании"),
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> JSONResponse:
    """
    Получить статистику платформ со сводными данными по отзывам
    """
    
    stats = await platform_repo.get_platforms_with_stats(company_id)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "platforms_stats": stats,
                "count": len(stats),
                "filtered_by_company": str(company_id) if company_id else None
            }
        }
    )


@router.get("/top-by-impact",
            summary="Топ платформ по влиянию",
            description="Платформы с наибольшим финансовым влиянием")
async def get_top_platforms_by_impact(
    limit: int = Query(10, ge=1, le=50, description="Количество платформ в топе"),
    company_id: Optional[UUID] = Query(None, description="Фильтр по компании"),
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> JSONResponse:
    """
    Топ платформ по финансовому влиянию отзывов
    """
    
    top_platforms = await platform_repo.get_top_platforms_by_impact(limit, company_id)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "top_platforms": top_platforms,
                "limit": limit,
                "filtered_by_company": str(company_id) if company_id else None
            }
        }
    )


@router.delete("/{platform_id}",
               summary="Удалить платформу",
               description="Удаление платформы и всех связанных отзывов")
async def delete_platform(
    platform_id: UUID,
    platform_repo: PlatformRepository = Depends(get_platform_repository)
) -> JSONResponse:
    """
    Удаление платформы со всеми отзывами
    """
    
    deleted = await platform_repo.delete(platform_id)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Платформа успешно удалена",
            "data": {
                "platform_id": str(platform_id),
                "deleted": deleted
            }
        }
    )