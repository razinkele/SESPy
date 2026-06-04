# AI-ISA Wizard SP4 — Optional Claude API Backend

Date: 2026-05-09
Status: **Implemented** — shipped to `main` 2026-06-04. Backed by `sespy/claude_backend.py`, the wizard consent/observer/sum-type flow in `sespy/modules/ai_isa_wizard.py`, the `anthropic` runtime dep, and 258 unit + e2e tests in CI. The §12 open items were resolved during implementation (incl. the frozen-dataclass-Exception fix for `@reactive.extended_task` propagation). (Footer corrected from "Draft" in the 2026-06-04 corpus review.)

**Sub-project context:** SP4 of 4 in the AI-Assisted SES Creation series.
- SP1 shipped 2026-05-01.
- SP2 shipped 2026-05-02.
- SP3 shipped 2026-05-04 (SP3 implementation merge commit; subsequent
  doc-fix at `c47444d`).
- **SP4 (this spec)** — optional Claude API backend for
  `suggest_connections`, switchable per wizard run via a button +
  consent dialog, with the SP3 rule-based scorer always rendered as a
  baseline. Closes the SP1–SP4 wizard sub-project series.

There is no R equivalent; SP4 is a SESPy-only addition.

**SP1 contract evolution.** SP1 §1 anticipated SP4 as "switchable via
setting (`wizard.scoring_backend`)" with SP3 as a fallback. SP4
evolves: the toggle is per-run via a button click (no persisted
setting), SP3 is augmented (not replaced — both render side-by-side
after a successful Claude call), and the `wizard.scoring_backend`
setting is deferred to a future Settings-module SP. Reasons: per-run is
a stronger consent gate for an action that sends data over the network
and costs money; side-by-side preserves comparison; settings
infrastructure for SP4 alone is over-scoping.

---

## 1. Goal & scope

### 1.1 In scope

A new pure-Python module `sespy/claude_backend.py` whose
`suggest_connections(state)` function matches SP3's signature shape and
returns a `ValidationOutcome` envelope of Claude-API-generated
suggestions. The wizard's connection-review step (#11) gains an opt-in
[Generate with Claude API] button that, on first click per session,
opens a consent modal disclosing data egress; on confirm, dispatches
to a `@reactive.extended_task` that calls the backend and renders
results in a second table below SP3. SP3 results remain visible at all
times. On API failure, a toast fires and the SP3 table remains the
only visible result set.

Files:

- `sespy/claude_backend.py` — new (~340 LOC). Anthropic SDK call,
  payload serialization, tool-use structured output, validation
  pipeline returning `ValidationOutcome`, single-dataclass error type.
- `sespy/data_structure.py` — edit (~+15 LOC). Add `Slug` Literal,
  `_CONN_TYPES` (10 3-tuples), `_VALID_TYPE_PAIRS` frozenset alongside
  the existing `ELEMENT_TYPE_MAP`. Co-located with the existing
  data-layer constants rather than placed in a separate module —
  `_CONN_TYPES` IS data structure (it defines the DAPSI(W)R(M) graph
  topology), and `data_structure.py` is already imported by both
  backends.
- `sespy/connection_scorer.py` — edit (~5 LOC). Replace local
  `_CONN_TYPES` definition with `from .data_structure import _CONN_TYPES`.
  The import line preserves `from sespy.connection_scorer import _CONN_TYPES`
  for `tests/test_connection_scorer.py:491`.
- `sespy/modules/ai_isa_wizard.py` — edit (~+110 LOC). Split the
  existing `wizard_suggestions` reactive into the sum-typed
  `wizard_claude_status` + `wizard_suggestions_sp3`; add the Generate
  button (env-gated visibility, plus `SESPY_DISABLE_CLAUDE`
  defence-in-depth); add the extended task + observer effect; add the
  consent modal flow with in-flight and step-11 guards; revise step-11
  renderer to show two tables with a drop-counts badge and explicit
  match-arms for all sum-type cases; revise `_on_finish` to merge
  accepted suggestions from both tables with dedup; revise `_on_back`
  to dismiss any open modal, reset SP4 status, and bump the generation
  counter; rename `accept_suggestion_*` → `accept_sp3_*`. Adds
  top-of-file imports for `asyncio` and `from shiny.types import SilentException`.
- `sespy/translations/core.json` — edit (+27 keys) inside the existing
  top-level `"translation"` wrapper, each as a per-language object
  across all 9 SESPy languages.
- `pyproject.toml` — add `anthropic>=0.50,<0.101` runtime dep; add
  `pytest-asyncio>=0.23` to test extras; fix the `package-data` glob
  to include `sespy/translations/*.json` (latent-bug fix).
- `tests/test_claude_backend.py` — new (~32 tests, parameterized).
- `tests/test_wizard.py` — edit (~+90 LOC, 14 new tests).
- `tests/test_wizard_e2e.py` — edit (+2 cases).
- README — bump unit-test count (180 → ~225) and add a 2-paragraph
  "Optional Claude API backend" section under the AI-ISA wizard
  description (matches the SP3 commit pattern).

### 1.2 Out of scope (deferred)

- Per-project Claude opt-in (PIMS metadata field). Per-run toggle was
  chosen during brainstorming; per-project would need `Project` schema
  bump 2→3.
- Settings UI / dedicated Settings module. No settings infrastructure
  exists in SESPy today.
- Caching of API responses by WizardState hash. Marginal benefit at
  one-call-per-click cadence.
- Streaming / partial results. The whole call is ~3–8 s.
- Multi-language rationales. SP3 is English-only too; matched for
  parity. Future SP can add a `language` parameter.
- Retry on transient errors (5xx, timeout). One-shot keeps cost
  bounded. The button is disabled for `Retry-After` seconds on 429
  to prevent click-storms.
- Soft token-budget guard above 200 elements. Hard cap at 200 with a
  clear toast.
- `AsyncAnthropic` (native async SDK client). Sync client +
  `asyncio.to_thread` is sufficient for SP4's 1-call-per-click
  workload.
- Optional `anthropic` extras (`pip install sespy[claude]`). The
  lazy-import + SDK-missing toast handles graceful degradation; SP4
  ships it as a hard dep for simplicity.
- KB-seed branch and ML-scoring branch (R's `SES_CONNECTION_DB`,
  `ml_inference.R`). Already deferred by SP3.
- Provenance field on `ConnectionSuggestion`. SP4 does not modify the
  boundary dataclass; future SPs may add `origin: Literal["rule", "claude"]`.
- Rationale sanitization (strip control chars, NFKC, etc.). Defer
  until project-export across users is real.

### 1.3 Non-goals

SP4 does not replace SP3, does not introduce settings infrastructure,
and does not change the `WizardState` or `ConnectionSuggestion`
boundary dataclasses, the wizard step flow, or any other module's
behaviour.

### 1.4 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| User-facing surface | Per-run button + consent modal, env-gated by `ANTHROPIC_API_KEY`; `SESPY_DISABLE_CLAUDE` is the institutional kill-switch | Smallest surface; explicit cost gate; opt-in privacy posture; no settings infrastructure required. |
| Failure UX | Toast + SP3 already visible | One round-trip cost ceiling. SP3 always-rendered means user always has suggestions. `Retry-After` from 429 disables the button for that duration. |
| Privacy / payload | Send full `WizardState` (5 fields) | Disclosure modal lists exactly what is sent. SP3 reads only `state.elements`; SP4 additionally sends `regional_sea`, `ecosystem_type`, `countries`, `main_issue` to give the model regional context for grounding rationales. |
| Architecture | Side-by-side: SP3 always rendered; button-triggered SP4 | Free path is unchanged; cost requires explicit click; preserves SP3 baseline visible after Claude succeeds. |
| Async dispatch | `@reactive.extended_task` + result-observer effect (NOT raw `asyncio.create_task`) | Framework-endorsed pattern; preserves session context; task exceptions surface; spinner reactive flushes correctly. |
| Reactive shape for SP4 | Sum-typed `_ClaudeIdle | _ClaudeLoading | _ClaudeReturned(outcome) | _ClaudeFailed(error)` | Distinguishes never-called, in-flight, called-and-zero, called-and-failed. |
| Output handling | Validate-and-drop on semantic invalidity; clamp on numeric out-of-range | Invalid IDs, type-pairs, polarity, non-finite/non-numeric/bool confidence, empty rationale → drop. Confidence in [0,1] taken as-is; out-of-range clamped. |
| Reactive rename | `wizard_suggestions` → `wizard_suggestions_sp3`, `accept_suggestion_*` → `accept_sp3_*` | Disambiguates SP3 vs SP4 in side-by-side rendering. Module-internal; no external test refs (verified by grep). |
| SDK pin | `anthropic>=0.50,<0.101` | Lower bound above the 0.34.0 release that introduced per-block `cache_control`; upper bound at next minor above the May-2026 latest. SDK has 2 published moderate-severity advisories — both Memory-Tool-related; SP4 does not use the Memory Tool. |

