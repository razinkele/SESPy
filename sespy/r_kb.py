"""K1 reference-data layer: allow-list, vendored load, immutable snapshots.

Shiny-free. Importing this module loads the vendored R knowledge-base files
eagerly (a broken build must not start) and reads nothing relative to APP_DIR.
"""
from __future__ import annotations

import json
import logging
import os
import stat as _stat
import time
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from sespy.r_sync import sha256_norm

KB_NAME = "ses_knowledge_db.json"
GOVERNANCE_NAME = "country_governance_db.json"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class AllowRow:
    name: str
    required_keys: tuple[str, ...]
    min_counts: dict[str, int]
    version_key: str
    override: bool
    # JSON container each min_counts path must be: a list of the right length
    # where readers call .get() would pass the count and crash a session.
    containers: dict[str, type] = field(default_factory=dict)


ALLOW_LIST: tuple[AllowRow, ...] = (
    AllowRow(
        name=KB_NAME,
        required_keys=("version", "contexts", "generic_fallback", "cross_ecosystem_links"),
        min_counts={"contexts": 33, "cross_ecosystem_links": 0},
        version_key="version",
        override=True,
        containers={"contexts": dict, "cross_ecosystem_links": list},
    ),
    AllowRow(
        name=GOVERNANCE_NAME,
        required_keys=(
            "version", "description", "countries_by_sea", "countries",
            "governance_elements", "socioeconomic_elements", "regional_conventions",
        ),
        min_counts={"countries": 105, "regional_conventions": 15, "countries_by_sea": 11},
        version_key="version",
        override=True,
        containers={"countries": dict, "regional_conventions": dict, "countries_by_sea": dict},
    ),
)


def _row(name: str) -> AllowRow:
    for row in ALLOW_LIST:
        if row.name == name:
            return row
    raise KeyError(f"{name!r} is not on the reference-data allow-list")


def version_major(value: int | str) -> int:
    """Major of a version key: an int is its own major; "1.0" -> 1."""
    if isinstance(value, bool):
        raise ValueError(f"not a version: {value!r}")
    if isinstance(value, int):
        return value
    return int(str(value).strip().split(".", 1)[0])


def _dig(data: Any, dotted: str) -> Any:
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def validate(row: AllowRow, data: Any, vendored_major: int) -> str | None:
    """None when `data` is acceptable for `row`, else a human-readable reason."""
    if not isinstance(data, dict):
        return "top level is not a JSON object"
    for key in row.required_keys:
        if key not in data:
            return f"missing required key {key!r}"
    try:
        major = version_major(data[row.version_key])
    except (ValueError, TypeError):
        return f"unreadable {row.version_key!r}: {data[row.version_key]!r}"
    if major != vendored_major:
        return f"major version {major} differs from vendored {vendored_major}"
    for path, minimum in row.min_counts.items():
        try:
            value = _dig(data, path)
        except KeyError:
            return f"missing {path!r}"
        want = row.containers.get(path)
        if want is not None and not isinstance(value, want):
            return f"{path!r} is a {type(value).__name__}, expected a {want.__name__}"
        try:
            n = len(value)
        except TypeError:
            return f"{path!r} has no length"
        if n < minimum:
            return f"{path!r} has {n} entries, fewer than the required {minimum}"
    return None


@dataclass(frozen=True)
class Entry:
    data: Any
    sha256_norm: str
    source: Literal["vendored", "shared"]
    version: str

    def provenance(self, vendored_r_tag: str) -> dict:
        return {
            "source": self.source,
            "sha256_norm": self.sha256_norm,
            "version": self.version,
            "vendored_r_tag": vendored_r_tag,
        }


def current_provenance(meta: Any, snapshot: "Snapshot", reads: frozenset[str]) -> dict:
    """Loaded entries kept, overlaid with this session's reads. Pure."""
    return {**meta.reference_data, **{f: snapshot.provenance(f) for f in reads}}


def add_reads(reads: Any, names: Iterable[str]) -> None:
    """Record that this session read `names` from its snapshot.

    `reads` is the session's `reactive.Value[frozenset[str]]`, or None for a
    caller mounted without one (MosaicSES): then this is a no-op. The value
    is read under `isolate()` and set only when a name is new, so a render
    that calls this never invalidates itself (`Value.set` compares by
    identity, so an unconditional set of a fresh frozenset would loop).
    """
    if reads is None:
        return
    from shiny import reactive  # lazy: r_kb stays stdlib-only at import

    with reactive.isolate():
        current_reads = reads.get()
    new = frozenset(names) - current_reads
    if new:
        reads.set(current_reads | new)


@dataclass(frozen=True)
class Snapshot:
    files: Mapping[str, Entry]
    taken_at: float
    manifest: dict
    live_r_version: str | None = None

    def get(self, name: str) -> Any:
        return self.files[name].data

    def kb(self) -> Any:
        return self.get(KB_NAME)

    def governance(self) -> Any:
        return self.get(GOVERNANCE_NAME)

    def provenance(self, name: str) -> dict:
        return self.files[name].provenance(self.manifest["r_tag"])

    def label(self, name: str) -> str:
        tag = self.manifest["r_tag"]
        entry = self.files[name]
        if entry.source == "vendored" or entry.sha256_norm == self.manifest["files"].get(name):
            return f"R {tag}"
        return f"shared, differs from R {tag}"


