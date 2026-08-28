# MosaicSES Scenario Studio — Sidecar Load/Save (Chunk 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Scenario Studio persist its work — save the active scenario to a `.scenarios.json` sidecar, load one back, switch between loaded scenarios, rename live, and warn when a loaded scenario was authored against a different baseline.

**Architecture:** Two new pure library functions in `multises/scenario.py` (`scenario_set_to_json`, `stamp_scenario`) and one pure predicate in the view module (`_baseline_drift`); everything else is reactive wiring in `multises_app/modules/scenario_view.py`, mirroring the download/upload idioms already proven in `project_setup.py`. Pushing logic out of the reactive layer is deliberate — it is what makes this testable without a Shiny harness. Nothing here touches the materialise/compare pipeline.

**Tech Stack:** Python 3.12+, Shiny for Python (`@module`, `reactive.effect`, `render.download`, `input_file`), frozen dataclasses, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-06-15-mosaicses-scenario-studio-sidecar-design.md` (SESPy repo, reviewed 2026-08-27 — **read §14 before starting**; it records two decisions this plan implements).

**Repo note:** the spec and this plan live in **SESPy** `docs/superpowers/`, with the earlier Scenario Studio corpus. The code lives in **MosaicSES**. All paths below are relative to the MosaicSES repo root.

## Global Constraints

- **No new dependencies.** Everything needed is already imported somewhere in the repo.
- **Pure helpers take a timestamp argument; only render/effect functions read the clock.** Use `datetime.now(timezone.utc).isoformat(timespec="seconds")`, matching `project_setup.py:52`.
- **E2e selectors must use Shiny-namespaced ids** (`#scenario-download_scenarios`). Never `[id$=...]`, `[id^=...]`, or a class shared across panels — every nav panel is in one DOM, and pattern selectors have caused two regressions in this repo.
- **E2e nav waits must go through `tests/_e2e_nav.py::wait_for_nav(page, panel)`.** Never a bare `wait_for_selector("#sespy_nav_...")`.
- **The scenario module namespace is `scenario`** — an input `"foo"` becomes `#scenario-foo`.
- **Uploads are an untrusted-file boundary:** broad `except`, `_log.exception`, `friendly_error` toast, state left untouched.
- **Do not extend the meaning of `state.dirty`** (spec §14 Decision F). Set it where this plan says and nowhere else.
- **Full suite before merge:** `micromamba run -n shiny python -m pytest tests/ -q` — never `-k "not e2e"`.

---

### Task 1: `scenario_set_to_json` library helper

**Files:**
- Modify: `multises/scenario.py` (add function; simplify `save_scenario_set` at :162)
- Modify: `multises/__init__.py` (re-export at :49 and :102)
- Test: `tests/test_scenario.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `scenario_set_to_json(scenario_set: ScenarioSet) -> str` — sidecar JSON text, `indent=2`, `ensure_ascii=False`. Used by Task 7.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scenario.py`:

```python
def test_scenario_set_to_json_round_trips(tmp_path):
    from multises.scenario import (Intervention, Scenario, ScenarioSet,
                                   ScenarioSetMetadata, scenario_set_to_json,
                                   load_scenario_set)
    # remove_node is in _NEEDS_COMPARTMENT (scenario.py:49), so omitting
    # compartment_id raises S002 at construction - not a serialiser bug.
    iv = Intervention(id="i1", kind="remove_node", compartment_id="c1",
                      target={"element_id": "E1"})
    sc = Scenario(id="s1", name="Depolder", baseline_name="Curonian",
                  interventions=(iv,))
    ss = ScenarioSet(metadata=ScenarioSetMetadata(name="Depolder"), scenarios=[sc])

    text = scenario_set_to_json(ss)
    path = tmp_path / "x.scenarios.json"
    path.write_text(text, encoding="utf-8")
    back = load_scenario_set(path)

    assert back.metadata.name == "Depolder"
    assert len(back.scenarios) == 1
    assert back.scenarios[0].name == "Depolder"
    assert back.scenarios[0].baseline_name == "Curonian"
    assert back.scenarios[0].interventions[0].target == {"element_id": "E1"}
    assert back.scenarios[0].interventions[0].compartment_id == "c1"


def test_scenario_set_to_json_is_indented_utf8():
    from multises.scenario import (Scenario, ScenarioSet, ScenarioSetMetadata,
                                   scenario_set_to_json)
    ss = ScenarioSet(metadata=ScenarioSetMetadata(name="Zuvys"),
                     scenarios=[Scenario(id="s1", name="Zuvys")])
    text = scenario_set_to_json(ss)
    assert "\n  " in text
    text.encode("utf-8")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -q -k scenario_set_to_json`
