"""Built-in SES templates — domain-specific starting projects.

Each `*.json` in this directory is a Project envelope (`{metadata, isa_data}`).
Loading a template into the app replaces `project_data`, fires `isa_change`,
and the four analysis modules see the new SES immediately.

To add a new template:
  1. Drop `mydomain.json` here, shaped like one of the existing files
  2. Restart the app — `list_templates()` discovers it automatically
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..persistent_storage import load_project
from ..data_structure import Project


@dataclass(frozen=True)
class TemplateInfo:
    """Lightweight metadata for the picker — full Project loaded on demand."""
    file: Path
    name: str
    description: str
    da_site: str
    element_count: int
    connection_count: int


def _templates_dir() -> Path:
    return Path(__file__).parent


def list_templates() -> list[TemplateInfo]:
    """Scan the templates directory and return discovered templates,
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