def _read_json(name: str) -> Any:
    try:
        text = (resources.files("sespy") / "data" / "r_kb" / name).read_text(encoding="utf-8-sig")
        return json.loads(text)
    except Exception as exc:  # missing file, bad JSON, bad encoding
        raise RuntimeError(f"vendored R reference file {name} is missing or unreadable: {exc}") from exc


def _load_vendored() -> Snapshot:
    import time

    manifest = _read_json(MANIFEST_NAME)
    files: dict[str, Entry] = {}
    for row in ALLOW_LIST:
        data = _read_json(row.name)
        if not isinstance(data, dict) or row.version_key not in data:
            raise RuntimeError(f"vendored R reference file {row.name} is invalid: no {row.version_key!r}")
        reason = validate(row, data, version_major(data[row.version_key]))
        if reason:
            raise RuntimeError(f"vendored R reference file {row.name} is invalid: {reason}")
        digest = sha256_norm(data)
        pinned = manifest.get("files", {}).get(row.name)
        if pinned != digest:
            raise RuntimeError(
                f"vendored R reference file {row.name} does not match manifest hash "
                f"({digest} != {pinned})"
            )
        files[row.name] = Entry(data=data, sha256_norm=digest, source="vendored",
                                version=str(data[row.version_key]))
    return Snapshot(files=files, taken_at=time.time(), manifest=manifest, live_r_version=None)


VENDORED: Snapshot = _load_vendored()


# ---------------------------------------------------------------------------
# Registry: live override, settings file, change detection, fallback (§4.1)
# ---------------------------------------------------------------------------
ENV_VAR = "SESPY_R_DATA_DIR"
SETTINGS_FILE = "server_settings.env"
DEFAULT_OVERRIDE_DIR = "/srv/shiny-server/marinesabres/data"
VERSION_INFO_NAME = "VERSION_INFO.json"

_log = logging.getLogger("sespy.r_kb")


def parse_settings_text(text: str) -> str | None:
    """THE settings-file parse rule (reused by check_live.py; mirrored by deploy.sh).

    Never `source` the file. Take the LAST line starting with
    ``SESPY_R_DATA_DIR=`` (no leading whitespace), strip the prefix and
    surrounding whitespace. Returns that raw value (possibly "" or "off"), or
    None when no line matches. Interpreting the value is `override_dir_from`'s job.
    """
    value: str | None = None
    prefix = ENV_VAR + "="
    for line in text.splitlines():
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
    return value


def override_dir_from(env: Mapping[str, str], settings_text: str | None) -> str | None:
    """Resolve the override directory: a path string, or None when the override is off.

    A variable present in `env` (even empty) wins and the settings file is
    ignored. Otherwise `settings_text` (None = file absent) is parsed with
    `parse_settings_text`; no matching line, or no file, means the default
    directory. An empty value or `off` (case-insensitive) means off.
    """
    if ENV_VAR in env:
        raw: str | None = env[ENV_VAR]
    else:
        raw = parse_settings_text(settings_text) if settings_text is not None else None
    if raw is None:
        return DEFAULT_OVERRIDE_DIR
    raw = raw.strip()
    if raw == "" or raw.lower() == "off":
        return None
    return raw


def _read_live_version(directory: Path) -> str | None:
    try:
        info = json.loads((directory.parent / VERSION_INFO_NAME).read_text(encoding="utf-8-sig"))
        value = info.get("version") if isinstance(info, dict) else None
        return None if value is None else str(value)
    except Exception:
        return None


class _Unreadable(Exception):
    """Override material that exists but cannot be read (permissions)."""


