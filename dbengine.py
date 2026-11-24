"""Ma'lumotlar bazasi dvigateli: SQLite (mahalliy) yoki PostgreSQL (Render free).

Render'ning bepul Web Service'ida fayl tizimi vaqtinchalik, shuning uchun
`DATABASE_URL` berilganda barcha so'rovlar PostgreSQL ga yuboriladi. Kodning
qolgan qismi aiosqlite uslubida (`?` / `:nom` parametrlari, `fetchone()`,
`rowcount`, `lastrowid`) yozilganligi uchun moslashtiruvchi qatlam ishlatiladi.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import aiosqlite

from config import DATABASE_URL

logger = logging.getLogger(__name__)

IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if IS_POSTGRES:  # pragma: no cover - Render'da ishlatiladi
    import asyncpg

    IntegrityError = asyncpg.UniqueViolationError
    Error = asyncpg.PostgresError

    class Row:  # aiosqlite.Row o'rniga bosqichma-bosqich belgi
        pass

else:
    IntegrityError = aiosqlite.IntegrityError
    Error = aiosqlite.Error
    Row = aiosqlite.Row


def _pg_dsn(url: str) -> tuple[str, Any]:
    """`sslmode` ni asyncpg tushunadigan `ssl` parameteriga aylantiradi."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    sslmode = query.pop("sslmode", [""])[0].lower()
    dsn = urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    ssl: Any = True if sslmode in {"require", "verify-ca", "verify-full"} else None
    return dsn, ssl


def _convert(sql: str, params: Any) -> tuple[str, list[Any]]:
    """`?` va `:nom` parametrlarini PostgreSQL `$1, $2, ...` ga o'zgartiradi."""
    if isinstance(params, dict):
        names: list[str] = []

        def replace_named(match: re.Match[str]) -> str:
            names.append(match.group(1))
            return f"${len(names)}"

        sql = re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", replace_named, sql)
        return sql, [params[name] for name in names]

    counter = [0]

    def replace_q(_: re.Match[str]) -> str:
        counter[0] += 1
        return f"${counter[0]}"

    return re.sub(r"\?", replace_q, sql), list(params)


class _Cursor:
    def __init__(
        self, rows: list[Any], lastrowid: int | None = None, rowcount: int = 0
    ) -> None:
        self._rows = rows
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self.row_factory: Any = None

    async def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


class _Connection:
    def __init__(self, conn: "asyncpg.Connection") -> None:
        self._conn = conn
        self.row_factory: Any = None

    async def execute(self, sql: str, params: Any = ()) -> _Cursor:
        sql, values = _convert(sql, params)
        upper = sql.lstrip().upper()
        if upper.startswith(("SELECT", "WITH")):
            rows = await self._conn.fetch(sql, *values)
            return _Cursor(rows, rowcount=len(rows))

        if upper.startswith("INSERT") and "RETURNING" not in upper:
            table_match = re.search(r"INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", upper)
            table = table_match.group(1).lower() if table_match else ""
            if table in {"applications", "admin_actions"}:
                rows = await self._conn.fetch(sql + " RETURNING id", *values)
                return _Cursor(rows, lastrowid=rows[0][0] if rows else None, rowcount=len(rows))

        status = await self._conn.execute(sql, *values)
        match = re.search(r"(\d+)\s*$", status)
        return _Cursor([], rowcount=int(match.group(1)) if match else 0)

    async def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            statement = statement.strip()
            if not statement or all(line.strip().startswith("--") for line in statement.splitlines()):
                continue
            statement = statement.replace(
                "INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY"
            )
            # Telegram user/chat ID'lari int32 ga sig'maydi (masalan 9046078440).
            for column in (
                "user_id",
                "chat_id",
                "bot_id",
                "admin_id",
                "reviewed_by",
                "added_by",
            ):
                statement = statement.replace(
                    f"{column} INTEGER", f"{column} BIGINT"
                )
            await self._conn.execute(statement)

    async def commit(self) -> None:
        return None  # asyncpg har so'rovni o'zaro mustaqil tranzaktsiyada bajaradi

    async def close(self) -> None:
        await self._conn.close()


class _Connector:
    """`async with connect(...) as db` uchun moslashtiruvchi."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._conn: _Connection | None = None

    async def __aenter__(self) -> _Connection:
        dsn, ssl = _pg_dsn(self.url)
        conn = await asyncpg.connect(dsn, ssl=ssl)
        self._conn = _Connection(conn)
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._conn:
            await self._conn.close()


def connect(path: str | Path) -> Any:
    if IS_POSTGRES:
        return _Connector(str(path))
    return aiosqlite.connect(path)


def location(path: str | Path) -> str:
    """Log uchun qisqa va xavfsiz baza manzili."""
    return "PostgreSQL (DATABASE_URL)" if IS_POSTGRES else str(path)
