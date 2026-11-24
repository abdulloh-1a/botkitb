"""Botga kirish, asosiy menyu, musobaqa haqida va bog'lanish bo'limlari."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import CREATOR, DISTRICT, ORGANIZER, REGION, SCHOOL_NAME
from keyboards.main import (
    BTN_ABOUT,
    BTN_CONTACT,
    main_menu,
)
from services.notifications import build_announcement

logger = logging.getLogger(__name__)

router = Router(name="start")

WELCOME = (
    "Assalomu alaykum!\n\n"
    "10-umumiy o'rta ta'lim maktabi Kengashi tomonidan tashkil etilayotgan "
    "KITOBXONLIK MUSOBAQASI rasmiy Telegram botiga xush kelibsiz!\n\n"
    "Ushbu musobaqada faqat Farg'ona viloyati, Toshloq tumani, 10-maktabning "
    "6–11-sinf o'quvchilari qatnashishi mumkin.\n\n"
    "Ariza topshirish uchun quyidagi tugmani bosing."
)

ABOUT = (
    "📖 MUSOBAQA HAQIDA\n\n"
    "Kitobxonlik musobaqasi 10-umumiy o'rta ta'lim maktabi Kengashi tomonidan "
    "o'quvchilarning kitob o'qishga qiziqishini oshirish, bilim va nutq madaniyatini "
    "rivojlantirish maqsadida tashkil etiladi.\n\n"
    f"🏫 Tashkilotchi:\n{ORGANIZER}\n\n"
    "👥 Qatnashchilar: faqat ushbu maktabning 6–11-sinf o'quvchilari.\n"
    "📝 Qatnashish tartibi: bot orqali ariza topshirish va admin tasdiqlashi.\n\n"
    f"👨‍💻 Bot yaratuvchisi:\n{CREATOR}"
)

CONTACT = (
    "📞 BO'GLANISH\n\n"
    f"{ORGANIZER}\n\n"
    "Savollaringiz bo'lsa, ushbu botga yozing – ko'rib chiqamiz.\n\n"
    f"👨‍💻 Bot yaratuvchisi: {CREATOR}\n"
    f"📍 Manzil: {REGION}, {DISTRICT}, {SCHOOL_NAME}"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()  # eski tugmalar/holatlar qayta boshlashda o'chiriladi
    await message.answer(WELCOME, reply_markup=main_menu())
    logger.info("Yangi foydalanuvchi: %s", message.from_user.id)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(WELCOME, reply_markup=main_menu())


@router.message(F.text == BTN_ABOUT)
async def about(message: Message) -> None:
    await message.answer(ABOUT, reply_markup=main_menu())


@router.message(F.text == BTN_CONTACT)
async def contact(message: Message) -> None:
    await message.answer(CONTACT, reply_markup=main_menu())


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu())


@router.callback_query(F.data == "menu:close")
async def close_menu(callback: CallbackQuery) -> None:
    await callback.answer("Panel yopildi")
    try:
        await callback.message.delete()
    except Exception as exc:  # noqa: BLE001 - xabar o'chirilmasa, xatolik yuborilmaydi
        logger.debug("Xabar o'chirilmadi: %s", exc)


@router.message(Command("competition"))
async def competition_info(message: Message, db) -> None:
    settings = await db.get_all_settings()
    await message.answer(build_announcement(settings), reply_markup=main_menu())
