"""Statistika: foydalanuvchilar uchun xavfsiz, adminlar uchun to'liq ko'rinish."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from config import GRADES
from database import Database
from filters.admin import IsAdminFilter
from keyboards.admin import back_to_admin
from keyboards.main import BTN_STATS, main_menu

router = Router(name="statistics")
NO_DATA = "yo'q"


def format_statistics(stats: dict) -> str:
    lines = [
        "📊 KITOBXONLIK MUSOBAQASI STATISTIKASI",
        "",
        f"👥 Jami arizalar: {stats['total']}",
        f"✅ Tasdiqlangan: {stats['approved']}",
        f"⏳ Kutilmoqda: {stats['pending']}",
        f"❌ Rad etilgan: {stats['rejected']}",
        "",
        f"👦 O'g'il bolalar: {stats['male']}",
        f"👧 Qiz bolalar: {stats['female']}",
        "",
    ]
    for grade in GRADES:
        lines.append(f"{grade}-sinf: {stats['grades'].get(grade, 0)} nafar")
    lines.append("")
    lines.append("Ma'lumotlar bazadan avtomatik hisoblanadi.")
    return "\n".join(lines)


async def show_stats(event, db: Database) -> None:
    await event.answer(format_statistics(await db.get_stats()), reply_markup=main_menu())


@router.message(F.text == BTN_STATS)
async def user_stats(message: Message, db: Database) -> None:
    await show_stats(message, db)


@router.callback_query(F.data == "stats:admin", IsAdminFilter())
async def admin_stats(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    text = format_statistics(await db.get_stats())
    text += (
        "\n\n👁 Adminlar soni: "
        + str(await db.count_admins())
        + "\n📝 Ko'rib chiqilgan arizalar: "
        + str((await db.get_stats())["approved"] + (await db.get_stats())["rejected"])
    )
    await callback.message.answer(text, reply_markup=back_to_admin())


@router.callback_query(F.data == "stats:bot", IsAdminFilter())
async def bot_stats(callback: CallbackQuery, db: Database) -> None:
    actions = await db.get_actions(1)
    stats = await db.get_stats()
    size_kb = round(db.path.stat().st_size / 1024, 1) if db.path.exists() else 0
    await callback.answer()
    await callback.message.answer(
        "📈 BOT STATISTIKASI\n\n"
        f"👤 Ro'yxatdan o'tgan o'quvchilar: {stats['total']}\n"
        f"🛡 Faol adminlar: {await db.count_admins()}\n"
        f"📋 Jami harakatlar logi: {len(await db.get_actions(10000))}\n"
        f"💾 Baza hajmi: {size_kb} KB\n"
        f"🕐 Oxirgi harakat: {actions[0]['created_at'] if actions else NO_DATA}",
        reply_markup=back_to_admin(),
    )
