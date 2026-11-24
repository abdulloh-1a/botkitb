"""Ariza topshirish FSM tugmalari."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import GRADES, STATUS_LABELS

EDIT_FIELDS = [
    ("Ism", "first_name"),
    ("Familiya", "last_name"),
    ("Yosh", "age"),
    ("Sinf", "grade"),
    ("Jins", "gender"),
    ("Telefon", "phone"),
]


def grades_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for grade in GRADES:
        row.append(
            InlineKeyboardButton(text=f"{grade}-sinf", callback_data=f"grade:{grade}")
        )
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(navigation_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def navigation_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="nav:back"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="nav:cancel"),
    ]


def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👦 O'g'il bola", callback_data="gender:male"),
                InlineKeyboardButton(text="👧 Qiz bola", callback_data="gender:female"),
            ],
            navigation_row(),
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Arizani yuborish", callback_data="app:submit")],
            [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="app:edit")],
            navigation_row(),
        ]
    )


def suggested_phone_keyboard() -> InlineKeyboardMarkup:
    """Avtomatik taklif qilingan raqamni bir bosishda ishlatish tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Shu raqamni ishlatish", callback_data="phone:use")],
            [InlineKeyboardButton(text="🎲 Yangi raqam taklif qilish", callback_data="phone:generate")],
            [InlineKeyboardButton(text="✏️ Boshqa raqam yuborish", callback_data="phone:other")],
        ]
    )


def my_applications_keyboard(apps: list[dict]) -> InlineKeyboardMarkup:
    """Bitta profilning barcha arizalari (maksimal 5 ta)."""
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"#{app['id']:04d} {app['first_name']} {app['last_name']} — "
                    f"{STATUS_LABELS.get(app['status'], app['status'])}"
                ),
                callback_data=f"myapp:{app['id']}",
            )
        ]
        for app in apps
    ]
    if len(apps) < 5:
        rows.append(
            [InlineKeyboardButton(text="📝 Yangi ariza qo'shish", callback_data="myapp:new")]
        )
    rows.append([InlineKeyboardButton(text="« Asosiy menyu", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def application_user_keyboard(app: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if app["status"] == "rejected":
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔄 Qayta ariza topshirish",
                    callback_data=f"app:restart:{app['id']}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="📱 Telefon raqamini o'zgartirish",
                callback_data=f"phone:change:{app['id']}",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="« Arizalarim", callback_data="myapp:list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=label, callback_data=f"app:edit:{field}")
            for label, field in EDIT_FIELDS[i : i + 2]
        ]
        for i in range(0, len(EDIT_FIELDS), 2)
    ]
    rows.append([InlineKeyboardButton(text="« Tasdiqlashga qaytish", callback_data="app:edit:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
