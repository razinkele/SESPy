# AI-ISA Wizard SP4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional Claude API backend to the AI-ISA wizard's connection-suggestion step, opt-in per wizard run via a [Generate with Claude API] button + consent modal. Side-by-side with the existing SP3 rule-based scorer; preserves SP3 as always-rendered baseline; falls back to SP3 on any API failure.

**Architecture:** Bottom-up TDD. Data-layer constants (Slug, _CONN_TYPES, _VALID_TYPE_PAIRS) move into `sespy/data_structure.py` (single source of truth for both backends). New pure-Python module `sespy/claude_backend.py` carries the Anthropic SDK call, structured-output extraction, validation pipeline returning a `ValidationOutcome` envelope, and a `Literal`-tagged `ClaudeBackendError`. The wizard module (`sespy/modules/ai_isa_wizard.py`) gains a sum-typed reactive `wizard_claude_status`, an `@reactive.extended_task` for the SDK call, an observer effect that maps task outcomes into the reactive, a 3-handler consent modal flow with in-flight + step-11 guards, a revised step-11 renderer with explicit empty-state branch + drop-counts badge + `assert_never` arms, and revised `_on_back` / `_on_finish` handlers. Test plan splits non-reactive tests into `tests/test_wizard.py` and reactive-context tests into `tests/test_wizard_e2e.py` (Option B from spec §6.3 — recommended given `@reactive.extended_task` has zero unit-test precedent in py-shiny's own suite).

**Tech Stack:** Python 3.11+, Shiny for Python ≥1.5, Anthropic SDK ≥0.50,<0.101 (`anthropic`), pytest + pytest-playwright + pytest-asyncio≥0.23.

**Spec:** `docs/superpowers/specs/2026-05-09-ai-isa-wizard-sp4-design.md` (v6.5 — 12 review rounds).

---

## Pre-flight

Before starting Task 1, work on a feature branch (matches SP1–SP3 pattern). All commits go on this branch; merge to main is fast-forward at end.

```bash
git checkout -b feat/ai-isa-wizard-sp4
git status   # confirm clean tree
```

The micromamba `shiny` env is the Python runtime per CLAUDE.md. All commands assume it's active or wrapped via `micromamba run -n shiny ...`.

### Task dependency graph

Tasks must run in order. Inter-task dependencies:

```
1 ──▶ 2 ──▶ 3 ──▶ 4 ──▶ 5 ──▶ 6 ──▶ 7 ──▶ 8 ──▶ 9
                                              │
                              ┌───────────────┴───────────┐
                              ▼                           ▼
                             10 ──▶ 11 ──▶ 12 ──▶ 13 ──▶ 14 ──▶ 15 ──▶ 16
                                                                       │
                                                                       ▼
                                                                  17 ──▶ 18
                                                                       │
                                                                       ▼
                                                                  19 ──▶ 20
```

**Critical:** Each task assumes its predecessors are committed and tests
green. If a task fails (Step 2 expectation differs, Step 4 tests don't
pass), STOP, surface the divergence, and request human review. Do NOT
attempt to fix the divergence by modifying scope; the task structure
preserves Red→Green→Refactor discipline that scope-creep would break.

### Shared symbols across tasks

Many tasks reference symbols defined in earlier tasks. Subagent runners
should know where each comes from to avoid re-defining them locally:

| Symbol | Defined in | Module |
|---|---|---|
| `Slug`, `_CONN_TYPES`, `_VALID_TYPE_PAIRS` | Task 1 | `sespy/data_structure.py` |
| `Element`, `WizardState`, `ConnectionSuggestion`, `ELEMENT_TYPE_MAP` | pre-SP4 (existing) | `sespy/data_structure.py` |
| `_DEFAULT_MODEL`, `_MAX_OUTPUT_TOKENS`, `_TIMEOUT_SECONDS`, `_MAX_ELEMENTS`, `_TOOL_NAME`, `_TYPE_TO_SLUG`, `_logger` | Task 3 | `sespy/claude_backend.py` (module-level) |
| `DropReason`, `ValidationOutcome`, `ClaudeErrorReason`, `ClaudeBackendError`, `_REASON_TO_I18N` | Task 3 | `sespy/claude_backend.py` |
| `_SYSTEM_PROMPT`, `_TOOL_DEFINITION` | Task 4 | `sespy/claude_backend.py` |
| `_DAPSIWRM_ORDER`, `_build_user_message` | Task 5 | `sespy/claude_backend.py` |
| `_extract_tool_input` | Task 6 | `sespy/claude_backend.py` |
| `_validate_and_coerce` | Task 7 | `sespy/claude_backend.py` |
| `suggest_connections` | Task 8 | `sespy/claude_backend.py` |
| `_ClaudeIdle/_Loading/_Returned/_Failed`, `ClaudeBackendStatus` | Task 12 | `sespy/modules/ai_isa_wizard.py` (module-top-level) |
| `wizard_claude_status`, `wizard_claude_consent_given`, `wizard_claude_generation` | Task 13 | `sespy/modules/ai_isa_wizard.py` (server-scope, inside `ai_isa_wizard_server`) |
| `_claude_task`, `_trigger_claude_call`, `_observe_claude_result` | Task 13 | `sespy/modules/ai_isa_wizard.py` (server-scope) |
| `_on_claude_generate_clicked`, `_on_consent_cancel`, `_on_consent_confirm` | Task 14 | `sespy/modules/ai_isa_wizard.py` (server-scope) |
| `_render_suggestions_table`, `_render_connection_review` (revised) | Task 15 | `sespy/modules/ai_isa_wizard.py` (module-top-level) |
| `_dedup_accepted` | Task 16 | `sespy/modules/ai_isa_wizard.py` (module-top-level) |

---

## Task 1: Add `Slug`, `_CONN_TYPES`, `_VALID_TYPE_PAIRS` to `data_structure.py`

**Files:**
- Modify: `sespy/data_structure.py` (extend existing file with new exports)
- Test: `tests/test_data_structure.py` (or create if absent)

**Goal:** Co-locate the type-pair topology constants with `ELEMENT_TYPE_MAP`. Both `connection_scorer` and `claude_backend` will import from here.

- [ ] **Step 1: Write the failing tests**

Create or extend `tests/test_data_structure.py`:

```python
"""Tests for the shared data-layer constants used by both backends."""
from typing import get_args

import pytest

from sespy.data_structure import (
    ELEMENT_TYPE_MAP,
    Slug,
    _CONN_TYPES,
    _VALID_TYPE_PAIRS,
)


def test_slug_literal_matches_element_type_map_keys():
    """Slug Literal members must equal the keys of ELEMENT_TYPE_MAP."""
    assert set(get_args(Slug)) == set(ELEMENT_TYPE_MAP.keys())
    assert len(get_args(Slug)) == 7


def test_conn_types_is_three_tuple_shape():
    """_CONN_TYPES preserves (from_slug, to_slug, key) 3-tuple shape from
    the original connection_scorer.py definition. Pinning this prevents
    a refactor from silently breaking tests/test_connection_scorer.py:491."""
    assert isinstance(_CONN_TYPES, list)
    assert len(_CONN_TYPES) == 10
    for entry in _CONN_TYPES:
        assert isinstance(entry, tuple)
        assert len(entry) == 3
        from_slug, to_slug, key = entry
        assert isinstance(from_slug, str)
        assert isinstance(to_slug, str)
        assert isinstance(key, str)
        assert key == f"{from_slug}_{to_slug}"


def test_conn_types_exact_entries():
    """The 10 type-pairs are the canonical DAPSI(W)R(M) directed edges."""
    expected = [
        ("drivers", "activities", "drivers_activities"),
        ("activities", "pressures", "activities_pressures"),
        ("pressures", "states", "pressures_states"),
        ("states", "impacts", "states_impacts"),
        ("impacts", "welfare", "impacts_welfare"),
        ("responses", "pressures", "responses_pressures"),
        ("responses", "drivers", "responses_drivers"),
        ("responses", "activities", "responses_activities"),
        ("welfare", "drivers", "welfare_drivers"),
        ("welfare", "responses", "welfare_responses"),
    ]
    assert _CONN_TYPES == expected


def test_valid_type_pairs_derives_from_conn_types():
    """_VALID_TYPE_PAIRS is the 2-tuple projection of _CONN_TYPES.
    Catches drift if either constant is later defined inline."""
    expected = frozenset(
        (from_slug, to_slug) for from_slug, to_slug, _key in _CONN_TYPES
    )
    assert _VALID_TYPE_PAIRS == expected
    assert isinstance(_VALID_TYPE_PAIRS, frozenset)
    assert len(_VALID_TYPE_PAIRS) == 10
```

- [ ] **Step 2: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_data_structure.py -v
```

Expected: ImportError or AttributeError — `Slug`, `_CONN_TYPES`, `_VALID_TYPE_PAIRS` not yet defined in `data_structure.py`.

- [ ] **Step 3: Add the three exports to `data_structure.py`**

Find the existing `ELEMENT_TYPE_MAP` block (around line 41) in `sespy/data_structure.py`. Immediately after its closing `}`, add:

```python
# ---------------------------------------------------------------------------
# DAPSI(W)R(M) connection-type topology — single source of truth for both
# the SP3 rule-based scorer (`connection_scorer.py`) and the SP4 Claude API
# backend (`claude_backend.py`). Co-located with ELEMENT_TYPE_MAP because
# this IS data structure (defines the framework's directed-graph topology).
# ---------------------------------------------------------------------------

Slug = Literal[
    "drivers", "activities", "pressures", "states",
    "impacts", "welfare", "responses",
]

