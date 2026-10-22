"""Convert an R MarineSABRES `*_SES_Template.json` into a SESPy Project (P1a).

A library function, not UI: P1a uses it on sha256-pinned test fixtures
(tests/parity/r_templates/), P2's sync script reuses it to build gallery
templates. Shiny-free, never uses the clock (converting a file twice gives
identical output), and never logs: everything worth reporting goes into the
ConversionReport and the caller decides what to log.

R reference: functions/template_loader.R (v1.29.0, unchanged at v1.31.0). Measures fold into
Responses as R does (template_loader.R:103,189-190), marked with
r_extra["r_kind"] = "measure". Element-level `type` labels and every field
without a SESPy column are kept in Element.r_extra (R drops them), and
connection descriptions are kept (R drops them on template load).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_structure import Connection, Element, IsaData, Project, ProjectMetadata, indicator_text
from .link_rules import classify

# (canonical key, legacy alias, SESPy type). Order = DAPSI(W)R(M) flow.
_CATEGORIES: tuple[tuple[str, str | None, str], ...] = (
    ("drivers", None, "Drivers"),
    ("activities", None, "Activities"),
    ("pressures", None, "Pressures"),
    ("marine_processes", "states", "Marine Processes & Functioning"),
    ("ecosystem_services", "impacts", "Ecosystem Services"),
    ("goods_benefits", "welfare", "Goods & Benefits"),
    ("responses", None, "Responses"),
    ("measures", None, "Responses"),        # folded, r_kind = "measure"
)

# R's connection from_type/to_type labels -> the R category they name.
_LABEL_CATEGORY = {
    "driver": "drivers", "activity": "activities", "pressure": "pressures",
    "state": "marine_processes", "impact": "ecosystem_services",
    "welfare": "goods_benefits", "response": "responses", "measure": "measures",
}

_ELEMENT_COLUMNS = {"id", "name", "description"}   # `type` -> r_extra["r_type"]
_POLARITIES = ("+", "-")
_STRENGTHS = ("weak", "medium", "strong")
_META_KEYS = ("version", "created_date", "source", "applicable_regions")


@dataclass(frozen=True)
class ConversionReport:
    key: str
    counts_by_type: dict[str, int]
    link_count: int
    folded_measures: tuple[str, ...]              # element ids
    off_rule_links: tuple[tuple[str, str], ...]
    type_mismatches: tuple[str, ...]              # from_type/to_type vs category
    extra_fields: tuple[str, ...]                 # R field names moved into r_extra
    template_meta: dict[str, Any]


def load_r_template(path: Path | str) -> dict:
    """Read an R template file. utf-8-sig tolerates a BOM; CRLF is harmless
    to json.loads."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _optional(c: dict, field: str, default: Any) -> Any:
    v = c.get(field)
    return default if v is None else v      # absent or JSON null -> R default


