"""Unit tests for sespy.wizard — pure-data wizard flow."""
from __future__ import annotations

from sespy.data_structure import WizardState
from sespy.wizard import (
    ELEMENT_TYPE_MAP,
    REGIONAL_SEAS,
    WIZARD_STEPS,
    suggest_connections,
)


def test_wizard_steps_count_is_12():
    assert len(WIZARD_STEPS) == 12


def test_wizard_steps_indices_are_0_to_11():
    indices = [s["step"] for s in WIZARD_STEPS]
    assert indices == list(range(12))


def test_wizard_steps_targets_match_spec():
    targets = [s["target"] for s in WIZARD_STEPS]
    assert targets == [
        "regional_sea", "ecosystem_type", "countries", "main_issue",
        "drivers", "activities", "pressures", "states",
        "impacts", "welfare", "responses", "connections",
    ]


def test_wizard_steps_archetypes():
    archetypes = [s["archetype"] for s in WIZARD_STEPS]
    assert archetypes == [
        "choice_one", "choice_one", "choice_many", "choice_many",
        "freeform_multiple", "freeform_multiple", "freeform_multiple",
        "freeform_multiple", "freeform_multiple", "freeform_multiple",
        "freeform_multiple", "connection_review",
    ]


def test_element_type_map_matches_constants():
    """The mapping must match constants.ELEMENT_ID_PREFIX semantics —
    impacts→Ecosystem Services, welfare→Goods & Benefits."""
    assert ELEMENT_TYPE_MAP["drivers"] == "Drivers"
    assert ELEMENT_TYPE_MAP["activities"] == "Activities"
    assert ELEMENT_TYPE_MAP["pressures"] == "Pressures"
    assert ELEMENT_TYPE_MAP["states"] == "Marine Processes & Functioning"
    assert ELEMENT_TYPE_MAP["impacts"] == "Ecosystem Services"
    assert ELEMENT_TYPE_MAP["welfare"] == "Goods & Benefits"
    assert ELEMENT_TYPE_MAP["responses"] == "Responses"


def test_regional_seas_placeholder_has_at_least_baltic():
    assert "baltic" in REGIONAL_SEAS
    baltic = REGIONAL_SEAS["baltic"]
    assert "name" in baltic
    assert "ecosystem_types" in baltic
    assert "countries" in baltic
    assert "common_issues" in baltic


def test_suggest_connections_empty_state_returns_empty():
    """SP3-renamed from test_suggest_connections_stub_returns_empty.

    The wizard-level test smokes the import-graph and delegation after
    Task 2's ELEMENT_TYPE_MAP relocation. The richer behavioral pinning
    moved to tests/test_connection_scorer.py Group 5 (which has 9 tests
    including its own test_empty_state_returns_empty for the impl path).
    """
    state = WizardState(regional_sea="baltic", ecosystem_type="open_coast")
    assert suggest_connections(state) == []


# ===========================================================================
# SP4 dedup logic tests — pure-data layer (no Shiny reactive context required).
# These test the dedup helper only; the full _on_finish flow is exercised
# via e2e in tests/test_wizard_e2e.py.
# ===========================================================================


from sespy.data_structure import ConnectionSuggestion

# Import the production helper directly — NOT a copy. Tests below
# exercise the exact same algorithm _on_finish uses.
from sespy.modules.ai_isa_wizard import _dedup_accepted as _dedup


def _make_sug(source, target, polarity, confidence, rationale="r"):
    return ConnectionSuggestion(
        source=source, target=target, polarity=polarity,
        confidence=confidence, rationale=rationale,
    )


def test_dedup_keeps_both_polarities_for_same_pair():
    """(D001, A001, +) and (D001, A001, -) co-exist — different polarity
    is NOT a duplicate."""
    pos = _make_sug("D001", "A001", "+", 0.9)
    neg = _make_sug("D001", "A001", "-", 0.7)
    final, discarded, overwritten = _dedup([pos, neg])
    assert len(final) == 2
    assert {(s.source, s.target, s.polarity) for s in final} == {
        ("D001", "A001", "+"), ("D001", "A001", "-"),
    }
    assert discarded == 0 and overwritten == 0


def test_dedup_drops_lower_confidence_same_polarity():
    sp3 = _make_sug("D001", "A001", "+", 0.5, rationale="sp3 r")
    sp4 = _make_sug("D001", "A001", "+", 0.9, rationale="sp4 r")
    # SP3 first, then SP4 (real iteration order in _on_finish).
    final, discarded, overwritten = _dedup([sp3, sp4])
    assert len(final) == 1
    # Higher confidence wins.
    assert final[0].confidence == 0.9
    assert final[0].rationale == "sp4 r"
    assert overwritten == 1
    assert discarded == 0


def test_dedup_tie_break_favors_sp3_via_iteration_order():
    """Equal confidence — first-iterated entry wins (the SP3 entry,
    since SP3 is read before SP4 in _on_finish)."""
    sp3 = _make_sug("D001", "A001", "+", 0.7, rationale="sp3 r")
    sp4 = _make_sug("D001", "A001", "+", 0.7, rationale="sp4 r")
    final, discarded, overwritten = _dedup([sp3, sp4])
    assert len(final) == 1
    assert final[0].rationale == "sp3 r"
    assert discarded == 1
    assert overwritten == 0
