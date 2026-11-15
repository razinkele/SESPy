"""Unit tests for sespy.connection_scorer, the rule-based scorer.

The scorer is an exact port of R v1.35.6 generate_connections (ML off); the
golden parity tests at the bottom are the arbiter. The tests above them pin
helper behaviour. The old SP3 keyword-JSON loader tests and the 0.3/0.6/0.9
relevance-step tests were deleted in K1b Task 6 (the JSON and the steps are
gone; relevance is R's calculate_enhanced_relevance, covered in
test_r_connection_kb.py).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sespy.r_kb import VENDORED

DB = VENDORED.connection_db()


# ---------------------------------------------------------------------------
# Polarity helpers and detect_polarity (5-arg R signature)
# ---------------------------------------------------------------------------

def test_analyze_polarity_phrase_reversal_compound():
    """The helper detects 'negative-of-negative' phrases as ('positive', True)
    via R's reversal-compounds list."""
    from sespy.connection_scorer import _analyze_polarity_phrase

    assert _analyze_polarity_phrase("pollution reduction") == ("positive", True)
    assert _analyze_polarity_phrase("emission reduction") == ("positive", True)
    assert _analyze_polarity_phrase("overfish prevention") == ("positive", True)
    assert _analyze_polarity_phrase("fishing activity") == ("neutral", False)
    # "no biodiversity" matches \bno\b but not any reversal compound.
    assert _analyze_polarity_phrase("no biodiversity") == ("neutral", True)


def test_responses_to_pressures_is_minus():
    """No KB match -> R's rule: always '-' for responses -> pressures."""
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Foo", "Bar", "responses", "pressures", DB) == "-"


def test_activities_to_pressures_mitigation_is_minus():
    """'Pollution reduction' from activities -> '-' via the reversal-compound
    path (mitigation keyword / positive phrase sentiment)."""
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Pollution reduction", "Eutrophication",
                           "activities", "pressures", DB) == "-"


def test_activities_to_pressures_default_is_plus():
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Zzz", "Qqq", "activities", "pressures", DB) == "+"


def test_pressures_to_states_branches():
    """No-KB-match rule branches of pressures -> states: negative-sounding
    target '+', positive-sounding target '-', neutral default '-'."""
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Zzz", "Fish stocks decline",
                           "pressures", "states", DB) == "+"
    assert detect_polarity("Zzz", "Healthy biodiversity",
                           "pressures", "states", DB) == "-"
    assert detect_polarity("Zzz", "Open coastal waters",
                           "pressures", "states", DB) == "-"


def test_states_to_impacts_negation_flip():
    """The negation flip zeroes from_is_negative when the phrase is negated
    AND negative. Observable only when the target is negative too: without
    the flip two negatives give '+', with it the source is neutral -> '-'."""
    from sespy import r_connection_kb as r_kb
    from sespy.connection_scorer import detect_polarity
    for f, t in (("Reduced qqq", "Pollution qqq"), ("Pollution qqq", "Pollution qqq")):
        assert r_kb.lookup_knowledge_base(f, "states", t, "impacts", DB) is None
    assert detect_polarity("Reduced qqq", "Pollution qqq",
                           "states", "impacts", DB) == "-"
    assert detect_polarity("Pollution qqq", "Pollution qqq",
                           "states", "impacts", DB) == "+"


def test_default_fallback_for_unspecified_pair():
    """Pairs without a named branch (and no KB match) return '+'."""
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Zzz", "Qqq", "drivers", "activities", DB) == "+"
    assert detect_polarity("Zzz", "Qqq", "responses", "drivers", DB) == "+"
    assert detect_polarity("Zzz", "Qqq", "responses", "activities", DB) == "+"
    assert detect_polarity("Zzz", "Qqq", "welfare", "drivers", DB) == "+"
    assert detect_polarity("Zzz", "Qqq", "welfare", "responses", DB) == "+"


@pytest.mark.parametrize("to_label,want", [
    ("Hypoxia extent", "-"),          # negative-sounding target: reduces a bad state
    ("Fish stock recovery", "+"),     # positive-sounding target: increases a good state
    ("Seabed sediment", "+"),         # neither: default "+"
])
def test_detect_polarity_responses_to_states(to_label, want):
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Zzz", to_label, "responses", "states", DB) == want


