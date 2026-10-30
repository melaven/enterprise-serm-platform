"""
Роутеры для управления отзывами
HTTP-обработка запросов, валидация, делегирование в сервисы
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, column, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.tenant import verify_tenant_access
from app.api.schemas.analytics import (
    DashboardMetrics,
    DashboardMetricsResponse,
    DashboardReview,
    DashboardReviewsPage,
    DashboardReviewsResponse,
)
from app.api.schemas.economics import (
    AssistantReviewSchema,
    GenerateReplyResponse,
    ReviewBase,
    ReviewStatus,
    SubmitModerationRequest,
)
from app.api.schemas.ingest import ReviewIngestPayload, ReviewIngestResponse
from app.api.schemas.review import ReviewCreate, ReviewResponse
from app.application import SentimentService
from app.application.reviews.service import (
    ReviewApplicationService,
    ReviewQueue,
    ReviewReplyAnalyzer,
)
from app.core.auth import get_current_tenant
from app.core.dependencies import (
    get_review_queue,
    get_review_reply_analyzer,
    get_review_repository,
    get_sentiment_service,
    get_tenant_db,
)
from app.core.rate_limit import check_llm_limits
from app.infrastructure.persistence.models.economics import Review
from app.infrastructure.persistence.repositories import ReviewRepository
from app.infrastructure.persistence.repositories.analytics_repo import (
    get_dashboard_metrics,
)
from app.infrastructure.persistence.repositories.analytics_repo import (
    get_reviews_list as fetch_dashboard_reviews,
)

router = APIRouter()


@router.post(
    "/ingest",
    response_model=ReviewIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Поставить отзыв в очередь на безопасную обработку",
)
async def ingest_review(
    payload: ReviewIngestPayload,
    tenant_id: UUID = Depends(verify_tenant_access),
    arq_pool: ReviewQueue | None = Depends(get_review_queue),
) -> ReviewIngestResponse:
    """Queue an untrusted review payload for worker-side PII sanitization."""
    if arq_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review ingestion queue is unavailable",
        )

    job_id = uuid4()
    queued_at = datetime.now(timezone.utc)
    job = await arq_pool.enqueue_job(
        "process_review_ingestion",
        str(tenant_id),
        payload.model_dump(mode="json"),
        _job_id=str(job_id),
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review ingestion job could not be queued",
        )

    return ReviewIngestResponse(
        job_id=job_id,
        tenant_id=tenant_id,
        queued_at=queued_at,
    )


@router.post(
    "/",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый отзыв",
    description="Принять новый отзыв от внешней системы и сохранить в базу данных",
)
async def create_review(
    review_data: ReviewCreate,
    session: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
    arq_pool: ReviewQueue | None = Depends(get_review_queue),
) -> ReviewResponse:
    """Сохранить отзыв и поставить его анализ в ARQ без ожидания обработки."""
    service = ReviewApplicationService(
        session=session,
        tenant_id=tenant_id,
        arq_pool=arq_pool,
    )
    new_review = await service.create_review(
        platform_id=review_data.platform_id,
        rating=review_data.rating,
        text=review_data.text,
    )

    return ReviewResponse.model_validate(new_review)


@router.post(
    "/{review_id}/reply",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Опубликовать ответ на отзыв",
)
async def publish_review_reply(review_id: UUID) -> JSONResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Reply publishing is disabled because external review IDs are not stored",
    )


@router.post(
    "/{review_id}/approve-ai-response",
    status_code=status.HTTP_200_OK,
    summary="Подтвердить AI-ответ",
)
async def approve_ai_response(
    review_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> JSONResponse:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="AI response approval and automated publication are disabled",
    )


@router.post(
    "/webhook",
    status_code=status.HTTP_201_CREATED,
    summary="Webhook для получения отзывов от внешних систем",
    description="Endpoint для интеграции с внешними платформами отзывов",
)
async def receive_review_webhook(
    review_data: ReviewBase,
    session: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
    arq_pool: ReviewQueue | None = Depends(get_review_queue),
) -> JSONResponse:
    """Принять отзыв и поставить его обработку в ARQ очередь."""
    service = ReviewApplicationService(
        session=session,
        tenant_id=tenant_id,
        arq_pool=arq_pool,
    )
    review = await service.create_review(
        platform_id=review_data.platform_id,
        rating=review_data.rating,
        text=review_data.text,
        review_status=review_data.status,
        financial_impact=review_data.financial_impact,
    )

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "Отзыв принят и поставлен в очередь обработки",
            "data": {
                "review_id": str(review.id),
                "status": review.state.value,
                "queued": True,
            },
        },
    )


@router.get(
    "/details/{review_id}",
    summary="Получить отзыв по ID",
    description="Детальная информация об отзыве",
)
async def get_review(
    review_id: UUID, review_repo: ReviewRepository = Depends(get_review_repository)
) -> JSONResponse:
    """
    Получение полной информации об отзыве
    включая данные платформы и компании
    """

    review = await review_repo.get_with_platform_and_company(review_id)
    if not review:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "type": "NotFoundError",
                    "message": f"Отзыв с ID {review_id} не найден",
                },
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "review_id": str(review.id),
                "platform_name": review.platform_ref.name,
                "company_name": review.platform_ref.company.name,
                "author_name": review.author_name,
                "rating": review.rating,
                "text": review.text,
                "status": review.status.value,
                "financial_impact": review.financial_impact,
                "si_response": review.si_response,
                "created_at": review.created_at.isoformat(),
            },
        },
    )


@router.get(
    "/platform/{platform_id}/reviews",
    summary="Отзывы по платформе",
    description="Получить отзывы для конкретной платформы с фильтрацией",
)
async def get_platform_reviews(
    platform_id: UUID,
    limit: int = Query(50, ge=1, le=200, description="Количество отзывов"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    status: ReviewStatus | None = Query(None, description="Фильтр по статусу"),
    min_rating: int | None = Query(None, ge=1, le=5, description="Минимальный рейтинг"),
    max_rating: int | None = Query(
        None, ge=1, le=5, description="Максимальный рейтинг"
    ),
    review_repo: ReviewRepository = Depends(get_review_repository),
) -> JSONResponse:
    """
    Получить отзывы для платформы с возможностью фильтрации:
    - По статусу обработки
    - По диапазону рейтингов
    - С пагинацией
    """

    # Получаем отзывы с базовой фильтрацией
    if min_rating and max_rating:
        reviews = await review_repo.get_by_rating_range(
            platform_id, min_rating, max_rating
        )
    else:
        reviews = await review_repo.get_by_platform_id(
            platform_id, limit, offset, status
        )

    # Преобразуем в JSON-формат
    reviews_data = []
    for review in reviews:
        reviews_data.append(
            {
                "review_id": str(review.id),
                "author_name": review.author_name,
                "rating": review.rating,
                "text": review.text,
                "status": review.status.value,
                "financial_impact": review.financial_impact,
                "has_response": bool(review.si_response),
                "created_at": review.created_at.isoformat(),
            }
        )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "platform_id": str(platform_id),
                "reviews": reviews_data,
                "count": len(reviews_data),
                "pagination": {"limit": limit, "offset": offset},
            },
        },
    )


@router.get(
    "/platform/{platform_id}/stats",
    summary="Статистика отзывов платформы",
    description="Аналитика отзывов за указанный период",
)
async def get_platform_review_stats(
    platform_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Период анализа в днях"),
    review_repo: ReviewRepository = Depends(get_review_repository),
) -> JSONResponse:
    """
    Статистика отзывов платформы:
    - Распределение по рейтингам
    - Статусы обработки
    - Финансовое влияние
    - Динамика за период
    """

    stats = await review_repo.get_reviews_stats(platform_id, days)

    return JSONResponse(status_code=200, content={"success": True, "data": stats})


@router.put(
    "/{review_id}/status",
    summary="Обновить статус отзыва",
    description="Изменение статуса обработки отзыва",
)
async def update_review_status(
    review_id: UUID,
    new_status: ReviewStatus,
    si_response: str | None = None,
    session: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
) -> JSONResponse:
    """
    Обновление статуса отзыва:
    - Смена статуса обработки
    - Сохранение ответа SI отдельно от privacy-constrained таблицы reviews
    """

    service = ReviewApplicationService(session=session, tenant_id=tenant_id)
    updated_review, has_response = await service.update_status(
        review_id=review_id,
        new_status=new_status,
        si_response=si_response,
    )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Статус отзыва обновлен",
            "data": {
                "review_id": str(updated_review.id),
                "new_status": updated_review.status.value,
                "has_response": has_response,
            },
        },
    )


@router.get(
    "/search",
    summary="Поиск отзывов",
    description="Поиск отзывов по содержимому текста или автору",
)
async def search_reviews(
    query: str = Query(..., min_length=2, description="Поисковый запрос"),
    platform_id: UUID | None = Query(None, description="Фильтр по платформе"),
    limit: int = Query(
        50, ge=1, le=100, description="Максимальное количество результатов"
    ),
    review_repo: ReviewRepository = Depends(get_review_repository),
) -> JSONResponse:
    """
    Поиск отзывов по тексту или имени автора
    """

    reviews = await review_repo.search_by_content(
        search_term=query, platform_id=platform_id, limit=limit
    )

    # Форматируем результаты
    search_results = []
    for review in reviews:
        search_results.append(
            {
                "review_id": str(review.id),
                "author_name": review.author_name,
                "rating": review.rating,
                "text": review.text[:200] + "..."
                if len(review.text) > 200
                else review.text,
                "platform_id": str(review.platform_id),
                "created_at": review.created_at.isoformat(),
            }
        )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "query": query,
                "results": search_results,
                "count": len(search_results),
            },
        },
    )


@router.get(
    "/sentiment-analysis/{review_id}",
    summary="🔒 Анализ тональности отзыва [Rate Limited]",
    description="LLM-анализ тональности и рекомендации (20 req/min)",
)
async def analyze_review_sentiment(
    review_id: UUID,
    limits: dict = Depends(check_llm_limits),
    review_repo: ReviewRepository = Depends(get_review_repository),
    sentiment_service: SentimentService = Depends(get_sentiment_service),
) -> JSONResponse:
    """
    Анализ тональности конкретного отзыва (LLM-powered):
    - Определение эмоциональной окраски
    - Приоритет обработки
    - Рекомендации по времени ответа

    **Rate Limiting:**
    - Лимит: 20 запросов / 60 секунд
    - 429 Too Many Requests при превышении
    - X-RateLimit-* headers в ответе

    **Quota Check:**
    - 402 Payment Required при исчерпании тарифа
    """

    review = await review_repo.get_by_id_or_404(review_id)

    sentiment_analysis = sentiment_service.analyze_sentiment(
        rating=review.rating, review_text=review.text
    )

    recommendations = sentiment_service.get_processing_recommendations(
        sentiment_analysis
    )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "review_id": str(review_id),
                "sentiment_analysis": sentiment_analysis,
                "processing_recommendations": recommendations,
                "limits": limits,  # Информация о лимитах: rate + quota
            },
        },
    )


@router.get(
    "/requiring-attention",
    summary="Отзывы, требующие внимания",
    description="Негативные отзывы без ответа, требующие срочной обработки",
)
async def get_reviews_requiring_attention(
    max_hours: int = Query(
        24, ge=1, le=168, description="Максимальное время без ответа (часы)"
    ),
    review_repo: ReviewRepository = Depends(get_review_repository),
) -> JSONResponse:
    """
    Получить отзывы, требующие внимания:
    - Негативные отзывы без ответа
    - Превысившие временной лимит
    - С полной информацией о платформе и компании
    """

    reviews = await review_repo.get_reviews_requiring_attention(max_hours)

    urgent_reviews = []
    for review in reviews:
        time_since_creation = datetime.utcnow() - review.created_at
        hours_without_response = time_since_creation.total_seconds() / 3600

        urgent_reviews.append(
            {
                "review_id": str(review.id),
                "platform_name": review.platform_ref.name,
                "company_name": review.platform_ref.company.name,
                "author_name": review.author_name,
                "rating": review.rating,
                "text": review.text,
                "created_at": review.created_at.isoformat(),
                "hours_without_response": round(hours_without_response, 1),
                "urgency": "critical" if hours_without_response > 48 else "high",
            }
        )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "reviews": urgent_reviews,
                "count": len(urgent_reviews),
                "threshold_hours": max_hours,
            },
        },
    )


# ============================================================================
# DASHBOARD API ENDPOINTS - для фронтенд-дашборда
# ============================================================================


@router.get(
    "",
    response_model=DashboardReviewsResponse,
    summary="Список отзывов с пагинацией",
    description="Основной эндпоинт для отображения отзывов в дашборде с tenant-изоляцией",
)
async def get_reviews_list(
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    limit: int | None = Query(None, ge=1, le=100, description="Размер страницы"),
    offset: int | None = Query(None, ge=0, description="Смещение для пагинации"),
    platform: str | None = Query(
        None, description="Фильтр по платформе (google, 2gis и т.д.)"
    ),
    rating: int | None = Query(None, ge=1, le=5, description="Фильтр по рейтингу"),
    sentiment: str | None = Query(None, description="Фильтр по тональности"),
    search: str | None = Query(None, min_length=1, max_length=200),
    sort_by: str = Query(
        "created_at", pattern="^(created_at|rating)$", description="Поле сортировки"
    ),
    sort_order: str = Query(
        "desc", pattern="^(asc|desc)$", description="Порядок сортировки: asc или desc"
    ),
    tenant_id: UUID = Depends(verify_tenant_access),
    db: AsyncSession = Depends(get_tenant_db),
) -> DashboardReviewsResponse:
    """
    Получить список отзывов с пагинацией и фильтрацией.

    **RLS изоляция:** Автоматическая фильтрация по tenant_id через RLS политику.

    **Параметры:**
    - page: номер страницы (начиная с 1)
    - page_size: количество отзывов на странице (максимум 100)
    - platform: фильтр по названию платформы
    - rating: фильтр по рейтингу (1-5)
    - sentiment: фильтр по тональности (positive, neutral, negative)
    - sort_by: поле для сортировки (created_at, rating)
    - sort_order: порядок сортировки (asc, desc)

    **Возвращает:**
    - items: массив отзывов
    - total: общее количество отзывов (с учётом фильтров)
    - page: текущая страница
    - page_size: размер страницы
    - total_pages: общее количество страниц
    """

    effective_page_size = limit or page_size
    effective_offset = (
        offset if offset is not None else (page - 1) * effective_page_size
    )
    response_page = effective_offset // effective_page_size + 1
    filters = [Review.company_id == tenant_id]

    if platform:
        # Используем column() для обращения к text-колонке platform
        # (в модели есть конфликт: relationship platform перекрывает column platform)
        filters.append(column("platform") == platform)

    if rating is not None:
        filters.append(Review.rating == rating)

    if sentiment:
        filters.append(func.upper(Review.sentiment) == sentiment.upper())

    if search:
        search_term = search.strip().lower()
        if search_term:
            filters.append(
                or_(
                    func.lower(Review.text).contains(search_term, autoescape=True),
                    func.lower(Review.author_name).contains(
                        search_term, autoescape=True
                    ),
                )
            )

    count_query = select(func.count(Review.id)).where(and_(*filters))
    total_result = await db.execute(count_query)
    total = int(total_result.scalar_one())

    if (
        platform is None
        and rating is None
        and sentiment is None
        and search is None
        and sort_by == "created_at"
        and sort_order == "desc"
    ):
        reviews = await fetch_dashboard_reviews(
            db, tenant_id, effective_page_size, effective_offset
        )
    else:
        query = select(Review).where(and_(*filters))
        sort_column = {
            "created_at": Review.created_at,
            "rating": Review.rating,
        }[sort_by]
        ordering = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        result = await db.execute(
            query.order_by(ordering).limit(effective_page_size).offset(effective_offset)
        )
        reviews = list(result.scalars().all())

    total_pages = (
        (total + effective_page_size - 1) // effective_page_size if total > 0 else 0
    )

    return DashboardReviewsResponse(
        success=True,
        data=DashboardReviewsPage(
            items=[DashboardReview.model_validate(review) for review in reviews],
            total=total,
            page=response_page,
            page_size=effective_page_size,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/summary",
    response_model=DashboardMetricsResponse,
    summary="KPI-метрики дашборда",
    description="Сводка по отзывам: всего, тональность, критичные проблемы",
)
async def get_reviews_summary(
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> DashboardMetricsResponse:
    """
    Получить KPI-метрики для дашборда в контексте авторизованного tenant.
    """
    metrics = await get_dashboard_metrics(db, tenant_id)
    return DashboardMetricsResponse(
        success=True,
        data=DashboardMetrics(**metrics),
    )


# ============================================================================
# ASSISTANT API ENDPOINTS - для рабочего места SI-Ассистента
# ============================================================================


@router.get(
    "/assistant",
    response_model=list[AssistantReviewSchema],
    summary="Список отзывов для ассистента",
    description="Получить отзывы для рабочего места ассистента с фильтрацией",
)
async def get_assistant_reviews(
    filter: str = Query(
        "all",
        pattern="^(all|negative|unanswered)$",
        description="Фильтр: all, negative, unanswered",
    ),
    branch_id: UUID | None = Query(None, description="Фильтр по филиалу"),
    limit: int = Query(50, ge=1, le=100, description="Количество отзывов"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    session: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
) -> list[AssistantReviewSchema]:
    """
    Получить список отзывов для рабочего места ассистента.

    **RLS изоляция:** Автоматическая фильтрация по tenant_id через RLS политику.

    **Параметры:**
    - filter: all (все), negative (только негативные), unanswered (без ответа)
    - branch_id: фильтр по филиалу (опционально)
    - limit: количество отзывов (максимум 100)
    - offset: смещение для пагинации

    **FSM статус moderation_status:**
    - new: новый отзыв без ответа
    - drafted: черновик ответа сгенерирован
    - pending_moderation: отправлен на модерацию
    - approved: одобрен модератором
    - published: ответ опубликован
    """
    service = ReviewApplicationService(session=session, tenant_id=tenant_id)
    return await service.list_assistant_reviews(filter, branch_id, limit, offset)


@router.post(
    "/{review_id}/generate-reply",
    response_model=GenerateReplyResponse,
    summary="Сгенерировать ответ на отзыв",
    description="Создать ответ из зашифрованного текста отзыва без сохранения ответа",
)
async def generate_reply(
    review_id: UUID,
    session: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
    analyzer: ReviewReplyAnalyzer = Depends(get_review_reply_analyzer),
) -> GenerateReplyResponse:
    service = ReviewApplicationService(
        session=session,
        tenant_id=tenant_id,
        analyzer=analyzer,
    )
    return GenerateReplyResponse(
        review_id=review_id,
        suggested_reply=await service.generate_reply(review_id),
    )


@router.post(
    "/{review_id}/submit-moderation",
    response_model=AssistantReviewSchema,
    summary="Отправить ответ на модерацию",
    description="Сохранить ответ и отправить на модерацию (FSM переход: drafted -> pending_moderation)",
)
async def submit_moderation(
    review_id: UUID,
    request: SubmitModerationRequest,
    session: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
) -> AssistantReviewSchema:
    """
    Отправить ответ на модерацию.

    **FSM переход:** drafted -> pending_moderation

    **Валидация:**
    - Переход разрешен только из статуса drafted
    - Текст ответа должен быть непустым (1-4000 символов)
    - Никакой автопубликации!

    **RLS изоляция:** Проверка прав доступа к отзыву через tenant_id.
    """
    service = ReviewApplicationService(session=session, tenant_id=tenant_id)
    return await service.submit_moderation(review_id, request.resolved_text)


@router.post(
    "/{review_id}/approve-moderation",
    response_model=AssistantReviewSchema,
    summary="Одобрить ответ на отзыв",
    description="Одобрить модерируемый ответ без его публикации",
)
async def approve_moderation(
    review_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant),
) -> AssistantReviewSchema:
    """Одобрить ответ, сохранив публикацию отдельным отключенным сценарием."""
    service = ReviewApplicationService(session=db, tenant_id=tenant_id)
    return await service.approve_moderation(review_id)
