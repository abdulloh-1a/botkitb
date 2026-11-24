"""Foydalanuvchi kiritgan ma'lumotlarni tekshirish va tozalash."""

from __future__ import annotations

import re
import unicodedata

from config import GRADES

_NAME_RE = re.compile(r"^[A-Za-zÀ-ÿOʻoʻGʻgʻ'\- ]+$")
_PHONE_DIGITS_RE = re.compile(r"\D+")


def clean_text(value: str) -> str:
    """Matnni normalize qilish: HTML emas, faqat bo'sh joylarni tartibga solish."""
    value = unicodedata.normalize("NFKC", value).strip()
    return re.sub(r"\s+", " ", value)


def validate_name(value: str, field: str = "Ism") -> tuple[str | None, str]:
    """Ism/familiyani tekshiradi. (qiymat, xato xabari) qaytaradi."""
    name = clean_text(value)
    if not 2 <= len(name) <= 50:
        return None, f"❌ {field} 2 dan 50 gacha belgidan iborat bo'lishi kerak."
    if not _NAME_RE.match(name):
        return None, f"❌ {field} faqat harflar, bo'sh joy, '-' va apostrofdan iborat bo'lishi kerak."
    return name, ""


def validate_age(value: str) -> tuple[int | None, str]:
    age_text = clean_text(value)
    if not age_text.isdigit():
        return None, "❌ Yosh faqat son bo'lishi kerak. Masalan: 14"
    age = int(age_text)
    if not 10 <= age <= 20:
        return None, "❌ Yosh 10 dan 20 gacha bo'lishi kerak."
    return age, ""


def validate_grade(value: str) -> tuple[int | None, str]:
    grade_text = clean_text(value).lower()
    grade_text = (
        grade_text.replace("-sinf", "")
        .replace(" sinf", "")
        .replace("sinf", "")
        .strip()
    )
    if not grade_text.isdigit() or int(grade_text) not in GRADES:
        allowed = ", ".join(str(g) for g in GRADES)
        return None, f"❌ Faqat {allowed}-sinflar tanlanadi. Masalan: 9 yoki 9-sinf."
    return int(grade_text), ""


def validate_gender(value: str) -> tuple[str | None, str]:
    raw = clean_text(value).lower()
    mapping = {
        "1": "male",
        "2": "female",
        "male": "male",
        "female": "female",
        "o'g'il": "male",
        "o'g'il bola": "male",
        "og'il": "male",
        "qiz": "female",
        "qiz bola": "female",
    }
    gender = mapping.get(raw)
    if gender is None:
        return None, "❌ 1 (o'g'il bola) yoki 2 (qiz bola) yuboring."
    return gender, ""


def normalize_phone(value: str) -> tuple[str | None, str]:
    """+998 90 123-45-67 ko'rinishidagi raqamni +998901234567 ga keltiradi."""
    digits = _PHONE_DIGITS_RE.sub("", value)
    if digits.startswith("998"):
        digits = digits[3:]
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        return None, (
            "❌ Telefon raqami noto'g'ri. Namuna: +998 90 123 45 67 "
            "yoki Contact tugmasi orqali yuboring."
        )
    operator = digits[3:5]
    if operator not in {"20", "30", "33", "50", "55", "62", "77", "88", "90", "91", "93", "94", "95", "97", "99"}:
        return None, "❌ Noto'g'ri operator kodi. Masalan: 90, 91, 93, 94, 95, 99."
    formatted = f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:]}"
    return formatted, ""


def validate_telegram_id(value: str) -> tuple[int | None, str]:
    raw = clean_text(value)
    if not raw.lstrip("-").isdigit():
        return None, "❌ Telegram ID faqat raqamlardan iborat bo'lishi kerak."
    user_id = int(raw)
    if user_id <= 0:
        return None, "❌ Telegram ID musbat son bo'lishi kerak."
    return user_id, ""


def validate_text_length(value: str, minimum: int = 2, maximum: int = 1000) -> tuple[str | None, str]:
    text = clean_text(value)
    if not minimum <= len(text) <= maximum:
        return None, f"❌ Matn {minimum} dan {maximum} gacha belgidan iborat bo'lishi kerak."
    return text, ""
