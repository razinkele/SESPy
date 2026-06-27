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
from dataclasses import dataclass
from typing import Literal, get_args

from .data_structure import (
    _VALID_TYPE_PAIRS,
    ELEMENT_TYPE_MAP,
    ConnectionSuggestion,
    Element,
    Slug,
    WizardState,
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


# NOTE: NOT frozen. A frozen dataclass Exception cannot be propagated through
# Shiny's @reactive.extended_task: the framework sets `exc.__traceback__` in
# pure Python (contextlib __exit__ inside DenialContext), which a frozen
# __setattr__ rejects with FrozenInstanceError. (Plain `raise` works because
# CPython sets __traceback__ at the C level, bypassing __setattr__ — which is
# why unit tests that raise/catch directly never hit this.) `eq=False` keeps
# exception-appropriate identity equality + hashability so the frozen
# _ClaudeFailed(error=...) wrapper in the wizard module still hashes/compares.
@dataclass(eq=False)
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


# ---------------------------------------------------------------------------
# User-message serialization
# ---------------------------------------------------------------------------

_DAPSIWRM_ORDER: tuple[Slug, ...] = (
    "drivers", "activities", "pressures", "states",
    "impacts", "welfare", "responses",
)


def _build_user_message(state: WizardState) -> str:
    """Serialize a WizardState into the model's user message.

    - Elements grouped by DAPSI(W)R(M) type, canonical reading order.
    - Empty groups skipped (saves tokens).
    - id/label quoted to clarify which is opaque vs descriptive
      (prompt-readability, not a tokenization guarantee).
    - Empty optional fields render as `(unspecified)`.
    """
    grouped: dict[Slug, list[Element]] = {slug: [] for slug in _DAPSIWRM_ORDER}
    for el in state.elements:
        slug = _TYPE_TO_SLUG.get(el.type)
        if slug is not None:
            grouped[slug].append(el)
    elements_block = "\n".join(
        f"## {slug.upper()}\n" + "\n".join(
            f'- id="{e.id}" label="{e.label}"' for e in grouped[slug]
        )
        for slug in _DAPSIWRM_ORDER
        if grouped[slug]
    )
    return (
        f"Regional sea: {state.regional_sea or '(unspecified)'}\n"
        f"Ecosystem type: {state.ecosystem_type or '(unspecified)'}\n"
        f"Countries: {', '.join(state.countries) or '(unspecified)'}\n"
        f"Main issue(s): {', '.join(state.main_issue) or '(unspecified)'}\n\n"
        f"## Elements\n\n{elements_block}\n\n"
        f"Suggest connections per the rules. "
        f"Use IDs (not labels) in source and target."
    )


def _extract_tool_input(response: object) -> list[object]:
    """Return the suggestions list from the response's first ToolUseBlock.

    Annotated as `object` (not `Any`) so the type checker forces structural
    checks on this untrusted SDK output. Last-write-wins on duplicate
    tool_use blocks. Raises ClaudeBackendError(reason='shape') if no
    tool_use block; captures any text-block content for diagnosis.
    """
    text_content: list[str] = []
    tool_use_input: list[object] | None = None
    duplicate_tool_use_count = 0
    for block in response.content:                       # type: ignore[attr-defined]
        block_type = getattr(block, "type", None)
        if block_type == "tool_use":
            inp = block.input                            # type: ignore[attr-defined]
            if not isinstance(inp, dict):
                raise ClaudeBackendError(
                    reason="shape",
                    text_content=f"tool_use input is not dict: {type(inp).__name__}",
                )
            sugs = inp.get("suggestions")
            if not isinstance(sugs, list):
                raise ClaudeBackendError(
                    reason="shape",
                    text_content=f"'suggestions' is not list: {type(sugs).__name__}",
                )
            if tool_use_input is not None:
                duplicate_tool_use_count += 1
            tool_use_input = sugs
        elif block_type == "text":
            text_content.append(getattr(block, "text", ""))
        else:
            _logger.warning("unexpected block type=%r in response", block_type)

    if duplicate_tool_use_count:
        _logger.warning(
            "claude response had %d duplicate tool_use block(s); used last",
            duplicate_tool_use_count,
        )

    if tool_use_input is not None:
        if text_content:
            text_blob = " | ".join(text_content)[:500]
            _logger.info(
                "claude response contained mixed text+tool_use; model said: %r",
                text_blob,
            )
        return tool_use_input

    text_blob = " | ".join(text_content)[:500] if text_content else ""
    raise ClaudeBackendError(
        reason="shape",
        text_content=(
            f"no tool_use block; model said: {text_blob!r}" if text_blob
            else "no tool_use block; response had no text either"
        ),
    )


def _validate_and_coerce(
    raw: list[object],
    valid_ids: set[str],
    elements: list[Element],
) -> ValidationOutcome:
    """Top-down validation pipeline. Each check increments at-most-one
    drop reason per entry and short-circuits via `continue`. Order is the
    §3.7 table order — pinned by test_drop_precedence_*.

    drops_by_reason invariant: every DropReason Literal member is a key
    in the returned mapping (zero if not encountered). Use
    dict.fromkeys(get_args(DropReason), 0) — NOT defaultdict, which
    omits never-seen keys from serialized form.
    """
    drops: dict[DropReason, int] = dict.fromkeys(get_args(DropReason), 0)
    by_id: dict[str, Element] = {el.id: el for el in elements}
    surviving: list[ConnectionSuggestion] = []
    raw_count = len(raw)

    for entry in raw:
        # 1. non_dict
        if not isinstance(entry, dict):
            drops["non_dict"] += 1
            continue
        # 2. missing_key
        try:
            source = entry["source"]
            target = entry["target"]
            polarity = entry["polarity"]
            confidence = entry["confidence"]
            rationale = entry["rationale"]
        except KeyError:
            drops["missing_key"] += 1
            continue
        # 3-5. ID checks (top-down)
        if source not in valid_ids:
            drops["unknown_source"] += 1
            continue
        if target not in valid_ids:
            drops["unknown_target"] += 1
            continue
        if source == target:
            drops["self_loop"] += 1
            continue
        # 6. type-pair (frozenset O(1) membership)
        from_slug = _TYPE_TO_SLUG.get(by_id[source].type)
        to_slug = _TYPE_TO_SLUG.get(by_id[target].type)
        if (from_slug, to_slug) not in _VALID_TYPE_PAIRS:
            drops["invalid_pair"] += 1
            continue
        # 7. polarity
        if polarity not in ("+", "-"):
            drops["invalid_polarity"] += 1
            continue
        # 8. confidence — bool BEFORE int/float (bool subclasses int).
        if isinstance(confidence, bool):
            drops["non_numeric_confidence"] += 1
            continue
        if not isinstance(confidence, (int, float)):
            drops["non_numeric_confidence"] += 1
            continue
        confidence = float(confidence)
        if not math.isfinite(confidence):
            drops["non_numeric_confidence"] += 1
            continue
        if confidence < 0.0:
            confidence = 0.0
        elif confidence > 1.0:
            confidence = 1.0
        # 9. rationale
        if not isinstance(rationale, str) or not rationale.strip():
            drops["empty_rationale"] += 1
            continue
        # All checks passed.
        surviving.append(ConnectionSuggestion(
            source=source,
            target=target,
            polarity=polarity,
            confidence=confidence,
            rationale=rationale,
        ))

    return ValidationOutcome(
        suggestions=surviving,
        raw_count=raw_count,
        drops_by_reason=drops,
    )


def suggest_connections(state: WizardState) -> ValidationOutcome:
    """SP4 contract: Anthropic-API-backed scoring.

    Returns a ValidationOutcome envelope (suggestions + drop counts).
    Synchronous — called from inside @reactive.extended_task via
    asyncio.to_thread (see sespy.modules.ai_isa_wizard).

    Raises ClaudeBackendError on:
    - too_many: state.elements > _MAX_ELEMENTS (200) — SDK NOT called.
    - auth, rate_limit, timeout, network, status: SDK exceptions, mapped
      from anthropic.* exception subclasses.
    - shape: malformed response (no tool_use block, non-dict input, or any
      non-ClaudeBackendError exception from _extract_tool_input or
      _validate_and_coerce — the latter is wrapped to preserve the
      structured INFO log's status=error reason=shape classification).
    """
    if len(state.elements) > _MAX_ELEMENTS:
        # Log before raising so the structured INFO line still fires for
        # too_many rejections.
        _logger.info(
            "claude_backend.call status=error reason=too_many "
            "element_count=%d", len(state.elements),
        )
        raise ClaudeBackendError(reason="too_many")

    import anthropic  # lazy import
    # `os.environ.get(key, default)` returns '' for explicitly-empty env
    # var. `or _DEFAULT_MODEL` handles empty-string-as-falsy.
    model = os.environ.get("SESPY_CLAUDE_MODEL") or _DEFAULT_MODEL
    # max_retries=0 enforces the "no retries" cost-bounding contract
    # documented in the spec (§1.4 row "Retries: None"). The Anthropic
    # SDK defaults to max_retries=2; without overriding, a single user
    # click on Generate could result in 3 paid API calls during a rate
    # limit, silently violating the cost ceiling.
    client = anthropic.Anthropic(timeout=_TIMEOUT_SECONDS, max_retries=0)
    started = time.monotonic()
    response = None
    error_reason: ClaudeErrorReason | None = None
    status_code: int | None = None
    outcome: ValidationOutcome | None = None

    try:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=_MAX_OUTPUT_TOKENS,
                system=[
                    {"type": "text", "text": _SYSTEM_PROMPT,
                     "cache_control": {"type": "ephemeral"}},
                ],
                tools=[_TOOL_DEFINITION],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[
                    {"role": "user", "content": _build_user_message(state)},
                ],
            )
        # ORDER MATTERS — most-specific first.
        # AuthenticationError, RateLimitError are subclasses of
        # APIStatusError. APITimeoutError is a subclass of
        # APIConnectionError.
        except anthropic.AuthenticationError as e:
            error_reason = "auth"
            raise ClaudeBackendError(reason="auth") from e
        except anthropic.RateLimitError as e:
            error_reason = "rate_limit"
            # Retry-After is a response header; RateLimitError has no
            # .retry_after attribute.
            retry_after_hdr = e.response.headers.get("retry-after") if e.response else None
            try:
                retry_after = float(retry_after_hdr) if retry_after_hdr else None
            except (TypeError, ValueError):
                retry_after = None
            raise ClaudeBackendError(
                reason="rate_limit", retry_after=retry_after,
            ) from e
        except anthropic.APITimeoutError as e:
            error_reason = "timeout"
            raise ClaudeBackendError(reason="timeout") from e
        except anthropic.APIConnectionError as e:
            error_reason = "network"
            raise ClaudeBackendError(reason="network") from e
        except anthropic.APIStatusError as e:
            error_reason = "status"
            status_code = e.status_code
            raise ClaudeBackendError(
                reason="status", status_code=e.status_code,
            ) from e

        # Post-SDK path: any exception MUST set error_reason before
        # propagating, otherwise the finally would misclassify the
        # failure as status=ok.
        try:
            raw = _extract_tool_input(response)
            valid_ids = {el.id for el in state.elements}
            outcome = _validate_and_coerce(raw, valid_ids, state.elements)
        except ClaudeBackendError as e:
            error_reason = e.reason
            status_code = e.status_code
            raise
        except Exception as e:                            # noqa: BLE001
            error_reason = "shape"
            raise ClaudeBackendError(
                reason="shape",
                text_content=f"unexpected post-SDK error: {type(e).__name__}: {e}",
            ) from e
        return outcome

    finally:
        # Always emit one structured INFO log, success OR failure.
        latency_ms = int((time.monotonic() - started) * 1000)
        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "input_tokens", None)
        tokens_out = getattr(usage, "output_tokens", None)
        _logger.info(
            "claude_backend.call status=%s reason=%s status_code=%s "
            "model=%s tokens_in=%s tokens_out=%s latency_ms=%d "
            "raw_count=%s suggestions_after_validation=%s",
            "ok" if error_reason is None else "error",
            error_reason or "",
            status_code or "",
            model,
            tokens_in, tokens_out, latency_ms,
            outcome.raw_count if outcome else None,
            len(outcome.suggestions) if outcome else 0,
        )
