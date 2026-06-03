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
