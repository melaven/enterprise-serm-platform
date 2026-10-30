from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentPayload
from app.core.rate_limit import check_parser_limits

router = APIRouter(prefix="/parser", tags=["parser"])


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
