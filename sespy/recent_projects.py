"""Recent projects registry — port of `modules/recent_projects_module.R`.

Tracks project files the user has saved or loaded in this session and on
prior sessions. Stored per browser token under `~/.sespy/recent/` (the
token is hashed into the file name, see autosave.token_key) so on a shared
server one visitor never sees another's entries. Capped at 10 entries; the
oldest is evicted when full. Without a token nothing is stored.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .autosave import private_subdir, token_key, valid_token

logger = logging.getLogger(__name__)

MAX_RECENT = 10


@dataclass
class RecentEntry:
    name: str
    path: str           # absolute path to the JSON file
    last_used: str      # ISO 8601 UTC
    element_count: int = 0
    connection_count: int = 0


def _registry_path(token: str) -> Path:
    return private_subdir("recent") / f"{token_key(token)}.json"


def list_recent(*, token: str | None) -> list[RecentEntry]:
    """Return entries newest-first. Filters out paths that no longer
    exist on disk so the user doesn't see broken pointers."""
    if not valid_token(token):
        return []
    path = _registry_path(token)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    out: list[RecentEntry] = []
    for r in raw if isinstance(raw, list) else []:
        try:
            entry = RecentEntry(**r)
        except TypeError:
            continue
        if Path(entry.path).exists():
            out.append(entry)
    out.sort(key=lambda e: e.last_used, reverse=True)
    return out[:MAX_RECENT]


def _write(token: str, entries: list[RecentEntry]) -> None:
    try:
        _registry_path(token).write_text(
            json.dumps([asdict(e) for e in entries], indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        # Best-effort — same as autosave, recent registry is a convenience.
        # Log for observability so a persistently failing write is diagnosable.
        logger.warning("recent_projects.write status=error reason=%s", type(e).__name__)


def add_recent(
    *,
    path: Path | str,
    name: str,
    element_count: int = 0,
    connection_count: int = 0,
    token: str | None,
) -> None:
    """Add or update an entry. Idempotent on path; updates `last_used`
    if the same file is touched again. No-op without a valid token."""
    if not valid_token(token):
        return
    path = str(Path(path).resolve())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    others = [e for e in list_recent(token=token) if e.path != path]
    new_entry = RecentEntry(
        name=name,
        path=path,
        last_used=now,
        element_count=element_count,
        connection_count=connection_count,
    )
    _write(token, ([new_entry] + others)[:MAX_RECENT])


def remove_recent(path: Path | str, *, token: str | None) -> None:
    """Drop an entry by path."""
    if not valid_token(token):
        return
    target = str(Path(path).resolve())
    _write(token, [e for e in list_recent(token=token) if e.path != target])
