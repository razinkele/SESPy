# MosaicSES Scenario Studio Hardening (Chunk 1) Implementation Plan

**Status:** **Implemented** ✓ — shipped to MosaicSES `main` (`eb2853c`..`f7a2237`, 2026-06-15) via subagent-driven TDD (4 tasks, spec + quality review each) + a final full-e2e gate. Full suite **455 passed** (439 non-e2e + all 16 e2e), `import app` OK. Plan-review caught a missed third `compare_scenario` caller before execution; the e2e gate caught + fixed the core `.comparative-card` regression.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the deferred MEDIUM/LOW final-review findings on the shipped Scenario Studio — validate channel values at the `Intervention` boundary, surface the discarded `ScenarioReport` warnings in a live drift banner, extract a pure unit-tested authoring parser, and make the `scenario_name` label honest.

**Architecture:** Four additive changes. (1) `Intervention.__post_init__` gains value validation (`S004`) against the canonical `data_structure` literals. (2) `compare_scenario` stops discarding the `ScenarioReport` and returns `(diffs, report)`. (3) The Studio's reactive layer becomes a single memoized `_comparison()` feeding both the five diff grids and a now-live `drift_banner`. (4) The `_add` parse logic moves into a pure, testable `build_intervention()`. No schema bump; no change to the structural-analysis contract.

**Tech Stack:** Python 3.13 · Shiny-for-Python 1.6.1 · pandas · networkx · pytest · Playwright. **Environment (mandatory):** everything through micromamba env `shiny` — `micromamba run -n shiny python -m pytest …`. Never a venv. MosaicSES test cwd is the MosaicSES repo root: `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES`.

**Spec:** `SESPy/docs/superpowers/specs/2026-06-14-mosaicses-scenario-studio-hardening-design.md`.

**Windows note:** never run multi-line `python -c "…"` (the shell splits it per line → stray files + `Unable to initialize device PRN`). Use single-line `-c` or a `.py` file. Create/edit files with the editor, never shell `>` redirection.

---

## File Structure

**Modified (MosaicSES):**
- `multises/scenario.py` — add `S004_INVALID_TARGET_VALUE`, the valid-value constants, and channel-value validation in `Intervention.__post_init__`.
- `multises/scenario_compare.py` — `compare_scenario` returns `(diffs, report)`.
- `multises_app/modules/scenario_view.py` — `_comparison()` memo + live `drift_banner`; pure `build_intervention()` + thin `_add`; honest `scenario_name` label.

**Tests (MosaicSES):**
- `tests/test_scenario.py` — `S004` value-validation cases.
- `tests/test_scenario_compare.py` — unpack `(diffs, report)`; assert report surfaces W501.
- `tests/test_depolderisation.py` — unpack the tuple at the third `compare_scenario` call site (Task 2).
- `tests/test_scenario_view_logic.py` — **new**, pure `build_intervention` cases.
- `tests/test_scenario_e2e.py` — add a dangling-target → drift-banner e2e.

Build order: Task 1 (validation) → Task 2 (compare signature) → Task 3 (drift banner) → Task 4 (parser + label). Task 3 depends on Task 2's signature; Task 4 depends on Task 1's validation.

---

## Task 0: Branch + baseline

**Files:** none (git only).

- [ ] **Step 1: Branch the MosaicSES repo off the shipped tip**

```bash
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
git checkout main
git checkout -b scenario-studio-hardening-2026-06-14
```

- [ ] **Step 2: Confirm baseline green**

Run: `micromamba run -n shiny python -m pytest tests/ -q -k "not e2e" -p no:cacheprovider`
Expected: `429 passed, 15 deselected` (the shipped structural core).

---

## Task 1: Channel-value validation at the Intervention boundary

**Why:** `Intervention.__post_init__` validates target *keys* but never channel *values*. The only value check lives in the `add_channel` UI branch, so `retune_channel` and any future sidecar-loaded scenario bypass it and a bad value detonates deep in `Channel.__post_init__` during materialisation (spec §3, final-review MEDIUM).

**Files:**
- Modify: `multises/scenario.py`
- Test: `tests/test_scenario.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scenario.py`:

