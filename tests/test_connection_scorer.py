"""Unit tests for sespy.connection_scorer — connection-scoring backend.

Test groups (per spec §7):
  G1 (this file's first 5 tests): JSON schema / loader
  G2: calculate_relevance (added in Task 4)
  G3: detect_polarity (added in Tasks 5-6)
  G4: _select_verb + _generate_smart_connections (added in Tasks 7-8)
  G5: suggest_connections — the SP3 contract (added in Task 9)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Group 1: JSON schema / loader (5 tests)
# ---------------------------------------------------------------------------

def test_keywords_json_loads():
    """File loads via _load_keywords() without error."""
    from sespy.connection_scorer import _load_keywords
    kw = _load_keywords()
    assert isinstance(kw, dict)
    assert "connection_types" in kw
    assert "polarity_signals" in kw


def test_all_10_connection_types_present():
    """Set-equality on connection_types keys against the 10 expected slugs."""
    from sespy.connection_scorer import _KW
    expected = {
        "drivers_activities", "activities_pressures", "pressures_states",
        "states_impacts", "impacts_welfare",
        "responses_pressures", "responses_drivers", "responses_activities",
        "welfare_drivers", "welfare_responses",
    }
    assert set(_KW["connection_types"].keys()) == expected


def test_polarity_signals_keys_present():
    """Set-equality on the 4 polarity-signal keys."""
    from sespy.connection_scorer import _KW
    expected = {"negative_keywords", "positive_keywords",
                "mitigation_keywords", "loss_keywords"}
    assert set(_KW["polarity_signals"].keys()) == expected


def test_every_keyword_list_non_empty():
    """All connection_types lists and all polarity_signals lists have len >= 1.

    Includes welfare_drivers — the SP3 hand-curated addition. Pinning
    non-emptiness here protects against a future 'minimize JSON' pass
    silently dropping the curated list.
    """
    from sespy.connection_scorer import _KW
    for slug, kws in _KW["connection_types"].items():
        assert len(kws) >= 1, f"{slug}: connection_types list is empty"
    for name, kws in _KW["polarity_signals"].items():
        assert len(kws) >= 1, f"{name}: polarity_signals list is empty"


def test_keywords_are_lowercase_and_stripped():
    """Canonicalization invariant: every keyword == kw.lower().strip()."""
    from sespy.connection_scorer import _KW
    for slug, kws in _KW["connection_types"].items():
        for kw in kws:
            assert kw == kw.lower().strip(), (
                f"{slug}: keyword {kw!r} is not lowercase/stripped"
            )
    for name, kws in _KW["polarity_signals"].items():
        for kw in kws:
            assert kw == kw.lower().strip(), (
                f"{name}: keyword {kw!r} is not lowercase/stripped"
            )


# ---------------------------------------------------------------------------
# Group 2: calculate_relevance (6 tests)
# ---------------------------------------------------------------------------

def test_zero_matches_returns_03():
    """Names with no keyword substring match → 0.3 (R's Low relevance floor)."""
    from sespy.connection_scorer import calculate_relevance
    # "Tractor" / "Bicycle" share no keyword stems with drivers_activities
    # (which has "fish", "food", "econom", "livelihood", ...).
    assert calculate_relevance("Tractor", "Bicycle", "drivers", "activities") == 0.3


def test_one_match_returns_06():
    """Exactly one keyword substring match across both names → 0.6."""
    from sespy.connection_scorer import calculate_relevance
    # "Fishing" matches "fish" stem (1 match in from_name); "Bicycle" matches
    # nothing → total_matches = 1 → 0.6.
    assert calculate_relevance("Fishing", "Bicycle", "drivers", "activities") == 0.6


def test_two_plus_matches_returns_09():
    """Two or more keyword substring matches → 0.9."""
    from sespy.connection_scorer import calculate_relevance
    # "Fishing" matches "fish"; "Tourism" matches "tourism" → total_matches = 2 → 0.9.
    assert calculate_relevance("Fishing", "Tourism", "drivers", "activities") == 0.9


def test_relevance_uses_substring_match():
    """'Fishing' matches keyword stem 'fish' (substring, not token-exact).

    Pinned because the substring-vs-token semantics is load-bearing —
    token-exact match would miss most real labels (R uses grepl, not
    word-boundary match).
    """
    from sespy.connection_scorer import calculate_relevance
    # If the implementation used token-exact match (e.g., 'fish' in name.split()),
    # 'Fishing' would NOT match 'fish' and this would return 0.3 (no matches).
    # With substring match, it matches and returns 0.6 (1 match in from_name).
    assert calculate_relevance("Fishing", "XYZ", "drivers", "activities") == 0.6


def test_relevance_is_case_insensitive():
    """'FISHING' matches keyword 'fish' (input lowercased before matching)."""
    from sespy.connection_scorer import calculate_relevance
    assert calculate_relevance("FISHING", "XYZ", "drivers", "activities") == 0.6


def test_relevance_unknown_pair_returns_05():
    """Unknown (from_slug, to_slug) pair → 0.5 (R's defensive default at line 376).

    Pins the defensive path so a future removal is a deliberate decision.
    Schema test guarantees all 10 valid pairs are present, so this only
    fires on coding errors.
    """
    from sespy.connection_scorer import calculate_relevance
    # "garbage_bogus" is not a valid slug pair; the lookup falls through to 0.5.
    assert calculate_relevance("X", "Y", "garbage", "bogus") == 0.5


# ---------------------------------------------------------------------------
# Group 3: detect_polarity (7 tests)
# ---------------------------------------------------------------------------

def test_analyze_polarity_phrase_reversal_compound():
    """The helper detects 'negative-of-negative' phrases as ('positive', True)
    via the 8-pattern reversal-compounds list (R lines 216-218).

    Falsifiable invariant for the load-bearing reversal-compound list:
    'pollution reduction' returns ('positive', True), 'emission reduction'
    likewise, an unrelated phrase returns ('neutral', False), a phrase
    matching only a negation pattern returns ('neutral', True).
    """
    from sespy.connection_scorer import _analyze_polarity_phrase

    # Reversal-compound matches → ("positive", True)
    assert _analyze_polarity_phrase("pollution reduction") == ("positive", True)
    assert _analyze_polarity_phrase("emission reduction") == ("positive", True)
    assert _analyze_polarity_phrase("overfish prevention") == ("positive", True)

    # No reversal, no negation → ("neutral", False)
    assert _analyze_polarity_phrase("fishing activity") == ("neutral", False)

    # Negation only (no reversal-compound match) → ("neutral", True)
    # "no biodiversity" matches \bno\b but not any reversal compound.
    assert _analyze_polarity_phrase("no biodiversity") == ("neutral", True)


def test_responses_to_pressures_is_minus():
    """Always '-' regardless of names (R line 117 invariant)."""
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Foo", "Bar", "responses", "pressures") == "-"
    assert detect_polarity("Marine policy", "Pollution",
                          "responses", "pressures") == "-"


def test_activities_to_pressures_mitigation_is_minus():
    """'Pollution reduction' from activities → '-' via the reversal-compound
    path: _analyze_polarity_phrase returns ('positive', True), then dispatch
    checks from_analysis.sentiment == 'positive' (R lines 133-138)."""
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Pollution reduction", "Eutrophication",
                          "activities", "pressures") == "-"


