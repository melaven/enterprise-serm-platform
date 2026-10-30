"""Tenant-scoped CRUD for outbound webhook endpoints."""

import ipaddress
import secrets
from collections.abc import AsyncIterator
from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import JWTPayload
from app.core.auth import get_current_tenant, get_jwt_payload
from app.core.database import AsyncSessionLocal
from app.core.tenant_session import get_tenant_session
from app.infrastructure.persistence.models.economics import WebhookEndpoint

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


class WebhookEndpointCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError("Webhook URL must be a valid HTTPS URL")
        hostname = parsed.hostname.lower().rstrip(".")
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError("Webhook URL must not target localhost")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return value
        if not address.is_global:
            raise ValueError("Webhook URL must not target a private IP address")
        return value


class WebhookEndpointUpdate(WebhookEndpointCreate):
    is_active: bool


class WebhookEndpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    is_active: bool
    created_at: datetime


class WebhookEndpointCreated(WebhookEndpointOut):
    secret_key: str


async def get_webhook_session(
    request: Request,
    tenant_id: UUID = Depends(get_current_tenant),
    payload: JWTPayload = Depends(get_jwt_payload),
) -> AsyncIterator[AsyncSession]:
    request.state.tenant_id = tenant_id
    request.state.user_id = payload.sub
    session = await get_tenant_session(
        factory=AsyncSessionLocal,
        tenant_id=tenant_id,
    )
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@router.post(
    "",
    response_model=WebhookEndpointCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook_endpoint(
    body: WebhookEndpointCreate,
    tenant_id: UUID = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_webhook_session),
) -> WebhookEndpoint:
    endpoint = WebhookEndpoint(
        company_id=tenant_id,
        url=body.url,
        secret_key=secrets.token_urlsafe(32),
        is_active=True,
    )
    session.add(endpoint)
    await session.flush()
    return endpoint


@router.get("", response_model=list[WebhookEndpointOut])
async def list_webhook_endpoints(
    tenant_id: UUID = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_webhook_session),
) -> list[WebhookEndpoint]:
    result = await session.scalars(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.company_id == tenant_id)
        .order_by(WebhookEndpoint.created_at.desc())
    )
    return list(result.all())


@router.get("/{endpoint_id}", response_model=WebhookEndpointOut)
async def get_webhook_endpoint(
    endpoint_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_webhook_session),
) -> WebhookEndpoint:
    endpoint = await session.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.company_id == tenant_id,
        )
    )
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found",
        )
    return endpoint


@router.patch("/{endpoint_id}", response_model=WebhookEndpointOut)
async def update_webhook_endpoint(
    endpoint_id: UUID,
    body: WebhookEndpointUpdate,
    tenant_id: UUID = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_webhook_session),
) -> WebhookEndpoint:
    endpoint = await session.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.company_id == tenant_id,
        )
    )
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found",
        )
    endpoint.url = body.url
    endpoint.is_active = body.is_active
    await session.flush()
    return endpoint


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook_endpoint(
    endpoint_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_webhook_session),
) -> None:
    endpoint = await session.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.company_id == tenant_id,
        )
    )
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found",
        )
    await session.delete(endpoint)