# 10 type-pairs as (from_slug, to_slug, conn_type_key) 3-tuples.
# Iteration order matches DAPSI(W)R(M) layer flow.
_CONN_TYPES: list[tuple[Slug, Slug, str]] = [
    ("drivers", "activities", "drivers_activities"),
    ("activities", "pressures", "activities_pressures"),
    ("pressures", "states", "pressures_states"),
    ("states", "impacts", "states_impacts"),
    ("impacts", "welfare", "impacts_welfare"),
    ("responses", "pressures", "responses_pressures"),
    ("responses", "drivers", "responses_drivers"),
    ("responses", "activities", "responses_activities"),
    ("welfare", "drivers", "welfare_drivers"),
    ("welfare", "responses", "welfare_responses"),
]

# 2-tuple projection of _CONN_TYPES — used by validation pipelines for
# O(1) membership testing of model-emitted (from, to) pairs.
_VALID_TYPE_PAIRS: frozenset[tuple[Slug, Slug]] = frozenset(
    (from_slug, to_slug) for from_slug, to_slug, _key in _CONN_TYPES
)
```

Add `Literal` to the existing `from typing import` line at the top of the file if it's not already imported.

- [ ] **Step 4: Run tests to verify they pass**

```
micromamba run -n shiny pytest tests/test_data_structure.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/data_structure.py tests/test_data_structure.py
git commit -m "feat(data_structure): add Slug, _CONN_TYPES, _VALID_TYPE_PAIRS shared constants

Single source of truth for both connection_scorer (SP3) and claude_backend
(SP4 — coming). _CONN_TYPES preserves the (slug, slug, key) 3-tuple shape
from connection_scorer.py:52 to keep tests/test_connection_scorer.py:491
working after the refactor."
```

---

## Task 2: Refactor `connection_scorer.py` to import `_CONN_TYPES` from `data_structure`

**Files:**
- Modify: `sespy/connection_scorer.py` (replace local `_CONN_TYPES` with import)
- Test: `tests/test_connection_scorer.py` (existing — verify still passes unchanged)

**Goal:** Eliminate the local definition; preserve the existing `from sespy.connection_scorer import _CONN_TYPES` import path via Python's normal import behavior (the imported name becomes accessible as a module attribute).

- [ ] **Step 1: Run existing tests as baseline**

```
micromamba run -n shiny pytest tests/test_connection_scorer.py -v
```

Expected: all existing tests pass (33 logical / 46 pytest items per SP3 baseline).

- [ ] **Step 2: Edit `sespy/connection_scorer.py`**

In `sespy/connection_scorer.py`, find lines 48-63 (the `_CONN_TYPES` block with its preceding comment). REPLACE that block with a single import line near the top of the module (after the existing `from .data_structure import ...` line):

```python
# (top of file, in the existing imports section)
from .data_structure import _CONN_TYPES  # re-exported for SP3-era tests

# (delete the entire former _CONN_TYPES = [...] block)
```

Keep `_MAX_PER_TYPE = 15` and `_MIN_RELEVANCE = 0.3` exactly where they are. Only the `_CONN_TYPES` definition moves.

Verify the rest of `connection_scorer.py` (which uses `_CONN_TYPES` internally) requires no other changes — it consumes the constant by iterating; the iteration semantics are identical.

- [ ] **Step 3: Run existing tests to verify no regression**

```
micromamba run -n shiny pytest tests/test_connection_scorer.py -v
```

Expected: same pass count as baseline. The import line `from sespy.connection_scorer import suggest_connections, _CONN_TYPES` at `tests/test_connection_scorer.py:491` continues to work because `_CONN_TYPES` is now accessible as a module attribute via the `from ... import` re-binding.

- [ ] **Step 4: Run the data_structure tests too**

```
micromamba run -n shiny pytest tests/test_data_structure.py tests/test_connection_scorer.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sespy/connection_scorer.py
git commit -m "refactor(connection_scorer): import _CONN_TYPES from data_structure

The constant is now defined once in data_structure.py (SP4 prep). The
import line preserves sespy.connection_scorer._CONN_TYPES as a module
attribute, so tests/test_connection_scorer.py:491's import continues to
work without modification."
```

---

## Task 3: Create `sespy/claude_backend.py` skeleton — error taxonomy + `ValidationOutcome`

**Files:**
- Create: `sespy/claude_backend.py`
- Create: `tests/test_claude_backend.py`

**Goal:** Establish the module's data types (error class hierarchy, validation outcome envelope, drop-reason Literal). Subsequent tasks add the helper functions and the orchestrator.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_claude_backend.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: ImportError — `sespy.claude_backend` does not exist.

- [ ] **Step 3: Create `sespy/claude_backend.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/claude_backend.py tests/test_claude_backend.py
git commit -m "feat(claude_backend): module skeleton with error types and ValidationOutcome

Establishes the data types for the SP4 backend: ClaudeBackendError frozen
dataclass with Literal-tagged reason, ValidationOutcome envelope, and the
_REASON_TO_I18N map. Helper functions and the orchestrator land in
subsequent tasks.

Lazy 'import anthropic' is deferred to suggest_connections (Task 12) so
the module is importable in environments without the SDK."
```

---

## Task 4: Add the system prompt and `_TOOL_DEFINITION` to `claude_backend.py`

**Files:**
- Modify: `sespy/claude_backend.py` (append the system prompt + tool definition)
- Modify: `tests/test_claude_backend.py` (add Group 2 schema/forcing tests)

**Goal:** The system prompt + tool definition are static constants. Pinning them in tests prevents accidental drift (e.g., breaking the few-shot examples or the confidence enum).

- [ ] **Step 1: Add tests**

Append to `tests/test_claude_backend.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: ImportError on `_SYSTEM_PROMPT` and `_TOOL_DEFINITION`.

- [ ] **Step 3: Append the system prompt + tool definition to `claude_backend.py`**

After the `_REASON_TO_I18N` block, append:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: 15 passed (5 from Task 3 + 10 from Task 4).

- [ ] **Step 5: Commit**

```bash
git add sespy/claude_backend.py tests/test_claude_backend.py
git commit -m "feat(claude_backend): system prompt + tool definition

System prompt encodes the 6 rules (directions, polarity sign convention,
confidence enum, rationale length, ID-not-label, per-pair cap), few-shot
positive and negative examples, and quantity/ordering guidance. Tool
definition uses schema-level defences (additionalProperties:false, enum,
maxItems, maxLength). Schema confidence is the discrete enum
{0.3, 0.5, 0.7, 0.9} matching Rule 3."
```

---

## Task 5: Implement `_build_user_message`

**Files:**
- Modify: `sespy/claude_backend.py` (add the helper function)
- Modify: `tests/test_claude_backend.py` (add Group 1 message-construction tests)

- [ ] **Step 1: Add tests**

Append to `tests/test_claude_backend.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: 6 new failures (ImportError on `_build_user_message`).

- [ ] **Step 3: Implement `_build_user_message`**

Append to `sespy/claude_backend.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: 21 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/claude_backend.py tests/test_claude_backend.py
git commit -m "feat(claude_backend): _build_user_message serializer

Builds the user-message from a WizardState. Empty element groups skipped;
empty optional fields render as '(unspecified)'. id/label format clarifies
which field is opaque vs descriptive."
```

---

## Task 6: Implement `_extract_tool_input`

**Files:**
- Modify: `sespy/claude_backend.py` (add the extractor)
- Modify: `tests/test_claude_backend.py` (add Group 2 extraction tests)

- [ ] **Step 1: Add tests**

Append to `tests/test_claude_backend.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: 6 new failures (ImportError on `_extract_tool_input`).

- [ ] **Step 3: Implement `_extract_tool_input`**

Append to `sespy/claude_backend.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: 27 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/claude_backend.py tests/test_claude_backend.py
git commit -m "feat(claude_backend): _extract_tool_input with diagnostic shape errors

Iterates response.content blocks, last-write-wins on duplicate tool_use,
captures text content for both the mixed-response INFO log and the
shape-error diagnostic. Annotated as 'object' (not 'Any') so the type
checker forces structural checks on untrusted SDK output."
```

---

## Task 7: Implement `_validate_and_coerce`

**Files:**
- Modify: `sespy/claude_backend.py` (add the validation pipeline)
- Modify: `tests/test_claude_backend.py` (add Group 3 validation tests)

**Goal:** This is the largest task — 9 drop reasons + 2 coercion paths + the all-keys invariant + drop precedence. Tests are parameterized to keep the test count tight while covering all branches.

- [ ] **Step 1: Add tests**

Append to `tests/test_claude_backend.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: 12 new failures (ImportError on `_validate_and_coerce`).

- [ ] **Step 3: Implement `_validate_and_coerce`**

Append to `sespy/claude_backend.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: 39+ passed (12 new + parametrize-expanded).

- [ ] **Step 5: Commit**

```bash
git add sespy/claude_backend.py tests/test_claude_backend.py
git commit -m "feat(claude_backend): _validate_and_coerce with top-down drop precedence

9 drop reasons + 2 clamp arms (no key — defense-in-depth against schema
bypass; the schema enum [0.3, 0.5, 0.7, 0.9] is the authoritative
enforcer). bool exclusion BEFORE int/float check (Python: bool is int
subclass). math.isfinite catches NaN/inf which clamp comparisons would
NaN-poison. drops_by_reason all-keys invariant via dict.fromkeys."
```

---

## Task 8: Implement `suggest_connections` orchestrator

**Files:**
- Modify: `sespy/claude_backend.py` (add the orchestrator with try/finally INFO log)
- Modify: `tests/test_claude_backend.py` (add Group 4 error mapping + INFO log tests)

- [ ] **Step 1: Install the anthropic SDK in the test environment**

Per CLAUDE.md, prefer `micromamba install` over `pip install` whenever a
package is on conda-forge. `anthropic` is available on conda-forge:

