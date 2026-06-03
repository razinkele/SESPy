# MosaicSES Chunk 4b — Project Setup Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the existing (currently empty) `"project"` nav-panel slot with a two-column MultiSES-metadata editing form, mirroring `sespy.modules.pims_project` adapted to `MultiSESMetadata`.

**Architecture:** One new Shiny module (`multises_app/modules/project_setup.py`) with `@module.ui` + `@module.server` decorators. Read-only consumer of `state.active_multises` for form population; writer on Save click. Two pure helpers (`_build_new_metadata`, `_build_new_multises`) extracted for testability. Five unit tests in a new test file.

**Tech Stack:** Shiny for Python 1.6.1, `sespy.modules.pims_project` as reference pattern (207 lines, two-column form, explicit Save button, reactive load/save discipline). Python managed by `micromamba run -n shiny` (no venv, no pip-install — per user CLAUDE.md).

**Spec (source of truth):** [`../specs/2026-05-18-mosaicses-chunk4b-project-setup-design.md`](../specs/2026-05-18-mosaicses-chunk4b-project-setup-design.md).

**Working directory for all commands:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES` (the MosaicSES git repo). Run pytest with `micromamba run -n shiny pytest tests/ -q`.

**Baseline at start of plan:** `main` branch at `27e3476` (chunk-4a shipped 2026-05-18); 267 unit tests + 2 Playwright e2e tests passing (269 total). Pre-existing uncommitted `.gitignore` modification (adds `.superpowers/`) stays untouched throughout all tasks.

**Pytest count expectations — read this before every `Expected: N passed` line.** Each task documents an approximate count (e.g., `Expected: 268 passed`) for orientation. The **load-bearing assertion is "no FAILED, no ERROR"** — exact counts may drift by ±2 if intermediate tasks add internal helper tests. Treat counts as informational; reject the run only on actual failures/errors.

**Branch strategy:** Work directly on `main` (chunk-4a's pattern). After all tasks, the human smoke + push happens at Task 6. Tag `chunk-4a-shipped` at `4bb4168` is preserved as a recovery anchor.

---

## Phase A — Task 0: Pre-implementation probes

Each probe is a 2-5-line micro-script. If any probe fails or returns unexpected output, **stop and revise the spec before proceeding**.

### Task 0: Run 7 probes capturing environment + API assumptions

**Files:**
- Create: `docs/2026-05-18-chunk4b-probe-results.md` (probe log)

- [ ] **Step 1: Probe 1 — `sespy.regional_seas.get_regional_seas()` shape**

Verified via multi-angle review 2026-05-18: `sespy.regional_seas` does NOT export a `REGIONAL_SEAS` constant. The function `get_regional_seas()` returns `dict[slug, dict[name, ecosystem_types, common_issues, countries, country_codes]]`. This step is now a CONFIRMATION (not a discovery), to catch any sespy upstream API drift before Task 2 lands the import.

Run:
```powershell
micromamba run -n shiny python -c "from sespy.regional_seas import get_regional_seas; rs = get_regional_seas(); first_slug, first_data = next(iter(rs.items())); print('slugs (first 5):', list(rs.keys())[:5]); print('first entry keys:', list(first_data.keys())); print('first entry name:', first_data.get('name'))"
```
Expected: prints 5 slugs including `'baltic'`, `'mediterranean'`, `'north_sea'`; first entry keys include `'name'`; the `name` value is a human-readable label string (e.g., `'Baltic Sea'`). If the shape diverges, STOP and revise Tasks 2 + 3.

- [ ] **Step 2: Probe 2 — `sespy.constants` resolves DA_SITES / TEMPORAL_SCALES / SPATIAL_SCALES**

Run:
```powershell
micromamba run -n shiny python -c "from sespy.constants import DA_SITES, TEMPORAL_SCALES, SPATIAL_SCALES; print('DA_SITES:', DA_SITES); print('TEMPORAL_SCALES:', TEMPORAL_SCALES); print('SPATIAL_SCALES:', SPATIAL_SCALES)"
```
Expected: prints three iterables (likely lists or tuples of strings). Capture verbatim into probe log — Task 2 reuses these strings as choice values. If any are absent, STOP (the chunk-4a `pims_project` reference imports them, so they should be present in the same `sespy.constants` module).

- [ ] **Step 3: Probe 3 — Current `"project"` nav-panel content in `app.py`**

Read `app.py` and find the `PANELS` tuple. Locate the `ui.nav_panel(...)` entry with `value="project"`. Capture into the probe log: (a) the exact line range, (b) what's currently in the panel body (empty placeholder, "coming soon" text, or other). Task 4 replaces this body with `project_setup_ui("project")`. If the panel is missing entirely, STOP and add a new entry to PANELS at the right slot in Task 4 instead of replacing.

- [ ] **Step 4: Probe 4 — seed/constants alignment audit** (heads-up, not a stop-condition — capture findings to the probe log and continue regardless)

Run:
```powershell
micromamba run -n shiny python -c "from multises import seed_curonian; from sespy.constants import DA_SITES; from sespy.regional_seas import get_regional_seas; ms = seed_curonian(); rs_slugs = list(get_regional_seas().keys()); print('seed da_site:', repr(ms.metadata.da_site), '— in DA_SITES:', ms.metadata.da_site in DA_SITES); print('seed regional_sea:', repr(ms.metadata.regional_sea), '— in get_regional_seas() slugs:', ms.metadata.regional_sea in rs_slugs)"
```
Expected: both report `False` (verified 2026-05-18 — see spec R6). The form will silently show empty for these two fields on first load. This is a known cosmetic gap, reconciled in chunk-4c. Document the observed mismatch in the probe log so the smoke-checklist gate doesn't surprise the human walker.

- [ ] **Step 5: Probe 5 — `state.event_bus.emit_isa_change()` signature**

Run:
```powershell
micromamba run -n shiny python -c "from multises_app.state import create_multises_state; from multises import seed_curonian; s = create_multises_state(seed_curonian()); import inspect; print('emit_isa_change signature:', inspect.signature(s.event_bus.emit_isa_change)); print('callable:', callable(s.event_bus.emit_isa_change))"
```
Expected: `()` (no args) and `True`. Confirms Task 3's `_handle_save` can call it with no arguments. If the signature requires args, STOP and update the spec/plan.

- [ ] **Step 6: Probe 6 — Shiny 1.6.1 API surface batch**

Run:
```powershell
micromamba run -n shiny python -c "import inspect; from shiny import ui, reactive; print('notif:', inspect.signature(ui.notification_show)); print('event:', inspect.signature(reactive.event)); print('layout_columns present:', hasattr(ui, 'layout_columns')); print('dl/dt/dd:', all(hasattr(ui.tags, t) for t in ('dl', 'dt', 'dd')))"
```
Expected: `notif` signature includes `type: Literal["default", "message", "warning", "error"]` and `duration: Optional[int|float] = 5`; `event` signature includes `ignore_none: bool = True, ignore_init: bool = False`; `layout_columns present: True`; `dl/dt/dd: True`. Validates Task 2 (UI tags) + Task 3 (`@reactive.event(input.save, ignore_init=True)` + `ui.notification_show(..., type="error")` are real API). **Action on divergence**: STOP and revise the affected Task 2 / Task 3 snippets before proceeding.

- [ ] **Step 7: Probe 7 — `MultiSES(metadata, compartments, channels)` reconstruction smoke**

Run:
```powershell
micromamba run -n shiny python -c "from multises import seed_curonian; from multises.data_structure import MultiSES; ms = seed_curonian(); ms2 = MultiSES(metadata=ms.metadata, compartments=ms.compartments, channels=ms.channels); print('reconstruction ok'); print('cmp_ref_preserved:', ms2.compartments is ms.compartments); print('ch_ref_preserved:', ms2.channels is ms.channels); print('len(cmp):', len(ms2.compartments), 'len(ch):', len(ms2.channels))"
```
Expected: no exception (post_init validation passes); both reference-preservation checks `True`; counts match `(6, 26+)`. Validates Task 1's `_build_new_multises` claim that "byte-for-byte same lists, cannot fail" is correct. **Action on divergence**: STOP and revise Task 1's `_build_new_multises` (likely needs deep-copy if `__post_init__` mutates).

- [ ] **Step 8: Write probe log**

Create `docs/2026-05-18-chunk4b-probe-results.md` with one section per probe (1, 2, 3, 4, 5, 6, 7). For each: the command run, the actual output (verbatim), and a one-line interpretation. Add a top-level summary line noting "all 7 probes ran successfully" or which ones diverged.

- [ ] **Step 9: Commit the probe log**

```powershell
git add docs/2026-05-18-chunk4b-probe-results.md
git commit -m "docs(mosaicses): chunk-4b Task 0 probe results"
```

---

## Phase B — Task 1: Pure helpers + helper tests

### Task 1: `_build_new_metadata` + `_build_new_multises` helpers with TDD

**Files:**
- Create: `multises_app/modules/project_setup.py` (initial — helpers only)
- Create: `tests/test_project_setup_module.py` (initial — 2 helper tests)

- [ ] **Step 1: Write failing tests in `tests/test_project_setup_module.py`**

```python
"""Project Setup module tests (chunk 4b)."""
from __future__ import annotations


