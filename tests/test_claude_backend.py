"""Tests for sespy.claude_backend (SP4)."""
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from typing import get_args

import pytest

from sespy.claude_backend import (
    ClaudeBackendError,
    ClaudeErrorReason,
    DropReason,
    ValidationOutcome,
    _REASON_TO_I18N,
)
from sespy.data_structure import ConnectionSuggestion


def test_claude_backend_error_is_frozen_dataclass_exception():
    """ClaudeBackendError is the single error type — Literal-tagged reason."""
    e = ClaudeBackendError(reason="auth")
    assert isinstance(e, Exception)
    assert e.reason == "auth"
    assert e.status_code is None
    assert e.retry_after is None
    assert e.text_content is None
    assert str(e) == "auth"
    with pytest.raises(FrozenInstanceError):
        e.reason = "rate_limit"  # type: ignore[misc]


def test_claude_error_reason_has_seven_members():
    expected = {"auth", "rate_limit", "timeout", "network",
                "status", "shape", "too_many"}
    assert set(get_args(ClaudeErrorReason)) == expected


def test_drop_reason_has_nine_members():
    expected = {"non_dict", "missing_key",
                "unknown_source", "unknown_target",
                "self_loop", "invalid_pair",
                "invalid_polarity", "non_numeric_confidence",
                "empty_rationale"}
    assert set(get_args(DropReason)) == expected


def test_validation_outcome_is_frozen():
    o = ValidationOutcome(
        suggestions=[],
        raw_count=0,
        drops_by_reason={r: 0 for r in get_args(DropReason)},
    )
    assert o.suggestions == []
    assert o.raw_count == 0
    assert isinstance(o.drops_by_reason, Mapping)
    with pytest.raises(FrozenInstanceError):
        o.raw_count = 1  # type: ignore[misc]


def test_REASON_TO_I18N_covers_every_ClaudeErrorReason():
    """Every Literal value maps to an i18n key. The sdk_missing key is
    intentionally absent (separate code path in the wizard module's
    ImportError handler). Tests for the full bidirectional check + the
    sdk_missing carve-out live in Task 14 against core.json."""
    assert set(_REASON_TO_I18N.keys()) == set(get_args(ClaudeErrorReason))
    for v in _REASON_TO_I18N.values():
        assert v.startswith("wizard.claude_error_")


from sespy.claude_backend import _SYSTEM_PROMPT, _TOOL_DEFINITION, _TOOL_NAME


def test_system_prompt_mentions_tool_by_name():
    """The prompt must reference the tool we force via tool_choice."""
    assert _TOOL_NAME in _SYSTEM_PROMPT
    assert "record_connection_suggestions" == _TOOL_NAME


def test_system_prompt_lists_all_10_directions():
    """Rule 1 lists the 10 valid type-pair directions verbatim."""
    for direction in ["D->A", "A->P", "P->S", "S->I", "I->W",
                      "R->P", "R->D", "R->A", "W->D", "W->R"]:
        assert direction in _SYSTEM_PROMPT


def test_system_prompt_pins_confidence_enum_values():
    """Rule 3 anchors confidence to discrete {0.3, 0.5, 0.7, 0.9}."""
    for value in ["0.3", "0.5", "0.7", "0.9"]:
        assert value in _SYSTEM_PROMPT


def test_system_prompt_contains_few_shot_block():
    """Round-6 added a <good_examples> block — pin its presence."""
    assert "<good_examples>" in _SYSTEM_PROMPT
    assert "</good_examples>" in _SYSTEM_PROMPT


def test_tool_definition_name_matches_TOOL_NAME():
    """Single source of truth — _TOOL_DEFINITION['name'] == _TOOL_NAME."""
    assert _TOOL_DEFINITION["name"] == _TOOL_NAME


def test_tool_definition_confidence_is_enum():
    """Schema constrains confidence to {0.3, 0.5, 0.7, 0.9}."""
    sug_props = _TOOL_DEFINITION["input_schema"]["properties"]["suggestions"]["items"]["properties"]
    assert sug_props["confidence"]["enum"] == [0.3, 0.5, 0.7, 0.9]


