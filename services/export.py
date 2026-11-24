"""Ariza ma'lumotlarini Excel (xlsx) formatida eksport qilish."""

from __future__ import annotations

from io import BytesIO

from aiogram.types import BufferedInputFile
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from config import GENDER_LABELS, STATUS_LABELS
from database import Database

HEADERS = [
    "ID",
    "Telegram ID",
    "Username",
    "Ism",
    "Familiya",
    "Yosh",
    "Sinf",
    "Jins",
    "Telefon",
    "Holat",
    "Yuborilgan vaqt",
    "Ko'rib chiqqan",
    "Izoh",
]


def _style_header(ws) -> None:
    fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"


async def export_applications(db: Database) -> BufferedInputFile:
    applications = await db.get_applications()
    stats = await db.get_stats()

    wb = Workbook()
    ws = wb.active
    ws.title = "Arizalar"
    ws.append(HEADERS)
    for app in applications:
        ws.append(
            [
                app["id"],
                app["user_id"],
                app.get("username") or "",
                app["first_name"],
                app["last_name"],
                app["age"],
                f"{app['grade']}-sinf",
                GENDER_LABELS.get(app["gender"], app["gender"]),
                app["phone"],
                STATUS_LABELS.get(app["status"], app["status"]),
                app["created_at"],
                app.get("reviewed_by") or "",
                app.get("rejection_reason") or "",
            ]
        )
    _style_header(ws)
    for index, header in enumerate(HEADERS, start=1):
        width = max(len(header) + 2, 14)
        ws.column_dimensions[get_column_letter(index)].width = width

    ws2 = wb.create_sheet("Statistika")
    ws2.append(["Ko'rsatkich", "Soni"])
    rows = [
        ("Jami arizalar", stats["total"]),
        ("Tasdiqlangan", stats["approved"]),
        ("Kutilayotgan", stats["pending"]),
        ("Rad etilgan", stats["rejected"]),
        ("O'g'il bolalar", stats["male"]),
        ("Qiz bolalar", stats["female"]),
    ]
    rows.extend((f"{grade}-sinf", count) for grade, count in sorted(stats["grades"].items()))
    for row in rows:
        ws2.append(row)
    _style_header(ws2)
    ws2.column_dimensions["A"].width = 24
    ws2.column_dimensions["B"].width = 12

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return BufferedInputFile(
        buffer.getvalue(), filename="kitobxonlik_arizalari.xlsx"
    )
