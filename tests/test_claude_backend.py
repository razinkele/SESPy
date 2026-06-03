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


def test_claude_backend_error_is_raisable_exception():
    """ClaudeBackendError is the single error type — Literal-tagged reason.

    It must NOT be a frozen dataclass: Shiny's @reactive.extended_task sets
    `exc.__traceback__` in pure Python while propagating a task error, which a
    frozen __setattr__ would reject with FrozenInstanceError (regression: the
    SP4 e2e auth-error path failed this way until the dataclass was un-frozen).
    """
    e = ClaudeBackendError(reason="auth")
    assert isinstance(e, Exception)
    assert e.reason == "auth"
    assert e.status_code is None
    assert e.retry_after is None
    assert e.text_content is None
    assert str(e) == "auth"
    # Must support the pure-Python attribute assignment Python's exception
    # machinery performs during propagation through extended_task (the guard).
    try:
        raise e
    except ClaudeBackendError as caught:
        assert caught.__traceback__ is not None
        caught.__traceback__ = None  # explicit pure-Python __traceback__ set


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


from unittest.mock import patch, MagicMock
import logging

import anthropic
import httpx


def _make_anthropic_response(suggestions, usage_in=100, usage_out=200):
    return SimpleNamespace(
        content=[SimpleNamespace(
            type="tool_use",
            input={"suggestions": suggestions},
        )],
        usage=SimpleNamespace(
            input_tokens=usage_in, output_tokens=usage_out,
        ),
    )


