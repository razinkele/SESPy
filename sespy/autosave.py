"""Auto-save — write project data to a per-browser sidecar file on every
ISA change.

Mirrors `modules/auto_save_module.R` (1167 LOC in R) but slimmed to the
core mechanic. Writes whenever `event_bus.isa_change` fires; on app
startup the user is offered to recover from that file if it exists and is
newer than the seed sample.

Why one file per browser token (port of R 1.20.1 N7):
- On a shared server every session runs as the same OS user, so a single
  `~/.sespy/autosave.json` was one file for EVERY visitor — the recovery
  toast handed one user's project to the next. Each browser keeps a random
  token in localStorage (www/browser-token.js) and only ever sees the
  autosave stored under the hash of that token.
- No token, no autosave: there is no shared fallback.
- Autosave is a recovery cushion, not a journal. Files older than 72 h are
  pruned; users who care about history use Save Project.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .data_structure import IsaData, Project
from .persistent_storage import (
    load_project,
    save_project_atomic,
)

logger = logging.getLogger(__name__)

AUTOSAVE_MAX_AGE_HOURS = 72

# crypto.randomUUID() output, or any similarly opaque id. Anything else
# (path separators, spaces, very short or long values) is refused, so a
# crafted input can never steer the file name.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9-]{32,64}$")

# Pre-1.12.2 files shared by every session on a server. They can't be
# attributed to anyone, so they are deleted and never offered.
_LEGACY_SHARED_FILES = ("autosave.json", "recent.json")


def valid_token(token: object) -> bool:
    return isinstance(token, str) and bool(_TOKEN_RE.fullmatch(token))


def token_key(token: str) -> str:
    """File-name-safe key for a token. A hash, so a directory listing never
    reveals a token another browser could replay."""
    if not valid_token(token):
        raise ValueError("invalid browser token")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def autosave_dir() -> Path:
    """Return `~/.sespy/`, creating it on demand. Falls back to a
    project-local `.sespy/` if HOME is unset (rare on managed Windows
    laptops in some CI environments)."""
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    base = Path(home) / ".sespy" if home else Path.cwd() / ".sespy"
    base.mkdir(parents=True, exist_ok=True)
    return base


def private_subdir(name: str) -> Path:
    """`~/.sespy/<name>/`, created owner-only (0700) on POSIX."""
    path = autosave_dir() / name
    path.mkdir(mode=0o700, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def autosave_path(token: str) -> Path:
    return private_subdir("autosaves") / f"{token_key(token)}.json"


def write_autosave(project_or_isa: Project | IsaData, *, token: str) -> Path | None:
    """Atomically write the current project to this browser's autosave.
    Accepts either a Project or a raw IsaData (wrapped on the fly).

    Returns None without writing for a project loaded from a newer SESPy
    (`newer_build_note`): this build has already dropped the data it does
    not understand, and an autosave would make that loss look like the
    user's last good state."""
    if isinstance(project_or_isa, IsaData):
        project_or_isa = Project.from_isa(project_or_isa, name="Autosave")
    if project_or_isa.newer_build_note:
        logger.info("autosave.write status=skipped reason=newer_build")
        return None
    path = autosave_path(token)
    try:
        save_project_atomic(project_or_isa, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        logger.info("autosave.write status=ok")
    except Exception as e:
        logger.error("autosave.write status=error reason=%s", type(e).__name__)
        raise
    return path


def read_autosave(*, token: str | None) -> Project | None:
    """Return this browser's autosaved project, or None if missing, invalid
    or the token is unusable. Never raises — autosave recovery is
    best-effort, a corrupt or newer-schema file must not block startup."""
    if not valid_token(token):
        return None
    path = autosave_path(token)
    if not path.exists():
        return None
    try:
        return load_project(path)
    except (ValueError, OSError, TypeError, KeyError):
        return None


def autosave_age_seconds(*, token: str | None) -> float | None:
    """Seconds since this browser's autosave was written, or None."""
    if not valid_token(token):
        return None
    path = autosave_path(token)
    if not path.exists():
        return None
    return (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime)


def clear_autosave(*, token: str | None) -> None:
    """Delete this browser's autosave. Called after the user explicitly
    saves so a stale recovery offer doesn't reappear on next launch."""
    if not valid_token(token):
        return
    path = autosave_path(token)
    if path.exists():
        try:
            path.unlink()
            logger.info("autosave.clear status=ok")
        except OSError as e:
            logger.error("autosave.clear status=error reason=%s", type(e).__name__)
            raise


def prune_autosaves(max_age_hours: float = AUTOSAVE_MAX_AGE_HOURS) -> int:
    """Delete autosaves older than `max_age_hours`; return how many."""
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for path in private_subdir("autosaves").glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info("autosave.prune removed=%d", removed)
    return removed


_HOUSEKEEPING_INTERVAL_S = 3600
_last_housekeeping: float | None = None


def housekeeping(now: float | None = None) -> bool:
    """Remove the legacy shared files and prune old autosaves, at most once
    an hour per process (every session start calls this). Returns whether
    it ran."""
    global _last_housekeeping
    now = time.time() if now is None else now
    if _last_housekeeping is not None and now - _last_housekeeping < _HOUSEKEEPING_INTERVAL_S:
        return False
    _last_housekeeping = now
    remove_legacy_shared_files()
    prune_autosaves()
    return True


def remove_legacy_shared_files() -> int:
    """Delete the pre-1.12.2 shared autosave/recent files; return how many."""
    removed = 0
    for name in _LEGACY_SHARED_FILES:
        path = autosave_dir() / name
        try:
            if path.is_file():
                path.unlink()
                removed += 1
        except OSError as e:
            logger.warning("autosave.legacy_remove status=error reason=%s", type(e).__name__)
    if removed:
        logger.info("autosave.legacy_remove removed=%d", removed)
    return removed
