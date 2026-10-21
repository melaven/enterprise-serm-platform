"""
Роутеры для управления платформами
HTTP-обработка, валидация, делегирование в репозитории
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import get_current_tenant
from ..core.dependencies import get_platform_repository, get_tenant_db
from ..models.economics import Platform, PlatformIntegration, Review
from ..repositories import PlatformRepository
from ..schemas.economics import PlatformBase, ReviewStatus
from ..services.entitlement import enforce_reviews_quota
from ..services.local_review_si import analyze_review_locally
from ..services.platforms.google import GoogleBusinessAdapter

router = APIRouter()


class GoogleBusinessIntegrationRequest(BaseModel):
    access_token: SecretStr = Field(min_length=1, max_length=8192)
    refresh_token: SecretStr | None = Field(default=None, max_length=8192)
    external_account_id: str = Field(min_length=1, max_length=255)
    external_location_id: str = Field(min_length=1, max_length=255)

    @field_validator("access_token")
    @classmethod
    def strip_access_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value().strip()
        if not token:
            raise ValueError("Google Business access token must not be blank")
        return SecretStr(token)

    @field_validator("refresh_token")
    @classmethod
    def strip_refresh_token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        token = value.get_secret_value().strip()
        if not token:
            raise ValueError("Google Business refresh token must not be blank")
        return SecretStr(token)

    @field_validator("external_account_id", "external_location_id")
    @classmethod
    def strip_external_ids(cls, value: str) -> str:
        value = value.strip()
        if not value or "/" in value:
            raise ValueError("Provide a non-empty provider ID, not a resource path")
        return value


class GoogleBusinessIntegrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    external_account_id: str
    external_location_id: str
    is_active: bool


@router.put(
    "/integrations/google-business",
    response_model=GoogleBusinessIntegrationResponse,
    summary="Настроить интеграцию Google Business",
)
async def upsert_google_business_integration(
    body: GoogleBusinessIntegrationRequest,
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> PlatformIntegration:
    integration = await db.scalar(
        select(PlatformIntegration).where(
            PlatformIntegration.company_id == tenant_id,
            PlatformIntegration.platform == "google_business",
        )
    )
    if integration is None:
        integration = PlatformIntegration(
            company_id=tenant_id,
            platform="google_business",
            encrypted_api_key="pending-encryption",
            is_active=True,
        )
        db.add(integration)

    integration.api_key = body.access_token.get_secret_value()
    if body.refresh_token is not None:
        integration.refresh_token = body.refresh_token.get_secret_value()
    integration.external_account_id = body.external_account_id.strip()
    integration.external_location_id = body.external_location_id.strip()
    integration.is_active = True
    if not integration.external_account_id or not integration.external_location_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Google Business account and location IDs must not be blank",
        )
    await db.flush()
    return integration


@router.post(
    "/integrations/google-business/sync",
    status_code=status.HTTP_200_OK,
    summary="Синхронизировать отзывы через официальный Google Business API",
)
async def sync_google_business_reviews(
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> JSONResponse:
    integration = await db.scalar(
        select(PlatformIntegration).where(
            PlatformIntegration.company_id == tenant_id,
            PlatformIntegration.platform == "google_business",
            PlatformIntegration.is_active.is_(True),
        )
    )
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active Google Business integration not found",
        )

    now = datetime.now(timezone.utc)
    since = integration.last_synced_at or now - timedelta(days=30)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    await enforce_reviews_quota(db, tenant_id)
    adapter = GoogleBusinessAdapter(
        api_key=integration.api_key,
        refresh_token=integration.refresh_token,
        meta_config={
            "external_account_id": integration.external_account_id,
            "external_location_id": integration.external_location_id,
        },
    )
    source_reviews = await adapter.fetch_reviews(since)

    platform = await db.scalar(
        select(Platform).where(
            Platform.company_id == tenant_id,
            Platform.name == "Google Business Profile",
        )
    )
    if platform is None:
        platform = Platform(
            company_id=tenant_id,
            name="Google Business Profile",
            monthly_views=0,
            conversion_rate=0.0,
            cac_on_platform=0.0,
            average_rating=0.0,
        )
        db.add(platform)
        await db.flush()

    rows = []
    for source_review in source_reviews:
        analysis = analyze_review_locally(source_review.text, int(source_review.rating))
        rows.append(
            {
                "company_id": tenant_id,
                "platform_id": platform.id,
                "platform": "google_business",
                "author_name": "Автор отзыва",
                "rating": int(source_review.rating),
                "text": analysis.summary,
                "status": ReviewStatus.NEW.value,
                "financial_impact": 0.0,
                "created_at": source_review.date,
                "sentiment": analysis.sentiment,
                "threat_level": analysis.threat_level,
                "tags": list(analysis.tags),
                "analysis_tags": list(analysis.tags),
                "is_critical": analysis.is_critical,
                "is_analyzed": True,
                "ai_pending": False,
            }
        )

    inserted_count = 0
    if rows:
        result = await db.execute(
            insert(Review)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=[
                    Review.company_id,
                    Review.platform_id,
                    Review.created_at,
                    Review.rating,
                    Review.text,
                ]
            )
            .returning(Review.id)
        )
        inserted_count = len(result.scalars().all())

    integration.api_key = adapter.api_key
    integration.refresh_token = adapter.refresh_token
    integration.expires_at = adapter.expires_at or integration.expires_at
    integration.last_synced_at = now
    await db.flush()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "source": "google_business_official_api",
            "fetched": len(source_reviews),
            "stored": inserted_count,
            "raw_review_text_stored": False,
            "external_review_ids_stored": False,
        },
    )


@router.post(
    "/",
    status_code=201,
    summary="Создать платформу",
    description="Добавление новой платформы размещения отзывов",
)
async def create_platform(
    platform_data: PlatformBase,
    platform_repo: PlatformRepository = Depends(get_platform_repository),
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
                    "message": f"Платформа '{platform_data.name}' уже существует для данной компании",
                },
            },
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
                "company_id": str(created_platform.company_id),
            },
        },
    )


@router.get(
    "/{platform_id}",
    summary="Получить платформу",
    description="Детальная информация о платформе",
)
async def get_platform(
    platform_id: UUID,
    include_reviews: bool = Query(False, description="Включить отзывы"),
    platform_repo: PlatformRepository = Depends(get_platform_repository),
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
                    "message": f"Платформа с ID {platform_id} не найдена",
                },
            },
        )

    platform_data = {
        "id": str(platform.id),
        "company_id": str(platform.company_id),
        "name": platform.name,
        "monthly_views": platform.monthly_views,
        "conversion_rate": platform.conversion_rate,
        "cac_on_platform": platform.cac_on_platform,
        "average_rating": platform.average_rating,
    }

    if include_reviews and platform.reviews:
        platform_data["reviews"] = [
            {
                "id": str(review.id),
                "author_name": review.author_name,
                "rating": review.rating,
                "status": review.status.value,
                "financial_impact": review.financial_impact,
                "created_at": review.created_at.isoformat(),
            }
            for review in platform.reviews
        ]
        platform_data["reviews_count"] = len(platform.reviews)

    return JSONResponse(
        status_code=200, content={"success": True, "data": platform_data}
    )


@router.get(
    "/company/{company_id}/platforms",
    summary="Платформы компании",
    description="Получить все платформы конкретной компании",
)
async def get_company_platforms(
    company_id: UUID,
    platform_repo: PlatformRepository = Depends(get_platform_repository),
) -> JSONResponse:
    """
    Список всех платформ компании
    """

    platforms = await platform_repo.get_by_company_id(company_id)

    platforms_data = []
    for platform in platforms:
        platforms_data.append(
            {
                "id": str(platform.id),
                "name": platform.name,
                "monthly_views": platform.monthly_views,
                "conversion_rate": platform.conversion_rate,
                "average_rating": platform.average_rating,
                "cac_on_platform": platform.cac_on_platform,
            }
        )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "company_id": str(company_id),
                "platforms": platforms_data,
                "count": len(platforms_data),
            },
        },
    )


@router.put(
    "/{platform_id}",
    summary="Обновить платформу",
    description="Изменение данных платформы",
)
async def update_platform(
    platform_id: UUID,
    platform_data: PlatformBase,
    platform_repo: PlatformRepository = Depends(get_platform_repository),
) -> JSONResponse:
    """
    Обновление данных платформы
    """

    updated_platform = await platform_repo.update(
        platform_id, **platform_data.model_dump()
    )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Данные платформы обновлены",
            "data": {"id": str(updated_platform.id), "name": updated_platform.name},
        },
    )


@router.put(
    "/{platform_id}/metrics",
    summary="Обновить метрики платформы",
    description="Изменение показов, конверсии и CAC",
)
async def update_platform_metrics(
    platform_id: UUID,
    monthly_views: int | None = Query(None, ge=0, description="Ежемесячные показы"),
    conversion_rate: float | None = Query(
        None, ge=0, le=1, description="Конверсия (0-1)"
    ),
    cac_on_platform: float | None = Query(None, ge=0, description="CAC на платформе"),
    platform_repo: PlatformRepository = Depends(get_platform_repository),
) -> JSONResponse:
    """
    Обновление метрик платформы
    """

    updated_platform = await platform_repo.update_metrics(
        platform_id=platform_id,
        monthly_views=monthly_views,
        conversion_rate=conversion_rate,
        cac_on_platform=cac_on_platform,
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
                "cac_on_platform": updated_platform.cac_on_platform,
            },
        },
    )


@router.put(
    "/{platform_id}/recalculate-rating",
    summary="Пересчитать средний рейтинг",
    description="Обновление среднего рейтинга на основе отзывов",
)
async def recalculate_platform_rating(
    platform_id: UUID,
    platform_repo: PlatformRepository = Depends(get_platform_repository),
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
                "new_average_rating": updated_platform.average_rating,
            },
        },
    )


@router.get(
    "/stats",
    summary="Статистика платформ",
    description="Статистика всех или выбранных платформ",
)
async def get_platforms_stats(
    company_id: UUID | None = Query(None, description="Фильтр по компании"),
    platform_repo: PlatformRepository = Depends(get_platform_repository),
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
                "filtered_by_company": str(company_id) if company_id else None,
            },
        },
    )


@router.get(
    "/top-by-impact",
    summary="Топ платформ по влиянию",
    description="Платформы с наибольшим финансовым влиянием",
)
async def get_top_platforms_by_impact(
    limit: int = Query(10, ge=1, le=50, description="Количество платформ в топе"),
    company_id: UUID | None = Query(None, description="Фильтр по компании"),
    platform_repo: PlatformRepository = Depends(get_platform_repository),
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
                "filtered_by_company": str(company_id) if company_id else None,
            },
        },
    )


@router.delete(
    "/{platform_id}",
    summary="Удалить платформу",
    description="Удаление платформы и всех связанных отзывов",
)
async def delete_platform(
    platform_id: UUID,
    platform_repo: PlatformRepository = Depends(get_platform_repository),
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
            "data": {"platform_id": str(platform_id), "deleted": deleted},
        },
    )
