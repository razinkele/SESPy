"""SQLite feedback store — pure data layer (no Shiny). Ported from the BowTie app."""
import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# sespy/logs/feedback.db (package-internal; logs/ is gitignored).
_DEFAULT_DB = Path(__file__).resolve().parent / "logs" / "feedback.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    category TEXT,
    message TEXT,
    rating INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    resolved_at TEXT,
    resolved_note TEXT,
    commit_sha TEXT
)
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path(db_path=None) -> Path:
    """Resolution precedence: explicit arg > SESPY_FEEDBACK_DB env > default."""
    if db_path is not None:
        return Path(db_path)
    env = os.environ.get("SESPY_FEEDBACK_DB")
    return Path(env) if env else _DEFAULT_DB


def db_path(db=None) -> Path:
    """Public wrapper — stable API for callers."""
    return _db_path(db)


def _connect(db_path=None) -> sqlite3.Connection:
    """Short-lived connection; ensures the dir + schema (idempotent). WAL + 5s
    timeout so concurrent Shiny sessions don't surface 'database is locked'."""
    path = _db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_SCHEMA)
    return conn


def add(message, rating, category, *, db_path=None) -> int:
    with closing(_connect(db_path)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO feedback (created_at, category, message, rating, status) "
            "VALUES (?, ?, ?, ?, 'open')",
            (_now_iso(), category, message, rating),
        )
        return int(cur.lastrowid)


def list_entries(status=None, limit=500, *, db_path=None) -> list[dict]:
    with closing(_connect(db_path)) as conn:
        if status is None:
            rows = conn.execute(
                "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM feedback WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [dict(r) for r in rows]


def get(entry_id, *, db_path=None) -> dict | None:
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            "SELECT * FROM feedback WHERE id = ?", (entry_id,)
        ).fetchone()
        return dict(row) if row else None