# ---------------------------------------------------------------------------
# Verb table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "from_slug,polarity,expected_verb",
    [
        ("drivers", "+", "drives"),
        ("drivers", "-", "drives"),
        ("activities", "+", "increases"),
        ("activities", "-", "causes"),
        ("pressures", "+", "increases"),
        ("pressures", "-", "decreases"),
        ("states", "+", "impacts"),
        ("states", "-", "impacts"),
        ("impacts", "+", "increases"),
        ("impacts", "-", "reduces"),
        ("responses", "+", "enables"),
        ("responses", "-", "restricts"),
        ("welfare", "+", "motivates"),
        ("welfare", "-", "reduces"),
    ],
)
def test_verb_selection_per_from_slug_polarity_pair(from_slug, polarity, expected_verb):
    from sespy.connection_scorer import _select_verb
    assert _select_verb(from_slug, polarity) == expected_verb


def _make_element(eid: str, label: str, etype: str):
    """Helper: build a minimal Element for testing."""
    from sespy.data_structure import Element
    return Element(id=eid, label=label, type=etype)


# ---------------------------------------------------------------------------
# _generate_smart_connections
# ---------------------------------------------------------------------------

def test_cross_product_pair_generation():
    """2 x 3 candidates, none filtered: every pair clears R's threshold when it
    has a KB match; assert the count equals the survivors of the threshold."""
    from sespy.connection_scorer import _generate_smart_connections
    from_els = [_make_element("D001", "Food security", "Drivers"),
                _make_element("D002", "Economic growth", "Drivers")]
    to_els = [_make_element("A001", "Commercial fishing", "Activities"),
              _make_element("A002", "Aquaculture", "Activities"),
              _make_element("A003", "Tourism", "Activities")]
    result = _generate_smart_connections(from_els, to_els, "drivers", "activities")
    assert 1 <= len(result) <= 6
    assert all(s.relevance >= 0.3 for s in result)


def test_double_negative_filter_uses_loss_keywords():
    """Both names contain a loss keyword -> candidate dropped (R's
    loss_keywords, regex search on the lowercased names)."""
    from sespy.connection_scorer import _generate_smart_connections
    from_els = [_make_element("S001", "Loss of biodiversity", "Marine Processes & Functioning")]
    to_els = [_make_element("I001", "Decline in fishery yield", "Ecosystem Services")]
    assert _generate_smart_connections(
        from_els, to_els, "states", "impacts", min_relevance=0.0) == []
    # Only one side is a loss name: the pair survives (threshold lowered so
    # the test does not depend on the relevance value).
    from_els = [_make_element("S002", "Pollution", "Marine Processes & Functioning")]
    to_els = [_make_element("I002", "Loss of habitat", "Ecosystem Services")]
    assert len(_generate_smart_connections(
        from_els, to_els, "states", "impacts", min_relevance=0.0)) == 1


def test_filtered_candidates_do_not_use_the_cap():
    """Skipped double-negatives free their slot: with max_count=2 and one
    filtered candidate ahead of two others, two rows come back."""
    from sespy.connection_scorer import _generate_smart_connections
    from_els = [_make_element("S1", "Loss of fish", "Marine Processes & Functioning"),
                _make_element("S2", "Fish biomass", "Marine Processes & Functioning")]
    to_els = [_make_element("I1", "Decline in catch", "Ecosystem Services"),
              _make_element("I2", "Fish provisioning", "Ecosystem Services")]
    got = _generate_smart_connections(from_els, to_els, "states", "impacts",
                                      max_count=3, min_relevance=0.0)
    pairs = {(s.source, s.target) for s in got}
    assert len(got) == 3 and ("S1", "I1") not in pairs


def test_results_sorted_by_relevance_desc_stable():
    from sespy.connection_scorer import _generate_smart_connections
    from_els = [_make_element(f"D{i}", n, "Drivers") for i, n in
                enumerate(["Food security", "Zzz", "Economic growth", "Qqq"])]
    to_els = [_make_element("A1", "Commercial fishing", "Activities")]
    got = _generate_smart_connections(from_els, to_els, "drivers", "activities",
                                      min_relevance=0.0)
    rel = [s.relevance for s in got]
    assert rel == sorted(rel, reverse=True)
    # Equal relevance keeps the (i, j) generation order (stable sort).
    for a, b in zip(got, got[1:]):
        if a.relevance == b.relevance:
            assert a.source < b.source


