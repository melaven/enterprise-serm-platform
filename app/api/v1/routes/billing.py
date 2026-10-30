"""POST /api/v1/billing/checkout: создаёт Stripe Checkout для апгрейда Free -> Pro.

client_reference_id = company_id из ПРОВЕРЕННОГО JWT: по нему вебхук привяжет оплату к компании.
"""

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentPayload, tenant_id_from_payload
from app.core.config import get_settings
from app.core.dependencies import get_tenant_db

router = APIRouter(prefix="/billing", tags=["billing"])

# Кто может покупать тариф (значения company_role из access-token hook; поправь под свои роли).
BILLING_ROLES = frozenset({"owner", "admin"})


class CheckoutOut(BaseModel):
    url: str


@router.post("/checkout", response_model=CheckoutOut)
async def create_checkout(
    auth: CurrentPayload, session: AsyncSession = Depends(get_tenant_db)
) -> CheckoutOut:
    s = get_settings()
    if not (s.stripe_secret_key and s.stripe_price_pro):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Billing not configured"
        )
    if auth.company_role not in BILLING_ROLES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only owner/admin can change the plan"
        )

    company_id = tenant_id_from_payload(auth)
    plan = (
        await session.execute(
            text("SELECT plan_code FROM app.get_entitlement(CAST(:t AS uuid))"),
            {"t": str(company_id)},
        )
    ).scalar_one_or_none()
    if plan == "pro":  # защита от двойной подписки
        raise HTTPException(status.HTTP_409_CONFLICT, "Already on Pro")

    base = s.app_base_url.rstrip("/")
    checkout = await stripe.checkout.Session.create_async(
        api_key=s.stripe_secret_key.get_secret_value(),
        mode="subscription",
        line_items=[{"price": s.stripe_price_pro, "quantity": 1}],
        client_reference_id=str(company_id),
        subscription_data={"metadata": {"company_id": str(company_id)}},
        success_url=f"{base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/billing/cancel",
    )
    if not checkout.url:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Stripe did not return a URL")
    return CheckoutOut(url=checkout.url)
