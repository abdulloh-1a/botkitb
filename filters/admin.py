"""Admin huquqlarini Telegram ID orqali tekshiruvchi filtrlar.

`db` va `SUPER_ADMIN_ID` aiogram dependency injection orqali beriladi
(dp["db"] = Database(...)).
"""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from config import SUPER_ADMIN_ID
from database import Database


class IsAdminFilter(BaseFilter):
    """Super admin yoki faol adminlargagina ruxsat beradi."""

    async def __call__(self, obj: TelegramObject, db: Database) -> bool:
        user = getattr(obj, "from_user", None)
        if user is None:
            return False
        return await db.is_admin(user.id)


class IsSuperAdminFilter(BaseFilter):
    """Faqat bitta super adminga ruxsat beradi."""

    async def __call__(self, obj: TelegramObject) -> bool:
        user = getattr(obj, "from_user", None)
        return bool(user and user.id == SUPER_ADMIN_ID)


class CanBroadcastFilter(BaseFilter):
    """Xabar yuborish huquqi bor adminlarga ruxsat beradi."""

    async def __call__(self, obj: TelegramObject, db: Database) -> bool:
        user = getattr(obj, "from_user", None)
        if user is None:
            return False
        return await db.can_broadcast(user.id)
