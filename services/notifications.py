"""Bildirishnomalar va ommaviy xabar yuborish xizmati."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import (
    BROADCAST_DELAY,
    DEFAULT_VENUE,
    GENDER_LABELS,
    ORGANIZER,
    STATUS_LABELS,
    SUPER_ADMIN_ID,
)
from database import Database

logger = logging.getLogger(__name__)

NO_DATA = "yo'q"
NO_REVIEW = "hali yo'q"


def format_application(app: dict, detailed: bool = True) -> str:
    """Arizani chiroyli ko'rinishga keltiradi."""
    username = f"@{app['username']}" if app.get("username") else NO_DATA
    text = (
        f"📋 ARIZA #{app['id']:04d}\n\n"
        f"👤 Ism: {app['first_name']}\n"
        f"👤 Familiya: {app['last_name']}\n"
        f"🎂 Yosh: {app['age']}\n"
        f"🎓 Sinf: {app['grade']}-sinf\n"
        f"{GENDER_LABELS.get(app['gender'], app['gender'])}\n"
        f"📱 Telefon: {app['phone']}\n"
        f"🔗 Telegram: {username} (ID: {app['user_id']})\n"
        f"📊 Holat: {STATUS_LABELS.get(app['status'], app['status'])}\n"
        f"🕐 Yuborilgan: {app['created_at']}"
    )
    if detailed:
        text += (
            f"\n👁 Ko'rib chiqqan: {app.get('reviewed_by') or NO_REVIEW}"
            f"\n📝 Izoh: {app.get('rejection_reason') or NO_DATA}"
        )
    return text


async def notify_new_application(bot: Bot, db: Database, app_id: int) -> int:
    """Yangi ariza haqida super admin va barcha faol adminlarga xabar beradi."""
    app = await db.get_application_by_id(app_id)
    if not app:
        return 0
    text = "🆕 YANGI ARIZA TOPSHIRILDI\n\n" + format_application(app)
    from keyboards.admin import review_keyboard

    recipients = [SUPER_ADMIN_ID]
    for admin in await db.list_admins(only_active=True):
        admin_id = int(admin["user_id"])
        if admin_id != SUPER_ADMIN_ID and admin_id not in recipients:
            recipients.append(admin_id)

    sent = 0
    for admin_id in recipients:
        try:
            await bot.send_message(admin_id, text, reply_markup=review_keyboard(app_id))
            sent += 1
        except TelegramAPIError as exc:
            logger.warning("Admin %s ga xabar yuborib bo'lmadi: %s", admin_id, exc)
    return sent


async def notify_review_result(bot: Bot, app: dict) -> bool:
    """Tasdiqlash/rad etish natijasini o'quvchiga yuboradi."""
    app_id = app["id"]
    if app["status"] == "approved":
        text = (
            "🎉 Tabriklaymiz!\n\n"
            "Sizning kitobxonlik musobaqasidagi ishtirok etish uchun yuborgan "
            "arizangiz tasdiqlandi!\n\n"
            "Musobaqa kuni va vaqti haqida qo'shimcha ma'lumot bot orqali yuboriladi.\n\n"
            f"Ariza raqamingiz: #{app_id:04d}"
        )
    else:
        reason = app.get("rejection_reason") or "Sabab ko'rsatilmagan"
        text = (
            "❌ Afsuski, arizangiz rad etildi.\n\n"
            f"Sabab: {reason}\n\n"
            f"Ariza raqamingiz: #{app_id:04d}\n"
            "Agar xatolikni tuzatsangiz, \"Qayta ariza topshirish\" tugmasi orqali "
            "qaytadan yuborishingiz mumkin."
        )
    from keyboards.main import status_action

    try:
        await bot.send_message(
            app["user_id"], text, reply_markup=status_action(app["status"], app["id"])
        )
        return True
    except TelegramAPIError as exc:
        logger.warning("Foydalanuvchi %s ga natija yuborib bo'lmadi: %s", app["user_id"], exc)
        return False


def build_announcement(settings: dict[str, str]) -> str:
    date = settings.get("competition_date") or "Admin tomonidan belgilanadi"
    time = settings.get("competition_time") or "Admin tomonidan belgilanadi"
    place = settings.get("competition_place") or DEFAULT_VENUE
    return (
        "📢 MUHIM E'LON!\n\n"
        "Hurmatli o'quvchi!\n\n"
        "Siz kitobxonlik musobaqasida ishtirok etish uchun ro'yxatdan o'tgansiz.\n\n"
        f"📅 Sana: {date}\n"
        f"⏰ Vaqt: {time}\n"
        f"📍 Manzil: {place}\n\n"
        "Musobaqa kuni belgilangan vaqtda kelishingizni so'raymiz.\n\n"
        f"{ORGANIZER}."
    )


async def broadcast_announcement(
    bot: Bot, db: Database, text: str
) -> tuple[int, int]:
    """Tasdiqlangan barcha ishtirokchilarga xabar yuboradi. (yuborilgan, xatoli)"""
    recipients = await db.get_recipients()
    sent = failed = 0
    for user_id in recipients:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except TelegramAPIError as exc:
            failed += 1
            logger.warning("Xabar %s ga yetkazilmadi: %s", user_id, exc)
        await asyncio.sleep(BROADCAST_DELAY)
    return sent, failed