def convert_r_template(raw: dict, *, key: str) -> tuple[Project, ConversionReport]:
    """Convert one parsed R template. Raises ValueError (naming `key` and the
    offending item) on: the legacy `elements` + `template_info` format, a
    category that is not a list, an element without id or name, a duplicate
    element id, a dangling connection endpoint, a self-loop, a duplicate
    (from_id, to_id) pair, `connections` present but not a list, a
    connection that is not an object, or a present-but-invalid polarity,
    strength, confidence or description. Element ids and connection
    endpoints are compared as strings, so integer ids (including 0) match."""
    if "dapsiwrm_framework" not in raw and ("elements" in raw or "template_info" in raw):
        raise ValueError(f"{key}: unsupported legacy R template format")
    fw = raw.get("dapsiwrm_framework")
    if not isinstance(fw, dict):
        raise ValueError(f"{key}: dapsiwrm_framework must be an object")

    elements: list[Element] = []
    category_of: dict[str, str] = {}
    counts: dict[str, int] = {}
    folded: list[str] = []
    extras: set[str] = set()
    for cat, alias, sespy_type in _CATEGORIES:
        items = fw.get(cat)
        if items is None and alias is not None:
            items = fw.get(alias)          # canonical key wins, as R's %||%
        if items is None:
            continue
        if not isinstance(items, list):
            raise ValueError(f"{key}: category {cat!r} is not a list")
        for i, item in enumerate(items):
            if (not isinstance(item, dict) or item.get("id") in (None, "")
                    or not item.get("name")):
                raise ValueError(f"{key}: {cat}[{i}] has no id or name")
            eid = str(item["id"])
            if eid in category_of:
                raise ValueError(f"{key}: duplicate element id {eid!r}")
            r_extra: dict[str, Any] = {}
            indicator = ""
            if item.get("type") is not None:      # only when the element has one
                r_extra["r_type"] = item["type"]
                extras.add("type")
            for f, v in item.items():
                if f == "indicator":
                    # P1b (spec §5(b)): R's `indicator` has a field since
                    # schema v8 (R ISA_INDICATOR_COLUMNS, constants.R:855);
                    # `baseline` and every other extra stay in r_extra.
                    indicator = indicator_text(v)
                elif f not in _ELEMENT_COLUMNS and f != "type":
                    r_extra[f] = v
                    extras.add(f)
            if cat == "measures":
                r_extra["r_kind"] = "measure"
                folded.append(eid)
            category_of[eid] = cat
            counts[sespy_type] = counts.get(sespy_type, 0) + 1
            desc = item.get("description")
            elements.append(Element(
                id=eid, label=str(item["name"]),
                type=sespy_type,
                description="" if desc is None else str(desc),
                confidence=3,
                r_extra=r_extra,
                indicator=indicator,
            ))

    type_of = {e.id: e.type for e in elements}
    connections: list[Connection] = []
    seen: set[tuple[str, str]] = set()
    off_rule: list[tuple[str, str]] = []
    mismatches: list[str] = []
    raw_connections = raw.get("connections")
    if raw_connections is None:                 # absent or null: R's %||% list()
        raw_connections = []
    elif not isinstance(raw_connections, list):
        raise ValueError(f"{key}: connections must be a list")
    for i, c in enumerate(raw_connections):
        if not isinstance(c, dict):
            raise ValueError(f"{key}: connections[{i}] is not an object")
        src, tgt = c.get("from_id"), c.get("to_id")
        src = None if src is None else str(src)     # integer ids match str() ids
        tgt = None if tgt is None else str(tgt)
        where = f"{key}: connections[{i}] {src}->{tgt}"
        for end in (src, tgt):
            if end not in category_of:
                raise ValueError(f"{where}: unknown element id {end!r}")
        if src == tgt:
            raise ValueError(f"{where}: self-loop")
        if (src, tgt) in seen:
            raise ValueError(f"{where}: duplicate link")
        seen.add((src, tgt))

        polarity = _optional(c, "polarity", "+")
        if polarity not in _POLARITIES:
            raise ValueError(f"{where}: invalid polarity {polarity!r}")
        strength = _optional(c, "strength", "medium")
        if strength not in _STRENGTHS:
            raise ValueError(f"{where}: invalid strength {strength!r}")
        confidence = _optional(c, "confidence", 3)
        if isinstance(confidence, bool) or not isinstance(confidence, int):
            raise ValueError(f"{where}: invalid confidence {confidence!r}")
        description = _optional(c, "description", "")
        if not isinstance(description, str):
            raise ValueError(f"{where}: invalid description {description!r}")

        for side, end in (("from_type", src), ("to_type", tgt)):
            label = c.get(side)
            if label is not None and _LABEL_CATEGORY.get(label) != category_of[end]:
                mismatches.append(
                    f"connections[{i}] {src}->{tgt}: {side} {label!r} "
                    f"vs category {category_of[end]!r}")
        if classify(type_of[src], type_of[tgt]) == "off_rule":
            off_rule.append((src, tgt))
        connections.append(Connection(
            source=src, target=tgt, polarity=polarity, strength=strength,
            confidence=min(5, max(1, confidence)), delay="immediate",
            description=description,
        ))

    meta_raw = raw.get("metadata") or {}
    regional = raw.get("regional_context")
    created = meta_raw.get("created_date") or ""
    regional_sea = ""
    if isinstance(regional, dict) and regional.get("regional_sea"):
        regional_sea = str(regional["regional_sea"])   # absent in Caribbean
    metadata = ProjectMetadata(
        name=raw.get("template_name") or key,
        description=raw.get("template_description") or "",
        regional_sea=regional_sea,
        created_at=created,
        modified_at=created,
        origin="r_template",
        r_template_version=str(meta_raw.get("version") or ""),
    )
    template_meta: dict[str, Any] = {}
    for k in ("complexity", "usage_notes"):
        if k in raw:
            template_meta[k] = raw[k]
    for k in _META_KEYS:
        if k in meta_raw:
            template_meta[k] = meta_raw[k]
    if regional is not None:
        template_meta["regional_context"] = regional

    report = ConversionReport(
        key=key,
        counts_by_type=counts,
        link_count=len(connections),
        folded_measures=tuple(folded),
        off_rule_links=tuple(off_rule),
        type_mismatches=tuple(mismatches),
        extra_fields=tuple(sorted(extras)),
        template_meta=template_meta,
    )
    return Project(metadata, IsaData(elements, connections)), report