Expected: FAIL with `ImportError: cannot import name 'scenario_set_to_json'`

- [ ] **Step 3: Add the function and simplify `save_scenario_set`**

In `multises/scenario.py`, replace the existing `save_scenario_set` with these two functions:

```python
def scenario_set_to_json(scenario_set: "ScenarioSet") -> str:
    """Serialise a ScenarioSet to sidecar JSON text, with no file I/O.

    Split out of save_scenario_set so the browser download path can yield
    bytes without a temp file; save_scenario_set keeps its path API for
    headless callers.
    """
    return json.dumps(asdict(scenario_set), indent=2, ensure_ascii=False)


def save_scenario_set(scenario_set: "ScenarioSet", path: Path | str) -> None:
    """Persist a ScenarioSet to a sidecar JSON via the generic atomic writer."""
    from .persistence import _atomic_write_bytes
    _atomic_write_bytes(path, scenario_set_to_json(scenario_set).encode("utf-8"))
```

- [ ] **Step 4: Re-export from the package**

In `multises/__init__.py`, add `scenario_set_to_json` to the `from .scenario import (...)` list (~line 49, beside `save_scenario_set`) and add `"scenario_set_to_json",` to `__all__` (~line 102).

- [ ] **Step 5: Run the whole file to verify nothing regressed**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -q`
Expected: PASS — all tests, not only the new ones, since `save_scenario_set` was refactored.

- [ ] **Step 6: Commit**

```bash
git add multises/scenario.py multises/__init__.py tests/test_scenario.py
git commit -m "feat(scenario): scenario_set_to_json for the browser download path"
```

---

### Task 2: `stamp_scenario` timestamp helper

Implements spec §14 Decision A. `Scenario.created_at` / `modified_at` are declared (`scenario.py:111-112`) and round-tripped by `load_scenario_set`, but **nothing writes them today** — they are always `""`. This chunk ships them inside every downloaded file, so they must be populated.

**Files:**
- Modify: `multises/scenario.py`
- Modify: `multises/__init__.py`
- Test: `tests/test_scenario.py`

**Interfaces:**
- Consumes: nothing
- Produces: `stamp_scenario(scenario: Scenario, now: str) -> Scenario` — copy with `modified_at=now`, and `created_at=now` **only if** `created_at` was empty. Used by Tasks 4 and 5.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scenario.py`:

```python
def test_stamp_scenario_sets_both_on_first_stamp():
    from multises.scenario import Scenario, stamp_scenario
    out = stamp_scenario(Scenario(id="s1", name="X"), "2026-08-27T10:00:00+00:00")
    assert out.created_at == "2026-08-27T10:00:00+00:00"
    assert out.modified_at == "2026-08-27T10:00:00+00:00"


def test_stamp_scenario_preserves_created_at():
    from multises.scenario import Scenario, stamp_scenario
    sc = Scenario(id="s1", name="X", created_at="2026-01-01T00:00:00+00:00")
    out = stamp_scenario(sc, "2026-08-27T10:00:00+00:00")
    assert out.created_at == "2026-01-01T00:00:00+00:00"
    assert out.modified_at == "2026-08-27T10:00:00+00:00"


def test_stamp_scenario_does_not_mutate_input():
    from multises.scenario import Scenario, stamp_scenario
    sc = Scenario(id="s1", name="X")
    stamp_scenario(sc, "2026-08-27T10:00:00+00:00")
    assert sc.created_at == "" and sc.modified_at == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -q -k stamp_scenario`
Expected: FAIL with `ImportError: cannot import name 'stamp_scenario'`

- [ ] **Step 3: Write the function**

In `multises/scenario.py`, add below `remove_intervention`:

```python
def stamp_scenario(scenario: "Scenario", now: str) -> "Scenario":
    """Return a copy with modified_at=now, and created_at=now if unset.

    `now` is an argument rather than a clock read so this stays pure and
    testable; the Shiny layer reads the clock and passes it in.
    """
    return replace(scenario, modified_at=now,
                   created_at=scenario.created_at or now)
```

`replace` is already imported at the top of the module.

- [ ] **Step 4: Re-export**

Add `stamp_scenario` to the `from .scenario import (...)` list and `"stamp_scenario",` to `__all__` in `multises/__init__.py`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add multises/scenario.py multises/__init__.py tests/test_scenario.py
git commit -m "feat(scenario): stamp_scenario populates created_at/modified_at"
```

---

### Task 3: `_baseline_drift` pure predicate

**Files:**
- Modify: `multises_app/modules/scenario_view.py` (module-level function, directly above `@module.ui`)
- Test: `tests/test_scenario_view_logic.py`

**Interfaces:**
- Consumes: `Scenario` (already imported in `scenario_view.py`)
- Produces: `_baseline_drift(active: Scenario | None, current_name: str) -> str | None` — warning text, or `None` when there is no drift. Used by Task 6.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scenario_view_logic.py`:

