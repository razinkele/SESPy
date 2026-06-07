"""ISA data model — minimal port of functions/data_structure.R.

The R app keeps project state in a nested reactiveVal. Here the same shape is
expressed as a dataclass tree. The JSON on-disk schema matches the R version,
so existing project files would load (subject to camelCase/snake_case fixups).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields, replace as _dc_replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

_log = logging.getLogger(__name__)

PROJECT_SCHEMA_VERSION = 5


# ---------------------------------------------------------------------------
# Wizard target → SESPy Element.type mapping for steps 4-10.
#
# Authoritative source for the wizard-target → element-type relationship.
# The id prefixes in sespy/constants.py::ELEMENT_ID_PREFIX encode the same
# relationship via the id prefix (impacts→ES→Ecosystem Services,
# welfare→GB→Goods & Benefits).
#
# Lives in data_structure.py (not wizard.py) so sespy/connection_scorer.py
# can import it without creating a cycle: wizard.py imports
# connection_scorer.py for suggest_connections, and connection_scorer.py
# needs the element-type → slug mapping. Anchoring the constant here
# (alongside the Element.type strings it references) gives a linear
# import graph: data_structure → (stdlib only); wizard → data_structure,
# regional_seas, connection_scorer; connection_scorer → data_structure.
#
# Re-exported from sespy/wizard.py for SP1 caller compatibility.
# ---------------------------------------------------------------------------

ELEMENT_TYPE_MAP: dict[str, str] = {
    "drivers": "Drivers",
    "activities": "Activities",
    "pressures": "Pressures",
    "states": "Marine Processes & Functioning",
    "impacts": "Ecosystem Services",
    "welfare": "Goods & Benefits",
    "responses": "Responses",
}

# ---------------------------------------------------------------------------
# DAPSI(W)R(M) connection-type topology — single source of truth for both
# the SP3 rule-based scorer (`connection_scorer.py`) and the SP4 Claude API
# backend (`claude_backend.py`). Co-located with ELEMENT_TYPE_MAP because
# this IS data structure (defines the framework's directed-graph topology).
# ---------------------------------------------------------------------------

Slug = Literal[
    "drivers", "activities", "pressures", "states",
    "impacts", "welfare", "responses",
]

# 10 type-pairs as (from_slug, to_slug, conn_type_key) 3-tuples.
# Iteration order matches DAPSI(W)R(M) layer flow.
_CONN_TYPES: list[tuple[Slug, Slug, str]] = [
    ("drivers", "activities", "drivers_activities"),
    ("activities", "pressures", "activities_pressures"),
    ("pressures", "states", "pressures_states"),
    ("states", "impacts", "states_impacts"),
    ("impacts", "welfare", "impacts_welfare"),
    ("responses", "pressures", "responses_pressures"),
    ("responses", "drivers", "responses_drivers"),
    ("responses", "activities", "responses_activities"),
    ("welfare", "drivers", "welfare_drivers"),
    ("welfare", "responses", "welfare_responses"),
]

# 2-tuple projection of _CONN_TYPES — used by validation pipelines for
# O(1) membership testing of model-emitted (from, to) pairs.
_VALID_TYPE_PAIRS: frozenset[tuple[Slug, Slug]] = frozenset(
    (from_slug, to_slug) for from_slug, to_slug, _key in _CONN_TYPES
)


@dataclass
class Element:
    id: str
    label: str
    type: str  # one of DAPSIWRM_ELEMENTS
    description: str = ""
    confidence: int = 3


@dataclass
class Connection:
    source: str  # element id
    target: str  # element id
    polarity: str = "+"  # "+" reinforcing, "-" opposing
    strength: str = "medium"  # weak | medium | strong
    confidence: int = 3
    delay: str = "immediate"


@dataclass
class IsaData:
    elements: list[Element] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)

    def element_count(self) -> int:
        return len(self.elements)

    def connection_count(self) -> int:
        return len(self.connections)

    def elements_by_type(self) -> dict[str, list[Element]]:
        out: dict[str, list[Element]] = {}
        for el in self.elements:
            out.setdefault(el.type, []).append(el)
        return out


def load_sample(path: Path | str) -> IsaData:
    """Load an ISA dataset from a JSON file shaped like the R app's exports."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return _isa_from_dict(raw)


def _isa_from_dict(raw: dict[str, Any]) -> IsaData:
    elements = [Element(**e) for e in raw.get("elements", [])]
    connections = [Connection(**c) for c in raw.get("connections", [])]
    return IsaData(elements=elements, connections=connections)


def empty() -> IsaData:
    return IsaData()


# ---------------------------------------------------------------------------
# Project envelope — wraps IsaData with metadata so the on-disk file is
# round-trippable, version-tagged, and forward-compatible. Mirrors the R
# app's project shape (functions/data_structure.R::init_session_data) but
# only the fields we actually use yet.
# ---------------------------------------------------------------------------

