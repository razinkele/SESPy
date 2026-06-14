# MosaicSES Scenario Studio — Hardening (Chunk 1) Design

**Status:** Draft — Chunk 1 of the Scenario Studio deferred follow-ups (Studio hardening → sidecar load/save → sign engine). Pending user review.

**Parent:** `2026-06-13-mosaicses-scenario-studio-design.md` (structural core, shipped to MosaicSES `main` `adff418`..`47e7ae2`).

## 1. Purpose

The structural-core Scenario Studio shipped, then a final whole-branch review flagged a cluster of MEDIUM/LOW issues that were deliberately deferred. This chunk closes all of them. It makes the Studio **honest** (it already computes dangling-target warnings but throws them away) and **hardened** (bad channel values are only caught deep in materialisation, surfacing as a generic per-card error rather than a precise authoring toast; the fragile UI parse has no unit coverage).

Nothing here changes the structural-analysis contract or the schema. It is additive and confined to the scenario library + the Studio module.

## 2. Scope

In scope (the four components below): library-boundary value validation; surfacing the discarded `ScenarioReport`; extracting + unit-testing the authoring parse; an honest `scenario_name` label.

Out of scope (later chunks): sidecar load/save UI; the *baseline-drift* half of the drift banner (loaded-scenario `baseline_name` vs current MultiSES); live `scenario_name` editing; the sign-propagation engine. These are tracked in the parent spec §8/§13/§15.

## 3. Component ① — Library-boundary value validation

**File:** `multises/scenario.py`.

Today `Intervention.__post_init__` validates that required target *keys* exist, never that channel *values* are valid slugs. The only value check is in the `add_channel` branch of the Studio's `_add` effect, so `retune_channel` and any future sidecar-loaded scenario bypass it; a bad value then reaches `Channel.__post_init__` deep in materialisation (M202/M203 for polarity/strength; `KeyError`/`ValueError` for channel_type) and surfaces as a generic per-card error.

Changes:
- Add a stable code: `ScenarioErrorCode.S004_INVALID_TARGET_VALUE = "S004_INVALID_TARGET_VALUE"`.
- Derive the valid sets from the canonical source in `data_structure` (no duplication, no circular import — `data_structure` does not import `scenario`):
  ```python
  from typing import Literal, get_args
  from .data_structure import CHANNEL_TYPES, Polarity, Strength
  _VALID_CHANNEL_TYPES = frozenset(CHANNEL_TYPES)
  _VALID_POLARITY = frozenset(get_args(Polarity))     # {"+", "-"}
  _VALID_STRENGTH = frozenset(get_args(Strength))      # {"weak","medium","strong"}
  ```
- In `Intervention.__post_init__`, after the existing key checks, for `kind in ("add_channel", "retune_channel")` validate each of `channel_type` / `polarity` / `strength` **when present** against its set, raising `ScenarioError(S004_INVALID_TARGET_VALUE, …)` naming the field and the allowed values. (`channel_type` is required for `add_channel`, so it is always present there; for `retune_channel` all three are optional.)

Effect: bad values are rejected at construction on **every** path (authoring, retune, future load) as a precise `ScenarioError`, before materialisation.

**Tests** (`tests/test_scenario.py`): `add_channel` with an unknown `channel_type` → `S004`; `retune_channel` with `polarity="x"` → `S004`; `retune_channel` with `strength="huge"` → `S004`; a valid `add_channel` and a valid `retune_channel` with all three values → constructs without error.

## 4. Component ② — Surface dangling-target warnings

**Files:** `multises/scenario_compare.py`, `multises_app/modules/scenario_view.py`.

`compare_scenario` calls `materialise_scenario`, which returns `(MultiSES, ScenarioReport)`, but it unpacks `materialised, _report = …` and discards the report. So W501 dangling/duplicate warnings never reach any caller, and a user who typos every target sees five all-zero "green" diff cards with no signal.

Changes:
- **`scenario_compare.py`:** `compare_scenario(baseline, scenario)` returns `tuple[dict[str, pd.DataFrame], ScenarioReport]` — the diffs dict (unchanged) plus the `report` it already has in hand. Import `ScenarioReport` for the type. (Only two callers: the C2 calc and the compare tests.)
- **`scenario_view.py`:** replace the `_diffs()` calc with a single memoized `_comparison()` `@reactive.calc` that returns a small dict `{"diffs": <dict|None>, "report": <ScenarioReport|None>, "error": <str|None>}` — one `compare_scenario` call per flush, shared by all consumers:
  - `None` interventions → `{"diffs": None, "report": None, "error": None}`.
  - success → `{"diffs": diffs, "report": report, "error": None}`.
  - exception → `{"diffs": None, "report": None, "error": friendly_error(...)}` (keep the broad-except soft-degrade + the `_log.exception` added in the final-review fix).
  - The 5 diff renderers read `_comparison()["error"]` / `["diffs"][metric_key]` (same fallbacks as today).
  - **`drift_banner`** reads `_comparison()["report"]`: when `report` is not None and `report.warnings` is non-empty, render a visible Bootstrap warning (`ui.div(..., class_="alert alert-warning")`) headed "⚠ N intervention(s) had no structural effect" with a `<ul>` of the warning messages; otherwise return the inert empty span. (The *baseline-drift* content of this banner remains deferred to Chunk 2; this chunk fills it with the warning surfacing only.)