### 1.5 Quantitative targets

- Validation drop rate budget: typical 0–10%; >40% in the structured
  INFO log indicates prompt regression.
- API call latency: target p95 < 12 s; hard timeout 60 s.
- Cost: ~$0.02–$0.05 per call (Sonnet 4.6 input pricing, ~800-token
  system + 100–500-token user message + ≤16k output tokens).

---

## 2. Architecture overview

```
   step 10 → Next                  ┌──────────────────────────────────┐
        │                          │  ai_isa_wizard module             │
        │  wizard_suggestions_sp3  │  - SP3 table always rendered      │
        │  ←────────────────────   │  - [Generate] button iff env key  │
        │  populated by SP3 path   │    set AND not disabled           │
        ▼                          │  - in-flight + step-11 guards     │
   step 11 (SP3 visible)           │  - first click: consent modal     │
        │                          │  - confirmed click: invokes       │
        │  click [Generate]        │    @reactive.extended_task        │
        ▼                          │  - observer reads task.result();  │
   sync click handler              │    maps into wizard_claude_status │
        │                          │  - on Back from 11: clear modal,  │
        │ if not consented ────►   │    reset status, bump generation  │
        │   show modal             │  - on Finish: merge+dedup both    │
        │ else                     └────┬───────────────┬──────────────┘
        │   set Loading                 │               │
        │   claude_task(state, gen)     │               ▼
        ▼                               ▼      ┌─────────────────────┐
   wizard_claude_status:        ┌──────────┐   │ @reactive.          │
     Loading                    │ wizard.py│   │ extended_task       │
                                │ delegate │   │ async fn:           │
                                │ to SP3   │   │   await asyncio     │
                                │ unchg'd  │   │     .to_thread(     │
                                └────┬─────┘   │     suggest_         │
                                     │         │     connections,    │
                                     ▼         │     state)          │
                              ┌──────────────┐ └─────────┬───────────┘
                              │ connection_  │           │ result or raise
                              │ scorer (SP3) │           │
                              └──────┬───────┘           ▼
                                     │            ┌───────────────────┐
                                     ▼            │ claude_backend    │
                              ┌──────────────┐    │ .suggest_         │
                              │ data_        │    │  connections      │
                              │ structure    │    │ - serialize       │
                              │ (Slug,       │    │ - call SDK with   │
                              │  _CONN_TYPES,│    │   tool_use        │
                              │  _VALID_     │    │ - validate        │
                              │   TYPE_PAIRS,│    │ - return Outcome  │
                              │  ELEMENT_    │    │ - or raise        │
                              │   TYPE_MAP)  │    └───────┬───────────┘
                              └──────────────┘            │
                                                          ▼
                                                  ┌─────────────────┐
                                                  │ anthropic SDK   │
                                                  │ messages.create │
                                                  └─────────────────┘
```

### 2.1 File layout

| File | Status | Purpose |
|---|---|---|
| `sespy/data_structure.py` | edit (+15 LOC) | Add `Slug` Literal, `_CONN_TYPES` (10 3-tuples preserving the existing `(slug, slug, key)` shape), `_VALID_TYPE_PAIRS = frozenset((from_, to_) for from_, to_, _key in _CONN_TYPES)`. Co-located with `ELEMENT_TYPE_MAP`. |
| `sespy/claude_backend.py` | new (~340 LOC) | Anthropic-API-backed `suggest_connections(state)`. Pure module. No Shiny imports. |
| `sespy/connection_scorer.py` | edit (~5 LOC) | `from .data_structure import _CONN_TYPES` (preserves `sespy.connection_scorer._CONN_TYPES` re-export for the existing test import). |
| `sespy/wizard.py` | unchanged | Pure-data layer. Still delegates to SP3. |
| `sespy/modules/ai_isa_wizard.py` | edit (+110 LOC) | New imports; split reactive into sum-type; extended task + observer + consent modal handlers + guards; new renderer; revised finish/back; accept-prefix rename. |
| `sespy/translations/core.json` | edit (+27 keys) | Toast, button, spinner, table headers, consent modal, drop-counts badge, "returned zero". |
| `pyproject.toml` | edit | `anthropic>=0.50,<0.101`, `pytest-asyncio>=0.23`, package-data fix. |
| `tests/test_claude_backend.py` | new (~32 tests, parameterized) | Mocked unit tests in 6 groups. |
| `tests/test_wizard.py` | edit (+90 LOC) | Rename references; 14 new tests. |
| `tests/test_wizard_e2e.py` | edit (+2 cases) | `case_claude_consent_then_generate`, `case_claude_consent_decline`. |

### 2.2 Dispatch boundary

`sespy.wizard.suggest_connections(state)` is unchanged: it still calls
`connection_scorer.suggest_connections(state)`. The wizard module
imports both backends but the pure-data layer is monomorphic.

The 10→11 transition continues to call the SP3 path via the existing
import. Lazy import of `claude_backend` lives inside the extended task
body — test environments without `anthropic` installed can still
import the wizard module.

The existing module-level imports are preserved:

```python
import asyncio
from shiny import reactive, ui
from shiny.types import SilentException
from ..wizard import suggest_connections      # SP3 entry point (unchanged)
# claude_backend NOT imported at module level — see §4.3 extended task.
```

### 2.3 Toggle visibility

The button is rendered iff `os.environ.get("ANTHROPIC_API_KEY")` is
truthy AND `os.environ.get("SESPY_DISABLE_CLAUDE")` is falsy/unset.
Read at every step-11 render.

---

## 3. The Claude backend module (`sespy/claude_backend.py`)

### 3.1 Module-level constants

```python
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

_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_OUTPUT_TOKENS = 16384
_TIMEOUT_SECONDS = 60.0
_MAX_ELEMENTS = 200
_TOOL_NAME = "record_connection_suggestions"

_TYPE_TO_SLUG: Mapping[str, Slug] = {v: k for k, v in ELEMENT_TYPE_MAP.items()}

_logger = logging.getLogger(__name__)
```

`_TOOL_NAME` is referenced by `_TOOL_DEFINITION` (§3.4) and the
`tool_choice` argument (§3.5) — single source of truth.

### 3.2 The system prompt

```python
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

Quality over quantity. Aim for **20–60 high-quality suggestions**;
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
  - {"source": "a1", "target": "d1", ...} — A->D is not in the 10
    allowed directions
  - confidence values other than {0.3, 0.5, 0.7, 0.9}
  - duplicate (source, target) pairs with different polarities
</good_examples>
"""
```

### 3.3 User-message serialization (`_build_user_message`)

```python
_DAPSIWRM_ORDER: tuple[Slug, ...] = (
    "drivers", "activities", "pressures", "states",
    "impacts", "welfare", "responses",
)

def _build_user_message(state: WizardState) -> str:
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
```

Empty groups are skipped to save tokens. The `id="X" label="Y"` quoting
clarifies which field is opaque (id) and which is descriptive (label) —
prompt-readability, not a tokenization guarantee. Element labels go
verbatim; see §10.1 for the prompt-injection threat model.

### 3.4 Tool definition

```python
_TOOL_DEFINITION = {
    "name": _TOOL_NAME,
    "description": (
        "Record causal connection suggestions for a DAPSI(W)R(M) "
        "system map. Each suggestion proposes ONE directed causal "
        "edge between two elements the user supplied. source and "
        "target MUST be element ids (verbatim, exact case) — never "
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
```

`tool_choice={"type": "tool", "name": _TOOL_NAME}` forces the model.
Schema-level defences (`additionalProperties: False`, `enum`,
`maxItems`, `maxLength`, `confidence` enum) reject malformed output
before the validation pipeline sees it. The Anthropic SDK exposes
`anthropic.types.ToolParam` (TypedDict); the implementation may
annotate `_TOOL_DEFINITION: anthropic.types.ToolParam` inside a
`TYPE_CHECKING` block.

