"""DAPSIWRM constants ported from constants.R.

Only the subset required by the CLD-visualization POC is included.
The full constants file (738 lines) covers loop analysis thresholds, ML
hyperparameters, and UI sizing that are not yet relevant.
"""

from __future__ import annotations

from dataclasses import dataclass

DAPSIWRM_ELEMENTS: tuple[str, ...] = (
    "Drivers",
    "Activities",
    "Pressures",
    "Marine Processes & Functioning",
    "Ecosystem Services",
    "Goods & Benefits",
    "Responses",
)

ELEMENT_ID_PREFIX: dict[str, str] = {
    "drivers": "D",
    "activities": "A",
    "pressures": "P",
    "states": "MPF",
    "impacts": "ES",
    "welfare": "GB",
    "responses": "R",
    "measures": "RM",
}

# Kumu-style colors (kept identical to the R original so visual parity is exact)
ELEMENT_COLORS: dict[str, str] = {
    "Drivers": "#776db3",
    "Activities": "#5abc67",
    "Pressures": "#fec05a",
    "Marine Processes & Functioning": "#bce2ee",
    "Ecosystem Services": "#313695",
    "Goods & Benefits": "#fff1a2",
    "Responses": "#9C27B0",
    "Measures": "#795548",
}

# vis.js shape names — same set as visNetwork
ELEMENT_SHAPES: dict[str, str] = {
    "Drivers": "star",
    "Activities": "hexagon",
    "Pressures": "diamond",
    "Marine Processes & Functioning": "dot",
    "Ecosystem Services": "square",
    "Goods & Benefits": "triangle",
    "Responses": "triangleDown",
    "Measures": "triangleDown",
}

EDGE_COLORS: dict[str, str] = {
    "reinforcing": "#80b8d7",
    "opposing": "#dc131e",
}

CONNECTION_POLARITY_LABELS: dict[str, str] = {
    "+": "+ reinforcing",
    "-": "− opposing",
}

CONFIDENCE_OPACITY: dict[int, float] = {
    1: 0.3,
    2: 0.5,
    3: 0.7,
    4: 0.9,
    5: 1.0,
}

DEFAULT_GROUP_COLOR = "#95A5A6"
DEFAULT_GROUP_SHAPE = "ellipse"

# DAPSIWRM hierarchical layout level — derived from the R app's level
# assignments in functions/visnetwork_helpers.R::create_nodes_df, but with
# Responses inserted as a unique row between Pressures and MPF (instead of
# R's same-row-with-x-offset trick that vis.js silently ignores in
# hierarchical mode).
#
# Levels MUST be small adjacent integers — vis-network treats level
# numbers as multipliers for `levelSeparation`. If we used {0, 10, 20, 30,
# 40, 50}, an `levelSeparation=90` slider value would render rows ~900 px
# apart (a 4500 px tall canvas crammed into a 650 px viewport).
#
# Visual order top→bottom in DU direction (smaller numbers at the bottom):
#   6  Drivers          (top)
#   5  Activities
#   4  Pressures
#   3  Responses        (between Pressures and MPF — own row)
#   2  Marine Processes & Functioning
#   1  Ecosystem Services
#   0  Goods & Benefits  (bottom)
DAPSIWRM_LEVEL: dict[str, int] = {
    "Goods & Benefits": 0,
    "Ecosystem Services": 1,
    "Marine Processes & Functioning": 2,
    "Responses": 3,
    "Measures": 3,
    "Pressures": 4,
    "Activities": 5,
    "Drivers": 6,
}

# Per-type node and font sizes. Tuned for readability on a 1080p / Retina
# screen with the larger spacing defaults below. Endpoints (Drivers, Goods &
# Benefits) get slightly bigger nodes to anchor the eye at the top and bottom
# of the framework flow.
# Per-type *base* sizes — these are multiplied by the user's "Node size"
# slider scale at render time, so the proportions between endpoints and main
# flow are preserved while the user tunes overall size.
DAPSIWRM_NODE_SIZE: dict[str, int] = {
    "Drivers": 30,
    "Goods & Benefits": 30,
    "Activities": 22,
    "Pressures": 22,
    "Marine Processes & Functioning": 22,
    "Ecosystem Services": 22,
    "Responses": 22,
    "Measures": 22,
}

DAPSIWRM_FONT_SIZE: dict[str, int] = {
    "Drivers": 14,
    "Goods & Benefits": 14,
    "Activities": 12,
    "Pressures": 12,
    "Marine Processes & Functioning": 12,
    "Ecosystem Services": 12,
    "Responses": 12,
    "Measures": 12,
}

# Maximum label width in pixels before vis.js wraps. Scales together with
# node size at render time so larger nodes get wider labels.
DAPSIWRM_LABEL_WIDTH = 140