```python
def test_baseline_drift_none_when_no_active_scenario():
    from multises_app.modules.scenario_view import _baseline_drift
    assert _baseline_drift(None, "Curonian") is None


def test_baseline_drift_none_when_baseline_unrecorded():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _baseline_drift
    # Scenarios authored before Task 4 carry baseline_name="". Silence is
    # correct: we do not know what they were authored against.
    assert _baseline_drift(Scenario(id="s1", name="X"), "Curonian") is None


def test_baseline_drift_none_when_baseline_matches():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _baseline_drift
    sc = Scenario(id="s1", name="X", baseline_name="Curonian")
    assert _baseline_drift(sc, "Curonian") is None


def test_baseline_drift_names_both_projects():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _baseline_drift
    sc = Scenario(id="s1", name="X", baseline_name="Curonian")
    msg = _baseline_drift(sc, "Nemunas")
    assert msg is not None
    assert "Curonian" in msg and "Nemunas" in msg
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q -k baseline_drift`
Expected: FAIL with `ImportError: cannot import name '_baseline_drift'`

- [ ] **Step 3: Write the function**

In `multises_app/modules/scenario_view.py`, directly above `@module.ui`:

```python
def _baseline_drift(active: Scenario | None, current_name: str) -> str | None:
    """Warning text when `active` was authored against a different baseline.

    Returns None when there is nothing to say — including when baseline_name
    is empty, which means the scenario predates baseline recording. Drift is
    informational: the scenario still materialises, and unresolved targets
    surface as the W501 warnings the banner already lists.
    """
    if active is None or not active.baseline_name:
        return None
    if active.baseline_name == current_name:
        return None
    return (f"This scenario was authored against baseline "
            f"'{active.baseline_name}'; the current project is "
            f"'{current_name}'. Targets may not resolve.")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/scenario_view.py tests/test_scenario_view_logic.py
git commit -m "feat(scenario-view): pure _baseline_drift predicate"
```

---

### Task 4: Stamp `baseline_name` and timestamps at creation

**Files:**
- Modify: `multises_app/modules/scenario_view.py` (imports; `_utc_now` helper; `_add` effect at ~:90)
- Test: `tests/test_scenario_view_logic.py`

**Interfaces:**
- Consumes: `stamp_scenario` (Task 2)
- Produces: `_utc_now() -> str` — module-level clock read, used by Task 5. Authored scenarios now carry a non-empty `baseline_name`, which is what makes Task 6's drift check meaningful.

- [ ] **Step 1: Write the failing test for the clock helper**

Append to `tests/test_scenario_view_logic.py`:

```python
def test_utc_now_is_second_precision_utc_iso():
    from multises_app.modules.scenario_view import _utc_now
    s = _utc_now()
    assert s.endswith("+00:00")
    assert len(s) == len("2026-08-27T10:00:00+00:00")
    from datetime import datetime
    datetime.fromisoformat(s)   # parses


def test_replace_in_set_substitutes_by_id_with_a_new_object():
    from multises.scenario import Scenario, ScenarioSet, ScenarioSetMetadata
    from multises_app.modules.scenario_view import _replace_in_set
    a, b = Scenario(id="s1", name="A"), Scenario(id="s2", name="B")
    ss = ScenarioSet(metadata=ScenarioSetMetadata(name="Set"), scenarios=[a, b])
    out = _replace_in_set(ss, Scenario(id="s1", name="A renamed"))
    assert out is not ss                      # identity must change to invalidate
    assert [s.name for s in out.scenarios] == ["A renamed", "B"]
    assert ss.scenarios[0].name == "A"        # input not mutated


def test_replace_in_set_is_a_no_op_for_a_non_member():
    from multises.scenario import Scenario, ScenarioSet, ScenarioSetMetadata
    from multises_app.modules.scenario_view import _replace_in_set
    ss = ScenarioSet(metadata=ScenarioSetMetadata(), scenarios=[])
    assert _replace_in_set(ss, Scenario(id="s1", name="Fresh")) is ss
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q -k "utc_now or replace_in_set"`
Expected: FAIL with `ImportError: cannot import name '_utc_now'`

- [ ] **Step 3: Add the imports and the clock helper**

In `multises_app/modules/scenario_view.py`, add to the imports at the top:

```python
from datetime import datetime, timezone
```

and extend the existing scenario import to include `stamp_scenario`:

```python
from multises.scenario import (Intervention, Scenario, add_intervention, ScenarioError,
                                ScenarioErrorCode, stamp_scenario, ScenarioSet)
```

