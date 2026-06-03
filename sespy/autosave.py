"""Auto-save — write project data to a sidecar file on every ISA change.

Mirrors `modules/auto_save_module.R` (1167 LOC in R) but slimmed to the
core mechanic. Writes to `~/.sespy/autosave.json` whenever
`event_bus.isa_change` fires; on app startup the user is offered to
recover from that file if it exists and is newer than the seed sample.

Why a single sidecar file (not timestamped per-save):
- The R app rotates timestamped autosaves and prunes by age. That's a lot
  of code for a POC. One file overwritten on each change is enough to
  prevent data loss; users who care about history use Save Project.
- If the user wants version history, they explicitly save with a
  meaningful filename. Autosave is a recovery cushion, not a journal.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from .data_structure import IsaData, Project
from .persistent_storage import (
    ValidationResult,
    load_project,
    save_project_atomic,
    validate_project_payload,
)


def autosave_dir() -> Path:
    """Return `~/.sespy/`, creating it on demand. Falls back to a
    project-local `.sespy/` if HOME is unset (rare on managed Windows
    laptops in some CI environments)."""
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    base = Path(home) / ".sespy" if home else Path.cwd() / ".sespy"
    base.mkdir(parents=True, exist_ok=True)
    return base


def autosave_path() -> Path:
    return autosave_dir() / "autosave.json"


def write_autosave(project_or_isa: Project | IsaData) -> Path:
    """Atomically write the current project to the autosave path. Accepts
    either a Project or a raw IsaData (wrapped on the fly)."""
    if isinstance(project_or_isa, IsaData):
        project_or_isa = Project.from_isa(project_or_isa, name="Autosave")
    path = autosave_path()
    save_project_atomic(project_or_isa, path)
    return path


def read_autosave() -> Project | None:
    """Return the autosaved project, or None if missing/invalid. Never
    raises — autosave recovery is best-effort, a corrupt file should
    not block app startup."""
    path = autosave_path()
    if not path.exists():
        return None
    try:
        return load_project(path)
    except (ValueError, OSError):
        return None


def autosave_age_seconds() -> float | None:
    """Seconds since the autosave was last written, or None if no file."""
    path = autosave_path()
    if not path.exists():
        return None
    return (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime)


def clear_autosave() -> None:
    """Delete the autosave file. Called after the user explicitly saves
    so a stale recovery offer doesn't reappear on next launch."""
    path = autosave_path()
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
