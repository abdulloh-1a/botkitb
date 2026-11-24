"""Tutib olinmagan (eskirgan) tugmalar uchun xavfsiz fallback."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.main import main_menu

logger = logging.getLogger(__name__)

router = Router(name="fallback")


@router.callback_query()
async def unknown_callback(callback: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    logger.warning(
        "Noma'lum callback: data=%r user=%s chat=%s state=%s",
        callback.data,
        callback.from_user.id,
        callback.message.chat.id if callback.message else None,
        current,
    )
    await callback.answer()
    await callback.message.answer(
        "⚠️ Bu tugma eskirgan yoki allaqachon ishlatilgan.\n\n"
        "Ariza topshirishni davom ettirish uchun /apply buyrug'idan foydalaning "
        "yoki asosiy menyudan qayta kirish tugmasini bosing.",
        reply_markup=main_menu(),
    )


@router.message(Command("reset"))
async def reset_state(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("FSM holati tozalandi. Qaytadan /apply bosing.", reply_markup=main_menu())
