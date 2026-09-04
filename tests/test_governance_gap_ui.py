"""Unit tests for the governance-gap UI state helper (branch precedence).

The four degenerate states and their ORDER were fixed by the 2026-08-12
design review: untyped-domination must outrank no-governance because a raw
.qsem import (all elements untyped) satisfies both, and "map themes first"
is the actionable message there.
"""
from pathlib import Path

from sespy import network
from sespy.data_structure import Connection, Element, IsaData, load_sample
from sespy.modules.analysis_metrics import (
    governance_concentration_verdict, governance_gap_state)


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


# ---------------------------------------------------------------------------
# governance_concentration_verdict (issue #26 review follow-up)
# ---------------------------------------------------------------------------

def _gc(ent, *, n=3, actor="R1", share=0.7):
    return {"n_actors": n, "normalised_entropy": ent, "dominant_actor": actor,
            "dominant_share": share, "shannon_entropy": None, "gini": None}


def test_verdict_none_below_two_actors():
    assert governance_concentration_verdict(_gc(None, n=1)) is None
    assert governance_concentration_verdict(_gc(None, n=0)) is None


def test_verdict_distributed_carries_n_and_entropy():
    key, kw = governance_concentration_verdict(_gc(0.87, n=5))
    assert key == "metrics.gov_concentration_distributed"
    assert kw == {"n": 5, "entropy": "0.87"}


def test_verdict_concentrated_carries_actor_share_n_entropy():
    key, kw = governance_concentration_verdict(_gc(0.10, n=2, actor="R002",
                                                   share=0.9865))
    assert key == "metrics.gov_concentration_concentrated"
    assert kw == {"actor": "R002", "share": "0.99", "n": 2, "entropy": "0.10"}


def test_verdict_threshold_agrees_with_displayed_entropy():
    # The wording must follow the number the user sees (2 dp), so 0.497
    # displays "0.50" and reads distributed, while 0.494 displays "0.49"
    # and reads concentrated — never two verdicts for one printed value.
    key_hi, kw_hi = governance_concentration_verdict(_gc(0.497))
    key_lo, kw_lo = governance_concentration_verdict(_gc(0.494))
    assert (key_hi, kw_hi["entropy"]) == ("metrics.gov_concentration_distributed", "0.50")
    assert (key_lo, kw_lo["entropy"]) == ("metrics.gov_concentration_concentrated", "0.49")


def test_verdict_on_sample_is_concentrated_in_r002():
    root = Path(__file__).resolve().parents[1]
    gc = network.governance_concentration(load_sample(root / "data" / "sample_ses.json"))
    key, kw = governance_concentration_verdict(gc)
    assert key == "metrics.gov_concentration_concentrated"
    assert kw["actor"] == "R002" and kw["entropy"] == "0.10"