Then add above `_baseline_drift`:

```python
def _utc_now() -> str:
    """Second-precision UTC ISO timestamp, matching project_setup.py:52."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _replace_in_set(ss: ScenarioSet, sc: Scenario) -> ScenarioSet:
    """Return `ss` with the member sharing `sc.id` replaced by `sc`.

    Returns `ss` unchanged when the id is absent (a freshly authored scenario
    belongs to no loaded set — state.py:118 seeds an empty one). Builds a NEW
    ScenarioSet rather than mutating the list: reactive.Value.set()
    short-circuits on identity, so re-setting the same object would never
    invalidate the picker. Without this, edits and renames live only in
    active_scenario — the selector label goes stale, and _pick_scenario
    resurrects the pre-edit member, silently discarding them.
    """
    members = list(getattr(ss, "scenarios", None) or [])
    if not any(s.id == sc.id for s in members):
        return ss
    return ScenarioSet(metadata=ss.metadata,
                       scenarios=[sc if s.id == sc.id else s for s in members])
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q -k "utc_now or replace_in_set"`
Expected: PASS

- [ ] **Step 5: Wire creation stamping into `_add`**

In the `_add` effect, replace these two lines:

```python
            base = sc or Scenario(id="s1", name=input.scenario_name())
            state.active_scenario.set(add_intervention(base, iv))
```

with:

```python
            # Record the baseline at creation so Task 6's drift check has
            # something to compare against; stamp on every edit so a saved
            # file reports when it actually changed.
            base = sc or Scenario(
                id="s1", name=input.scenario_name(),
                baseline_name=state.active_multises.get().metadata.name)
            edited = stamp_scenario(add_intervention(base, iv), _utc_now())
            state.active_scenario.set(edited)
            # Keep a loaded set in sync, or _pick_scenario resurrects the
            # pre-edit member and silently discards these interventions.
            state.scenario_set.set(_replace_in_set(state.scenario_set.get(), edited))
            state.dirty.set(True)
```

- [ ] **Step 6: Run the scenario tests**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py tests/test_scenario_view_module.py tests/test_state_scenario.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add multises_app/modules/scenario_view.py tests/test_scenario_view_logic.py
git commit -m "feat(scenario-view): record baseline and timestamps at creation"
```

---

### Task 5: Live scenario-name editing

Chunk 1 only relabelled the input honestly ("New scenario name"); the name never reached the `Scenario`. Now that the name round-trips through save and shows in the selector, editing must actually apply.

**Files:**
- Modify: `multises_app/modules/scenario_view.py` (new effect; `replace` import)
- Test: `tests/test_scenario_view_logic.py`

**Interfaces:**
- Consumes: `stamp_scenario` (Task 2), `_utc_now` (Task 4)
- Produces: nothing new; `active_scenario.name` now tracks the input.

- [ ] **Step 1: Write the failing test for the rename decision**

The effect itself needs a Shiny session, but its *decision* is pure. Extract and test that. Append to `tests/test_scenario_view_logic.py`:

```python
def test_should_rename_false_when_no_scenario():
    from multises_app.modules.scenario_view import _should_rename
    assert _should_rename(None, "Anything") is False


def test_should_rename_false_when_blank_or_unchanged():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _should_rename
    sc = Scenario(id="s1", name="Depolder")
    assert _should_rename(sc, "   ") is False
    assert _should_rename(sc, "Depolder") is False
    assert _should_rename(sc, "  Depolder  ") is False   # trimmed compare


def test_should_rename_true_on_a_real_change():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _should_rename
    sc = Scenario(id="s1", name="Depolder")
    assert _should_rename(sc, "Depolder v2") is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q -k should_rename`
Expected: FAIL with `ImportError: cannot import name '_should_rename'`

- [ ] **Step 3: Write the predicate and the effect**

Add `replace` to the dataclasses import at the top of `scenario_view.py`:

```python
from dataclasses import replace
```

Add beside `_baseline_drift`:

```python
def _should_rename(active: Scenario | None, raw_name: str) -> bool:
    """True when `raw_name` is a real change to `active`'s name.

    Guards the rename effect against no-op churn: re-setting an identical
    name would re-stamp modified_at on every keystroke.
    """
    if active is None:
        return False
    new_name = (raw_name or "").strip()
    return bool(new_name) and new_name != active.name
