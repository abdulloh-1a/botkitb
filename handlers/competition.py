"""Musobaqa sanasi/vaqti/joyini belgilash va ishtirokchilarga xabar yuborish."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import DEFAULT_VENUE, ORGANIZER, SUPER_ADMIN_ID
from database import Database
from filters.admin import CanBroadcastFilter, IsAdminFilter, IsSuperAdminFilter
from keyboards.admin import back_to_admin, broadcast_confirm, competition_keyboard
from keyboards.main import BTN_CANCEL, cancel_only, main_menu
from services.notifications import broadcast_announcement, build_announcement
from states.application import AdminStates
from utils.validators import validate_text_length

logger = logging.getLogger(__name__)

router = Router(name="competition")

SETTING_FIELDS = {
    "date": ("competition_date", AdminStates.set_date, "📅 Sana", "Masalan: 25-noyabr 2026-yil"),
    "time": ("competition_time", AdminStates.set_time, "⏰ Vaqt", "Masalan: 10:00"),
    "place": ("competition_place", AdminStates.set_place, "📍 Joy", "Masalan: 10-maktab, 2-qavat"),
}


# --- Bekor qilish (ma'lumot kirituvchi handlerlardan OLDIN turadi) --------
@router.message(AdminStates.set_date, F.text == BTN_CANCEL)
@router.message(AdminStates.set_time, F.text == BTN_CANCEL)
@router.message(AdminStates.set_place, F.text == BTN_CANCEL)
@router.message(AdminStates.broadcast, F.text == BTN_CANCEL)
async def cancel_operation(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Amal bekor qilindi.", reply_markup=main_menu())


@router.callback_query(F.data == "comp:view", IsAdminFilter())
async def view_competition(callback: CallbackQuery, db: Database) -> None:
    settings = await db.get_all_settings()
    await callback.answer()
    await callback.message.answer(
        "📅 MUSOBAQA MA'LUMOTI\n\n"
        f"Sana: {settings.get('competition_date') or 'belgilanmagan'}\n"
        f"Vaqt: {settings.get('competition_time') or 'belgilanmagan'}\n"
        f"Joy: {settings.get('competition_place') or DEFAULT_VENUE}\n\n"
        f"Tashkilotchi: {ORGANIZER}",
        reply_markup=competition_keyboard(callback.from_user.id == SUPER_ADMIN_ID),
    )


@router.callback_query(F.data.startswith("comp:set:"), IsSuperAdminFilter())
async def set_competition_start(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 2)[2]
    if field not in SETTING_FIELDS:
        await callback.answer("Noto'g'ri maydon", show_alert=True)
        return
    _, _, title, example = SETTING_FIELDS[field]
    await callback.answer()
    await state.set_state(SETTING_FIELDS[field][1])
    await state.update_data(setting_field=field)
    await callback.message.answer(
        f"{title} uchun qiymat kiriting.\nNamuna: {example}\n\nBekor qilish uchun «{BTN_CANCEL}»",
        reply_markup=cancel_only(),
    )


@router.message(AdminStates.set_date, IsSuperAdminFilter())
@router.message(AdminStates.set_time, IsSuperAdminFilter())
@router.message(AdminStates.set_place, IsSuperAdminFilter())
async def set_competition_value(message: Message, state: FSMContext, db: Database) -> None:
    current = await state.get_state()
    field = next((key for key, value in SETTING_FIELDS.items() if value[1] == current), None)
    if not field:
        await state.clear()
        return
    key, _, title, _ = SETTING_FIELDS[field]
    value, error = validate_text_length(message.text or "", 2, 150)
    if error:
        await message.answer(error + " Qaytadan kiriting:", reply_markup=cancel_only())
        return
    await db.set_setting(key, value)
    await state.clear()
    await db.log_action(message.from_user.id, f"set_{field}", value)
    await message.answer(f"✅ {title} saqlandi: {value}", reply_markup=competition_keyboard(True))


# --- Ommaviy xabar --------------------------------------------------------
@router.callback_query(F.data == "comp:broadcast", CanBroadcastFilter())
async def broadcast_start(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    settings = await db.get_all_settings()
    default_text = build_announcement(settings)
    await state.set_state(AdminStates.broadcast)
    await state.update_data(broadcast_text=default_text)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Namunaviy xabarni olish", callback_data="comp:broadcast:template")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="comp:broadcast:cancel")],
        ]
    )
    await callback.answer()
    await callback.message.answer(
        "📢 Barcha tasdiqlangan ishtirokchilarga yuboriladigan xabar matnini kiriting "
        "yoki namunaviy xabardan foydalaning:\n\n" + default_text,
        reply_markup=markup,
    )


@router.message(AdminStates.broadcast, CanBroadcastFilter())
async def broadcast_custom_text(message: Message, state: FSMContext) -> None:
    text, error = validate_text_length(message.text or "", 10, 3500)
    if error:
        await message.answer(error + " Qaytadan kiriting.", reply_markup=cancel_only())
        return
    await state.update_data(broadcast_text=text)
    await message.answer("Xabar tayyor. Yuborishni tasdiqlang:", reply_markup=broadcast_confirm())


@router.callback_query(F.data == "comp:broadcast:template", CanBroadcastFilter())
async def broadcast_template(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.answer()
    await callback.message.answer(
        "Xabar tayyor. Yuborishni tasdiqlang:\n\n" + data["broadcast_text"],
        reply_markup=broadcast_confirm(),
    )


@router.callback_query(F.data == "comp:broadcast:cancel", CanBroadcastFilter())
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Bekor qilindi")
    await callback.message.answer("Xabar yuborish bekor qilindi.", reply_markup=back_to_admin())


@router.callback_query(F.data == "comp:broadcast:send", CanBroadcastFilter())
async def broadcast_send(
    callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot
) -> None:
    data = await state.get_data()
    text = data.get("broadcast_text") or build_announcement(await db.get_all_settings())
    await state.clear()
    await callback.answer()
    sent, failed = await broadcast_announcement(bot, db, text)
    await db.log_action(callback.from_user.id, "broadcast", f"sent={sent}, failed={failed}")
    await callback.message.answer(
        f"📢 Xabar yuborish yakunlandi.\n\n✅ Yuborildi: {sent}\n❌ Xatolik: {failed}",
        reply_markup=back_to_admin(),
    )
    logger.info("Xabar yuborildi: sent=%s failed=%s admin=%s", sent, failed, callback.from_user.id)
