"""Telegram-интерфейс к бэкенду парсинга отзывов (aiogram 3.x).

Запуск из корня проекта:  python -m tg_bot.main
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)

from tg_bot.api_client import ApiClient, ApiError, JobStatus
from tg_bot.formatting import esc, extract_url, format_result
from tg_bot.jobs import JobRef, JobRegistry
from tg_bot.settings import BotSettings

logger = logging.getLogger("tg_bot")
router = Router()

CALLBACK_PREFIX = "st:"
MAX_POLL_ERRORS = 5

HELP_TEXT = (
    "Привет! Пришли ссылку на карточку организации (Яндекс Карты, 2ГИС, Google Maps), "
    "и я запущу сбор и анализ отзывов.\n\n"
    "Пример: <code>https://yandex.ru/maps/org/...</code>"
)


# --------------------------------------------------------------------------- #
# Доступ
# --------------------------------------------------------------------------- #
class AccessMiddleware(BaseMiddleware):
    """Пускает только user id из TG_ALLOWED_USER_IDS (если список задан)."""

    def __init__(self, allowed: frozenset[int]) -> None:
        self._allowed = allowed

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if self._allowed and (user is None or user.id not in self._allowed):
            if isinstance(event, Message):
                await event.answer("⛔ Нет доступа.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Нет доступа", show_alert=True)
            return None
        return await handler(event, data)


# --------------------------------------------------------------------------- #
# Хелперы
# --------------------------------------------------------------------------- #
def status_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Проверить статус",
                    callback_data=f"{CALLBACK_PREFIX}{token}",
                )
            ]
        ]
    )


def spawn(
    tasks: set[asyncio.Task[None]], coro: Coroutine[Any, Any, None]
) -> asyncio.Task[None]:
    """create_task со ссылкой на задачу: иначе её может собрать GC на лету."""
    task = asyncio.create_task(coro)
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return task


async def deliver_if_terminal(bot: Bot, ref: JobRef, status: JobStatus) -> bool:
    """Отправляет итог, если задача завершилась. Идемпотентна (lock + delivered)."""
    async with ref.lock:
        if ref.delivered:
            return True
        if status.is_complete:
            for text in format_result(ref.job_id, status.result):
                await bot.send_message(ref.chat_id, text, disable_web_page_preview=True)
        elif status.is_failed:
            reason = f"\n<code>{esc(status.error)}</code>" if status.error else ""
            await bot.send_message(
                ref.chat_id,
                f"❌ Задача <code>{esc(ref.job_id)}</code> завершилась с ошибкой."
                f"{reason}",
            )
        else:
            return False
        ref.delivered = True

    if ref.message_id is not None:  # убираем кнопку под исходным сообщением
        try:
            await bot.edit_message_reply_markup(
                chat_id=ref.chat_id, message_id=ref.message_id, reply_markup=None
            )
        except TelegramBadRequest:
            pass
    return True


async def poll_job(
    bot: Bot, api: ApiClient, settings: BotSettings, ref: JobRef
) -> None:
    """Автоопрос статуса до результата/ошибки/таймаута."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.poll_timeout
    errors = 0
    while loop.time() < deadline:
        await asyncio.sleep(settings.poll_interval)
        if ref.delivered:  # пользователь уже нажал кнопку
            return
        try:
            status = await api.get_status(ref.job_id)
            errors = 0
        except ApiError as exc:
            errors += 1
            logger.warning("poll %s failed (%d): %s", ref.job_id, errors, exc)
            if not exc.retryable or errors >= MAX_POLL_ERRORS:
                await _notify(bot, ref, f"❌ Не удалось получить статус: {esc(exc)}")
                return
            continue
        if await deliver_if_terminal(bot, ref, status):
            return

    if not ref.delivered:
        await _notify(
            bot,
            ref,
            "⌛ Задача выполняется дольше обычного. "
            "Нажмите «Проверить статус» под сообщением с Job ID позже.",
        )


async def _notify(bot: Bot, ref: JobRef, text: str) -> None:
    try:
        await bot.send_message(ref.chat_id, text)
    except TelegramAPIError:
        logger.exception("failed to notify chat %s", ref.chat_id)


# --------------------------------------------------------------------------- #
# Хендлеры
# --------------------------------------------------------------------------- #
@router.message(CommandStart())
@router.message(Command("help"))
async def on_start(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(F.text)
async def on_text(
    message: Message,
    bot: Bot,
    api: ApiClient,
    settings: BotSettings,
    registry: JobRegistry,
    tasks: set[asyncio.Task[None]],
) -> None:
    url = extract_url(message.text or "")
    if url is None:
        await message.answer(
            "Не вижу ссылку 🤔 Пришли URL, начинающийся с <code>https://</code>."
        )
        return

    try:
        job_id = await api.start_job(url, settings.company_id)
    except ApiError as exc:
        logger.warning("start_job failed: %s", exc)
        await message.answer(f"❌ Не удалось запустить задачу: {esc(exc)}")
        return

    ref = JobRef(
        job_id=job_id,
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else 0,
        url=url,
    )
    token = registry.add(ref)
    sent = await message.answer(
        f"Задача взята в работу ⏳\nJob ID: <code>{esc(job_id)}</code>",
        reply_markup=status_keyboard(token),
    )
    ref.message_id = sent.message_id
    spawn(tasks, poll_job(bot, api, settings, ref))


@router.callback_query(F.data.startswith(CALLBACK_PREFIX))
async def on_check_status(
    callback: CallbackQuery, bot: Bot, api: ApiClient, registry: JobRegistry
) -> None:
    token = (callback.data or "").removeprefix(CALLBACK_PREFIX)
    ref = registry.get(token)
    if ref is None:
        await callback.answer(
            "Задача не найдена (возможно, бот перезапускался). Отправь ссылку заново.",
            show_alert=True,
        )
        return
    if ref.delivered:
        await callback.answer("Результат уже отправлен ✅")
        return

    try:
        status = await api.get_status(ref.job_id)
    except ApiError as exc:
        await callback.answer(f"Ошибка API: {exc}"[:200], show_alert=True)
        return

    if await deliver_if_terminal(bot, ref, status):
        await callback.answer("Готово ✅")
    else:
        await callback.answer(f"Статус: {status.status} ⏳")


# --------------------------------------------------------------------------- #
# Запуск
# --------------------------------------------------------------------------- #
async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = BotSettings()  # type: ignore[call-arg]
    api = ApiClient(
        settings.api_base_url,
        api_token=settings.api_token.get_secret_value() if settings.api_token else None,
    )
    tasks: set[asyncio.Task[None]] = set()

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # kwargs диспетчера становятся workflow data: хендлеры получают их по имени.
    dp = Dispatcher(settings=settings, api=api, registry=JobRegistry(), tasks=tasks)
    access = AccessMiddleware(settings.allowed_ids)
    router.message.outer_middleware(access)
    router.callback_query.outer_middleware(access)
    dp.include_router(router)

    if not settings.allowed_ids:
        logger.warning("TG_ALLOWED_USER_IDS не задан: бот доступен всем")

    try:
        await dp.start_polling(bot)
    finally:
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await api.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
