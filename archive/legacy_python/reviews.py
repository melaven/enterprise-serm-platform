import hashlib
from collections.abc import Sequence
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.jobs import enqueue_unique
from app.core.redis import RedisPool
from app.core.security import CurrentAuth
from app.db.session import TenantSession
from app.infrastructure.persistence.models.review import Review  # подставь свою модель
from app.infrastructure.persistence.repositories.review_repository import ReviewRepository
from app.application.entitlement import require_reviews_quota
from app.application.reviews.service import ReviewNotFoundError, ReviewService, ReviewsNotFoundError

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    created_at: datetime
    # + остальные поля модели


def get_review_service(session: TenantSession) -> ReviewService:
    return ReviewService(ReviewRepository(session))


ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]


@router.get("", response_model=list[ReviewOut])
async def list_reviews(
    service: ReviewServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Review]:
    return await service.list_reviews(limit=limit, offset=offset)


MAX_ANALYZE_BATCH = 200
ANALYZE_TASK = "process_reviews_batch"


class AnalyzeReviewsIn(BaseModel):
    review_ids: list[UUID] = Field(min_length=1, max_length=MAX_ANALYZE_BATCH)

    @field_validator("review_ids")
    @classmethod
    def _dedupe(cls, ids: list[UUID]) -> list[UUID]:
        return list(
            dict.fromkeys(ids)
        )  # дубли в запросе не удваивают работу; порядок сохраняется


class AnalyzeAccepted(BaseModel):
    job_id: str
    accepted: int
    deduplicated: bool = (
        False  # такой же пакет уже в очереди/выполняется: вернули существующий job_id
    )


@router.post(
    "/analyze",
    response_model=AnalyzeAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(require_reviews_quota)
    ],  # 402 раньше проверки id и постановки в очередь
)
async def analyze_reviews(
    body: AnalyzeReviewsIn,
    auth: CurrentAuth,
    service: ReviewServiceDep,
    pool: RedisPool,
) -> AnalyzeAccepted:
    """Ставит пакетный анализ отзывов в очередь ARQ. tenant_id берётся ТОЛЬКО из проверенного JWT."""
    try:
        # Под RLS: чужие id неотличимы от несуществующих, в очередь они не попадут.
        await service.ensure_visible(body.review_ids)
    except ReviewsNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "reviews_not_found", "missing": exc.missing},
        ) from exc

    digest = hashlib.sha256(
        ",".join(sorted(str(i) for i in body.review_ids)).encode()
    ).hexdigest()[:16]
    job_id = (
        f"{ANALYZE_TASK}:{auth.company_id}:{digest}"  # повторный клик не плодит задачи
    )
    job = await enqueue_unique(
        pool, ANALYZE_TASK, auth.company_id, body.review_ids, job_id=job_id
    )
    return AnalyzeAccepted(
        job_id=job_id, accepted=len(body.review_ids), deduplicated=job is None
    )


@router.get("/{review_id}", response_model=ReviewOut)
async def get_review(review_id: UUID, service: ReviewServiceDep) -> Review:
    try:
        return await service.get_review(review_id)
    except ReviewNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found") from exc