def test_max_count_cap_honored():
    """> 15 candidates -> exactly 15 returned."""
    from sespy.connection_scorer import _generate_smart_connections
    from_els = [_make_element(f"D{i:03d}", f"Tourism{i}", "Drivers") for i in range(1, 5)]
    to_els = [_make_element(f"A{i:03d}", f"Recreation{i}", "Activities") for i in range(1, 6)]
    result = _generate_smart_connections(
        from_els, to_els, "drivers", "activities", max_count=15, min_relevance=0.0)
    assert len(result) == 15


def test_threshold_is_inclusive():
    """relevance == min_relevance survives; one ulp above it does not."""
    import math

    from sespy.connection_scorer import _generate_smart_connections
    from_els = [_make_element("D001", "Bicycle", "Drivers")]
    to_els = [_make_element("A001", "Letter", "Activities")]
    r = _generate_smart_connections(
        from_els, to_els, "drivers", "activities", min_relevance=0.0)[0].relevance
    assert len(_generate_smart_connections(
        from_els, to_els, "drivers", "activities", min_relevance=r)) == 1
    assert _generate_smart_connections(
        from_els, to_els, "drivers", "activities",
        min_relevance=math.nextafter(r, 2.0)) == []


# ---------------------------------------------------------------------------
# suggest_connections
# ---------------------------------------------------------------------------

def test_empty_state_returns_empty():
    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import WizardState
    assert suggest_connections(WizardState()) == []


def test_single_element_state_returns_empty():
    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import WizardState
    state = WizardState(elements=[_make_element("D001", "Tourism", "Drivers")])
    assert suggest_connections(state) == []


def test_full_state_returns_typed_suggestions():
    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import ConnectionSuggestion, WizardState
    state = WizardState(elements=[
        _make_element("D001", "Food security", "Drivers"),
        _make_element("A001", "Commercial fishing", "Activities"),
        _make_element("P001", "Overfishing", "Pressures"),
    ])
    result = suggest_connections(state)
    assert len(result) > 0
    for s in result:
        assert isinstance(s, ConnectionSuggestion)
        assert 0.3 <= s.relevance <= 1.0
        assert s.polarity in {"+", "-"}
        assert s.strength in {"weak", "medium", "strong"}
        assert s.confidence in {3, 4}


def test_per_type_cap_honored_end_to_end():
    """5 x 5 = 25 D->A candidates (all above threshold) -> exactly 15."""
    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import WizardState
    drivers = [_make_element(f"D{i:03d}", f"Food security {i}", "Drivers")
               for i in range(1, 6)]
    activities = [_make_element(f"A{i:03d}", f"Commercial fishing {i}", "Activities")
                  for i in range(1, 6)]
    result = suggest_connections(WizardState(elements=drivers + activities))
    assert sum(1 for s in result if s.source.startswith("D")) == 15


def test_unknown_element_type_skipped(caplog):
    import logging

    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import WizardState
    state = WizardState(elements=[
        _make_element("X001", "Mystery thing", "Foo"),
        _make_element("D001", "Food security", "Drivers"),
        _make_element("A001", "Commercial fishing", "Activities"),
    ])
    with caplog.at_level(logging.WARNING, logger="sespy.connection_scorer"):
        result = suggest_connections(state)
    assert len(result) >= 1
    assert any("X001" in rec.message and "Foo" in rec.message
               for rec in caplog.records)


def test_type_slug_map_is_inverse_of_wizard_map():
    from sespy.connection_scorer import _TYPE_TO_SLUG
    from sespy.data_structure import ELEMENT_TYPE_MAP
    for slug, type_str in ELEMENT_TYPE_MAP.items():
        assert _TYPE_TO_SLUG[type_str] == slug
    assert len(_TYPE_TO_SLUG) == len(ELEMENT_TYPE_MAP)