def test_build_new_metadata_applies_empty_name_fallback():
    from multises_app.modules.project_setup import _build_new_metadata
    from multises import seed_curonian
    ms = seed_curonian()
    inputs = {
        "name": "", "description": "test description",
        "da_site": "", "river_basin": "Nemunas",
        "regional_sea": "", "focal_issue": "Eutrophication",
        "temporal_scale": "", "spatial_scale": "",
    }
    new_meta = _build_new_metadata(ms.metadata, inputs)
    assert new_meta.name == "Untitled MultiSES"
    assert new_meta.description == "test description"
    assert new_meta.river_basin == "Nemunas"
    assert new_meta.focal_issue == "Eutrophication"
    assert new_meta.created_at == ms.metadata.created_at  # preserved
    assert new_meta.modified_at != ms.metadata.modified_at  # updated
    assert new_meta.schema_version == ms.metadata.schema_version  # preserved


def test_build_new_multises_preserves_compartments_and_channels():
    from multises_app.modules.project_setup import _build_new_multises
    from multises import seed_curonian
    ms = seed_curonian()
    new_meta = ms.metadata  # use same metadata; identity check is what matters
    ms_new = _build_new_multises(ms, new_meta)
    assert ms_new.compartments is ms.compartments  # same list reference
    assert ms_new.channels is ms.channels
    assert ms_new.metadata is new_meta
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
micromamba run -n shiny pytest tests/test_project_setup_module.py -v
```
Expected: 2 ImportError / ModuleNotFoundError (module doesn't exist yet).

- [ ] **Step 3: Create `multises_app/modules/project_setup.py` with helpers**

```python
"""Project Setup module — MultiSES metadata-editing form (chunk 4b).

Two-column form (left: Project Information + Save; right: System Scope + status).
Direct adaptation of `sespy.modules.pims_project` to `MultiSESMetadata`.

Pure helpers `_build_new_metadata` and `_build_new_multises` are extracted
from the save effect for testability without a Shiny session.
"""
from __future__ import annotations

