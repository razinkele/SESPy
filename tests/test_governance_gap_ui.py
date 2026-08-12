"""Unit tests for the governance-gap UI state helper (branch precedence).

The four degenerate states and their ORDER were fixed by the 2026-08-12
design review: untyped-domination must outrank no-governance because a raw
.qsem import (all elements untyped) satisfies both, and "map themes first"
is the actionable message there.
"""
from pathlib import Path

from sespy import network
from sespy.data_structure import Connection, Element, IsaData, load_sample
from sespy.modules.analysis_metrics import governance_gap_state


def _state(isa):
    return governance_gap_state(network.governance_gap(isa), len(isa.elements))


def test_state_zero_edges():
    isa = IsaData(elements=[Element(id="P1", label="p", type="Pressures")])
    assert _state(isa) == "none"


def test_state_untyped_outranks_no_gov():
    els = [Element(id=f"U{i}", label="u", type="") for i in range(3)]
    els.append(Element(id="P1", label="p", type="Pressures"))
    isa = IsaData(elements=els,
                  connections=[Connection(source="U0", target="U1")])
    assert _state(isa) == "untyped"


def test_state_no_gov():
    els = [Element(id="P1", label="p", type="Pressures"),
           Element(id="D1", label="d", type="Drivers")]
    isa = IsaData(elements=els,
                  connections=[Connection(source="D1", target="P1")])
    assert _state(isa) == "no_gov"


def test_state_no_eco():
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="D1", label="d", type="Drivers")]
    isa = IsaData(elements=els,
                  connections=[Connection(source="R1", target="D1")])
    assert _state(isa) == "no_eco"


def test_state_no_press_when_ecological_but_no_pressures():
    # Typed ecological nodes exist but none are Pressures: the headline
    # "0 of 0 pressure nodes" would be a confident number in a degenerate
    # state — exactly the failure class the amended design guards against.
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="MPF1", label="m", type="Marine Processes & Functioning")]
    isa = IsaData(elements=els,
                  connections=[Connection(source="R1", target="MPF1")])
    assert _state(isa) == "no_press"


def test_state_ok_on_sample():
    root = Path(__file__).resolve().parents[1]
    assert _state(load_sample(root / "data" / "sample_ses.json")) == ""