def test_activities_to_pressures_default_is_plus():
    """Neutral names → '+' (default for activities → pressures)."""
    from sespy.connection_scorer import detect_polarity
    # "Tourism" has no mitigation_keywords match, no reversal-compound match.
    # → from_is_mitigation=False, from_analysis.sentiment="neutral" → default "+".
    assert detect_polarity("Tourism", "Noise", "activities", "pressures") == "+"


def test_pressures_to_states_branches():
    """All three pressures→states branches (R lines 144-150):
    - to_is_negative=True → "+" (pressure increases negative state)
    - to_is_positive=True → "-" (pressure decreases positive state)
    - neutral → default "-"

    The to_is_positive branch is observationally identical to the
    default in the current implementation (both return "-") but is
    pinned here so a future refactor that distinguishes them would
    break the test instead of silently changing behavior.
    """
    from sespy.connection_scorer import detect_polarity
    # to_is_negative path: "Fish stocks decline" has "declin" → "+"
    assert detect_polarity("Eutrophication", "Fish stocks decline",
                           "pressures", "states") == "+"
    # to_is_positive path: "Healthy biodiversity" has "health", "biodiver" → "-"
    assert detect_polarity("Eutrophication", "Healthy biodiversity",
                           "pressures", "states") == "-"
    # neutral default path: "Open coastal waters" has no positive/negative
    # keyword → "-"
    assert detect_polarity("Eutrophication", "Open coastal waters",
                           "pressures", "states") == "-"


