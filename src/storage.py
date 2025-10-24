from __future__ import annotations
import json
from typing import List, Dict, Any, Optional, Tuple
import aiosqlite
import asyncio
from datetime import datetime

PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
]

INIT_SQL = """
CREATE TABLE IF NOT EXISTS dedup (
    topic TEXT NOT NULL,
    event_id TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (topic, event_id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    event_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    processed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_topic ON events(topic);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""

class DedupStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = asyncio.Lock()  # serialize init

    async def init(self) -> None:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                for p in PRAGMAS:
                    await db.execute(p)
                await db.executescript(INIT_SQL)
                await db.commit()

    async def mark_processed_if_new(self, event: Dict[str, Any]) -> bool:
        """
        Try insert into dedup; if inserted, also insert full event into events table.
        Returns True if this is the first time we see the (topic,event_id), else False.
        """
        async with aiosqlite.connect(self.db_path) as db:
            for p in PRAGMAS:
                await db.execute(p)
            await db.execute("BEGIN;")
            try:
                now_iso = datetime.utcnow().isoformat() + "Z"
                # Attempt insert into dedup
                cursor = await db.execute(
                    "INSERT OR IGNORE INTO dedup(topic, event_id, processed_at) VALUES (?, ?, ?)",
                    (event["topic"], event["event_id"], now_iso),
                )
                await cursor.close()
                inserted = db.total_changes > 0
                if inserted:
                    payload_json = json.dumps(event.get("payload", {}), separators=(",", ":"), ensure_ascii=False)
                    await db.execute(
                        "INSERT INTO events(topic, event_id, ts, source, payload_json, processed_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            event["topic"],
                            event["event_id"],
                            event["timestamp"],
                            event["source"],
                            payload_json,
                            now_iso,
                        ),
                    )
                await db.commit()
                return inserted
            except Exception:
                await db.execute("ROLLBACK;")
                raise

    async def get_events(self, topic: Optional[str] = None, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        q = "SELECT topic, event_id, ts, source, payload_json, processed_at FROM events"
        params: Tuple[Any, ...] = ()
        if topic:
            q += " WHERE topic = ?"
            params = (topic,)
        q += " ORDER BY processed_at ASC LIMIT ? OFFSET ?"
        params = params + (limit, offset)
        async with aiosqlite.connect(self.db_path) as db:
            for p in PRAGMAS:
                await db.execute(p)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(q, params)
            rows = await cur.fetchall()
        events: List[Dict[str, Any]] = []
        for r in rows:
            events.append({
                "topic": r["topic"],
                "event_id": r["event_id"],
                "timestamp": r["ts"],
                "source": r["source"],
                "payload": json.loads(r["payload_json"]),
                "processed_at": r["processed_at"],
            })
        return events

    async def count_dedup(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            for p in PRAGMAS:
                await db.execute(p)
            cur = await db.execute("SELECT COUNT(*) FROM dedup;")
            (c,) = await cur.fetchone()
            return int(c)

    async def list_topics(self) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            for p in PRAGMAS:
                await db.execute(p)
            cur = await db.execute("SELECT DISTINCT topic FROM events ORDER BY topic;")
            rows = await cur.fetchall()
            return [r[0] for r in rows]