```
micromamba install -n shiny -c conda-forge "anthropic>=0.50,<0.101"
```

If conda-forge resolution fails for any reason, fall back to pip:

```
micromamba run -n shiny pip install "anthropic>=0.50,<0.101"
```

Verify:

```
micromamba run -n shiny python -c "import anthropic; print(anthropic.__version__)"
```

- [ ] **Step 2: Add tests**

Append to `tests/test_claude_backend.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: ImportError on `suggest_connections`.

- [ ] **Step 4: Implement `suggest_connections`**

Append to `sespy/claude_backend.py`:

```python
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

    import anthropic                                   # lazy import
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
```

- [ ] **Step 5: Run tests to verify they pass**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: 50+ passed (parametrize-expanded over 4 SDK exception types).

- [ ] **Step 6: Commit**

```bash
git add sespy/claude_backend.py tests/test_claude_backend.py
git commit -m "feat(claude_backend): add suggest_connections orchestrator

Lazy 'import anthropic' inside the function so the module is importable
in environments without the SDK. SDK exception arms in most-specific-first
order (verified against the SDK source: AuthenticationError, RateLimitError
are subclasses of APIStatusError; APITimeoutError is a subclass of
APIConnectionError). Post-SDK extract+validate wrapper catches
non-ClaudeBackendError exceptions and wraps as reason='shape' so the
structured INFO log classifies the failure as status=error (without
this wrapper, an unforeseen exception in _validate_and_coerce would
propagate untagged and the finally would log status=ok). Single
try/finally emits one structured log line on success AND failure.

max_retries=0 in the Anthropic() constructor enforces the no-retries
cost-bounding contract (SDK default is 2). Pinned by
test_anthropic_client_constructed_with_max_retries_zero +
test_messages_create_called_exactly_once_on_rate_limit."
```

---

## Task 9: Add the lazy-import test for `claude_backend`

**Files:**
- Modify: `tests/test_claude_backend.py` (add Group 6 module-import tests)

- [ ] **Step 1: Add tests**

Append to `tests/test_claude_backend.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify behavior**

```
micromamba run -n shiny pytest tests/test_claude_backend.py::test_module_import_does_not_eagerly_import_anthropic tests/test_claude_backend.py::test_module_imports_with_no_env_var_set -v
```

Expected: 2 passed.

- [ ] **Step 3: Run the full claude_backend test suite as a sanity check**

```
micromamba run -n shiny pytest tests/test_claude_backend.py -v
```

Expected: ~52 passed (Group 1-4, 6).

- [ ] **Step 4: Commit**

```bash
git add tests/test_claude_backend.py
git commit -m "test(claude_backend): pin lazy-import contract for anthropic SDK"
```

---

## Task 10: Update `pyproject.toml` — anthropic dep, pytest-asyncio, package-data fix

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read the current pyproject.toml**

Inspect the existing file to know what's there:

```
cat pyproject.toml
```

- [ ] **Step 2: Edit `pyproject.toml`**

Apply three changes:

1. Add `"anthropic>=0.50,<0.101"` to `[project] dependencies`:
   ```toml
   dependencies = [
       "shiny>=1.5",
       "networkx>=3.0",
       "htmltools>=0.5",
       "pandas>=2.0",
       "pyvis>=0.3",
       "anthropic>=0.50,<0.101",
   ]
   ```
2. Add `"pytest-asyncio>=0.23"` to `[project.optional-dependencies] test`:
   ```toml
   test = [
       "pytest>=8",
       "pytest-playwright>=0.5",
       "pytest-asyncio>=0.23",
   ]
   ```
3. **Skip** the `asyncio_mode = "auto"` setting. The `tests/test_wizard_e2e.py`
   files are standalone async scripts (run via `python tests/test_X_e2e.py`,
   not pytest), and Task 17 + Task 18 (per Option B) do NOT need `pytest-asyncio`
   semantics. Adding `asyncio_mode = "auto"` would risk pytest re-interpreting
   the existing `async def case_*` functions across 26+ e2e files at collection
   time. The `pytest-asyncio` dep is added for forward-compat (Option A spike,
   if ever attempted) but is currently unused.
4. Update the package-data glob to include `translations/*.json`:
   ```toml
   [tool.setuptools.package-data]
   sespy = ["*.json", "translations/*.json"]
   ```

- [ ] **Step 3: Verify the existing test suite still passes after the edits**

```
micromamba run -n shiny pip install -e .
micromamba run -n shiny pytest -q
```

Expected: same pass count as before SP4. (No regressions from adding anthropic / pytest-asyncio / package-data fix.)

- [ ] **Step 4: Build and inspect the wheel to verify the package-data fix**

```
micromamba run -n shiny python -m build --wheel
# POSIX: python -m zipfile -l dist/sespy-*.whl | grep core.json
# Windows PowerShell: Get-ChildItem dist\sespy-*.whl | ForEach-Object { python -m zipfile -l $_.FullName } | Select-String core.json
```

Expected: `sespy/translations/core.json` listed in the wheel contents.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build(pyproject): SP4 deps + package-data fix for translations/

- anthropic>=0.50,<0.101 (runtime dep)
- pytest-asyncio>=0.23 (test extra; forward-compat — currently unused
  given test_*_e2e.py files are async scripts run via 'python', not
  pytest. asyncio_mode=auto deliberately NOT added: it would break
  collection of 26+ existing async-script e2e files.)
- package-data glob now includes 'translations/*.json' — closes a latent
  bug where sespy/translations/core.json may not have shipped in
  SP1/SP2/SP3 wheels."
```

---

## Task 11: Add 27 i18n keys to `core.json`

**Files:**
- Modify: `sespy/translations/core.json`

**Goal:** All 27 keys appended to the `wizard.*` group (logical order, not alphabetical) inside the top-level `"translation"` wrapper. Each key is a 9-language object; English authored, other 8 duplicate English pending translation (matches SP1/SP2/SP3 pattern).

- [ ] **Step 1: Find the end of the wizard.* group in core.json**

Open `sespy/translations/core.json`. Find the last `wizard.*` key (likely something like `wizard.placeholder_*` or `wizard.no_suggestions`). Note its position.

- [ ] **Step 2: Insert 27 new keys after the last wizard.* key**

Each key follows the per-language object shape:

```json
"wizard.claude_generate_button": {
  "en": "Generate with Claude API",
  "es": "Generate with Claude API",
  "fr": "Generate with Claude API",
  "de": "Generate with Claude API",
  "lt": "Generate with Claude API",
  "pt": "Generate with Claude API",
  "it": "Generate with Claude API",
  "no": "Generate with Claude API",
  "el": "Generate with Claude API"
},
```

Insert all 27 keys with their English values from spec §5:

| Key | English |
|---|---|
| `wizard.claude_generate_button` | `Generate with Claude API` |
| `wizard.claude_generating` | `Generating with Claude API…` |
| `wizard.claude_returned_zero` | `Claude returned no suggestions for this state.` |
| `wizard.claude_retry_after` | `Rate limited — retry in {s} s` |
| `wizard.claude_drops_badge` | `Showing {kept} of {raw} suggestions ({dropped} dropped)` |
| `wizard.claude_consent_title` | `Send your project to Anthropic?` |
| `wizard.claude_consent_body` | `Generating suggestions with Claude sends your wizard answers to Anthropic's API. The following fields are sent:` |
| `wizard.claude_consent_field_sea` | `Regional sea` |
| `wizard.claude_consent_field_ecosystem` | `Ecosystem type` |
| `wizard.claude_consent_field_countries` | `Countries` |
| `wizard.claude_consent_field_issues` | `Main issues` |
| `wizard.claude_consent_field_elements` | `All element labels and IDs` |
| `wizard.claude_consent_privacy_note` | `Anthropic processes API requests per their privacy policy: https://www.anthropic.com/legal/privacy. Default 30-day retention. Click Send to proceed; consent applies only to the current session.` |
| `wizard.claude_consent_confirm` | `Send` |
| `wizard.claude_consent_cancel` | `Cancel` |
| `wizard.claude_error_auth` | `Claude API: invalid API key. Used rule-based scoring.` |
| `wizard.claude_error_rate_limit` | `Claude API: rate limit reached. Try again shortly.` |
| `wizard.claude_error_timeout` | `Claude API: request timed out. Used rule-based scoring.` |
| `wizard.claude_error_network` | `Claude API: network error. Used rule-based scoring.` |
| `wizard.claude_error_other` | `Claude API call failed. Used rule-based scoring.` |
| `wizard.claude_error_shape` | `Claude API: response format unexpected. Used rule-based scoring.` |
| `wizard.claude_error_too_many` | `Project too large for Claude API (>200 elements). Used rule-based scoring.` |
| `wizard.claude_error_sdk_missing` | `Claude SDK not installed. Run pip install anthropic.` |
| `wizard.suggestions_rule_based_n` | `Rule-based suggestions ({n}):` |
| `wizard.suggestions_claude_n` | `Claude API suggestions ({n}):` |
| `wizard.duplicates_resolved_n` | `Resolved {discarded} discarded duplicate(s); {overwritten} replaced with higher-confidence version.` |
| `wizard.read_failures_n` | `Could not read {n} accept checkboxes. Re-check and click Finish again.` |

**Plus 3 additional table-header keys for the renderer (Task 15):**

First grep `sespy/translations/core.json` for `wizard.source`, `wizard.target`,
`wizard.polarity` — if any already exist (likely from SP1's existing
renderer), reuse them and SKIP adding here. Otherwise, add the missing
keys with these English values:

| Key | English |
|---|---|
| `wizard.source` | `Source` |
| `wizard.target` | `Target` |
| `wizard.polarity` | `Polarity` |

