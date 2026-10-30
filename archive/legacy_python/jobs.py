"""Реестр задач бота: короткий токен для callback_data -> данные задачи.

callback_data в Telegram ограничена 64 байтами, а job_id бэкенда может быть
длиннее (например, составной), поэтому в кнопку кладём короткий токен.
Реестр в памяти: после перезапуска бота старые кнопки перестают работать.
"""

import asyncio
import secrets
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass(eq=False)
class JobRef:
    job_id: str
    chat_id: int
    user_id: int
    url: str
    message_id: int | None = None
    delivered: bool = False  # результат уже отправлен пользователю
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class JobRegistry:
    def __init__(self, max_size: int = 1000) -> None:
        self._items: OrderedDict[str, JobRef] = OrderedDict()
        self._max_size = max_size

    def add(self, ref: JobRef) -> str:
        token = secrets.token_urlsafe(8)  # 11 символов
        self._items[token] = ref
        while len(self._items) > self._max_size:
            self._items.popitem(last=False)  # вытесняем самые старые
        return token

    def get(self, token: str) -> JobRef | None:
        return self._items.get(token)
