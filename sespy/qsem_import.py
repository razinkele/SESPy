"""Direct .qsem (QSEM web app) JSON import — companion to excel_import.py.

A .qsem file is JSON: a node/link graph under `canvas`. Canonical nodes map to
Elements, links map to Connections, then the shared `validate_project_payload`
runs — so a bad .qsem fails the same way a bad JSON/Excel load does.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .constants import DAPSIWRM_ELEMENTS
from .data_structure import Connection, Element
from .persistent_storage import ValidationResult, validate_project_payload


def qsem_delay_to_level(delay: object) -> str:
    """Map a QSEM integer delay to a SESPy DELAY_LEVELS token: <=0 immediate,
    ==1 short, >=2 long. NOT `constants.normalize_delay` — that flattens every
    nonzero int to 'short', losing QSEM's slow-link signal."""
    try:
        d = int(delay)
    except (TypeError, ValueError):
        return "immediate"
    if d <= 0:
        return "immediate"
    if d == 1:
        return "short"
    return "long"


def _impact_to_strength(impact: object) -> str:
    try:
        imp = int(impact)
    except (TypeError, ValueError):
        imp = 2
    if imp <= 1:
        return "weak"
    if imp == 2:
        return "medium"
    return "strong"


def _resolve_type(theme: str, theme_map: dict[str, str] | None) -> str:
    """The final DAPSIWRM type for a node's theme. Membership-coerced (not
    truthiness) so None/stale/non-DAPSIWRM values become untyped."""
    if theme_map is None:
        return theme if theme in DAPSIWRM_ELEMENTS else ""
    rt = theme_map.get(theme, "")
    return rt if rt in DAPSIWRM_ELEMENTS else ""


def qsem_to_isa(
    data: dict, theme_map: dict[str, str] | None = None
) -> tuple[list[Element], list[Connection]]:
    """Pure map: a QSEM dict -> (elements, connections). Ghost nodes are skipped;
    links referencing a ghost are redirected to its `originalNodeId`. Dangling
    and self-loop links are skipped. Every node-field access is `.get`-safe."""
    canvas = data.get("canvas", {}) if isinstance(data, dict) else {}
    nodes = canvas.get("nodes") if isinstance(canvas.get("nodes"), list) else []
    links = canvas.get("links") if isinstance(canvas.get("links"), list) else []

    canonical = [n for n in nodes if isinstance(n, dict) and not n.get("isGhost")]
    ghost_to_original = {
        n.get("id"): n.get("originalNodeId") for n in nodes if isinstance(n, dict) and n.get("isGhost")
    }

    elements: list[Element] = []
    id_map: dict[str, str] = {}
    for i, node in enumerate(canonical, start=1):
        new_id = f"N{i:03d}"
        qid = node.get("id")
        if qid is not None:
            id_map[qid] = new_id
        theme = node.get("theme") or ""
        rt = _resolve_type(theme, theme_map)
        elements.append(Element(
            id=new_id,
            label=str(node.get("label", "")),
            type=rt,
            description="" if (rt or not theme) else f"Theme: {theme}",
            confidence=3,
        ))

    def resolve(ref: object) -> str | None:
        return id_map.get(ghost_to_original.get(ref, ref))

    connections: list[Connection] = []
    for link in links:
        if not isinstance(link, dict):
            continue
        src = resolve(link.get("sourceNodeId"))
        tgt = resolve(link.get("targetNodeId"))
        if src is None or tgt is None or src == tgt:
            continue
        connections.append(Connection(
            source=src,
            target=tgt,
            polarity="-" if link.get("polarity") == "negative" else "+",
            strength=_impact_to_strength(link.get("impact", 2)),
            confidence=3,
            delay=qsem_delay_to_level(link.get("delay", 0)),
        ))
    return elements, connections


def qsem_themes(data: dict) -> list[tuple[str, int]]:
    """Distinct themes of canonical (non-ghost) nodes with counts. Uses the
    SAME node guard and `theme or ""` normalization as qsem_to_isa so the keys
    line up exactly with what gets typed. Sorted by count desc, then name."""
    canvas = data.get("canvas", {}) if isinstance(data, dict) else {}
    nodes = canvas.get("nodes") if isinstance(canvas.get("nodes"), list) else []
    counts: Counter[str] = Counter(
        (n.get("theme") or "")
        for n in nodes
        if isinstance(n, dict) and not n.get("isGhost")
    )
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def build_project(
    data: dict, name: str, theme_map: dict[str, str] | None = None
) -> ValidationResult:
    """Map a QSEM dict -> validated Project named `name`. Shared by parse_qsem
    (theme_map=None) and the import module's DAPSIWRM re-map path, so both
    validate and name identically."""
    elements, connections = qsem_to_isa(data, theme_map)
    payload = {
        "metadata": {"name": name, "description": f"Imported from {name}"},
        "isa_data": {
            "elements": [e.__dict__ for e in elements],
            "connections": [c.__dict__ for c in connections],
        },
    }
    return validate_project_payload(payload)


def parse_qsem(path: Path | str) -> ValidationResult:
    """Parse a .qsem JSON file into a Project. Same contract as parse_excel."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return ValidationResult(False, [f"Not a valid QSEM/JSON file: {e}"])

    canvas = data.get("canvas", {}) if isinstance(data, dict) else {}
    if not isinstance(canvas.get("nodes"), list):
        return ValidationResult(False, ["Not a QSEM file (missing canvas.nodes)"])
    if not canvas.get("nodes"):
        return ValidationResult(False, ["QSEM file has no nodes"])

    return build_project(data, path.stem)
