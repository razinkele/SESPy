"""Connection scoring backend for the AI-ISA wizard.

Rule-based scorer: an exact port of R v1.35.6 generate_connections (ML off)
on R's 10 type pairs (connection_generator.R:62-187, 198-226, 436-574,
755-1001; relevance and KB lookup live in r_connection_kb). Exposes
suggest_connections(state, snapshot=None), re-exported by sespy/wizard.py.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from . import r_connection_kb as r_kb
from .data_structure import (
    _CONN_TYPES,  # noqa: F401  re-exported for SP3-era tests
    ELEMENT_TYPE_MAP,  # post-Task-2 home (data_structure.py)
    ConnectionSuggestion,
    Element,
    WizardState,
)
from .r_kb import VENDORED as _R_VENDORED

if TYPE_CHECKING:
    from .r_kb import Snapshot

_logger = logging.getLogger(__name__)

_TYPE_TO_SLUG = {v: k for k, v in ELEMENT_TYPE_MAP.items()}
# {"Drivers": "drivers", "Activities": "activities", ...,
#  "Marine Processes & Functioning": "states", "Ecosystem Services": "impacts",
#  "Goods & Benefits": "welfare", "Responses": "responses"}

_MAX_PER_TYPE = 15
_MIN_RELEVANCE = 0.3

# R's analyze_phrase_polarity tables (ses_connection_knowledge_base.R:1363-1435),
# 28 reversal compounds and 19 negation patterns, PCRE -> Python re.
_REVERSAL_COMPOUNDS: list[str] = [
    r"pollut.*reduc", r"pollut.*remov", r"pollut.*control",
    r"emission.*reduc", r"emission.*control", r"emission.*limit",
    r"pressure.*reduc", r"stress.*reduc", r"risk.*reduc",
    r"litter.*reduc", r"litter.*remov", r"litter.*clean",
    r"waste.*reduc", r"waste.*treat", r"waste.*remov",
    r"erosion.*control", r"erosion.*prevent",
    r"noise.*reduc", r"noise.*control",
    r"overfish.*prevent", r"overfish.*reduc",
    r"deforest.*prevent", r"habitat.*loss.*prevent",
    r"decline.*halt", r"decline.*revers",
    r"degradat.*halt", r"degradat.*revers",
]

_NEGATION_PATTERNS: list[str] = [
    r"\bno\b", r"\bnot\b", r"\bnon[- ]", r"\bwithout\b",
    r"\bprevent", r"\bprohibit", r"\bban\b", r"\bbanned\b",
    r"\breduc", r"\bremov", r"\belimin", r"\bavoid",
    r"\bcontrol", r"\blimit", r"\brestrict", r"\bstop",
    r"\bless\b", r"\black\b", r"\babsence\b",
]

_PHRASE_POSITIVE_KW = ("increas", "improv", "enhanc", "restor", "recover",
                       "growth", "benefit", "gain", "protect", "conserv",
                       "sustain", "resilient", "healthy", "abundant")
_PHRASE_NEGATIVE_KW = ("declin", "loss", "degrad", "damag", "destruct",
                       "pollut", "contamin", "overfish", "erosion",
                       "deplet", "collapse", "extinct", "harm",
                       "bleach", "hypox", "mortality")

# R's detect_polarity keyword lists (connection_generator.R:86-105).
_NEGATIVE_KEYWORDS = (
    "declin", "degrad", "loss", "reduc", "damag", "destruct", "pollut",
    "eutrophic", "overfish", "bycatch", "invasive", "extinct", "harm",
    "contaminat", "erosion", "acidific", "hypox", "dead zone", "bleach",
    "disease", "mortality", "collapse", "fragment", "depletion",
)
_POSITIVE_KEYWORDS = (
    "increas", "growth", "restor", "recover", "improv", "enhanc", "protect",
    "conserv", "benefit", "health", "sustain", "resilient", "biodiver",
    "abundance", "productiv", "regenerat", "rehabilit", "rebui",
)
_MITIGATION_KEYWORDS = (
    "ban", "prohibit", "restrict", "limit", "regulat", "control", "manag",
    "reduce", "prevent", "mitigat", "protect", "enforce", "monitor",
    "stop", "remov", "clean", "treat",
)


def _any_match(patterns, text: str) -> bool:
    return any(
        re.search(p, text, re.ASCII if r"\b" in p else 0) for p in patterns
    )


def _analyze_polarity_phrase(name_lower: str) -> tuple[str, bool]:
    """Return (sentiment, negated); port of R's analyze_phrase_polarity
    (ses_connection_knowledge_base.R:1363-1435), which R's
    .analyze_polarity_phrase delegates to (the inline fallback is dead)."""
    if _any_match(_REVERSAL_COMPOUNDS, name_lower):
        return ("positive", True)
    has_negation = _any_match(_NEGATION_PATTERNS, name_lower)
    has_pos = _any_match(_PHRASE_POSITIVE_KW, name_lower)
    has_neg = _any_match(_PHRASE_NEGATIVE_KW, name_lower)
    if has_pos and not has_neg:
        base = "positive"
    elif has_neg and not has_pos:
        base = "negative"
    elif has_pos and has_neg:
        base = "mixed"
    else:
        base = "neutral"
    if has_negation and base == "positive":
        return ("negative", True)
    if has_negation and base == "negative":
        return ("positive", True)
    return (base, has_negation)


def detect_polarity(from_name: str, to_name: str, from_type: str,
                    to_type: str, db: dict) -> str:
    """Port of R's detect_polarity (connection_generator.R:62-187): the KB
    entry's polarity when lookup_knowledge_base matches, else R's rules.
    Types are R's plural slugs."""
    kb = r_kb.lookup_knowledge_base(from_name, from_type, to_name, to_type, db)
    return _polarity_from_match(kb, from_name, to_name, from_type, to_type)


