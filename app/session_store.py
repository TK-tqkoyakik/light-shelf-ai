from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_DIR = PROJECT_ROOT / "runtime" / "sessions"


class SessionStore:
    """SQLite session flow store so AIs do not need to keep history internally."""

    def __init__(self, session_dir: Path = SESSION_DIR) -> None:
        self.session_dir = session_dir

    def create(self, title: str) -> Path:
        self.session_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_title = "".join(char for char in title if char.isalnum() or char in ("-", "_"))[:30] or "session"
        path = self.session_dir / f"{stamp}-{safe_title}.sqlite3"
        self._init_db(path)
        self.append(path, "session_started", {"title": title})
        return path

    def append(self, path: Path, event: str, payload: dict[str, Any]) -> None:
        path.parent.mkdir(exist_ok=True)
        self._init_db(path)
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(path) as con:
            con.execute(
                "INSERT INTO events(created_at, event, payload_json) VALUES (?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), event, payload_json),
            )

    def read_handoffs(self, path: Path, limit: int = 8) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        self._init_db(path)
        with sqlite3.connect(path) as con:
            rows = con.execute(
                """
                SELECT payload_json
                FROM events
                WHERE event = 'handoff'
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    def append_dataclass(self, path: Path, event: str, value: Any) -> None:
        self.append(path, event, asdict(value))

    def _init_db(self, path: Path) -> None:
        path.parent.mkdir(exist_ok=True)
        with sqlite3.connect(path) as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_events_event_id ON events(event, id)")