```

Then add this effect inside `scenario_view_server`, directly after `_add`:

```python
    @reactive.effect
    @reactive.event(input.scenario_name)
    def _rename():
        # reactive.event on the INPUT plus isolate on the read: this effect
        # writes active_scenario, so taking a reactive dependency on it here
        # would make the effect re-trigger itself.
        with reactive.isolate():
            sc = state.active_scenario.get()
        if not _should_rename(sc, input.scenario_name()):
            return
        renamed = replace(sc, name=input.scenario_name().strip())
        stamped = stamp_scenario(renamed, _utc_now())
        state.active_scenario.set(stamped)
        # Keep a loaded set in sync, or the picker label goes stale and
        # _pick_scenario discards the rename.
        state.scenario_set.set(_replace_in_set(state.scenario_set.get(), stamped))
```

**No retrigger loop.** `_add` and `_rename` are both `@reactive.event`-gated on inputs, which isolates their bodies, so reading and writing `scenario_set` here cannot re-fire them. The re-rendered `input_select` may re-emit `input.pick_scenario` with the same value; `_pick_scenario`'s `if active is not None and active.id == chosen: return` guard terminates that.

- [ ] **Step 4: Retitle the input and move it off per-keystroke updates**

`ui.input_text` defaults to `update_on="change"`, i.e. debounced keystroke
updates. Left alone, every intermediate name ("D", "De", "Dep"...) re-sets
`active_scenario`, invalidating `_comparison()` — a full `compare_scenario`
materialise plus five analyses — and re-rendering five diff cards.
`_should_rename` only suppresses *identical* names, so it does not help here.

The label also needs correcting: Chunk 1's "New scenario name" was honest when
the field only named a scenario yet to be created, but after this task it
renames the *active* scenario.

Change `multises_app/modules/scenario_view.py:54`:

```python
            ui.input_text("scenario_name", "Scenario name",
                          value="New scenario", update_on="blur"),
```

Safe to rename the label: `"New scenario name"` appears nowhere else in the
repo, `test_scenario_view_module.py` asserts on ids and the disclaimer, and
`test_scenario_e2e.py` uses `#scenario-*` ids. If `update_on="blur"` turns out
to interfere with the `ui.update_text` echo in Tasks 8 and 9, fall back to
`update_on="change"` plus a debounce in the effect.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add multises_app/modules/scenario_view.py tests/test_scenario_view_logic.py
git commit -m "feat(scenario-view): live scenario-name editing"
```

---

### Task 6: Baseline drift in the banner

**Files:**
- Modify: `multises_app/modules/scenario_view.py` (`drift_banner` at ~:135)
- Test: covered by Task 3's predicate tests; no new unit test (see spec §11 carve-out)

**Interfaces:**
- Consumes: `_baseline_drift` (Task 3)
- Produces: nothing

- [ ] **Step 1: Extend `drift_banner`**

Replace the whole `drift_banner` renderer with:

```python
    @output
    @render.ui
    def drift_banner():
        report = _comparison()["report"]
        warnings = report.warnings if report else []
        drift = _baseline_drift(state.active_scenario.get(),
                                state.active_multises.get().metadata.name)
        if not drift and not warnings:
            return ui.tags.span("")   # inert unless there is something to surface
        parts: list = []
        if drift:
            parts.append(ui.tags.p(f"⚠ {drift}", class_="mb-1"))
        if warnings:
            parts.append(ui.tags.strong(
                f"⚠ {len(warnings)} intervention(s) had no structural effect"))
            parts.append(ui.tags.ul(*[ui.tags.li(msg) for _code, msg in warnings]))
        return ui.div(*parts, class_="alert alert-warning", role="alert")
```

- [ ] **Step 2: Verify the existing banner e2e still passes**

`tests/test_scenario_e2e.py` asserts the banner contains "had no structural effect". That string is unchanged, and drift is absent for a freshly authored scenario (its `baseline_name` equals the current project), so the banner must behave exactly as before in that flow.

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_e2e.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add multises_app/modules/scenario_view.py
git commit -m "feat(scenario-view): surface baseline drift in the banner"
```

---

### Task 7: Save — download the active scenario

**Files:**
- Modify: `multises_app/modules/scenario_view.py` (sidebar UI; new `@render.download`)
- Test: `tests/test_scenario_view_logic.py`

**Interfaces:**
- Consumes: `scenario_set_to_json` (Task 1)
- Produces: `_active_scenario_set(active: Scenario | None) -> ScenarioSet` — the pure payload builder, so the download's content is testable without driving a browser. Download control id: `#scenario-download_scenarios`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scenario_view_logic.py`:

```python
def test_active_scenario_set_wraps_the_active_scenario():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _active_scenario_set
    sc = Scenario(id="s1", name="Depolder")
    ss = _active_scenario_set(sc)
    assert ss.scenarios == [sc]
    assert ss.metadata.name == "Depolder"


def test_active_scenario_set_is_valid_when_nothing_authored():
    from multises.scenario import scenario_set_to_json
    from multises_app.modules.scenario_view import _active_scenario_set
    ss = _active_scenario_set(None)
    assert ss.scenarios == []
    assert ss.metadata.name == "Scenarios"
    import json
    json.loads(scenario_set_to_json(ss))   # still valid JSON, no crash
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q -k active_scenario_set`
Expected: FAIL with `ImportError: cannot import name '_active_scenario_set'`