def test_states_to_impacts_negation_flip():
    """The negation flip (R line 158) zeroes from_is_negative when
    from_analysis.negated AND from_is_negative both hold. This test pins
    the flip behavior with a label whose POST-FLIP polarity output
    differs from its NO-FLIP output -- i.e., a label where the flip
    is observable, not a silent no-op.

    Test pair design uses "Reduced biodiversity" + "Healthy ecosystem
    services" so the expected output "+" is ONLY achievable if the flip
    correctly zeroed from_is_negative (without flip, both flags stay True
    and the matrix returns "-"). Negative control "Pollution" has no
    negation pattern, so no flip; opposite-sign matrix gives "-".
    """
    from sespy.connection_scorer import detect_polarity
    # Positive expected output proves the flip ran.
    assert detect_polarity(
        "Reduced biodiversity", "Healthy ecosystem services",
        "states", "impacts",
    ) == "+"
    # Negative control: a from_name with no negation flag should NOT
    # trigger the flip; matrix sees from_is_negative=True AND
    # to_is_positive=True → opposite-sign → "-".
    assert detect_polarity(
        "Pollution",  # negative_keyword "pollut" but no negation pattern
        "Healthy ecosystem services",
        "states", "impacts",
    ) == "-"


def test_default_fallback_for_unspecified_pair():
    """(drivers, activities) and other pairs without a named branch return
    '+' per R line 186 (default fallback).
    """
    from sespy.connection_scorer import detect_polarity
    # No named branch for (drivers, activities) — falls through to "+".
    assert detect_polarity("Tourism demand", "Coastal development",
                           "drivers", "activities") == "+"
    # Same for the other 4 default-fallback pairs.
    assert detect_polarity("Marine policy", "Tourism demand",
                           "responses", "drivers") == "+"
    assert detect_polarity("Marine policy", "Coastal development",
                           "responses", "activities") == "+"
    assert detect_polarity("Public concern", "Tourism demand",
                           "welfare", "drivers") == "+"
    assert detect_polarity("Public concern", "Marine policy",
                           "welfare", "responses") == "+"