def test_tool_definition_polarity_is_enum():
    sug_props = _TOOL_DEFINITION["input_schema"]["properties"]["suggestions"]["items"]["properties"]
    assert sug_props["polarity"]["enum"] == ["+", "-"]


def test_tool_definition_rationale_max_length_150():
    sug_props = _TOOL_DEFINITION["input_schema"]["properties"]["suggestions"]["items"]["properties"]
    assert sug_props["rationale"]["maxLength"] == 150


def test_tool_definition_max_items_150():
    arr = _TOOL_DEFINITION["input_schema"]["properties"]["suggestions"]
    assert arr["maxItems"] == 150


def test_tool_definition_additional_properties_false():
    """Schema-level defence — reject model-invented fields."""
    items = _TOOL_DEFINITION["input_schema"]["properties"]["suggestions"]["items"]
    assert items["additionalProperties"] is False
    assert _TOOL_DEFINITION["input_schema"]["additionalProperties"] is False


from sespy.claude_backend import _build_user_message
from sespy.data_structure import Element, WizardState


def _make_state(**overrides):
    """Helper: build a minimal WizardState with sensible defaults."""
    defaults = {
        "regional_sea": "baltic",
        "ecosystem_type": "Coastal lagoon",
        "countries": ["LT", "LV"],
        "main_issue": ["Eutrophication"],
        "elements": [
            Element(id="D001", type="Drivers", label="Agricultural runoff"),
            Element(id="A001", type="Activities", label="Industrial farming"),
            Element(id="P001", type="Pressures", label="Nutrient loading"),
        ],
    }
    defaults.update(overrides)
    return WizardState(**defaults)


def test_user_message_includes_all_5_wizard_state_fields():
    state = _make_state()
    msg = _build_user_message(state)
    assert "Regional sea: baltic" in msg
    assert "Ecosystem type: Coastal lagoon" in msg
    assert "Countries: LT, LV" in msg
    assert "Main issue(s): Eutrophication" in msg
    assert "## DRIVERS" in msg


def test_user_message_skips_empty_element_groups():
    """No `## RESPONSES` header when there are no Responses elements."""
    state = _make_state()  # only D, A, P
    msg = _build_user_message(state)
    assert "## RESPONSES" not in msg
    assert "## STATES" not in msg


def test_user_message_groups_in_dapsiwrm_order():
    elements = [
        Element(id="W1", type="Goods & Benefits", label="welfare element"),
        Element(id="D1", type="Drivers", label="driver element"),
        Element(id="P1", type="Pressures", label="pressure element"),
    ]
    state = _make_state(elements=elements)
    msg = _build_user_message(state)
    # Even though elements list ordered W, D, P, output groups must be
    # in DAPSI(W)R(M) canonical order: D before P before W.
    d_pos = msg.index("## DRIVERS")
    p_pos = msg.index("## PRESSURES")
    w_pos = msg.index("## WELFARE")
    assert d_pos < p_pos < w_pos


def test_user_message_uses_id_label_format():
    """Exact line shape: - id="X" label="Y" — quoted to clarify which
    field is opaque (id) vs descriptive (label)."""
    state = _make_state()
    msg = _build_user_message(state)
    assert '- id="D001" label="Agricultural runoff"' in msg


def test_user_message_handles_empty_optional_fields():
    state = _make_state(regional_sea="", countries=[], main_issue=[])
    msg = _build_user_message(state)
    assert "Regional sea: (unspecified)" in msg
    assert "Countries: (unspecified)" in msg
    assert "Main issue(s): (unspecified)" in msg


def test_user_message_includes_use_ids_instruction():
    state = _make_state()
    msg = _build_user_message(state)
    assert "Use IDs (not labels) in source and target." in msg


from types import SimpleNamespace

from sespy.claude_backend import _extract_tool_input


def _mock_response(*content_blocks):
    """Helper: build a SimpleNamespace fake of an Anthropic Message."""
    return SimpleNamespace(content=list(content_blocks))


def _tool_use_block(suggestions):
    return SimpleNamespace(
        type="tool_use",
        input={"suggestions": suggestions},
    )


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def test_extract_returns_suggestions_list_from_first_tool_use():
    sugs = [{"source": "d1", "target": "a1"}]
    response = _mock_response(_tool_use_block(sugs))
    assert _extract_tool_input(response) == sugs


