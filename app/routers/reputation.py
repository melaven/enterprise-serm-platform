"""Endpoints for tenant-scoped reputation statistics."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import get_current_tenant
from ..core.dependencies import get_tenant_db
from ..repositories.analytics_repo import get_reputation_statistics
from ..schemas.analytics import ReputationStatistics

router = APIRouter(prefix="/api/v1/reputation", tags=["Reputation"])


@router.get("/statistics", response_model=ReputationStatistics)
async def reputation_statistics(
    period_days: int = Query(30, ge=1, le=365),
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> ReputationStatistics:
    stats = await get_reputation_statistics(db, tenant_id, period_days)
    return ReputationStatistics.model_validate(stats)