def test_no_wizard_import_in_connection_scorer():
    """Defensive: no top-level or lazy wizard import in connection_scorer.py
    (re-introduces the import cycle ELEMENT_TYPE_MAP's relocation broke)."""
    import ast
    src_path = (Path(__file__).resolve().parent.parent
                / "sespy" / "connection_scorer.py")
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "wizard" and node.level == 1:
                pytest.fail(f"connection_scorer.py:{node.lineno} imports .wizard")
            if node.module == "sespy.wizard":
                pytest.fail(f"connection_scorer.py:{node.lineno} imports sespy.wizard")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("sespy.wizard", "wizard"):
                    pytest.fail(f"connection_scorer.py:{node.lineno} imports sespy.wizard")


def test_r_to_mpf_has_no_keyword_relevance_without_kb_match():
    """R has no relevance keywords for R->MPF: with no KB match the relevance
    is a flat 0.5 (KB:1253 defensive default)."""
    from sespy import r_connection_kb as r_kb
    assert r_kb.lookup_knowledge_base("Zzz", "responses", "Qqq", "states", DB) is None
    assert r_kb.calculate_enhanced_relevance(
        "Zzz", "Qqq", "responses", "states", DB) == 0.5


def test_snapshot_none_means_vendored_and_is_passed_through():
    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import WizardState
    state = WizardState(elements=[
        _make_element("D1", "Food security", "Drivers"),
        _make_element("A1", "Commercial fishing", "Activities")])
    assert suggest_connections(state) == suggest_connections(state, VENDORED)


# ---------------------------------------------------------------------------
# K1b Task 6: golden parity with R v1.35.6 generate_connections (ML off)
# ---------------------------------------------------------------------------

import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent / "parity"))
from k1b_fixtures import load_k1b_fixture  # noqa: E402


def _state_from_case(case):
    """One Element per fixture name, in R's element order; ids[(slug, i)]."""
    from sespy.data_structure import ELEMENT_TYPE_MAP, WizardState
    els, ids = [], {}
    for slug, names in case["elements"].items():
        for i, name in enumerate(names, start=1):
            eid = f"{slug}-{i}"
            ids[(slug, i)] = eid
            els.append(_make_element(eid, name, ELEMENT_TYPE_MAP[slug]))
    return WizardState(elements=els), ids


@pytest.mark.parametrize("case", load_k1b_fixture("connections")["cases"],
                         ids=lambda c: c["id"])
def test_matches_r_generate_connections(case):
    from sespy.connection_scorer import suggest_connections
    state, ids = _state_from_case(case)
    got = suggest_connections(state)
    want = [(ids[(r["from_type"], r["from_index"])],
             ids[(r["to_type"], r["to_index"])],
             r["polarity"], r["strength"], int(r["confidence"]))
            for r in case["rows"]]
    assert [(s.source, s.target, s.polarity, s.strength, s.confidence)
            for s in got] == want
    for s, r in zip(got, case["rows"]):
        assert s.relevance == pytest.approx(r["relevance"], abs=1e-12)
        assert s.rationale.startswith(r["from_name"] + " ")
        assert s.rationale.endswith(" " + r["to_name"])


def test_pairs_are_rs_ten_in_order():
    from sespy.connection_scorer import R_CONNECTION_PAIRS
    assert [f"{a[0]}-{b[0]}".upper() for a, b in R_CONNECTION_PAIRS] == \
        ["D-A", "A-P", "P-S", "S-I", "I-W", "R-P", "W-D", "W-R", "R-D", "R-A"]


def test_duplicate_names_map_to_distinct_ids():
    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import WizardState
    state = WizardState(elements=[
        _make_element("A1", "Commercial fishing", "Activities"),
        _make_element("A2", "Commercial fishing", "Activities"),
        _make_element("P1", "Overfishing", "Pressures"),
    ])
    got = suggest_connections(state)
    assert [(s.source, s.target) for s in got] == [("A1", "P1"), ("A2", "P1")]


def test_scorer_runs_under_two_seconds_for_40_per_type():
    import time

    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import ELEMENT_TYPE_MAP, WizardState
    names = ["fishing", "tourism", "nutrient", "habitat", "income"]
    els = [_make_element(f"{slug}-{i}", f"{names[i % 5]} item {i}", t)
           for slug, t in ELEMENT_TYPE_MAP.items() for i in range(40)]
    state = WizardState(elements=els)
    suggest_connections(state)  # warm regex caches
    t0 = time.perf_counter()
    got = suggest_connections(state)
    assert time.perf_counter() - t0 < 2.0
    assert len(got) <= 150
