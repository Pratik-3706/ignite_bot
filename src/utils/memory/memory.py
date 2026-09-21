import sqlite3
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any
from src.config import MEMORY_DIR

DB_PATH = MEMORY_DIR / "memory.db"

class MemoryManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL,
                    guild_id TEXT,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_channel_messages 
                ON messages(channel_id, id DESC);

                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, fact_key)
                );

                CREATE TABLE IF NOT EXISTS club_memory (
                    guild_id TEXT NOT NULL,
                    mem_key TEXT NOT NULL,
                    mem_value TEXT NOT NULL,
                    updated_by TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, mem_key)
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    details TEXT,
                    date_time TEXT,
                    created_by TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

    async def add_message(self, channel_id: int | str, guild_id: Optional[int | str], 
                          user_id: int | str, user_name: str, role: str, content: str):
        def _insert():
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO messages (channel_id, guild_id, user_id, user_name, role, content)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (str(channel_id), str(guild_id) if guild_id else None, str(user_id), user_name, role, content)
                )
        await asyncio.to_thread(_insert)

    async def get_channel_history(self, channel_id: int | str, limit: int = 15) -> List[Dict[str, str]]:
        def _fetch():
            with self._get_conn() as conn:
                rows = conn.execute(
                    """SELECT user_id, user_name, role, content 
                       FROM messages 
                       WHERE channel_id = ? 
                       ORDER BY id DESC LIMIT ?""",
                    (str(channel_id), limit)
                ).fetchall()
                return list(reversed(rows))

        rows = await asyncio.to_thread(_fetch)
        messages: List[Dict[str, str]] = []
        for r in rows:
            if r["role"] == "assistant":
                messages.append({"role": "assistant", "content": r["content"]})
            else:
                formatted_user_msg = f"[User ID: {r['user_id']} | Name: {r['user_name']}]: {r['content']}"
                messages.append({"role": "user", "content": formatted_user_msg})
        return messages

    async def set_user_fact(self, user_id: int | str, fact_key: str, fact_value: str):
        def _upsert():
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO user_profiles (user_id, fact_key, fact_value, updated_at)
                       VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(user_id, fact_key) DO UPDATE SET 
                       fact_value=excluded.fact_value, updated_at=CURRENT_TIMESTAMP""",
                    (str(user_id), fact_key, fact_value)
                )
        await asyncio.to_thread(_upsert)

    async def get_user_facts(self, user_id: int | str) -> Dict[str, str]:
        def _get():
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT fact_key, fact_value FROM user_profiles WHERE user_id = ?",
                    (str(user_id),)
                ).fetchall()
                return {r["fact_key"]: r["fact_value"] for r in rows}
        return await asyncio.to_thread(_get)

    async def set_club_memory(self, guild_id: int | str, mem_key: str, mem_value: str, updated_by: str):
        def _upsert():
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO club_memory (guild_id, mem_key, mem_value, updated_by, updated_at)
                       VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(guild_id, mem_key) DO UPDATE SET 
                       mem_value=excluded.mem_value, updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP""",
                    (str(guild_id), mem_key, mem_value, updated_by)
                )
        await asyncio.to_thread(_upsert)

    async def get_club_memories(self, guild_id: int | str) -> Dict[str, str]:
        def _get():
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT mem_key, mem_value FROM club_memory WHERE guild_id = ?",
                    (str(guild_id),)
                ).fetchall()
                return {r["mem_key"]: r["mem_value"] for r in rows}
        return await asyncio.to_thread(_get)

    async def clear_channel_history(self, channel_id: int | str):
        def _clear():
            with self._get_conn() as conn:
                conn.execute("DELETE FROM messages WHERE channel_id = ?", (str(channel_id),))
        await asyncio.to_thread(_clear)

    async def get_stats(self) -> Dict[str, Any]:
        def _stats():
            with self._get_conn() as conn:
                msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
                user_count = conn.execute("SELECT COUNT(DISTINCT user_id) FROM messages").fetchone()[0]
                event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                club_mem_count = conn.execute("SELECT COUNT(*) FROM club_memory").fetchone()[0]
                size_kb = (self.db_path.stat().st_size // 1024) if self.db_path.exists() else 0
                return {
                    "total_messages": msg_count,
                    "unique_users": user_count,
                    "events": event_count,
                    "club_memories": club_mem_count,
                    "db_size_kb": size_kb
                }
        return await asyncio.to_thread(_stats)

memory_manager = MemoryManager()