### 3.5 The orchestrator (`suggest_connections`)

```python
def suggest_connections(state: WizardState) -> ValidationOutcome:
    """SP4 contract: Anthropic-API-backed scoring. Returns a
    ValidationOutcome envelope (suggestions + drop counts).
    Synchronous — called from inside @reactive.extended_task via
    asyncio.to_thread."""
    if len(state.elements) > _MAX_ELEMENTS:
        # Log before raising so the structured INFO line still fires
        # for too_many rejections.
        _logger.info(
            "claude_backend.call status=error reason=too_many "
            "element_count=%d", len(state.elements),
        )
        raise ClaudeBackendError(reason="too_many")

    import anthropic                                   # lazy import
    # `os.environ.get(key, default)` returns the empty string for an
    # explicitly-empty env var, NOT the default. The `or` chain
    # handles empty-string-as-falsy.
    model = os.environ.get("SESPY_CLAUDE_MODEL") or _DEFAULT_MODEL
    client = anthropic.Anthropic(timeout=_TIMEOUT_SECONDS)
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
        # APIConnectionError. Catching APIStatusError or
        # APIConnectionError earlier would swallow the more-specific
        # subclasses into the generic bucket.
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

        # Post-SDK path: extract + validate. Any exception raised here
        # MUST set error_reason before propagating, otherwise the finally
        # would misclassify the failure as status=ok. This includes:
        # (a) ClaudeBackendError(reason="shape") from _extract_tool_input,
        # (b) unexpected exceptions from _validate_and_coerce (e.g.,
        # KeyError on a malformed _TYPE_TO_SLUG lookup, TypeError on
        # arithmetic, AttributeError from a future schema drift). Both
        # paths set error_reason; the second wraps as reason="shape" with
        # text_content carrying the original exception for diagnosis.
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
```

### 3.6 Extracting the tool input

```python
def _extract_tool_input(response: object) -> list[object]:
    """Return the suggestions list from the response's first ToolUseBlock.
    Annotated as `object` (not `Any`) so the type checker forces
    structural checks on this untrusted SDK output. Last-write-wins on
    duplicate tool_use blocks.

    Raises ClaudeBackendError(reason='shape') if no tool_use block;
    captures any text-block content for diagnosis.
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
            "claude response had %d duplicate tool_use block(s); "
            "used last", duplicate_tool_use_count,
        )

    if tool_use_input is not None:
        if text_content:
            text_blob = " | ".join(text_content)[:500]
            _logger.info(
                "claude response contained mixed text+tool_use; "
                "model said: %r", text_blob,
            )
        return tool_use_input

    text_blob = " | ".join(text_content)[:500] if text_content else ""
    raise ClaudeBackendError(
        reason="shape",
        text_content=f"no tool_use block; model said: {text_blob!r}" if text_blob
                     else "no tool_use block; response had no text either",
    )
```

### 3.7 Validation & coercion pipeline

```python
DropReason = Literal[
    "non_dict", "missing_key",
    "unknown_source", "unknown_target",
    "self_loop", "invalid_pair",
    "invalid_polarity", "non_numeric_confidence",
    "empty_rationale",
]


@dataclass(frozen=True)
class ValidationOutcome:
    suggestions: list[ConnectionSuggestion]
    raw_count: int
    drops_by_reason: Mapping[DropReason, int]
```

| Field check | Action | Reason key |
|---|---|---|
| Suggestion is not a dict | Drop | `non_dict` |
| Required key missing | Drop | `missing_key` |
| `source` not in `valid_ids` | Drop | `unknown_source` |
| `target` not in `valid_ids` | Drop | `unknown_target` |
| `source == target` | Drop (no self-loops) | `self_loop` |
| `(from_slug, to_slug)` not in `_VALID_TYPE_PAIRS` | Drop | `invalid_pair` |
| `polarity` not in `{"+", "-"}` | Drop | `invalid_polarity` |
| Suggestion has extra keys | Silently ignored (read by name) | n/a |
| `confidence` is `bool` | Drop | `non_numeric_confidence` |
| `confidence` is `NaN` or `±inf` | Drop | `non_numeric_confidence` |
| `confidence` not numeric (str, None, list, …) | Drop | `non_numeric_confidence` |
| `confidence` < 0 (finite, non-bool) | Clamp to 0.0 | (no key — clamp) |
| `confidence` > 1 (finite, non-bool) | Clamp to 1.0 | (no key — clamp) |
| `rationale` empty/whitespace | Drop | `empty_rationale` |

Order of surviving items preserves model-emitted order — drops collapse
the list without resort.

**Drop precedence:** When multiple checks fail on the same suggestion,
the FIRST failing row above determines `drops_by_reason`'s incremented
key. The implementation MUST evaluate top-down. Pinned by
`test_drop_precedence` (see §6.1).

**Confidence-type guard recipe:**

```python
if isinstance(c, bool):
    drop("non_numeric_confidence"); continue
if not isinstance(c, (int, float)):
    drop("non_numeric_confidence"); continue
c = float(c)
if not math.isfinite(c):
    drop("non_numeric_confidence"); continue
if c < 0.0: c = 0.0
elif c > 1.0: c = 1.0
```

The bool exclusion comes BEFORE the int/float check because `bool` is
a subclass of `int` in Python. The `math.isfinite` check comes AFTER
the `float()` cast.

**Top-down validation loop skeleton:**

```python
def _validate_and_coerce(
    raw: list[object],
    valid_ids: set[str],
    elements: list[Element],
) -> ValidationOutcome:
    drops: dict[DropReason, int] = dict.fromkeys(get_args(DropReason), 0)
    by_id = {el.id: el for el in elements}
    surviving: list[ConnectionSuggestion] = []
    raw_count = len(raw)

    for entry in raw:
        # Top-down precedence — first failing check increments and continues.
        if not isinstance(entry, dict):
            drops["non_dict"] += 1; continue
        try:
            source = entry["source"]; target = entry["target"]
            polarity = entry["polarity"]; confidence = entry["confidence"]
            rationale = entry["rationale"]
        except KeyError:
            drops["missing_key"] += 1; continue
        if source not in valid_ids:
            drops["unknown_source"] += 1; continue
        if target not in valid_ids:
            drops["unknown_target"] += 1; continue
        if source == target:
            drops["self_loop"] += 1; continue
        from_slug = _TYPE_TO_SLUG.get(by_id[source].type)
        to_slug = _TYPE_TO_SLUG.get(by_id[target].type)
        if (from_slug, to_slug) not in _VALID_TYPE_PAIRS:
            drops["invalid_pair"] += 1; continue
        if polarity not in ("+", "-"):
            drops["invalid_polarity"] += 1; continue
        # confidence guard recipe (above)
        if isinstance(confidence, bool):
            drops["non_numeric_confidence"] += 1; continue
        if not isinstance(confidence, (int, float)):
            drops["non_numeric_confidence"] += 1; continue
        confidence = float(confidence)
        if not math.isfinite(confidence):
            drops["non_numeric_confidence"] += 1; continue
        if confidence < 0.0: confidence = 0.0
        elif confidence > 1.0: confidence = 1.0
        if not isinstance(rationale, str) or not rationale.strip():
            drops["empty_rationale"] += 1; continue
        surviving.append(ConnectionSuggestion(
            source=source, target=target, polarity=polarity,
            confidence=confidence, rationale=rationale,
        ))

    return ValidationOutcome(
        suggestions=surviving,
        raw_count=raw_count,
        drops_by_reason=drops,
    )
```

Each check increments at-most-one drop reason per entry and
short-circuits via `continue` to the next entry — this preserves the
top-down precedence pinned by `test_drop_precedence`.

**`drops_by_reason` invariant:** the returned envelope's
`drops_by_reason` mapping MUST contain every `DropReason` Literal
member as a key (zero if not encountered). Use
`dict.fromkeys(get_args(DropReason), 0)` at the start of
`_validate_and_coerce`, NOT a `defaultdict` (the latter omits
never-seen keys from the serialized form).