from datetime import datetime, timezone

from multises.data_structure import MultiSES, MultiSESMetadata


def _build_new_metadata(current_meta: MultiSESMetadata,
                        inputs: dict[str, str]) -> MultiSESMetadata:
    """Build a fresh MultiSESMetadata from raw input values.

    Applies empty-name fallback ("Untitled MultiSES"), strips whitespace
    from all fields, preserves created_at and schema_version from the
    current metadata, and stamps modified_at with the current UTC time.
    """
    name = (inputs.get("name") or "").strip() or "Untitled MultiSES"
    return MultiSESMetadata(
        name=name,
        description=(inputs.get("description") or "").strip(),
        da_site=(inputs.get("da_site") or "").strip(),
        river_basin=(inputs.get("river_basin") or "").strip(),
        regional_sea=(inputs.get("regional_sea") or "").strip(),
        focal_issue=(inputs.get("focal_issue") or "").strip(),
        temporal_scale=(inputs.get("temporal_scale") or "").strip(),
        spatial_scale=(inputs.get("spatial_scale") or "").strip(),
        created_at=current_meta.created_at,
        modified_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        schema_version=current_meta.schema_version,
    )


def _build_new_multises(current: MultiSES,
                        new_meta: MultiSESMetadata) -> MultiSES:
    """Build a fresh MultiSES with new metadata, preserving compartments and channels.

    Preserves the existing compartments and channels by reference (not deep-copy);
    the validation in MultiSES.__post_init__ re-runs, but since both lists are
    byte-for-byte the same as the previously-validated current state, it cannot fail.
    """
    return MultiSES(
        metadata=new_meta,
        compartments=current.compartments,
        channels=current.channels,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
micromamba run -n shiny pytest tests/test_project_setup_module.py -v
```
Expected: 2 PASSED.

- [ ] **Step 5: Run full suite — regression guard**

```powershell
micromamba run -n shiny pytest tests/ -q --ignore=tests/test_comparative_e2e.py --ignore=tests/test_cross_view_e2e.py
```
Expected: approximately 269 passed (267 baseline + 2 new). Load-bearing: no FAILED, no ERROR. (Excluding e2e for speed — e2e tests take ~30s each and aren't affected by this change.)

- [ ] **Step 6: Commit**

```powershell
git add multises_app/modules/project_setup.py tests/test_project_setup_module.py
git commit -m "feat(mosaicses): project_setup pure helpers (_build_new_metadata, _build_new_multises)"
```

---

## Phase C — Task 2: Module shell — UI + server stub + 3 module-shape tests

### Task 2: `project_setup_ui` + `project_setup_server` stub + 3 module-shape tests

**Files:**
- Modify: `multises_app/modules/project_setup.py` (add `@module.ui` + `@module.server`)
- Modify: `tests/test_project_setup_module.py` (append 3 module-shape tests)

- [ ] **Step 1: Append the 3 module-shape tests to `tests/test_project_setup_module.py`**

Append at the end of the file:

```python
def test_project_setup_module_importable():
    from multises_app.modules import project_setup  # noqa: F401


def test_project_setup_ui_renders_8_inputs():
    from multises_app.modules.project_setup import project_setup_ui
    html = str(project_setup_ui("test_id"))
    # 4 text/textarea + 4 select + 1 action button = 9 input-like ids
    for input_id in ("name", "description", "da_site", "focal_issue",
                     "river_basin", "regional_sea", "temporal_scale",
                     "spatial_scale", "save"):
        assert input_id in html, f"missing input: {input_id}"


def test_project_setup_server_is_module_decorated():
    """Verifies @module.server decoration was applied (proxy via wrapper signature).

    `@module.server` wraps the function so `inspect.signature(...)` shows
    `(id, *args, **kwargs)` — the wrapper's signature, NOT the wrapped
    function's. The decorator exposes no `__wrapped__` / `_fn` / `fn`
    accessor, so we can't introspect the inner `(input, output, session, *, state)`
    signature. Instead, assert the wrapper-shape — `params == ["id", "args", "kwargs"]`
    is a reliable proxy for "decorator was applied".

    Verified against chunk-4a `comparative_server` and `cross_view_server` —
    both expose this exact wrapper signature.
    """
    import inspect
    from multises_app.modules.project_setup import project_setup_server
    sig = inspect.signature(project_setup_server)
    params = list(sig.parameters.keys())
    assert params == ["id", "args", "kwargs"], (
        f"Expected @module.server wrapper signature [id, args, kwargs]; got {params}"
    )
```

- [ ] **Step 2: Run new tests to verify they fail**

```powershell
micromamba run -n shiny pytest tests/test_project_setup_module.py -v -k "module_importable or ui_renders or module_decorated"
```
Expected: 1 PASSED (`module_importable` — module exists from Task 1), 2 FAILED (`ui_renders_8_inputs` and `is_module_decorated` — symbols `project_setup_ui` and `project_setup_server` don't exist yet).

- [ ] **Step 3: Update imports in `project_setup.py`**

Replace the existing import block at the top of `multises_app/modules/project_setup.py` with:

```python
from __future__ import annotations

import logging
from datetime import datetime, timezone

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from sespy.constants import DA_SITES, SPATIAL_SCALES, TEMPORAL_SCALES
from sespy.regional_seas import get_regional_seas  # verified by Task 0 Probe 1 — function, not a constant

from multises.data_structure import MultiSES, MultiSESMetadata
from multises_app.state import MultiSESState

_log = logging.getLogger("multises")
_log.addHandler(logging.NullHandler())
```

The `logging` import + `_log` handle are used by Task 3's `_handle_save` try/except (R7 mitigation).

- [ ] **Step 4: Add choice-mapper helpers (after the 2 existing helpers)**

Append below `_build_new_multises`:

```python
def _da_site_choices() -> dict[str, str]:
    """Return {value: label} mapping for the DA site select.

    Fail-fast: iterates DA_SITES so adding a new site to constants forces
    a missing-label-key KeyError here rather than silently producing an
    incomplete dropdown.
    """
    return {"": "—", **{s: s for s in DA_SITES}}


def _regional_sea_choices() -> dict[str, str]:
    # get_regional_seas() returns dict[slug, dict[name, ecosystem_types, ...]].
    # Extract human-readable names; fall back to slug if name absent.
    return {"": "—", **{slug: data.get("name", slug) for slug, data in get_regional_seas().items()}}


def _temporal_choices() -> dict[str, str]:
    return {"": "—", **{v: v for v in TEMPORAL_SCALES}}


def _spatial_choices() -> dict[str, str]:
    return {"": "—", **{v: v for v in SPATIAL_SCALES}}
```

- [ ] **Step 5: Add `project_setup_ui` (append after the 4 choice helpers)**

```python
@module.ui
def project_setup_ui() -> ui.Tag:
    return ui.card(
        ui.card_header("Project Setup"),
        ui.div(
            ui.tags.p(
                "Project-level metadata. Edits apply on Save.",
                class_="text-muted",
            ),
            ui.layout_columns(
                # Left: Project Information
                ui.div(
                    ui.h4("Project Information"),
                    ui.input_text(
                        "name", "Project name",
                        placeholder="e.g. Curonian Lagoon — Nemunas basin",
                    ),
                    ui.input_text_area(
                        "description", "Description",
                        placeholder="Brief one-paragraph summary of the project",
                        rows=3,
                        width="100%",
                    ),
                    ui.input_select(
                        "da_site", "Demonstration area",
                        choices=_da_site_choices(),
                        selected="",
                    ),
                    ui.input_text_area(
                        "focal_issue", "Focal issue",
                        placeholder="The central management question or risk this project addresses",
                        rows=4,
                        width="100%",
                    ),
                    ui.input_action_button(
                        "save", "Save",
                        class_="btn btn-primary",
                        style="margin-top: 8px;",
                    ),
                ),
                # Right: System Scope
                ui.div(
                    ui.h4("System Scope"),
                    ui.input_text(
                        "river_basin", "River basin",
                        placeholder="e.g. Nemunas",
                    ),
                    ui.input_select(
                        "regional_sea", "Regional sea",
                        choices=_regional_sea_choices(),
                        selected="",
                    ),
                    ui.input_select(
                        "temporal_scale", "Temporal scale",
                        choices=_temporal_choices(),
                        selected="",
                    ),
                    ui.input_select(
                        "spatial_scale", "Spatial scale",
                        choices=_spatial_choices(),
                        selected="",
                    ),
                    ui.tags.hr(),
                    ui.output_ui("status"),
                ),
                col_widths=(6, 6),
            ),
            style="padding: 16px;",
        ),
        class_="mosaicses-project-setup-card",
        full_screen=True,
    )
```

- [ ] **Step 6: Add `project_setup_server` stub (append after `project_setup_ui`)**

```python
@module.server
def project_setup_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    state: MultiSESState,
) -> None:
    # Reactive plumbing filled in Task 3.
    pass
