"""Regional Context report content (K1).

A port of the MarineSABRES R app at v1.35.6, ``functions/kb_report_helpers.R``:
``get_kb_context_for_report`` (:42-87), ``match_user_connections_to_kb``
(:105-186), ``get_governance_context`` (:205-254) and
``format_kb_section_for_report`` (:273-369), as the report calls them
(``functions/report_generation.R:172-175``, without ``i18n``, so the headings
are English literals and the ``modules.kb_report.*`` keys are not used).

R's behaviour is reproduced exactly, quirks included. Functions take the
parsed JSON (``snapshot.kb()``, ``snapshot.governance()``) and never read the
registry. ``None`` stands for R's ``NULL``.

One deliberate difference: R pastes a newline inside a table cell verbatim,
which splits the evidence row in Markdown. ``to_markdown`` replaces line
breaks inside cells with a space so a row is always one line (spec Review
Focus 4). For text without a line break the output is R's, byte for byte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sespy.kb_suggestions import (
    _trimws,
    _unique,
    find_context,
    get_context_connections,
    get_context_elements,
)

__all__ = [
    "CATEGORY_LABELS",
    "HEADINGS",
    "EvidenceRow",
    "RegionalContext",
    "build_regional_context",
    "to_markdown",
]

#: R's ``cat_labels`` (:295-303), in category order.
CATEGORY_LABELS = {
    "drivers": "Drivers (D)",
    "activities": "Activities (A)",
    "pressures": "Pressures (P)",
    "states": "States/Components (C)",
    "impacts": "Impacts (ES)",
    "welfare": "Welfare (HW/GB)",
    "responses": "Responses (R/M)",
}

#: R's six heading texts, in document order, without the ``#`` markers
#: (R's levels are 1, 2, 3, 3, 3, 4; the HTML/Word renderers shift them).
HEADINGS = (
    "Regional Context",
    "Site Ecological Context",
    "Key DAPSI(W)R(M) Elements from Knowledge Base",
    "Scientific Evidence for Connections",
    "Relevant Governance Frameworks",
    "Country-Specific Governance Groups",
)

_MIN_RELEVANCE = 0.8


@dataclass(frozen=True)
class EvidenceRow:
    """One matched connection. Text is raw: pipes are escaped by ``to_markdown``."""

    connection: str
    rationale: str
    references: str
    temporal_lag: str
    reversibility: str


@dataclass
class RegionalContext:
    #: ``None`` when the knowledge base has no context or its description is blank.
    site_description: str | None = None
    #: ``(category key, names)`` in DAPSI(W)R(M) order; labels are ``CATEGORY_LABELS``.
    top_elements: list[tuple[str, list[str]]] = field(default_factory=list)
    evidence: list[EvidenceRow] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    #: ``(country code, governance group)`` as R prints them (raw keys).
    country_groups: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# R primitives
# ---------------------------------------------------------------------------

def _str(v) -> str:
    """R ``x %||% ""`` for a string field."""
    return "" if v is None else str(v)


def _contains(needle: str, hay: str) -> bool:
    """R ``grepl(needle, hay, fixed = TRUE)`` (an empty needle always matches)."""
    return needle in hay


def _lower(s: str) -> str:
    return s.lower()


# ---------------------------------------------------------------------------
# get_kb_context_for_report (:42-87)
# ---------------------------------------------------------------------------

def _kb_context(kb, sea, ecosystem) -> tuple[str | None, list[tuple[str, list[str]]]]:
    """``(description, top_elements)``; ``(None, [])`` when R returns available = FALSE."""
    if sea is None or ecosystem is None:
        return None, []
    # R's ses_knowledge_db_available(): loaded with contexts
    if not isinstance(kb, dict) or not kb.get("contexts"):
        return None, []
    found = find_context(kb, sea, ecosystem)
    if found is None:
        return None, []
    description = found[1].get("description")
    if description is None:
        description = f"Marine SES context for {sea} {ecosystem}"
    top: list[tuple[str, list[str]]] = []
    for cat in CATEGORY_LABELS:
        elements = get_context_elements(kb, sea, ecosystem, cat, min_relevance=_MIN_RELEVANCE)
        if elements:
            top.append((cat, elements))
    return description, top


# ---------------------------------------------------------------------------
# match_user_connections_to_kb (:105-186), matched rows only
# ---------------------------------------------------------------------------

def _match(kb, sea, ecosystem, edges) -> list[EvidenceRow]:
    if not edges:
        return []
    # The KB's own list: read only, never sorted or annotated.
    kb_connections = get_context_connections(kb, sea, ecosystem)
    rows: list[EvidenceRow] = []
    for user_from, user_to in edges:
        user_from = _str(user_from)
        user_to = _str(user_to)
        for conn in kb_connections:
            kb_from = _str(conn.get("from"))
            kb_to = _str(conn.get("to"))
            if len(kb_from) <= 2 or len(kb_to) <= 2:
                continue
            from_match = (_contains(kb_from, user_from)
                          or _contains(_lower(kb_from), _lower(user_from))
                          or _contains(_lower(user_from), _lower(kb_from)))
            to_match = (_contains(kb_to, user_to)
                        or _contains(_lower(kb_to), _lower(user_to))
                        or _contains(_lower(user_to), _lower(kb_to)))
            if from_match and to_match:
                refs = conn.get("references")
                refs = "; ".join(str(r) for r in refs) if refs else ""
                rows.append(EvidenceRow(
                    connection=f"{user_from} → {user_to}",
                    rationale=_str(conn.get("rationale")),
                    references=refs,
                    temporal_lag=_str(conn.get("temporal_lag")),
                    reversibility=_str(conn.get("reversibility")),
                ))
                break
    return rows


# ---------------------------------------------------------------------------
# get_governance_context (:205-254), called without countries
# ---------------------------------------------------------------------------

def _governance(gov, sea) -> tuple[list[str], list[tuple[str, str]]]:
    """``(frameworks, country_groups)``; empty when R's ``available`` is FALSE."""
    if not isinstance(sea, str) or len(_trimws(sea)) == 0:
        return [], []
    if not isinstance(gov, dict):
        return [], []
    codes = (gov.get("countries_by_sea") or {}).get(_trimws(sea).lower())
    if not codes:
        return [], []
    countries = gov.get("countries") or {}
    records: dict[str, dict] = {}
    for code in codes:  # R's result[[code]] <- record: a repeat keeps its first position
        rec = countries.get(code)
        if rec is not None:
            records[code] = rec
    conventions = _unique(c for r in records.values() for c in (r.get("regional_conventions") or []))
    conventions = [c for c in conventions if c is not None and len(c) > 0]
    groups: list[tuple[str, str]] = []
    for code, rec in records.items():
        grp = rec.get("governance_group")
        if grp is not None and len(grp) > 0:
            groups.append((code, grp))
    if not conventions and not groups:  # available = FALSE
        return [], []
    return conventions, groups


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_regional_context(kb, gov, sea, ecosystem, edges) -> RegionalContext | None:
    """The report's Regional Context, or None when its body would be empty.

    ``edges`` is a list of ``(from_label, to_label)`` in project order.
    """
    description, top = _kb_context(kb, sea, ecosystem)
    site = description if description is not None and len(_trimws(description)) > 0 else None
    evidence = _match(kb, sea, ecosystem, list(edges or [])) if description is not None else []
    frameworks, groups = _governance(gov, sea)
    rc = RegionalContext(site, top, evidence, frameworks, groups)
    if not _has_content(rc):
        return None
    return rc