- [ ] **Step 3: Write the payload builder**

Extend the scenario import in `scenario_view.py` to add three names (`ScenarioSet` was already added in Task 4). **`load_scenario_set` is unused in this task on purpose** — it is imported here so Task 8's upload effect has it. Do not strip it as an unused import: Task 8 calls it inside a broad `except Exception`, so the resulting `NameError` would be swallowed into a friendly toast and the Open button would silently never work.

```python
from multises.scenario import (Intervention, Scenario, add_intervention, ScenarioError,
                                ScenarioErrorCode, stamp_scenario, ScenarioSet,
                                ScenarioSetMetadata, scenario_set_to_json,
                                load_scenario_set)   # ScenarioSet added in Task 4
```

Add beside `_baseline_drift`:

```python
def _active_scenario_set(active: Scenario | None) -> ScenarioSet:
    """Wrap the active scenario as a one-member ScenarioSet for download.

    The set borrows the scenario's name. With a single-scenario download the
    distinction is cosmetic; once multi-scenario sets are authored (out of
    scope, spec §2) the set needs a name of its own.
    """
    return ScenarioSet(
        metadata=ScenarioSetMetadata(name=active.name if active else "Scenarios"),
        scenarios=[active] if active else [])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q -k active_scenario_set`
Expected: PASS

- [ ] **Step 5: Add the sidebar control**

In `scenario_view_ui`, immediately after the `ui.output_ui("intervention_list")` line:

```python
            ui.tags.hr(),
            ui.h5("Scenario file"),
            ui.download_button("download_scenarios", "Save (download .json)",
                               class_="btn btn-success"),
```

- [ ] **Step 6: Add the download renderer**

Inside `scenario_view_server`, after the `_rename` effect:

```python
    @render.download(
        filename=lambda: f"mosaicses-{datetime.now():%Y%m%d-%H%M%S}.scenarios.json")
    def download_scenarios():
        # The renderer may read the clock; the pure builder above may not.
        yield scenario_set_to_json(
            _active_scenario_set(state.active_scenario.get())).encode("utf-8")
```

- [ ] **Step 7: Confirm the app still starts**

Run: `micromamba run -n shiny python -c "import multises_app.modules.scenario_view"`
Expected: no output, exit 0.

- [ ] **Step 8: Commit**

```bash
git add multises_app/modules/scenario_view.py tests/test_scenario_view_logic.py
git commit -m "feat(scenario-view): save the active scenario as a .scenarios.json download"
```

---

### Task 8: Open — upload a scenario set

**Files:**
- Modify: `multises_app/modules/scenario_view.py` (sidebar UI; `_first_scenario`; new effect)
- Test: `tests/test_scenario.py` (load boundary) + `tests/test_scenario_view_logic.py` (`_first_scenario`)

**Interfaces:**
- Consumes: `load_scenario_set` (already in the library; imported in Task 7)
- Produces: `_first_scenario(scenarios: list) -> Scenario | None` — the upload's activation policy. Upload control id `#scenario-upload_scenarios`. Populates `state.scenario_set`, which Task 9 reads.

- [ ] **Step 1: Write the failing test**

This pins the claim the UI's error handling depends on — that a tampered file raises at load rather than silently producing a broken scenario. Append to `tests/test_scenario.py`:

```python
def test_load_scenario_set_rejects_a_bad_channel_type(tmp_path):
    import json
    import pytest
    from multises.scenario import load_scenario_set, ScenarioError
    payload = {
        "metadata": {"name": "Tampered", "schema_version": 1},
        "scenarios": [{
            "id": "s1", "name": "Tampered", "description": "",
            "baseline_name": "Curonian",
            "interventions": [{
                "id": "i1", "kind": "add_channel", "label": "",
                "compartment_id": None,
                "target": {"source": "a", "channel_type": "BOGUS", "target": "b"},
                "rationale": "",
            }],
            "created_at": "", "modified_at": "", "schema_version": 1,
        }],
    }
    path = tmp_path / "bad.scenarios.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_scenario_set(path)
```

And append to `tests/test_scenario_view_logic.py` — spec §11 names the
upload-activate policy as a module-level test, so it must not stay untested
inside a Shiny effect:

```python
def test_first_scenario_none_on_empty_set():
    from multises_app.modules.scenario_view import _first_scenario
    assert _first_scenario([]) is None


def test_first_scenario_activates_the_first_member():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _first_scenario
    a = Scenario(id="s1", name="A")
    assert _first_scenario([a, Scenario(id="s2", name="B")]) is a
```