```

- [ ] **Step 7: Run new tests + module-shape tests to verify they pass**

```powershell
micromamba run -n shiny pytest tests/test_project_setup_module.py -v
```
Expected: all 5 tests PASS (2 helpers from Task 1 + 3 module-shape tests from this task).

- [ ] **Step 8: Run full suite — regression guard**

```powershell
micromamba run -n shiny pytest tests/ -q --ignore=tests/test_comparative_e2e.py --ignore=tests/test_cross_view_e2e.py
```
Expected: approximately 272 passed (267 baseline + 5 new). Load-bearing: no FAILED, no ERROR.

- [ ] **Step 9: Commit**

```powershell
git add multises_app/modules/project_setup.py tests/test_project_setup_module.py
git commit -m "feat(mosaicses): project_setup module shell (2-column form UI + server stub)"
```

---

## Phase D — Task 3: Server body — load + save + status

### Task 3: Fill `project_setup_server` with reactive plumbing

**Files:**
- Modify: `multises_app/modules/project_setup.py` (replace `pass` body in `project_setup_server`)

- [ ] **Step 1: Replace `project_setup_server`'s `pass` body with the 3 reactive elements**

Replace lines containing `# Reactive plumbing filled in Task 3.` and `pass` in `project_setup_server` with:

```python
    # Session-only "last saved" indicator: HH:MM:SS string set on the most
    # recent Save click in this session. None until first save.
    last_saved_at: reactive.Value[str | None] = reactive.value(None)

    @reactive.effect
    def _load_form_values() -> None:
        # Subscribes to state.active_multises ONLY — not to inputs, to avoid
        # clobbering keystrokes. Re-fires on external state change (file load,
        # switcher) and on initial mount.
        meta = state.active_multises.get().metadata
        ui.update_text("name", value=meta.name or "")
        ui.update_text_area("description", value=meta.description or "")
        ui.update_select("da_site", selected=meta.da_site or "")
        ui.update_text_area("focal_issue", value=meta.focal_issue or "")
        ui.update_text("river_basin", value=meta.river_basin or "")
        ui.update_select("regional_sea", selected=meta.regional_sea or "")
        ui.update_select("temporal_scale", selected=meta.temporal_scale or "")
        ui.update_select("spatial_scale", selected=meta.spatial_scale or "")

    @reactive.effect
    @reactive.event(input.save, ignore_init=True)
    def _handle_save() -> None:
        # Wrap in try/except so a downstream listener exception (e.g., chunk-3
        # isa_change listener raises) doesn't leave state.active_multises mutated
        # without the user seeing confirmation. See spec §6 + R7.
        try:
            current = state.active_multises.get()
            inputs = {
                "name": input.name(),
                "description": input.description(),
                "da_site": input.da_site(),
                "focal_issue": input.focal_issue(),
                "river_basin": input.river_basin(),
                "regional_sea": input.regional_sea(),
                "temporal_scale": input.temporal_scale(),
                "spatial_scale": input.spatial_scale(),
            }
            new_meta = _build_new_metadata(current.metadata, inputs)
            ms_new = _build_new_multises(current, new_meta)
            state.active_multises.set(ms_new)
            state.event_bus.emit_isa_change()
            last_saved_at.set(datetime.now().strftime("%H:%M:%S"))
            ui.notification_show("Saved ✓", duration=3, type="message")
        except Exception as e:  # noqa: BLE001 — surface any save-path failure
            _log.exception("project_setup: save failed")
            ui.notification_show(
                f"Save failed: {type(e).__name__}. See server log.",
                duration=6, type="error",
            )

    @output
    @render.ui
    def status():
        ms = state.active_multises.get()
        meta = ms.metadata
        saved_text = last_saved_at.get() or "—"
        # ARIA live region (R8 mitigation) — Shiny's notification_show is
        # SR-invisible, so wrap the status dl in role="status" + aria-live
        # so screen-reader users hear the "Saved this session" timestamp update.
        # _log.exception output goes to Shiny's stderr (no handlers configured
        # on 'multises' logger; root logger uses lastResort). "See server log"
        # in any error toast/smoke item = the terminal running `shiny run`.
        return ui.tags.div(
            ui.tags.dl(
                ui.tags.dt("Saved this session"), ui.tags.dd(saved_text),
                ui.tags.dt("Modified at"), ui.tags.dd(meta.modified_at or "—"),
                ui.tags.dt("Schema version"), ui.tags.dd(str(meta.schema_version)),
                ui.tags.dt("Compartments"), ui.tags.dd(str(len(ms.compartments))),
                ui.tags.dt("Channels"), ui.tags.dd(str(len(ms.channels))),
            ),
            role="status",
            **{"aria-live": "polite"},
        )
```

