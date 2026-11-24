"""Ariza topshirish: FSM bosqichlari, tasdiqlash, tahrirlash va qayta yuborish."""

from __future__ import annotations

import logging
import random

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import GENDER_LABELS, STATUS_LABELS, STATUS_REJECTED
from database import Database
from keyboards.application import (
    application_user_keyboard,
    confirm_keyboard,
    edit_keyboard,
    gender_keyboard,
    grades_keyboard,
    my_applications_keyboard,
    suggested_phone_keyboard,
)
from keyboards.main import (
    BTN_APPLY,
    BTN_BACK,
    BTN_CANCEL,
    BTN_MY_APP,
    back_cancel,
    main_menu,
    phone_keyboard,
)
from services.notifications import format_application, notify_new_application
from states.application import ApplicationStates
from utils.validators import (
    normalize_phone,
    validate_age,
    validate_gender,
    validate_grade,
    validate_name,
)

logger = logging.getLogger(__name__)

router = Router(name="application")


async def reply(event, text: str, reply_markup=None) -> None:
    """Message yoki CallbackQuery bo'lishidan qat'i nazar xabar yuboradi.

    CallbackQuery.answer() faqat tugma bosilganini tasdiqlaydi, matn va
    klaviatura yubormaydi — shuning uchun xabar uchun message.answer ishlatamiz.
    """
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, reply_markup=reply_markup)
    else:
        await event.answer(text, reply_markup=reply_markup)

FIRST = ApplicationStates.first_name.state
LAST = ApplicationStates.last_name.state
AGE = ApplicationStates.age.state
GRADE = ApplicationStates.grade.state
GENDER = ApplicationStates.gender.state
PHONE = ApplicationStates.phone.state
CONFIRM = ApplicationStates.confirm.state

FIELD_BY_STATE = {
    FIRST: "first_name",
    LAST: "last_name",
    AGE: "age",
    GRADE: "grade",
    GENDER: "gender",
    PHONE: "phone",
}
STATE_BY_FIELD = {value: key for key, value in FIELD_BY_STATE.items()}
NEXT_STATE = {FIRST: LAST, LAST: AGE, AGE: GRADE, GRADE: GENDER, GENDER: PHONE, PHONE: CONFIRM}

PROMPTS = {
    FIRST: ("1️⃣ Ismingizni kiriting:", back_cancel()),
    LAST: ("2️⃣ Familiyangizni kiriting:", back_cancel()),
    AGE: ("3️⃣ Yoshingizni kiriting (masalan, 14):", back_cancel()),
    GRADE: (
        "4️⃣ Sinfingizni tanlang (6–11):\n"
        "Tugmadan bosing yoki raqam yuboring (masalan, 9).",
        grades_keyboard(),
    ),
    GENDER: (
        "5️⃣ Jinsingizni tanlang:\n"
        "1 — 👦 O'g'il bola, 2 — 👧 Qiz bola (yoki tugmadan bosing).",
        gender_keyboard(),
    ),
    PHONE: ("6️⃣ Telefon raqamingizni yuboring:", phone_keyboard()),
}


def preview(data: dict) -> str:
    gender = GENDER_LABELS.get(data.get("gender"), "—")
    return (
        "📋 SIZNING ARIZANGIZ\n\n"
        f"Ism: {data.get('first_name') or '—'}\n"
        f"Familiya: {data.get('last_name') or '—'}\n"
        f"Yosh: {data.get('age') or '—'}\n"
        f"Sinf: {data.get('grade') or '—'}-sinf\n"
        f"Jinsi: {gender}\n"
        f"Telefon: {data.get('phone') or '—'}\n\n"
        "Ma'lumotlar to'g'ri bo'lsa, arizani yuboring."
    )


async def ask(event, state_value: str, data: dict) -> None:
    """FSM bosqichi uchun savol va tugmalarni yuboradi."""
    if state_value == CONFIRM:
        await reply(event, preview(data), reply_markup=confirm_keyboard())
        return
    text, markup = PROMPTS[state_value]
    if state_value == PHONE and data.get("suggested_phone"):
        suggested = data["suggested_phone"]
        await reply(
            event,
            f"📌 Avtomatik raqam: `{suggested}`\n\n"
            "Raqamni nusxalab olishingiz yoki «✅ Shu raqamni ishlatish» tugmasini bosishingiz mumkin.\n"
            "Boshqa odam uchun yangi raqam yuborish uchun pastdagi klaviaturadan foydalaning.",
            reply_markup=suggested_phone_keyboard(),
        )
    if data.get("editing"):
        text = "✏️ Tahrirlash rejimi\n\n" + text
    await reply(event, text, reply_markup=markup)