# ---------------------------------------------------------------------------
# PIMS (Process & Information Management System) — Project Setup constants.
# Mirrors ../SESToolbox/MarineSABRES_SES_Shiny/constants.R:528, 682.
# ---------------------------------------------------------------------------

DA_SITES: tuple[str, ...] = (
    "Tuscan Archipelago",
    "Arctic Northeast Atlantic",
    "Macaronesia",
)

SPATIAL_SCALES: tuple[str, ...] = (
    "Local",
    "Regional",
    "National",
    "International",
)

TEMPORAL_SCALES: tuple[str, ...] = (
    "Daily",
    "Monthly",
    "Yearly",
    "Decadal",
)

# --- Element indicator fields (P1b, schema v8) --------------------------------
# R WP5_POLICY_TARGETS (constants.R:940, v1.33.0). Element.policy_target holds
# one of these codes or free text (spec §4.3).
POLICY_TARGET_CODES: tuple[str, ...] = (
    "kmgbf_30x30", "eu_nrr", "msfd_ges_d1", "msfd_ges_d6", "national_mpa_pct",
)

# --- Connection delay vocabulary (QSEM time-delay surfacing) -----------------
DELAY_LEVELS: tuple[str, ...] = ("immediate", "short", "long")

# Values that mean "no delay" — guarded so a negated/zero cell is not
# mislabelled as delayed.
_DELAY_IMMEDIATE_SENTINELS = frozenset({
    "", "none", "immediate", "instant", "now", "no", "n/a", "na", "false", "f", "-",
})


def normalize_delay(raw: object) -> str:
    """Map any stored/imported delay value to DELAY_LEVELS, conservatively.

    Order (case-insensitive, stripped): exact short/long/immediate; an
    immediate/negation sentinel -> 'immediate'; numeric 0 -> 'immediate',
    > 0 -> 'short'; any remaining non-empty free-text -> 'short'. 'long' is
    only produced by an exact match (never auto-promoted).
    """
    s = ("" if raw is None else str(raw)).strip().lower()
    if s in ("short", "long", "immediate"):
        return s
    if s in _DELAY_IMMEDIATE_SENTINELS:
        return "immediate"
    try:
        return "immediate" if float(s) == 0 else "short"
    except ValueError:
        return "short" if s else "immediate"


# ---------------------------------------------------------------------------
# DAPSI(W)R(M) link rules (P1a). Ported from R v1.29.0 (unchanged at v1.31.0)
# functions/dapsiwrm_connection_rules.R:26-341 (targets, extension_targets,
# per-pair target_polarities). R's table has no rule ids: they come from R's
# DAPSIWRM_FRAMEWORK_RULES.md ("6-7" = the collapsed GB->D rules, "ExUP" =
# the D->P exogenic-unmanaged-pressure exception). R's per-source
# default_polarity is unreachable (every listed target has its own
# polarity), so it is not ported. There is no Measures entry: Measures fold
# into Responses (M->R is covered by R->R, Rule 14).
# tests/parity/test_r_rules_parity.py pins this table to the R file.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuleTarget:
    to_type: str
    polarity: str      # "+" | "-"
    rule_id: str


@dataclass(frozen=True)
class AdjacencyRule:
    targets: tuple[RuleTarget, ...]              # canonical: offered as suggestions
    extension_targets: tuple[RuleTarget, ...]    # valid, never suggested


_MPF = "Marine Processes & Functioning"

DAPSIWRM_ADJACENCY_RULES: dict[str, AdjacencyRule] = {
    "Drivers": AdjacencyRule(
        targets=(RuleTarget("Activities", "+", "1"),),
        extension_targets=(RuleTarget("Pressures", "+", "ExUP"),),
    ),
    "Activities": AdjacencyRule(
        targets=(RuleTarget("Pressures", "+", "2"),),
        extension_targets=(RuleTarget("Activities", "+", "18"),),
    ),
    "Pressures": AdjacencyRule(
        targets=(RuleTarget(_MPF, "-", "3"),),
        extension_targets=(RuleTarget("Pressures", "+", "17"),),
    ),
    _MPF: AdjacencyRule(
        targets=(RuleTarget("Ecosystem Services", "+", "4"),),
        extension_targets=(RuleTarget(_MPF, "+", "16"),),
    ),
    "Ecosystem Services": AdjacencyRule(
        targets=(RuleTarget("Goods & Benefits", "+", "5"),),
        extension_targets=(),
    ),
    "Goods & Benefits": AdjacencyRule(
        targets=(RuleTarget("Drivers", "+", "6-7"),
                 RuleTarget("Responses", "+", "8")),
        extension_targets=(),
    ),
    "Responses": AdjacencyRule(
        targets=(RuleTarget("Drivers", "-", "9"),
                 RuleTarget("Activities", "-", "10"),
                 RuleTarget("Pressures", "-", "11"),
                 RuleTarget(_MPF, "+", "12")),
        extension_targets=(RuleTarget("Responses", "+", "14"),),
    ),
}
