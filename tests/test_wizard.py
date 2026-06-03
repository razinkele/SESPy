"""Unit tests for sespy.wizard — pure-data wizard flow."""
from __future__ import annotations

from sespy.wizard import (
    WIZARD_STEPS,
    ELEMENT_TYPE_MAP,
    REGIONAL_SEAS,
    suggest_connections,
)
from sespy.data_structure import WizardState


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
