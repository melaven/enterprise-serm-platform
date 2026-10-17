import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl, model_validator
from session import get_tenant_session
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentPayload
from app.core.rate_limit import check_parser_limits
from app.services.entitlement import enforce_reviews_quota
from app.services.parser_queue import ParserQueueManager

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/parser", tags=["parser"])

# Poll interval для SSE status stream (секунды)
_JOB_STATUS_POLL_INTERVAL_SECONDS = 2.0


# Dependency для ParserQueueManager
async def get_parser_queue() -> ParserQueueManager:
    """Dependency: возвращает ParserQueueManager singleton."""
    from app.core.dependencies import get_parser_queue_manager

    return await get_parser_queue_manager()


class ParseRequest(BaseModel):
    platform: Literal["2gis"]
    url: HttpUrl

    @model_validator(mode="after")
    def _validate_url(self) -> "ParseRequest":
        """Валидация URL для безопасности (SSRF protection)"""
        url_str = str(self.url)
        # Базовая проверка что это 2GIS URL
        if "2gis" not in url_str.lower():
            raise ValueError("URL must be a valid 2GIS link")
        return self


class ParseJobOut(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"


@router.post("/jobs", response_model=ParseJobOut, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_fetch_reviews(
    body: ParseRequest,
    auth: CurrentPayload,
    session: AsyncSession = Depends(get_tenant_session),
    queue: ParserQueueManager = Depends(get_parser_queue),
    _rate_limit: None = Depends(check_parser_limits),
) -> ParseJobOut:
    """
    Постановка задачи парсинга в очередь.

    Returns 202 Accepted с job_id для отслеживания статуса.
    """
    url = str(body.url)
    company_id = auth.tenant_id or auth.sub
    await enforce_reviews_quota(session, company_id)

    # Создаем запрос для ParserQueueManager
    from app.services.parser_queue import ParserJobRequest

    request = ParserJobRequest(
        platform=body.platform,
        url=url,
    )

    # Ставим задачу в очередь
    response = await queue.enqueue_parser_job(company_id, request)

    log.info("parser_enqueued", job_id=response.job_id, platform=body.platform)

    return ParseJobOut(job_id=response.job_id)


async def _sse_status_generator(
    job_id: str,
    tenant_id: str,
    queue: ParserQueueManager,
) -> AsyncGenerator[str, None]:
    """
    SSE generator для real-time статусов парсера.

    Формат событий:
    - event: status
    - data: {"state": "queued" | "in_progress" | "analyzing" | "succeeded" | "failed", ...}

    Терминальные статусы: succeeded, failed
    """
    from uuid import UUID

    previous_state = None

    while True:
        try:
            # Получаем текущий статус задачи
            status_obj = await queue.get_job_status(job_id, UUID(tenant_id))

            # Маппинг статусов backend → frontend
            state_map = {
                "queued": "queued",
                "in_progress": "in_progress",
                "complete": "succeeded",
                "failed": "failed",
            }

            current_state = state_map.get(status_obj.status, status_obj.status)

            # Если есть progress.stage == "analyzing", отправляем особый статус
            if (
                status_obj.progress
                and isinstance(status_obj.progress, dict)
                and status_obj.progress.get("stage") == "analyzing"
            ):
                current_state = "analyzing"

            # Отправляем событие только если статус изменился
            if current_state != previous_state:
                event_data = {
                    "state": current_state,
                    "job_id": job_id,
                    "progress": status_obj.progress,
                    "result": status_obj.result,
                    "error": status_obj.error,
                }

                yield "event: status\n"
                yield f"data: {json.dumps(event_data)}\n\n"

                previous_state = current_state

                log.info("sse_status_sent", job_id=job_id, state=current_state)

            # Завершаем stream на терминальных статусах
            if current_state in ("succeeded", "failed"):
                log.info("sse_stream_closed", job_id=job_id, final_state=current_state)
                break

            # Ждем перед следующим poll
            await asyncio.sleep(_JOB_STATUS_POLL_INTERVAL_SECONDS)

        except Exception as e:
            log.error("sse_status_error", job_id=job_id, error=str(e))
            error_data = {
                "state": "failed",
                "job_id": job_id,
                "error": f"Internal error: {str(e)}",
            }
            yield "event: status\n"
            yield f"data: {json.dumps(error_data)}\n\n"
            break


@router.get("/stream/{job_id}")
async def stream_parser_status(
    job_id: str,
    auth: CurrentPayload,
    queue: ParserQueueManager = Depends(get_parser_queue),
) -> StreamingResponse:
    """
    SSE endpoint для real-time отслеживания статуса парсера.

    Клиент подключается через EventSource и получает события:
    - event: status
    - data: {"state": "queued" | "in_progress" | "analyzing" | "succeeded" | "failed"}

    Соединение автоматически закрывается на терминальных статусах.

    Example:
    ```javascript
    const eventSource = new EventSource('/api/v1/parser/stream/job-123');
    eventSource.addEventListener('status', (event) => {
      const data = JSON.parse(event.data);
      console.log('Job state:', data.state);
    });
    ```
    """
    company_id = auth.tenant_id or auth.sub
    log.info("sse_stream_started", job_id=job_id, tenant_id=str(company_id))

    return StreamingResponse(
        _sse_status_generator(job_id, str(company_id), queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Отключаем буферизацию в nginx
        },
    )