@dataclass
class ProjectMetadata:
    name: str = "Untitled Project"
    description: str = ""
    da_site: str = ""
    regional_sea: str = ""
    ecosystem_type: str = ""
    # PIMS Project Setup fields (added with schema v2).
    focal_issue: str = ""
    definition_statement: str = ""
    temporal_scale: str = ""
    spatial_scale: str = ""
    system_in_focus: str = ""
    created_at: str = ""
    modified_at: str = ""
    schema_version: int = PROJECT_SCHEMA_VERSION

    @staticmethod
    def new(name: str = "Untitled Project") -> "ProjectMetadata":
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return ProjectMetadata(name=name, created_at=now, modified_at=now)


@dataclass
class Stakeholder:
    """A single PIMS stakeholder. Ported from pims_stakeholder_module.R.

    Controlled-vocabulary fields store canonical CODE strings (see
    sespy/modules/pims_stakeholders.py for the code->label maps), not the
    translated label — codes are i18n-stable. `created_at` mirrors R's
    DateAdded.
    """
    id: str
    name: str
    stakeholder_type: str = ""
    sector: str = ""
    contact: str = ""
    interests: str = ""
    role: str = ""
    power: str = ""            # "HIGH" | "MEDIUM" | "LOW" | ""
    interest: str = ""         # "HIGH" | "MEDIUM" | "LOW" | ""
    attitude: str = ""
    engagement_level: str = ""
    created_at: str = ""


@dataclass
class Engagement:
    """A planned/completed engagement activity for one stakeholder.

    Ported from pims_stakeholder_module.R Tab 3 (add_engagement ~639-650).
    References a `Stakeholder` by id (no denormalized name — resolved at render
    time so it never goes stale on rename).
    """
    id: str
    stakeholder_id: str
    method: str = ""
    date: str = ""
    objectives: str = ""
    outcomes: str = ""
    status: str = "planned"
    facilitator: str = ""
    created_at: str = ""


@dataclass
class Communication:
    """A planned/tracked stakeholder communication item.

    Ported from pims_stakeholder_module.R Tab 4 (add_communication ~677-686).
    `audience` is a category code (not a Stakeholder FK).
    """
    id: str
    audience: str = ""
    comm_type: str = ""
    date: str = ""
    frequency: str = "one_time"
    message: str = ""
    responsible: str = ""
    created_at: str = ""


