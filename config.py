"""Loyiha konfiguratsiyasi.

Barcha maxfiy ma'lumotlar .env faylidan o'qiladi. .env fayli repositoriesga
qo'shilmasligi kerak (faqat .env.example namuna sifatida saqlanadi).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} butun son bo'lishi kerak, olingan: {raw!r}") from exc


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


# --- Bot sozlamalari -------------------------------------------------------
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
SUPER_ADMIN_ID: int = _get_int("SUPER_ADMIN_ID", 123456789)
DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "bot.db")))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
LOG_FILE: Path = Path(os.getenv("LOG_FILE", str(BASE_DIR / "bot.log")))
# Render kabi platformalarda fayl tizimi vaqtinchalik — faqat stdout ga yozamiz.
ENABLE_FILE_LOG: bool = _get_bool("ENABLE_FILE_LOG", True)
BROADCAST_DELAY: float = float(os.getenv("BROADCAST_DELAY", "0.05"))

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. .env faylida BOT_TOKEN=... qatorini to'ldiring."
    )
if ":" not in BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN noto'g'ri formatda. Masalan: 123456789:AAaa...")

if SUPER_ADMIN_ID <= 0:
    raise RuntimeError("SUPER_ADMIN_ID musbat Telegram ID bo'lishi kerak.")

PLACEHOLDER_MODE = "PLACEHOLDER" in BOT_TOKEN.upper() or SUPER_ADMIN_ID == 123456789

# --- Musobaqa ma'lumotlari -------------------------------------------------
SCHOOL_NAME = "10-umumiy o'rta ta'lim maktabi"
REGION = "Farg'ona viloyati"
DISTRICT = "Toshloq tumani"
ORGANIZER = f"{REGION}, {DISTRICT}, {SCHOOL_NAME} Kengashi"
CREATOR = "Xudoberdiyev Abdulloh"
DEFAULT_VENUE = f"{SCHOOL_NAME}"

GRADES: tuple[int, ...] = (6, 7, 8, 9, 10, 11)

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

STATUS_LABELS = {
    STATUS_PENDING: "⏳ Kutilmoqda",
    STATUS_APPROVED: "✅ Tasdiqlangan",
    STATUS_REJECTED: "❌ Rad etilgan",
}

GENDER_LABELS = {"male": "👦 O'g'il bola", "female": "👧 Qiz bola"}

IS_DEBUG = _get_bool("DEBUG", False)
