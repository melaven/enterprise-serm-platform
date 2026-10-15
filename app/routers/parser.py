import hashlib
from typing import Literal

from fastapi import APIRouter, HTTPException, status
import structlog
from pydantic import BaseModel, HttpUrl, model_validator

from app.core.redis import ArqPool
from app.core.security import CurrentAuth
from app.core.jobs import enqueue_unique
from app.db.session import TenantSession
from app.services.entitlement import enforce_reviews_quota
from app.services.scrapers import Platform
from app.services.scrapers.platforms import host_allowed

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/parser", tags=["parser"])


class ParseRequest(BaseModel):
    platform: Platform
    url: HttpUrl

    @model_validator(mode="after")
    def _host_matches_platform(self) -> "ParseRequest":
        # Защита от SSRF: воркер ходит по URL из запроса, поэтому хост ограничен
        # доменами площадки (тот же список проверяет и сам адаптер).
        if not host_allowed(str(self.url), self.platform):
            raise ValueError(f"URL host does not belong to {self.platform}")
        return self


class ParseJobOut(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"


@router.post("/jobs", response_model=ParseJobOut, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_fetch_reviews(
    body: ParseRequest, auth: CurrentAuth, pool: ArqPool, session: TenantSession
) -> ParseJobOut:
    url = str(body.url)
    # Быстрый отказ 402 до постановки в очередь. Гарантию даёт атомарный резерв в воркере.
    await enforce_reviews_quota(session, auth.company_id)
    # company_id берётся ТОЛЬКО из проверенного JWT, не из тела запроса.
    # Детерминированный job_id: двойной клик не плодит параллельные парсинги.
    job_id = (
        f"fetch_reviews:{auth.company_id}:{body.platform}:"
        f"{hashlib.sha256(url.encode()).hexdigest()[:16]}"
    )
    # correlation_id запроса уезжает в job: логи воркера склеятся с логами этого запроса.
    job = await enqueue_unique(
        pool,
        "fetch_reviews_task",
        auth.company_id,
        body.platform,
        url,
        job_id=job_id,
    )
    if job is None:  # такой job_id уже в очереди, выполняется или недавно завершён
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Parsing for this URL is already queued or running",
        )
    log.info("parser_enqueued", job_id=job.job_id, platform=body.platform)
    return ParseJobOut(job_id=job.job_id)
