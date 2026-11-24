"""Doimiy FSM storage: ariza jarayoni bot qayta ishga tushganda ham saqlanadi."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from dbengine import IS_POSTGRES, connect

logger = logging.getLogger(__name__)


class PersistentStorage(BaseStorage):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not IS_POSTGRES:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with connect(self.path) as db:
            if not IS_POSTGRES:
                await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                """CREATE TABLE IF NOT EXISTS fsm_states (
                       bot_id INTEGER NOT NULL,
                       chat_id INTEGER NOT NULL,
                       user_id INTEGER NOT NULL,
                       state TEXT,
                       data TEXT NOT NULL DEFAULT '{}',
                       PRIMARY KEY (bot_id, chat_id, user_id)
                   )"""
            )
            await db.commit()

    @staticmethod
    def _key(key: StorageKey) -> tuple[int, int, int]:
        return (key.bot_id, key.chat_id, key.user_id)

    async def set_state(self, key: StorageKey, state: str | State | None = None) -> None:
        value = state.state if isinstance(state, State) else state
        bot_id, chat_id, user_id = self._key(key)
        async with connect(self.path) as db:
            await db.execute(
                """INSERT INTO fsm_states (bot_id, chat_id, user_id, state)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(bot_id, chat_id, user_id) DO UPDATE SET state=excluded.state""",
                (bot_id, chat_id, user_id, value),
            )
            await db.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        async with connect(self.path) as db:
            cursor = await db.execute(
                "SELECT state FROM fsm_states WHERE bot_id=? AND chat_id=? AND user_id=?",
                self._key(key),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        bot_id, chat_id, user_id = self._key(key)
        async with connect(self.path) as db:
            await db.execute(
                """INSERT INTO fsm_states (bot_id, chat_id, user_id, data)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(bot_id, chat_id, user_id) DO UPDATE SET data=excluded.data""",
                (bot_id, chat_id, user_id, json.dumps(dict(data), ensure_ascii=False)),
            )
            await db.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with connect(self.path) as db:
            cursor = await db.execute(
                "SELECT data FROM fsm_states WHERE bot_id=? AND chat_id=? AND user_id=?",
                self._key(key),
            )
            row = await cursor.fetchone()
            if not row:
                return {}
            try:
                return json.loads(row[0])
            except (TypeError, ValueError):
                logger.warning("Buzilgan FSM ma'lumoti: key=%s", self._key(key))
                return {}

    async def close(self) -> None:
        """Aiogram close chaqirganda hech qanday ochiq ulanish yo'q."""
        return None
