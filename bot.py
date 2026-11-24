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

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError, TelegramForbiddenError
from aiogram.types import BotCommand, BotCommandScopeDefault, ErrorEvent

from config import (
    APP_VERSION,
    BOT_TOKEN,
    DATABASE_PATH,
    DATABASE_URL,
    ENABLE_FILE_LOG,
    ENABLE_HEALTH_SERVER,
    IS_RENDER,
    LOG_FILE,
    LOG_LEVEL,
    PLACEHOLDER_MODE,
    PORT,
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
    elif isinstance(exception, TelegramConflictError):
        logger.warning(
            "Telegram conflict: yana bir instans shu token bilan polling qilayapti. "
            "Render'da faqat bitta xizmat qoldiring, mahalliy botni to'xtating. %s",
            exception,
        )
    else:
        logger.error("Handler xatosi (user=%s): %s", actor, exception, exc_info=exception)
    return True  # xatolik aiogram tomonidan qayta ko'tarilmaydi


async def _health(_: web.Request) -> web.Response:
    """Render Web Service port ochilganligini tekshiradi."""
    return web.Response(text="OK", content_type="text/plain")


async def start_health_server() -> web.AppRunner | None:
    if not ENABLE_HEALTH_SERVER:
        return None
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    logger.info("Health server ishga tushdi: 0.0.0.0:%s/health", PORT)
    return runner


async def main() -> None:
    setup_logging()
    # Logning birinchi qatori qaysi kod ishlab turganini aniqlab beradi.
    logger.info(
        "Bot versiyasi: %s | Render: %s | Health: %s | Port: %s",
        APP_VERSION,
        IS_RENDER,
        ENABLE_HEALTH_SERVER,
        PORT,
    )
    if PLACEHOLDER_MODE:
        logger.warning(
            "PLACEHOLDER rejimi: .env faylida haqiqiy BOT_TOKEN va SUPER_ADMIN_ID ni "
            "sozlang. Aks holda bot Telegram ga ulanmaydi."
        )
    if not DATABASE_URL and ENABLE_HEALTH_SERVER:
        logger.warning(
            "DATABASE_URL yo'q: ma'lumotlar vaqtinchalik SQLite faylida saqlanadi va "
            "Render restart'da yo'qoladi. Doimiy PostgreSQL ulanishi uchun "
            "DATABASE_URL ni Environment'ga qo'shing."
        )

    # Render portni darhol ko'rishi uchun health server eng avval ochiladi.
    # Aks holda "No open ports detected" chiqib, yangi instans o'chiriladi va
    # eski instans bilan ikki polling sodir bo'ladi (TelegramConflictError).
    health_runner = await start_health_server()
    bot: Bot | None = None
    try:
        db_target = DATABASE_URL or DATABASE_PATH
        db = Database(db_target)
        await db.init()
        storage = PersistentStorage(db_target)
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

        logger.info("Bot ishga tushdi. Baza: %s", db_target)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as exc:  # noqa: BLE001 - xatolik log faylga yoziladi
        logger.exception("Bot ishlamay qoldi: %s", exc)
        raise
    finally:
        if bot is not None:
            await bot.session.close()
        if health_runner:
            await health_runner.cleanup()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot foydalanuvchi tomonidan to'xtatildi.")
