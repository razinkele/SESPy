"""Recent projects registry — port of `modules/recent_projects_module.R`.

Tracks project files the user has saved or loaded in this session and on
prior sessions. Stored as `~/.sespy/recent.json` so it survives between
sessions. Capped at 10 entries; the oldest is evicted when full.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .autosave import autosave_dir

MAX_RECENT = 10
RECENT_FILE = "recent.json"


@dataclass
class RecentEntry:
    name: str
    path: str           # absolute path to the JSON file
    last_used: str      # ISO 8601 UTC
    element_count: int = 0
    connection_count: int = 0


def _registry_path() -> Path:
    return autosave_dir() / RECENT_FILE


def list_recent() -> list[RecentEntry]:
    """Return entries newest-first. Filters out paths that no longer
    exist on disk so the user doesn't see broken pointers."""
    path = _registry_path()
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


def add_recent(
    *,
    path: Path | str,
    name: str,
    element_count: int = 0,
    connection_count: int = 0,
) -> None:
    """Add or update an entry. Idempotent on path; updates `last_used`
    if the same file is touched again."""
    path = str(Path(path).resolve())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    existing = list_recent()
    # Drop any prior entry with the same path so the new one floats to top
    others = [e for e in existing if e.path != path]
    new_entry = RecentEntry(
        name=name,
        path=path,
        last_used=now,
        element_count=element_count,
        connection_count=connection_count,
    )
    rolled = [new_entry] + others
    rolled = rolled[:MAX_RECENT]
    try:
        _registry_path().write_text(
            json.dumps([asdict(e) for e in rolled], indent=2),
            encoding="utf-8",
        )
    except OSError:
        # Best-effort — same as autosave, recent registry is a convenience
        pass


def remove_recent(path: Path | str) -> None:
    """Drop an entry by path."""
    target = str(Path(path).resolve())
    others = [e for e in list_recent() if e.path != target]
    try:
        _registry_path().write_text(
            json.dumps([asdict(e) for e in others], indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