```python
def test_add_channel_unknown_channel_type_raises_s004():
    from multises.scenario import Intervention, ScenarioError, ScenarioErrorCode
    with pytest.raises(ScenarioError) as ei:
        Intervention(id="i1", kind="add_channel",
                     target={"source": "a", "target": "b", "channel_type": "BOGUS"})
    assert ei.value.code == ScenarioErrorCode.S004_INVALID_TARGET_VALUE


def test_retune_channel_invalid_polarity_raises_s004():
    from multises.scenario import Intervention, ScenarioError, ScenarioErrorCode
    with pytest.raises(ScenarioError) as ei:
        Intervention(id="i1", kind="retune_channel",
                     target={"channel_id": "ch1", "polarity": "x"})
    assert ei.value.code == ScenarioErrorCode.S004_INVALID_TARGET_VALUE


def test_retune_channel_invalid_strength_raises_s004():
    from multises.scenario import Intervention, ScenarioError, ScenarioErrorCode
    with pytest.raises(ScenarioError) as ei:
        Intervention(id="i1", kind="retune_channel",
                     target={"channel_id": "ch1", "strength": "huge"})
    assert ei.value.code == ScenarioErrorCode.S004_INVALID_TARGET_VALUE


def test_valid_channel_values_construct_ok():
    from multises.scenario import Intervention
    add = Intervention(id="i1", kind="add_channel",
                       target={"source": "a", "target": "b",
                               "channel_type": "organisms_marine_estuarine",
                               "polarity": "+", "strength": "strong"})
    retune = Intervention(id="i2", kind="retune_channel",
                          target={"channel_id": "ch1", "strength": "weak", "polarity": "-"})
    assert add.target["channel_type"] == "organisms_marine_estuarine"
    assert retune.target["strength"] == "weak"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -q`
Expected: the 3 raising tests FAIL (no `S004_INVALID_TARGET_VALUE` attribute / no error raised).

- [ ] **Step 3: Implement the validation**

In `multises/scenario.py`, change the typing import (line 12) from:

```python
from typing import Literal
```

to:

```python
from typing import Literal, get_args
```

Add, immediately after that import line, the data_structure value sources (no circular import — `data_structure` is the base module):

```python
from .data_structure import CHANNEL_TYPES, Polarity, Strength
```

Add the new code in `ScenarioErrorCode` (after the `S003_…` line):

```python
    S004_INVALID_TARGET_VALUE = "S004_INVALID_TARGET_VALUE"
```

Add the valid-value constants after the `_NEEDS_COMPARTMENT = …` line:

```python
# Canonical valid channel values (single source of truth in data_structure).
_VALID_CHANNEL_TYPES = frozenset(CHANNEL_TYPES)
_VALID_POLARITY = frozenset(get_args(Polarity))
_VALID_STRENGTH = frozenset(get_args(Strength))
_CHANNEL_VALUE_KINDS = frozenset({"add_channel", "retune_channel"})
```

In `Intervention.__post_init__`, append (after the `_NEEDS_COMPARTMENT` compartment_id check) the value-validation block:

```python
        if self.kind in _CHANNEL_VALUE_KINDS:
            for fname, valid in (("channel_type", _VALID_CHANNEL_TYPES),
                                 ("polarity", _VALID_POLARITY),
                                 ("strength", _VALID_STRENGTH)):
                val = self.target.get(fname)
                if val is not None and val not in valid:
                    raise ScenarioError(
                        ScenarioErrorCode.S004_INVALID_TARGET_VALUE,
                        f"intervention {self.id!r}: invalid {fname} {val!r}; "
                        f"expected one of {sorted(valid)}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -q`
Expected: all PASS (the original tests + the 4 new ones).

- [ ] **Step 5: Commit**

```bash
git add multises/scenario.py tests/test_scenario.py
git commit -m "feat(mosaicses): S004 channel-value validation at the Intervention boundary"
```

End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: compare_scenario returns (diffs, report)

**Why:** `compare_scenario` already receives the `ScenarioReport` from `materialise_scenario` but unpacks it as `_report` and throws it away, so dangling-target warnings never reach the UI (spec §4, final-review MEDIUM).

