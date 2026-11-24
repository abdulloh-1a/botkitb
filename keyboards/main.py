"""Asosiy menyu va umumiy tugmalar."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import STATUS_REJECTED

BTN_APPLY = "📝 Ariza topshirish"
BTN_ABOUT = "📖 Musobaqa haqida"
BTN_STATS = "📊 Ishtirokchilar statistikasi"
BTN_MY_APP = "👤 Mening arizam"
BTN_CONTACT = "📞 Bog'lanish"

BTN_BACK = "⬅️ Orqaga"
BTN_CANCEL = "❌ Bekor qilish"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_APPLY), KeyboardButton(text=BTN_MY_APP)],
            [KeyboardButton(text=BTN_ABOUT), KeyboardButton(text=BTN_STATS)],
            [KeyboardButton(text=BTN_CONTACT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyu bo'limini tanlang",
    )


def back_cancel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def cancel_only() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamini yuborish", request_contact=True)],
            [KeyboardButton(text="✏️ Qo'lda kiritish")],
            [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Contact yoki raqamni qo'lda kiriting",
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def restart_application(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Qayta ariza topshirish",
                    callback_data=f"app:restart:{app_id}",
                )
            ],
            [InlineKeyboardButton(text="« Asosiy menyu", callback_data="menu:main")],
        ]
    )


def status_action(status: str, app_id: int) -> InlineKeyboardMarkup:
    if status == STATUS_REJECTED:
        return restart_application(app_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="« Asosiy menyu", callback_data="menu:main")]]
    )
