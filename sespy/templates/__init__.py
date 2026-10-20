"""Built-in SES templates — domain-specific starting projects.

Two groups, both plain Project envelopes (`{metadata, isa_data}`) loaded with
`load_template()`:

- **SESPy examples**: each top-level `*.json` here, discovered by
  `list_templates()` (which validates every file).
- **MarineSABRES templates** (P2): R's 7 curated templates, pre-converted by
  `python -m scripts.sync_r_templates` into `marinesabres/`, and listed by
  `list_catalogue()` from the generated `marinesabres/catalogue.json` only
  (no project parsing at list time). Never edit those files by hand.

Loading a template into the app replaces `project_data`, fires `isa_change`,
and the analysis modules see the new SES immediately.

To add a SESPy example:
  1. Drop `mydomain.json` here, shaped like one of the existing files
  2. Restart the app — `list_templates()` discovers it automatically
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from ..data_structure import Project
from ..persistent_storage import load_project
from ..r_template_catalogue import ALWAYS_NON_EMPTY, CATALOGUE_KEYS

log = logging.getLogger(__name__)

_COUNT_KEYS = ("element_count", "connection_count")
_TEXT_KEYS = tuple(k for k in CATALOGUE_KEYS if k not in _COUNT_KEYS)


@dataclass(frozen=True)
class TemplateInfo:
    """Lightweight metadata for the picker — full Project loaded on demand."""
    file: Path
    name: str
    description: str
    da_site: str
    element_count: int
    connection_count: int
    group: str = "sespy"                 # "sespy" | "marinesabres"
    category: str = ""                   # the MarineSABRES fields (catalogue.json)
    complexity: str = ""
    version: str = ""
    regional_sea_label: str = ""
    source: str = ""
    usage_notes: str = ""


def _templates_dir() -> Path:
    return Path(__file__).parent


def _catalogue_dir() -> Path:
    return _templates_dir() / "marinesabres"


def _entry_problem(entry: object, base: Path) -> str | None:
    """Why a catalogue entry is unusable, or None when it is fine."""
    if not isinstance(entry, dict):
        return "not an object"
    missing = [k for k in CATALOGUE_KEYS if k not in entry]
    if missing:
        return f"missing {', '.join(missing)}"
    for k in _TEXT_KEYS:
        if not isinstance(entry[k], str):
            return f"{k} is not a string"
    for k in ALWAYS_NON_EMPTY:
        if not entry[k]:
            return f"empty {k}"
    for k in _COUNT_KEYS:
        v = entry[k]
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            return f"{k} is not a positive integer"
    path = (base / entry["file"]).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        return f"file {entry['file']!r} is outside the catalogue directory or missing"
    return None


def list_catalogue(directory: Path | None = None) -> list[TemplateInfo]:
    """The MarineSABRES templates, in catalogue order, from
    `<directory or templates/marinesabres>/catalogue.json` only. A bad entry
    is skipped with a WARNING; a missing or unparsable catalogue gives []."""
    d = Path(directory) if directory is not None else _catalogue_dir()
    try:
        catalogue = json.loads((d / "catalogue.json").read_bytes().decode("utf-8-sig"))
        entries = catalogue["templates"]
        if not isinstance(entries, list):
            raise TypeError("templates is not a list")
    except (OSError, ValueError, KeyError, TypeError) as e:
        log.warning("MarineSABRES template catalogue unavailable in %s: %s", d, e)
        return []
    # Both sides resolved, so an 8.3 short path or a symlinked sespy/ works.
    base = d.resolve()
    out: list[TemplateInfo] = []
    for i, entry in enumerate(entries):
        problem = _entry_problem(entry, base)
        if problem:
            log.warning("MarineSABRES catalogue entry %d skipped: %s", i, problem)
            continue
        out.append(TemplateInfo(
            file=(base / entry["file"]).resolve(),
            name=entry["name"],
            description=entry["description"],
            da_site="",
            element_count=entry["element_count"],
            connection_count=entry["connection_count"],
            group="marinesabres",
            category=entry["category"],
            complexity=entry["complexity"],
            version=entry["version"],
            regional_sea_label=entry["regional_sea_label"],
            source=entry["source"],
            usage_notes=entry["usage_notes"],
        ))
    return out


def list_templates() -> list[TemplateInfo]:
    """Scan the templates directory (top-level `*.json` only, so
    `marinesabres/` is not picked up) and return the SESPy examples,
    name-sorted. Skips files that fail to validate so a broken sample
    doesn't poison the picker."""
    out: list[TemplateInfo] = []
    for path in sorted(_templates_dir().glob("*.json")):
        try:
            project = load_project(path)
        except (ValueError, OSError):
            continue
        out.append(TemplateInfo(
            file=path,
            name=project.metadata.name or path.stem,
            description=project.metadata.description or "",
            da_site=project.metadata.da_site or "",
            element_count=project.isa_data.element_count(),
            connection_count=project.isa_data.connection_count(),
        ))
    return out


def load_template(file: Path | str) -> Project:
    """Reuse the standard project loader (validation + envelope handling)."""
    return load_project(file)
