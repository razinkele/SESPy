"""App test: build_loop_payload (pyvis-backed) from sespy.modules.analysis_loops."""
from __future__ import annotations

from pathlib import Path

import pytest

from sespy import network
from sespy.data_structure import load_sample

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_ses.json"


def test_pyvis_loop_payload_shape():
    """pyvis 4.2 used as a JSON builder: build_loop_payload should hand back
    the same {nodes, edges} dict shape the vis-network bridge expects, with
    DAPSIWRM colors/shapes already mapped per element type.
    """
    # analysis_loops imports `pyvis.shiny`, which only exists in the pyvis
    # fork (not upstream PyPI pyvis). Skip where the fork isn't installed
    # rather than fail a fork-independent environment (e.g. CI on PyPI deps).
    pytest.importorskip("pyvis.shiny")
    from sespy.constants import EDGE_COLORS, ELEMENT_COLORS, ELEMENT_SHAPES
    from sespy.modules.analysis_loops import build_loop_payload

    isa = load_sample(SAMPLE)
    cycles = network.feedback_loops(isa)
    assert cycles, "sample SES should contain at least one cycle"

    payload = build_loop_payload(cycles[0], isa)
    assert set(payload) == {"nodes", "edges"}

    type_by_id = {e.id: e.type for e in isa.elements}
    for node in payload["nodes"]:
        nid = node["id"]
        assert "label" in node
        # Color/shape come from the DAPSIWRM constants via pyvis
        assert node["color"] == ELEMENT_COLORS[type_by_id[nid]]
        assert node["shape"] == ELEMENT_SHAPES[type_by_id[nid]]

    # Edges are colored by polarity (reinforcing/opposing) — same rule as the
    # CLD canvas, applied loop-wide so the cycle classification is visible.
    valid_edge_colors = set(EDGE_COLORS.values())
    for edge in payload["edges"]:
        assert edge["from"] in {n["id"] for n in payload["nodes"]}
        assert edge["to"] in {n["id"] for n in payload["nodes"]}
        assert edge["color"] in valid_edge_colors
        assert edge["label"] in {"+", "-"}
