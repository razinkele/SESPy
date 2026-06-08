# MosaicSES Chunk 4d — File Flows + Topology A11y + Bridge-Chart Fix — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** Add New/Open/Save file flows + a screen-reader tabular fallback for the topology network, and fix the bridge-chart's conflated y-axis — in the MosaicSES app (`..\MosaicSES\` repo).

**Architecture:** Pure helpers + Shiny wiring; reuses the existing `multises` persistence (`to_json`/`from_json`) and `MultiSESState`. No `multises/` library change, no `app.py` change. Code lands in the **MosaicSES repo**; this plan + its spec live in SESPy's `docs/superpowers/`.

**Spec:** `docs/superpowers/specs/2026-06-08-mosaicses-chunk4d-file-flows-a11y-design.md` (rev. 2) — has the full code blocks; this plan sequences them TDD-style.

**Repo + commands (verified 2026-06-08):**
- Work in `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES`.
- Tests: `micromamba run -n shiny pytest tests/ -q` (274 unit + 2 e2e currently green). Exclude e2e during fast iteration: `--ignore=tests/test_comparative_e2e.py --ignore=tests/test_cross_view_e2e.py`.
- App: `micromamba run -n shiny shiny run app.py --port 8000`.

**Conventions verified against live MosaicSES code:**
- `MultiSESState` (`multises_app/state.py:37-43`): `active_multises`, `active_compartment_id`, `active_compartment_project`, `event_bus`; helpers `initial_active_compartment_id(ms)` (:46) + `_initial_active_project(ms)` (:62); `event_bus.emit_isa_change()`.
- `multises/__init__.py` re-exports `MultiSES`, `MultiSESIntegrityError`, `seed_curonian`. `MultiSES.to_json(indent=2)` (`data_structure.py:499`), `from_json(text) -> LoadResult` (:688), `LoadResult.multises`/`.report`, `LoadReport.warnings` (tuple).
- `Channel` fields: `id`, `source`, `target`, `channel_type`, `polarity`, `strength`, `confidence`, `delay`, `description`, `_unknown_channel_type_original` (`data_structure.py:240`). `topology.py:129` already uses `ch._unknown_channel_type_original or ch.channel_type` and `ch.source`/`ch.target`.
- `project_setup.py`: `project_setup_ui` is `@module.ui`, `project_setup_server(input, output, session, *, state)` is `@module.server`; `reactive`/`render`/`ui` imported; existing `_handle_save` uses `ui.notification_show`. Form inputs: `name`/`description`/`da_site`/`focal_issue`/`save` + scope fields.
- `topology.py`: `output_pyvis_network("network")`; `_compartment_summary_rows(ms)` → keys `id`/`label`/`archetype`/`element_count`/`is_focal_tw`; `ms.channels` iterable.
- `cross_view.py`: `bridge_chart()` `@render.image` (`:342`), grouped bars in_deg/out_deg/between (`:346-354`), shared y-axis (the bug); `_bridge_chart_alt_text` already covers all three series.
- Tests: module tests are unit-style; e2e use `shiny.pytest.create_app_fixture` (sync Playwright) via the `mosaicses_app_url` fixture (`tests/conftest.py`).

---

## Task 1: `MultiSESState.load_multises`

**Files:** `multises_app/state.py`; `tests/test_state_bridge.py` (or `tests/test_project_setup_module.py`)

- [ ] **Step 1: Failing test** — in the state test module, build a MultiSES with ≥2 compartments (use `seed_curonian()` or a fixture), construct state via `create_multises_state`, then call `state.load_multises(other_ms)` and assert: `state.active_multises.get() is other_ms`; `state.active_compartment_id.get() == initial_active_compartment_id(other_ms)`; `state.active_compartment_project.get() == _initial_active_project(other_ms)`. Also assert an `isa_change` listener fired (subscribe a flag via `event_bus`). Reactive reads must run inside `reactive.isolate()` or a test reactive context per the repo's existing state tests — match their pattern.
- [ ] **Step 2: Run; verify fail** (no `load_multises`).
- [ ] **Step 3: Implement** — add the method to `MultiSESState` exactly as spec §2:
  ```python
  def load_multises(self, ms: MultiSES) -> None:
      self.active_multises.set(ms)
      self.active_compartment_id.set(initial_active_compartment_id(ms))
      self.active_compartment_project.set(_initial_active_project(ms))
      self.event_bus.emit_isa_change()
  ```
