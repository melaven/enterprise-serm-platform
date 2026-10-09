"""
Production-ready Parser API endpoints для ARQ задач
Включает LLM-аналитику отзывов
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
from arq.connections import create_pool
from arq.jobs import Job, JobStatus
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

router = APIRouter(prefix="/api/v1/parsers", tags=["Parsers"])

# 1. Схемы запросов и ответов
class ParserStartRequest(BaseModel):
    url: HttpUrl
    company_id: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None

# 2. Функция для настройки Redis (без dependency injection для упрощения)
def get_redis_settings():
    """Получение настроек Redis для ARQ"""
    from arq.connections import RedisSettings
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    if redis_url.startswith("redis://"):
        url_parts = redis_url.replace("redis://", "").split("/")
        host_port = url_parts[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 6379
        database = int(url_parts[1]) if len(url_parts) > 1 else 0
        
        return RedisSettings(host=host, port=port, database=database)
    else:
        return RedisSettings.from_dsn(redis_url)

# 3. Dependency для получения пула Redis
async def get_redis_pool():
    """Создание пула Redis подключений"""
    redis_settings = get_redis_settings()
    return await create_pool(redis_settings)

# 4. Эндпоинт постановки задачи в очередь с LLM-аналитикой
@router.post("/start", summary="Запуск парсинга с LLM-аналитикой")
async def start_parser(request: ParserStartRequest, redis=Depends(get_redis_pool)):
    """
    Запускает фоновую задачу парсинга отзывов с LLM-аналитикой:
    - Парсинг отзывов с указанного URL
    - Анализ тональности (Positive/Neutral/Negative) 
    - Извлечение тегов из текста
    - Генерация предлагаемых ответов
    """
    try:
        job = await redis.enqueue_job(
            'fetch_reviews_task',
            platform_url=str(request.url),
            company_id=request.company_id
        )
        
        if not job:
            raise HTTPException(status_code=500, detail="Не удалось поставить задачу в очередь")
            
        return {
            "job_id": job.job_id, 
            "status": "queued",
            "message": "Задача парсинга с LLM-аналитикой поставлена в очередь",
            "platform_url": str(request.url),
            "company_id": request.company_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка постановки задачи: {str(e)}")
    
    finally:
        await redis.close()

# 5. Эндпоинт проверки статуса задачи
@router.get("/status/{job_id}", response_model=JobStatusResponse, summary="Статус задачи парсинга")
async def get_job_status(job_id: str, redis=Depends(get_redis_pool)):
    """
    Проверяет статус задачи парсинга и возвращает результаты LLM-аналитики:
    - queued: задача в очереди
    - in_progress: задача выполняется
    - complete: задача завершена с результатами
    - not_found: задача не найдена
    """
    try:
        job = Job(job_id, redis)
        
        try:
            status: JobStatus = await job.status()
        except Exception:
            raise HTTPException(status_code=404, detail="Задача не найдена")

        response_data = {
            "job_id": job_id,
            "status": status.value
        }

        # Если задача завершена, получаем результат с LLM-аналитикой
        if status == JobStatus.complete:
            try:
                result = await job.result(timeout=1)
                response_data["result"] = {
                    "info": "Парсинг и LLM-аналитика успешно завершены", 
                    "data": result,
                    "llm_features": {
                        "sentiment_analysis": "Анализ тональности отзывов",
                        "tag_extraction": "Извлечение ключевых тегов",
                        "response_generation": "Генерация предлагаемых ответов"
                    }
                }
            except Exception as e:
                response_data["result"] = {"error": str(e)}
        elif status == JobStatus.in_progress:
            response_data["message"] = "Выполняется LLM-анализ отзывов..."
        elif status == JobStatus.queued:
            response_data["message"] = "Задача ожидает выполнения в очереди"

        return response_data
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")
    
    finally:
        await redis.close()

# 6. Эндпоинт получения статистики очереди
@router.get("/queue/stats", summary="Статистика очереди ARQ")
async def get_queue_stats(redis=Depends(get_redis_pool)):
    """
    Возвращает статистику очереди ARQ задач
    """
    try:
        # Получаем информацию о Redis и очереди
        info = await redis.info()
        
        return {
            "redis_info": {
                "version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            },
            "queue_info": {
                "default_queue": "arq:queue",
                "worker_functions": ["fetch_reviews_task"],
                "features": [
                    "LLM sentiment analysis", 
                    "Tag extraction",
                    "Response generation",
                    "Financial impact calculation"
                ]
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")
    
    finally:
        await redis.close()