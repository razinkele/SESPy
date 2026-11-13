"""K1 reference-data layer: allow-list, vendored load, immutable snapshots.

Shiny-free. Importing this module loads the vendored R knowledge-base files
eagerly (a broken build must not start) and reads nothing relative to APP_DIR.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Literal, Mapping

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


ALLOW_LIST: tuple[AllowRow, ...] = (
    AllowRow(
        name=KB_NAME,
        required_keys=("version", "contexts", "generic_fallback", "cross_ecosystem_links"),
        min_counts={"contexts": 33, "cross_ecosystem_links": 0},
        version_key="version",
        override=True,
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
            n = len(_dig(data, path))
        except KeyError:
            return f"missing {path!r}"
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
