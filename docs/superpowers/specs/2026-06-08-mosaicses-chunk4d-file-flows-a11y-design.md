# MosaicSES Chunk 4d — File Flows + Topology Accessibility — Design

Date: 2026-06-08 (rev. 2 — after deep-review)
Status: **Draft** — design phase, not yet implemented.

**rev. 2 changes (from the review):** (a) **Bridge-chart axis fix RE-INCLUDED** — the
chart DOES exist (in `cross_view.py`, not `comparative.py` which the first exploration
checked); the bug is that integer degree counts and normalized betweenness (0–1) share
one y-axis, so betweenness bars are invisibly tiny — fix = a secondary `twinx` axis (§5).
(b) `Channel` fields are `source`/`target` (not `_id`); the a11y channel table uses them
+ `_unknown_channel_type_original or channel_type` for tolerant display. (c) Open treats
the upload as an untrusted boundary (broad `except` + log). (d) a11y tables extracted to a
pure `_channel_summary_rows` helper for testability + a "No channels" row. (e) the New
e2e first mutates state so the reset assertion can't false-pass from the default seed.

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

**Scope decisions made during investigation (2026-06-08, rev. 2):**
- **Bridge-chart axis fix — IN SCOPE** (corrected in rev. 2). The chart lives in
  `multises_app/modules/cross_view.py` (`bridge_chart()` `@render.image`, a "Bridge
  metrics" card), drawing three grouped bars per compartment: `channel_in_degree`,
  `channel_out_degree`, `betweenness`. **Bug:** all three share one y-axis, but
  in/out-degree are integer counts while `betweenness` is normalized to [0, 1] — so the
  betweenness bars are visually negligible and the chart misleads. **Fix:** plot
  betweenness on a secondary y-axis via `ax.twinx()` (§5).
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
    table (source → target, type, polarity, strength, delay), built from a new pure
    `_channel_summary_rows(ms)` helper. Gives screen-reader users a navigable equivalent
    of the pyvis canvas (WCAG 1.1.1 non-text content).
- **Bridge-chart axis fix** in `multises_app/modules/cross_view.py`: betweenness onto a
  secondary `twinx` y-axis so it's readable next to the integer degree counts (§5).
- Unit module tests + e2e coverage.

### 1.2 Out of scope
- Recent-projects registry/list (chunk 4e).
- Building NEW analytics charts (the bridge chart already exists; only its axis is fixed).
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
    # An uploaded file is untrusted input: from_json may raise
    # MultiSESIntegrityError (wrapped model errors) OR json.JSONDecodeError /
    # KeyError / TypeError / ValueError from the parse boundary. Catch broadly,
    # log, toast, and leave state untouched.
    try:
        text = Path(finfo[0]["datapath"]).read_text(encoding="utf-8")
        result = MultiSES.from_json(text)
    except Exception as e:  # noqa: BLE001 — untrusted file boundary
        _log.exception("project_setup: open failed")
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
Imports: `from multises import MultiSES, seed_curonian`, `from pathlib import Path`,
`from datetime import datetime`, and a module logger `_log = logging.getLogger("multises")`
(`import logging`) — extend existing imports; `render`/`reactive`/`ui` already imported.
(`MultiSESIntegrityError` no longer needs importing since Open catches broadly.)

## 4. Topology a11y fallback (`multises_app/modules/topology.py`)
**Pure helper** (module-level, unit-testable; tolerant of unknown channel types):
```python
def _channel_summary_rows(ms) -> list[dict]:
    return [
        {
            "source": c.source,
            "target": c.target,
            "type": c._unknown_channel_type_original or c.channel_type,
            "polarity": c.polarity,
            "strength": c.strength,
            "delay": c.delay,
        }
        for c in ms.channels
    ]
```
**UI** — add next to `output_pyvis_network("network", ...)`:
```python
ui.tags.details(
    ui.tags.summary("Tabular view (accessible)"),
    ui.output_ui("network_table"),
),
```
**Server** — a `@render.ui` building two semantic tables from the active MultiSES, using
`_compartment_summary_rows` (existing) + `_channel_summary_rows` (new):
```python
@output
@render.ui
def network_table():
    ms = state.active_multises.get()
    comp_rows = _compartment_summary_rows(ms)
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
    chan_rows = _channel_summary_rows(ms)
    chan_body = [
        ui.tags.tr(ui.tags.td(r["source"]), ui.tags.td(r["target"]),
                   ui.tags.td(r["type"]), ui.tags.td(r["polarity"]),
                   ui.tags.td(r["strength"]), ui.tags.td(r["delay"]))
        for r in chan_rows
    ] or [ui.tags.tr(ui.tags.td("No channels", colspan="6"))]
    chan_tbl = ui.tags.table(
        ui.tags.caption("Channels"),
        ui.tags.thead(ui.tags.tr(*[ui.tags.th(h) for h in
            ("Source", "Target", "Type", "Polarity", "Strength", "Delay")])),
        ui.tags.tbody(*chan_body),
    )
    return ui.div(comp_tbl, chan_tbl)
```
The existing left-sidebar `compartments_list()` HTML table stays; this adds the missing
**channels** equivalent and groups both under one screen-reader `<details>`.

**Nice-to-have (optional):** when `active_multises` changes (Open/New), the inspector's
`input.inspector_target` may point at a removed node. `_inspector_node_info` already
returns `None` safely (no crash), but resetting the inspector selection to `""`/the first
valid target in the existing choice-update effect improves UX. Not required for chunk 4d.

## 5. Bridge-chart axis fix (`multises_app/modules/cross_view.py`)
The `bridge_chart()` `@render.image` plots three grouped bars per compartment —
`channel_in_degree`, `channel_out_degree` (integer counts) and `betweenness` (normalized
to [0, 1]) — on **one shared y-axis**, so the betweenness bars are visually negligible.
**Fix:** draw betweenness on a secondary axis:
```python
fig, ax = plt.subplots(figsize=(8, 4), dpi=72)
ax.bar(x - w, in_deg,  width=w, label="in-degree")
ax.bar(x,     out_deg, width=w, label="out-degree")
ax.set_ylabel("degree (count)")
ax2 = ax.twinx()
b = ax2.bar(x + w, between, width=w, color="C2", label="betweenness")
ax2.set_ylabel("betweenness (0–1)")
ax2.set_ylim(0, max(1.0, max(between, default=0)))
ax.set_xticks(x); ax.set_xticklabels(compartments, rotation=30, ha="right")
# Combined legend across both axes (ax.legend() alone would drop betweenness):
handles1, labels1 = ax.get_legend_handles_labels()
ax.legend(handles1 + [b], labels1 + ["betweenness"], loc="upper right")
fig.tight_layout()
```
Keeps the existing temp-file/`render.image` plumbing and the `_bridge_chart_alt_text`
alt text (which already describes all three series) unchanged.

## 6. i18n
MosaicSES ships an English-only translator stub (`app.py:65` `Translator({"en": {}})`),
so chunk-4d labels are inline English strings (matching the existing `project_setup.py`
form labels). No `core.json` work.

## 7. Testing
- **Unit — `tests/test_project_setup_module.py`** (extend): assert the rendered
  `project_setup_ui` contains the `download_multises` button, the `open_multises`
  file input, and the `new_multises` button (HTML/string checks, the module's existing
  test style). Add a focused test for `MultiSESState.load_multises`: build a 2-compartment
  MultiSES, call `load_multises`, assert `active_multises`, `active_compartment_id`
  (= first compartment), and that `emit_isa_change` fired.
- **Unit — `tests/test_topology_module.py`** (extend): assert `topology_ui` contains a
  `<details>`/`network_table` output; test the pure **`_channel_summary_rows(ms)`** helper
  directly — one row per channel for a seeded MultiSES, correct field keys, and that an
  unknown channel type surfaces via `_unknown_channel_type_original`; empty `ms.channels`
  → `[]`.
- **Unit — `tests/test_cross_view_module.py`** (extend): a regression test for the
  bridge-chart axis fix — `bridge_chart` produces a valid PNG, and (asserting on the
  pure-data side) the betweenness series is on a 0–1 scale while degrees are integer
  counts (assert the metrics helper outputs, not pixels — the twinx itself is a render
  detail). At minimum, assert the render still returns a valid image dict without raising.
- **e2e — `tests/test_project_setup_e2e.py`** (new, via `shiny.pytest.create_app_fixture`
  like the existing e2e): on the Project panel — (a) **mutate state first** (edit the name
  field to a non-Curonian value and Save the metadata, OR Open a different project), THEN
  click **New** and assert the name field returns to the Curonian seed name (so the reset
  assertion can't false-pass from the default seed); (b) trigger the **Save** download and
  assert it fires with a `.json` suggested filename (Playwright `expect_download`);
  (c) **Open** a small valid MultiSES JSON (written to a temp file, `set_input_files` on
  `#project-open_multises`) and assert the project name updates. Use module-namespaced
  selectors (`#project-download_multises`, `#project-open_multises`, `#project-new_multises`).
  Reuse the harness conventions from `tests/test_comparative_e2e.py` / `test_cross_view_e2e.py`.

## 8. Files

| File | Status | Purpose |
|---|---|---|
| `multises_app/state.py` | edit | add `MultiSESState.load_multises(ms)` |
| `multises_app/modules/project_setup.py` | edit | New/Open/Save UI + 3 handlers + `_log` |
| `multises_app/modules/topology.py` | edit | `_channel_summary_rows` + `<details>` a11y mirror (`network_table`) |
| `multises_app/modules/cross_view.py` | edit | bridge-chart `twinx` secondary y-axis for betweenness |
| `tests/test_project_setup_module.py` | edit | file-flow UI presence + `load_multises` unit tests |
| `tests/test_topology_module.py` | edit | `_channel_summary_rows` + a11y table tests |
| `tests/test_cross_view_module.py` | edit | bridge-chart render regression |
| `tests/test_project_setup_e2e.py` | new | New / Save-download / Open e2e via app fixture |

No `multises/` library change; no `app.py` change (panels already mounted). SESPy
untouched (the spec/plan live in SESPy's `docs/superpowers/`; the code change is in the
MosaicSES repo).