async def move_to(event, state: FSMContext, target: str) -> None:
    data = await state.get_data()
    current = await state.get_state()
    history = list(data.get("history") or [])
    if current and current != target:
        history.append(current)
    await state.update_data(history=history)
    await state.set_state(target)
    await ask(event, target, await state.get_data())


async def save_and_advance(
    event, state: FSMContext, field: str, value, current: str
) -> None:
    data = await state.get_data()
    await state.update_data({field: value})
    if data.get("editing"):
        await state.update_data(editing=False)
        target = CONFIRM
        # Tasdiqlash ekranidagi "Orqaga" tahrir qilingan maydonga qaytish uchun
        await state.update_data(history=[STATE_BY_FIELD[field]])
    else:
        target = NEXT_STATE[current]
    await move_to(event, state, target)


MAX_PER_USER = 5


async def begin_application(
    event, state: FSMContext, db: Database, user_id: int, app_id: int | None = None
) -> None:
    """Yangi ariza yoki rad etilgan arizani qayta yuborish FSM ni boshlaydi."""
    apps = await db.get_applications_by_user(user_id)
    # Avtomatik taklif qilinadigan raqam: shu profil oxirgi ishlatgan raqam.
    suggested = None
    for candidate in apps:
        if candidate.get("phone"):
            maybe_phone, phone_error = normalize_phone(candidate["phone"])
            if not phone_error:
                suggested = maybe_phone
                break
    if app_id is None and len(apps) >= MAX_PER_USER:
        await reply(event,
            f"⚠️ Bitta Telegram profilidan maksimal {MAX_PER_USER} ta ariza topshirish mumkin.\n\n"
            "Siz bu cheklovga yetdingiz. Mavjud arizalar ro'yxati:",
            reply_markup=my_applications_keyboard(apps),
        )
        return

    if app_id is not None:
        app = await db.get_application_by_id(app_id)
        if not app or app["user_id"] != user_id or app["status"] != STATUS_REJECTED:
            await reply(event, "Bu arizani qayta topshirib bo'lmaydi.", reply_markup=main_menu())
            return
        initial = {
            "first_name": app["first_name"],
            "last_name": app["last_name"],
            "age": app["age"],
            "grade": app["grade"],
            "gender": app["gender"],
            "phone": app["phone"],
        }
        note = "🔄 Avvalgi ma'lumotlar yuklandi. O'zgartirish uchun yana yuboring yoki Orqaga bosing.\n\n"
    else:
        initial = {
            "first_name": None,
            "last_name": None,
            "age": None,
            "grade": None,
            "gender": None,
            "phone": None,
        }
        note = (
            f"ℹ️ Bitta profildan {MAX_PER_USER} tagacha ariza topshirishingiz mumkin.\n"
            f"Hozirda sizda: {len(apps)} ta.\n\n"
        )

    await state.set_data(
        {
            **initial,
            "history": [],
            "editing": False,
            "reapply_app_id": app_id,
            "suggested_phone": suggested,
        }
    )
    await state.set_state(FIRST)
    text, markup = PROMPTS[FIRST]
    await reply(event, note + text, reply_markup=markup)


async def show_my_application(event, db: Database, user_id: int) -> None:
    apps = await db.get_applications_by_user(user_id)
    if not apps:
        await reply(event,
            "Siz hali ariza topshirmagansiz. Ariza topshirish uchun tugmani bosing.",
            reply_markup=main_menu(),
        )
        return
    lines = [
        f"👤 MENING ARIZALARIM ({len(apps)}/{MAX_PER_USER})\n",
        "Batafsil ma'lumot va telefon raqamini o'zgartirish uchun arizani tanlang.",
    ]
    await reply(event, "\n".join(lines), reply_markup=my_applications_keyboard(apps))


