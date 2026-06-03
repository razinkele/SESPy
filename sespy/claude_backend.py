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


# ---------------------------------------------------------------------------
# System prompt (~800 tokens with few-shot examples). Sent on every call.
# `cache_control={"type": "ephemeral"}` is set on the system block in the
# orchestrator (Task 12) — silently no-ops below the model's threshold
# (2,048 tokens for Sonnet 4.6) but is forward-compatible.
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert in social-ecological systems analysis using the
DAPSI(W)R(M) framework (Drivers, Activities, Pressures, States,
Impacts, Welfare, Responses), with depth in marine, estuarine, and
coastal contexts. You suggest causal connections between elements of
a system map.

Given a project's element list grouped by DAPSI(W)R(M) type plus
regional context, propose plausible connections following these rules:

1. Allowed type-pair directions (10 valid):
   D->A, A->P, P->S, S->I, I->W,
   R->P, R->D, R->A, W->D, W->R.
   Connections in any other direction are NOT VALID. Don't neglect
   the feedback-direction pairs (R->*, W->*) — they are often the
   most useful suggestions.

2. Polarity — the SIGN of the causal effect, not whether both
   elements grow:
   "+" = an increase in source CAUSES an increase in target;
   "-" = an increase in source CAUSES a DECREASE in target.

   Worked examples:
   - Driver "population growth" -> Activity "fishing effort": "+"
     (more people drive more fishing).
   - Response "marine protected area" -> Pressure "bottom trawling": "-"
     (the response REDUCES the pressure).
   - Response "subsidy reform" -> Driver "fleet expansion": "-"
     (curbing subsidies reduces fleet growth).
   - Welfare "ecosystem service loss" -> Response "policy intervention": "+"
     (more loss triggers more response).

3. Confidence — discrete enum {0.3, 0.5, 0.7, 0.9}, with a target
   distribution:
   - 0.9: well-established in peer-reviewed literature for THIS
     ecosystem type AND polarity uncontested.
   - 0.7: documented but context-dependent or polarity sometimes
     inverted.
   - 0.5: plausible mechanism, limited direct evidence.
   - 0.3: speculative — only emit if novel or non-obvious.
   Aim for roughly 30/30/30/10 across 0.9/0.7/0.5/0.3. If you find
   yourself emitting >50% at 0.9, you are being generous — re-grade.

4. Rationale: 6 to 12 words, hard cap 15. One mechanism, no hedging.
   Ground it in the regional sea / ecosystem / countries the user
   named, using vocabulary appropriate to that system. Bad: "may
   potentially contribute under certain circumstances." Good:
   "Eutrophication in Baltic shallows triggers cyanobacterial blooms."

5. Use source/target IDs exactly as provided in the input. Do NOT
   invent new elements, do NOT use labels in source/target fields.

6. At most ONE suggestion per (source, target) pair. If both
   polarities seem plausible, pick the dominant one. (Per Rule 4,
   the rationale itself should state ONE mechanism without hedging
   — the polarity choice is your judgement; the rationale supports
   that one choice.)

Return your output by calling the `record_connection_suggestions`
tool. Order suggestions from highest confidence to lowest. Within
the same confidence, prioritize NON-OBVIOUS connections — cross-
category cascades, feedback loops, behavior-change pathways. Skip
tautologies (e.g., "fishing activity" -> "fish mortality pressure" is
too direct to be useful).

Quality over quantity. Aim for **20-60 high-quality suggestions**;
emit more only if genuinely warranted. The hard cap is 150 (a
ceiling, not an anchor). If a labeled element is ambiguous to you
(unfamiliar jargon, unclear scope), skip it rather than guess.

<good_examples>
Given input fragment:
  ## DRIVERS
  - id="d1" label="coastal population growth"
  ## ACTIVITIES
  - id="a1" label="recreational boating"
  ## RESPONSES
  - id="r1" label="speed-limit zone for vessels"

You would emit (among others):
  {"source": "d1", "target": "a1", "polarity": "+",
   "confidence": 0.9, "rationale": "more residents drive
   recreational vessel demand"}
  {"source": "r1", "target": "a1", "polarity": "-",
   "confidence": 0.7, "rationale": "speed limits deter
   pleasure-boat traffic in protected zones"}

You would NOT emit:
  - any suggestion using "coastal population growth" in the source
    field (use the id "d1")
  - {"source": "a1", "target": "d1", ...} - A->D is not in the 10
    allowed directions
  - confidence values other than {0.3, 0.5, 0.7, 0.9}
  - duplicate (source, target) pairs (any variation)
</good_examples>
"""


# ---------------------------------------------------------------------------
# Tool definition — schema-validated structured output. tool_choice in the
# orchestrator forces the model to call this exact tool.
# ---------------------------------------------------------------------------

_TOOL_DEFINITION = {
    "name": _TOOL_NAME,
    "description": (
        "Record causal connection suggestions for a DAPSI(W)R(M) "
        "system map. Each suggestion proposes ONE directed causal "
        "edge between two elements the user supplied. source and "
        "target MUST be element ids (verbatim, exact case) - never "
        "element labels. Polarity is the SIGN of the causal effect "
        "(+ = increase causes increase, - = increase causes decrease). "
        "Order the array highest confidence first. At most one "
        "suggestion per (source, target) pair."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "maxItems": 150,
                "items": {
                    "type": "object",
                    "properties": {
                        "source":     {"type": "string"},
                        "target":     {"type": "string"},
                        "polarity":   {"type": "string", "enum": ["+", "-"]},
                        "confidence": {"type": "number",
                                       "enum": [0.3, 0.5, 0.7, 0.9]},
                        "rationale":  {"type": "string", "maxLength": 150},
                    },
                    "required": [
                        "source", "target", "polarity",
                        "confidence", "rationale",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["suggestions"],
        "additionalProperties": False,
    },
}
