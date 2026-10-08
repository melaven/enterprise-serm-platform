"""
Роутеры для управления компаниями
HTTP-обработка, валидация, делегирование в репозитории
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..schemas.economics import CompanyBase, CompanyResponse
from ..dependencies import get_company_repository
from ..repositories import CompanyRepository


router = APIRouter()


@router.post("/",
             status_code=201,
             summary="Создать компанию",
             description="Регистрация новой компании в системе SERM")
async def create_company(
    company_data: CompanyBase,
    company_repo: CompanyRepository = Depends(get_company_repository)
) -> JSONResponse:
    """
    Создание новой компании с экономическими показателями:
    - Название компании
    - Средний чек и маржинальность
    - CAC и базовый LTV
    """
    
    # Проверяем на дубликаты по названию
    existing_company = await company_repo.get_by_name(company_data.name)
    if existing_company:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "type": "ValidationError",
                    "message": f"Компания с названием '{company_data.name}' уже существует"
                }
            }
        )
    
    created_company = await company_repo.create(**company_data.model_dump())
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "Компания успешно создана",
            "data": {
                "id": str(created_company.id),
                "name": created_company.name,
                "created_at": created_company.created_at.isoformat()
            }
        }
    )


@router.get("/{company_id}",
            summary="Получить компанию",
            description="Детальная информация о компании")
async def get_company(
    company_id: UUID,
    include_platforms: bool = Query(False, description="Включить данные платформ"),
    company_repo: CompanyRepository = Depends(get_company_repository)
) -> JSONResponse:
    """
    Получение информации о компании
    с возможностью включения данных платформ
    """
    
    if include_platforms:
        company = await company_repo.get_with_platforms(company_id)
    else:
        company = await company_repo.get_by_id(company_id)
    
    if not company:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "type": "NotFoundError",
                    "message": f"Компания с ID {company_id} не найдена"
                }
            }
        )
    
    company_data = {
        "id": str(company.id),
        "name": company.name,
        "average_check": company.average_check,
        "margin_percent": company.margin_percent,
        "cac": company.cac,
        "base_ltv": company.base_ltv,
        "created_at": company.created_at.isoformat()
    }
    
    if include_platforms and company.platforms:
        company_data["platforms"] = [
            {
                "id": str(platform.id),
                "name": platform.name,
                "monthly_views": platform.monthly_views,
                "conversion_rate": platform.conversion_rate,
                "average_rating": platform.average_rating
            }
            for platform in company.platforms
        ]
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": company_data
        }
    )


@router.get("/",
            summary="Список компаний",
            description="Получить список всех компаний с пагинацией")
async def list_companies(
    limit: int = Query(50, ge=1, le=200, description="Количество компаний"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    search: Optional[str] = Query(None, description="Поиск по названию компании"),
    company_repo: CompanyRepository = Depends(get_company_repository)
) -> JSONResponse:
    """
    Получение списка компаний с возможностью поиска
    """
    
    if search:
        companies = await company_repo.search_by_name_pattern(search, limit)
    else:
        companies = await company_repo.get_all(limit=limit, offset=offset)
    
    companies_data = []
    for company in companies:
        companies_data.append({
            "id": str(company.id),
            "name": company.name,
            "average_check": company.average_check,
            "base_ltv": company.base_ltv,
            "created_at": company.created_at.isoformat()
        })
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "companies": companies_data,
                "count": len(companies_data),
                "pagination": {
                    "limit": limit,
                    "offset": offset
                }
            }
        }
    )


@router.put("/{company_id}",
            summary="Обновить компанию",
            description="Изменение данных компании")
async def update_company(
    company_id: UUID,
    company_data: CompanyBase,
    company_repo: CompanyRepository = Depends(get_company_repository)
) -> JSONResponse:
    """
    Обновление данных компании
    """
    
    updated_company = await company_repo.update(company_id, **company_data.model_dump())
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Данные компании обновлены",
            "data": {
                "id": str(updated_company.id),
                "name": updated_company.name,
                "updated_fields": list(company_data.model_dump().keys())
            }
        }
    )


@router.put("/{company_id}/economics",
            summary="Обновить экономические показатели",
            description="Изменение CAC, LTV, маржинальности и среднего чека")
async def update_company_economics(
    company_id: UUID,
    average_check: Optional[float] = Query(None, gt=0, description="Средний чек"),
    margin_percent: Optional[float] = Query(None, ge=0, le=100, description="Маржинальность %"),
    cac: Optional[float] = Query(None, ge=0, description="Стоимость привлечения клиента"),
    base_ltv: Optional[float] = Query(None, ge=0, description="Базовый LTV"),
    company_repo: CompanyRepository = Depends(get_company_repository)
) -> JSONResponse:
    """
    Обновление экономических показателей компании
    """
    
    updated_company = await company_repo.update_economics(
        company_id=company_id,
        average_check=average_check,
        margin_percent=margin_percent,
        cac=cac,
        base_ltv=base_ltv
    )
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Экономические показатели обновлены",
            "data": {
                "id": str(updated_company.id),
                "name": updated_company.name,
                "average_check": updated_company.average_check,
                "margin_percent": updated_company.margin_percent,
                "cac": updated_company.cac,
                "base_ltv": updated_company.base_ltv
            }
        }
    )


@router.delete("/{company_id}",
               summary="Удалить компанию",
               description="Удаление компании и всех связанных данных")
async def delete_company(
    company_id: UUID,
    company_repo: CompanyRepository = Depends(get_company_repository)
) -> JSONResponse:
    """
    Удаление компании со всеми платформами и отзывами
    """
    
    deleted = await company_repo.delete(company_id)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Компания успешно удалена",
            "data": {
                "company_id": str(company_id),
                "deleted": deleted
            }
        }
    )


@router.get("/{company_id}/dashboard",
            summary="Дашборд компании",
            description="Сводная аналитика по всем платформам компании")
async def get_company_dashboard(
    company_id: UUID,
    company_repo: CompanyRepository = Depends(get_company_repository)
) -> JSONResponse:
    """
    Сводная аналитика компании:
    - Базовые показатели
    - Статистика по платформам
    - Общее финансовое влияние отзывов
    """
    
    company = await company_repo.get_with_full_data(company_id)
    if not company:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "type": "NotFoundError", 
                    "message": f"Компания с ID {company_id} не найдена"
                }
            }
        )
    
    # Собираем аналитику
    total_reviews = 0
    total_financial_impact = 0.0
    platforms_stats = []
    
    for platform in company.platforms:
        platform_reviews_count = len(platform.reviews)
        platform_impact = sum(review.financial_impact for review in platform.reviews)
        
        total_reviews += platform_reviews_count
        total_financial_impact += platform_impact
        
        platforms_stats.append({
            "platform_id": str(platform.id),
            "platform_name": platform.name,
            "reviews_count": platform_reviews_count,
            "average_rating": platform.average_rating,
            "financial_impact": platform_impact
        })
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "company": {
                    "id": str(company.id),
                    "name": company.name,
                    "average_check": company.average_check,
                    "base_ltv": company.base_ltv
                },
                "analytics": {
                    "total_reviews": total_reviews,
                    "total_financial_impact": total_financial_impact,
                    "platforms_count": len(company.platforms),
                    "roi_estimate": (
                        (total_financial_impact / company.cac) * 100 
                        if company.cac > 0 else 0
                    )
                },
                "platforms": platforms_stats
            }
        }
    )