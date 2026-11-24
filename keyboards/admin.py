"""Admin va super admin panellari tugmalari."""

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import STATUS_APPROVED, STATUS_PENDING, STATUS_REJECTED, SUPER_ADMIN_ID


def admin_menu(is_super: bool, can_broadcast: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="📋 Barcha arizalar", callback_data="list:all:0"),
            InlineKeyboardButton(text="⏳ Kutilayotganlar", callback_data="list:pending:0"),
        ],
        [
            InlineKeyboardButton(text="✅ Tasdiqlanganlar", callback_data="list:approved:0"),
            InlineKeyboardButton(text="❌ Rad etilganlar", callback_data="list:rejected:0"),
        ],
        [
            InlineKeyboardButton(text="🔎 Ishtirokchi qidirish", callback_data="admin:search"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="stats:admin"),
        ],
        [
            InlineKeyboardButton(text="📅 Musobaqa ma'lumoti", callback_data="comp:view"),
        ],
    ]
    if can_broadcast or is_super:
        rows.append([InlineKeyboardButton(text="📢 Ishtirokchilarga xabar", callback_data="comp:broadcast")])
    if is_super:
        rows.extend(
            [
                [
                    InlineKeyboardButton(text="👥 Adminlar", callback_data="admin:manage"),
                    InlineKeyboardButton(text="📈 Bot statistikasi", callback_data="stats:bot"),
                ],
                [
                    InlineKeyboardButton(text="📥 Excel eksporti", callback_data="export:excel"),
                    InlineKeyboardButton(text="📜 Faoliyat logi", callback_data="admin:activity"),
                ],
            ]
        )
    rows.append([InlineKeyboardButton(text="❌ Yopish", callback_data="menu:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Admin paneli", callback_data="menu:admin")]
        ]
    )


def review_keyboard(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"review:{app_id}:approve"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"review:{app_id}:reject"),
            ],
            [
                InlineKeyboardButton(text="📋 To'liq ma'lumot", callback_data=f"app:{app_id}")
            ],
        ]
    )


def detail_keyboard(app: dict[str, Any]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if app["status"] == STATUS_PENDING:
        rows.append(
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"review:{app['id']}:approve"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"review:{app['id']}:reject"),
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="« Orqaga", callback_data=f"list:{app['status']}:0")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def applications_list(
    items: list[dict[str, Any]], status: str, page: int, total: int, per_page: int = 8
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"#{item['id']:04d} {item['first_name']} {item['last_name']}",
                callback_data=f"app:{item['id']}",
            )
        ]
        for item in items
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"list:{status}:{page - 1}"))
    if (page + 1) * per_page < total:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"list:{status}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="« Admin paneli", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_list_keyboard(admins: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for admin in admins:
        if admin["user_id"] == SUPER_ADMIN_ID:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"👑 Super admin: {admin['user_id']}",
                        callback_data="noop",
                    )
                ]
            )
            continue
        mark = "✅" if admin["can_broadcast"] else "🔕"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🛡 {admin['user_id']}",
                    callback_data=f"admin:info:{admin['user_id']}",
                ),
                InlineKeyboardButton(
                    text=f"{mark} Xabar",
                    callback_data=f"admin:toggle:{admin['user_id']}",
                ),
                InlineKeyboardButton(
                    text="➖ Olish",
                    callback_data=f"admin:remove:{admin['user_id']}",
                ),
            ]
        )
    rows.extend(
        [
            [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="admin:add")],
            [InlineKeyboardButton(text="« Admin paneli", callback_data="menu:admin")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Adminlar ro'yxati", callback_data="admin:list")],
            [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="admin:add")],
            [InlineKeyboardButton(text="« Admin paneli", callback_data="menu:admin")],
        ]
    )


def competition_keyboard(is_super: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📅 Hozirgi ma'lumot", callback_data="comp:view")]]
    if is_super:
        rows.extend(
            [
                [
                    InlineKeyboardButton(text="📅 Sana", callback_data="comp:set:date"),
                    InlineKeyboardButton(text="⏰ Vaqt", callback_data="comp:set:time"),
                ],
                [InlineKeyboardButton(text="📍 Joy", callback_data="comp:set:place")],
            ]
        )
    rows.append([InlineKeyboardButton(text="« Admin paneli", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yuborish", callback_data="comp:broadcast:send")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="comp:broadcast:cancel")],
        ]
    )


def status_filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Barcha", callback_data="list:all:0"),
                InlineKeyboardButton(text="Tasdiqlangan", callback_data="list:approved:0"),
            ],
            [
                InlineKeyboardButton(text="Kutilayotgan", callback_data="list:pending:0"),
                InlineKeyboardButton(text="Rad etilgan", callback_data="list:rejected:0"),
            ],
        ]
    )