@dataclass
class Project:
    """A complete saveable project: metadata + ISA data."""
    metadata: ProjectMetadata
    isa_data: IsaData
    stakeholders: list["Stakeholder"] = field(default_factory=list)
    engagements: list["Engagement"] = field(default_factory=list)
    communications: list["Communication"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": asdict(self.metadata),
            "isa_data": {
                "elements": [asdict(e) for e in self.isa_data.elements],
                "connections": [asdict(c) for c in self.isa_data.connections],
            },
            "stakeholders": [asdict(s) for s in self.stakeholders],
            "engagements": [asdict(e) for e in self.engagements],
            "communications": [asdict(c) for c in self.communications],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Project":
        meta_raw = raw.get("metadata", {}) or {}
        valid_keys = {f.name for f in fields(ProjectMetadata)}
        meta_filtered = {k: v for k, v in meta_raw.items() if k in valid_keys}
        dropped = sorted(set(meta_raw.keys()) - valid_keys)
        if dropped:
            _log.warning(
                "Project metadata had unknown keys (dropped): %s", dropped
            )
        meta = ProjectMetadata(**meta_filtered)
        isa = _isa_from_dict(raw.get("isa_data", raw))  # tolerate flat shapes
        sh_keys = {f.name for f in fields(Stakeholder)}
        stakeholders = [
            Stakeholder(**{k: v for k, v in s.items() if k in sh_keys})
            for s in (raw.get("stakeholders") or [])
        ]
        eng_keys = {f.name for f in fields(Engagement)}
        engagements = [
            Engagement(**{k: v for k, v in e.items() if k in eng_keys})
            for e in (raw.get("engagements") or [])
        ]
        comm_keys = {f.name for f in fields(Communication)}
        communications = [
            Communication(**{k: v for k, v in c.items() if k in comm_keys})
            for c in (raw.get("communications") or [])
        ]
        meta.schema_version = PROJECT_SCHEMA_VERSION   # upgrade-on-load (no down-convert)
        return cls(
            metadata=meta,
            isa_data=isa,
            stakeholders=stakeholders,
            engagements=engagements,
            communications=communications,
        )

    @classmethod
    def from_json(cls, text: str) -> "Project":
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_isa(cls, isa: IsaData, *, name: str = "Untitled Project") -> "Project":
        return cls(metadata=ProjectMetadata.new(name), isa_data=isa)

    def replace(self, **changes: Any) -> "Project":
        """Return a copy with `changes` applied, preserving all other fields
        (incl. stakeholders). Use this for every partial Project edit instead
        of `Project(metadata=…, isa_data=…)`, which silently drops new fields."""
        return _dc_replace(self, **changes)

    def with_modified_now(self) -> "Project":
        meta = ProjectMetadata(
            **{**asdict(self.metadata),
               "modified_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        )
        return self.replace(metadata=meta)


def to_visnetwork(
    isa: IsaData,
    *,
    size_scale: float = 1.0,
    font_scale: float = 1.0,
) -> dict[str, list[dict]]:
    """Project ISA data into the {nodes, edges} payload that vis.js expects.

    Each node carries an explicit DAPSIWRM `level` so vis.js's hierarchical
    layout puts elements on the right rows. Mirrors
    functions/visnetwork_helpers.R::create_nodes_df — without explicit levels
    the directed-sort algorithm picks roots heuristically and the visual
    flow drifts.

    size_scale: multiplier on per-type node size and label-wrap width.
    font_scale: separate multiplier on label font size — independent so the
                user can crank labels up without making the shapes bigger.
    """
    from .constants import (
        CONFIDENCE_OPACITY,
        DAPSIWRM_FONT_SIZE,
        DAPSIWRM_LABEL_WIDTH,
        DAPSIWRM_LEVEL,
        DAPSIWRM_NODE_SIZE,
        DEFAULT_GROUP_COLOR,
        DEFAULT_GROUP_SHAPE,
        EDGE_COLORS,
        ELEMENT_COLORS,
        ELEMENT_SHAPES,
    )

    label_max = max(60, int(DAPSIWRM_LABEL_WIDTH * size_scale))

    nodes = []
    for el in isa.elements:
        base_size = DAPSIWRM_NODE_SIZE.get(el.type, 80)
        base_font = DAPSIWRM_FONT_SIZE.get(el.type, 24)
        nodes.append(
            {
                "id": el.id,
                "label": el.label,
                "group": el.type,
                "color": ELEMENT_COLORS.get(el.type, DEFAULT_GROUP_COLOR),
                "shape": ELEMENT_SHAPES.get(el.type, DEFAULT_GROUP_SHAPE),
                "title": f"{el.type}: {el.label}",
                "level": DAPSIWRM_LEVEL.get(el.type, 3),
                "size": max(15, int(base_size * size_scale)),
                "font": {
                    "size": max(8, int(base_font * font_scale)),
                    "multi": "html",
                },
                "widthConstraint": {"maximum": label_max},
            }
        )

    edges = [
        {
            "from": c.source,
            "to": c.target,
            "color": {
                "color": EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
                "opacity": CONFIDENCE_OPACITY.get(c.confidence, 0.7),
            },
            "arrows": "to",
            "label": c.polarity,
            "smooth": {"type": "curvedCW", "roundness": 0.15},
        }
        for c in isa.connections
    ]
    return {"nodes": nodes, "edges": edges}


def filter_elements(isa: IsaData, types: Iterable[str]) -> IsaData:
    """Return a new IsaData restricted to the given element types."""
    keep_types = set(types)
    kept_elements = [e for e in isa.elements if e.type in keep_types]
    kept_ids = {e.id for e in kept_elements}
    kept_connections = [
        c for c in isa.connections if c.source in kept_ids and c.target in kept_ids
    ]
    return IsaData(elements=kept_elements, connections=kept_connections)


# ---------------------------------------------------------------------------
# AI-ISA Wizard contract types (added with SP1).
#
# WizardState is constructed at step-11 entry from wizard_answers + the
# current project_data and passed to suggest_connections(). SP3 (TF-IDF)
# and SP4 (Claude API) consume it as a frozen snapshot.
#
# ConnectionSuggestion is what suggest_connections() returns. It mirrors
# Connection's source/target/polarity but adds confidence (float 0..1) and
# rationale (free-text). SP3/SP4 must define the float→int confidence
# mapping when converting accepted suggestions to Connection objects (see
# spec §9).
# ---------------------------------------------------------------------------


@dataclass
class WizardState:
    """Snapshot of the wizard's accumulated context at the moment
    suggest_connections() is invoked. Holds the current SES element list
    plus the wizard-only ephemeral fields (countries, main_issue) that
    don't persist to the project file."""
    regional_sea: str = ""
    ecosystem_type: str = ""
    countries: list[str] = field(default_factory=list)
    main_issue: list[str] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)


@dataclass
class ConnectionSuggestion:
    """One suggested connection from a scoring backend (SP3 or SP4).
    SP1 returns an empty list of these from the stub."""
    source: str  # element id
    target: str  # element id
    polarity: str  # "+" reinforcing, "-" opposing
    confidence: float  # 0..1
    rationale: str  # short string explaining the suggestion
