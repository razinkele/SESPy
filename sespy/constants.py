"""DAPSIWRM constants ported from constants.R.

Only the subset required by the CLD-visualization POC is included.
The full constants file (738 lines) covers loop analysis thresholds, ML
hyperparameters, and UI sizing that are not yet relevant.
"""

from __future__ import annotations

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