The keyword-only `*, state: MultiSESState` signature stays unchanged from the Task 2 stub.

- [ ] **Step 2: Verify the module still imports cleanly**

```powershell
micromamba run -n shiny python -c "from multises_app.modules import project_setup; print('OK:', project_setup.project_setup_server, project_setup.project_setup_ui)"
```
Expected: `OK: <function project_setup_server at ...> <function project_setup_ui at ...>`. If ImportError, check that `datetime` is imported at module top (it's imported by Task 1's helper block — should already be there) and that `reactive` / `render` are imported from `shiny` (added in Task 2 Step 3).

- [ ] **Step 3: Run all project_setup tests**

```powershell
micromamba run -n shiny pytest tests/test_project_setup_module.py -v
```
Expected: all 5 tests still PASS (no new tests added in this task — the server body's behavior is covered indirectly by the existing helper tests, since the server delegates to `_build_new_metadata` and `_build_new_multises`).

- [ ] **Step 4: Run full suite — regression guard**

```powershell
micromamba run -n shiny pytest tests/ -q --ignore=tests/test_comparative_e2e.py --ignore=tests/test_cross_view_e2e.py
```
Expected: approximately 272 passed. Load-bearing: no FAILED, no ERROR.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/project_setup.py
git commit -m "feat(mosaicses): project_setup server body (load + save + status)"
```

---

## Phase E — Task 4: Wire into app.py

### Task 4: Re-export from `__init__.py` + replace `"project"` nav-panel content + mount server

**Files:**
- Modify: `multises_app/modules/__init__.py` (+2 lines re-export)
- Modify: `app.py` (1 import + 1 nav-panel content + 1 server mount)

- [ ] **Step 1: Re-export from `multises_app/modules/__init__.py`**

Read `multises_app/modules/__init__.py` to see the existing structure (chunk-4a's Task 14 added `comparative_ui, comparative_server, cross_view_ui, cross_view_server` exports). Append:

```python
from .project_setup import project_setup_ui, project_setup_server
```

- [ ] **Step 2: Verify the new exports resolve**

```powershell
micromamba run -n shiny python -c "from multises_app.modules import project_setup_ui, project_setup_server; print('OK:', project_setup_ui, project_setup_server)"
```
Expected: prints two function references. If ImportError, check `multises_app/modules/__init__.py` syntax and that the new line is at module level (not inside a conditional).

- [ ] **Step 3: Modify `app.py` — add the import**

Find the existing line in `app.py` that reads:
```python
from multises_app.modules import comparative_ui, comparative_server, cross_view_ui, cross_view_server
```
(added by chunk-4a Task 14)

Replace it with:
```python
from multises_app.modules import (
    comparative_ui, comparative_server,
    cross_view_ui, cross_view_server,
    project_setup_ui, project_setup_server,
)
```

- [ ] **Step 4: Modify `app.py` — replace the `"project"` nav-panel content with `project_setup_ui("project")`**

Per Task 0 Probe 3, the existing `ui.nav_panel(... value="project")` body is currently empty / a placeholder. Replace its body with `project_setup_ui("project")`. The exact diff depends on probe results; expected shape:

```python
ui.nav_panel("Project", project_setup_ui("project"), value="project"),
```

(The first positional argument `"Project"` is the visible nav label; `value="project"` is the nav id used by NAV_TO_STEP.)

- [ ] **Step 5: Modify `app.py` — add `project_setup_server` mount call**

Find the existing server-mount block in `app.py`'s server function (chunk-4a Task 14 added `comparative_server("comparative", state=state)` and `cross_view_server("cross_view", state=state)`). Add a sibling line:

```python
project_setup_server("project", state=state)
```

Place it BEFORE the `comparative_server` mount (panel order convention: project → topology → compartments → comparative → cross_view).

- [ ] **Step 6: Verify the app imports cleanly**

```powershell
micromamba run -n shiny python -c "import app; print('PANELS:', len(app.PANELS)); print('panel ids:', [getattr(p, 'get_value', lambda: None)() for p in app.PANELS])"
```
Expected: prints `PANELS: 5` and the list `['project', 'topology', 'compartments', 'comparative', 'cross_view']`. The existing `test_app_module_loads` test (extended by chunk-4a Task 14) verifies this too — Step 7 runs it explicitly.

- [ ] **Step 7: Run the existing app-loads test**

```powershell
micromamba run -n shiny pytest tests/test_multises_app_imports.py -v
```
Expected: all tests PASS, including `test_app_module_loads` (asserts both `"comparative"` and `"cross_view"` are in PANELS — `"project"` was already there from chunk-3, so no test update needed).

- [ ] **Step 8: Run full suite — regression guard**

```powershell
micromamba run -n shiny pytest tests/ -q --ignore=tests/test_comparative_e2e.py --ignore=tests/test_cross_view_e2e.py
```
Expected: approximately 272 passed. Load-bearing: no FAILED, no ERROR.

- [ ] **Step 9: Commit**

```powershell
git add multises_app/modules/__init__.py app.py
git commit -m "feat(mosaicses): wire project_setup into app.py (replaces empty 'project' nav-panel)"
```

---

## Phase F — Task 5: Manual smoke checklist file + final pytest sweep

### Task 5: Create chunk-4b smoke checklist + run final full-suite sweep including e2e

**Files:**
- Create: `docs/2026-05-18-chunk4b-smoke-checklist.md`

- [ ] **Step 1: Final pytest sweep (full suite, including e2e)**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: approximately 274 passed (267 unit baseline + 5 new chunk-4b unit + 2 e2e). Load-bearing: no FAILED, no ERROR. **All must pass before proceeding.** If e2e flakes, re-run; if it fails consistently, investigate (chunk-4a Task 14 wiring change might not have broken anything, but verify).

- [ ] **Step 2: Write the smoke checklist file**

Create `docs/2026-05-18-chunk4b-smoke-checklist.md`:

```markdown
# Chunk 4b Smoke Checklist (2026-05-18)

Run before pushing to origin/main. Ship gate per spec §9 + saved feedback memory
`feedback_runtime_verify_before_shared_state.md`.

Launch:
\`\`\`powershell
micromamba run -n shiny shiny run --launch-browser app.py
\`\`\`

## App boot
- [ ] App boots without console errors.
- [ ] All 5 nav panels visible: Project / Topology / Compartments / Comparative / Cross-view.
- [ ] Default landing remains Topology (no behavioral change from chunk-4a).

## Project panel — form populates from seed
- [ ] Project nav-panel renders the form (two columns, "Project Information" left, "System Scope" right).
- [ ] Form is pre-populated with Curonian seed metadata for: `name`, `description`, `river_basin`, `focal_issue`, `temporal_scale`, `spatial_scale`.
- [ ] **Known cosmetic gap (R6 in spec)**: `da_site` and `regional_sea` show EMPTY on first load because the Curonian seed values (`'Curonian Lagoon'`, `'baltic_sea'`) aren't in the dropdown choice lists. Verify this matches expectation; do NOT flag as bug. Reconciliation is chunk-4c seed-data work.
- [ ] Status panel (bottom-right) shows: "Saved this session: —" (initial), "Modified at: —" (seed has empty modified_at) or "<ISO timestamp>", "Schema version: <integer>", "Compartments: 6", "Channels: ≥ 26".

## Project panel — Save flow
- [ ] Edit the `name` field to something new (e.g., append " (test)").
- [ ] Click Save.
- [ ] **Toast appears**: "Saved ✓" (auto-dismisses ~3s).
- [ ] Status panel updates: "Saved this session: HH:MM:SS" (current time) AND "Modified at" timestamp advances.
- [ ] The name field still shows the new value (didn't get clobbered by `_load_form_values`).

## Project panel — Empty name fallback
- [ ] Clear the `name` field (all whitespace).
- [ ] Click Save.
- [ ] Toast appears.
- [ ] After save, the name field shows "Untitled MultiSES" (the fallback fired during the `_load_form_values` round-trip).

## Project panel — Field round-trip
- [ ] Edit `river_basin` to "Nemunas (test)".
- [ ] Edit `temporal_scale` to a different value via dropdown.
- [ ] Click Save.
- [ ] Switch to Topology panel, then back to Project. Both edits survive.

## Reactivity invariant (chunk-3 carry-through)
- [ ] After saving in Project panel, switch to Compartments. Edit any compartment's CLD data. Switch back to Project — the modified_at timestamp in the status panel advanced (event_bus.isa_change wiring intact).

## AC7 — external state change re-populates form
- [ ] With Project panel visible, programmatically replace `state.active_multises` (proxy: use Compartments panel to add/delete a compartment, which mutates the underlying MultiSES). Verify the form's `_load_form_values` re-fires and re-populates fields from the new metadata. (Spec §9 AC7.)

## Error-path smoke (R7 + R8 mitigation)
Concrete procedure for triggering the error path (no in-app toggle exists; this is a one-off monkeypatch):
1. Stop the running `shiny run` server.
2. Edit `multises_app/state.py` temporarily — find `event_bus=create_event_bus()` in `create_multises_state` and wrap it: `event_bus=_BrokenEventBus()` where `_BrokenEventBus` is a temp class with `def emit_isa_change(self): raise RuntimeError("smoke-test")`.
3. Restart `shiny run`. Open the Project panel. Edit `name`. Click Save.
4. Verify (visual): error toast "Save failed: RuntimeError. See server log." appears, red type.
5. Verify (terminal where `shiny run` is launched): a Python traceback with "RuntimeError: smoke-test" is printed via `_log.exception`.
6. Verify (status panel): "Saved this session" does NOT update (because the try/except interrupted before `last_saved_at.set(...)`). Correct partial-state behavior.
7. Revert step 2's edit. Restart `shiny run`. Confirm Save now succeeds normally.

If steps 4-6 all pass: R7 and R8 mitigations confirmed end-to-end.

## Persistence (file-level, not enforced by chunk-4b but spot-check)
- [ ] Save/reload cycle preserves metadata (chunks 1-3 persistence tests pass via pytest).

## Accessibility spot-check
- [ ] Tab key navigates through Project Information fields in order: name → description → da_site → focal_issue → Save.
- [ ] Tab continues to System Scope: river_basin → regional_sea → temporal_scale → spatial_scale.
- [ ] Save button has visible focus ring when tabbed-to.
- [ ] Each input has a visible label.
- [ ] **Screen-reader save announcement (R8)**: open the app with NVDA, JAWS, or Windows Narrator. Edit `name`, click Save. Verify the "Saved this session" timestamp update is announced (via the `role="status" aria-live="polite"` wrapper on the status panel). The Shiny toast itself is NOT announced (known limitation, chunk-4c).
- [ ] **Heading outline**: open browser devtools "Accessibility tree" or run a HeadingsMap-style extension. Verify there is no skipped heading level between the app shell and the form's `h4` column headings. If there's a gap (e.g., shell is `h1` → card_header is plain div → h4 inside columns), the card_header should be upgraded to `ui.card_header(ui.h3("Project Setup"))`.
- [ ] **Windows High Contrast mode**: re-test the success toast (visible) and error toast (visible) at the OS level. Confirm color contrast holds.
- [ ] **200% browser zoom**: form remains usable, no horizontal scroll, columns reflow to single-column stacking.
```

- [ ] **Step 3: Commit**

```powershell
git add docs/2026-05-18-chunk4b-smoke-checklist.md
git commit -m "docs(mosaicses): chunk-4b manual smoke checklist"
```

---

## Phase G — Task 6: Ship gate — push pending manual smoke pass

### Task 6: Push to origin after smoke

- [ ] **Step 1: Verify branch state ahead of origin/main**

```powershell
git status --short --branch
git log --oneline origin/main..HEAD
```
Expected: clean tree (only `.gitignore` M, pre-existing); 6 commits ahead of `origin/main` (Task 0 probe log + 5 task commits).

- [ ] **Step 2: Final pytest sweep**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: all passing.

- [ ] **Step 3: HUMAN GATE — run smoke checklist**

Run `docs/2026-05-18-chunk4b-smoke-checklist.md` in a real browser via:
```powershell
micromamba run -n shiny shiny run --launch-browser app.py
```
**Do not push until every item is ticked.** Per the saved feedback memory `feedback_runtime_verify_before_shared_state.md`: shared-state actions (push) gate on real-runtime verification, not just unit tests. The load-bearing items here are the **Save flow** and **Empty name fallback** — verify them deliberately.

- [ ] **Step 4: On smoke pass — push to origin**

```powershell
git push origin main
```
Expected: fast-forward push, no force, no `--no-verify`.

- [ ] **Step 5: Chunk 4b shipped**

Optionally tag the shipped state:
```powershell
git tag chunk-4b-shipped HEAD
git push origin chunk-4b-shipped
```

Update the memory file `chunk3_status.md` to record:
- New HEAD on `origin/main`.
- Remaining chunks 4c (polish: CSS/JS extraction, recent_projects, LOAC layout, bridge-chart fix, CHANNEL_TYPE_RENDER, seed authoring, pyvis tabular fallbacks) and 4d (test/CI/ship: external-API contract tests, 2 remaining e2e, CI integration, v1 ship checklist).
- Invoke `superpowers:brainstorming` for chunk 4c when ready.

---

## Self-review

**Spec coverage:**

| Spec section | Plan task |
|---|---|
| §1.1 in-scope (single module, fills `"project"` slot, mirror of pims_project) | Tasks 1 + 2 + 3 + 4 |
| §1.2 deferrals | Documented at top + Task 4 only replaces existing slot (no panel additions) |
| §2 decisions table (13 rows) | Each honored: reference mirror (Task 2 + 3), explicit Save (Task 3), 2-column (Task 2 UI), grouping (Task 2 UI), river_basin free-text (Task 2 UI), no i18n (no `t()` in Task 2 strings), empty-name fallback (Task 1 helper), emit_isa_change (Task 3 server), no Reset button (Task 2 UI omits it), status content (Task 3 status render), 5 tests (Tasks 1+2 add them), MultiSES reconstruction strategy (Task 1 helper) |
| §3 architecture | Tasks 1 + 2 + 4 |
| §4 UI design | Task 2 Step 5 (verbatim) |
| §5 data flow | Task 3 (Step 1 verbatim) |
| §6 error handling | Task 1 (empty-name fallback test), Task 3 (server uses helpers) |
| §7 risks + mitigations | R1 + R2 + R3 accepted-as-designed (no code change). R4 fixed pre-execution (Round 1 review). R5 (re-entry loop) accepted; chunk-3 listeners read-only. R6 (seed/constants drift) acknowledged in Task 0 Probe 4 + smoke checklist + spec §6. R7 (try/except for partial state) implemented in Task 3 `_handle_save`. R8 (SR-invisible toast) mitigated via `role="status" aria-live="polite"` wrapper in Task 3 `status` render. R9 (tautological test) replaced in Task 2 Step 1 with wrapper-shape signature check. |
| §8 testing (5 tests) | Tasks 1 (tests 4 + 5) + 2 (tests 1 + 2 + 3) |
| §9 acceptance criteria | Task 5 smoke checklist |
| §10 hand-off | Plan complete + Task 6 ship gate |

All 13 decisions in §2 have explicit plan tasks. All 5 tests in §8 are written verbatim across Tasks 1 and 2. No spec section is unmapped.

**Placeholder scan:** No "TBD" / "TODO" / "fill in later" / "implement later" / "similar to Task N" / "add appropriate error handling" / vague "write tests for the above". Two probe-driven adjustments are flagged explicitly with concrete adjustment instructions (Task 2 Step 3 + Step 4 if Probe 1 finds an unexpected shape) — not placeholders, but documented decision points.

**Type consistency:**
- `_build_new_metadata(current_meta: MultiSESMetadata, inputs: dict[str, str]) -> MultiSESMetadata` — introduced Task 1, consumed Task 3. Same name + signature.
- `_build_new_multises(current: MultiSES, new_meta: MultiSESMetadata) -> MultiSES` — introduced Task 1, consumed Task 3. Same.
- `last_saved_at: reactive.Value[str | None]` — introduced Task 3 server body, consumed by `status` render in same task.
- `state: MultiSESState` keyword-only param — same signature in Task 2 stub and Task 3 body.
- UI input ids (`name`, `description`, `da_site`, `focal_issue`, `river_basin`, `regional_sea`, `temporal_scale`, `spatial_scale`, `save`) — defined Task 2, referenced Task 3 via `input.<id>()`, asserted Task 2 test 2 via `assert input_id in html`. All 9 ids consistent.
- Output id `status` — defined Task 2 UI as `ui.output_ui("status")`, server-side `@output @render.ui def status()` defined Task 3.

**Gap check:** §7 R1-R3 accepted-as-designed (no code change). R4 fixed during Round-1 review (REGIONAL_SEAS → get_regional_seas). R5-R9 each mapped to a concrete plan element (Probe 4 + smoke / try-except / ARIA wrapper / wrapper-shape test). ✅

---

## Execution handoff

**Plan complete and saved to** `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESPy\docs\superpowers\plans\2026-05-18-mosaicses-chunk4b-project-setup.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task with two-stage review (spec compliance → code quality). Same workflow that shipped chunk 4a successfully. Per [[feedback_multi_round_agent_review]], the pattern caught two latent bugs in the chunk-4a plan during execution.

**2. Inline Execution** — `superpowers:executing-plans` with batch checkpoints. Faster on a small 6-task plan but loses the independent-verification benefit.

Which approach?
