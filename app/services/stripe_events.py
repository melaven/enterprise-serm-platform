"""Бизнес-логика вебхуков Stripe. Работает ТОЛЬКО с уже проверенной подписью полезной нагрузкой.

Принципы:
  * tenant для первого события берётся из client_reference_id, который мы сами положили при создании
    checkout-сессии; для всех следующих — ТОЛЬКО из БД по stripe_subscription_id (метаданным не верим).
  * идемпотентность: record_event + применение в одной транзакции; дубль -> no-op.
  * неизвестная подписка (событие опередило checkout) -> OutOfOrder -> HTTP 500 -> Stripe повторит.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import structlog

log = structlog.get_logger(__name__)

HANDLED = frozenset(
    {"checkout.session.completed", "invoice.payment_succeeded", "customer.subscription.deleted"}
)
_RESET_REASONS = frozenset({"subscription_create", "subscription_cycle"})


class OutOfOrder(Exception):
    """Событие пришло раньше, чем стала известна подписка: пусть Stripe повторит доставку."""


class Gateway(Protocol):
    async def record_event(self, event_id: str, event_type: str) -> bool: ...
    async def activate_pro(self, tenant_id: UUID, customer: str, subscription: str) -> None: ...
    async def period_paid(
        self, subscription: str, start: datetime | None, end: datetime | None, reset_usage: bool
    ) -> bool: ...
    async def cancel(self, subscription: str) -> bool: ...


def _ts(v: Any) -> datetime | None:
    return datetime.fromtimestamp(int(v), tz=UTC) if v else None


def _id(v: Any) -> str | None:
    """Stripe отдаёт id строкой, либо развёрнутым объектом при expand."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("id")
    return None


def _invoice_subscription(inv: dict[str, Any]) -> str | None:
    # Поле переехало между версиями API: invoice.subscription -> invoice.parent.subscription_details.subscription
    sub = _id(inv.get("subscription"))
    if sub:
        return sub
    parent = inv.get("parent") or {}
    return _id(((parent.get("subscription_details")) or {}).get("subscription"))


async def apply_event(gw: Gateway, event_id: str, event_type: str, obj: dict[str, Any]) -> str:
    """Возвращает: 'duplicate' | 'ignored' | 'applied'. Исключение = откат транзакции и 500."""
    if event_type not in HANDLED:
        return "ignored"
    if not await gw.record_event(event_id, event_type):
        return "duplicate"

    if event_type == "checkout.session.completed":
        if obj.get("mode") != "subscription":
            return "ignored"
        if obj.get("payment_status") not in ("paid", "no_payment_required"):
            return "ignored"  # асинхронные методы оплаты: активируем по invoice.payment_succeeded/повтору
        customer, sub = _id(obj.get("customer")), _id(obj.get("subscription"))
        try:
            tenant = UUID(str(obj.get("client_reference_id")))
        except ValueError:
            tenant = None
        if not (customer and sub and tenant):
            log.error("stripe_checkout_malformed", event_id=event_id)
            return "ignored"  # повтор не поможет: данные неполные
        await gw.activate_pro(tenant, customer, sub)
        log.info("billing_pro_activated", tenant_id=str(tenant), event_id=event_id)
        return "applied"

    if event_type == "invoice.payment_succeeded":
        sub = _invoice_subscription(obj)
        if not sub:
            return "ignored"  # разовый счёт не по подписке
        reason = obj.get("billing_reason")
        start = end = None
        if reason in _RESET_REASONS:
            lines = ((obj.get("lines") or {}).get("data")) or []
            period = (lines[0].get("period") if lines else None) or {}
            start, end = _ts(period.get("start")), _ts(period.get("end"))
        if not await gw.period_paid(sub, start, end, reason in _RESET_REASONS):
            raise OutOfOrder(f"subscription {sub} unknown yet")
        return "applied"

    # customer.subscription.deleted
    sub = _id(obj.get("id"))
    if not sub:
        return "ignored"
    if not await gw.cancel(sub):
        # подписка не текущая/неизвестна: запоздавшее событие старой подписки или чужой аккаунт Stripe
        log.warning("billing_cancel_unknown_subscription", subscription=sub, event_id=event_id)
        return "ignored"
    log.info("billing_downgraded_to_free", subscription=sub, event_id=event_id)
    return "applied"