- [ ] **Step 2: Run the test**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -q -k rejects_a_bad_channel_type`
Expected: PASS immediately — `Intervention.__post_init__` already raises S004. If it FAILS, stop: the untrusted-file boundary in Step 4 is unsound and the spec's §10 assumption is wrong.

- [ ] **Step 3: Add the activation-policy helper**

Beside `_baseline_drift`:

```python
def _first_scenario(scenarios: list):
    """The scenario an upload activates: the first member, or None for an
    empty set. Kept separate from Task 9's _scenario_by_id because the
    policies genuinely differ - upload falls back to the first member, the
    picker must not fall back at all.
    """
    return scenarios[0] if scenarios else None
```

- [ ] **Step 4: Add the sidebar control**

Directly after the `download_scenarios` button added in Task 7:

```python
            ui.input_file("upload_scenarios", "Open .scenarios.json",
                          accept=[".json"], multiple=False),
```

- [ ] **Step 5: Add the upload effect**

Inside `scenario_view_server`, after `download_scenarios`:

```python
    @reactive.effect
    @reactive.event(input.upload_scenarios)
    def _open_scenarios():
        finfo = input.upload_scenarios()
        if not finfo:
            return
        # Untrusted-file boundary, mirroring project_setup._apply_open: a
        # tampered file raises ScenarioError (S001/S002/S004) at load, and
        # a malformed one raises at the JSON parse. Catch broadly, log,
        # toast, and leave state untouched.
        try:
            loaded = load_scenario_set(finfo[0]["datapath"])
        except Exception as e:  # noqa: BLE001 — untrusted file boundary
            _log.exception("scenario_view: open failed")
            ui.notification_show(
                friendly_error("Could not load the scenarios file", e),
                duration=6, type="warning")
            return
        state.scenario_set.set(loaded)
        first = _first_scenario(list(getattr(loaded, "scenarios", None) or []))
        if first is not None:
            state.active_scenario.set(first)
            ui.update_text("scenario_name", value=first.name)
            state.dirty.set(True)
```

- [ ] **Step 6: Verify the module imports and the suite still passes**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py tests/test_scenario_view_logic.py tests/test_scenario_view_module.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add multises_app/modules/scenario_view.py tests/test_scenario.py tests/test_scenario_view_logic.py
git commit -m "feat(scenario-view): open a .scenarios.json sidecar"
```

---

### Task 9: Scenario selector for multi-scenario loads

**Files:**
- Modify: `multises_app/modules/scenario_view.py` (sidebar UI; `scenario_picker` output; pick effect)
- Test: `tests/test_scenario_view_logic.py`

**Interfaces:**
- Consumes: `state.scenario_set` (populated by Task 8)
- Produces: `_picker_choices(scenarios: list) -> dict` and `_scenario_by_id(scenarios: list, chosen: str) -> Scenario | None`. Selector id `#scenario-pick_scenario`, rendered only when the set holds 2+ scenarios.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scenario_view_logic.py`:

```python
def test_picker_choices_empty_below_two_scenarios():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _picker_choices
    assert _picker_choices([]) == {}
    assert _picker_choices([Scenario(id="s1", name="Only")]) == {}


def test_picker_choices_maps_id_to_name():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _picker_choices
    out = _picker_choices([Scenario(id="s1", name="A"),
                           Scenario(id="s2", name="B")])
    assert out == {"s1": "A", "s2": "B"}


def test_scenario_by_id_matches_id_not_name():
    from multises.scenario import Scenario
    from multises_app.modules.scenario_view import _scenario_by_id
    # Names cross-wired to the OTHER scenario's id, so a name-matcher returns
    # `a` where `b` is correct.
    a, b = Scenario(id="s1", name="s2"), Scenario(id="s2", name="s1")
    assert _scenario_by_id([a, b], "s2") is b
    assert _scenario_by_id([a, b], "nope") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q -k "picker_choices or scenario_by_id"`
Expected: FAIL with `ImportError: cannot import name '_picker_choices'`

- [ ] **Step 3: Write the pure helper**

Beside `_baseline_drift`:

```python
def _picker_choices(scenarios: list) -> dict:
    """id -> name for the selector, empty below two scenarios.

    A single-scenario load auto-activates, so a one-option selector would be
    clutter that does nothing.
    """
    if len(scenarios) < 2:
        return {}
    return {s.id: s.name for s in scenarios}


