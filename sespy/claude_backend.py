"""Claude API backend for the AI-ISA wizard's connection-suggestion step
(SP4). Pure Python module — no Shiny imports. Called from
sespy.modules.ai_isa_wizard via @reactive.extended_task.

Contract: same signature shape as SP3's connection_scorer.suggest_connections,
but returns a ValidationOutcome envelope (suggestions + drop counts).

The lazy `import anthropic` inside suggest_connections (Task 12) keeps this
module importable even if the Anthropic SDK is not installed — useful for
test environments and the `claude_error_sdk_missing` graceful-degradation
path in the wizard module.
"""
from __future__ import annotations

import logging
import math
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from .data_structure import (
    Element,
    ELEMENT_TYPE_MAP,
    Slug,
    WizardState,
    ConnectionSuggestion,
    _VALID_TYPE_PAIRS,
)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_OUTPUT_TOKENS = 16384
_TIMEOUT_SECONDS = 60.0
_MAX_ELEMENTS = 200    # hard cap; raises ClaudeBackendError(reason="too_many")
_TOOL_NAME = "record_connection_suggestions"

# Inverse of ELEMENT_TYPE_MAP — Element.type (e.g., "Drivers") → Slug ("drivers").
_TYPE_TO_SLUG: Mapping[str, Slug] = {v: k for k, v in ELEMENT_TYPE_MAP.items()}

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Drop-reason Literal + ValidationOutcome envelope (used by Task 7's
# _validate_and_coerce; defined here so Task 3 tests can pin them).
# ---------------------------------------------------------------------------

DropReason = Literal[
    "non_dict", "missing_key",
    "unknown_source", "unknown_target",
    "self_loop", "invalid_pair",
    "invalid_polarity", "non_numeric_confidence",
    "empty_rationale",
]


@dataclass(frozen=True)
class ValidationOutcome:
    """Envelope returned by _validate_and_coerce.

    suggestions: kept entries, in model-emitted order (drops collapse the list).
    raw_count: total number of model-emitted entries (pre-validation).
    drops_by_reason: count per DropReason. INVARIANT — every Literal member
        is a key in this mapping (zero if not encountered). Use
        dict.fromkeys(get_args(DropReason), 0) at the start of
        _validate_and_coerce to satisfy this invariant.
    """
    suggestions: list[ConnectionSuggestion]
    raw_count: int
    drops_by_reason: Mapping[DropReason, int]


# ---------------------------------------------------------------------------
# Error taxonomy — single dataclass with Literal-tagged reason. The wizard
# module's observer dispatches on `error.reason` via the i18n map below.
# ---------------------------------------------------------------------------

ClaudeErrorReason = Literal[
    "auth", "rate_limit", "timeout", "network",
    "status", "shape", "too_many",
]


@dataclass(frozen=True)
class ClaudeBackendError(Exception):
    reason: ClaudeErrorReason
    status_code: int | None = None        # for reason='status'
    retry_after: float | None = None      # for reason='rate_limit'
    text_content: str | None = None       # for reason='shape' (model output captured for diagnosis)

    def __str__(self) -> str:
        return self.reason


# ---------------------------------------------------------------------------
# i18n key map — used by the wizard module's observer to dispatch
# ClaudeBackendError to the correct toast string. The
# `wizard.claude_error_sdk_missing` key is intentionally absent: the
# SDK-missing path is caught as ImportError/ModuleNotFoundError in the
# wizard module and calls t() directly (separate code path).
# ---------------------------------------------------------------------------

_REASON_TO_I18N: Mapping[ClaudeErrorReason, str] = {
    "auth":       "wizard.claude_error_auth",
    "rate_limit": "wizard.claude_error_rate_limit",
    "timeout":    "wizard.claude_error_timeout",
    "network":    "wizard.claude_error_network",
    "status":     "wizard.claude_error_other",
    "shape":      "wizard.claude_error_shape",
    "too_many":   "wizard.claude_error_too_many",
}
