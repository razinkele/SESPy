# MosaicSES Chunk 4d — File Flows + Topology A11y + Bridge-Chart Fix — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** Add New/Open/Save file flows + a screen-reader tabular fallback for the topology network, and fix the bridge-chart's conflated y-axis — in the MosaicSES app (`..\MosaicSES\` repo).

**Architecture:** Pure helpers + Shiny wiring; reuses the existing `multises` persistence (`to_json`/`from_json`) and `MultiSESState`. No `multises/` library change, no `app.py` change. Code lands in the **MosaicSES repo**; this plan + its spec live in SESPy's `docs/superpowers/`.

**Spec:** `docs/superpowers/specs/2026-06-08-mosaicses-chunk4d-file-flows-a11y-design.md` (rev. 2) — has the full code blocks; this plan sequences them TDD-style.

**Plan rev. 2 (from deep-review):** (a) `EventBus` has **no subscribe API** — it's reactive counters; Task-1 asserts `isa_change.get()` **increment** under `reactive.isolate()` (the repo's required read pattern). (b) The e2e fixture exposes only `mosaicses_app_url` (no page) — Task 5 **creates its own sync Playwright page** with `accept_downloads=True`. (c) Nested `@render.*` functions can't be unit-tested, so Task 3 extracts a pure `_network_table_ui(ms)` and Task 4 a pure `_bridge_chart_figure(ms) -> Figure` (the renders become thin wrappers) — both directly testable. (d) Exact ids: nav `#sespy_nav_project`, `#project-name`, `#project-save`, seed name `"Curonian Lagoon LOAC seed"`. (e) keep the existing `MultiSESMetadata` import in `project_setup.py`. Verified: seed max betweenness 0.375 (fix is meaningful), harness is sync Playwright.

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

- [ ] **Step 1: Failing test** — in the state test module, build a 2nd MultiSES (e.g. a renamed `seed_curonian()`), construct state via `create_multises_state(seed_curonian())`, call `state.load_multises(other_ms)`, and assert under the repo's required `reactive.isolate()` read pattern (`EventBus` has **no** subscribe API — assert the `isa_change` counter increments):
  ```python
  import multises_app.state as state_mod
  from shiny import reactive
  ...
  s = state_mod.create_multises_state(seed_curonian())
  with reactive.isolate():
      before = s.event_bus.isa_change.get()
  s.load_multises(other_ms)
  with reactive.isolate():
      assert s.active_multises.get() is other_ms
      assert s.active_compartment_id.get() == state_mod.initial_active_compartment_id(other_ms)
      assert s.active_compartment_project.get() is state_mod._initial_active_project(other_ms)
      assert s.event_bus.isa_change.get() == before + 1
  ```
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
- [ ] **Step 3: Implement** — add the "Project file" section to `project_setup_ui` (3 controls, spec §3) and the 3 server handlers (`download_multises` `@render.download`; `_open` `@reactive.event(input.open_multises)` with the **broad `except Exception` + `_log.exception` + toast**; `_new` resetting to `seed_curonian()`), all per spec §3. Extend the existing import (`project_setup.py:19` already imports `MultiSES, MultiSESMetadata` — **keep both**, `_build_new_metadata` needs `MultiSESMetadata`): `from multises import MultiSES, MultiSESMetadata, seed_curonian`. Add `from pathlib import Path`, `from datetime import datetime`, `import logging` + `_log = logging.getLogger("multises")`. Route Open/New through `state.load_multises(...)`.
- [ ] **Step 4: Run; verify pass** + `flake8` + `micromamba run -n shiny python -c "import app; print('app ok')"` (in MosaicSES) to confirm the panel still imports.
- [ ] **Step 5: Commit** — `feat(mosaicses): New/Open/Save MultiSES file flows in Project panel (chunk-4d)`

---

## Task 3: Topology screen-reader tabular fallback (`topology.py`)

**Files:** `multises_app/modules/topology.py`; `tests/test_topology_module.py`

