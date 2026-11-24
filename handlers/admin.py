"""Admin paneli: arizalar, tasdiqlash, qidirish va admin boshqaruvi."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import (
    STATUS_APPROVED,
    STATUS_LABELS,
    STATUS_PENDING,
    STATUS_REJECTED,
    SUPER_ADMIN_ID,
)
from database import Database
from filters.admin import IsAdminFilter, IsSuperAdminFilter
from keyboards.admin import (
    admin_list_keyboard,
    admin_management_keyboard,
    admin_menu,
    applications_list,
    back_to_admin,
    detail_keyboard,
    status_filter_keyboard,
)
from keyboards.main import BTN_CANCEL, cancel_only, main_menu
from services.export import export_applications
from services.notifications import format_application, notify_review_result
from states.application import AdminStates
from utils.validators import validate_telegram_id, validate_text_length

logger = logging.getLogger(__name__)

router = Router(name="admin")
NO_DATA = "yo'q"
PER_PAGE = 8
STATUS_MAP = {
    "all": None,
    STATUS_PENDING: STATUS_PENDING,
    STATUS_APPROVED: STATUS_APPROVED,
    STATUS_REJECTED: STATUS_REJECTED,
}
STATUS_TITLES = {
    "all": "📋 BARCHA ARIZALAR",
    STATUS_PENDING: "⏳ KUTILAYOTGAN ARIZALAR",
    STATUS_APPROVED: "✅ TASDIQLANGAN ARIZALAR",
    STATUS_REJECTED: "❌ RAD ETILGAN ARIZALAR",
}


async def open_admin_panel(event, user_id: int, db: Database) -> None:
    is_super = user_id == SUPER_ADMIN_ID
    can_broadcast = await db.can_broadcast(user_id)
    text = (
        "🛡 ADMIN PANELI\n\n"
        f"Rolingiz: {'👑 Super admin' if is_super else '🛡 Admin'}\n"
        f"Telegram ID: {user_id}\n\n"
        "Kerakli bo'limni tanlang:"
    )
    await event.answer(text, reply_markup=admin_menu(is_super, can_broadcast))


# --- Kirish ---------------------------------------------------------------
@router.message(Command("admin"), IsAdminFilter())
@router.message(Command("panel"), IsAdminFilter())
async def admin_panel(message: Message, db: Database) -> None:
    await open_admin_panel(message, message.from_user.id, db)


@router.message(Command("admin"))
@router.message(Command("panel"))
async def admin_denied(message: Message) -> None:
    await message.answer(
        "⛔ Sizda admin huquqi yo'q. Bu buyruq faqat maktab Kengashi tomonidan "
        "tayinlangan adminlar uchun.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "menu:admin", IsAdminFilter())
async def admin_panel_callback(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    await open_admin_panel(callback.message, callback.from_user.id, db)


# --- Arizalar ro'yxati ----------------------------------------------------
@router.callback_query(F.data.startswith("list:"), IsAdminFilter())
async def list_applications(callback: CallbackQuery, db: Database) -> None:
    try:
        _, status_key, page_raw = callback.data.split(":")
        page = max(0, int(page_raw))
    except (ValueError, TypeError):
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return
    if status_key not in STATUS_MAP:
        await callback.answer("Bunday ro'yxat yo'q", show_alert=True)
        return

    status = STATUS_MAP[status_key]
    total = await db.count_applications(status)
    items = await db.get_applications(status, limit=PER_PAGE, offset=page * PER_PAGE)
    await callback.answer()
    if not items:
        await callback.message.answer(
            f"{STATUS_TITLES[status_key]}\n\nRo'yxat bo'sh.",
            reply_markup=status_filter_keyboard(),
        )
        return
    await callback.message.answer(
        f"{STATUS_TITLES[status_key]}\n\nJami: {total} ta ariza",
        reply_markup=applications_list(items, status_key, page, total, PER_PAGE),
    )


@router.callback_query(F.data.startswith("app:"), IsAdminFilter())
async def application_details(callback: CallbackQuery, db: Database) -> None:
    try:
        app_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri ID", show_alert=True)
        return
    app = await db.get_application_by_id(app_id)
    if not app:
        await callback.answer("Ariza topilmadi", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(format_application(app), reply_markup=detail_keyboard(app))


# --- Tasdiqlash / rad etish ----------------------------------------------
@router.callback_query(F.data.startswith("review:"), IsAdminFilter())
async def review_application(
    callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot
) -> None:
    try:
        _, app_id_raw, action = callback.data.split(":")
        app_id = int(app_id_raw)
    except (ValueError, TypeError):
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return

    app = await db.get_application_by_id(app_id)
    if not app:
        await callback.answer("Ariza topilmadi", show_alert=True)
        return
    if app["status"] != STATUS_PENDING:
        await callback.answer("Bu ariza allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    if action == "approve":
        ok = await db.update_status(app_id, STATUS_APPROVED, callback.from_user.id)
        if not ok:
            await callback.answer("Ariza allaqachon tasdiqlangan!", show_alert=True)
            return
        await db.log_action(callback.from_user.id, "approve", f"#{app_id:04d}")
        await notify_review_result(bot, await db.get_application_by_id(app_id))
        await callback.answer("Ariza tasdiqlandi ✅")
        await callback.message.answer(
            f"✅ Ariza #{app_id:04d} tasdiqlandi va o'quvchiga xabar yuborildi."
        )
        logger.info("Ariza #%s tasdiqlandi, admin=%s", app_id, callback.from_user.id)
        return

    if action == "reject":
        await state.set_state(AdminStates.reject_reason)
        await state.update_data(reject_app_id=app_id)
        await callback.answer()
        await callback.message.answer(
            f"❌ Ariza #{app_id:04d} ni rad etish sababini yozing:",
            reply_markup=cancel_only(),
        )


@router.message(AdminStates.reject_reason, F.text == BTN_CANCEL)
async def cancel_reject(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Rad etish bekor qilindi.", reply_markup=main_menu())


@router.message(AdminStates.reject_reason, IsAdminFilter())
async def reject_reason(
    message: Message, state: FSMContext, db: Database, bot: Bot
) -> None:
    reason, error = validate_text_length(message.text or "", 5, 500)
    if error:
        await message.answer(error + " Qaytadan yozing:", reply_markup=cancel_only())
        return
    data = await state.get_data()
    app_id = int(data["reject_app_id"])
    ok = await db.update_status(
        app_id, STATUS_REJECTED, message.from_user.id, reason=reason
    )
    await state.clear()
    if not ok:
        await message.answer("Ariza allaqachon ko'rib chiqilgan.", reply_markup=main_menu())
        return
    await db.log_action(message.from_user.id, "reject", f"#{app_id:04d}: {reason}")
    await notify_review_result(bot, await db.get_application_by_id(app_id))
    await message.answer(
        f"❌ Ariza #{app_id:04d} rad etildi va sabab o'quvchiga yuborildi.",
        reply_markup=main_menu(),
    )
    logger.info("Ariza #%s rad etildi, admin=%s", app_id, message.from_user.id)


# --- Qidirish -------------------------------------------------------------
@router.callback_query(F.data == "admin:search", IsAdminFilter())
async def start_search(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.search)
    await callback.message.answer(
        "🔎 Qidiruv so'rovini kiriting (ism, familiya, sinf, telefon yoki ariza ID):",
        reply_markup=cancel_only(),
    )


@router.message(AdminStates.search, F.text == BTN_CANCEL)
async def cancel_search(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Qidiruv bekor qilindi.", reply_markup=main_menu())


@router.message(AdminStates.search, IsAdminFilter())
async def do_search(message: Message, state: FSMContext, db: Database) -> None:
    query, error = validate_text_length(message.text or "", 2, 100)
    if error:
        await message.answer(error, reply_markup=cancel_only())
        return
    results = await db.search_applications(query)
    await state.clear()
    if not results:
        await message.answer(
            f"«{query}» bo'yicha hech narsa topilmadi.", reply_markup=back_to_admin()
        )
        return
    text = f"🔎 «{query}» bo'yicha {len(results)} ta natija:\n\n" + "\n".join(
        f"#{a['id']:04d} {a['first_name']} {a['last_name']} — "
        f"{a['grade']}-sinf, {STATUS_LABELS[a['status']]}"
        for a in results[:10]
    )
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"#{a['id']:04d} ochish", callback_data=f"app:{a['id']}")]
            for a in results[:10]
        ]
        + [[InlineKeyboardButton(text="« Admin paneli", callback_data="menu:admin")]]
    )
    await message.answer(text, reply_markup=markup)


# --- Adminlarni boshqarish (faqat super admin) ---------------------------
@router.callback_query(F.data == "admin:manage", IsSuperAdminFilter())
async def manage_admins(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "👥 ADMINLARNI BOSHQARISH\n\n"
        f"Super admin ID: {SUPER_ADMIN_ID} (o'zgartirib bo'lmaydi)\n\n"
        "Amalni tanlang:",
        reply_markup=admin_management_keyboard(),
    )


@router.callback_query(F.data == "admin:list", IsSuperAdminFilter())
async def list_admins(callback: CallbackQuery, db: Database) -> None:
    admins = await db.list_admins()
    lines = ["👑 Super admin:", f"  ID: {SUPER_ADMIN_ID} (himoyalangan)", "", "🛡 Adminlar:"]
    active = [a for a in admins if a["user_id"] != SUPER_ADMIN_ID]
    if not active:
        lines.append("  Hali admin qo'shilmagan.")
    else:
        for admin in active:
            state = "faol" if admin["is_active"] else "nosoz"
            bc = "✅ xabar huquqi bor" if admin["can_broadcast"] else "🔕 xabar huquqi yo'q"
            lines.append(
                f"  ID: {admin['user_id']} | @{admin.get('username') or NO_DATA} | {state} | {bc}"
            )
    await callback.answer()
    await callback.message.answer("\n".join(lines), reply_markup=admin_list_keyboard(admins))


@router.callback_query(F.data == "admin:add", IsSuperAdminFilter())
async def add_admin_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.add_admin_id)
    await callback.message.answer(
        "Yangi adminning Telegram ID sini kiriting (@userinfobot orqali olinadi):",
        reply_markup=cancel_only(),
    )


@router.message(AdminStates.add_admin_id, F.text == BTN_CANCEL)
@router.message(AdminStates.add_admin_username, F.text == BTN_CANCEL)
async def cancel_add_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Admin qo'shish bekor qilindi.", reply_markup=main_menu())


@router.message(AdminStates.add_admin_id, IsSuperAdminFilter())
async def add_admin_id(message: Message, state: FSMContext, db: Database) -> None:
    user_id, error = validate_telegram_id(message.text or "")
    if error:
        await message.answer(error, reply_markup=cancel_only())
        return
    if user_id == SUPER_ADMIN_ID:
        await message.answer("Bu ID super admin ga tegishli. Uni o'zgartirib bo'lmaydi.", reply_markup=cancel_only())
        return
    if await db.is_admin(user_id):
        await message.answer("Bu foydalanuvchi allaqachon admin.", reply_markup=cancel_only())
        return
    await state.update_data(new_admin_id=user_id)
    await state.set_state(AdminStates.add_admin_username)
    await message.answer(
        "Admin username'ini kiriting (ixtiyoriy, keyingi qadamda tasdiqlanadi).\n"
        "Masalan: @admin_yoki_yo‘q",
        reply_markup=cancel_only(),
    )


@router.message(AdminStates.add_admin_username, IsSuperAdminFilter())
async def add_admin_username(message: Message, state: FSMContext) -> None:
    username = (message.text or "").strip().lstrip("@")
    if username.lower() in {"yo'q", "yoq", "no", "-"}:
        username = ""
    if len(username) > 64:
        await message.answer("Username 64 belgidan qisqa bo'lishi kerak.", reply_markup=cancel_only())
        return
    data = await state.get_data()
    await state.update_data(new_admin_username=username)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="admin:confirm_add")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:cancel_add")],
        ]
    )
    await message.answer(
        f"Yangi admin:\n\nID: {data['new_admin_id']}\n"
        f"Username: {username or NO_DATA}\n\nTasdiqlaysizmi?",
        reply_markup=markup,
    )


@router.callback_query(F.data == "admin:confirm_add", IsSuperAdminFilter())
async def confirm_add_admin(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    user_id = int(data["new_admin_id"])
    username = data.get("new_admin_username", "")
    ok = await db.add_admin(user_id, username or None, SUPER_ADMIN_ID)
    await state.clear()
    await callback.answer()
    if not ok:
        await callback.message.answer("Admin qo'shishda xatolik yuz berdi.", reply_markup=main_menu())
        return
    await db.log_action(SUPER_ADMIN_ID, "add_admin", str(user_id))
    await callback.message.answer(
        f"✅ Foydalanuvchi {user_id} admin etib tayinlandi.", reply_markup=main_menu()
    )
    try:
        await callback.bot.send_message(
            user_id,
            "🎉 Siz 10-maktab kitobxonlik musobaqasi botining admini etib tayinlandi!\n\n"
            "Arizalarni ko'rish va tasdiqlash uchun /admin buyrug'idan foydalaning.",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Yangi adminga xabar yuborilmadi: %s", exc)


@router.callback_query(F.data == "admin:cancel_add", IsSuperAdminFilter())
async def cancel_add_admin_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Bekor qilindi")
    await callback.message.answer("Admin qo'shish bekor qilindi.", reply_markup=main_menu())


@router.callback_query(F.data.startswith("admin:remove:"), IsSuperAdminFilter())
async def confirm_remove_admin(callback: CallbackQuery) -> None:
    try:
        user_id = int(callback.data.split(":", 2)[2])
    except ValueError:
        await callback.answer("Noto'g'ri ID", show_alert=True)
        return
    if user_id == SUPER_ADMIN_ID:
        await callback.answer("Super adminni o'chirib bo'lmaydi!", show_alert=True)
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, olish", callback_data=f"admin:confirm_remove:{user_id}"
                )
            ],
            [InlineKeyboardButton(text="❌ Yo'q", callback_data="admin:list")],
        ]
    )
    await callback.answer()
    await callback.message.answer(f"Admin {user_id} lavozimidan olishni tasdiqlaysizmi?", reply_markup=markup)


@router.callback_query(F.data.startswith("admin:confirm_remove:"), IsSuperAdminFilter())
async def remove_admin(callback: CallbackQuery, db: Database) -> None:
    user_id = int(callback.data.split(":", 2)[2])
    ok = await db.remove_admin(user_id)
    await callback.answer()
    if ok:
        await db.log_action(SUPER_ADMIN_ID, "remove_admin", str(user_id))
    await callback.message.answer(
        f"{'✅ Admin lavozimidan olindi.' if ok else '⚠️ Bunday faol admin topilmadi.'}",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data.startswith("admin:toggle:"), IsSuperAdminFilter())
async def toggle_broadcast(callback: CallbackQuery, db: Database) -> None:
    user_id = int(callback.data.split(":", 2)[2])
    admin = await db.get_admin(user_id)
    if not admin:
        await callback.answer("Admin topilmadi", show_alert=True)
        return
    new_value = not bool(admin["can_broadcast"])
    await db.set_broadcast_permission(user_id, new_value)
    await db.log_action(SUPER_ADMIN_ID, "toggle_broadcast", f"{user_id}={new_value}")
    await callback.answer("Huquq o'zgartirildi")
    await callback.message.answer(
        f"Admin {user_id} uchun xabar yuborish huquqi: "
        f"{'✅ berildi' if new_value else '🔕 olindi'}.",
        reply_markup=admin_list_keyboard(await db.list_admins()),
    )


@router.callback_query(F.data.startswith("admin:info:"), IsSuperAdminFilter())
async def admin_info(callback: CallbackQuery, db: Database) -> None:
    user_id = int(callback.data.split(":", 2)[2])
    admin = await db.get_admin(user_id)
    if not admin:
        await callback.answer("Topilmadi", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        f"🛡 ADMIN MA'LUMOTI\n\n"
        f"ID: {admin['user_id']}\n"
        f"Username: @{admin.get('username') or NO_DATA}\n"
        f"Qo'shgan: {admin['added_by']}\n"
        f"Vaqt: {admin['added_at']}\n"
        f"Faol: {'ha' if admin['is_active'] else NO_DATA}\n"
        f"Xabar huquqi: {'ha' if admin['can_broadcast'] else NO_DATA}",
        reply_markup=back_to_admin(),
    )


@router.callback_query(F.data == "admin:activity", IsSuperAdminFilter())
async def admin_activity(callback: CallbackQuery, db: Database) -> None:
    actions = await db.get_actions(25)
    text = "📜 ADMIN FAOLIYATI (oxirgi 25 ta)\n\n"
    if not actions:
        text += "Hali harakatlar yo'q."
    else:
        for action in actions:
            text += (
                f"#{action['id']} | {action['created_at']}\n"
                f"  Admin: {action['admin_id']} | {action['action']}: {action['details']}\n"
            )
    await callback.answer()
    await callback.message.answer(text[:4000], reply_markup=back_to_admin())


# --- Excel eksporti -------------------------------------------------------
@router.callback_query(F.data == "export:excel", IsSuperAdminFilter())
async def export_excel(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    file = await export_applications(db)
    await callback.message.answer_document(
        file,
        caption=f"📥 Arizalar eksporti ({await db.count_applications()} ta ariza).",
    )
    await db.log_action(SUPER_ADMIN_ID, "export_excel", "")


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer("Bu element himoyalangan")
