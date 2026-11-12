from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AnyHttpUrl, BaseModel, Field

from app.core.auth import CurrentPayload
from app.core.rate_limit import check_parser_limits

router = APIRouter(prefix="/parser", tags=["parser"])


class ParserJobRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=32)
    url: AnyHttpUrl


class ParserJobResult(BaseModel):
    reviews_found: int = 0
    reviews_new: int = 0
    reviews_saved: int = 0
    ai_enriched: int = 0
    ai_pending: int = 0
    duration_ms: int = 0


class ParserJobCreated(BaseModel):
    job_id: UUID


class ParserJobStatus(BaseModel):
    job_id: UUID
    state: Literal["queued", "in_progress", "succeeded", "failed"]
    result: ParserJobResult | None
    error: str | None


@router.post(
    "/start",
    response_model=ParserJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Создать демонстрационную задачу парсинга",
)
async def start_mock_parser_job(
    _request: ParserJobRequest,
    _auth: CurrentPayload,
    _rate_limit: None = Depends(check_parser_limits),
) -> ParserJobCreated:
    return ParserJobCreated(job_id=uuid4())


@router.get("/jobs/{job_id}", response_model=ParserJobStatus)
async def get_mock_parser_job_status(
    job_id: UUID,
    _auth: CurrentPayload,
) -> ParserJobStatus:
    return ParserJobStatus(
        job_id=job_id,
        state="succeeded",
        result=ParserJobResult(),
        error=None,
    )


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_fetch_reviews(
    auth: CurrentPayload,
    _rate_limit: None = Depends(check_parser_limits),
) -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Public-page scraping is disabled. Connect an authorized official "
            "integration or submit customer-provided data to the SI API."
        ),
    )


@router.get("/stream/{job_id}")
async def stream_parser_status(job_id: str, auth: CurrentPayload) -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Public-page scraping jobs are disabled",
    )
