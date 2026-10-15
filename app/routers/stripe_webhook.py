"""POST /api/v1/webhooks/stripe

Единственный источник истины об оплате. Без валидной подписи Stripe запрос отклоняется ДО любого разбора
и ДО обращения к БД. Эндпоинт без cookie/JWT: из глобального CSRF-dependency его нужно исключить
(подписанное тело — его собственная защита).
"""

import json
from typing import Annotated

import stripe
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from stripe import SignatureVerificationError

from app.core.config import Settings, get_settings
from app.db.billing_db import BillingNotConfigured, SqlGateway, billing_session
from app.services.stripe_events import OutOfOrder, apply_event

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

MAX_BODY = 512 * 1024
TOLERANCE_SECONDS = 300  # защита от replay: подпись старше 5 минут отклоняется


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, bool]:
    secret = settings.stripe_webhook_secret
    if secret is None:  # fail closed: без секрета никого не принимаем
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook not configured")
    if not stripe_signature:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing signature")

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Too large")
    payload = await request.body()  # СЫРЫЕ байты: подпись считается по ним, не по перепакованному JSON
    if len(payload) > MAX_BODY:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Too large")

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, secret.get_secret_value(), tolerance=TOLERANCE_SECONDS
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid payload") from exc
    except SignatureVerificationError as exc:
        log.warning("stripe_signature_invalid")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature") from exc

    # Дальше работаем с теми же проверенными байтами (JSON разбираем сами: не зависим от типов SDK).
    data = json.loads(payload)
    event_id, event_type = str(event["id"]), str(event["type"])
    if data.get("id") != event_id:  # страховка от расхождения
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid payload")
    obj = (data.get("data") or {}).get("object") or {}

    try:
        async with billing_session() as session:
            outcome = await apply_event(SqlGateway(session), event_id, event_type, obj)
    except BillingNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Billing not configured") from exc
    except OutOfOrder:
        log.info("stripe_out_of_order_retry", event_id=event_id, type=event_type)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Retry later") from None
    except Exception:  # откат транзакции уже произошёл; Stripe повторит доставку
        log.exception("stripe_event_failed", event_id=event_id, type=event_type)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Processing failed") from None

    log.info("stripe_event", event_id=event_id, type=event_type, outcome=outcome)
    return {"received": True}
