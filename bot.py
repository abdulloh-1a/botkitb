"""10-maktab kitobxonlik musobaqasi Telegram botining kirish nuqtasi.

Ishga tushirish:
    source .venv/bin/activate
    python bot.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import BotCommand, BotCommandScopeDefault, ErrorEvent

from config import (
    BOT_TOKEN,
    DATABASE_PATH,
    ENABLE_FILE_LOG,
    LOG_FILE,
    LOG_LEVEL,
    PLACEHOLDER_MODE,
)
from database import Database
from handlers import admin, application, competition, fallback, start, statistics
from storage import PersistentStorage

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger_root = logging.getLogger()
    logger_root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger_root.addHandler(console)

    if ENABLE_FILE_LOG:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger_root.addHandler(file_handler)


async def handle_errors(event: ErrorEvent) -> bool:
    """Xatolarni toza loglaydi: bloklagan foydalanuvchi uchun traceback yozmaydi."""
    update = event.update
    if update.message:
        actor = update.message.from_user.id
    elif update.callback_query:
        actor = update.callback_query.from_user.id
    elif update.my_chat_member:
        actor = update.my_chat_member.from_user.id
    else:
        actor = "noma'lum"

    exception = event.exception
    if isinstance(exception, TelegramForbiddenError):
        logger.warning(
            "Foydalanuvchi %s botni bloklagan yoki chat yopiq: %s", actor, exception
        )
    else:
        logger.error("Handler xatosi (user=%s): %s", actor, exception, exc_info=exception)
    return True  # xatolik aiogram tomonidan qayta ko'tarilmaydi


async def main() -> None:
    setup_logging()
    if PLACEHOLDER_MODE:
        logger.warning(
            "PLACEHOLDER rejimi: .env faylida haqiqiy BOT_TOKEN va SUPER_ADMIN_ID ni "
            "sozlang. Aks holda bot Telegram ga ulanmaydi."
        )

    db = Database(DATABASE_PATH)
    await db.init()
    storage = PersistentStorage(DATABASE_PATH)
    await storage.init()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)
    dp["db"] = db  # handler va filtrlarga dependency injection orqali beriladi

    dp.include_router(start.router)
    dp.include_router(application.router)
    dp.include_router(admin.router)
    dp.include_router(statistics.router)
    dp.include_router(competition.router)
    dp.include_router(fallback.router)  # oxirida: qolgan barcha tugmalarni loglaydi
    dp.errors.register(handle_errors)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Botni boshlash"),
            BotCommand(command="apply", description="Ariza topshirish"),
            BotCommand(command="admin", description="Admin paneli"),
            BotCommand(command="competition", description="Musobaqa ma'lumoti"),
            BotCommand(command="help", description="Yordam"),
        ],
        scope=BotCommandScopeDefault(),
    )

    logger.info("Bot ishga tushdi. Baza: %s", DATABASE_PATH)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as exc:  # noqa: BLE001 - xatolik log faylga yoziladi
        logger.exception("Bot ishlamay qoldi: %s", exc)
        raise
    finally:
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot foydalanuvchi tomonidan to'xtatildi.")