**Why the clamp arms exist alongside the schema enum:** §3.4's
schema constrains `confidence` to `enum: [0.3, 0.5, 0.7, 0.9]` —
the model is server-side prevented from emitting other values. The
`< 0` / `> 1` clamp arms in this validation pipeline are
defense-in-depth: schema enforcement is best-effort (historical SDK
behavior has occasionally let through non-conforming numbers,
especially on `stop_reason="max_tokens"` truncations); a
hand-constructed test fixture or a future schema-validation
regression could feed `_validate_and_coerce` raw dicts that bypass
the schema. Off-enum values within `[0,1]` (e.g., `0.85`) are NOT
additionally rejected here — the schema is the authoritative
enforcer; the validator's clamp covers schema-bypass scenarios.

Bad-suggestion logs emit only the type and field name, never the
offending payload (avoids label leakage).

### 3.8 Error taxonomy

```python
ClaudeErrorReason = Literal[
    "auth", "rate_limit", "timeout", "network",
    "status", "shape", "too_many",
]


@dataclass(frozen=True)
class ClaudeBackendError(Exception):
    reason: ClaudeErrorReason
    status_code: int | None = None        # for reason='status'
    retry_after: float | None = None      # for reason='rate_limit'
    text_content: str | None = None       # for reason='shape'

    def __str__(self) -> str:
        return self.reason
```

The i18n key map:

```python
_REASON_TO_I18N: Mapping[ClaudeErrorReason, str] = {
    "auth":       "wizard.claude_error_auth",
    "rate_limit": "wizard.claude_error_rate_limit",
    "timeout":    "wizard.claude_error_timeout",
    "network":    "wizard.claude_error_network",
    "status":     "wizard.claude_error_other",
    "shape":      "wizard.claude_error_shape",
    "too_many":   "wizard.claude_error_too_many",
}
# `wizard.claude_error_sdk_missing` is intentionally absent. The
# SDK-missing path lives in the wizard module's ImportError handler
# and calls t() directly. The map's exhaustiveness test only checks
# ClaudeErrorReason members.
```

A test loads `core.json` and asserts every value of `_REASON_TO_I18N`
is a key in the file, plus no orphan `wizard.claude_error_*` keys
exist beyond the map values + `sdk_missing` carve-out (see §6.1).

### 3.9 Prompt caching

The Anthropic API does NOT auto-cache without explicit `cache_control`.
Caching has a model-specific minimum prefix size:

| Model | Minimum cacheable tokens |
|---|---|
| Sonnet 4.6 | 2,048 |
| Opus 4.7 / 4.6 | 4,096 |
| Sonnet 4.5 / earlier | 1,024 |

Below-threshold `cache_control` is silently no-op'd (no error;
`cache_creation_input_tokens` and `cache_read_input_tokens` both
report 0).

For `claude-sonnet-4-6` with the SP4 ~800-token prefix (after few-shot
examples in §3.2), caching does not engage today. The `cache_control`
block is set anyway for forward compatibility — if a future SP grows
the prompt past 2,048 tokens, caching engages without a code change.
There is no current cost benefit to claim.

### 3.10 Logging

- `_logger = logging.getLogger(__name__)` at module top.
- INFO: one log per call (success OR failure) via the try/finally;
  one additional INFO when `_extract_tool_input` sees mixed
  text+tool_use.
- WARNING: every validation drop or coercion (reason category, NOT
  payload).
- No element-label logging from `claude_backend`. The shape-error
  captures up to 500 chars of model-emitted text — model output, not
  user-typed labels.
- Wizard module's `_logger.exception` runs in a frame where the
  spawned task's `state` is not in scope (async-dispatched). Python's
  default `logging.Formatter` does not include frame locals; Sentry
  / Rollbar capture them by default — operators using such tools
  must configure scrubbing.

To capture telemetry, set
`logging.getLogger("sespy.claude_backend").setLevel(logging.INFO)`.

---

## 4. Wizard module changes

### 4.1 Reactive plumbing

Renames (existing reactive, single rename):
- `wizard_suggestions` → `wizard_suggestions_sp3`
- accept-checkbox prefix `accept_suggestion_` → `accept_sp3_`
  (breaking change to existing `_on_finish` reads).

New sum-typed reactive.

**Scope split (load-bearing for Shiny):** The four `_Claude*`
dataclasses + `ClaudeBackendStatus` union live at **module top-level**
(types). The `reactive.Value(...)` constructors must run inside a
session context, so the three `wizard_claude_*` reactives live
**inside `ai_isa_wizard_server`**, alongside the existing
`wizard_suggestions_sp3`. Calling `reactive.Value(...)` at module
top-level raises `RuntimeError` at import time in Shiny for Python.

At module top-level (types only):

```python
from typing import assert_never

@dataclass(frozen=True)
class _ClaudeIdle: pass
@dataclass(frozen=True)
class _ClaudeLoading: pass
@dataclass(frozen=True)
class _ClaudeReturned:
    outcome: ValidationOutcome
@dataclass(frozen=True)
class _ClaudeFailed:
    error: ClaudeBackendError

ClaudeBackendStatus = _ClaudeIdle | _ClaudeLoading | _ClaudeReturned | _ClaudeFailed
```

Inside `ai_isa_wizard_server` (session-scoped reactives, alongside
the existing renamed `wizard_suggestions_sp3`):

```python
wizard_claude_status: reactive.Value[ClaudeBackendStatus] = \
    reactive.Value(_ClaudeIdle())
wizard_claude_consent_given: reactive.Value[bool] = reactive.Value(False)
# Generation counter — incremented on Back-from-11. The extended task
# captures the generation at start; the observer compares before
# writing. Stale results are silently discarded.
wizard_claude_generation: reactive.Value[int] = reactive.Value(0)
```

Same split applies to all `@reactive.effect` blocks in §4.3 and
`@reactive.extended_task` `_claude_task` — they all live inside
`ai_isa_wizard_server` (closures over the reactives + `input` +
`session`), matching the existing pattern of every other reactive
effect in the wizard module.

### 4.2 Step 11 renderer

```python
def _render_connection_review(
    sp3: list[ConnectionSuggestion],
    sp4_status: ClaudeBackendStatus,
    claude_available: bool,
) -> ui.Tag:
    parts: list[ui.Tag] = []

    # Empty-state branch — preserve the friendly SP1 message when
    # there's nothing to show AND no Claude path.
    if not sp3 and not claude_available:
        parts.append(ui.tags.div(
            ui.tags.p(t("wizard.no_suggestions"), class_="text-muted"),
            ui.tags.p(
                "Click Finish to complete the wizard. You can add "
                "connections manually via the Edit Data module.",
                class_="text-muted",
            ),
        ))
        return ui.tags.div(*parts)

    parts.append(_render_suggestions_table(
        sp3, prefix="accept_sp3_",
        title=t("wizard.suggestions_rule_based_n").format(n=len(sp3)),
    ))

    if claude_available:
        match sp4_status:
            case _ClaudeLoading():
                parts.append(ui.tags.div(
                    ui.tags.span(class_="spinner-border spinner-border-sm me-2"),
                    t("wizard.claude_generating"),
                    class_="my-3 text-muted",
                ))
            case _ClaudeFailed(error=ClaudeBackendError(reason="rate_limit", retry_after=ra)) if ra is not None and ra > 0:
                # Positive Retry-After only — zero/absent means "retry now".
                parts.append(ui.input_action_button(
                    "wizard_claude_generate",
                    t("wizard.claude_retry_after").format(s=int(ra)),
                    class_="btn btn-outline-primary my-3 disabled",
                ))
            case _ClaudeIdle() | _ClaudeReturned() | _ClaudeFailed():
                parts.append(ui.input_action_button(
                    "wizard_claude_generate",
                    t("wizard.claude_generate_button"),
                    class_="btn btn-outline-primary my-3",
                ))
            case _ as unreachable:
                assert_never(unreachable)

    match sp4_status:
        case _ClaudeReturned(outcome=outcome):
            if outcome.suggestions:
                if outcome.raw_count > len(outcome.suggestions):
                    parts.append(ui.tags.div(
                        t("wizard.claude_drops_badge").format(
                            kept=len(outcome.suggestions),
                            raw=outcome.raw_count,
                            dropped=outcome.raw_count - len(outcome.suggestions),
                        ),
                        class_="alert alert-info py-1",
                    ))
                parts.append(_render_suggestions_table(
                    outcome.suggestions, prefix="accept_sp4_",
                    title=t("wizard.suggestions_claude_n").format(
                        n=len(outcome.suggestions)
                    ),
                ))
            else:
                parts.append(ui.tags.div(
                    t("wizard.claude_returned_zero"),
                    class_="text-muted my-3",
                ))
        case _ClaudeIdle() | _ClaudeLoading() | _ClaudeFailed():
            pass
        case _ as unreachable:
            assert_never(unreachable)

    return ui.tags.div(*parts)
```