def _scenario_by_id(scenarios: list, chosen: str):
    """The scenario whose id is `chosen`, or None. No fallback on purpose:
    after an upload swaps the set, input.pick_scenario can still hold a stale
    id, and activating an arbitrary member then is worse than doing nothing.
    """
    for s in scenarios:
        if s.id == chosen:
            return s
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py -q -k "picker_choices or scenario_by_id"`
Expected: PASS

- [ ] **Step 5: Add the selector slot to the sidebar**

Directly after the `upload_scenarios` input:

```python
            ui.output_ui("scenario_picker"),
```

- [ ] **Step 6: Add the renderer and the pick effect**

Inside `scenario_view_server`, after `_open_scenarios`:

```python
    @output
    @render.ui
    def scenario_picker():
        ss = state.scenario_set.get()
        scenarios = list(getattr(ss, "scenarios", None) or [])
        choices = _picker_choices(scenarios)
        if not choices:
            return ui.tags.span("")
        active = state.active_scenario.get()
        return ui.input_select(
            "pick_scenario", "Scenario", choices=choices,
            selected=active.id if active else scenarios[0].id)

    @reactive.effect
    @reactive.event(input.pick_scenario)
    def _pick_scenario():
        chosen = input.pick_scenario()
        ss = state.scenario_set.get()
        with reactive.isolate():
            active = state.active_scenario.get()
        if active is not None and active.id == chosen:
            return          # already active: no churn
        picked = _scenario_by_id(list(getattr(ss, "scenarios", None) or []), chosen)
        if picked is None:
            return          # stale id after a set swap: do nothing
        state.active_scenario.set(picked)
        ui.update_text("scenario_name", value=picked.name)
```

- [ ] **Step 7: Run the scenario tests**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_logic.py tests/test_scenario_view_module.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add multises_app/modules/scenario_view.py tests/test_scenario_view_logic.py
git commit -m "feat(scenario-view): scenario selector for multi-scenario loads"
```

---

### Task 10: E2e — the file controls render

Per spec §11, the e2e asserts only that the controls exist. Driving a real file upload plus a project swap in Playwright is high-cost, and the logic it would exercise is already covered by the pure helpers in Tasks 3, 5, 7, 8 and 9 — `_baseline_drift` (drift), `_first_scenario` (upload→activate), `_scenario_by_id` (pick→activate), `_picker_choices` (when the selector appears) and `_replace_in_set` (edit write-back). **This is a declared coverage limit, not an oversight.**

**Files:**
- Modify: `tests/test_scenario_e2e.py`

**Interfaces:**
- Consumes: `#scenario-download_scenarios` (Task 7), `#scenario-upload_scenarios` (Task 8)
- Produces: nothing

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scenario_e2e.py` (the file already imports `sync_playwright`, `expect` and `wait_for_nav`):

```python
def test_scenario_file_controls_render(mosaicses_app_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            wait_for_nav(page, "scenario")
            page.click("#sespy_nav_scenario")

            # Namespaced ids, never a suffix match: every nav panel shares
            # one DOM, and a pattern selector here would collide with the
            # project panel's own download/upload controls.
            expect(page.locator("#scenario-download_scenarios")).to_be_visible()
            expect(page.locator("#scenario-upload_scenarios")).to_be_attached()

            # The picker stays hidden until a 2+ scenario set is loaded.
            assert page.locator("#scenario-pick_scenario").count() == 0
        finally:
            browser.close()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_e2e.py -q -k file_controls`
Expected: FAIL — the controls do not exist if Tasks 7–9 were skipped. If Tasks 7–9 are already done, it should PASS; in that case confirm by checking out the pre-Task-7 state, or accept the earlier task-level verification.

- [ ] **Step 3: Run the full e2e file**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_e2e.py -q`
Expected: PASS (3 tests)

- [ ] **Step 4: Run the FULL suite — the merge gate**

Run: `micromamba run -n shiny python -m pytest tests/ -q`
Expected: PASS, ~512 tests (487 today + 24 new unit tests from Tasks 1-9 + Task 10's e2e). The exact number will differ if you split or merge cases — what matters is **0 failed**.

Never gate on `-k "not e2e"`. A cross-panel regression reached `main` twice in this repo because a green subset felt like a green suite.

- [ ] **Step 5: Commit**

```bash
git add tests/test_scenario_e2e.py
git commit -m "test(e2e): scenario file controls render"
```

---

## Done means

- The Studio can save the active scenario, and re-open it in a fresh session with its interventions, name, and baseline intact.
- A scenario loaded against a different project shows a drift warning naming both projects.
- Renaming the scenario updates the saved name and the selector label.
- `created_at` / `modified_at` are populated in every saved file.
- Full suite green, including all e2e.

## Explicitly out of scope

Accumulating several authored scenarios into one file before download; rename/delete of saved scenarios; a separate `scenario_dirty` flag (spec §14 Decision F); and the Chunk 3 sign-propagation engine.