- [ ] **Step 1: Failing tests** — extend `test_topology_module.py`: (a) test the pure `_channel_summary_rows(ms)` helper — for `seed_curonian()` one dict per channel with keys `source/target/type/polarity/strength/delay`; empty-channel MultiSES → `[]`; a channel with `_unknown_channel_type_original` surfaces in `type`. (b) test the pure `_network_table_ui(ms)` helper — `str(_network_table_ui(ms).tagify())` contains `<table>`, the "Compartments"/"Channels" captions, a row per compartment + per channel, and a "No channels" cell for an empty-channel MultiSES. (c) assert `str(topology_ui("topology").tagify())` contains `network_table` and `<details>`/`summary`.
- [ ] **Step 2: Run; verify fail** (no helpers / no output).
- [ ] **Step 3: Implement** — add module-level `_channel_summary_rows(ms)` AND `_network_table_ui(ms)` (the latter builds the two `ui.tags.table`s incl. the "No channels" colspan row — spec §4); add `ui.tags.details(ui.tags.summary(...), ui.output_ui("network_table"))` in `topology_ui` adjacent to the network output; the `@render.ui def network_table(): return _network_table_ui(state.active_multises.get())` is a thin wrapper so the logic is unit-tested via the pure helper.
- [ ] **Step 4: Run; verify pass** + `flake8` + app-import check.
- [ ] **Step 5: Commit** — `feat(mosaicses): topology screen-reader tabular fallback (chunk-4d)`

---

## Task 4: Bridge-chart axis fix (`cross_view.py`)

**Files:** `multises_app/modules/cross_view.py`; `tests/test_cross_view_module.py`

- [ ] **Step 1: Failing test** — extend `test_cross_view_module.py`: test a NEW pure helper `_bridge_chart_figure(ms) -> matplotlib.figure.Figure` (extracted from `bridge_chart`). For `seed_curonian()`: `fig = _bridge_chart_figure(ms)`; assert `len(fig.axes) == 2` (primary + twinx); the 2nd axis ylabel mentions "betweenness" and its ylim covers 0–1; the primary axis ylabel is "degree (count)". (Fails before the fix — currently a single axis.)
- [ ] **Step 2: Run; verify fail** (helper doesn't exist / single axis).
- [ ] **Step 3: Implement** — extract `_bridge_chart_figure(ms)` containing the plotting logic with the `twinx` fix (spec §5: degrees on `ax`, betweenness on `ax2 = ax.twinx()`, combined legend, `ax2.set_ylim(0, max(1.0, ...))`, `fig.tight_layout()`); `bridge_chart()` `@render.image` becomes thin plumbing — `fig = _bridge_chart_figure(ms)`, savefig to the temp PNG, return the image dict with `_bridge_chart_alt_text(ms)` unchanged.
- [ ] **Step 4: Run; verify pass** + `flake8`. Optionally launch the app and eyeball the Cross-view "Bridge metrics" card (betweenness bars now visible on the right axis).
- [ ] **Step 5: Commit** — `fix(mosaicses): bridge-chart betweenness on secondary y-axis (chunk-4d)`

---

## Task 5: e2e — file flows (`tests/test_project_setup_e2e.py`)

**Files:** `tests/test_project_setup_e2e.py` (new)

- [ ] **Step 1: Develop against the live app** — `shiny run app.py --port 8000`; with a sync Playwright probe, confirm the selectors: nav `#sespy_nav_project`, name `#project-name`, metadata Save `#project-save`, plus the new `#project-download_multises` / `#project-open_multises` / `#project-new_multises`. Seed project name is `"Curonian Lagoon LOAC seed"`.
- [ ] **Step 2: Write the test** — the `mosaicses_app_url` fixture gives only a URL (no page); the test **creates its own sync Playwright page with a download-enabled context** (matching `test_comparative_e2e.py`'s sync style):
  ```python
  from playwright.sync_api import sync_playwright, expect

  def test_project_file_flows_e2e(mosaicses_app_url, tmp_path):
      with sync_playwright() as p:
          browser = p.chromium.launch(headless=True)
          context = browser.new_context(accept_downloads=True)
          page = context.new_page()
          page.goto(mosaicses_app_url, wait_until="networkidle")
          page.click("#sespy_nav_project")
          # New reset (mutate first so it can't false-pass):
          page.fill("#project-name", "ZZZ-temp")
          page.click("#project-save")
          page.click("#project-new_multises")
          expect(page.locator("#project-name")).to_have_value("Curonian Lagoon LOAC seed")
          # Save download:
          with page.expect_download() as dl:
              page.click("#project-download_multises")
          assert dl.value.suggested_filename.endswith(".json")
          # Open a renamed seed:
          from multises import seed_curonian
          ms = seed_curonian()
          # (rename via MultiSESMetadata replace or a hand-edited JSON; write to tmp_path)
          json_path = tmp_path / "renamed.json"
          json_path.write_text(ms.to_json(), encoding="utf-8")  # adjust to set a distinct name
          page.set_input_files("#project-open_multises", str(json_path))
          # assert the name field updates to the opened project's name
          browser.close()
  ```
- [ ] **Step 3: Run** — `micromamba run -n shiny pytest tests/test_project_setup_e2e.py -q` → green. Stop the app.
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
