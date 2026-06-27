"""Persistent storage — port of functions/persistent_storage.R + the
validation pieces of server/project_io.R::validate_json_project_input.

Keeps project I/O off the module surface — modules talk to a
`reactive.Value[IsaData]` and don't care where it came from.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import DAPSIWRM_ELEMENTS, DELAY_LEVELS
from .data_structure import Project

# Controlled vocabularies enforced at load time. A value is only checked when
# the key is present and non-null — an omitted field falls back to the
# dataclass default in Project.from_dict, so optional fields stay optional.
# Element.type tolerates "" (an explicitly untyped node — e.g. a QSEM theme
# that doesn't map onto a DAPSI(W)R(M) layer) so importer round-trips survive.
_VALID_ELEMENT_TYPES: frozenset[str] = frozenset(DAPSIWRM_ELEMENTS) | {""}
_VALID_POLARITIES: frozenset[str] = frozenset({"+", "-"})
_VALID_STRENGTHS: frozenset[str] = frozenset({"weak", "medium", "strong"})
_VALID_DELAYS: frozenset[str] = frozenset(DELAY_LEVELS)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    project: Project | None = None


def validate_project_payload(raw: dict[str, Any]) -> ValidationResult:
    """Schema-check a parsed JSON payload before constructing a Project.

    Mirrors `validate_json_project_input` in server/project_io.R — the goal
    is to catch obvious garbage before it reaches the reactive graph, where
    bad data causes hard-to-debug downstream errors.
    """
    errors: list[str] = []
    if not isinstance(raw, dict):
        return ValidationResult(False, ["payload must be a JSON object"])
    isa = raw.get("isa_data") or raw  # tolerate flat shape
    elements = isa.get("elements")
    connections = isa.get("connections")
    if not isinstance(elements, list) or not isinstance(connections, list):
        if not isinstance(elements, list):
            errors.append("isa_data.elements must be a list")
        if not isinstance(connections, list):
            errors.append("isa_data.connections must be a list")
        return ValidationResult(False, errors)

    # Per-element / per-connection structural checks. Stop after first 5
    # errors per category so the user gets a concise summary, not a flood.
    seen_ids: set[Any] = set()
    for i, el in enumerate(elements):
        if not isinstance(el, dict):
            errors.append(f"element[{i}] is not an object")
            continue
        for required in ("id", "label", "type"):
            if required not in el:
                errors.append(f"element[{i}] missing required field {required!r}")
        etype = el.get("type")
        if etype is not None and etype not in _VALID_ELEMENT_TYPES:
            errors.append(
                f"element[{i}] has invalid type {etype!r} "
                f"(expected one of {sorted(DAPSIWRM_ELEMENTS)})"
            )
        if el.get("id") in seen_ids:
            errors.append(f"element[{i}] has duplicate id {el.get('id')!r}")
        else:
            seen_ids.add(el.get("id"))
        if len(errors) >= 5:
            break

    if not errors:
        valid_ids = {e["id"] for e in elements if isinstance(e, dict) and "id" in e}
        for i, c in enumerate(connections):
            if not isinstance(c, dict):
                errors.append(f"connection[{i}] is not an object")
                continue
            for ref in ("source", "target"):
                if c.get(ref) not in valid_ids:
                    errors.append(
                        f"connection[{i}].{ref} references unknown element id "
                        f"{c.get(ref)!r}"
                    )
            # Self-loop: a connection from an element to itself. Rejected
            # outright (not silently dropped) so a malformed model surfaces at
            # load instead of vanishing in the analysis layer, which skips
            # self-loops.
            src, tgt = c.get("source"), c.get("target")
            if src is not None and src == tgt:
                errors.append(
                    f"connection[{i}] is a self-loop on element {src!r} "
                    f"(source and target must differ)"
                )
            pol = c.get("polarity")
            if pol is not None and pol not in _VALID_POLARITIES:
                errors.append(
                    f"connection[{i}] has invalid polarity {pol!r} "
                    f"(expected '+' or '-')"
                )
            strength = c.get("strength")
            if strength is not None and strength not in _VALID_STRENGTHS:
                errors.append(
                    f"connection[{i}] has invalid strength {strength!r} "
                    f"(expected one of {sorted(_VALID_STRENGTHS)})"
                )
            delay = c.get("delay")
            if delay is not None and delay not in _VALID_DELAYS:
                errors.append(
                    f"connection[{i}] has invalid delay {delay!r} "
                    f"(expected one of {sorted(_VALID_DELAYS)})"
                )
            if len(errors) >= 10:
                break

    if errors:
        return ValidationResult(False, errors)
    return ValidationResult(True, [], Project.from_dict(raw))


def save_project_atomic(project: Project, path: Path | str) -> None:
    """Write a Project to disk via temp-file-and-rename. The replace is
    atomic on every supported OS (POSIX rename + Windows MoveFileEx),
    so a crashed write never leaves a half-written file behind.

    Mirrors the discipline in functions/persistent_storage.R::write_atomic.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = project.with_modified_now().to_json()
    fd, tmp_name = tempfile.mkstemp(
        prefix=target.stem + ".",
        suffix=".tmp.json",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, target)
    except Exception:
        # Best-effort cleanup of the orphan temp file
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_project(path: Path | str) -> Project:
    """Read a Project from disk. Raises ValueError on validation failure."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    result = validate_project_payload(raw)
    if not result.valid or result.project is None:
        raise ValueError(
            "Invalid project file:\n  - " + "\n  - ".join(result.errors)
        )
    return result.project


def project_to_bytes(project: Project) -> bytes:
    """Serialize a Project for the Shiny download handler (`bytes` payload)."""
    return project.with_modified_now().to_json().encode("utf-8")