`_render_suggestions_table(items, *, prefix, title)` is a new helper
extracted from the existing renderer body. The implementer should
inspect `ai_isa_wizard.py:156-199` for the existing inline structure
to extract.

### 4.3 Async dispatch — extended task + observer

```python
@reactive.extended_task
async def _claude_task(state: WizardState, generation: int) -> tuple[int, ValidationOutcome]:
    """Capture generation alongside outcome so the observer can discard
    stale results (Back-while-loading race)."""
    from ..claude_backend import suggest_connections as _claude_impl
    outcome = await asyncio.to_thread(_claude_impl, state)
    return (generation, outcome)


@reactive.effect
@reactive.event(input.wizard_claude_generate, ignore_init=True)
def _on_claude_generate_clicked() -> None:
    # In-flight guard — protects against rapid-clicks during Loading.
    if isinstance(wizard_claude_status.get(), _ClaudeLoading):
        return
    if wizard_claude_consent_given.get():
        _trigger_claude_call()
        return
    ui.modal_show(ui.modal(
        ui.tags.p(t("wizard.claude_consent_body")),
        ui.tags.ul(
            ui.tags.li(t("wizard.claude_consent_field_sea")),
            ui.tags.li(t("wizard.claude_consent_field_ecosystem")),
            ui.tags.li(t("wizard.claude_consent_field_countries")),
            ui.tags.li(t("wizard.claude_consent_field_issues")),
            ui.tags.li(t("wizard.claude_consent_field_elements")),
        ),
        ui.tags.p(t("wizard.claude_consent_privacy_note")),
        title=t("wizard.claude_consent_title"),
        footer=ui.tags.div(
            ui.input_action_button(
                "wizard_claude_consent_cancel",
                t("wizard.claude_consent_cancel"),
                class_="btn btn-secondary me-2",
            ),
            ui.input_action_button(
                "wizard_claude_consent_confirm",
                t("wizard.claude_consent_confirm"),
                class_="btn btn-primary",
            ),
        ),
        easy_close=False,
    ))


@reactive.effect
@reactive.event(input.wizard_claude_consent_cancel, ignore_init=True)
def _on_consent_cancel() -> None:
    ui.modal_remove()


@reactive.effect
@reactive.event(input.wizard_claude_consent_confirm, ignore_init=True)
def _on_consent_confirm() -> None:
    # Defensive guard against stale Shiny event replay on reconnect.
    if isinstance(wizard_claude_status.get(), _ClaudeLoading):
        ui.modal_remove()
        return
    wizard_claude_consent_given.set(True)
    ui.modal_remove()
    _trigger_claude_call()


def _trigger_claude_call() -> None:
    """Snapshot state + generation, mark Loading, invoke the task."""
    # Step assertion — the consent flow could fire from a stale event
    # (e.g., Back-without-dismiss + queued Confirm).
    if wizard_step.get() != 11:
        return
    state = _assemble_wizard_state()
    generation = wizard_claude_generation.get()
    wizard_claude_status.set(_ClaudeLoading())
    _claude_task(state, generation)


@reactive.effect
def _observe_claude_result() -> None:
    # NB: no @reactive.event — the dependency on _claude_task.status
    # is registered by the unconditional .result() read. Adding
    # @reactive.event would break the dependency. The initial-run
    # SilentException is expected.
    try:
        result = _claude_task.result()
    except SilentException:
        # .result() registers the status dependency before raising;
        # re-raise so the effect re-fires on success/error.
        raise
    except (ImportError, ModuleNotFoundError):
        _logger.exception("claude_backend SDK missing")
        ui.notification_show(
            t("wizard.claude_error_sdk_missing"),
            type="warning", duration=8,
        )
        wizard_claude_status.set(_ClaudeIdle())
        return
    except ClaudeBackendError as e:
        _logger.exception("claude backend failed: %s", e.reason)
        i18n_key = _REASON_TO_I18N[e.reason]
        msg = t(i18n_key)
        if e.reason == "status" and e.status_code:
            msg = f"{msg} (HTTP {e.status_code})"
        ui.notification_show(msg, type="warning", duration=6)
        wizard_claude_status.set(_ClaudeFailed(error=e))
        return
    except Exception as e:                            # noqa: BLE001
        # Catch-all for anything outside the documented taxonomy:
        # AttributeError if `response is None` (SDK bug or proxy);
        # RuntimeError from asyncio thread oddities; future SDK
        # exception classes that are not subclasses of APIStatusError
        # / APIConnectionError. Without this arm, an unforeseen
        # exception leaves the spinner stuck.
        _logger.exception("unexpected error in claude observer")
        ui.notification_show(
            t("wizard.claude_error_other"),
            type="warning", duration=6,
        )
        wizard_claude_status.set(_ClaudeFailed(error=ClaudeBackendError(
            reason="status",
            text_content=f"unexpected: {type(e).__name__}: {e}",
        )))
        return

    captured_generation, outcome = result
    if captured_generation != wizard_claude_generation.get():
        # Stale result — user clicked Back-from-11 and started fresh.
        # Log so operators can detect the Back-during-loading flow.
        _logger.info(
            "claude observer: discarded stale result "
            "(captured_generation=%d, current=%d)",
            captured_generation, wizard_claude_generation.get(),
        )
        return
    wizard_claude_status.set(_ClaudeReturned(outcome=outcome))
```

### 4.4 Finish-time merge & dedup

```python
@reactive.effect
@reactive.event(input.wizard_finish, ignore_init=True)
def _on_finish() -> None:
    if wizard_step.get() != 11:
        return

    accepted: list[ConnectionSuggestion] = []
    read_failures = 0

    for i, s in enumerate(wizard_suggestions_sp3.get()):
        try:
            if input[f"accept_sp3_{i}"]():
                accepted.append(s)
        except SilentException:
            raise
        except KeyError as e:
            _logger.warning("accept checkbox sp3_%d not found: %s", i, e)
            read_failures += 1

    sp4_outcome = (
        wizard_claude_status.get().outcome
        if isinstance(wizard_claude_status.get(), _ClaudeReturned)
        else None
    )
    if sp4_outcome:
        for i, s in enumerate(sp4_outcome.suggestions):
            try:
                if input[f"accept_sp4_{i}"]():
                    accepted.append(s)
            except SilentException:
                raise
            except KeyError as e:
                _logger.warning("accept checkbox sp4_%d not found: %s", i, e)
                read_failures += 1

    if read_failures:
        ui.notification_show(
            t("wizard.read_failures_n").format(n=read_failures),
            type="warning", duration=6,
        )
        return

    # Dedup by (source, target, polarity); keep higher confidence.
    # On confidence tie, the SP3 entry wins (iterated first).
    # Different polarity for the same edge is NOT a duplicate.
    seen: dict[tuple[str, str, str], ConnectionSuggestion] = {}
    discarded = 0
    overwritten = 0
    for s in accepted:
        key = (s.source, s.target, s.polarity)
        prev = seen.get(key)
        if prev is None:
            seen[key] = s
        elif s.confidence > prev.confidence:
            seen[key] = s
            overwritten += 1
        else:
            discarded += 1

    if discarded or overwritten:
        ui.notification_show(
            t("wizard.duplicates_resolved_n").format(
                discarded=discarded, overwritten=overwritten,
            ),
            type="message", duration=4,
        )

    final = list(seen.values())
    # ... existing Connection-write path, unchanged.
```

### 4.5 Back-from-11 invalidation

Add the `if wizard_step.get() == 11:` block at the **top** of the
existing `_on_back` handler — BEFORE the existing step-decrement /
freeform-counts re-seed logic. This way the check reads the *current*
step (still 11), takes the SP4-specific cleanup, then falls through
to the existing step-decrement branch which transitions to step 10.

```python
@reactive.effect
@reactive.event(input.wizard_back, ignore_init=True)
def _on_back() -> None:
    if wizard_step.get() == 11:
        # Defensively dismiss any open consent modal.
        ui.modal_remove()
        wizard_claude_status.set(_ClaudeIdle())
        # Bump generation; in-flight task results will fail the
        # staleness check.
        wizard_claude_generation.set(
            wizard_claude_generation.get() + 1
        )
        # wizard_suggestions_sp3 will be repopulated on the next 10->11.
    # ... existing step-decrement + freeform-counts re-seed logic,
    # unchanged from SP1/SP3.
```