If all 3 are pre-existing, the SP4 i18n key total stays at 27. If any
are net-new, the total adjusts upward (e.g., 28 / 29 / 30 keys); update
all "27 new keys" mentions accordingly in §1.1, §2.1, the SP4 i18n test
fixture, and the test description.

For all 27 (or 30) keys: each value object has all 9 languages (`en, es, fr, de, lt, pt, it, no, el`) duplicating the English string. Add a trailing comma to the previous-last wizard.* key if it doesn't have one (strict JSON forbids trailing commas — but the previous key needs one before the next key starts).

- [ ] **Step 3: Validate JSON syntax**

```
micromamba run -n shiny python -c "import json; json.load(open('sespy/translations/core.json'))"
```

Expected: no exception.

- [ ] **Step 4: Add the i18n key-coverage tests**

Append to `tests/test_claude_backend.py`:

```python
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
```

- [ ] **Step 5: Run the i18n tests**

```
micromamba run -n shiny pytest tests/test_claude_backend.py::test_REASON_TO_I18N_bidirectional_check tests/test_claude_backend.py::test_all_sp4_non_error_i18n_keys_exist_in_core_json -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add sespy/translations/core.json tests/test_claude_backend.py
git commit -m "feat(i18n): add 27 SP4 keys to translations/core.json

5 button/UI + 10 consent modal + 8 error + 2 table headers + 2
dedup/read-failure. English authored; other 8 languages duplicate
English pending translation (matches SP1/SP2/SP3 pattern). Tests pin
the bidirectional check (every ClaudeErrorReason has a key; no orphan
wizard.claude_error_* keys beyond the map + sdk_missing carve-out)."
```

---

## Task 12: Wizard module — module-level types + accept-prefix rename

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` (add module-level dataclasses + the rename)

**Goal:** Establish the sum-typed dataclasses at module top-level, BEFORE adding the server-scope reactives in Task 13. Also performs the breaking rename `accept_suggestion_*` → `accept_sp3_*` at all call sites (verified zero hits in `tests/`).

- [ ] **Step 1: Read existing wizard module to find call sites**

```
grep -n "wizard_suggestions\|accept_suggestion_" sespy/modules/ai_isa_wizard.py
```

Expect ~6 hits (line numbers may shift): the reactive declaration, the 10→11 transition write, the `_render_connection_review` table render, the `_on_finish` accept-checkbox reads, and the renderer dispatch.

- [ ] **Step 2: Add module-level imports**

Near the top of `sespy/modules/ai_isa_wizard.py`, ensure these imports are present (add any missing):

```python
import asyncio
import logging
import os
from dataclasses import dataclass
from typing import assert_never

from shiny import reactive, ui, module, Inputs, Outputs, Session
from shiny.types import SilentException

from ..claude_backend import (    # NOTE: lazy import for runtime use lives in
    ClaudeBackendError,           #       the @reactive.extended_task body (Task 13).
    ClaudeErrorReason,            #       These top-level imports are types only —
    ValidationOutcome,            #       claude_backend itself imports nothing from
    _REASON_TO_I18N,              #       Shiny, and these classes are pure dataclasses
)                                 #       so they're safe to import unconditionally.
```

If `from ..claude_backend import ...` triggers a `ModuleNotFoundError` (anthropic not installed), the wizard module will fail to import. This is acceptable because Task 10 added `anthropic` as a hard runtime dep — if it's missing, every SESPy launch fails the same way. The §1.2 "Optional `anthropic` extras" deferred item documents the future-SP path to make this conditional.

- [ ] **Step 3: Add the 4 sum-type dataclasses at module top-level**

Insert AFTER the imports, BEFORE any `@module.server`-decorated function. These are types only — pure module-top-level. The corresponding `reactive.Value(...)` constructors live inside the server function in Task 13 (they require session context).

```python
# ---------------------------------------------------------------------------
# SP4 sum-typed status — distinguishes never-called, in-flight, returned-N,
# and failed states that an empty-list reactive would conflate.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _ClaudeIdle:
    pass


@dataclass(frozen=True)
class _ClaudeLoading:
    pass


@dataclass(frozen=True)
class _ClaudeReturned:
    outcome: ValidationOutcome


@dataclass(frozen=True)
class _ClaudeFailed:
    error: ClaudeBackendError


ClaudeBackendStatus = (
    _ClaudeIdle | _ClaudeLoading | _ClaudeReturned | _ClaudeFailed
)


_logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Rename `wizard_suggestions` → `wizard_suggestions_sp3` and `accept_suggestion_` → `accept_sp3_` everywhere in the wizard module**

Find each occurrence (per Step 1 grep) and rename. Do NOT touch test files (verified zero references). Specific changes:

- `wizard_suggestions: reactive.Value[list[ConnectionSuggestion]] = reactive.Value([])` → `wizard_suggestions_sp3: reactive.Value[list[ConnectionSuggestion]] = reactive.Value([])`
- `wizard_suggestions.set(...)` → `wizard_suggestions_sp3.set(...)`
- `wizard_suggestions.get()` → `wizard_suggestions_sp3.get()`
- `f"accept_suggestion_{i}"` → `f"accept_sp3_{i}"` (in both the renderer's `ui.input_checkbox(...)` and the `_on_finish` reads)

- [ ] **Step 5: Run the existing wizard test suite to verify no breakage from the rename**

```
micromamba run -n shiny pytest tests/test_wizard.py tests/test_wizard_e2e.py -v
```

Expected: same pass count as before. The wizard module imports cleanly; existing flows still work because the rename is internal.

- [ ] **Step 6: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "refactor(wizard): module-level SP4 types + accept-checkbox prefix rename

Add module-top-level dataclasses for ClaudeBackendStatus sum type
(_ClaudeIdle | _ClaudeLoading | _ClaudeReturned | _ClaudeFailed); these
are pure types and live alongside other module-level definitions. The
reactive.Value() constructors will live inside ai_isa_wizard_server
(Task 13) since they require session context.

Also rename wizard_suggestions → wizard_suggestions_sp3 and
accept_suggestion_* → accept_sp3_* throughout the module (verified zero
hits in tests/). Disambiguates SP3 vs SP4 in the upcoming side-by-side
rendering."
```

---

## Task 13: Wizard module — server-scope reactives + extended task + observer effect

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` (add server-scope reactives + extended task + observer)

**Goal:** Inside the existing `ai_isa_wizard_server` function, add the three new SP4 reactives, the `@reactive.extended_task` `_claude_task`, the result-observer effect, and the trigger function. Do NOT yet add the click handler or modal handlers — those land in Task 14.

- [ ] **Step 1: Locate the existing server-scope reactives**

In `sespy/modules/ai_isa_wizard.py`, find `wizard_suggestions_sp3 = reactive.Value(...)` (renamed in Task 12) inside `ai_isa_wizard_server`. The new reactives go alongside it.

- [ ] **Step 2: Add the three new server-scope reactives**

Just after `wizard_suggestions_sp3 = reactive.Value([])`, add:

```python
# SP4 sum-typed status reactive (alongside wizard_suggestions_sp3 above).
wizard_claude_status: reactive.Value[ClaudeBackendStatus] = (
    reactive.Value(_ClaudeIdle())
)
# One-time per-session consent flag; reset on new session.
wizard_claude_consent_given: reactive.Value[bool] = reactive.Value(False)
# Generation counter — incremented on Back-from-11. The extended task
# captures the generation at start; the observer compares before
# writing wizard_claude_status. Stale results are silently discarded.
wizard_claude_generation: reactive.Value[int] = reactive.Value(0)
```

- [ ] **Step 3: Add the `@reactive.extended_task` and `_trigger_claude_call` helper**

Inside the same `ai_isa_wizard_server` function, after the reactives:

```python
@reactive.extended_task
async def _claude_task(
    state: WizardState, generation: int,
) -> tuple[int, ValidationOutcome]:
    """Capture generation alongside outcome so the observer can discard
    stale results (Back-while-loading race)."""
    # Lazy import inside the task body — runs only when the task is
    # invoked (not at module load).
    from ..claude_backend import suggest_connections as _claude_impl
    outcome = await asyncio.to_thread(_claude_impl, state)
    return (generation, outcome)


def _trigger_claude_call() -> None:
    """Snapshot state + generation, mark Loading, invoke the task.
    Step assertion guards against stale events (e.g., Back-without-
    dismiss + queued Confirm)."""
    if wizard_step.get() != 11:
        return
    state = _assemble_wizard_state()
    generation = wizard_claude_generation.get()
    wizard_claude_status.set(_ClaudeLoading())
    _claude_task(state, generation)
```

(`_assemble_wizard_state` is a pre-existing SP1 closure inside `ai_isa_wizard_server` — re-use it as-is.)

- [ ] **Step 4: Add the observer effect**

Same scope:

```python
@reactive.effect
def _observe_claude_result() -> None:
    """Maps task outcome into wizard_claude_status. NB: no
    @reactive.event — the dependency on _claude_task.status is
    registered by the unconditional .result() read. Adding
    @reactive.event would break the dependency. The initial-run
    SilentException is expected."""
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
        # Catch-all: AttributeError if response is None; RuntimeError
        # from asyncio thread oddities; future SDK exceptions outside
        # the documented set. Without this, an unforeseen exception
        # leaves the spinner stuck in Loading forever.
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
        # Log so operators can detect Back-during-loading frequency
        # (cost-ceiling honesty: the call was paid, result discarded).
        _logger.info(
            "claude observer: discarded stale result "
            "(captured_generation=%d, current=%d)",
            captured_generation, wizard_claude_generation.get(),
        )
        return
    wizard_claude_status.set(_ClaudeReturned(outcome=outcome))
```

- [ ] **Step 5: Verify the wizard module still imports cleanly**

```
micromamba run -n shiny python -c "from sespy.modules import ai_isa_wizard"
```

Expected: no error. (The extended task + observer are declared but not exercised.)

- [ ] **Step 6: Run existing tests as a regression check**

```
micromamba run -n shiny pytest tests/test_wizard.py tests/test_wizard_e2e.py -v
```

Expected: same pass count as before (the new reactives + task + observer are inert until invoked by the click handler in Task 14).

- [ ] **Step 7: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): @reactive.extended_task + observer effect