def test_extract_uses_last_when_two_tool_use_blocks():
    """Last-write-wins for duplicate tool_use blocks (rare; warn on it)."""
    first = [{"source": "d1", "target": "a1"}]
    last = [{"source": "d2", "target": "a2"}]
    response = _mock_response(
        _tool_use_block(first),
        _tool_use_block(last),
    )
    assert _extract_tool_input(response) == last


def test_extract_raises_shape_when_no_tool_use_block():
    response = _mock_response(_text_block("I cannot comply."))
    with pytest.raises(ClaudeBackendError) as excinfo:
        _extract_tool_input(response)
    assert excinfo.value.reason == "shape"
    assert "I cannot comply" in (excinfo.value.text_content or "")


def test_extract_raises_shape_when_no_blocks_at_all():
    response = _mock_response()  # empty content
    with pytest.raises(ClaudeBackendError) as excinfo:
        _extract_tool_input(response)
    assert excinfo.value.reason == "shape"
    assert "had no text either" in (excinfo.value.text_content or "")


def test_extract_raises_shape_when_input_not_dict():
    block = SimpleNamespace(type="tool_use", input="not a dict")
    response = _mock_response(block)
    with pytest.raises(ClaudeBackendError) as excinfo:
        _extract_tool_input(response)
    assert excinfo.value.reason == "shape"
    assert "is not dict" in (excinfo.value.text_content or "")


def test_extract_raises_shape_when_suggestions_not_list():
    block = SimpleNamespace(type="tool_use", input={"suggestions": "string"})
    response = _mock_response(block)
    with pytest.raises(ClaudeBackendError) as excinfo:
        _extract_tool_input(response)
    assert excinfo.value.reason == "shape"
    assert "is not list" in (excinfo.value.text_content or "")


from sespy.claude_backend import _validate_and_coerce


def _valid_suggestion(**overrides):
    """A minimum-valid suggestion dict for parametrized happy-path tests."""
    base = {
        "source": "D001",
        "target": "A001",
        "polarity": "+",
        "confidence": 0.9,
        "rationale": "drives the activity",
    }
    base.update(overrides)
    return base


def _three_elements():
    return [
        Element(id="D001", type="Drivers", label="X"),
        Element(id="A001", type="Activities", label="Y"),
        Element(id="P001", type="Pressures", label="Z"),
    ]


@pytest.mark.parametrize("invalid_field, invalid_value, expected_drop", [
    ("source",     "UNKNOWN_ID",   "unknown_source"),
    ("target",     "UNKNOWN_ID",   "unknown_target"),
    ("source",     "A001",         "self_loop"),  # source == target after override
])
def test_drops_invalid_id_field(invalid_field, invalid_value, expected_drop):
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    if expected_drop == "self_loop":
        sug = _valid_suggestion(source="A001", target="A001")
    else:
        sug = _valid_suggestion(**{invalid_field: invalid_value})
    outcome = _validate_and_coerce([sug], valid_ids, elements)
    assert outcome.suggestions == []
    assert outcome.drops_by_reason[expected_drop] == 1


def test_drops_invalid_type_pair_states_to_drivers():
    """States -> Drivers is not in the 10 valid type-pair directions."""
    elements = [
        Element(id="S001", type="Marine Processes & Functioning", label="X"),
        Element(id="D001", type="Drivers", label="Y"),
    ]
    valid_ids = {el.id for el in elements}
    sug = _valid_suggestion(source="S001", target="D001")
    outcome = _validate_and_coerce([sug], valid_ids, elements)
    assert outcome.suggestions == []
    assert outcome.drops_by_reason["invalid_pair"] == 1


def test_drops_invalid_polarity():
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    sug = _valid_suggestion(polarity="garbage")
    outcome = _validate_and_coerce([sug], valid_ids, elements)
    assert outcome.suggestions == []
    assert outcome.drops_by_reason["invalid_polarity"] == 1