### 4.6 Toggle visibility

```python
elif archetype == "connection_review":
    claude_available = bool(
        os.environ.get("ANTHROPIC_API_KEY")
        and not os.environ.get("SESPY_DISABLE_CLAUDE")
    )
    widget = _render_connection_review(
        wizard_suggestions_sp3.get(),
        wizard_claude_status.get(),
        claude_available,
    )
```

---

## 5. i18n keys (`sespy/translations/core.json`)

Insert inside the existing top-level `"translation"` wrapper, appended
to the `wizard.*` group (which is ordered logically — title, start,
back, next, finish — not alphabetically). Each key is a per-language
object with all 9 SESPy languages: `en`, `es`, `fr`, `de`, `lt`, `pt`,
`it`, `no`, `el`. English is authored; other 8 duplicate English
pending translation.

27 new keys (5 button/UI + 10 consent modal + 8 error + 2 table
headers + 2 dedup/read-failure):

```
wizard.claude_generate_button:    "Generate with Claude API"
wizard.claude_generating:         "Generating with Claude API…"
wizard.claude_returned_zero:      "Claude returned no suggestions for this state."
wizard.claude_retry_after:        "Rate limited — retry in {s} s"
wizard.claude_drops_badge:        "Showing {kept} of {raw} suggestions ({dropped} dropped)"

wizard.claude_consent_title:      "Send your project to Anthropic?"
wizard.claude_consent_body:       "Generating suggestions with Claude sends your wizard answers to Anthropic's API. The following fields are sent:"
wizard.claude_consent_field_sea:       "Regional sea"
wizard.claude_consent_field_ecosystem: "Ecosystem type"
wizard.claude_consent_field_countries: "Countries"
wizard.claude_consent_field_issues:    "Main issues"
wizard.claude_consent_field_elements:  "All element labels and IDs"
wizard.claude_consent_privacy_note:    "Anthropic processes API requests per their privacy policy: https://www.anthropic.com/legal/privacy. Default 30-day retention. Click Send to proceed; consent applies only to the current session."
wizard.claude_consent_confirm:    "Send"
wizard.claude_consent_cancel:     "Cancel"

wizard.claude_error_auth:         "Claude API: invalid API key. Used rule-based scoring."
wizard.claude_error_rate_limit:   "Claude API: rate limit reached. Try again shortly."
wizard.claude_error_timeout:      "Claude API: request timed out. Used rule-based scoring."
wizard.claude_error_network:      "Claude API: network error. Used rule-based scoring."
wizard.claude_error_other:        "Claude API call failed. Used rule-based scoring."
wizard.claude_error_shape:        "Claude API: response format unexpected. Used rule-based scoring."
wizard.claude_error_too_many:     "Project too large for Claude API (>200 elements). Used rule-based scoring."
wizard.claude_error_sdk_missing:  "Claude SDK not installed. Run pip install anthropic."

wizard.suggestions_rule_based_n:  "Rule-based suggestions ({n}):"
wizard.suggestions_claude_n:      "Claude API suggestions ({n}):"

wizard.duplicates_resolved_n:     "Resolved {discarded} discarded duplicate(s); {overwritten} replaced with higher-confidence version."
wizard.read_failures_n:           "Could not read {n} accept checkboxes. Re-check and click Finish again."
```

i18n trap: keys MUST be inside the top-level `"translation"` wrapper.
The `_load_one()` reader does `raw.get("translation", {})` —
root-level keys are silently skipped.

---

## 6. Testing

### 6.1 `tests/test_claude_backend.py` (new, ~32 tests in 6 groups)

**Group 1 — happy path & message construction (5 tests):**

1. `test_call_uses_default_model` — patches `anthropic.Anthropic`; asserts model.
2. `test_env_var_overrides_model` — `SESPY_CLAUDE_MODEL` set + empty-string both covered.
3. `test_user_message_includes_all_5_wizard_state_fields` + groups in DAPSI(W)R(M) order + `id="X" label="Y"` format (single test, multiple assertions).
4. `test_user_message_skips_empty_element_groups`.
5. `test_returns_typed_ValidationOutcome`.

**Group 2 — schema/forcing/extraction (5 tests):**

6. `test_tool_choice_and_definition_name_match` — both reference `_TOOL_NAME`.
7. `test_system_prompt_has_ephemeral_cache_control` + `test_max_tokens` (combined).
8. `test_extract_tool_input_uses_last_when_two_tool_use_blocks` — pin last-write-wins; assert WARNING fires.
9. `test_extract_tool_input_shape_errors` — parameterized over: no tool_use, no tool_use no text, non-dict input, non-list suggestions.
10. `test_extract_tool_input_logs_text_on_mixed_response`.

**Group 3 — validation drops (8 tests, parameterized):**

11. `test_drops_invalid_id_field` — parameterized: unknown_source, unknown_target, self_loop.
12. `test_drops_invalid_pair` — parameterized: `(states, drivers)`, `(impacts, drivers)`, etc. Confirms type-pair check.
13. `test_drops_invalid_polarity` — parameterized: garbage string, missing.
14. `test_drops_non_numeric_confidence` — parameterized: bool True/False, NaN, ±inf, str, None, list. Each must drop with reason `non_numeric_confidence`.
15. `test_clamps_confidence_out_of_range` — parameterized: -0.5 → 0.0, 1.5 → 1.0; assert NO drop.
16. `test_drops_empty_rationale` — parameterized: empty string, whitespace-only.
17. `test_drop_precedence_top_down` — parameterized fixtures with multiple invariants failing simultaneously; assert the FIRST row in the §3.7 table determines `drops_by_reason`.
18. `test_validation_outcome_invariants` — combined: preserves model order after drops; raw_count populated; `drops_by_reason` contains every `DropReason` Literal as a key (zero if not encountered).

**Group 4 — error mapping & logging (8 tests, parameterized):**

19. `test_SDK_exception_maps_to_reason` — parameterized over 5 SDK exception types.
20. `test_RateLimitError_retry_after_from_headers` — parameterized: Retry-After=30 → 30.0, missing → None, malformed → None.
21. `test_too_many_elements_raises_too_many_with_INFO_log` — assert SDK never called AND structured INFO line emits with `reason=too_many element_count=...`.
22. `test_no_retries_on_rate_limit` — SDK called exactly once.
23. `test_REASON_TO_I18N_bidirectional_check` — every Literal value has an i18n key; no orphan `wizard.claude_error_*` key in `core.json` beyond the map values + `sdk_missing` carve-out.
24. `test_all_sp4_non_error_i18n_keys_exist_in_core_json` — explicitly enumerate the 19 non-error keys; assert each present in all 9 languages.
25. `test_INFO_log_classification` — parameterized over success / SDK error / extraction shape error / unexpected post-SDK exception; each asserts `status=` and `reason=` populate correctly in the finally-block log. The shape-error and unexpected-exception cases pin that `error_reason` is set by the post-SDK try-block's two except arms; without them, those failures would misclassify as `status=ok`. The unexpected-exception fixture mocks `_validate_and_coerce` to raise `KeyError`; assertion: log emits `status=error reason=shape` AND the wrapping `ClaudeBackendError` carries the original exception type in `text_content`.
26. `test_INFO_log_emitted_on_mixed_response_text`.

**Group 5 — type-pair derivation (1 test):**

27. `test_VALID_TYPE_PAIRS_derives_from_CONN_TYPES` — explicitly constructs the expected `frozenset` from `_CONN_TYPES` (preserving 3-tuple shape) and asserts equality. Also asserts exactly 10 entries.

**Group 6 — module import (5 tests):**

28. `test_module_import_does_not_eagerly_import_anthropic` — fresh subprocess; assert `"anthropic" not in sys.modules` after import.
29. `test_module_imports_with_no_env_var_set`.
30. `test_CONN_TYPES_is_three_tuple_shape` — assert `_CONN_TYPES[0]` unpacks as `(slug, slug, key)`. Pins backwards-compat with `tests/test_connection_scorer.py`.
31. `test_data_structure_exports_Slug_VALID_TYPE_PAIRS_CONN_TYPES` — assert imports work.
32. `test_connection_scorer_re_exports_CONN_TYPES` — assert `from sespy.connection_scorer import _CONN_TYPES` continues to work.