**Files:**
- Modify: `multises/scenario_compare.py`
- Test: `tests/test_scenario_compare.py`
- Test: `tests/test_depolderisation.py` — a **third** caller of `compare_scenario`; its line 30 must unpack the tuple or it `TypeError`s at line 31 (caught by plan-review).

- [ ] **Step 1: Update the tests to expect the new signature**

Replace the body of `tests/test_scenario_compare.py` from `def test_compare_returns_a_frame_per_metric():` onward so all three existing tests unpack the tuple, and add a fourth. The full replacement (everything after the imports + `CID` + `_add_node_scenario` helper, i.e. lines 17 to end):

```python
def test_compare_returns_a_frame_per_metric():
    diffs, report = compare_scenario(seed_curonian(), _add_node_scenario())
    assert set(diffs) == set(METRIC_KEYS)
    for k, df in diffs.items():
        assert isinstance(df, pd.DataFrame), k
    assert report.warnings == ()


def test_compartment_summary_delta_reflects_added_node():
    diffs, _ = compare_scenario(seed_curonian(), _add_node_scenario())
    row = diffs["compartment_summary"].set_index("compartment_id").loc[CID]
    assert row["element_count_delta"] == 1


def test_inter_compartment_metrics_normalised_to_frame():
    # the source is a dict-of-dicts; the diff must still be a frame keyed by compartment
    diffs, _ = compare_scenario(seed_curonian(), _add_node_scenario())
    icm = diffs["inter_compartment_metrics"]
    assert "compartment_id" in icm.columns
    assert "betweenness_delta" in icm.columns


def test_compare_surfaces_dangling_warning_in_report():
    sc = Scenario(id="s", name="bad", interventions=(
        Intervention(id="i1", kind="remove_node", compartment_id=CID,
                     target={"element_id": "DOES_NOT_EXIST"}),))
    diffs, report = compare_scenario(seed_curonian(), sc)
    assert any(code == "W501_DANGLING_TARGET" for code, _ in report.warnings)
    assert set(diffs) == set(METRIC_KEYS)   # diffs still well-formed
```

Then update the **third** caller, `tests/test_depolderisation.py` line 30, to unpack the tuple. Change:

```python
    diffs = compare_scenario(ms, build_depolderisation_scenario(ms))
```

to:

```python
    diffs, _ = compare_scenario(ms, build_depolderisation_scenario(ms))
```

