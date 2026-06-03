"""Connection scoring backend for the AI-ISA wizard (SP3).

Pure-Python rule-based scoring across all 10 DAPSI(W)R(M) connection
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

from .data_structure import (
    WizardState,
    ConnectionSuggestion,
    Element,
    ELEMENT_TYPE_MAP,  # post-Task-2 home (data_structure.py)
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

# 10 connection types as (from_slug, to_slug, conn_type_key) tuples.
# Iteration order matches R's natural DAPSI(W)R(M) layer flow at
# connection_generator.R:755+. The conn_type_key is f"{from_slug}_{to_slug}"
# matching R's paste(from_type, to_type, sep="_") at line 373.
_CONN_TYPES: list[tuple[str, str, str]] = [
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

# Reversal-compounds used by _analyze_polarity_phrase to detect
# "negative-of-negative" phrases (e.g., "pollution reduction" → positive).
# Bare X.*Y stems with no \b boundaries — matches R lines 216-218 verbatim.
# Algorithm-shape (regex), kept inline rather than in JSON.
_REVERSAL_COMPOUNDS: list[str] = [
    r"pollut.*reduc",  r"emission.*reduc",  r"pressure.*reduc",
    r"litter.*reduc",  r"waste.*reduc",     r"noise.*reduc",
    r"overfish.*prevent",  r"erosion.*control",
]

# Negation-regex patterns with \b word boundaries — matches R lines 209-211
# verbatim. Algorithm-shape (regex), kept inline rather than in JSON.
_NEGATION_PATTERNS: list[str] = [
    r"\bno\b",       r"\bnot\b",       r"\bnon[- ]",     r"\bwithout\b",
    r"\bprevent",    r"\bban\b",       r"\breduc",       r"\bremov",
    r"\bcontrol",    r"\blimit",       r"\brestrict",
]


def calculate_relevance(
    from_name: str, to_name: str, from_slug: str, to_slug: str
) -> float:
    """Return one of {0.3, 0.6, 0.9} based on keyword-substring-match
    count across both names (0 matches → 0.3 floor, 1 → 0.6, 2+ → 0.9).
    Returns 0.5 if the (from_slug, to_slug) pair is missing from the
    keyword JSON (defensive default at R line 376; schema test pins all
    10 pairs present so 0.5 doesn't fire in normal operation).

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
    """Return (sentiment, negated) for a single name. Two-check scheme;
    reversal takes precedence in the return.

    Returns only ("positive", True), ("neutral", True), or
    ("neutral", False) — never ("negative", *). R's helper has no path
    emitting "negative" sentiment; the negative semantic is captured
    separately by the from_is_negative / to_is_negative substring flags
    computed in detect_polarity Step A (see §5 of the spec).

    Direct port of R's .analyze_polarity_phrase at
    connection_generator.R:198-226. R's third return field
    base_sentiment is dropped — R's detect_polarity (R 117-186) reads
    only sentiment and negated.

    Implementation notes:
    - name_lower is assumed already lowercased by the caller (matches
      R's code path where tolower() runs before this helper).
    - Reversal-compounds are checked first to give them return-priority.
      In R, both checks compute their flags before the early return on
      reversal; either order produces the same observable behaviour.
    - Pattern lists _REVERSAL_COMPOUNDS and _NEGATION_PATTERNS are
      module-level (algorithm-shape, not data; see §5).
    """
    # Phase 1: reversal-compounds (precedence in return).
    for pattern in _REVERSAL_COMPOUNDS:
        if re.search(pattern, name_lower):
            return ("positive", True)

    # Phase 2: negation regex with \b boundaries.
    for pattern in _NEGATION_PATTERNS:
        if re.search(pattern, name_lower):
            return ("neutral", True)

    return ("neutral", False)


def detect_polarity(
    from_name: str, to_name: str, from_slug: str, to_slug: str
) -> str:
    """Return '+' or '-' via per-pair dispatch with precomputed per-name
    signals. Faithful to R's structure at connection_generator.R:62-187
    (KB-lookup branch at R 63-75 dropped per scope).

    Slug params are lowercase, NOT human Element.type strings.

    Step A: Precompute per-name signals (R lines 86-112):
      - Lowercase both names.
      - Substring-match polarity_signals keyword sets against each name.
      - Call _analyze_polarity_phrase twice (once per name).

    Step B: Per-pair dispatch over (from_slug, to_slug):
      - ("responses", "pressures"): always "-" (R line 117).
      - ("activities", "pressures"): mitigation-aware (R 133-138).
      - ("pressures", "states"): to-flag-aware (R 143-150).
      - ("states", "impacts"): negation-flip + matrix (R 153-167).
      - ("impacts", "welfare"): negation-flip + simple fall-through (R 170-183).
      - All other pairs: default "+" (R line 186).

    R's KB-lookup branch (R 63-75) and ML-scoring branch are not
    ported per the rule-based-only scope decision. R also has an
    11th branch ("responses", "states") at R 122-130 that SP3 does
    NOT port: _CONN_TYPES (Task 3) only generates 10 type-pairs and
    "responses" -> "states" is not among them, so the branch would
    be unreachable dead code. SP4 can re-add it with a test if
    needed (see spec §5 dispatch-table prose).
    """
    from_lower = from_name.lower()
    to_lower = to_name.lower()

    # --- Step A: Precompute per-name signals (universal hoist) -----
    polarity = _KW["polarity_signals"]
    negative_keywords = polarity["negative_keywords"]
    positive_keywords = polarity["positive_keywords"]
    mitigation_keywords = polarity["mitigation_keywords"]

    def _has_any(text: str, kws: list[str]) -> bool:
        return any(re.search(re.escape(kw), text) for kw in kws)

    from_is_negative = _has_any(from_lower, negative_keywords)
    from_is_positive = _has_any(from_lower, positive_keywords)
    to_is_negative = _has_any(to_lower, negative_keywords)
    to_is_positive = _has_any(to_lower, positive_keywords)
    from_is_mitigation = _has_any(from_lower, mitigation_keywords)

    from_analysis = _analyze_polarity_phrase(from_lower)
    to_analysis = _analyze_polarity_phrase(to_lower)

    # --- Step B: Per-pair dispatch ---------------------------------
    # ("responses", "pressures") — R line 117: always "-".
    if from_slug == "responses" and to_slug == "pressures":
        return "-"

    # ("activities", "pressures") — R lines 133-138.
    if from_slug == "activities" and to_slug == "pressures":
        if from_is_mitigation or from_analysis[0] == "positive":
            return "-"
        return "+"

    # ("pressures", "states") — R lines 143-150.
    if from_slug == "pressures" and to_slug == "states":
        if to_is_negative:
            return "+"  # pressure increases negative state
        if to_is_positive:
            return "-"
        return "-"  # default

    # ("states", "impacts") — R lines 153-167.
    if from_slug == "states" and to_slug == "impacts":
        # Negation flip: only negative flags flip; positive flags NEVER flip.
        if from_analysis[1] and from_is_negative:  # from_analysis.negated
            from_is_negative = False
        if to_analysis[1] and to_is_negative:
            to_is_negative = False
        # Matrix:
        if (from_is_negative and to_is_negative) or (
            from_is_positive and to_is_positive
        ):
            return "+"  # same-sign reinforcement
        if (from_is_negative and to_is_positive) or (
            from_is_positive and to_is_negative
        ):
            return "-"  # opposite-sign opposition
        return "-"  # default for ambiguous/neutral pairs

    # ("impacts", "welfare") — R lines 170-183.
    if from_slug == "impacts" and to_slug == "welfare":
        # Only from-side flags are read (R reads only from_*); to_is_*
        # were precomputed in Step A but UNUSED in this branch.
        if from_analysis[1] and from_is_negative:  # from_analysis.negated
            from_is_negative = False
        if from_is_negative:
            return "-"
        if from_is_positive:
            return "+"
        return "-"  # default: impacts reduce welfare

    # All other pairs (D->A, R->D, R->A, W->D, W->R) — R line 186 default.
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

            polarity = detect_polarity(
                from_el.label, to_el.label, from_slug, to_slug
            )
            verb = _select_verb(from_slug, polarity)
            candidates.append(ConnectionSuggestion(
                source=from_el.id,
                target=to_el.id,
                polarity=polarity,
                confidence=relevance,
                rationale=f"{from_el.label} {verb} {to_el.label}",
            ))

    # Sort desc by confidence (stable -- preserves cross-product order on ties).
    candidates.sort(key=lambda s: s.confidence, reverse=True)
    return candidates[:max_count]


def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """SP3 contract: rule-based scoring across all 10 connection types.
    Same signature as SP1's stub at sespy/wizard.py:92.

    Top-level orchestrator (R lines 755-1001; constants MAX_PER_TYPE=15
    and MIN_RELEVANCE=0.3 at R 757-758). KB-seed and ML-scoring
    branches dropped per rule-based-only scope.

    Returns a flat list of <=150 (10 types x 15 cap) ConnectionSuggestions
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

    # 2. For each of the 10 connection-type pairs, generate suggestions.
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
