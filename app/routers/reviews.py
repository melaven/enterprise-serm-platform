"""
Роутеры для управления отзывами
HTTP-обработка запросов, валидация, делегирование в сервисы
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from ..schemas.economics import ReviewBase, ReviewResponse, ReviewStatus
from ..dependencies import (
    get_review_repository, 
    get_review_processor_service,
    get_sentiment_service
)
from ..repositories import ReviewRepository
from ..services import ReviewProcessorService, SentimentService


router = APIRouter()


@router.post("/webhook",
             status_code=status.HTTP_201_CREATED,
             summary="Webhook для получения отзывов от внешних систем",
             description="Endpoint для интеграции с внешними платформами отзывов")
async def receive_review_webhook(
    review_data: ReviewBase,
    processor: ReviewProcessorService = Depends(get_review_processor_service)
) -> JSONResponse:
    """
    Webhook для получения отзывов от внешних систем:
    - Google Maps, 2GIS, Trustpilot и др.
    - Автоматическая обработка и анализ
    - Генерация ответов для критических случаев
    """
    
    # Полная обработка отзыва через сервис
    result = await processor.process_new_review(review_data)
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "Отзыв успешно получен и обработан",
            "data": {
                "review_id": result["review_id"],
                "status": result["status"],
                "priority": result["sentiment_analysis"]["priority"],
                "financial_impact": result["financial_impact"]["financial_impact"],
                "response_generated": bool(result["generated_response"])
            }
        }
    )


@router.get("/{review_id}",
            summary="Получить отзыв по ID",
            description="Детальная информация об отзыве")
async def get_review(
    review_id: UUID,
    review_repo: ReviewRepository = Depends(get_review_repository)
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
                    "message": f"Отзыв с ID {review_id} не найден"
                }
            }
        )
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "review_id": str(review.id),
                "platform_name": review.platform.name,
                "company_name": review.platform.company.name,
                "author_name": review.author_name,
                "rating": review.rating,
                "text": review.text,
                "status": review.status.value,
                "financial_impact": review.financial_impact,
                "si_response": review.si_response,
                "created_at": review.created_at.isoformat()
            }
        }
    )


@router.get("/platform/{platform_id}/reviews",
            summary="Отзывы по платформе",
            description="Получить отзывы для конкретной платформы с фильтрацией")
async def get_platform_reviews(
    platform_id: UUID,
    limit: int = Query(50, ge=1, le=200, description="Количество отзывов"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    status: Optional[ReviewStatus] = Query(None, description="Фильтр по статусу"),
    min_rating: Optional[int] = Query(None, ge=1, le=5, description="Минимальный рейтинг"),
    max_rating: Optional[int] = Query(None, ge=1, le=5, description="Максимальный рейтинг"),
    review_repo: ReviewRepository = Depends(get_review_repository)
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
        reviews_data.append({
            "review_id": str(review.id),
            "author_name": review.author_name,
            "rating": review.rating,
            "text": review.text,
            "status": review.status.value,
            "financial_impact": review.financial_impact,
            "has_response": bool(review.si_response),
            "created_at": review.created_at.isoformat()
        })
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "platform_id": str(platform_id),
                "reviews": reviews_data,
                "count": len(reviews_data),
                "pagination": {
                    "limit": limit,
                    "offset": offset
                }
            }
        }
    )


@router.get("/platform/{platform_id}/stats",
            summary="Статистика отзывов платформы",
            description="Аналитика отзывов за указанный период")
async def get_platform_review_stats(
    platform_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Период анализа в днях"),
    review_repo: ReviewRepository = Depends(get_review_repository)
) -> JSONResponse:
    """
    Статистика отзывов платформы:
    - Распределение по рейтингам
    - Статусы обработки
    - Финансовое влияние
    - Динамика за период
    """
    
    stats = await review_repo.get_reviews_stats(platform_id, days)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": stats
        }
    )


@router.put("/{review_id}/status",
            summary="Обновить статус отзыва",
            description="Изменение статуса обработки отзыва")
async def update_review_status(
    review_id: UUID,
    new_status: ReviewStatus,
    si_response: Optional[str] = None,
    review_repo: ReviewRepository = Depends(get_review_repository)
) -> JSONResponse:
    """
    Обновление статуса отзыва:
    - Смена статуса обработки
    - Добавление ответа SI (опционально)
    - Пересчет финансового влияния
    """
    
    updated_review = await review_repo.update_status_and_response(
        review_id=review_id,
        status=new_status,
        si_response=si_response
    )
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Статус отзыва обновлен",
            "data": {
                "review_id": str(updated_review.id),
                "new_status": updated_review.status.value,
                "has_response": bool(updated_review.si_response)
            }
        }
    )


@router.get("/search",
            summary="Поиск отзывов",
            description="Поиск отзывов по содержимому текста или автору")
async def search_reviews(
    query: str = Query(..., min_length=2, description="Поисковый запрос"),
    platform_id: Optional[UUID] = Query(None, description="Фильтр по платформе"),
    limit: int = Query(50, ge=1, le=100, description="Максимальное количество результатов"),
    review_repo: ReviewRepository = Depends(get_review_repository)
) -> JSONResponse:
    """
    Поиск отзывов по тексту или имени автора
    """
    
    reviews = await review_repo.search_by_content(
        search_term=query,
        platform_id=platform_id,
        limit=limit
    )
    
    # Форматируем результаты
    search_results = []
    for review in reviews:
        search_results.append({
            "review_id": str(review.id),
            "author_name": review.author_name,
            "rating": review.rating,
            "text": review.text[:200] + "..." if len(review.text) > 200 else review.text,
            "platform_id": str(review.platform_id),
            "created_at": review.created_at.isoformat()
        })
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "query": query,
                "results": search_results,
                "count": len(search_results)
            }
        }
    )


@router.get("/sentiment-analysis/{review_id}",
            summary="Анализ тональности отзыва",
            description="Детальный анализ тональности и рекомендации")
async def analyze_review_sentiment(
    review_id: UUID,
    review_repo: ReviewRepository = Depends(get_review_repository),
    sentiment_service: SentimentService = Depends(get_sentiment_service)
) -> JSONResponse:
    """
    Анализ тональности конкретного отзыва:
    - Определение эмоциональной окраски
    - Приоритет обработки
    - Рекомендации по времени ответа
    """
    
    review = await review_repo.get_by_id_or_404(review_id)
    
    sentiment_analysis = sentiment_service.analyze_sentiment(
        rating=review.rating,
        review_text=review.text
    )
    
    recommendations = sentiment_service.get_processing_recommendations(sentiment_analysis)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "review_id": str(review_id),
                "sentiment_analysis": sentiment_analysis,
                "processing_recommendations": recommendations
            }
        }
    )


@router.get("/requiring-attention",
            summary="Отзывы, требующие внимания",
            description="Негативные отзывы без ответа, требующие срочной обработки")
async def get_reviews_requiring_attention(
    max_hours: int = Query(24, ge=1, le=168, description="Максимальное время без ответа (часы)"),
    review_repo: ReviewRepository = Depends(get_review_repository)
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
        
        urgent_reviews.append({
            "review_id": str(review.id),
            "platform_name": review.platform.name,
            "company_name": review.platform.company.name,
            "author_name": review.author_name,
            "rating": review.rating,
            "text": review.text,
            "created_at": review.created_at.isoformat(),
            "hours_without_response": round(hours_without_response, 1),
            "urgency": "critical" if hours_without_response > 48 else "high"
        })
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "reviews": urgent_reviews,
                "count": len(urgent_reviews),
                "threshold_hours": max_hours
            }
        }
    )