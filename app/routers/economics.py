"""
Роутеры для экономических операций SERM
Только HTTP-обработка, валидация, делегирование в сервисы
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..schemas.economics import ReviewBase, ReviewResponse
from ..dependencies import get_review_processor_service, get_economics_service
from ..services import ReviewProcessorService, EconomicsService


router = APIRouter()


@router.post("/simulate", 
             summary="Симуляция финансового влияния отзыва",
             description="Моделирование экономического влияния отзыва без сохранения в БД")
async def simulate_review_impact(
    review_data: ReviewBase,
    processor: ReviewProcessorService = Depends(get_review_processor_service)
) -> JSONResponse:
    """
    Симуляция влияния отзыва на экономические показатели
    
    - **platform_id**: ID платформы размещения
    - **rating**: Рейтинг отзыва (1-5)
    - **text**: Текст отзыва
    - **author_name**: Имя автора
    - **status**: Статус обработки (опционально)
    """
    
    # Делегируем всю логику в сервис
    simulation_result = await processor.simulate_review_impact(review_data)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Симуляция выполнена успешно",
            "data": simulation_result
        }
    )


@router.post("/process",
             summary="Обработка реального отзыва", 
             description="Полная обработка отзыва с сохранением в БД и генерацией ответа")
async def process_review(
    review_data: ReviewBase,
    processor: ReviewProcessorService = Depends(get_review_processor_service)
) -> JSONResponse:
    """
    Полная обработка нового отзыва:
    - Анализ тональности
    - Расчет финансового влияния  
    - Генерация ответа (при необходимости)
    - Сохранение в базе данных
    """
    
    result = await processor.process_new_review(review_data)
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "Отзыв успешно обработан",
            "data": result
        }
    )


@router.post("/bulk-process",
             summary="Массовая обработка отзывов",
             description="Обработка множественных отзывов одним запросом")
async def bulk_process_reviews(
    reviews_data: List[ReviewBase],
    processor: ReviewProcessorService = Depends(get_review_processor_service)
) -> JSONResponse:
    """
    Массовая обработка отзывов для импорта или синхронизации
    """
    
    if len(reviews_data) > 100:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "type": "ValidationError",
                    "message": "Максимум 100 отзывов за один запрос"
                }
            }
        )
    
    result = await processor.bulk_process_reviews(reviews_data)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": f"Обработано {result['summary']['success']} из {result['summary']['total']} отзывов",
            "data": result
        }
    )


@router.get("/platform/{platform_id}/roi",
            summary="ROI платформы",
            description="Расчет возврата инвестиций для платформы")
async def get_platform_roi(
    platform_id: UUID,
    economics: EconomicsService = Depends(get_economics_service)
) -> JSONResponse:
    """
    Расчет ROI (возврат инвестиций) для конкретной платформы
    на основе финансового влияния всех отзывов
    """
    
    roi_data = await economics.calculate_platform_roi(platform_id)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": roi_data
        }
    )


@router.get("/platform/{platform_id}/risk-assessment",
            summary="Оценка рисков потери LTV",
            description="Анализ рисков на основе негативных отзывов без ответа")
async def get_ltv_risk_assessment(
    platform_id: UUID,
    hours_threshold: int = Query(24, ge=1, le=168, description="Порог времени без ответа (часы)"),
    economics: EconomicsService = Depends(get_economics_service)
) -> JSONResponse:
    """
    Оценка риска потери LTV из-за негативных отзывов
    без своевременного реагирования
    """
    
    risk_data = await economics.calculate_ltv_risk_assessment(
        platform_id=platform_id,
        time_without_response_hours=hours_threshold
    )
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": risk_data
        }
    )


@router.get("/processing-queue",
            summary="Очередь отзывов для обработки",
            description="Список отзывов, требующих внимания, отсортированный по приоритету")
async def get_processing_queue(
    priority: Optional[str] = Query(None, regex="^(critical|high|medium|low)$", description="Фильтр по приоритету"),
    processor: ReviewProcessorService = Depends(get_review_processor_service)
) -> JSONResponse:
    """
    Получить очередь отзывов для обработки:
    - Негативные отзывы без ответа
    - Отсортированы по приоритету и времени создания
    - Можно фильтровать по уровню приоритета
    """
    
    queue_data = await processor.get_review_processing_queue(priority_filter=priority)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": queue_data
        }
    )