Adds the SP4 server-scope reactives (wizard_claude_status,
wizard_claude_consent_given, wizard_claude_generation), the extended
task (lazy-imports claude_backend in its body), the observer effect
that maps task outcomes into the sum-typed reactive, and the
_trigger_claude_call helper with step-11 assertion. Inert until the
click handler arrives (Task 14)."
```

---

## Task 14: Wizard module — consent modal flow + click handler

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` (add three @reactive.effect handlers for the consent flow)

- [ ] **Step 1: Add the click handler with in-flight + consent guards**

Inside `ai_isa_wizard_server`, after `_observe_claude_result`:

```python
@reactive.effect
@reactive.event(input.wizard_claude_generate, ignore_init=True)
def _on_claude_generate_clicked() -> None:
    """First-stage handler: in-flight guard, then consent or call."""
    # In-flight guard — protects against rapid-clicks during Loading.
    if isinstance(wizard_claude_status.get(), _ClaudeLoading):
        return
    if wizard_claude_consent_given.get():
        # Already consented — go straight to call.
        _trigger_claude_call()
        return
    # First click — show consent modal.
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
```

- [ ] **Step 2: Verify wizard module still imports**

```
micromamba run -n shiny python -c "from sespy.modules import ai_isa_wizard"
```

Expected: no error.

- [ ] **Step 3: Run regression suite**

```
micromamba run -n shiny pytest tests/test_wizard.py tests/test_wizard_e2e.py -v
```

Expected: same pass count (handlers are inert until the button is rendered + clicked).

- [ ] **Step 4: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): consent modal flow + click handler

Three @reactive.effect handlers: button-click (in-flight + consent
guards), consent-cancel (modal_remove only), consent-confirm
(defensive in-flight guard, set consent, dismiss modal, trigger call).
Modal copy uses the new i18n keys; bullet list discloses the 5 fields
sent to Anthropic per §10.2."
```

---

## Task 15: Wizard module — revised step-11 renderer

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` (revise `_render_connection_review` + extract `_render_suggestions_table` helper)

**Goal:** Two-table side-by-side rendering, drop-counts badge, empty-state branch, `assert_never` arms for exhaustiveness.

- [ ] **Step 1: Locate the existing `_render_connection_review`**

Open `sespy/modules/ai_isa_wizard.py`. Find `_render_connection_review` (around line 156). Read its current body to understand the inline table-building.

- [ ] **Step 2: Extract `_render_suggestions_table` helper**

**Read the existing renderer FIRST** (`sespy/modules/ai_isa_wizard.py:156-199`)
to capture its exact column structure and i18n key usage. The SP1 renderer uses:
- 6 columns: `# | Source | Target | Confidence | Rationale | Accept` (row-number
  first, accept-checkbox LAST, NO Polarity column).
- Header labels via i18n keys: `t("wizard.confidence")`, `t("wizard.rationale")`,
  `t("wizard.accept")`. (Source/Target may be inline strings — check.)
- Single `<table>` wrapping (no `<thead>`/`<tbody>` separation).

The SP4 helper MUST preserve this exact column structure to maintain visual
continuity for SP3 users. SP4 introduces the **Polarity** column for both
SP3 and SP4 tables (the spec assumes side-by-side parity). Add a 7th column.

Required i18n key additions to Task 11 (NOT in the original 27-key list):
- `wizard.source` — "Source" (and 8 duplicates)
- `wizard.target` — "Target" (and 8 duplicates)
- `wizard.polarity` — "Polarity" (and 8 duplicates)

(If `wizard.source` / `wizard.target` already exist in `core.json` from
SP1, reuse — DO NOT re-add. Grep `core.json` for `wizard.source` /
`wizard.target` first.)