def _has_content(rc: RegionalContext) -> bool:
    # R: sections is empty only when no heading was ever added.
    return bool(rc.site_description or rc.top_elements or rc.evidence
                or rc.frameworks or rc.country_groups)


def _cell(s: str) -> str:
    return re.sub(r"\r\n|\r|\n", " ", s)


def to_markdown(rc: RegionalContext) -> str:
    """R's ``paste0("# Regional Context\\n\\n", format_kb_section_for_report(...))``."""
    h = HEADINGS
    sections: list[str] = []
    if rc.site_description is not None:
        sections += [f"## {h[1]}", "", rc.site_description, ""]
    if rc.top_elements:
        sections += [f"### {h[2]}", ""]
        for cat, items in rc.top_elements:
            if not items:
                continue
            sections += [f"**{CATEGORY_LABELS.get(cat, cat)}**", *[f"- {i}" for i in items], ""]
    if rc.evidence:
        sections += [f"### {h[3]}", "",
                     "| Connection | Rationale | References | Temporal Lag | Reversibility |",
                     "|---|---|---|---|---|"]
        for r in rc.evidence:
            rationale = _cell(r.rationale).replace("|", "\\|")
            refs = _cell(r.references).replace("|", "\\|")
            sections.append(f"| {_cell(r.connection)} | {rationale} | {refs} | "
                            f"{_cell(r.temporal_lag)} | {_cell(r.reversibility)} |")
        sections.append("")
    if rc.frameworks:
        sections += [f"### {h[4]}", "", *[f"- {f}" for f in rc.frameworks], ""]
    if rc.country_groups:
        sections += [f"#### {h[5]}", ""]
        sections += [f"- **{code}**: {grp}" for code, grp in rc.country_groups]
        sections.append("")
    return f"# {h[0]}\n\n" + "\n".join(sections)
