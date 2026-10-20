"""Уведомления о критических угрозах: email + Telegram параллельно.

ВАЖНО: в моём дереве не было прежнего notifications.py; email-канал подключается через протокол EmailNotifier
(`send_email_alert`). Подставь свою существующую отправку email и перенеси сюда только Telegram-часть, если
функция у тебя уже есть.
"""

from __future__ import annotations

import asyncio
import html
from collections.abc import Mapping
from typing import Any, Protocol

import structlog

from app.core.telegram import send_telegram_alert

log = structlog.get_logger(__name__)

CRITICAL_THREAT_LEVEL = 4  # 4 — публичная эскалация, 5 — суд/надзорные органы (шкала из si_pipeline.SYSTEM_PROMPT)


class EmailNotifier(Protocol):
    async def __call__(
        self, *, company_name: str, platform: str, threat_level: int, review_id: str
    ) -> None: ...


def build_telegram_message(company_name: str, platform: str, threat_level: int) -> str:
    # Название компании и площадки приходят из БД/пользователя: экранируем под parse_mode=HTML.
    return (
        "🚨 <b>Критическая угроза!</b>\n"
        f"🏢 Компания: <b>{html.escape(company_name)}</b>\n"
        f"📍 Платформа: {html.escape(platform)}\n"
        f"⚠️ Оценка: <b>{threat_level}/5</b>"
    )


def telegram_chat_id(meta_config: Mapping[str, Any] | None) -> str | None:
    value = (meta_config or {}).get("telegram_chat_id")
    text = str(value).strip() if value is not None else ""
    return text or None


async def check_and_notify_critical_threat(
    *,
    company_name: str,
    company_meta_config: Mapping[str, Any] | None,
    platform: str,
    threat_level: int,
    review_id: str,
    email_notifier: EmailNotifier | None = None,
    threshold: int = CRITICAL_THREAT_LEVEL,
) -> bool:
    """True, если угроза критическая и уведомления отправлялись. Telegram-сбои никогда не пробрасываются.

    Ошибка email пробрасывается ПОСЛЕ завершения Telegram-отправки (ARQ может повторить задачу; тогда Telegram
    уйдёт повторно — при необходимости дедуплицируй по review_id выше по стеку).
    """
    if threat_level < threshold:
        return False

    tasks: list[asyncio.Future[Any] | Any] = []
    if email_notifier is not None:
        tasks.append(
            email_notifier(
                company_name=company_name,
                platform=platform,
                threat_level=threat_level,
                review_id=review_id,
            )
        )
    chat_id = telegram_chat_id(company_meta_config)
    if chat_id:
        tasks.append(
            send_telegram_alert(
                build_telegram_message(company_name, platform, threat_level), chat_id
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    email_error = next(
        (
            r
            for r in results[:1]
            if isinstance(r, BaseException) and email_notifier is not None
        ),
        None,
    )
    if email_error is not None:
        log.error(
            "critical_threat_email_failed",
            review_id=review_id,
            error_type=type(email_error).__name__,
        )
        raise email_error
    return True