# ---------------------------------------------------------------------------
# Group 4: _generate_smart_connections (6 tests)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "from_slug,polarity,expected_verb",
    [
        # drivers and states are polarity-insensitive (R 514-515, 519-520) —
        # both polarities yield the same verb. The parameterization runs them
        # twice anyway to catch a regression where polarity is accidentally
        # consulted.
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
    """Pin the 7 from-slugs × 2 polarities = 14-case verb table verbatim
    (matches R lines 513-529).

    Critical because the verb table lives only in _select_verb's
    docstring + this test. A typo in either drift would ship silently
    without this parameterized coverage.
    """
    from sespy.connection_scorer import _select_verb
    assert _select_verb(from_slug, polarity) == expected_verb


def _make_element(eid: str, label: str, etype: str):
    """Helper: build a minimal Element for testing without going through
    the wizard's id-prefix machinery."""
    from sespy.data_structure import Element
    return Element(id=eid, label=label, type=etype)


def test_cross_product_pair_generation():
    """2 from-elements x 3 to-elements -> <= 6 candidates pre-filter
    (some may drop via double-negative filter).
    """
    from sespy.connection_scorer import _generate_smart_connections
    from_els = [_make_element("D001", "Tourism", "Drivers"),
                _make_element("D002", "Fishing", "Drivers")]
    to_els = [_make_element("A001", "Recreation", "Activities"),
              _make_element("A002", "Commercial fishing", "Activities"),
              _make_element("A003", "Aquaculture", "Activities")]
    result = _generate_smart_connections(
        from_els, to_els, "drivers", "activities"
    )
    # Cross-product is 2x3=6; double-negative filter doesn't apply (no
    # loss_keywords in any name). All 6 pairs survive the threshold
    # because R's 0.3 floor admits everything.
    assert len(result) == 6


def test_double_negative_filter_uses_loss_keywords():
    """Both names contain loss_keywords substring -> suggestion dropped.
    Names with negative_keywords that are NOT loss_keywords (e.g.,
    'Pollution') survive.
    """
    from sespy.connection_scorer import _generate_smart_connections
    # Both labels have "loss" / "decline" -> loss_keywords match -> dropped.
    from_els = [_make_element("S001", "Loss of biodiversity",
                              "Marine Processes & Functioning")]
    to_els = [_make_element("I001", "Decline in fishery yield",
                            "Ecosystem Services")]
    result = _generate_smart_connections(
        from_els, to_els, "states", "impacts"
    )
    assert result == []  # Filtered out

    # Now: one name has only negative_keywords (not loss_keywords).
    # "Pollution" matches negative_keywords but NOT loss_keywords (loss list
    # has decline/declin/degrad/reduc/damag/destruct/decreas/diminish/
    # deplet/erosion/collapse/extinct/mortality/death/disappear/absent/
    # lack/scarcity -- no 'pollut'). Pair survives.
    from_els = [_make_element("S002", "Pollution",
                              "Marine Processes & Functioning")]
    to_els = [_make_element("I002", "Loss of habitat",
                            "Ecosystem Services")]
    result = _generate_smart_connections(
        from_els, to_els, "states", "impacts"
    )
    assert len(result) == 1


def test_results_sorted_by_confidence_desc():
    """Output is sorted by confidence descending (stable sort).

    Use a to-element with NO keyword matches ('XYZ') so the from-element
    keyword count solely determines confidence. Otherwise the to-element
    contribution masks the gradient and the test still passes via
    sortedness coincidence rather than the property under test.
    """
    from sespy.connection_scorer import _generate_smart_connections
    # to-name "XYZ" has 0 keyword matches in drivers_activities;
    # from-name match counts: "Tourism fishing"=2, "Tourism"=1, "Bicycle"=0.
    # -> confidences {0.9, 0.6, 0.3}.
    from_els = [
        _make_element("D001", "Tourism fishing", "Drivers"),  # 2 stems -> 0.9
        _make_element("D002", "Tourism", "Drivers"),          # 1 stem -> 0.6
        _make_element("D003", "Bicycle", "Drivers"),          # 0 stems -> 0.3
    ]
    to_els = [_make_element("A001", "XYZ", "Activities")]
    result = _generate_smart_connections(
        from_els, to_els, "drivers", "activities"
    )
    confidences = [s.confidence for s in result]
    assert confidences == [0.9, 0.6, 0.3]
    assert confidences == sorted(confidences, reverse=True)


def test_max_count_cap_honored():
    """> 15 candidates -> exactly 15 returned."""
    from sespy.connection_scorer import _generate_smart_connections
    # 4 x 5 = 20 candidates; cap at max_count=15.
    from_els = [_make_element(f"D{i:03d}", f"Tourism{i}", "Drivers")
                for i in range(1, 5)]
    to_els = [_make_element(f"A{i:03d}", f"Recreation{i}", "Activities")
              for i in range(1, 6)]
    result = _generate_smart_connections(
        from_els, to_els, "drivers", "activities",
        max_count=15
    )
    assert len(result) == 15


def test_pair_with_relevance_exactly_03_survives():
    """Pin R's >= threshold semantics at the floor: a pair with
    relevance == 0.3 IS emitted (the gate is vacuous given R's floor).
    Future change to min_relevance > 0.3 (or strict >) would change
    this; the test forces a deliberate decision.
    """
    from sespy.connection_scorer import _generate_smart_connections
    # No keyword matches -> relevance = 0.3 exactly.
    from_els = [_make_element("D001", "Bicycle", "Drivers")]
    to_els = [_make_element("A001", "Letter", "Activities")]
    result = _generate_smart_connections(
        from_els, to_els, "drivers", "activities"
    )
    assert len(result) == 1
    assert result[0].confidence == 0.3


# ---------------------------------------------------------------------------
# Group 5: suggest_connections (the SP3 contract) (9 tests)
# ---------------------------------------------------------------------------


def test_empty_state_returns_empty():
    """state.elements = [] → []."""
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    state = WizardState()
    assert suggest_connections(state) == []


def test_single_element_state_returns_empty():
    """Only one element → no possible cross-product → []."""
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    state = WizardState(
        elements=[_make_element("D001", "Tourism", "Drivers")]
    )
    assert suggest_connections(state) == []


def test_full_state_returns_typed_suggestions():
    """Multi-type state → all items are ConnectionSuggestion, all
    confidence ∈ {0.3, 0.6, 0.9}, all polarity ∈ {'+', '-'}.
    """
    from sespy.data_structure import WizardState, ConnectionSuggestion
    from sespy.connection_scorer import suggest_connections
    state = WizardState(elements=[
        _make_element("D001", "Tourism", "Drivers"),
        _make_element("A001", "Recreation", "Activities"),
        _make_element("P001", "Pollution", "Pressures"),
    ])
    result = suggest_connections(state)
    assert len(result) > 0
    for s in result:
        assert isinstance(s, ConnectionSuggestion)
        assert s.confidence in {0.3, 0.6, 0.9}
        assert s.polarity in {"+", "-"}


def test_per_type_cap_honored_end_to_end():
    """State designed to overflow D→A → ≤ 15 D→A suggestions in output."""
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    # 5 × 5 = 25 D→A candidates; cap at 15.
    drivers = [_make_element(f"D{i:03d}", f"Tourism{i}", "Drivers")
               for i in range(1, 6)]
    activities = [_make_element(f"A{i:03d}", f"Recreation{i}", "Activities")
                  for i in range(1, 6)]
    state = WizardState(elements=drivers + activities)
    result = suggest_connections(state)
    da_count = sum(
        1 for s in result
        if s.source.startswith("D") and s.target.startswith("A")
    )
    assert da_count == 15


def test_all_10_types_yield_high_confidence_suggestions():
    """Designed-to-overlap reference fixture: ≥2 elements per type with
    keyword-rich labels. Assert that for each of the 10 connection types,
    at least one suggestion has confidence >= 0.6 (i.e., ≥ 1 keyword match
    across both names).

    NOTE: A weaker form ("≥1 suggestion per type") would pass trivially
    because R's 0.3 floor admits every cross-product pair. This stronger
    form actually verifies the keyword JSON has overlap-rich coverage —
    if a future JSON edit drops too many stems, this test fails.
    """
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections, _CONN_TYPES
    # IMPORTANT: at least one element per S/I/W group MUST have a label
    # WITHOUT loss_keywords (loss/decline/declin/degrad/reduc/damag/...)
    # because the double-negative filter drops pairs where BOTH labels
    # match loss_keywords.
    state = WizardState(elements=[
        _make_element("D001", "Tourism demand", "Drivers"),
        _make_element("D002", "Fishing economy", "Drivers"),
        _make_element("A001", "Recreational fishing", "Activities"),
        _make_element("A002", "Commercial fishing", "Activities"),
        _make_element("P001", "Pollution from waste", "Pressures"),
        _make_element("P002", "Habitat removal", "Pressures"),
        _make_element("S001", "Decline in biodiversity",
                      "Marine Processes & Functioning"),
        _make_element("S002", "Habitat structure",
                      "Marine Processes & Functioning"),
        _make_element("I001", "Loss of fish abundance",
                      "Ecosystem Services"),
        _make_element("I002", "Cultural service provision",
                      "Ecosystem Services"),
        _make_element("W001", "Reduced food security",
                      "Goods & Benefits"),
        _make_element("W002", "Cultural wellbeing",
                      "Goods & Benefits"),
        _make_element("R001", "Marine policy intervention", "Responses"),
        _make_element("R002", "Fishing quota regulation", "Responses"),
    ])
    result = suggest_connections(state)
    # Map: drivers→D, activities→A, pressures→P, states→S,
    # impacts→I, welfare→W, responses→R.
    high_conf_seen = set()
    for s in result:
        if s.confidence < 0.6:
            continue
        for from_slug, to_slug, key in _CONN_TYPES:
            from_prefix = from_slug[0].upper()
            to_prefix = to_slug[0].upper()
            if s.source.startswith(from_prefix) and s.target.startswith(to_prefix):
                high_conf_seen.add(key)
                break
    expected = {key for _, _, key in _CONN_TYPES}
    missing = expected - high_conf_seen
    assert not missing, (
        f"Missing high-confidence (>=0.6) suggestions for: {sorted(missing)}. "
        f"This may indicate the keyword JSON has insufficient overlap "
        f"with the fixture labels for those connection types."
    )


def test_unknown_element_type_skipped(caplog):
    """Element with .type = 'Foo' (not in _TYPE_TO_SLUG) is skipped without
    raising; one logging.warning per unknown-typed element with element
    id and type in the message for diagnostics.
    """
    import logging
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    state = WizardState(elements=[
        _make_element("X001", "Mystery thing", "Foo"),  # unknown type
        _make_element("D001", "Tourism", "Drivers"),
        _make_element("A001", "Recreation", "Activities"),
    ])
    with caplog.at_level(logging.WARNING, logger="sespy.connection_scorer"):
        result = suggest_connections(state)
    # Suggestions still produced for the valid (D, A) pair:
    assert len(result) >= 1
    # Warning emitted with id + type:
    assert any("X001" in rec.message and "Foo" in rec.message
               for rec in caplog.records)


def test_type_slug_map_is_inverse_of_wizard_map():
    """_TYPE_TO_SLUG exactly inverts ELEMENT_TYPE_MAP."""
    from sespy.data_structure import ELEMENT_TYPE_MAP
    from sespy.connection_scorer import _TYPE_TO_SLUG
    for slug, type_str in ELEMENT_TYPE_MAP.items():
        assert _TYPE_TO_SLUG[type_str] == slug
    assert len(_TYPE_TO_SLUG) == len(ELEMENT_TYPE_MAP)


def test_polarity_default_fallback_returns_positive():
    """Pair of (drivers, activities) — one of the 5 type-pairs without
    a named branch — returns '+' regardless of name content (R line 186
    fallback). Distinct from test_default_fallback_for_unspecified_pair
    in Group 3 by being end-to-end through suggest_connections.
    """
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    state = WizardState(elements=[
        _make_element("D001", "Tourism", "Drivers"),
        _make_element("A001", "Recreation", "Activities"),
    ])
    result = suggest_connections(state)
    da_polarities = {
        s.polarity for s in result
        if s.source.startswith("D") and s.target.startswith("A")
    }
    assert da_polarities == {"+"}


def test_no_wizard_import_in_connection_scorer():
    """Defensive: parse sespy/connection_scorer.py via AST and assert
    no top-level OR lazy (function-body) wizard import exists.
    Path is anchored to this file's location (Path(__file__)) so
    the test works regardless of pytest's cwd.
    """
    import ast
    from pathlib import Path
    src_path = (
        Path(__file__).resolve().parent.parent
        / "sespy" / "connection_scorer.py"
    )
    src = src_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "wizard" and node.level == 1:
                pytest.fail(
                    f"connection_scorer.py:{node.lineno} imports from "
                    f".wizard -- re-introduces the import cycle that "
                    f"ELEMENT_TYPE_MAP relocation broke; see spec §6"
                )
            if node.module == "sespy.wizard":
                pytest.fail(
                    f"connection_scorer.py:{node.lineno} imports from "
                    f"sespy.wizard -- re-introduces the import cycle"
                )
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("sespy.wizard", "wizard"):
                    pytest.fail(
                        f"connection_scorer.py:{node.lineno} imports "
                        f"sespy.wizard -- re-introduces the import cycle"
                    )
