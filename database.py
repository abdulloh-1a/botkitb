"""Ma'lumotlar bazasi: mahalliy SQLite yoki doimiy PostgreSQL.

`DATABASE_URL` berilganda baza PostgreSQL'ga yoziladi (Render bepul rejimi uchun
tavsiya etiladi — fayl tizimi vaqtinchalik bo'lgani uchun SQLite yo'qoladi).
Birinchi ishga tushirishda jadvallar avtomatik yaratiladi.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import STATUS_APPROVED, STATUS_PENDING, STATUS_REJECTED, SUPER_ADMIN_ID
from dbengine import (
    IS_POSTGRES,
    Error,
    IntegrityError,
    Row,
    connect,
    location,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path) -> None:
        if IS_POSTGRES:
            # URL ni Path ga aylantirmang: Path("postgresql://...") `//` ni yo'q qiladi
            # va asyncpg "invalid DSN" xatosini beradi.
            self.path: str | Path = str(path)
        else:
            self.path = Path(path)
            self.path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with connect(self.path) as db:
            if not IS_POSTGRES:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA foreign_keys=ON")
                # Eski sxemada user_id UNIQUE edi (bitta profil = bitta ariza).
                # Yangi talab: bitta profildan 5 tagacha ariza. Jadvalni qayta quramiz.
                cursor = await db.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='applications'"
                )
                table_sql = (await cursor.fetchone() or [None])[0]
                if table_sql and "UNIQUE" in table_sql.upper():
                    logger.info("Eski applications jadvali yangilanadi (UNIQUE user_id olib tashlanadi)")
                    await db.executescript(
                        """
                        CREATE TABLE applications_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            username TEXT,
                            first_name TEXT NOT NULL,
                            last_name TEXT NOT NULL,
                            age INTEGER NOT NULL,
                            grade INTEGER NOT NULL,
                            gender TEXT NOT NULL,
                            phone TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'pending',
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            reviewed_at TEXT,
                            reviewed_by INTEGER,
                            rejection_reason TEXT
                        );
                        INSERT INTO applications_new SELECT * FROM applications;
                        DROP TABLE applications;
                        ALTER TABLE applications_new RENAME TO applications;
                        """
                    )

            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    grade INTEGER NOT NULL,
                    gender TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by INTEGER,
                    rejection_reason TEXT
                );

                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    can_broadcast INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    added_by INTEGER NOT NULL,
                    added_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
                CREATE INDEX IF NOT EXISTS idx_applications_grade ON applications(grade);
                CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id);
                CREATE INDEX IF NOT EXISTS idx_actions_admin ON admin_actions(admin_id);
                """
            )
            await db.commit()
        logger.info("Ma'lumotlar bazasi tayyor: %s", location(self.path))

    # --- Arizalar ----------------------------------------------------------
    async def add_application(self, data: dict[str, Any]) -> int | None:
        now = _now()
        async with connect(self.path) as db:
            db.row_factory = Row
            try:
                cursor = await db.execute(
                    """INSERT INTO applications
                       (user_id, username, first_name, last_name, age, grade, gender,
                        phone, status, created_at, updated_at)
                       VALUES (:user_id, :username, :first_name, :last_name, :age,
                               :grade, :gender, :phone, :status, :created_at, :updated_at)""",
                    {
                        **data,
                        "status": STATUS_PENDING,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                await db.commit()
                return int(cursor.lastrowid)
            except IntegrityError:
                logger.warning("Takroriy ariza: user_id=%s", data.get("user_id"))
                return None

    async def update_application(self, app_id: int, data: dict[str, Any]) -> bool:
        """Rad etilgan arizani qayta topshirishda ma'lumotlarni yangilash."""
        fields = ["username", "first_name", "last_name", "age", "grade", "gender", "phone"]
        values = {key: data[key] for key in fields if key in data}
        values["updated_at"] = _now()
        set_clause = ", ".join(f"{key}=:{key}" for key in values)
        async with connect(self.path) as db:
            cursor = await db.execute(
                f"""UPDATE applications SET {set_clause}, status=:status,
                    reviewed_at=NULL, reviewed_by=NULL, rejection_reason=NULL
                    WHERE id=:app_id AND status=:old_status""",
                {
                    **values,
                    "app_id": app_id,
                    "status": STATUS_PENDING,
                    "old_status": STATUS_REJECTED,
                },
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_phone(self, app_id: int, phone: str) -> bool:
        async with connect(self.path) as db:
            cursor = await db.execute(
                "UPDATE applications SET phone=?, updated_at=? WHERE id=?",
                (phone, _now(), app_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_applications_by_user(self, user_id: int) -> list[dict[str, Any]]:
        return await self._fetch_all(
            "SELECT * FROM applications WHERE user_id=? ORDER BY id DESC", (user_id,)
        )

    async def count_user_applications(self, user_id: int) -> int:
        return await self._fetch_scalar(
            "SELECT COUNT(*) FROM applications WHERE user_id=?", (user_id,)
        )

    async def get_application_by_id(self, app_id: int) -> dict[str, Any] | None:
        return await self._fetch_one("SELECT * FROM applications WHERE id=?", (app_id,))

    async def get_applications(
        self, status: str | None = None, limit: int | None = None, offset: int = 0
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM applications"
        params: list[Any] = []
        if status:
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY id DESC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        return await self._fetch_all(query, tuple(params))

    async def search_applications(self, query: str) -> list[dict[str, Any]]:
        # Telefon raqami bo'yicha qidirishda formatsiz va formatlangan ko'rinishni ham tekshiramiz.
        from utils.validators import normalize_phone

        variants = [clean_like(query)]
        formatted, _ = normalize_phone(query)
        if formatted and clean_like(formatted) not in variants:
            variants.append(clean_like(formatted))

        condition = (
            "(first_name LIKE ? ESCAPE '\\' OR last_name LIKE ? ESCAPE '\\' "
            "OR phone LIKE ? ESCAPE '\\' OR username LIKE ? ESCAPE '\\' "
            "OR CAST(grade AS TEXT) LIKE ? ESCAPE '\\' "
            "OR CAST(id AS TEXT) LIKE ? ESCAPE '\\')"
        )
        params: list[Any] = []
        for variant in variants:
            like = f"%{variant}%"
            params.extend([like] * 6)
        sql = (
            "SELECT * FROM applications WHERE "
            + " OR ".join([condition] * len(variants))
            + " ORDER BY id DESC LIMIT 50"
        )
        return await self._fetch_all(sql, tuple(params))

    async def update_status(
        self,
        app_id: int,
        status: str,
        reviewer_id: int,
        reason: str | None = None,
    ) -> bool:
        """Faqat kutilayotgan ariza holati o'zgaradi (ikki marta tasdiqlash oldini oladi)."""
        async with connect(self.path) as db:
            cursor = await db.execute(
                """UPDATE applications
                   SET status=?, reviewed_at=?, reviewed_by=?, rejection_reason=?, updated_at=?
                   WHERE id=? AND status=?""",
                (status, _now(), reviewer_id, reason, _now(), app_id, STATUS_PENDING),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def count_applications(self, status: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM applications"
        params: tuple[Any, ...] = ()
        if status:
            sql += " WHERE status=?"
            params = (status,)
        return await self._fetch_scalar(sql, params)

    async def get_recipients(self, status: str = STATUS_APPROVED) -> list[int]:
        rows = await self._fetch_all(
            "SELECT DISTINCT user_id FROM applications WHERE status=? ORDER BY user_id", (status,)
        )
        return [int(row["user_id"]) for row in rows]

    async def get_stats(self) -> dict[str, Any]:
        rows = await self._fetch_all(
            """SELECT
                   COUNT(*) AS total,
                   SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved,
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected,
                   SUM(CASE WHEN gender='male' THEN 1 ELSE 0 END) AS male,
                   SUM(CASE WHEN gender='female' THEN 1 ELSE 0 END) AS female
               FROM applications"""
        )
        row = rows[0] if rows else {}
        grade_rows = await self._fetch_all(
            "SELECT grade, COUNT(*) AS count FROM applications GROUP BY grade ORDER BY grade"
        )
        return {
            "total": int(row.get("total") or 0),
            "approved": int(row.get("approved") or 0),
            "pending": int(row.get("pending") or 0),
            "rejected": int(row.get("rejected") or 0),
            "male": int(row.get("male") or 0),
            "female": int(row.get("female") or 0),
            "grades": {int(r["grade"]): int(r["count"]) for r in grade_rows},
        }

    # --- Adminlar ----------------------------------------------------------
    async def add_admin(self, user_id: int, username: str | None, added_by: int) -> bool:
        async with connect(self.path) as db:
            try:
                await db.execute(
                    """INSERT INTO admins (user_id, username, added_by, added_at, is_active)
                       VALUES (?, ?, ?, ?, 1)
                       ON CONFLICT(user_id) DO UPDATE SET
                           is_active=1, username=excluded.username, added_by=excluded.added_by,
                           added_at=excluded.added_at""",
                    (user_id, username, added_by, _now()),
                )
                await db.commit()
                return True
            except Error as exc:
                logger.error("Admin qo'shish xatoligi: %s", exc)
                return False

    async def remove_admin(self, user_id: int) -> bool:
        async with connect(self.path) as db:
            cursor = await db.execute(
                "UPDATE admins SET is_active=0 WHERE user_id=? AND is_active=1", (user_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def is_admin(self, user_id: int) -> bool:
        if user_id == SUPER_ADMIN_ID:
            return True
        row = await self._fetch_one(
            "SELECT 1 FROM admins WHERE user_id=? AND is_active=1", (user_id,)
        )
        return row is not None

    async def get_admin(self, user_id: int) -> dict[str, Any] | None:
        return await self._fetch_one("SELECT * FROM admins WHERE user_id=?", (user_id,))

    async def list_admins(self, only_active: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM admins"
        if only_active:
            sql += " WHERE is_active=1"
        sql += " ORDER BY added_at DESC"
        return await self._fetch_all(sql)

    async def set_broadcast_permission(self, user_id: int, enabled: bool) -> bool:
        async with connect(self.path) as db:
            cursor = await db.execute(
                "UPDATE admins SET can_broadcast=? WHERE user_id=? AND is_active=1",
                (int(enabled), user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def can_broadcast(self, user_id: int) -> bool:
        if user_id == SUPER_ADMIN_ID:
            return True
        row = await self._fetch_one(
            "SELECT can_broadcast FROM admins WHERE user_id=? AND is_active=1", (user_id,)
        )
        return bool(row and row["can_broadcast"])

    async def count_admins(self, only_active: bool = True) -> int:
        sql = "SELECT COUNT(*) FROM admins"
        if only_active:
            sql += " WHERE is_active=1"
        return await self._fetch_scalar(sql)

    # --- Admin harakatlari logi -------------------------------------------
    async def log_action(self, admin_id: int, action: str, details: str = "") -> None:
        async with connect(self.path) as db:
            await db.execute(
                "INSERT INTO admin_actions (admin_id, action, details, created_at) VALUES (?, ?, ?, ?)",
                (admin_id, action, details, _now()),
            )
            await db.commit()

    async def get_actions(self, limit: int = 30) -> list[dict[str, Any]]:
        return await self._fetch_all(
            "SELECT * FROM admin_actions ORDER BY id DESC LIMIT ?", (limit,)
        )

    # --- Sozlamalar (musobaqa sanasi/vaqti/joyi) --------------------------
    async def set_setting(self, key: str, value: str) -> None:
        async with connect(self.path) as db:
            await db.execute(
                """INSERT INTO settings (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (key, value),
            )
            await db.commit()

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self._fetch_one("SELECT value FROM settings WHERE key=?", (key,))
        return str(row["value"]) if row else default

    async def get_all_settings(self) -> dict[str, str]:
        rows = await self._fetch_all("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in rows}

    # --- Umumiy yordamchilar ----------------------------------------------
    async def _fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        async with connect(self.path) as db:
            db.row_factory = Row
            cursor = await db.execute(sql, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        async with connect(self.path) as db:
            db.row_factory = Row
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def _fetch_scalar(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        async with connect(self.path) as db:
            cursor = await db.execute(sql, params)
            row = await cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0


def clean_like(value: str) -> str:
    """LIKE uchun maxsus belgilardan qochish."""
    return value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