### 6.2 Mocking strategy

- Lazy `import anthropic` means the patch target is `anthropic.Anthropic` itself: `unittest.mock.patch("anthropic.Anthropic", autospec=True)`.
- Helper `_mock_response(suggestions, usage_in=0, usage_out=0)` builds a fake `Message` using `types.SimpleNamespace` (NOT real `anthropic.types.Message`, which requires `id`, `model`, `role`, `stop_reason` etc. that the orchestrator never reads):
  ```python
  from types import SimpleNamespace
  def _mock_response(suggestions, usage_in=0, usage_out=0):
      return SimpleNamespace(
          content=[SimpleNamespace(
              type="tool_use",
              input={"suggestions": suggestions},
          )],
          usage=SimpleNamespace(
              input_tokens=usage_in, output_tokens=usage_out,
          ),
      )
  ```
- For 429 tests, `_mock_rate_limit_error(retry_after_header)` builds a real `RateLimitError` with a real `httpx.Response` whose headers expose `retry-after`:
  ```python
  import httpx, anthropic
  def _mock_rate_limit_error(retry_after_header: str | None):
      headers = {"retry-after": retry_after_header} if retry_after_header else {}
      response = httpx.Response(
          status_code=429, headers=headers,
          request=httpx.Request("POST", "https://api.anthropic.com"),
      )
      return anthropic.RateLimitError(
          message="rate limited", response=response, body=None,
      )
  ```
- No real network calls. No VCR cassettes.

### 6.3 `tests/test_wizard.py` — new and updated tests

`grep wizard_suggestions accept_suggestion_ tests/test_wizard.py` returns
zero hits in the existing tests, so no rename work in this file — only
14 new tests.

**Test harness:** `tests/test_wizard.py` currently tests only the
pure-data layer (`from sespy.wizard import ...`). The 14 new tests
need to drive the Shiny `module.server` reactive context. There is
no pre-existing harness in this file. The plan doc must specify the
harness; the two viable patterns are:

- **Option A (unit-test fixture, requires a spike):** Build a
  `pytest` fixture using py-shiny's own internal test pattern from
  `posit-dev/py-shiny/tests/pytest/test_destroy.py`. The literal
  recipe (verified against py-shiny source):
  ```python
  from shiny._app import App
  from shiny._connection import MockConnection
  from shiny import ui
  from shiny.session import session_context
  from shiny.reactive import flush

  root = App(ui.TagList(), None)._create_session(MockConnection())
  proxy = root.make_scope("wizard")
  with session_context(proxy):
      # @module.server strips input/output/session and prepends id;
      # call as: ai_isa_wizard_server("wizard", project_data, event_bus)
      ai_isa_wizard_server("wizard", project_data, event_bus)
  await flush()  # propagate reactive invalidation; NOT asyncio.sleep(0)
  ```
  Mock `ui.modal_show` / `ui.modal_remove` / `ui.notification_show`
  via `monkeypatch.setattr("sespy.modules.ai_isa_wizard.ui.modal_show", mock)` —
  the wizard's module-level `ui` binding refers to the shared
  `shiny.ui` module object. For `@reactive.extended_task` assertions
  (the 5 observer/stale-generation tests), monkeypatch
  `asyncio.to_thread` to a sync shim (§6.5) AND await one additional
  `flush()` after task invocation. **Caveat:** `@reactive.extended_task`
  has zero unit-test precedent in py-shiny's own test suite (only
  Playwright/e2e tests). Option A requires a spike to validate the
  observer-effect interaction with extended-task `.result()` reads
  before locking it in.

