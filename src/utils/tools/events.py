import asyncio
import sqlite3
from typing import List, Dict, Any, Optional
from src.utils.memory.memory import memory_manager

async def add_event(guild_id: int | str, title: str, details: str, 
                    date_time: str, created_by: str) -> int:
    def _insert():
        with memory_manager._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO events (guild_id, title, details, date_time, created_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(guild_id), title, details, date_time, created_by)
            )
            return cur.lastrowid
    return await asyncio.to_thread(_insert)

async def get_events(guild_id: int | str) -> List[Dict[str, Any]]:
    def _fetch():
        with memory_manager._get_conn() as conn:
            rows = conn.execute(
                """SELECT id, title, details, date_time, created_by, created_at 
                   FROM events 
                   WHERE guild_id = ? 
                   ORDER BY id ASC""",
                (str(guild_id),)
            ).fetchall()
            return [dict(r) for r in rows]
    return await asyncio.to_thread(_fetch)

async def remove_event(guild_id: int | str, event_id: int) -> bool:
    def _delete():
        with memory_manager._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM events WHERE guild_id = ? AND id = ?",
                (str(guild_id), event_id)
            )
            return cur.rowcount > 0
    return await asyncio.to_thread(_delete)
