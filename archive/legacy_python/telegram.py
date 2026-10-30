"""Отправка алертов в Telegram. Контракт: send_telegram_alert НИКОГДА не бросает исключений (кроме отмены задачи).

Секрет: токен бота входит в URL запроса. Поэтому
  * в логи пишем только тип ошибки и HTTP-статус, никогда str(exc) / URL (в сообщении httpx-ошибок есть токен);
  * логгеры httpx/httpcore поднимаются до WARNING (на INFO httpx печатает полный URL каждого запроса).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LEN = 4096  # лимит Telegram на текст сообщения
_CHAT_ID = re.compile(r"^(-?\d{1,20}|@[A-Za-z][A-Za-z0-9_]{4,31})$")


def _token() -> str | None:
    from app.core.config import (
        get_settings,
    )  # лениво: модуль не тянет окружение приложения при импорте

    secret = get_settings().telegram_bot_token
    return secret.get_secret_value() if secret else None


def _timeout() -> float:
    from app.core.config import get_settings

    return float(get_settings().telegram_timeout_s)


def _mask(chat_id: str) -> str:
    return f"…{chat_id[-4:]}" if len(chat_id) > 4 else "…"


async def send_telegram_alert(
    message: str,
    chat_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Отправить HTML-сообщение в чат. True = Telegram принял; False = любая причина отказа (уже залогирована).

    `message` — HTML (parse_mode=HTML): вставляемые значения вызывающий обязан экранировать (html.escape).
    """
    try:
        token = _token()
        if not token:
            log.warning("telegram_not_configured")
            return False
        chat = str(chat_id).strip()
        if not _CHAT_ID.fullmatch(chat):
            log.warning("telegram_bad_chat_id", chat=_mask(chat))
            return False

        payload: dict[str, Any] = {
            "chat_id": chat,
            "text": message[:MAX_MESSAGE_LEN],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        url = API_URL.format(token=token)
        if client is not None:
            response = await client.post(url, json=payload)
        else:
            async with httpx.AsyncClient(timeout=_timeout()) as own:
                response = await own.post(url, json=payload)

        if response.status_code == 200:
            return True
        # 401 — неверный токен, 403 — бот заблокирован/удалён из чата, 400 — чат не найден/битая разметка, 429 — флуд-лимит.
        log.warning("telegram_rejected", status=response.status_code, chat=_mask(chat))
        return False
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - сеть, DNS, TLS, таймаут, блокировка Telegram: алерт не должен ронять конвейер
        log.warning(
            "telegram_send_failed", error_type=type(exc).__name__
        )  # без str(exc): там может быть URL с токеном
        return False