- [ ] **Step 4: Run; verify pass** + `flake8 multises_app/state.py` (match repo's lint config).
- [ ] **Step 5: Commit** — `feat(mosaicses): MultiSESState.load_multises atomic project swap (chunk-4d)`

---

## Task 2: New / Open / Save file flows (`project_setup.py`)

**Files:** `multises_app/modules/project_setup.py`; `tests/test_project_setup_module.py`

- [ ] **Step 1: Failing tests** — extend `test_project_setup_module.py`: render `project_setup_ui("project")` and assert its HTML/str contains `download_multises`, `open_multises`, `new_multises` (the three control ids). (Behavior of Open/New is covered by the Task-1 `load_multises` test + the Task-5 e2e; module tests assert UI presence per the repo's existing module-test style.)
- [ ] **Step 2: Run; verify fail.**
- [ ] **Step 3: Implement** — add the "Project file" section to `project_setup_ui` (3 controls, spec §3) and the 3 server handlers (`download_multises` `@render.download`; `_open` `@reactive.event(input.open_multises)` with the **broad `except Exception` + `_log.exception` + toast**; `_new` resetting to `seed_curonian()`), all per spec §3. Extend imports: `from multises import MultiSES, seed_curonian`, `from pathlib import Path`, `from datetime import datetime`, `import logging` + `_log = logging.getLogger("multises")`. Route Open/New through `state.load_multises(...)`.
- [ ] **Step 4: Run; verify pass** + `flake8` + `micromamba run -n shiny python -c "import app; print('app ok')"` (in MosaicSES) to confirm the panel still imports.
- [ ] **Step 5: Commit** — `feat(mosaicses): New/Open/Save MultiSES file flows in Project panel (chunk-4d)`

---

## Task 3: Topology screen-reader tabular fallback (`topology.py`)

**Files:** `multises_app/modules/topology.py`; `tests/test_topology_module.py`

- [ ] **Step 1: Failing tests** — extend `test_topology_module.py`: (a) test the pure `_channel_summary_rows(ms)` helper — for `seed_curonian()` it returns one dict per channel with keys `source/target/type/polarity/strength/delay`; an empty-channel MultiSES → `[]`; a channel with `_unknown_channel_type_original` set surfaces that value in `type`. (b) assert `topology_ui("topology")` HTML contains `network_table` and a `<details>`/`summary`.
- [ ] **Step 2: Run; verify fail** (no helper / no output).
- [ ] **Step 3: Implement** — add module-level `_channel_summary_rows(ms)` (spec §4), the `ui.tags.details(ui.tags.summary(...), ui.output_ui("network_table"))` in `topology_ui` adjacent to the network output, and the `@render.ui def network_table()` building the two semantic tables (with the "No channels" colspan row), per spec §4.
- [ ] **Step 4: Run; verify pass** + `flake8` + app-import check.
- [ ] **Step 5: Commit** — `feat(mosaicses): topology screen-reader tabular fallback (chunk-4d)`

---

## Task 4: Bridge-chart axis fix (`cross_view.py`)

**Files:** `multises_app/modules/cross_view.py`; `tests/test_cross_view_module.py`

- [ ] **Step 1: Failing/regression test** — extend `test_cross_view_module.py`: a test that exercises `bridge_chart` for the seeded project and asserts it returns a valid image dict (`{"src": <path>, ...}`) without raising, and the PNG file exists + is non-empty (magic bytes `\x89PNG`). (The twinx is a render detail; assert no-raise + valid PNG. Optionally assert the underlying `inter_compartment_metrics` betweenness values are ≤ 1.0 to document the scale rationale.)
- [ ] **Step 2: Run** — current code already renders, so this test should PASS pre-change (it's a guard that the fix doesn't break rendering). If the test module can't easily invoke the nested render, assert on `inter_compartment_metrics` scale instead.
- [ ] **Step 3: Implement** — apply the `twinx` secondary-axis fix in `bridge_chart()` per spec §5 (degrees on `ax`, betweenness on `ax2 = ax.twinx()`, combined legend, `ax2.set_ylim(0, max(1.0, ...))`, `fig.tight_layout()`). Keep the temp-file/`render.image` plumbing + `_bridge_chart_alt_text` unchanged.
- [ ] **Step 4: Run; verify pass** + `flake8`. Optionally launch the app and eyeball the Cross-view "Bridge metrics" card (betweenness bars now visible on the right axis).
- [ ] **Step 5: Commit** — `fix(mosaicses): bridge-chart betweenness on secondary y-axis (chunk-4d)`

---

## Task 5: e2e — file flows (`tests/test_project_setup_e2e.py`)

**Files:** `tests/test_project_setup_e2e.py` (new)

- [ ] **Step 1: Develop against the live app** — `shiny run app.py --port 8000`; with a Playwright probe (sync, matching the repo's e2e style), nav to the Project panel, exercise New/Save/Open, find the module-namespaced selectors (`#project-download_multises`, `#project-open_multises`, `#project-new_multises`) and the name-field selector.
- [ ] **Step 2: Write the test** (via `mosaicses_app_url` + `create_app_fixture`, sync Playwright like `test_comparative_e2e.py`):
  - **New reset (no false-pass):** first edit the name field to a sentinel (e.g. `"ZZZ-temp"`) and click the metadata **Save** so state changes; then click `#project-new_multises` and assert the name field returns to the Curonian seed name.
  - **Save download:** `with page.expect_download() as dl: page.click("#project-download_multises")`; assert `dl.value.suggested_filename.endswith(".json")`.
  - **Open:** write a small valid MultiSES JSON to a temp file (`MultiSES.to_json()` of a renamed seed), `page.set_input_files("#project-open_multises", tmp)`, assert the name field updates to that file's project name.
- [ ] **Step 3: Run** — `micromamba run -n shiny pytest tests/test_project_setup_e2e.py -q` → green (context already has `accept_downloads=True`? confirm the fixture; if not, the test creates its own context or the harness supports downloads — verify in Step 1). Stop the app.
- [ ] **Step 4: Commit** — `test(mosaicses): e2e New/Save/Open file flows (chunk-4d)`

---

## Final verification
- [ ] `micromamba run -n shiny pytest tests/ -q` (full MosaicSES suite) → green (was 276; chunk 4d adds ~10–14 tests).
- [ ] Manual smoke: launch app, exercise New/Open/Save on Project, the `<details>` tabular view on Topology, and the Cross-view bridge chart.
- [ ] Commit any smoke-checklist doc under MosaicSES `docs/` per the repo's chunk convention (optional).
- [ ] Update this plan's checkboxes + the SESPy spec status line on completion.

## Sequencing notes
- TDD order: state helper (1) → file flows (2) → a11y (3) → bridge fix (4, independent) → e2e (5). Tasks 1–4 are independently committable; Task 4 is fully independent of 1–3.
- All code commits land in the **MosaicSES repo** (`..\MosaicSES\`), not SESPy. The MosaicSES repo is currently 9 commits ahead of its origin (unpushed) — chunk-4d commits add to that; pushing is a separate user decision.
