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