def _make_rate_limit_error(retry_after_header: str | None):
    headers = {"retry-after": retry_after_header} if retry_after_header else {}
    response = httpx.Response(
        status_code=429, headers=headers,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return anthropic.RateLimitError(
        message="rate limited", response=response, body=None,
    )


@pytest.fixture
def state():
    return WizardState(
        regional_sea="baltic",
        ecosystem_type="Coastal lagoon",
        countries=["LT"],
        main_issue=["Eutrophication"],
        elements=[
            Element(id="D001", type="Drivers", label="X"),
            Element(id="A001", type="Activities", label="Y"),
        ],
    )


def test_suggest_connections_calls_with_default_model(state):
    from sespy.claude_backend import suggest_connections
    sugs = [{"source": "D001", "target": "A001", "polarity": "+",
             "confidence": 0.9, "rationale": "test rationale"}]
    with patch("anthropic.Anthropic") as MockAnth:
        client = MockAnth.return_value
        client.messages.create.return_value = _make_anthropic_response(sugs)
        outcome = suggest_connections(state)
    assert len(outcome.suggestions) == 1
    create_kwargs = client.messages.create.call_args.kwargs
    assert create_kwargs["model"] == "claude-sonnet-4-6"
    assert create_kwargs["max_tokens"] == 16384
    assert create_kwargs["tool_choice"] == {"type": "tool", "name": _TOOL_NAME}


def test_suggest_connections_env_override_model(state, monkeypatch):
    from sespy.claude_backend import suggest_connections
    monkeypatch.setenv("SESPY_CLAUDE_MODEL", "claude-opus-test")
    with patch("anthropic.Anthropic") as MockAnth:
        client = MockAnth.return_value
        client.messages.create.return_value = _make_anthropic_response([])
        suggest_connections(state)
    assert client.messages.create.call_args.kwargs["model"] == "claude-opus-test"


def test_suggest_connections_empty_string_env_uses_default(state, monkeypatch):
    """`os.environ.get(key, default)` returns '' for explicitly-empty value;
    the `or _DEFAULT_MODEL` chain handles this."""
    from sespy.claude_backend import suggest_connections
    monkeypatch.setenv("SESPY_CLAUDE_MODEL", "")
    with patch("anthropic.Anthropic") as MockAnth:
        client = MockAnth.return_value
        client.messages.create.return_value = _make_anthropic_response([])
        suggest_connections(state)
    assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-4-6"


def test_suggest_connections_too_many_elements_short_circuits():
    from sespy.claude_backend import suggest_connections
    big_state = WizardState(
        regional_sea="x", ecosystem_type="x", countries=[], main_issue=[],
        elements=[Element(id=f"X{i}", type="Drivers", label="x")
                  for i in range(201)],
    )
    with patch("anthropic.Anthropic") as MockAnth:
        with pytest.raises(ClaudeBackendError) as excinfo:
            suggest_connections(big_state)
        # SDK never called.
        MockAnth.return_value.messages.create.assert_not_called()
    assert excinfo.value.reason == "too_many"


@pytest.mark.parametrize("sdk_exc, expected_reason", [
    (anthropic.AuthenticationError(
        message="bad key",
        response=httpx.Response(status_code=401,
                                request=httpx.Request("POST", "https://api.anthropic.com")),
        body=None), "auth"),
    (anthropic.APITimeoutError(
        request=httpx.Request("POST", "https://api.anthropic.com")), "timeout"),
    (anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com")), "network"),
])
def test_suggest_connections_maps_SDK_exceptions(state, sdk_exc, expected_reason):
    from sespy.claude_backend import suggest_connections
    with patch("anthropic.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.side_effect = sdk_exc
        with pytest.raises(ClaudeBackendError) as excinfo:
            suggest_connections(state)
    assert excinfo.value.reason == expected_reason


def test_suggest_connections_rate_limit_extracts_retry_after_from_header(state):
    from sespy.claude_backend import suggest_connections
    with patch("anthropic.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.side_effect = (
            _make_rate_limit_error("30")
        )
        with pytest.raises(ClaudeBackendError) as excinfo:
            suggest_connections(state)
    assert excinfo.value.reason == "rate_limit"
    assert excinfo.value.retry_after == 30.0


def test_suggest_connections_rate_limit_no_retry_after_header(state):
    from sespy.claude_backend import suggest_connections
    with patch("anthropic.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.side_effect = (
            _make_rate_limit_error(None)
        )
        with pytest.raises(ClaudeBackendError) as excinfo:
            suggest_connections(state)
    assert excinfo.value.reason == "rate_limit"
    assert excinfo.value.retry_after is None


def test_suggest_connections_status_error_carries_status_code(state):
    from sespy.claude_backend import suggest_connections
    response = httpx.Response(
        status_code=500,
        request=httpx.Request("POST", "https://api.anthropic.com"),
    )
    with patch("anthropic.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.side_effect = (
            anthropic.APIStatusError(
                message="server error", response=response, body=None,
            )
        )
        with pytest.raises(ClaudeBackendError) as excinfo:
            suggest_connections(state)
    assert excinfo.value.reason == "status"
    assert excinfo.value.status_code == 500


def test_suggest_connections_unexpected_post_SDK_exception_wraps_as_shape(state):
    """Round-8 fix: exceptions from _validate_and_coerce (e.g., a future
    KeyError on _TYPE_TO_SLUG) MUST be wrapped, otherwise the finally
    block misclassifies as status=ok."""
    from sespy.claude_backend import suggest_connections
    sugs = [{"source": "D001", "target": "A001", "polarity": "+",
             "confidence": 0.9, "rationale": "ok"}]
    with patch("anthropic.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.return_value = (
            _make_anthropic_response(sugs)
        )
        with patch("sespy.claude_backend._validate_and_coerce",
                   side_effect=KeyError("synthetic")):
            with pytest.raises(ClaudeBackendError) as excinfo:
                suggest_connections(state)
    assert excinfo.value.reason == "shape"
    assert "KeyError" in (excinfo.value.text_content or "")


def test_INFO_log_emitted_on_success(state, caplog):
    from sespy.claude_backend import suggest_connections
    sugs = [{"source": "D001", "target": "A001", "polarity": "+",
             "confidence": 0.9, "rationale": "ok"}]
    with patch("anthropic.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.return_value = (
            _make_anthropic_response(sugs, usage_in=123, usage_out=456)
        )
        with caplog.at_level(logging.INFO, logger="sespy.claude_backend"):
            suggest_connections(state)
    matches = [r for r in caplog.records if "claude_backend.call" in r.message]
    assert len(matches) == 1
    assert "status=ok" in matches[0].getMessage()
    assert "tokens_in=123" in matches[0].getMessage()


def test_INFO_log_emitted_on_too_many_path(caplog):
    from sespy.claude_backend import suggest_connections
    big_state = WizardState(
        regional_sea="x", ecosystem_type="x", countries=[], main_issue=[],
        elements=[Element(id=f"X{i}", type="Drivers", label="x")
                  for i in range(201)],
    )
    with caplog.at_level(logging.INFO, logger="sespy.claude_backend"):
        with pytest.raises(ClaudeBackendError):
            suggest_connections(big_state)
    matches = [r for r in caplog.records if "claude_backend.call" in r.message]
    assert any("status=error reason=too_many" in r.getMessage() for r in matches)


def test_anthropic_client_constructed_with_max_retries_zero(state):
    """The 'no retries' cost-bounding contract from spec §1.4: SDK
    defaults to max_retries=2; we must override to 0 to keep a single
    user click bounded to one paid API call."""
    from sespy.claude_backend import suggest_connections
    sugs = [{"source": "D001", "target": "A001", "polarity": "+",
             "confidence": 0.9, "rationale": "ok"}]
    with patch("anthropic.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.return_value = (
            _make_anthropic_response(sugs)
        )
        suggest_connections(state)
    # Constructor was called with max_retries=0.
    constructor_kwargs = MockAnth.call_args.kwargs
    assert constructor_kwargs.get("max_retries") == 0, (
        "Anthropic client must be constructed with max_retries=0 to "
        "enforce the no-retries cost-bounding contract."
    )


def test_messages_create_called_exactly_once_on_rate_limit(state):
    """No retries on rate_limit. The SDK with max_retries=0 should
    NOT retry the API call; the wrapper should propagate the
    RateLimitError after exactly one attempt."""
    from sespy.claude_backend import suggest_connections
    with patch("anthropic.Anthropic") as MockAnth:
        client = MockAnth.return_value
        client.messages.create.side_effect = _make_rate_limit_error("30")
        with pytest.raises(ClaudeBackendError):
            suggest_connections(state)
    assert client.messages.create.call_count == 1, (
        "Expected exactly 1 call (no retries); got "
        f"{client.messages.create.call_count}"
    )


def test_INFO_log_classification_on_shape_error(state, caplog):
    """Round-5 bug-fix pin: shape error MUST log status=error reason=shape,
    NOT status=ok. Without the post-SDK except wrapper, error_reason stays
    None and the finally misclassifies."""
    from sespy.claude_backend import suggest_connections
    sugs = [{"source": "D001", "target": "A001", "polarity": "+",
             "confidence": 0.9, "rationale": "ok"}]
    with patch("anthropic.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.return_value = (
            _make_anthropic_response(sugs)
        )
        with patch("sespy.claude_backend._validate_and_coerce",
                   side_effect=ClaudeBackendError(reason="shape", text_content="injected")):
            with caplog.at_level(logging.INFO, logger="sespy.claude_backend"):
                with pytest.raises(ClaudeBackendError):
                    suggest_connections(state)
    matches = [r for r in caplog.records if "claude_backend.call" in r.message]
    assert any("status=error reason=shape" in r.getMessage() for r in matches)


# ---------------------------------------------------------------------------
# Group 6 — module-import contract tests
# ---------------------------------------------------------------------------
import subprocess
import sys


def test_module_import_does_not_eagerly_import_anthropic():
    """Fresh subprocess: importing sespy.claude_backend must NOT load
    anthropic (the import is lazy inside suggest_connections)."""
    result = subprocess.run(
        [sys.executable, "-c",
         "import sespy.claude_backend; import sys; "
         "assert 'anthropic' not in sys.modules, 'anthropic loaded eagerly'; "
         "print('ok')"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_module_imports_with_no_env_var_set(monkeypatch):
    """Module-import time must NOT depend on ANTHROPIC_API_KEY being set."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("SESPY_CLAUDE_MODEL", raising=False)
    # Re-import under cleared env (already imported in this test process,
    # but verify the contract: no env reads at import).
    import importlib
    import sespy.claude_backend
    importlib.reload(sespy.claude_backend)
    assert sespy.claude_backend._DEFAULT_MODEL == "claude-sonnet-4-6"


import json
from pathlib import Path


def _load_core_json():
    path = Path(__file__).parent.parent / "sespy" / "translations" / "core.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)["translation"]


def test_REASON_TO_I18N_bidirectional_check():
    """Every Literal value has an i18n key; no orphan wizard.claude_error_*
    keys in core.json beyond the map values + sdk_missing carve-out."""
    translations = _load_core_json()
    # Forward: every map value exists.
    for key in _REASON_TO_I18N.values():
        assert key in translations, f"missing i18n key: {key}"
    # Backward: no orphan wizard.claude_error_* keys.
    error_keys = {k for k in translations if k.startswith("wizard.claude_error_")}
    expected = set(_REASON_TO_I18N.values()) | {"wizard.claude_error_sdk_missing"}
    assert error_keys == expected, f"orphan or missing: {error_keys ^ expected}"


def test_all_sp4_non_error_i18n_keys_exist_in_core_json():
    """The 19 non-error keys (5 button/UI + 10 consent modal + 2 table
    headers + 2 dedup/read-failure)."""
    translations = _load_core_json()
    expected = {
        "wizard.claude_generate_button",
        "wizard.claude_generating",
        "wizard.claude_returned_zero",
        "wizard.claude_retry_after",
        "wizard.claude_drops_badge",
        "wizard.claude_consent_title",
        "wizard.claude_consent_body",
        "wizard.claude_consent_field_sea",
        "wizard.claude_consent_field_ecosystem",
        "wizard.claude_consent_field_countries",
        "wizard.claude_consent_field_issues",
        "wizard.claude_consent_field_elements",
        "wizard.claude_consent_privacy_note",
        "wizard.claude_consent_confirm",
        "wizard.claude_consent_cancel",
        "wizard.suggestions_rule_based_n",
        "wizard.suggestions_claude_n",
        "wizard.duplicates_resolved_n",
        "wizard.read_failures_n",
    }
    for key in expected:
        assert key in translations, f"missing i18n key: {key}"
        # Each must be a per-language object with all 9 languages.
        value = translations[key]
        assert isinstance(value, dict)
        for lang in ["en", "es", "fr", "de", "lt", "pt", "it", "no", "el"]:
            assert lang in value, f"key {key} missing language {lang}"