@pytest.mark.parametrize("bad_confidence", [
    True,                  # bool — must be rejected BEFORE int/float check
    False,
    "0.9",                 # str
    None,                  # None
    [0.9],                 # list
    float("nan"),          # NaN — clamp comparisons NaN-poison
    float("inf"),
    float("-inf"),
])
def test_drops_non_numeric_confidence(bad_confidence):
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    sug = _valid_suggestion(confidence=bad_confidence)
    outcome = _validate_and_coerce([sug], valid_ids, elements)
    assert outcome.suggestions == []
    assert outcome.drops_by_reason["non_numeric_confidence"] == 1


@pytest.mark.parametrize("conf, clamped", [
    (-0.5, 0.0),
    (1.5,  1.0),
])
def test_clamps_confidence_out_of_range(conf, clamped):
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    sug = _valid_suggestion(confidence=conf)
    outcome = _validate_and_coerce([sug], valid_ids, elements)
    assert len(outcome.suggestions) == 1
    assert outcome.suggestions[0].confidence == clamped


@pytest.mark.parametrize("rationale", ["", "   ", "\t\n"])
def test_drops_empty_rationale(rationale):
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    sug = _valid_suggestion(rationale=rationale)
    outcome = _validate_and_coerce([sug], valid_ids, elements)
    assert outcome.suggestions == []
    assert outcome.drops_by_reason["empty_rationale"] == 1


def test_drops_non_dict_suggestion():
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    outcome = _validate_and_coerce(["not a dict"], valid_ids, elements)
    assert outcome.suggestions == []
    assert outcome.drops_by_reason["non_dict"] == 1


def test_drops_missing_key():
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    sug = {"source": "D001"}  # missing target, polarity, etc.
    outcome = _validate_and_coerce([sug], valid_ids, elements)
    assert outcome.suggestions == []
    assert outcome.drops_by_reason["missing_key"] == 1


def test_drop_precedence_unknown_source_beats_invalid_polarity():
    """Top-down precedence — first failing row in the §3.7 table wins."""
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    sug = _valid_suggestion(source="UNKNOWN", polarity="garbage")
    outcome = _validate_and_coerce([sug], valid_ids, elements)
    assert outcome.suggestions == []
    assert outcome.drops_by_reason["unknown_source"] == 1
    assert outcome.drops_by_reason["invalid_polarity"] == 0


def test_drops_by_reason_contains_all_DropReason_members_with_all_valid_input():
    """All-keys invariant: every Literal member is a key (zero if not encountered).
    Catches the defaultdict-trap where never-seen keys are absent on serialization."""
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    sug = _valid_suggestion()  # all-valid
    outcome = _validate_and_coerce([sug], valid_ids, elements)
    assert len(outcome.suggestions) == 1
    for reason in get_args(DropReason):
        assert reason in outcome.drops_by_reason
        assert outcome.drops_by_reason[reason] == 0


def test_preserves_model_emitted_order_after_drops():
    """5 entries; entry 2 (index 1) is invalid; output is [0, 2, 3, 4]."""
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    raw = [
        _valid_suggestion(source="D001", target="A001"),  # 0 valid
        _valid_suggestion(source="UNKNOWN"),               # 1 invalid
        _valid_suggestion(source="D001", target="P001",
                          polarity="-"),                  # 2 valid (D->P invalid pair?)
        _valid_suggestion(source="A001", target="P001",
                          rationale="r3"),                # 3 valid
        _valid_suggestion(source="A001", target="P001",
                          polarity="-",
                          rationale="r4"),                # 4 valid
    ]
    # Note: D->P is invalid_pair. The valid surviving entries are 0, 3, 4.
    outcome = _validate_and_coerce(raw, valid_ids, elements)
    assert len(outcome.suggestions) == 3
    assert outcome.suggestions[0].source == "D001"
    assert outcome.suggestions[0].target == "A001"
    assert outcome.suggestions[1].rationale == "r3"
    assert outcome.suggestions[2].rationale == "r4"


def test_returns_empty_outcome_when_all_invalid():
    elements = _three_elements()
    valid_ids = {el.id for el in elements}
    raw = [_valid_suggestion(source="UNKNOWN"), {"missing": "fields"}]
    outcome = _validate_and_coerce(raw, valid_ids, elements)
    assert outcome.suggestions == []
    assert outcome.raw_count == 2
    assert outcome.drops_by_reason["unknown_source"] == 1
    assert outcome.drops_by_reason["missing_key"] == 1