# --- Bekor qilish va orqaga (barcha FSM bosqichlarida) --------------------
@router.message(ApplicationStates(), F.text == BTN_CANCEL)
@router.message(ApplicationStates(), Command("cancel"))
async def cancel_application(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Ariza topshirish bekor qilindi.", reply_markup=main_menu())


@router.message(ApplicationStates(), F.text == BTN_BACK)
async def back_step(message: Message, state: FSMContext) -> None:
    await go_back(message, state)


@router.callback_query(ApplicationStates(), F.data == "nav:back")
async def back_step_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await go_back(callback, state)


async def go_back(event, state: FSMContext) -> None:
    data = await state.get_data()
    history = list(data.get("history") or [])
    if not history:
        await state.clear()
        await reply(event, "Boshlash uchun yana ariza topshiring.", reply_markup=main_menu())
        return
    target = history.pop()
    await state.update_data(history=history, editing=False)
    await state.set_state(target)
    await ask(event, target, await state.get_data())


@router.callback_query(ApplicationStates(), F.data == "nav:cancel")
async def cancel_step_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Ariza bekor qilindi")
    await callback.message.answer("❌ Ariza topshirish bekor qilindi.", reply_markup=main_menu())


# --- Boshlash ------------------------------------------------------------
@router.message(Command("apply"))
@router.message(F.text == BTN_APPLY)
async def apply_start(message: Message, state: FSMContext, db: Database) -> None:
    await begin_application(message, state, db, message.from_user.id)


@router.message(F.text == BTN_MY_APP)
async def my_application(message: Message, db: Database) -> None:
    await show_my_application(message, db, message.from_user.id)


@router.callback_query(F.data == "myapp:list")
async def my_applications_list(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    await show_my_application(callback, db, callback.from_user.id)


@router.callback_query(F.data == "myapp:new")
async def my_applications_new(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await callback.answer()
    await begin_application(callback.message, state, db, callback.from_user.id)


@router.callback_query(
    F.data.startswith("myapp:") & ~F.data.in_({"myapp:list", "myapp:new"})
)
async def my_application_detail(callback: CallbackQuery, db: Database) -> None:
    try:
        app_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Noto'g'ri ariza", show_alert=True)
        return
    app = await db.get_application_by_id(app_id)
    if not app or app["user_id"] != callback.from_user.id:
        await callback.answer("Bu ariza sizga tegishli emas", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        format_application(app, detailed=False)
        + f"\n\nHolat: {STATUS_LABELS.get(app['status'], app['status'])}",
        reply_markup=application_user_keyboard(app),
    )


@router.callback_query(F.data.startswith("app:restart:"))
async def restart_application(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    await callback.answer()
    try:
        app_id = int(callback.data.split(":", 2)[2])
    except ValueError:
        return
    await begin_application(callback.message, state, db, callback.from_user.id, app_id)


@router.callback_query(F.data.startswith("phone:change:"))
async def change_phone_start(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    try:
        app_id = int(callback.data.split(":", 2)[2])
    except ValueError:
        return
    app = await db.get_application_by_id(app_id)
    if not app or app["user_id"] != callback.from_user.id:
        await callback.answer("Bu ariza sizga tegishli emas", show_alert=True)
        return
    await callback.answer()
    await state.set_state(ApplicationStates.change_phone)
    await state.update_data(change_app_id=app_id)
    await callback.message.answer(
        f"📱 Ariza #{app_id:04d} uchun yangi telefon raqamini yuboring.\n"
        "Contact tugmasi yoki qo'lda kiritish mumkin.",
        reply_markup=phone_keyboard(),
    )


@router.callback_query(ApplicationStates.phone, F.data == "phone:use")
async def use_suggested_phone(callback: CallbackQuery, state: FSMContext) -> None:
    """Avtomatik taklif qilingan raqamni bir bosishda qabul qilish."""
    phone = (await state.get_data()).get("suggested_phone")
    if not phone:
        await callback.answer("Avval raqam yuboring", show_alert=True)
        return
    await callback.answer("Raqam qabul qilindi")
    await save_and_advance(callback, state, "phone", phone, PHONE)


@router.callback_query(ApplicationStates.phone, F.data == "phone:generate")
async def generate_phone(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    """Yangi o'quvchi uchun tasodifiy, takrorlanmaydigan raqam taklif qilish."""
    used = {
        (app.get("phone") or "").replace(" ", "")
        for app in await db.get_applications_by_user(callback.from_user.id)
    }
    for _ in range(30):
        candidate = (
            f"+998 {random.randint(90, 99)} {random.randint(100, 999):03d} "
            f"{random.randint(10, 99):02d} {random.randint(10, 99):02d}"
        )
        if candidate.replace(" ", "") not in used:
            break
    await state.update_data(suggested_phone=candidate)
    await callback.answer("Yangi raqam taklif qilindi")
    await reply(
        callback,
        f"🎲 Yangi avtomatik raqam: `{candidate}`\n\n"
        "Uni nusxalab oling yoki «✅ Shu raqamni ishlatish» tugmasini bosing.\n"
        "O'zingiznikini yuborish uchun «✏️ Boshqa raqam yuborish» ni tanlang.",
        reply_markup=suggested_phone_keyboard(),
    )


@router.callback_query(ApplicationStates.phone, F.data == "phone:other")
async def other_phone(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "Yangi telefon raqamini yuboring (contact tugmasi yoki qo'lda):",
        reply_markup=phone_keyboard(),
    )


# --- Matn bosqichlari -----------------------------------------------------
@router.message(ApplicationStates.first_name)
async def get_first_name(message: Message, state: FSMContext) -> None:
    value, error = validate_name(message.text or "", "Ism")
    if error:
        await message.answer(error, reply_markup=back_cancel())
        return
    await save_and_advance(message, state, "first_name", value, FIRST)


@router.message(ApplicationStates.last_name)
async def get_last_name(message: Message, state: FSMContext) -> None:
    value, error = validate_name(message.text or "", "Familiya")
    if error:
        await message.answer(error, reply_markup=back_cancel())
        return
    await save_and_advance(message, state, "last_name", value, LAST)


@router.message(ApplicationStates.age)
async def get_age(message: Message, state: FSMContext) -> None:
    value, error = validate_age(message.text or "")
    if error:
        await message.answer(error, reply_markup=back_cancel())
        return
    await save_and_advance(message, state, "age", value, AGE)


# --- Inline tanlov bosqichlari -------------------------------------------
@router.callback_query(F.data.startswith("grade:"))
async def get_grade(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("age") is None:
        await callback.answer("Avval yoshingizni kiriting.", show_alert=True)
        return
    grade, error = validate_grade(callback.data.split(":", 1)[1])
    if error:
        await callback.answer(error, show_alert=True)
        return
    if await state.get_state() != GRADE:
        await state.set_state(GRADE)
    await callback.answer()
    await save_and_advance(callback, state, "grade", grade, GRADE)


@router.callback_query(F.data.startswith("gender:"))
async def get_gender(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("grade") is None:
        await callback.answer("Avval sinfingizni tanlang.", show_alert=True)
        return
    gender, error = validate_gender(callback.data.split(":", 1)[1])
    if error:
        await callback.answer(error, show_alert=True)
        return
    if await state.get_state() != GENDER:
        await state.set_state(GENDER)
    await callback.answer()
    await save_and_advance(callback, state, "gender", gender, GENDER)


@router.message(ApplicationStates.grade)
async def get_grade_text(message: Message, state: FSMContext) -> None:
    """Sinfni tugmasiz ham yuborish: 6, 7, 8, 9, 10 yoki 11."""
    grade, error = validate_grade(message.text or "")
    if error:
        await message.answer(error, reply_markup=grades_keyboard())
        return
    await save_and_advance(message, state, "grade", grade, GRADE)


@router.message(ApplicationStates.gender)
async def get_gender_text(message: Message, state: FSMContext) -> None:
    """Jinsni tugmasiz ham yuborish: 1 — o'g'il, 2 — qiz."""
    gender, error = validate_gender(message.text or "")
    if error:
        await message.answer(error, reply_markup=gender_keyboard())
        return
    await save_and_advance(message, state, "gender", gender, GENDER)


# --- Telefon raqami -------------------------------------------------------
@router.message(ApplicationStates.phone, F.contact)
async def get_contact(message: Message, state: FSMContext) -> None:
    phone, error = normalize_phone(message.contact.phone_number)
    if error:
        await message.answer(error, reply_markup=phone_keyboard())
        return
    await save_and_advance(message, state, "phone", phone, PHONE)


@router.message(ApplicationStates.phone, F.text)
async def get_phone_text(message: Message, state: FSMContext) -> None:
    if message.text == "✏️ Qo'lda kiritish":
        await message.answer("Raqamni xalqaro formatda kiriting: +998 90 123 45 67", reply_markup=phone_keyboard())
        return
    phone, error = normalize_phone(message.text)
    if error:
        await message.answer(error, reply_markup=phone_keyboard())
        return
    await save_and_advance(message, state, "phone", phone, PHONE)


# --- Telefon raqamini keyinroq o'zgartirish -------------------------------
async def finish_phone_change(message: Message, state: FSMContext, db: Database, value: str) -> None:
    phone, error = normalize_phone(value)
    if error:
        await message.answer(error, reply_markup=phone_keyboard())
        return
    data = await state.get_data()
    app_id = data.get("change_app_id")
    await state.clear()
    ok = await db.update_phone(app_id, phone)
    if not ok:
        await message.answer("Ariza topilmadi.", reply_markup=main_menu())
        return
    await db.log_action(message.from_user.id, "change_phone", f"#{app_id:04d}")
    app = await db.get_application_by_id(app_id)
    await message.answer(
        f"✅ Telefon raqami o'zgartirildi: {phone}\n\n"
        "Yangi raqam arizada saqlandi.",
        reply_markup=application_user_keyboard(app),
    )


@router.message(ApplicationStates.change_phone, F.contact)
async def change_phone_contact(message: Message, state: FSMContext, db: Database) -> None:
    await finish_phone_change(message, state, db, message.contact.phone_number)


@router.message(ApplicationStates.change_phone, F.text)
async def change_phone_text(message: Message, state: FSMContext, db: Database) -> None:
    if message.text == "✏️ Qo'lda kiritish":
        await message.answer(
            "Raqamni xalqaro formatda kiriting: +998 90 123 45 67",
            reply_markup=phone_keyboard(),
        )
        return
    await finish_phone_change(message, state, db, message.text)


# --- Tasdiqlash, tahrirlash va yuborish ----------------------------------
@router.callback_query(ApplicationStates.confirm, F.data == "app:submit")
async def submit_application(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    bot: Bot,
) -> None:
    data = await state.get_data()
    payload = {
        "user_id": callback.from_user.id,
        "username": callback.from_user.username,
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "age": data["age"],
        "grade": data["grade"],
        "gender": data["gender"],
        "phone": data["phone"],
    }
    reapply_id = data.get("reapply_app_id")
    app_id = None
    if reapply_id:
        old = await db.get_application_by_id(reapply_id)
        if old and old["user_id"] == callback.from_user.id and old["status"] == STATUS_REJECTED:
            app_id = reapply_id if await db.update_application(reapply_id, payload) else None
    else:
        if await db.count_user_applications(callback.from_user.id) >= MAX_PER_USER:
            await state.clear()
            await callback.answer("Arizalar soni to'ldi", show_alert=True)
            await callback.message.answer(
                f"⚠️ Bitta profildan maksimal {MAX_PER_USER} ta ariza topshirish mumkin.",
                reply_markup=main_menu(),
            )
            return
        app_id = await db.add_application(payload)
    if app_id is None:
        await state.clear()
        await callback.answer("Ariza yuborib bo'lmadi", show_alert=True)
        await callback.message.answer(
            "Arizani yuborib bo'lmadi. \"👤 Mening arizam\" bo'limidan tekshiring.",
            reply_markup=main_menu(),
        )
        return

    await db.log_action(callback.from_user.id, "submit_application", f"#{app_id:04d}")
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "✅ Arizangiz muvaffaqiyatli yuborildi!\n\n"
        f"Ariza raqamingiz: #{app_id:04d}\n"
        "Holat: ⏳ Kutilmoqda\n\n"
        "Admin ko'rib chiqqach, natija haqida xabar olasiz.",
        reply_markup=main_menu(),
    )
    await notify_new_application(bot, db, app_id)
    logger.info("Yangi ariza #%s yuborildi: user_id=%s", app_id, callback.from_user.id)


@router.callback_query(ApplicationStates.confirm, F.data == "app:edit")
async def edit_application(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("Qaysi ma'lumotni o'zgartirmoqchisiz?", reply_markup=edit_keyboard())


@router.callback_query(ApplicationStates.confirm, F.data.startswith("app:edit:"))
async def edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 2)[2]
    await callback.answer()
    if field == "back":
        await state.update_data(editing=False)
        await state.set_state(CONFIRM)
        await ask(callback, CONFIRM, await state.get_data())
        return
    target = STATE_BY_FIELD.get(field)
    if not target:
        return
    await state.update_data(history=[], editing=True)
    await state.set_state(target)
    await ask(callback, target, await state.get_data())


@router.callback_query(ApplicationStates(), F.data == "app:cancel")
async def cancel_application_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Ariza bekor qilindi")
    await callback.message.answer("❌ Ariza topshirish bekor qilindi.", reply_markup=main_menu())


@router.message(ApplicationStates(), ~F.text)
async def unsupported_content(message: Message) -> None:
    await message.answer(
        "Iltimos, ma'lumotlarni matn yoki tugma yordamida kiriting.",
        reply_markup=back_cancel(),
    )