- **Option B (move to e2e, lower-risk):** Move the 5
  reactive-context-dependent tests to `tests/test_wizard_e2e.py` —
  Playwright already drives the full app and can assert on DOM
  state after each click. Specifically: `test_observer_maps_typed_error_to_failed_status`,
  `test_observer_maps_unexpected_exception_to_failed_with_text_content`,
  `test_observer_discards_stale_result_when_generation_changed`,
  `test_back_from_step_11_dismisses_consent_modal`, `test_consent_modal_*`.
  Keep the dedup + read-failures + button-visibility tests in
  `test_wizard.py` (they don't require a running reactive scope).

**Recommendation: Option B.** The lack of `@reactive.extended_task`
unit-test precedent in py-shiny's own suite means Option A is
high-risk territory; Option B uses the already-proven Playwright
fixtures that drive cases 1–6 of `test_wizard_e2e.py`. Plan doc
should default to Option B unless a spike validates Option A. Test
counts in §1.1 / §6.1 are unchanged either way; only the file split
shifts.

The 14 new tests:

- `test_button_visibility` — parameterized: no key (absent), key+disable (absent), key+no-disable (present), key=empty-string (absent).
- `test_consent_modal_shows_on_first_click`.
- `test_consent_modal_hidden_on_subsequent_click`.
- `test_back_from_step_11_dismisses_consent_modal` — opens modal, clicks Back, asserts (a) `ui.modal_remove` was called (mock-patch), (b) status reset to `_ClaudeIdle`, (c) generation bumped.
- `test_dedup` — parameterized: keeps both polarities; drops lower confidence same polarity; SP3 wins on confidence tie.
- `test_observer_maps_typed_error_to_failed_status` — parameterized over 7 `ClaudeErrorReason` Literals.
- `test_observer_maps_unexpected_exception_to_failed_with_text_content`.
- `test_observer_discards_stale_result_when_generation_changed`.
- `test_finish_short_circuits_with_toast_when_read_failures_present`.
- `test_dedup_emits_toast_with_correct_discarded_overwritten_counts`.
- `test_trigger_claude_call_returns_when_step_is_not_11`.

### 6.4 `tests/test_wizard_e2e.py` — new cases

Shiny module namespace prefix: the wizard module is registered with
namespace `wizard`, so input ids in the DOM are prefixed with `wizard-`.
All new SP4 selectors must use `#wizard-wizard_claude_generate`,
`#wizard-wizard_claude_consent_confirm`, `#wizard-accept_sp3_{i}`, etc.

- `case_claude_consent_then_generate`: monkeypatch the backend, drive
  to step 11, assert SP3 visible + button visible, click button,
  modal appears, click Confirm, spinner appears, SP4 table renders
  with 3 rows below SP3. SP3 still visible (side-by-side).
- `case_claude_consent_decline`: same setup, click button, Cancel,
  modal closes, no SP4 table, monkey-patched function never called.
  Click button again → modal re-appears (consent did not persist).

### 6.5 Mocking notes for async

`@reactive.extended_task` exposes `.result()`, `.invoke()` (or `()`),
`.status()`. Tests use `pytest-asyncio` with `asyncio_mode = "auto"`.

Replace `asyncio.to_thread` via:

```python
async def _fake_to_thread(fn, *args, **kwargs):
    return fn(*args, **kwargs)

with mock.patch("asyncio.to_thread", side_effect=_fake_to_thread):
    ...
```

For modal-show / modal-remove assertions: monkeypatch
`sespy.modules.ai_isa_wizard.ui.modal_remove` (and `modal_show`) and
assert call counts.

---

## 7. Dependencies & packaging

### 7.1 `pyproject.toml`

```toml
[project]
dependencies = [
    "shiny>=1.5",
    "networkx>=3.0",
    "htmltools>=0.5",
    "pandas>=2.0",
    "pyvis>=0.3",
    "anthropic>=0.50,<0.101",   # NEW
]

[project.optional-dependencies]
prod = ["python-igraph>=0.11"]
test = [
    "pytest>=8",
    "pytest-playwright>=0.5",
    "pytest-asyncio>=0.23",      # NEW
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"            # NEW

[tool.setuptools.package-data]
sespy = ["*.json", "translations/*.json"]   # CHANGED — see §7.3
```

### 7.2 Package-data fix

Existing `sespy = ["*.json"]` covers `sespy/*.json` (SP2/SP3 JSONs).
`sespy/translations/` is not a Python package (no `__init__.py`), so
`sespy/translations/core.json` may not have shipped in SP1/SP2/SP3
wheels — a latent bug. SP4 fixes via the glob extension. After SP4
ships, verify via `python -m zipfile -l dist/sespy-*.whl` (portable
across Windows/POSIX) and grep / Select-String for `translations/core.json`.

### 7.3 No new JSON data file

Unlike SP2 / SP3, SP4 has no static data file beyond the i18n edits.
The system prompt and tool definition are Python literals.

---

## 8. Risk register

| Risk | Mitigation |
|---|---|
| Model emits invalid IDs / type-pairs / self-loops / polarity / confidence / rationale | Validation drops with reason logged + drop-counts badge + structured INFO log totals (§3.7, §4.2). |
| `_VALID_TYPE_PAIRS` and `_CONN_TYPES` drift | Both live in `data_structure.py`; test pins single-source-of-truth (§6.1 #27). |
| `_CONN_TYPES` 3-tuple shape lost by future refactor | Test #30 pins shape; preserves `tests/test_connection_scorer.py:491` import. |
| Button visibility bypass (env-var quirks) | `bool(KEY) and not bool(DISABLE)` semantics; parameterized test (§6.3). |
| User has key but no SDK installed | Lazy import; observer's `(ImportError, ModuleNotFoundError)` catch shows install-instruction toast. |
| Anthropic SDK breaking change | Tight pin `>=0.50,<0.101`. SDK has 2 known advisories (Memory-Tool-related; SP4 doesn't use Memory Tool). |
| Cost surprise (button mashed) | In-flight guard; 429-with-Retry-After disables button. User owns key. |
| Sync click handler blocks event loop | `@reactive.extended_task` is the framework-endorsed async pattern. |
| Stale-write race: Back-during-loading | Generation counter (§4.1, §4.5); observer compares before writing. |
| Stale SP4 table on regenerate failure | Observer sets `_ClaudeFailed`, not stale `_ClaudeReturned`. |
| Empty SP4 result conflated with never-called | Sum type distinguishes `Idle`, `Loading`, `Returned([])`, `Returned([...])`, `Failed`. |
| Operator can't trace failed calls | INFO log emits on success AND failure (try/finally + post-SDK extract/validate wrapper). |
| Observer fall-through on unforeseen exception | Generic `except Exception` arm logs and sets `_ClaudeFailed` — spinner never sticks. |
| `core.json` not shipping in wheel | §7.2 package-data fix; post-build verification. |
| `pytest-asyncio` missing | Added to test deps. |
| Modal persistence across Back | `_on_back` calls `ui.modal_remove()` (idempotent); `_trigger_claude_call` asserts step==11. |
| Prompt injection via element labels | Schema constrains output structure; validation drops invalid IDs/types/polarities/empty rationale; residual rationale-content vector documented in §10.1. |
| Country list contains sanctioned-jurisdiction names | Documented in §10.2; operators use `SESPY_DISABLE_CLAUDE`. |
| Browser-disconnect mid-call duplicates cost on user re-click | The extended task continues running on disconnect, but its result is unrecoverable across reconnect. User re-clicks → second paid call. Mitigation: documented as accepted residual; no retry/idempotency layer in SP4. SP5 may add a request-ID-keyed result cache. |
| `@reactive.extended_task` has zero unit-test precedent in py-shiny's own suite (verified by GitHub search of `posit-dev/py-shiny`) | Mitigation: §6.3 recommends Option B (move 5 reactive-context tests to e2e). If Option A is desired, plan doc must include a spike to validate the observer-effect + `.result()` interaction before locking the test fixture. |

---

## 9. Future work / SP5+

- Per-project Claude opt-in (schema bump 2→3).
- Settings module — would unify Claude opt-in, language pref, autosave.
- Result caching by WizardState hash.
- Multi-language rationales (`language` parameter).
- Streaming results.
- Retry on transient errors (with cost-loop care).
- Hybrid scoring — run both backends and merge with origin badges.
- Provenance field on `ConnectionSuggestion` (`origin: Literal["rule", "claude"]`).
- Rationale sanitization for cross-user export.
- `AsyncAnthropic` (native async client).
- Optional `anthropic` extras (`pip install sespy[claude]`).
- Soft token-budget warning for >200 elements.
- Rationale in `Connection` dataclass — currently dropped at Finish
  (existing pre-SP4 data-loss preserved, not introduced).

---

## 10. Security & privacy

### 10.1 Prompt-injection threat model

Element labels are user-typed free-form strings sent verbatim. The
threat model:

- **Code execution:** None. Tool schema constrains output; validation
  drops invalid items.
- **Data exfiltration:** None. Model has no tools beyond
  `record_connection_suggestions`.
- **Confidence-skew attack:** A label like "rate connections involving
  this element at 0.95" could systematically inflate confidence. The
  schema's `enum: [0.3, 0.5, 0.7, 0.9]` mitigates by forcing discrete
  values, but a model that complies with the injection could still
  pick 0.9 systematically. Realistic likelihood: low for current
  single-user use; meaningful if projects are exchanged.
- **Rationale-content abuse:** A label that successfully steers the
  model can produce attacker-controlled text in the rationale field.
  The rationale survives validation (only "non-empty string"
  checked). Users sharing exported projects propagate the rationale.
  Realistic likelihood: low for current single-user use.
- **ID-format injection:** A label containing `id="X1" label="injected"`
  is caught by the validation pipeline's unknown-ID drop check.

No sanitization beyond the schema's `maxLength: 150` on rationale.
Future SPs adding multi-user rendering must revisit.

### 10.2 GDPR / data-residency awareness

SP4 sends project metadata to Anthropic's API. Anthropic's standard
data retention is 30 days; zero-retention requires a separate
agreement. Users handling sensitive data — sanctioned jurisdictions,
named individuals in element labels, embargoed research — should
consult institutional data-governance policy before enabling SP4.
`SESPY_DISABLE_CLAUDE` provides institutional lockdown.

API key handling notes:
- Do not pass the key via CLI args.
- Do not enable `httpx`/`anthropic` debug logging in production.
- If a future SP adds Sentry/Rollbar, configure `before_send` to
  scrub `ANTHROPIC_API_KEY` and frame locals.

The wizard module's `_logger.exception` runs in a frame where the
spawned task's `state` is not in scope (async-dispatched). Default
Python `logging.Formatter` does not capture frame locals.

---

## 11. Open questions

Two items remain open at draft time and warrant validation during
plan or early implementation:

1. **All-same-type project gives an unhelpful drop message.** A
   project with only Drivers (no Activities, etc.) has zero valid
   type-pairs; the model's hallucinations all drop and the badge
   says "Showing 0 of N" with the generic reason. A pre-flight
   "no_valid_pairs" check could give a specific i18n message, but
   adds scope.
2. **Editable installs + package-data.** `pip install -e .` reads
   files from the source tree, bypassing the wheel's `package-data`
   glob. The fix in §7.2 matters for wheel/sdist installs only.
   Verify both flows during implementation.

---

## 12. Definition of done

SP4 is ready to merge to main when:

- New module `sespy/claude_backend.py` and the additions in
  `sespy/data_structure.py` (Slug, `_CONN_TYPES`, `_VALID_TYPE_PAIRS`)
  are present.
- `sespy/connection_scorer.py` re-imports `_CONN_TYPES` from
  `data_structure`; `from sespy.connection_scorer import _CONN_TYPES`
  continues to work (`tests/test_connection_scorer.py:491` passes
  unchanged).
- `sespy/modules/ai_isa_wizard.py` carries the full SP4 changes per §4
  (sum-typed reactive, extended task + observer, consent modal,
  guards, renamed reactive and accept-prefix).
- `sespy/translations/core.json` includes 27 new keys per §5, in all
  9 languages.
- `pyproject.toml` reflects the dep additions and package-data fix
  per §7.
- `tests/test_claude_backend.py` (32 tests), updated `tests/test_wizard.py`
  (+14 tests), and `tests/test_wizard_e2e.py` (+2 cases) all pass.
- Wheel-install verification: `translations/core.json` listed in the
  built wheel. POSIX: `python -m zipfile -l dist/sespy-*.whl | grep core.json`.
  PowerShell: `Get-ChildItem dist\sespy-*.whl | ForEach-Object { python -m zipfile -l $_.FullName } | Select-String core.json`.
- Full pre-existing test suite still green (no regressions).
- README bumps unit-test count (180 → ~225) and adds the "Optional
  Claude API backend" section per §1.1.
- Branch `feat/ai-isa-wizard-sp4` ready for fast-forward merge to
  main.

---

*End of spec.*