def _polarity_from_match(kb, from_name: str, to_name: str, from_type: str,
                         to_type: str) -> str:
    """detect_polarity given the caller's precomputed KB lookup result."""
    if kb is not None and kb.polarity is not None:
        return kb.polarity

    from_lower = from_name.lower()
    to_lower = to_name.lower()
    from_analysis = _analyze_polarity_phrase(from_lower)
    to_analysis = _analyze_polarity_phrase(to_lower)

    to_is_negative = _any_match(_NEGATIVE_KEYWORDS, to_lower)
    to_is_positive = _any_match(_POSITIVE_KEYWORDS, to_lower)
    from_is_mitigation = _any_match(_MITIGATION_KEYWORDS, from_lower)

    if from_type == "responses" and to_type == "pressures":
        return "-"
    if from_type == "responses" and to_type == "states":
        if to_is_negative:
            return "-"
        if to_is_positive:
            return "+"
        return "+"
    if from_type == "activities" and to_type == "pressures":
        if from_is_mitigation or from_analysis[0] == "positive":
            return "-"
        return "+"
    if from_type == "pressures" and to_type == "states":
        if to_is_negative:
            return "+"
        if to_is_positive:
            return "-"
        return "-"
    if from_type == "states" and to_type == "impacts":
        from_is_negative = _any_match(_NEGATIVE_KEYWORDS, from_lower)
        from_is_positive = _any_match(_POSITIVE_KEYWORDS, from_lower)
        if from_analysis[1] and from_is_negative:
            from_is_negative = False
        if to_analysis[1] and to_is_negative:
            to_is_negative = False
        if (from_is_negative and to_is_negative) or (
                from_is_positive and to_is_positive):
            return "+"
        if (from_is_negative and to_is_positive) or (
                from_is_positive and to_is_negative):
            return "-"
        return "-"
    if from_type == "impacts" and to_type == "welfare":
        from_is_negative = _any_match(_NEGATIVE_KEYWORDS, from_lower)
        from_is_positive = _any_match(_POSITIVE_KEYWORDS, from_lower)
        if from_analysis[1] and from_is_negative:
            from_is_negative = False
        if from_is_negative:
            return "-"
        if from_is_positive:
            return "+"
        return "-"
    return "+"


def _select_verb(from_slug: str, polarity: str) -> str:
    """Verb for the rationale string, polarity-aware for some types.
    Matches R's verb selection at connection_generator.R:513-529.

        drivers     -> "drives"                (polarity-insensitive)
        activities  -> "increases" (+) | "causes" (-)
        pressures   -> "increases" (+) | "decreases" (-)
        states      -> "impacts"               (polarity-insensitive)
        impacts     -> "increases" (+) | "reduces" (-)
        responses   -> "enables" (+)   | "restricts" (-)
        welfare     -> "motivates" (+) | "reduces" (-)
        default     -> "affects positively" (+) | "affects negatively" (-)

    The default branch is unreachable from _CONN_TYPES' 7 from-slugs
    (the test parameterization runs only the 7x2=14 valid cases) but
    is included for forward-compat with future Element-type additions.
    """
    if from_slug == "drivers":
        return "drives"
    if from_slug == "activities":
        return "increases" if polarity == "+" else "causes"
    if from_slug == "pressures":
        return "increases" if polarity == "+" else "decreases"
    if from_slug == "states":
        return "impacts"
    if from_slug == "impacts":
        return "increases" if polarity == "+" else "reduces"
    if from_slug == "responses":
        return "enables" if polarity == "+" else "restricts"
    if from_slug == "welfare":
        return "motivates" if polarity == "+" else "reduces"
    # Default fallback for forward-compat
    return "affects positively" if polarity == "+" else "affects negatively"