Helper structure (matching SP1's column order + new Polarity column):

```python
def _render_suggestions_table(
    items: list[ConnectionSuggestion],
    *,
    prefix: str,
    title: str,
) -> ui.Tag:
    """Render a suggestions table with accept-checkboxes.
    `prefix` is the input-id prefix ('accept_sp3_' or 'accept_sp4_').
    Extracted from the existing inline rendering in
    _render_connection_review (SP1) to support the SP4 two-table flow.
    Column order matches SP1: # | Source | Target | Polarity | Confidence
    | Rationale | Accept (Polarity column added for SP4 parity).
    """
    rows = []
    rows.append(ui.tags.tr(
        ui.tags.th("#"),
        ui.tags.th(t("wizard.source") if "wizard.source" in <i18n-loaded> else "Source"),
        ui.tags.th(t("wizard.target") if "wizard.target" in <i18n-loaded> else "Target"),
        ui.tags.th(t("wizard.polarity") if "wizard.polarity" in <i18n-loaded> else "Polarity"),
        ui.tags.th(t("wizard.confidence")),
        ui.tags.th(t("wizard.rationale")),
        ui.tags.th(t("wizard.accept")),
    ))
    for i, s in enumerate(items):
        rows.append(ui.tags.tr(
            ui.tags.td(str(i + 1)),
            ui.tags.td(s.source),
            ui.tags.td(s.target),
            ui.tags.td(s.polarity),
            ui.tags.td(f"{s.confidence:.2f}"),
            ui.tags.td(s.rationale),
            ui.tags.td(ui.input_checkbox(f"{prefix}{i}", "", value=False)),
        ))
    return ui.tags.div(
        ui.tags.h6(title),
        ui.tags.table(*rows, class_="table table-sm"),
    )
```

**Pseudocode notation `<i18n-loaded>`** is for the implementer's clarity:
treat it as "if the key exists in core.json, use t(...); otherwise inline
the English string". The simpler implementation: just call `t(...)`
unconditionally — if the key is missing, `t()` returns the key string verbatim,
which is acceptable as a fallback. Use:

```python
ui.tags.th(t("wizard.source")),
ui.tags.th(t("wizard.target")),
ui.tags.th(t("wizard.polarity")),
```

and add the 3 keys to Task 11. This is the cleaner approach.

- [ ] **Step 3: Replace `_render_connection_review` body**

Replace the existing function body with:

```python
def _render_connection_review(
    sp3: list[ConnectionSuggestion],
    sp4_status: ClaudeBackendStatus,
    claude_available: bool,
) -> ui.Tag:
    parts: list[ui.Tag] = []

    # Empty-state branch: preserve the friendly SP1 message when there's
    # nothing to show AND no Claude path.
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

    # SP3 table — always shown (even if empty, for side-by-side layout).
    parts.append(_render_suggestions_table(
        sp3, prefix="accept_sp3_",
        title=t("wizard.suggestions_rule_based_n").format(n=len(sp3)),
    ))

    # Generate-with-Claude button — only when env key set + not disabled.
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

    # SP4 table — render based on status.
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

- [ ] **Step 4: Update the renderer call site**

Find the renderer call (probably in the step-render dispatch around `archetype == "connection_review"`). Update the call:

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

- [ ] **Step 5: Run regression suite**

```
micromamba run -n shiny pytest tests/test_wizard.py tests/test_wizard_e2e.py -v
```

Expected: same pass count as Task 14. The renderer is updated but no tests exercise the new branches yet.

- [ ] **Step 6: Smoke-test the app launches**

```
micromamba run -n shiny shiny run --port 8000 app.py
# In another shell: curl http://localhost:8000/ | head -20
# Stop with Ctrl+C
```

Expected: app starts cleanly, returns HTML.

- [ ] **Step 7: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): revised step-11 renderer with side-by-side tables

Two-table rendering: SP3 always shown; SP4 below button after success.
Empty-state branch preserves the SP1 'no_suggestions' message when
SP3 is empty AND no Claude path. Drop-counts badge surfaces validation
drops to the user. assert_never arms enforce exhaustiveness over
ClaudeBackendStatus. Button visibility gated by ANTHROPIC_API_KEY
truthy AND SESPY_DISABLE_CLAUDE falsy."
```

---

## Task 16: Wizard module — revised `_on_back` and `_on_finish`

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` (revise existing handlers)

- [ ] **Step 1: Revise `_on_back`**

Find the existing `_on_back` reactive effect. Add a new branch at the TOP of the function body (BEFORE the existing step-decrement / freeform-counts re-seed logic):

```python
@reactive.effect
@reactive.event(input.wizard_back, ignore_init=True)
def _on_back() -> None:
    if wizard_step.get() == 11:
        # Defensively dismiss any open consent modal.
        ui.modal_remove()
        wizard_claude_status.set(_ClaudeIdle())
        # Bump generation; in-flight task results will fail the staleness check.
        wizard_claude_generation.set(
            wizard_claude_generation.get() + 1
        )
        # wizard_suggestions_sp3 will be repopulated on the next 10->11.
    # ... existing step-decrement + freeform-counts re-seed logic, unchanged.
```

(Preserve the existing body exactly — the new block is additive at the top.)

- [ ] **Step 2: Revise `_on_finish`**

Find the existing `_on_finish` reactive effect. Replace the accept-reading + Connection-write section with the dedup-aware version:

```python
@reactive.effect
@reactive.event(input.wizard_finish, ignore_init=True)
def _on_finish() -> None:
    if wizard_step.get() != 11:
        return

    accepted: list[ConnectionSuggestion] = []
    read_failures = 0

    # Read SP3 acceptances first (so ties favor SP3 in dedup).
    for i, s in enumerate(wizard_suggestions_sp3.get()):
        try:
            if input[f"accept_sp3_{i}"]():
                accepted.append(s)
        except SilentException:
            raise   # Shiny session disconnect — propagate, don't swallow.
        except KeyError as e:
            _logger.warning("accept checkbox sp3_%d not found: %s", i, e)
            read_failures += 1

    # Read SP4 acceptances if any.
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
        # Deliberate abort-and-retry semantics: if ANY checkbox read
        # fails, we surface the toast and require the user to click
        # Finish again. Rationale: a failed read indicates a transient
        # render/session issue; partial commit could lose the user's
        # accept clicks they THINK they made (the failed-to-read
        # checkbox might have been ON). Aborting protects against
        # silent partial-acceptance. The trade-off: if the same
        # transient race recurs on the next Finish click, the user
        # gets stuck — but in practice render races are rare and
        # idempotent retries succeed.
        ui.notification_show(
            t("wizard.read_failures_n").format(n=read_failures),
            type="warning", duration=6,
        )
        return

    # Delegate dedup to the shared helper. This keeps the production
    # code AND the unit tests in tests/test_wizard.py exercising the
    # exact same algorithm — not a copy.
    final, discarded, overwritten = _dedup_accepted(accepted)

    if discarded or overwritten:
        ui.notification_show(
            t("wizard.duplicates_resolved_n").format(
                discarded=discarded, overwritten=overwritten,
            ),
            type="message", duration=4,
        )
    # ... existing Connection-write path: build new isa_data, set
    # project_data, emit isa_change + cld_update — unchanged from SP1/SP3.
```

**Important variable rename in the preserved Connection-write block:** the
existing SP1/SP3 code reads `for s in accepted: ...` to build Connection
objects. After this refactor, `final` (the dedup'd list) is what should be
iterated. Update `for s in accepted:` to `for s in final:` in the
preserved block — this is the ONLY change to the Connection-write path
itself; everything else (Connection construction, `project_data.set(...)`,
`event_bus.emit_isa_change()`, `emit_cld_update()`, `wizard_active.set(False)`,
final notification) is unchanged.

**Also add the `_dedup_accepted` helper as a module-level pure function**
in `sespy/modules/ai_isa_wizard.py` (NOT inside `ai_isa_wizard_server` —
this needs to be importable by tests):

```python
# At module top-level (after the imports, before @module.ui or any
# server function — alongside _render_suggestions_table from Task 15).

def _dedup_accepted(
    accepted: list[ConnectionSuggestion],
) -> tuple[list[ConnectionSuggestion], int, int]:
    """Pure-data dedup helper extracted from _on_finish.

    Dedups by (source, target, polarity) — different polarity for the
    same edge is NOT a duplicate. On confidence tie, the FIRST entry
    wins (iteration order; in _on_finish, SP3 is iterated first so SP3
    wins ties).

    Returns (deduped_list, discarded_count, overwritten_count).
    Extracted so tests/test_wizard.py can exercise the exact same
    algorithm production code uses — NOT a copy.
    """
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
    return list(seen.values()), discarded, overwritten
```

- [ ] **Step 3: Run regression suite**

```
micromamba run -n shiny pytest tests/test_wizard.py tests/test_wizard_e2e.py -v
```

Expected: same pass count. No SP4 tests yet exercise the new logic.

- [ ] **Step 4: Smoke-test the wizard end-to-end manually (no API key)**

```
micromamba run -n shiny shiny run --port 8000 app.py
# Browser: open http://localhost:8000/
# Navigate the wizard through all 12 steps. At step 11:
# - SP3 table renders (existing behavior).
# - No "Generate with Claude API" button (no API key set).
# - Click Finish, verify accepted suggestions become Connections.
```

Expected: existing SP1+SP3 flow unchanged.

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): _on_back + _on_finish revisions for SP4

_on_back: dismisses open consent modal, resets wizard_claude_status to
Idle, bumps generation counter on Back-from-step-11. Generation bump
ensures in-flight task results fail the staleness check.

_on_finish: dedup-aware merge of SP3 + SP4 accepted suggestions. Reads
both index spaces (accept_sp3_*, accept_sp4_*); SilentException
re-raised (Shiny session disconnect); KeyError logged + counted with
short-circuit toast. Dedup by (source, target, polarity), higher
confidence wins, ties go to SP3 (iterated first). Different polarity
for same pair is NOT a duplicate."
```

---

## Task 17: Wizard non-reactive tests in `tests/test_wizard.py`

**Files:**
- Modify: `tests/test_wizard.py` (add tests that don't require Shiny reactive context)

**Goal:** Per spec §6.3 Option B (recommended), the 5 reactive-context-dependent tests live in e2e (Task 18). Here we add the 9 non-reactive tests: button-visibility env-var checks, dedup logic, and read-failures behavior.

- [ ] **Step 1: Read existing test_wizard.py to confirm pure-data layer testing pattern**

```
head -50 tests/test_wizard.py
```

Expected: tests import from `sespy.wizard` (pure-data layer). Tests don't drive the Shiny module.

- [ ] **Step 2: Add tests at the end of `tests/test_wizard.py`**

```python
# ===========================================================================
# SP4 dedup logic tests — pure-data layer (no Shiny reactive context required).
# These test the dedup helper only; the full _on_finish flow is exercised
# via e2e in tests/test_wizard_e2e.py.
# ===========================================================================

import pytest

from sespy.data_structure import ConnectionSuggestion
# Import the production helper directly — NOT a copy. Tests below
# exercise the exact same algorithm _on_finish uses.
from sespy.modules.ai_isa_wizard import _dedup_accepted as _dedup


def _make_sug(source, target, polarity, confidence, rationale="r"):
    return ConnectionSuggestion(
        source=source, target=target, polarity=polarity,
        confidence=confidence, rationale=rationale,
    )


def test_dedup_keeps_both_polarities_for_same_pair():
    """(D001, A001, +) and (D001, A001, -) co-exist — different polarity
    is NOT a duplicate."""
    pos = _make_sug("D001", "A001", "+", 0.9)
    neg = _make_sug("D001", "A001", "-", 0.7)
    final, discarded, overwritten = _dedup([pos, neg])
    assert len(final) == 2
    assert {(s.source, s.target, s.polarity) for s in final} == {
        ("D001", "A001", "+"), ("D001", "A001", "-"),
    }
    assert discarded == 0 and overwritten == 0


def test_dedup_drops_lower_confidence_same_polarity():
    sp3 = _make_sug("D001", "A001", "+", 0.5, rationale="sp3 r")
    sp4 = _make_sug("D001", "A001", "+", 0.9, rationale="sp4 r")
    # SP3 first, then SP4 (real iteration order in _on_finish).
    final, discarded, overwritten = _dedup([sp3, sp4])
    assert len(final) == 1
    # Higher confidence wins.
    assert final[0].confidence == 0.9
    assert final[0].rationale == "sp4 r"
    assert overwritten == 1
    assert discarded == 0


def test_dedup_tie_break_favors_sp3_via_iteration_order():
    """Equal confidence — first-iterated entry wins (the SP3 entry,
    since SP3 is read before SP4 in _on_finish)."""
    sp3 = _make_sug("D001", "A001", "+", 0.7, rationale="sp3 r")
    sp4 = _make_sug("D001", "A001", "+", 0.7, rationale="sp4 r")
    final, discarded, overwritten = _dedup([sp3, sp4])
    assert len(final) == 1
    assert final[0].rationale == "sp3 r"
    assert discarded == 1
    assert overwritten == 0
```

- [ ] **Step 3: Run the new tests**

```
micromamba run -n shiny pytest tests/test_wizard.py -v -k "dedup"
```

Expected: 3 passed.

- [ ] **Step 4: Run the full test_wizard.py to verify no regressions**

```
micromamba run -n shiny pytest tests/test_wizard.py -v
```

Expected: existing pass count + 3 new.

- [ ] **Step 5: Commit**

```bash
git add tests/test_wizard.py
git commit -m "test(wizard): add SP4 dedup tests against the shared helper

Per spec §6.3 Option B: the 5 reactive-context-dependent tests
(button visibility, consent modal, observer error mapping,
stale-generation discard, modal-removal-on-Back, step-mismatch guard)
live in tests/test_wizard_e2e.py — Playwright drives the full app
and asserts on DOM state. Here we cover only the pure-data dedup
helper.

Tests import the production _dedup_accepted helper directly from
sespy.modules.ai_isa_wizard — NOT a copy of the dedup body. This
prevents test/production drift: a future change to _on_finish's
dedup logic must update _dedup_accepted, which both production and
tests exercise."
```

---

## Task 18: Wizard e2e tests — async-script additions (consent flow + button visibility + modal-on-Back + retry-disable)

**Files:**
- Modify: `tests/test_wizard_e2e.py` (add async cases consistent with existing pattern)

**Goal:** Per spec §6.3 Option B, reactive-context-dependent assertions belong in e2e. **Important:** the existing `tests/test_wizard_e2e.py` is a **standalone async script** run via `python tests/test_wizard_e2e.py` (NOT pytest-managed). All cases are `async def case_*(page)`, called from `async def main()` via `asyncio.run(main())` at module bottom. Playwright is used via `playwright.async_api.async_playwright`. There is no `pytest-playwright`, no `monkeypatch` fixture, no `unittest.mock.patch` available. New cases MUST follow the same pattern.

**Cross-process mocking caveat:** the test process and the Shiny app process are separate. `unittest.mock.patch` in the test process does NOT affect symbols inside the running app. Therefore, the mocking strategy from earlier drafts of this plan is unworkable. New approach:

- For consent-flow visibility tests (modal show/hide, button visibility, modal-on-Back): set `ANTHROPIC_API_KEY` to a deliberately-fake value BEFORE launching the app (e.g., `set ANTHROPIC_API_KEY=test-fake-key & shiny run --port 8000 app.py`). The button visibility, modal flow, and consent persistence are exercised cross-process; the actual API call (when Confirm is clicked) returns `auth` error, which is part of the testable path.
- For retry-disable test: same approach — set fake key, click Generate + Confirm, observe the auth-error toast (the spec's documented behavior). The retry-after-disabled-button state requires a real `RateLimitError` response which isn't easily simulated cross-process; this specific test is **deferred to a future SP** with proper in-process Shiny test infrastructure (added to §11 open questions during plan execution).
- For drop-counts-badge and observer-success tests requiring specific `ValidationOutcome`: same deferral — these need in-process testing.

The 4 cases below are what's testable cross-process. The 3 deferred cases (retry-disabled-button, drop-counts-badge, observer-success-table-render) are documented as TODOs at the end of Task 18.

- [ ] **Step 1: Read existing e2e test structure**

```
grep -n "^async def case_\|^async def main\|asyncio.run" tests/test_wizard_e2e.py | head -30
```

Verify the file uses `asyncio.run(main())` at bottom and `async def case_*(page)` throughout. The namespace prefix `wizard-` applies to all SP4 inputs (verified in spec §6.4). The existing helper `_start_wizard_empty_via_replace(page)` (around line 28) navigates from boot to step-0-empty-wizard.

- [ ] **Step 2: Add an async helper `_drive_to_step_11(page)` that mirrors `case_full_run`**

Open `tests/test_wizard_e2e.py`, find the existing `case_full_run` (around line 57). Copy its step 0–10 navigation logic into a new helper near the top of the file (after `_start_wizard_empty_via_replace`):

```python
async def _drive_to_step_11(page):
    """Reusable: drive the wizard from boot through step-10 → Next →
    step 11. Mirrors the navigation portion of case_full_run; copy-adapt
    the exact `Shiny.setInputValue` / click sequence from there.
    Pre-condition: app running on http://127.0.0.1:8000."""
    await _start_wizard_empty_via_replace(page)
    # ... (copy from case_full_run: 12 steps of input setting + Next clicks)
    # End state: wizard_step == 11; SP3 table rendered; ready for SP4 button click.
```

The implementer copies the body verbatim from `case_full_run`, stopping at the click that transitions step 10 → 11.

- [ ] **Step 3: Add 4 new async cases (cross-process-testable)**

Append to `tests/test_wizard_e2e.py` (BEFORE the `async def main():` block):

```python
async def case_claude_button_not_rendered_without_env_key(page):
    """No ANTHROPIC_API_KEY → no button at step 11.
    Pre-condition: launch app WITHOUT setting ANTHROPIC_API_KEY."""
    print("\n=== case 7: Claude button hidden without env key ===")
    await _drive_to_step_11(page)
    button = await page.query_selector("#wizard-wizard_claude_generate")
    assert button is None, "expected no button without ANTHROPIC_API_KEY"


async def case_claude_consent_modal_shows_and_dismisses_via_cancel(page):
    """First click on Generate shows consent modal; Cancel dismisses it.
    Pre-condition: launch app with ANTHROPIC_API_KEY=test-fake-key."""
    print("\n=== case 8: Claude consent modal show + Cancel ===")
    await _drive_to_step_11(page)
    # Verify button is visible (env key was set at app launch).
    await page.wait_for_selector("#wizard-wizard_claude_generate", timeout=5000)
    # Click → consent modal appears.
    await page.click("#wizard-wizard_claude_generate")
    await page.wait_for_selector("text=Send your project to Anthropic?", timeout=5000)
    # Cancel → modal closes (Bootstrap leaves nodes in DOM with display:none;
    # use state="hidden", not state="detached").
    await page.click("#wizard-wizard_claude_consent_cancel")
    await page.wait_for_selector("text=Send your project to Anthropic?",
                                  state="hidden", timeout=5000)
    # Click button again → modal re-appears (consent did not persist on decline).
    await page.click("#wizard-wizard_claude_generate")
    await page.wait_for_selector("text=Send your project to Anthropic?", timeout=5000)
    # Cleanup: dismiss modal so subsequent cases start clean.
    await page.click("#wizard-wizard_claude_consent_cancel")


async def case_claude_consent_then_confirm_yields_auth_error(page):
    """Click Generate → Confirm with the fake API key → backend raises
    AuthenticationError → toast shows 'Claude API: invalid API key.
    Used rule-based scoring.' SP3 table remains visible.
    Pre-condition: launch app with ANTHROPIC_API_KEY=test-fake-key."""
    print("\n=== case 9: Claude consent + Confirm → auth-error toast ===")
    await _drive_to_step_11(page)
    await page.click("#wizard-wizard_claude_generate")
    await page.wait_for_selector("text=Send your project to Anthropic?", timeout=5000)
    await page.click("#wizard-wizard_claude_consent_confirm")
    # Wait for the auth error toast (the real backend will reject the fake key).
    # The exact toast text comes from wizard.claude_error_auth.
    await page.wait_for_selector("text=Claude API: invalid API key",
                                  timeout=15000)
    # SP3 table still visible (side-by-side fallback semantics).
    await page.wait_for_selector("#wizard-accept_sp3_0", timeout=2000)


async def case_back_from_step_11_dismisses_consent_modal(page):
    """Open modal, click Back without dismissing; modal goes away.
    Pre-condition: launch app with ANTHROPIC_API_KEY=test-fake-key.

    Note on the click: Bootstrap renders a .modal-backdrop overlay that
    intercepts pointer events to elements behind the modal. Playwright's
    default page.click() runs an actionability check (waits for the
    target to receive pointer events) that fails with the backdrop
    blocking. Use force=True to dispatch the click programmatically
    (bypasses backdrop), OR fall back to JS-evaluation if force=True is
    insufficient. For modal close-state assertion, use state="hidden"
    rather than state="detached" — Bootstrap modals stay in the DOM
    with display:none after close, not removed.
    """
    print("\n=== case 10: Back-from-11 dismisses consent modal ===")
    await _drive_to_step_11(page)
    await page.click("#wizard-wizard_claude_generate")
    await page.wait_for_selector("text=Send your project to Anthropic?", timeout=5000)
    # Force-click bypasses the modal-backdrop intercept.
    await page.click("#wizard-wizard_back", force=True)
    # Use 'hidden' (display:none) rather than 'detached' (removed from DOM).
    await page.wait_for_selector("text=Send your project to Anthropic?",
                                  state="hidden", timeout=5000)
```

- [ ] **Step 4: Wire the new cases into `async def main()`**

Find the existing `async def main():` near line 343. Add calls for the new cases:

```python
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        # Existing cases:
        await case_full_run(page)
        # ... cases 2-6 ...
        # SP4 cases:
        await case_claude_button_not_rendered_without_env_key(page)
        await case_claude_consent_modal_shows_and_dismisses_via_cancel(page)
        await case_claude_consent_then_confirm_yields_auth_error(page)
        await case_back_from_step_11_dismisses_consent_modal(page)
        await context.close()
        await browser.close()
```

(Note: cases 7–10's pre-conditions differ — case 7 requires NO `ANTHROPIC_API_KEY`; cases 8–10 require it set. The simplest approach is to split the e2e run into TWO invocations:
1. Run case 7 with the app launched WITHOUT the env var.
2. Run cases 8–10 with the app launched WITH `ANTHROPIC_API_KEY=test-fake-key`.

The implementer can either: (a) run the existing 6 cases + case 7 in pass-1, then case 7 commented out and 8–10 enabled in pass-2; (b) split `main()` into two functions selected by a `--mode` CLI arg; (c) document that case 7 runs in a separate process from cases 8–10. Option (c) is the simplest — manually run the script twice with different env at app boot.)

- [ ] **Step 5: Document deferred cases**

Add a comment block at the bottom of `tests/test_wizard_e2e.py`:

```python
# === Deferred cases (require in-process Shiny test infrastructure) ===
#
# The following 3 SP4 e2e cases require ability to inject specific
# `ValidationOutcome` responses into a running Shiny app — which is not
# currently possible with the existing standalone-script + cross-process
# pattern. They are documented here as TODOs for a future SP that adds
# in-process test harness (per spec §11 open questions):
#
# 1. case_claude_consent_then_generate_renders_sp4_table
#    Confirm clicked → SP4 table renders with hardcoded suggestions.
#    Requires: stub `claude_backend.suggest_connections` in app process.
#
# 2. case_observer_failed_status_disables_retry_after
#    RateLimitError with retry_after=30 → button shows
#    "Rate limited — retry in 30 s" and is disabled.
#    Requires: inject RateLimitError from app process.
#
# 3. case_drop_counts_badge_renders_when_validation_drops
#    Specific raw_count > suggestions count → "Showing 3 of 5" badge.
#    Requires: inject ValidationOutcome with specific drop counts.
#
# Until in-process testing exists, these contracts are pinned by the
# unit tests in tests/test_claude_backend.py (orchestrator + observer
# behavior) plus manual smoke tests during release verification.
```

- [ ] **Step 6: Run the e2e script**

For case 7 (no env key):

```bash
# Terminal 1: launch app without ANTHROPIC_API_KEY
unset ANTHROPIC_API_KEY      # POSIX
$env:ANTHROPIC_API_KEY = $null  # PowerShell
micromamba run -n shiny shiny run --port 8000 app.py

# Terminal 2: run e2e (with case 7 enabled in main())
micromamba run -n shiny python tests/test_wizard_e2e.py
```

For cases 8–10 (with fake env key):

```bash
# Terminal 1: launch app with fake key
export ANTHROPIC_API_KEY=test-fake-key   # POSIX
$env:ANTHROPIC_API_KEY = "test-fake-key"  # PowerShell
micromamba run -n shiny shiny run --port 8000 app.py

# Terminal 2: run e2e (with cases 8-10 enabled in main())
micromamba run -n shiny python tests/test_wizard_e2e.py
```

Expected: existing 6 cases pass + 4 new cases pass.

- [ ] **Step 7: Commit**

```bash
git add tests/test_wizard_e2e.py
git commit -m "test(e2e): SP4 — 4 cross-process-testable cases (consent flow + auth fallback)

Adds case_claude_button_not_rendered_without_env_key,
case_claude_consent_modal_shows_and_dismisses_via_cancel,
case_claude_consent_then_confirm_yields_auth_error,
case_back_from_step_11_dismisses_consent_modal — all async, mirroring
the existing async-script pattern (asyncio.run(main())).

Three response-specific tests (sp4_table_render, retry_disable,
drop_counts_badge) are documented as TODOs requiring in-process Shiny
test infrastructure (deferred to a future SP per spec §11 open questions).
The orchestrator and observer behaviors those tests would pin are
covered by tests/test_claude_backend.py unit tests."
```

---

## Task 19: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the unit-test count**

Run `pytest --collect-only` to get the actual count BEFORE editing README:

```
micromamba run -n shiny pytest --collect-only -q tests/test_data_structure.py tests/test_claude_backend.py tests/test_wizard.py tests/test_connection_scorer.py 2>&1 | tail -1
```

(Exclude `tests/test_*_e2e.py` from the count — those are async scripts, not pytest-collected.)

In `README.md`, find the line citing "180 unit tests" (or whatever the current SP3-baseline count is). Update to reflect the actual count from the command above. Plan estimate: ~250–270 pytest items post-SP4 (180 SP3 baseline + ~75 new from SP4 with parametrize expansion). E2e cases go from 6 to 10 (case_full_run + 5 SP1 cases + 4 new SP4 cases).

- [ ] **Step 2: Add the "Optional Claude API backend" section**

In the AI-ISA wizard description area, add 2 paragraphs:

```markdown
### Optional Claude API backend (SP4)

In addition to the SP3 rule-based scorer that runs on every wizard
session, SESPy ships an optional Claude API backend for the
connection-suggestion step. When `ANTHROPIC_API_KEY` is set in the
environment, a [Generate with Claude API] button appears on step 11
of the wizard. Clicking it opens a one-time per-session consent
modal listing the data sent (regional sea, ecosystem type,
countries, main issues, all element labels and IDs); on confirm,
the backend calls Claude Sonnet 4.6 with structured tool-use output
and renders results in a second table below the rule-based
suggestions. SP3 results stay visible — the two backends are
side-by-side, and the user accepts from either or both at Finish.

**Getting an API key:** create an Anthropic account at
https://console.anthropic.com/, generate a key under Settings →
API Keys, and set it in your shell before launching SESPy:

```
# POSIX:
export ANTHROPIC_API_KEY=sk-ant-...

# Windows PowerShell:
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

**Cost:** ~$0.02–$0.05 per click (Sonnet 4.6 input pricing). A
typical wizard session is 10–30 clicks → $0.20–$1.50 per session.
SESPy does NOT enforce a per-session spending cap; set spending
alerts in the Anthropic console (Settings → Plans & Billing →
Usage Limits) for cost protection. Override the default model with
`SESPY_CLAUDE_MODEL=<model-id>`. For institutional deployments
where Claude must be globally disabled even when a key is present,
set `SESPY_DISABLE_CLAUDE=1`.

**Privacy:** Anthropic processes API requests per their privacy
policy at https://www.anthropic.com/legal/privacy (default 30-day
retention); zero-retention requires a separate agreement with
Anthropic. Each user provides their own key — SESPy does not store
keys. Users handling politically-sensitive jurisdictions (sanctioned
regions, named individuals in element labels, embargoed research)
should consult their institutional data-governance policy before
enabling the Claude backend.
```

- [ ] **Step 3: Verify the markdown renders cleanly**

```
micromamba run -n shiny python -m markdown README.md > /tmp/readme.html 2>&1 || true
```

Or visually inspect in the editor.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): SP4 — bump unit-test count + add Optional Claude API backend section

Matches the SP3 commit pattern (46304f7 docs(readme): bump unit test
count to 180 after SP3). New section under the AI-ISA wizard
description covers what the feature does, how to enable
(ANTHROPIC_API_KEY), how to disable globally (SESPY_DISABLE_CLAUDE),
cost (~\$0.02–\$0.05), model override (SESPY_CLAUDE_MODEL), and
privacy/retention disclosure with link to Anthropic's privacy policy."
```

---

## Task 20: Final verification + wheel-install check

**Files:**
- (No file modifications — verification only)

- [ ] **Step 1: Run the full test suite**

```
micromamba run -n shiny pytest -v
```

Expected: all tests pass.
- Pre-SP4 baseline: 180 unit + existing e2e cases.
- Post-SP4: ~225 unit (+45 from SP4) + 13 e2e cases (+7 from SP4).

If any test fails, debug it before proceeding.

- [ ] **Step 2: Build the wheel**

```
micromamba run -n shiny python -m build --wheel
```

Expected: `dist/sespy-0.x.0-py3-none-any.whl` appears.

- [ ] **Step 3: Verify `sespy/translations/core.json` ships in the wheel**

POSIX:
```
python -m zipfile -l dist/sespy-*.whl | grep core.json
```

PowerShell:
```
Get-ChildItem dist\sespy-*.whl | ForEach-Object { python -m zipfile -l $_.FullName } | Select-String core.json
```

Expected: `sespy/translations/core.json` listed in the output.

- [ ] **Step 4: Smoke-test the app launches with the new dependencies**

```
micromamba run -n shiny shiny run --port 8000 app.py
```

Open http://localhost:8000/ in a browser, navigate the wizard:
- Without `ANTHROPIC_API_KEY`: confirm the SP3-only flow still works (no Claude button).
- With `ANTHROPIC_API_KEY=test-fake-key` (and a network-disabled mock or with a test key): click button → consent modal → Confirm → toast "Claude API: invalid API key. Used rule-based scoring." → SP3 table remains.

- [ ] **Step 5: Commit any final adjustments**

If the smoke-test surfaces issues, address them and commit. Otherwise:

```bash
git status
# (should be clean)
```

- [ ] **Step 6: Push the branch**

```bash
git push -u origin feat/ai-isa-wizard-sp4
```

- [ ] **Step 7: Verify the commit history is clean**

```bash
git log --oneline main..feat/ai-isa-wizard-sp4
```

Expected: ~20 commits, each focused on one task. Ready for fast-forward merge to main.

- [ ] **Step 8: Open a pull request**

Use `gh pr create` or the GitHub web UI. PR title:

```
feat: SP4 — Optional Claude API backend for AI-ISA wizard
```

PR body should reference the spec at `docs/superpowers/specs/2026-05-09-ai-isa-wizard-sp4-design.md` and the plan at `docs/superpowers/plans/2026-05-09-ai-isa-wizard-sp4.md`.

---

## Self-review checklist (run before declaring done)

- [ ] **Spec coverage:** Every section of `docs/superpowers/specs/2026-05-09-ai-isa-wizard-sp4-design.md` has at least one task implementing it.
- [ ] **No placeholders:** Search the plan for "TBD", "TODO", "implement later", "fill in details", "Add appropriate error handling", "Similar to Task N" — none found.
- [ ] **Type consistency:** Method signatures used in later tasks match those defined in earlier tasks. Spot-check: `_validate_and_coerce` signature in Task 7 matches the call in Task 8's orchestrator. `ValidationOutcome` fields match across all consumers (Task 7 defines, Task 8 consumes, Tasks 13/15/16 consume).
- [ ] **Module-level vs server-scope split (round-10 finding):** Module-level types in Task 12 step 3; server-scope reactives in Task 13 step 2. Verified.
- [ ] **`@reactive.extended_task` lazy import:** Task 13 step 3 — `from ..claude_backend import suggest_connections as _claude_impl` lives inside `_claude_task`'s body, not at module top.
- [ ] **`_CONN_TYPES` 3-tuple shape preserved:** Task 1 step 3 uses 3-tuples; Task 2 step 2 imports from data_structure, preserving the existing `tests/test_connection_scorer.py:491` import via Python's module-attribute re-binding.
- [ ] **Drop precedence top-down (round-4 finding):** Task 7 step 3 — implementation is a single top-down loop with `continue` short-circuiting after each drop. Test `test_drop_precedence_unknown_source_beats_invalid_polarity` pins it.
- [ ] **`error_reason` always set before finally (round-5 finding):** Task 8 step 4 — both inner SDK except arms and the post-SDK try-block's `except ClaudeBackendError` AND `except Exception` arms set `error_reason`. Test `test_INFO_log_classification_on_shape_error` pins the round-5 bug fix.
- [ ] **Confidence guard order (round-4 finding):** Task 7 step 3 — `isinstance(c, bool)` BEFORE `isinstance(c, (int, float))`. `math.isfinite` AFTER the `float()` cast.
- [ ] **Module namespace prefix in e2e selectors (round-4 finding):** Task 18 step 2 — all selectors use `#wizard-...` form.
- [ ] **Modal-remove on Back-from-step-11 (round-4 finding):** Task 16 step 1.
- [ ] **Generic `Exception` catch-all in observer (round-4 finding):** Task 13 step 4 — final `except Exception` arm wraps as synthesized `ClaudeBackendError(reason="status")`.
- [ ] **Empty-state branch (round-4 finding):** Task 15 step 3 — `if not sp3 and not claude_available:` branch with `wizard.no_suggestions` message.
- [ ] **Frequent commits:** ~20 commits, one per task at minimum. Each commit message states what + why.

---

*End of plan.*