**Tests** (`tests/test_scenario_compare.py`): update the three existing tests to unpack `(diffs, _report)`; add a test that an all-dangling scenario (e.g. `remove_node` on an absent id) returns a `report` whose `warnings` contains a `W501_DANGLING_TARGET` while the diffs are still well-formed (all-zero deltas).

## 5. Component ③ — Extract + unit-test the authoring parse

**File:** `multises_app/modules/scenario_view.py`.

The `_add` effect inlines the kind→target mapping, including the fragile `src>type>dst` split and the channel_type check — none of it unit-tested (the module tests are import/structure/callable only; the single e2e drives just the `add_node` happy path).

Changes:
- Extract a **pure** module-level function:
  ```python
  def build_intervention(iv_id: str, kind: str, tgt_raw: str, element_type: str,
                         compartment: str | None, rationale: str) -> Intervention
  ```
  It maps the raw inputs to a target dict per kind (add_node → `{"element": {...}}`; remove_node → `{"element_id": …}`; add_channel → split `tgt_raw` on `>` into source/channel_type/target; remove/retune_channel → `{"channel_id": …}`), rejects a blank node-op target with `ScenarioError(S002_MISSING_TARGET_FIELD)` (the guard added in the final-review fix), and **constructs and returns the `Intervention`** — so value validation (Component ①) runs inside it. No Shiny imports; fully testable.
- Remove the now-redundant inline `get_channel_types()` channel_type check and its import from the module (validation is centralised in ①).
- `_add` becomes thin: read inputs, compute the next `iv_id`, call `build_intervention(...)` inside the existing `try`, `add_intervention` + `dirty.set(True)`; the existing `except ScenarioError` surfaces any S002/S004 as a friendly toast.

**Tests** (new `tests/test_scenario_view_logic.py`, no Shiny harness): valid `add_channel` `"curonian_lagoon>organisms_marine_estuarine>klaipeda_strait"` → an `Intervention` with target `{"source": "curonian_lagoon", "channel_type": "organisms_marine_estuarine", "target": "klaipeda_strait"}`; unknown channel_type → `ScenarioError` `S004`; blank `add_node` target → `ScenarioError` `S002` (the blank node-op guard fires before construction); malformed `"a>b"` add_channel (parses to source `"a"`, channel_type `"b"`, empty target) → `ScenarioError` `S004` (channel_type `"b"` invalid); valid `add_node` and `remove_channel` → correct target shapes.

## 6. Component ④ — Honest `scenario_name` label

**File:** `multises_app/modules/scenario_view.py`.

`input.scenario_name()` is consumed only when the first intervention creates the `Scenario`; later edits are silently discarded. Because nothing in this chunk renders or saves the name, a live-edit fix would be invisible. Change the input label from `"Scenario name"` to `"New scenario name"` so the one-shot semantics are explicit. Full live editing lands with the save/load UI in Chunk 2.

No test (label-only).

## 7. Data flow (after)

Author input → `build_intervention()` (parse + validate via `Intervention.__post_init__`, ① ) → `add_intervention` → `state.active_scenario`. On flush, `_comparison()` runs `compare_scenario` once → `(diffs, report)`; the five cards render `diffs`, `drift_banner` renders `report.warnings`. A bad value never reaches materialisation (rejected at ①); a dangling-but-valid target materialises to a W501 warning that is now **visible** in the banner.

## 8. Error handling

- Hard validation (unknown kind, missing key, bad value): `ScenarioError` at `Intervention` construction → friendly toast in `_add`.
- Soft, post-materialisation (dangling/duplicate/collision target): `W501` warnings in the `ScenarioReport` → visible drift-banner alert (no longer discarded).
- Residual library error in the compare pipeline: broad-except soft-degrade to a per-card `_error` message **plus** `_log.exception` (unchanged from the final-review fix).

## 9. Testing summary

`test_scenario.py` (+4 S004 value cases) · `test_scenario_compare.py` (3 unpacks + 1 report-surfaced) · new `test_scenario_view_logic.py` (pure `build_intervention`, ~5 cases) · `test_scenario_e2e.py` (+1: author a dangling `remove_node` → assert the drift-banner alert text is visible). Full non-e2e suite must stay green (no regressions); the parent's existing scenario tests continue to pass.

## 10. Build order

① validation (library, no UI dep) → ② compare return + drift banner → ③ parse extraction (depends on ① for validation-in-construction) → ④ label. Each component is independently testable; ② and ③ both touch `scenario_view.py` but in disjoint regions.

## 11. Risks

- **API change to `compare_scenario`** — mitigated: only the C2 calc + `test_scenario_compare.py` call it; both updated in the same chunk; a missed caller fails loudly at import/test time.
- **`scenario.py` → `data_structure` import** — safe: `data_structure` is the base module and does not import `scenario` (verify at implementation; materialise already imports both).
- **Over-strict validation** — only validate values that are *present*; never require optional `polarity`/`strength` on `retune_channel`.
