# MosaicSES Chunk 4d — File Flows + Topology Accessibility — Design

Date: 2026-06-08
Status: **Draft** — design phase, not yet implemented.

**Sub-project context:** MosaicSES (separate repo `..\MosaicSES\`, package `multises` +
app `multises_app`; depends on SESPy via path-dep). Chunks 1–4c are shipped (276 tests
green through `chunk-4c-ui`). Chunk 4d picks up two of the most-deferred, user-facing
gaps from the chunk-4b/4c "out of scope" tables:
1. **Project file flows** — New / Open / Save of a `MultiSES` (the `recent_projects.py`
   deferral from chunk 4b). Today the Project panel's only button commits *metadata
   edits to in-memory state*; there is **no way to persist a MultiSES to a file or load
   one back** from the UI.
2. **Topology screen-reader accessibility** — a `<details>`-wrapped tabular mirror of the
   pyvis network (compartments **and** channels), the carried-forward "pyvis tabular
   a11y fallback" deferral.

**Scope decisions made during investigation (2026-06-08):**
- **Bridge-chart axis fix — DROPPED.** Investigation found **no bridge chart exists** in
  `comparative.py` (renders are `vital_signs`/`leverage`/`gap_*`/`heatmap`/meta-graph).
  The bridge chart was *defined* in the chunk-4a design (3-bar group:
  channel_in_degree / out_degree / betweenness) but **never built**, so there is no axis
  to fix. Building the bridge chart is a separate analytics increment; the "axis fix"
  deferral is moot and is removed from chunk-4d scope.
- **Recent-projects list — DEFERRED to chunk 4e.** SESPy's recent registry
  (`~/.sespy/recent.json`) keys on **absolute filesystem paths**, which doesn't map to a
  web Save=download / Open=upload model (the server never learns the user's real path).
  A session/registry design for recent MultiSES files is its own increment; chunk 4d
  ships New/Open/Save (the core, immediately-useful flows).

## 1. Goal & scope

### 1.1 In scope
- **File flows** in the Project panel (`multises_app/modules/project_setup.py`):
  - **Save** — a `@render.download` button streaming `active_multises.to_json()` bytes.
  - **Open** — a `ui.input_file(accept=[".json"])` that loads a `MultiSES` from the
    uploaded JSON via `MultiSES.from_json`, surfacing `LoadReport` warnings and
    `MultiSESIntegrityError` as toasts.
  - **New** — a button resetting to the Curonian seed (`seed_curonian()`), the app's
    default project.
  - A shared **`MultiSESState.load_multises(ms)`** method (new, in `state.py`) that
    atomically resets `active_multises` + `active_compartment_id` +
    `active_compartment_project` and emits `isa_change` — so Open/New can't leave a stale
    compartment selection pointing at the previous project.
- **Topology a11y fallback** in `multises_app/modules/topology.py`:
  - A `<details><summary>` block (collapsed) holding an **accessible tabular mirror** of
    the network: a **compartments** table (`_compartment_summary_rows`) + a **channels**
    table (source → target, type, polarity, strength, delay). Gives screen-reader users a
    navigable equivalent of the pyvis canvas (WCAG 1.1.1 non-text content).
- Unit module tests + e2e coverage.

### 1.2 Out of scope
- Bridge chart + its axis fix (see above — never built; separate increment).
- Recent-projects registry/list (chunk 4e).
- Autosave (SESPy has it; MosaicSES hasn't adopted it — separate).
- CSS/JS extraction, theme/skin, Compartments/Project-Setup redesign (chunk-4c §9).
- Any `multises` library data-model/persistence change — `to_json`/`from_json`/`save`/
  `load` already exist and are reused unchanged.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Save mechanism | `@render.download` → `active_multises.get().to_json().encode("utf-8")` | Mirrors SESPy `project_io.py` Save; `MultiSES.to_json(indent=2)` exists (`data_structure.py:499`). Browser download — no server path needed. |
| Open mechanism | `ui.input_file(accept=[".json"])` → read temp file text → `MultiSES.from_json(text)` → `LoadResult` | Mirrors SESPy Load. `from_json` returns `LoadResult(.multises, .report)`; hard errors raise `MultiSESIntegrityError`, soft issues land in `report.warnings`. |
| New mechanism | reset to `seed_curonian()` | The app already seeds Curonian on startup (`app.py:124`); "New" = back to the known-good sample, matching SESPy's "New = seed". |
| State reset | new `MultiSESState.load_multises(ms)` resets all 3 reactive values via the existing `initial_active_compartment_id` / `_initial_active_project` helpers + `event_bus.emit_isa_change()` | A bare `active_multises.set(ms)` would leave `active_compartment_id`/`active_compartment_project` pointing at the **old** project's compartments — a stale-selection bug. Centralizing the reset prevents it. |
| Error/warn UX | `ui.notification_show` toasts: success ("Loaded ✓" + warning count if any), `MultiSESIntegrityError` → warning toast, no state change | Matches SESPy `project_io.py` + MosaicSES `project_setup.py` `_handle_save` toast convention. |
| A11y fallback shape | `ui.tags.details(ui.tags.summary(...), <compartments table>, <channels table>)`, collapsed by default, placed adjacent to the `output_pyvis_network("network")` | A `<details>` keeps the sighted layout uncluttered while giving AT users a real text equivalent. Reuses `_compartment_summary_rows`; adds a channels-row helper. |
| Tables | `@render.data_frame` (`render.DataGrid`) for both, OR static HTML `ui.tags.table` | DataGrid is already used across MosaicSES; but for a pure a11y text-equivalent a semantic `<table>` in the `<details>` is simplest and fully SR-navigable. **Choose semantic `ui.tags.table`** via `@render.ui` (no interactive grid needed). |

## 2. State change (`multises_app/state.py`)
Add one method to `MultiSESState` (no field changes):
```python
def load_multises(self, ms: MultiSES) -> None:
    """Atomically swap in a new project: reset the active compartment + its
    project view so nothing points at the previous MultiSES, then signal."""
    self.active_multises.set(ms)
    cid = initial_active_compartment_id(ms)
    self.active_compartment_id.set(cid)
    self.active_compartment_project.set(_initial_active_project(ms))
    self.event_bus.emit_isa_change()
```
(`initial_active_compartment_id` and `_initial_active_project` already exist in
`state.py`.) The existing `_handle_save` in `project_setup.py` may later route through a
sibling, but chunk 4d leaves `_handle_save` (metadata-edit commit) untouched.

## 3. File flows (`multises_app/modules/project_setup.py`)
**UI** — add a "Project file" card/section (above or beside the existing form) with:
```python
ui.download_button("download_multises", "Save (download .json)"),
ui.input_file("open_multises", "Open .json", accept=[".json"], multiple=False),
ui.input_action_button("new_multises", "New (Curonian seed)"),
```
**Server** — add to `project_setup_server` (alongside `_handle_save`):
```python
@render.download(filename=lambda: f"mosaicses-{datetime.now():%Y%m%d-%H%M%S}.json")
def download_multises():
    yield state.active_multises.get().to_json().encode("utf-8")

@reactive.effect
@reactive.event(input.open_multises, ignore_init=True)
def _open():
    finfo = input.open_multises()
    if not finfo:
        return
    text = Path(finfo[0]["datapath"]).read_text(encoding="utf-8")
    try:
        result = MultiSES.from_json(text)
    except MultiSESIntegrityError as e:
        ui.notification_show(f"Could not load: {e}", type="warning", duration=6)
        return
    state.load_multises(result.multises)
    n = len(result.report.warnings)
    msg = "Loaded ✓" + (f" ({n} warning(s))" if n else "")
    ui.notification_show(msg, type="message", duration=4)

@reactive.effect
@reactive.event(input.new_multises, ignore_init=True)
def _new():
    state.load_multises(seed_curonian())
    ui.notification_show("New project (Curonian seed) ✓", type="message", duration=3)
```
Imports: `from multises import MultiSES, MultiSESIntegrityError, seed_curonian`,
`from pathlib import Path`, `from datetime import datetime` (extend existing imports;
`render` already imported in the module).

## 4. Topology a11y fallback (`multises_app/modules/topology.py`)
**UI** — add next to `output_pyvis_network("network", ...)`:
```python
ui.tags.details(
    ui.tags.summary("Tabular view (accessible)"),
    ui.output_ui("network_table"),
),
```
**Server** — a `@render.ui` building two semantic tables from the active MultiSES:
```python
@output
@render.ui
def network_table():
    ms = state.active_multises.get()
    comp_rows = _compartment_summary_rows(ms)   # existing helper
    comp_tbl = ui.tags.table(
        ui.tags.caption("Compartments"),
        ui.tags.thead(ui.tags.tr(*[ui.tags.th(h) for h in
            ("ID", "Label", "Archetype", "Elements", "Focal TW")])),
        ui.tags.tbody(*[
            ui.tags.tr(ui.tags.td(r["id"]), ui.tags.td(r["label"]),
                       ui.tags.td(r["archetype"]), ui.tags.td(str(r["element_count"])),
                       ui.tags.td("yes" if r["is_focal_tw"] else "no"))
            for r in comp_rows]),
    )
    chan_tbl = ui.tags.table(
        ui.tags.caption("Channels"),
        ui.tags.thead(ui.tags.tr(*[ui.tags.th(h) for h in
            ("Source", "Target", "Type", "Polarity", "Strength", "Delay")])),
        ui.tags.tbody(*[
            ui.tags.tr(ui.tags.td(c.source_id), ui.tags.td(c.target_id),
                       ui.tags.td(c.channel_type), ui.tags.td(c.polarity),
                       ui.tags.td(c.strength), ui.tags.td(c.delay))
            for c in ms.channels]),
    )
    return ui.div(comp_tbl, chan_tbl)
```
(Confirm the `Channel` attribute names — `source_id`/`target_id`/`channel_type`/
`polarity`/`strength`/`delay` per `multises/data_structure.py`; adjust to the real field
names during implementation. Empty channel list → a table with a header row only.)
The existing left-sidebar `compartments_list()` HTML table stays; this adds the missing
**channels** equivalent and groups both under one screen-reader `<details>`.

## 5. i18n
MosaicSES ships an English-only translator stub (`app.py:65` `Translator({"en": {}})`),
so chunk-4d labels are inline English strings (matching the existing `project_setup.py`
form labels). No `core.json` work.

## 6. Testing
- **Unit — `tests/test_project_setup_module.py`** (extend): assert the rendered
  `project_setup_ui` contains the `download_multises` button, the `open_multises`
  file input, and the `new_multises` button (HTML/string checks, the module's existing
  test style). Add a focused test for `MultiSESState.load_multises`: build a 2-compartment
  MultiSES, call `load_multises`, assert `active_multises`, `active_compartment_id`
  (= first compartment), and that `emit_isa_change` fired.
- **Unit — `tests/test_topology_module.py`** (extend): assert `topology_ui` contains a
  `<details>`/`network_table` output; assert `network_table`'s helper produces a row per
  compartment and per channel for a seeded MultiSES.
- **e2e — `tests/test_project_setup_e2e.py`** (new, via `shiny.pytest.create_app_fixture`
  like the existing e2e): on the Project panel — (a) click **New**, assert a toast / the
  metadata fields repopulate to the Curonian seed; (b) trigger the **Save** download and
  assert it fires with a `.json` suggested filename (Playwright `expect_download`);
  (c) **Open** a small valid MultiSES JSON (written to a temp file, set on the file input)
  and assert the project name updates. Reuse the e2e harness conventions from
  `tests/test_comparative_e2e.py` / `test_cross_view_e2e.py`.

## 7. Files

| File | Status | Purpose |
|---|---|---|
| `multises_app/state.py` | edit | add `MultiSESState.load_multises(ms)` |
| `multises_app/modules/project_setup.py` | edit | New/Open/Save UI + 3 handlers |
| `multises_app/modules/topology.py` | edit | `<details>` a11y tabular mirror (`network_table`) |
| `tests/test_project_setup_module.py` | edit | file-flow UI presence + `load_multises` unit tests |
| `tests/test_topology_module.py` | edit | a11y table presence + row-count tests |
| `tests/test_project_setup_e2e.py` | new | New / Save-download / Open e2e via app fixture |

No `multises/` library change; no `app.py` change (panels already mounted). SESPy
untouched (the spec/plan live in SESPy's `docs/superpowers/`; the code change is in the
MosaicSES repo).
