from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .safety_policy import SafetyDecision


PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DB = PROJECT_ROOT / "runtime" / "security" / "safety_audit.sqlite3"


class SafetyAuditLog:
    """Compact SQLite audit trail for safety decisions.

    The log stores a hash and a short redacted preview instead of the full input,
    so pasted secrets are less likely to be preserved in clear text.
    """

    SECRETISH = re.compile(r"(?i)(api[_ -]?key|token|password|secret|認証コード|秘密鍵)\s*[:=]?\s*\S+")
    EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
    LONG_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_\-]{24,}(?![A-Za-z0-9])")

    def __init__(self, path: Path = AUDIT_DB) -> None:
        self.path = path

    def record(
        self,
        *,
        scope: str,
        decision: SafetyDecision,
        text: str,
        agent_name: str | None = None,
        session_path: Path | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._init_db()
        payload_json = json.dumps(extra or {}, ensure_ascii=False, separators=(",", ":"))
        risks_json = json.dumps(list(decision.risks), ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(self.path) as con:
            con.execute(
                """
                INSERT INTO safety_events(
                    created_at,
                    scope,
                    agent_name,
                    session_path,
                    allowed,
                    requires_review,
                    reason,
                    risks_json,
                    text_hash,
                    text_preview,
                    extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    scope,
                    agent_name,
                    str(session_path) if session_path else None,
                    1 if decision.allowed else 0,
                    1 if decision.requires_review else 0,
                    decision.reason,
                    risks_json,
                    self._hash_text(text),
                    self._preview(text),
                    payload_json,
                ),
            )

    def latest(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        self._init_db()
        with sqlite3.connect(self.path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                """
                SELECT *
                FROM safety_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _init_db(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS safety_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    agent_name TEXT,
                    session_path TEXT,
                    allowed INTEGER NOT NULL,
                    requires_review INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    risks_json TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    text_preview TEXT NOT NULL,
                    extra_json TEXT NOT NULL
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_safety_scope_id ON safety_events(scope, id)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_safety_allowed_review ON safety_events(allowed, requires_review)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_safety_agent_id ON safety_events(agent_name, id)")

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    def _preview(self, text: str, limit: int = 160) -> str:
        redacted = self.SECRETISH.sub("[REDACTED_SECRET]", text)
        redacted = self.EMAIL.sub("[REDACTED_EMAIL]", redacted)
        redacted = self.LONG_TOKEN.sub("[REDACTED_TOKEN]", redacted)
        redacted = " ".join(redacted.split())
        if len(redacted) > limit:
            redacted = redacted[: limit - 1] + "…"
        return redacted