class _Registry:
    def __init__(self, vendored: Snapshot | None = None) -> None:
        self._vendored = vendored if vendored is not None else VENDORED
        self._snapshot: Snapshot = self._vendored
        self._app_dir: Path | None = None
        self._seen: tuple | None = None
        self._last_shared: dict[str, str] = {}

    def configure(self, app_dir: Path) -> None:
        self._app_dir = Path(app_dir)
        self._seen = None

    def current(self) -> Snapshot:
        return self._snapshot

    def hashes_for_load_check(self, name: str) -> tuple[str, str | None]:
        _row(name)
        return self._vendored.files[name].sha256_norm, self._last_shared.get(name)

    def refresh(self) -> None:
        """Never raises: it runs at every session start (app.py), so any
        unexpected failure logs a warning and falls back to the shipped copy."""
        try:
            self._refresh()
        except Exception as exc:  # noqa: BLE001 - a session must always start
            _log.warning("r_kb.refresh failed (%s: %s); using the shipped copy",
                         type(exc).__name__, exc)
            try:
                self._fall_to_vendored(f"refresh failed: {type(exc).__name__}")
            except Exception:  # noqa: BLE001
                self._seen = None
                self._snapshot = self._vendored

    def _refresh(self) -> None:
        if self._app_dir is None:
            return
        directory_str = override_dir_from(os.environ, self._read_settings())
        if directory_str is None:
            self._fall_to_vendored("override off")
            return
        directory = Path(directory_str)
        try:
            if not _stat.S_ISDIR(os.stat(directory).st_mode):
                raise FileNotFoundError(str(directory))
        except (OSError, ValueError) as exc:  # ValueError: a NUL in the path
            self._fall_to_vendored(f"override directory unavailable: {type(exc).__name__}")
            return

        keys: dict[str, tuple | None] = {}
        problems: dict[str, str] = {}
        for row in ALLOW_LIST:
            if not row.override:
                continue
            try:
                st = os.stat(directory / row.name)
                keys[row.name] = (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            except PermissionError as exc:
                self._fall_to_vendored(f"{row.name} unreadable: {type(exc).__name__}")
                return
            except FileNotFoundError:
                keys[row.name] = None
                problems[row.name] = "file missing from override directory"
            except OSError as exc:
                keys[row.name] = None
                problems[row.name] = f"stat failed: {type(exc).__name__}"
        seen = (str(directory), tuple(sorted(keys.items())))
        if not problems and seen == self._seen:
            return

        entries: dict[str, Entry] = {}
        for row in ALLOW_LIST:
            if not row.override or row.name in problems:
                continue
            try:
                entry, reason = self._parse(directory / row.name, row)
            except _Unreadable as exc:
                self._fall_to_vendored(f"{row.name} unreadable: {exc}")
                return
            if entry is None:
                problems[row.name] = reason or "invalid"
            else:
                entries[row.name] = entry
                self._last_shared[row.name] = entry.sha256_norm

        if problems:
            self._keep_last_good(problems)
            return

        old = self._snapshot
        files = dict(self._vendored.files)
        files.update(entries)
        self._snapshot = Snapshot(files=files, taken_at=time.time(),
                                  manifest=self._vendored.manifest,
                                  live_r_version=_read_live_version(directory))
        self._seen = seen
        for name, entry in entries.items():
            before = old.files[name]
            if before.source != "shared":
                self._log(name, before.source, "shared", "override file validated", entry.sha256_norm)
            elif before.sha256_norm != entry.sha256_norm:
                self._log(name, "shared", "shared", "override file changed", entry.sha256_norm)

    def _read_settings(self) -> str | None:
        # errors="replace": deploy.sh parses the file as bytes, so a non-UTF-8
        # byte elsewhere (e.g. a cp1257 comment) must not hide the ASCII
        # SESPY_R_DATA_DIR= line; treating the file as absent would switch an
        # `off` file to the default directory.
        try:
            return (self._app_dir / SETTINGS_FILE).read_text(encoding="utf-8-sig",
                                                              errors="replace")
        except OSError:
            return None

    def _parse(self, path: Path, row: AllowRow) -> tuple[Entry | None, str | None]:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except PermissionError as exc:
            raise _Unreadable(type(exc).__name__) from exc
        except UnicodeDecodeError:
            return None, "not valid UTF-8"
        except OSError as exc:
            return None, f"read failed: {type(exc).__name__}"
        try:
            data = json.loads(text)
        except ValueError as exc:
            return None, f"unparsable JSON: {exc}"
        vendored_major = version_major(self._vendored.files[row.name].version)
        reason = validate(row, data, vendored_major)
        if reason:
            return None, reason
        return Entry(data=data, sha256_norm=sha256_norm(data), source="shared",
                     version=str(data[row.version_key])), None

    @staticmethod
    def _log(name: str, src: str, dst: str, reason: str, digest: str) -> None:
        _log.warning("r_kb.transition file=%s from=%s to=%s reason=%s hash=%s",
                     name, src, dst, reason, digest[:8])

    def _fall_to_vendored(self, reason: str) -> None:
        self._seen = None
        old = self._snapshot
        if all(e.source == "vendored" for e in old.files.values()):
            return
        for name, entry in old.files.items():
            if entry.source != "vendored":
                self._log(name, entry.source, "vendored", reason,
                          self._vendored.files[name].sha256_norm)
        self._snapshot = Snapshot(files=dict(self._vendored.files), taken_at=time.time(),
                                  manifest=self._vendored.manifest, live_r_version=None)

    def _keep_last_good(self, problems: dict[str, str]) -> None:
        """A failure is never recorded as seen; the snapshot stays as it is."""
        self._seen = None
        has_good = any(e.source == "shared" for e in self._snapshot.files.values())
        for name, reason in problems.items():
            entry = self._snapshot.files[name]
            self._log(name, entry.source, "last-good" if has_good else "vendored",
                      reason, entry.sha256_norm)


_REGISTRY = _Registry()


def configure(app_dir: Path) -> None:
    _REGISTRY.configure(app_dir)


def refresh() -> None:
    _REGISTRY.refresh()


def current() -> Snapshot:
    return _REGISTRY.current()


def hashes_for_load_check(name: str) -> tuple[str, str | None]:
    """(vendored_hash, last_parsed_shared_hash); the latter survives a fallback, None before any parse."""
    return _REGISTRY.hashes_for_load_check(name)
