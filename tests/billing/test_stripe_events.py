"""Логика вебхуков без БД и без SDK: фейковый Gateway. Плюс эталонная проверка формата подписи Stripe."""

import hashlib
import hmac
import sys
import time
import types
from uuid import uuid4

import pytest

# structlog может отсутствовать в окружении тестов: заглушка
if "structlog" not in sys.modules:
    try:
        import structlog  # noqa: F401
    except ImportError:
        m = types.ModuleType("structlog")
        m.get_logger = lambda *_a, **_k: types.SimpleNamespace(
            info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None
        )
        sys.modules["structlog"] = m

from app.services.stripe_events import OutOfOrder, apply_event  # noqa: E402


class FakeGw:
    def __init__(self, known_subs=()):
        self.events, self.pro, self.paid, self.canceled = set(), [], [], []
        self.known = set(known_subs)

    async def record_event(self, eid, t):
        if eid in self.events:
            return False
        self.events.add(eid)
        return True

    async def activate_pro(self, tenant, customer, sub):
        self.pro.append((tenant, customer, sub))
        self.known.add(sub)

    async def period_paid(self, sub, start, end, reset):
        if sub not in self.known:
            return False
        self.paid.append((sub, start, end, reset))
        return True

    async def cancel(self, sub):
        if sub not in self.known:
            return False
        self.canceled.append(sub)
        return True


def checkout(tenant, **kw):
    o = {"mode": "subscription", "payment_status": "paid", "client_reference_id": str(tenant),
         "customer": "cus_1", "subscription": "sub_1"}
    o.update(kw)
    return o


@pytest.mark.asyncio
async def test_checkout_activates_pro_once():
    gw, t = FakeGw(), uuid4()
    assert await apply_event(gw, "evt_1", "checkout.session.completed", checkout(t)) == "applied"
    assert await apply_event(gw, "evt_1", "checkout.session.completed", checkout(t)) == "duplicate"
    assert gw.pro == [(t, "cus_1", "sub_1")]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    {"mode": "payment"}, {"payment_status": "unpaid"}, {"client_reference_id": "not-a-uuid"},
    {"client_reference_id": None}, {"customer": None}, {"subscription": None},
])
async def test_checkout_rejects_unpaid_or_malformed(bad):
    gw = FakeGw()
    assert await apply_event(gw, "evt_x", "checkout.session.completed", checkout(uuid4(), **bad)) == "ignored"
    assert gw.pro == []


@pytest.mark.asyncio
async def test_unknown_event_type_ignored_and_not_recorded():
    gw = FakeGw()
    assert await apply_event(gw, "evt_9", "charge.refunded", {}) == "ignored"
    assert gw.events == set()


@pytest.mark.asyncio
async def test_invoice_cycle_resets_usage_and_sets_period():
    gw = FakeGw({"sub_1"})
    inv = {"subscription": "sub_1", "billing_reason": "subscription_cycle",
           "lines": {"data": [{"period": {"start": 1_760_000_000, "end": 1_762_600_000}}]}}
    assert await apply_event(gw, "evt_2", "invoice.payment_succeeded", inv) == "applied"
    sub, start, end, reset = gw.paid[0]
    assert reset is True and start.year == 2025 and end > start


@pytest.mark.asyncio
async def test_invoice_proration_does_not_reset_usage():
    gw = FakeGw({"sub_1"})
    inv = {"subscription": "sub_1", "billing_reason": "subscription_update",
           "lines": {"data": [{"period": {"start": 1, "end": 2}}]}}
    await apply_event(gw, "evt_3", "invoice.payment_succeeded", inv)
    assert gw.paid[0][1:] == (None, None, False)


@pytest.mark.asyncio
async def test_invoice_new_api_shape_parent_subscription_details():
    gw = FakeGw({"sub_1"})
    inv = {"parent": {"subscription_details": {"subscription": "sub_1"}}, "billing_reason": "subscription_cycle",
           "lines": {"data": [{"period": {"start": 1_760_000_000, "end": 1_762_600_000}}]}}
    assert await apply_event(gw, "evt_4", "invoice.payment_succeeded", inv) == "applied"


@pytest.mark.asyncio
async def test_invoice_before_checkout_raises_for_retry():
    gw = FakeGw()
    with pytest.raises(OutOfOrder):
        await apply_event(gw, "evt_5", "invoice.payment_succeeded", {"subscription": "sub_9", "billing_reason": "subscription_create"})


@pytest.mark.asyncio
async def test_invoice_without_subscription_ignored():
    assert await apply_event(FakeGw(), "evt_6", "invoice.payment_succeeded", {"billing_reason": "manual"}) == "ignored"


@pytest.mark.asyncio
async def test_subscription_deleted_downgrades_only_known():
    gw = FakeGw({"sub_1"})
    assert await apply_event(gw, "evt_7", "customer.subscription.deleted", {"id": "sub_1"}) == "applied"
    assert await apply_event(gw, "evt_8", "customer.subscription.deleted", {"id": "sub_old"}) == "ignored"
    assert gw.canceled == ["sub_1"]


# --- Эталон формата подписи Stripe: t=<ts>,v1=HMAC_SHA256(secret, f"{t}.{payload}") ---
def stripe_sig(secret: str, payload: bytes, ts: int | None = None) -> str:
    ts = ts or int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def test_real_stripe_sdk_signature_roundtrip():
    stripe = pytest.importorskip("stripe")
    secret, payload = "whsec_test", b'{"id":"evt_1","type":"invoice.payment_succeeded","object":"event"}'
    ev = stripe.Webhook.construct_event(payload, stripe_sig(secret, payload), secret, tolerance=300)
    assert ev["id"] == "evt_1"
    with pytest.raises(stripe.SignatureVerificationError):  # подделка: чужой секрет
        stripe.Webhook.construct_event(payload, stripe_sig("whsec_evil", payload), secret, tolerance=300)
    with pytest.raises(stripe.SignatureVerificationError):  # изменённое тело
        stripe.Webhook.construct_event(payload + b" ", stripe_sig(secret, payload), secret, tolerance=300)
    with pytest.raises(stripe.SignatureVerificationError):  # replay старше tolerance
        stripe.Webhook.construct_event(payload, stripe_sig(secret, payload, int(time.time()) - 4000), secret, tolerance=300)