# R's generate_connections block order (connection_generator.R:922-993).
R_CONNECTION_PAIRS: tuple[tuple[str, str], ...] = (
    ("drivers", "activities"), ("activities", "pressures"),
    ("pressures", "states"), ("states", "impacts"), ("impacts", "welfare"),
    ("responses", "pressures"), ("welfare", "drivers"),
    ("welfare", "responses"), ("responses", "drivers"),
    ("responses", "activities"),
)

# R's double-negative filter list (connection_generator.R:440-444).
_LOSS_KEYWORDS = (
    "loss", "decline", "declin", "degrad", "reduc", "damag", "destruct",
    "decreas", "diminish", "deplet", "erosion", "collapse", "extinct",
    "mortality", "death", "disappear", "absent", "lack", "scarcity",
)
_LOSS_RX = re.compile("|".join(_LOSS_KEYWORDS))


def _is_loss(lowered: str) -> bool:
    return _LOSS_RX.search(lowered) is not None


def _generate_smart_connections(
    from_elements: list[Element],
    to_elements: list[Element],
    from_slug: str,
    to_slug: str,
    max_count: int = _MAX_PER_TYPE,
    min_relevance: float = _MIN_RELEVANCE,
    db: dict | None = None,
) -> list[ConnectionSuggestion]:
    """Port of R's generate_smart_connections (connection_generator.R:436-574,
    ML off): (i, j) candidates, inclusive threshold, double-negative filter,
    one KB lookup per candidate reused for relevance, polarity, strength and
    confidence, stable descending sort by relevance, cap."""
    if db is None:
        db = _R_VENDORED.connection_db()
    from_loss = [_is_loss(e.label.lower()) for e in from_elements]
    to_loss = [_is_loss(e.label.lower()) for e in to_elements]
    # (relevance, from element, to element, KB match). Polarity, verb and
    # rationale never feed the threshold, the filter or the sort, so they are
    # built only for the survivors of the cap.
    candidates: list[tuple[float, Element, Element, r_kb.KBMatch | None]] = []

    for i, from_el in enumerate(from_elements):
        for j, to_el in enumerate(to_elements):
            kb = r_kb.lookup_knowledge_base(
                from_el.label, from_slug, to_el.label, to_slug, db)
            relevance = r_kb.calculate_enhanced_relevance(
                from_el.label, to_el.label, from_slug, to_slug, db, kb=kb)
            if relevance < min_relevance:
                continue
            if from_loss[i] and to_loss[j]:
                continue  # skipped candidates do not use the cap
            candidates.append((relevance, from_el, to_el, kb))

    candidates.sort(key=lambda c: -c[0])  # stable: ties keep (i, j) order
    out: list[ConnectionSuggestion] = []
    for relevance, from_el, to_el, kb in candidates[:max_count]:
        polarity = _polarity_from_match(
            kb, from_el.label, to_el.label, from_slug, to_slug)
        verb = _select_verb(from_slug, polarity)
        out.append(ConnectionSuggestion(
            source=from_el.id,
            target=to_el.id,
            polarity=polarity,
            relevance=relevance,
            rationale=f"{from_el.label} {verb} {to_el.label}",
            strength=kb.strength if kb is not None else "medium",
            confidence=4 if kb is not None and kb.match_quality == "exact" else 3,
        ))
    return out


def suggest_connections(state: WizardState,
                        snapshot: Snapshot | None = None) -> list[ConnectionSuggestion]:
    """R's generate_connections with ML off: the 10 pairs in R's order, at
    most 15 per pair, no cross-pair dedup. ``snapshot`` None means the
    vendored R data."""
    snap = snapshot if snapshot is not None else _R_VENDORED
    db = snap.connection_db()
    grouped: dict[str, list[Element]] = {
        slug: [] for slug in _TYPE_TO_SLUG.values()
    }
    for el in state.elements:
        slug = _TYPE_TO_SLUG.get(el.type)
        if slug is None:
            _logger.warning(
                "unknown Element.type %r for id %r; skipping",
                el.type, el.id,
            )
            continue
        grouped[slug].append(el)

    out: list[ConnectionSuggestion] = []
    for from_slug, to_slug in R_CONNECTION_PAIRS:
        from_list = grouped[from_slug]
        to_list = grouped[to_slug]
        if not from_list or not to_list:
            continue
        out.extend(_generate_smart_connections(
            from_list, to_list, from_slug, to_slug, db=db))
    return out