(Line 31 dict-indexes `diffs["inter_compartment_metrics"]`; without this change it indexes a tuple → `TypeError`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_compare.py tests/test_depolderisation.py -q`
Expected: FAIL — `compare_scenario` still returns a dict, so the new tuple-unpacking raises (e.g. `ValueError: too many values to unpack` in `test_depolderisation.py`, and the compare assertions error).

- [ ] **Step 3: Change the return type**

In `multises/scenario_compare.py`, change the scenario import (line 15) from:

```python
from .scenario import Scenario
```

to:

```python
from .scenario import Scenario, ScenarioReport
```

Change the `compare_scenario` signature and body. Replace:

```python
def compare_scenario(baseline: MultiSES, scenario: Scenario) -> dict[str, pd.DataFrame]:
    materialised, _report = materialise_scenario(baseline, scenario)
```

with:

```python
def compare_scenario(baseline: MultiSES, scenario: Scenario) -> tuple[dict[str, pd.DataFrame], ScenarioReport]:
    materialised, report = materialise_scenario(baseline, scenario)
```

and replace the final `return out` with:

```python
    return out, report
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_compare.py tests/test_depolderisation.py -q`
Expected: all PASS (4 compare + 3 depolderisation).

- [ ] **Step 5: Commit**

```bash
git add multises/scenario_compare.py tests/test_scenario_compare.py tests/test_depolderisation.py
git commit -m "refactor(mosaicses): compare_scenario returns (diffs, report)"
```

End with the `Co-Authored-By:` trailer.

---

## Task 3: Surface dangling-target warnings in a live drift banner

**Why:** the now-available `report.warnings` must become visible; today `drift_banner` is an inert empty span and a user who typos every target sees five misleading all-zero "green" cards (spec §4).

**Files:**
- Modify: `multises_app/modules/scenario_view.py`
- Test: `tests/test_scenario_e2e.py`

- [ ] **Step 1: Write the failing e2e**

Append to `tests/test_scenario_e2e.py`:

```python
def test_dangling_target_shows_drift_banner(mosaicses_app_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.wait_for_selector("#sespy_nav_scenario", timeout=10_000)
            page.click("#sespy_nav_scenario")
            page.select_option("#scenario-iv_kind", "remove_node")
            page.fill("#scenario-iv_compartment", "curonian_lagoon")
            page.fill("#scenario-iv_target", "DOES_NOT_EXIST")
            page.click("#scenario-add_intervention")
            page.wait_for_timeout(1500)   # materialise + diff
            banner = page.locator("#scenario-drift_banner")
            expect(banner).to_contain_text("had no structural effect", timeout=10_000)
        finally:
            browser.close()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_e2e.py::test_dangling_target_shows_drift_banner -q`
Expected: FAIL — the inert `drift_banner` renders nothing, so the text is absent.

- [ ] **Step 3: Replace the reactive layer with `_comparison()` + a live banner**

In `multises_app/modules/scenario_view.py`, replace the `drift_banner`, `_diffs`, and `_diff_renderer` definitions. Replace this block:

```python
    @output
    @render.ui
    def drift_banner():
        return ui.tags.span("")   # inert placeholder — populated once the sidecar load/save UI lands (follow-on; review R1)

    @reactive.calc
    def _diffs():
        # Compute once per flush (memoised) and share across all five diff
        # renderers — each renderer calling compare_scenario independently would
        # re-materialise + re-run all five analyses 5x per flush (review F2/LOW).
        sc = state.active_scenario.get()
        if not sc or not sc.interventions:
            return None
        # Guard the materialise/analyse pipeline (mirrors comparative.py's
        # convention of wrapping its risky analysis): a residual library error
        # here is surfaced as a friendly per-card message via the `_error`
        # sentinel rather than crashing all five renderers with raw Shiny errors.
        try:
            return compare_scenario(state.active_multises.get(), sc)
        except Exception as e:  # noqa: BLE001 — broad on purpose: never crash the panel
            # Soft-degrade for the user, but never lose the traceback for a developer:
            # friendly_error truncates to one line, so log the full stack here.
            _log.exception("compare_scenario failed for the active scenario")
            return {"_error": friendly_error("Could not compute scenario diff", e)}

    def _diff_renderer(metric_key: str):
        @render.data_frame
        def _():
            import pandas as pd
            diffs = _diffs()
            if diffs is None:
                return render.DataGrid(pd.DataFrame({"info": ["Add an intervention to see the diff."]}))
            if "_error" in diffs:
                return render.DataGrid(pd.DataFrame({"error": [diffs["_error"]]}))
            return render.DataGrid(diffs[metric_key], height="260px")
        return _
```

with:

```python
    @reactive.calc
    def _comparison() -> dict:
        # Compute once per flush (memoised) and share across the five diff renderers
        # AND the drift banner — each consumer calling compare_scenario independently
        # would re-materialise + re-run all five analyses per flush.
        sc = state.active_scenario.get()
        if not sc or not sc.interventions:
            return {"diffs": None, "report": None, "error": None}
        # Guard the materialise/analyse pipeline: a residual library error is surfaced
        # as a friendly per-card message rather than crashing all five renderers.
        try:
            diffs, report = compare_scenario(state.active_multises.get(), sc)
            return {"diffs": diffs, "report": report, "error": None}
        except Exception as e:  # noqa: BLE001 — broad on purpose: never crash the panel
            # Soft-degrade for the user, but never lose the traceback for a developer.
            _log.exception("compare_scenario failed for the active scenario")
            return {"diffs": None, "report": None,
                    "error": friendly_error("Could not compute scenario diff", e)}

    @output
    @render.ui
    def drift_banner():
        report = _comparison()["report"]
        if not report or not report.warnings:
            return ui.tags.span("")   # inert unless there is something to surface
        return ui.div(
            ui.tags.strong(f"⚠ {len(report.warnings)} intervention(s) had no structural effect"),
            ui.tags.ul(*[ui.tags.li(msg) for _code, msg in report.warnings]),
            class_="alert alert-warning", role="alert")

    def _diff_renderer(metric_key: str):
        @render.data_frame
        def _():
            import pandas as pd
            comp = _comparison()
            if comp["error"] is not None:
                return render.DataGrid(pd.DataFrame({"error": [comp["error"]]}))
            diffs = comp["diffs"]
            if diffs is None:
                return render.DataGrid(pd.DataFrame({"info": ["Add an intervention to see the diff."]}))
            return render.DataGrid(diffs[metric_key], height="260px")
        return _
```

- [ ] **Step 4: Run the e2e + the module tests**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_e2e.py tests/test_scenario_view_module.py -q`
Expected: all PASS (both e2e tests + the 3 module tests).

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/scenario_view.py tests/test_scenario_e2e.py
git commit -m "feat(mosaicses): surface dangling-target warnings in the drift banner"
```

End with the `Co-Authored-By:` trailer.

---

## Task 4: Extract a pure build_intervention + honest scenario-name label

**Why:** the `_add` effect inlines the fragile `source>type>target` parse with no unit coverage, and duplicates the channel_type check now centralised in Task 1; the `scenario_name` input silently ignores edits after the first intervention (spec §5, §6).

**Files:**
- Modify: `multises_app/modules/scenario_view.py`
- Test: `tests/test_scenario_view_logic.py` (new)

- [ ] **Step 1: Write the failing unit tests**

Create `tests/test_scenario_view_logic.py`:

```python
from __future__ import annotations
import pytest
from multises.scenario import ScenarioError, ScenarioErrorCode
from multises_app.modules.scenario_view import build_intervention


def test_build_add_channel_parses_source_type_target():
    iv = build_intervention("iv1", "add_channel",
                            "curonian_lagoon>organisms_marine_estuarine>klaipeda_strait",
                            "", None, "")
    assert iv.kind == "add_channel"
    assert iv.target == {"source": "curonian_lagoon",
                         "channel_type": "organisms_marine_estuarine",
                         "target": "klaipeda_strait"}


def test_build_add_channel_unknown_type_raises_s004():
    with pytest.raises(ScenarioError) as ei:
        build_intervention("iv1", "add_channel", "a>BOGUS>b", "", None, "")
    assert ei.value.code == ScenarioErrorCode.S004_INVALID_TARGET_VALUE


def test_build_blank_node_target_raises_s002():
    with pytest.raises(ScenarioError) as ei:
        build_intervention("iv1", "add_node", "   ", "Pressures", "curonian_lagoon", "")
    assert ei.value.code == ScenarioErrorCode.S002_MISSING_TARGET_FIELD


def test_build_malformed_add_channel_raises_s004():
    # "a>b" -> source "a", channel_type "b", target "" -> channel_type "b" invalid
    with pytest.raises(ScenarioError) as ei:
        build_intervention("iv1", "add_channel", "a>b", "", None, "")
    assert ei.value.code == ScenarioErrorCode.S004_INVALID_TARGET_VALUE


def test_build_add_node_and_remove_channel_shapes():
    add = build_intervention("iv1", "add_node", "E9", "Pressures", "c1", "r")
    assert add.target == {"element": {"id": "E9", "label": "E9", "type": "Pressures"}}
    assert add.compartment_id == "c1"
    rm = build_intervention("iv2", "remove_channel", "ch1", "", None, "")
    assert rm.target == {"channel_id": "ch1"}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_intervention'`.

- [ ] **Step 3: Add the pure helper, thin `_add`, drop the redundant import, relabel**

In `multises_app/modules/scenario_view.py`:

(a) Remove the now-unused channels import line:

```python
from multises.channels import get_channel_types
```

(b) Add the pure helper immediately after the `_KIND_CHOICES = { … }` block (before `@module.ui`):

```python
def build_intervention(iv_id: str, kind: str, tgt_raw: str, element_type: str,
                       compartment: str | None, rationale: str) -> Intervention:
    """Pure: map raw Studio inputs to a validated Intervention. Parses the
    add_channel 'source>type>target' free-text form; value validation (channel_type/
    polarity/strength) and the blank-node guard run in Intervention.__post_init__ and
    here. Raises ScenarioError on any invalid input (the caller shows a friendly toast)."""
    tgt_raw = (tgt_raw or "").strip()
    if kind in ("add_node", "remove_node") and not tgt_raw:
        raise ScenarioError(ScenarioErrorCode.S002_MISSING_TARGET_FIELD,
                            "an element id is required for node operations")
    if kind == "add_node":
        target, comp = {"element": {"id": tgt_raw, "label": tgt_raw,
                                    "type": element_type}}, (compartment or None)
    elif kind == "remove_node":
        target, comp = {"element_id": tgt_raw}, (compartment or None)
    elif kind == "add_channel":
        src, ctype, dst = (tgt_raw.split(">") + ["", "", ""])[:3]
        target, comp = {"source": src, "channel_type": ctype, "target": dst}, None
    else:  # remove_channel / retune_channel
        target, comp = {"channel_id": tgt_raw}, None
    return Intervention(id=iv_id, kind=kind, compartment_id=comp,
                        target=target, rationale=rationale)
```

(c) Replace the entire `_add` effect:

```python
    @reactive.effect
    @reactive.event(input.add_intervention)
    def _add():
        try:
            kind = input.iv_kind()
            tgt_raw = (input.iv_target() or "").strip()
            # Reject a blank node-op target at authoring time (mirrors the add_channel
            # empty-channel_type guard) so it surfaces as a friendly toast instead of
            # silently materialising an empty-id node (final-review LOW).
            if kind in ("add_node", "remove_node") and not tgt_raw:
                raise ScenarioError(ScenarioErrorCode.S002_MISSING_TARGET_FIELD,
                                    "an element id is required for node operations")
            if kind == "add_node":
                target = {"element": {"id": tgt_raw, "label": tgt_raw,
                                      "type": input.iv_element_type()}}
                comp = input.iv_compartment() or None
            elif kind == "remove_node":
                target, comp = {"element_id": tgt_raw}, (input.iv_compartment() or None)
            elif kind == "add_channel":
                src, ctype, dst = (tgt_raw.split(">") + ["", "", ""])[:3]
                # Validate the free-text channel_type slug at authoring time so an
                # invalid type is caught HERE (surfaced as a friendly toast via the
                # `except ScenarioError` path below) rather than detonating later as
                # an uncaught KeyError in make_channel() -> get_channel_type(), which
                # would replace all five diff cards with raw Shiny render errors.
                valid = get_channel_types()
                if ctype not in valid:
                    raise ScenarioError(
                        ScenarioErrorCode.S002_MISSING_TARGET_FIELD,
                        f"unknown channel_type {ctype!r}; expected one of {sorted(valid)}",
                    )
                target, comp = {"source": src, "channel_type": ctype, "target": dst}, None
            else:  # remove_channel / retune_channel
                target, comp = {"channel_id": tgt_raw}, None
            n = len(state.active_scenario.get().interventions) if state.active_scenario.get() else 0
            iv = Intervention(id=f"iv{n+1}", kind=kind, compartment_id=comp,
                              target=target, rationale=input.iv_rationale() or "")
            sc = state.active_scenario.get() or Scenario(id="s1", name=input.scenario_name())
            state.active_scenario.set(add_intervention(sc, iv))
            state.dirty.set(True)
        except ScenarioError as e:
            ui.notification_show(friendly_error("Invalid intervention", e),
                                 type="error", duration=6)
```

with the thin version:

```python
    @reactive.effect
    @reactive.event(input.add_intervention)
    def _add():
        try:
            sc = state.active_scenario.get()
            n = len(sc.interventions) if sc else 0
            iv = build_intervention(
                iv_id=f"iv{n+1}", kind=input.iv_kind(),
                tgt_raw=input.iv_target() or "", element_type=input.iv_element_type(),
                compartment=input.iv_compartment() or None,
                rationale=input.iv_rationale() or "")
            base = sc or Scenario(id="s1", name=input.scenario_name())
            state.active_scenario.set(add_intervention(base, iv))
            state.dirty.set(True)
        except ScenarioError as e:
            ui.notification_show(friendly_error("Invalid intervention", e),
                                 type="error", duration=6)
```

(d) Relabel the name input — replace:

```python
            ui.input_text("scenario_name", "Scenario name", value="New scenario"),
```

with:

```python
            ui.input_text("scenario_name", "New scenario name", value="New scenario"),
```

- [ ] **Step 4: Run the unit tests + the module/e2e tests**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py tests/test_scenario_view_module.py tests/test_scenario_e2e.py -q`
Expected: all PASS (5 logic + 3 module + 2 e2e).

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/scenario_view.py tests/test_scenario_view_logic.py
git commit -m "refactor(mosaicses): extract pure build_intervention + honest scenario-name label"
```

End with the `Co-Authored-By:` trailer.

---

## Final verification

- [ ] **Full non-e2e suite** — Run: `micromamba run -n shiny python -m pytest tests/ -q -k "not e2e" -p no:cacheprovider`
  Expected: **439 passed, 16 deselected** = 429 baseline + 4 new S004 cases (Task 1) + 1 new compare-report case (Task 2; the other 3 compare tests + the `test_depolderisation.py` line are modified, not added) + 5 new `build_intervention` cases (Task 4); deselected rises 15 → 16 because Task 3 adds a second e2e. Zero failures.
- [ ] **E2e** — Run: `micromamba run -n shiny python -m pytest tests/test_scenario_e2e.py -q`
  Expected: 2 passed.
- [ ] **Import smoke** — Run: `micromamba run -n shiny python -c "import app; print('IMPORT OK')"`
  Expected: `IMPORT OK`.
- [ ] **Tree clean** — Run: `git status --porcelain` → empty (no stray files).

---

## Self-review notes (author)

- **Spec coverage:** §3 value validation → Task 1; §4 compare return + drift banner → Tasks 2–3; §5 parse extraction → Task 4; §6 honest label → Task 4 (d). §7 data flow, §8 error handling realised across Tasks 1/3. Out-of-scope items (sidecar load/save, baseline-drift, live name edit, sign engine) correctly excluded.
- **Type consistency:** `compare_scenario` returns `(dict, ScenarioReport)` in Task 2 and is consumed as such by `_comparison()` in Task 3 and the tests; `build_intervention(iv_id, kind, tgt_raw, element_type, compartment, rationale)` in Task 4 matches its call site and tests; `S004_INVALID_TARGET_VALUE` defined in Task 1, asserted in Tasks 1 & 4. `_comparison()` returns the three-key dict (`diffs`/`report`/`error`) consumed by both `drift_banner` and `_diff_renderer`.
- **Verified seams:** no circular import (`data_structure` imports no higher-level multises module); `CHANNEL_TYPES` (8), `get_args(Polarity)` `('+','-')`, `get_args(Strength)` `('weak','medium','strong')` all importable; `organisms_marine_estuarine` is a real channel_type; `remove_node` of an absent id produces a `W501` (asserted by the shipped `test_materialise.py`).
- **Count gate:** 429 baseline + 10 new non-e2e tests = **439 passed, 16 deselected**, zero failures; the e2e file goes from 1 → 2.
- **Verified by plan-review** (workflow `wf_0c22180d-b2e`; integration dry-run + fresh-eyes + triage on the real seed): caught one HIGH defect — Task 2 changed `compare_scenario`'s signature but the original plan missed `tests/test_depolderisation.py`, the **third** of exactly three callers (`grep`-confirmed), whose line 31 dict-indexes the result → `TypeError`; without the fix the suite ends 438 passed / 1 failed. **Fixed above** (Task 2 now updates that line + commits it). All else verified sound: the S004 validator rejects 0 of 7 existing channel-value constructions and the correct field on the bad cases; `get_channel_types` has exactly two references, both removed by Task 4; every Task 3/4 edit anchor matches `main` verbatim; baseline is 429 (not stale); no circular import.
