"""Connection scoring backend for the AI-ISA wizard (SP3).

Pure-Python rule-based scoring across all 11 DAPSI(W)R(M) connection
types. Loads a keyword JSON eagerly at module import; exposes
suggest_connections(state) as the SP3 contract — same signature as
SP1's stub, replacing it via sespy/wizard.py.

R source-of-truth: ../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/
connection_generator.R (1009 LOC; SP3 ports lines 62-187, 198-226,
264-323, 338-387, 436-574, 755-1001 with KB-lookup and ML branches
dropped per scope).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from . import r_connection_kb as r_kb  # noqa: E402
from .r_kb import VENDORED as _R_VENDORED  # noqa: E402
from .data_structure import (
    _CONN_TYPES,  # re-exported for SP3-era tests
    ELEMENT_TYPE_MAP,  # post-Task-2 home (data_structure.py)
    ConnectionSuggestion,
    Element,
    WizardState,
)

_KW_PATH = Path(__file__).parent / "connection_keywords.json"
_logger = logging.getLogger(__name__)


def _load_keywords() -> dict[str, Any]:
    """Read and parse the keyword JSON. Called once at module import."""
    with _KW_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_KW = _load_keywords()
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


def calculate_relevance(
    from_name: str, to_name: str, from_slug: str, to_slug: str
) -> float:
    """Return one of {0.3, 0.6, 0.9} based on keyword-substring-match
    count across both names (0 matches → 0.3 floor, 1 → 0.6, 2+ → 0.9).
    Returns 0.5 if the (from_slug, to_slug) pair is missing from the
    keyword JSON (R line 376). That is the normal path for responses_states
    (R->MPF): R has no keywords for it and scores it at a flat 0.5, so the
    keyword JSON deliberately has no responses_states key (10 keys for the
    11 pairs).

    Slug params are lowercase (e.g., "drivers", "states"), NOT human
    Element.type strings.

    Direct port of R's .calculate_basic_relevance at
    connection_generator.R:338-387.
    """
    key = f"{from_slug}_{to_slug}"
    keywords = _KW["connection_types"].get(key)
    if keywords is None:
        return 0.5

    from_lower = from_name.lower()
    to_lower = to_name.lower()
    from_matches = sum(
        1 for kw in keywords if re.search(re.escape(kw), from_lower)
    )
    to_matches = sum(
        1 for kw in keywords if re.search(re.escape(kw), to_lower)
    )
    total_matches = from_matches + to_matches

    if total_matches == 0:
        return 0.3
    if total_matches == 1:
        return 0.6
    return 0.9


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


def _generate_smart_connections(
    from_elements: list[Element],
    to_elements: list[Element],
    from_slug: str,
    to_slug: str,
    max_count: int = _MAX_PER_TYPE,
    min_relevance: float = _MIN_RELEVANCE,
) -> list[ConnectionSuggestion]:
    """Per-type pair generator. Cross-product, threshold filter,
    double-negative filter, sort desc by confidence, cap at max_count.

    Direct port of R's generate_smart_connections at
    connection_generator.R:436-574 (KB and ML branches dropped per
    scope). Verb is derived per-pair via _select_verb(from_slug,
    polarity) -- NOT a parameter, because verb is polarity-aware and
    polarity varies per pair.

    Note: the conn_type_key (f"{from_slug}_{to_slug}") is reproducible
    from from_slug+to_slug and is used internally by calculate_relevance
    via the same construction. Not passed as a separate parameter.

    The double-negative filter uses _KW["polarity_signals"]
    ["loss_keywords"] (specific decline/loss vocabulary), NOT
    "negative_keywords" (broader, includes pollutants like 'pollut',
    'contaminat'). The two sets overlap but are distinct in R.
    """
    loss_keywords = _KW["polarity_signals"]["loss_keywords"]
    candidates: list[ConnectionSuggestion] = []

    for from_el in from_elements:
        for to_el in to_elements:
            relevance = calculate_relevance(
                from_el.label, to_el.label, from_slug, to_slug
            )
            # Threshold gate (R uses >= at line 452; vacuous given 0.3 floor
            # but pinned by test_pair_with_relevance_exactly_03_survives).
            if relevance < min_relevance:
                continue

            # Double-negative filter (R lines 440-463).
            from_lower = from_el.label.lower()
            to_lower = to_el.label.lower()
            from_is_loss = any(
                re.search(re.escape(kw), from_lower) for kw in loss_keywords
            )
            to_is_loss = any(
                re.search(re.escape(kw), to_lower) for kw in loss_keywords
            )
            if from_is_loss and to_is_loss:
                continue

            db = _R_VENDORED.connection_db()
            polarity = detect_polarity(
                from_el.label, to_el.label, from_slug, to_slug, db
            )
            kb = r_kb.lookup_knowledge_base(
                from_el.label, from_slug, to_el.label, to_slug, db
            )
            strength = kb.strength if kb is not None else "medium"
            confidence = 4 if kb is not None and kb.match_quality == "exact" else 3
            verb = _select_verb(from_slug, polarity)
            candidates.append(ConnectionSuggestion(
                source=from_el.id,
                target=to_el.id,
                polarity=polarity,
                relevance=relevance,
                rationale=f"{from_el.label} {verb} {to_el.label}",
                strength=strength,
                confidence=confidence,
            ))

    # Sort desc by confidence (stable -- preserves cross-product order on ties).
    candidates.sort(key=lambda s: s.relevance, reverse=True)
    return candidates[:max_count]


def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """SP3 contract: rule-based scoring across all 11 connection types.
    Same signature as SP1's stub at sespy/wizard.py:92.

    Top-level orchestrator (R lines 755-1001; constants MAX_PER_TYPE=15
    and MIN_RELEVANCE=0.3 at R 757-758). KB-seed and ML-scoring
    branches dropped per rule-based-only scope.

    Returns a flat list of <=165 (11 types x 15 cap) ConnectionSuggestions
    sorted globally by source group order (per _CONN_TYPES iteration)
    and within each group by confidence descending.
    """
    # 1. Group state.elements by type using _TYPE_TO_SLUG.
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

    # 2. For each of the 11 connection-type pairs, generate suggestions.
    # _CONN_TYPES is a 3-tuple list (from_slug, to_slug, conn_type_key);
    # we destructure the 3rd field but don't pass it -- calculate_relevance
    # rebuilds the conn_type_key from (from_slug, to_slug) internally.
    out: list[ConnectionSuggestion] = []
    for from_slug, to_slug, _conn_type_key in _CONN_TYPES:
        from_list = grouped[from_slug]
        to_list = grouped[to_slug]
        if not from_list or not to_list:
            continue  # cross-product would be empty anyway
        out.extend(_generate_smart_connections(
            from_list, to_list, from_slug, to_slug
        ))

    return out
