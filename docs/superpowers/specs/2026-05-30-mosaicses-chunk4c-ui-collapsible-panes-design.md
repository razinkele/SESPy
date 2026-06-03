# MosaicSES chunk-4c-ui — Collapsible panes (native bslib)

**Date:** 2026-05-30
**Status:** Design — awaiting user review
**Scope class:** Focused single-chunk UI change
**Depends on:** chunk-4b shipped to `origin/main` (collapsible-panes work is queued *behind* the 4b smoke + push; no code changes here begin until 4b is on origin).

## 1. Problem

The MosaicSES dashboard's per-page panes are frozen at fixed widths. Inside
each page, `ui.layout_columns(...)` assigns hard `col_widths` to control/list/
inspector cards, so they cannot get out of the way of the graph the user is
trying to read. User feedback (2026-05-30): *"generally the UI is not nice at
all. Panes are not collapsible"*, with `razinkele/osmopy` cited as the
reference for collapsible panes.

### Reference: how osmopy does it

osmopy is built on `ui.navset_pill_list` (not bslib layout primitives), so it
hand-rolls collapse:

- `collapsible_card_header(title, page_id)` — a card header with a `«` button
  calling `togglePanel('<page_id>')`.
- `expand_tab(title, page_id)` — a vertical re-expand tab shown when collapsed.
- `togglePanel()` / `toggleNav()` JS toggles a `.collapsed` class on the left
  column, shows the expand tab, and persists state to `localStorage`.

This delivers: **collapse the controls pane → the map/graph reclaims the
freed width**, plus per-page persistence of collapsed state.

### Current MosaicSES structure (verified 2026-05-30)

| Panel | File | Layout today |
|---|---|---|
| Project Setup | `multises_app/modules/project_setup.py` | 2-column form (info ∣ scope) |
| Topology | `multises_app/modules/topology.py` | `layout_columns(col_widths=[3,6,3])`: Compartments list ∣ pyvis canvas ∣ Inspector |
| Compartments | `multises_app/modules/compartments.py` | top-bar picker + `navset_tab` of 10 nested SESPy modules |
| Comparative | `multises_app/modules/comparative.py` | 5 stacked read-only `ui.card`s (vital signs, heatmap, leverage, R–P gap, meta-graph) |
| Cross-view | `multises_app/modules/cross_view.py` | horizontal filter toolbar (`ui.row` of switches + Refresh) above composite-canvas card + loops/bridge cards |

The shell (`sespy.dashboard.dashboard_page`) already provides a collapsible
**outer nav sidebar** via bslib `page_sidebar` + a custom mini-mode burger
script. The gap is purely the **per-page** panes.

## 2. Goal & non-goals

**Goal:** Make the per-page control panes collapsible so the graph/canvas can
reclaim the width, using MosaicSES's native bslib stack.

**Non-goals (explicitly deferred):**

- Theme/skin work; visual polish beyond collapsibility.
- CSS extraction to `www/mosaic-skin.css`; JS extraction.
- Compartments panel restructure.
- Project Setup redesign.
- Persistence of collapsed state across reloads (localStorage / bookmarking).
- Porting osmopy's `togglePanel`/`expand_tab` custom-JS machinery.

## 3. Approach

Replace fixed `layout_columns` control panes with native bslib
`ui.layout_sidebar(ui.sidebar(...), main_content)`.

Rationale (decision locked with user 2026-05-30): bslib's `sidebar` ships its
own chevron toggle, is keyboard- and screen-reader-accessible by default
(`aria-expanded` handled by the framework), and reflows the main content
automatically on collapse. Because MosaicSES already sits on bslib layout
primitives, this is a ~5-lines-per-panel drop-in with **zero custom JS** —
strictly better maintenance and accessibility than porting osmopy's hand-rolled
approach. It matches osmopy's *behavior* (controls collapse → graph widens),
not its *implementation*.

### Sidebar configuration conventions

Every converted sidebar uses:

- `open="desktop"` — open on desktop viewports, collapsed on mobile.
- a unique, stable `id` (e.g. `topology_list_sb`, `topology_inspector_sb`,
  `cross_view_filters_sb`) so the toggle is addressable and future
  enhancements (persistence, programmatic toggle) have a handle.
- `position="left"` or `position="right"` as noted per panel.
- `width≈300` (px) for control panes; tune during smoke.
- `title=` giving the sidebar a visible header.

## 4. Per-panel plan

### 4.1 Topology — primary win (two collapsible side panes)

Convert the `layout_columns([3,6,3])` into **two nested `layout_sidebar`s**:

```python
ui.layout_sidebar(
    ui.sidebar(
        ui.output_ui("compartments_list"),
        id="topology_list_sb", title="Compartments",
        position="left", open="desktop", width=300,
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_select("inspector_target", "Inspect:", choices={}),
            ui.output_ui("inspector_detail"),
            id="topology_inspector_sb", title="Inspector",
            position="right", open="desktop", width=320,
        ),
        ui.card(
            ui.card_header("Topology"),
            output_pyvis_network("network", height="650px", show_toolbar=False,
                                 show_search=False, show_layout_switcher=False,
                                 show_export=True, show_status=False),
            full_screen=True,
        ),
    ),
)
```

Collapsing the left (Compartments) or right (Inspector) sidebar widens the
central canvas. The pyvis canvas card gains `full_screen=True` for maximize.

**Server unchanged:** output ids (`compartments_list`, `network`,
`inspector_target`, `inspector_detail`) are preserved, so `topology_server`
needs no logic changes.

### 4.2 Cross-view — filter toolbar → collapsible left sidebar

Move the horizontal filter toolbar (the `ui.row` of `dapsi`/`channels`/
`cycles_only` switches, `types` selectize, and the `refresh` button, plus the
`dirty_hint` aria-live status) into a **collapsible left sidebar**
(`id="cross_view_filters_sb"`, `position="left"`, `open="desktop"`). The
composite-graph card reclaims the freed width and gains `full_screen=True`.

**Input ids preserved** (`dapsi`, `channels`, `cycles_only`, `types`,
`refresh`) and the `dirty_hint` output id preserved, so `cross_view_server`
and the `_CROSS_VIEW_JS` handler are untouched. The loops/bridge cards below
the canvas are unchanged.

### 4.3 Comparative — light touch (no sidebar)

These are 5 stacked read-only cards with no control inputs, so there is
nothing to collapse into a sidebar. Add `full_screen=True` to the
graph-bearing cards (the **meta-graph** card and the **centrality heatmap**
card) so the user can maximize them. No layout restructure, no server change.

### 4.4 Compartments — untouched

Decision locked with user: leave as-is. The picker is a top bar and the 10
nested SESPy analysis modules own their own internal layouts; restructuring is
high-risk, low-value, and out of scope.

### 4.5 Project Setup — untouched

A data-entry form; collapsing panes adds nothing.

## 5. Task 0 probe (pre-implementation verification)

Following the team's chunk-4a/4b probe convention, before writing code verify
against the installed Shiny/bslib in the `shiny` micromamba env:

1. `ui.sidebar` accepts `position="right"`, `open="desktop"`, `id=`, `title=`,
   `width=` in this version.
2. Nested `ui.layout_sidebar` (a `layout_sidebar` as the main content of an
   outer `layout_sidebar`) renders both a left and a right collapsible sidebar
   around a central pane.
3. `ui.card(..., full_screen=True)` is supported and the pyvis output renders
   correctly inside a full-screen-capable card (watch for the known
   `transform:none`/`display:block` pyvis-canvas guards the shell CSS applies).
4. A collapsed sidebar does not break the pyvis network's initial sizing
   (canvas width is read at render; confirm reflow on collapse/expand does not
   leave a zero-width or clipped canvas).

Record results in `docs/2026-05-30-chunk4c-ui-probe-results.md`. If probe 2 or
4 fails, fall back to single-sidebar-per-panel (left only for Topology,
Inspector becoming a `full_screen` card or an `accordion`) and re-confirm with
the user.

## 6. Testing & verification

### Affected tests (expected to need updates)

- `tests/test_topology_module.py` — asserts on the topology UI structure
  (likely `layout_columns`/`col_widths`); update to assert the new
  `layout_sidebar`/`sidebar` structure and that the four output/input ids
  still exist.
- `tests/test_cross_view_module.py` — asserts on toolbar/card structure;
  update for the sidebar-hosted filters while confirming input ids persist.
- `tests/test_comparative_module.py` — confirm `full_screen` additions don't
  break existing card assertions.
- `tests/test_cross_view_e2e.py`, `tests/test_comparative_e2e.py` — Playwright
  selectors that walk the DOM may need updating for the new structure;
  the loop-highlight invariant (chunk-4a) must still pass.

The contract to preserve in every test update: **all server-bound input/output
ids are unchanged**, so only structural/DOM assertions move — no behavioral
assertions should change.

### Manual smoke gate (ships the chunk)

Per `[[feedback_runtime_verify_before_shared_state]]`, collapse-reflow is a
render-state property unit tests cannot observe, so this chunk ends with a
manual browser smoke checklist (`docs/2026-05-30-chunk4c-ui-smoke-checklist.md`)
covering, at minimum:

- Topology: collapse left pane → canvas widens; collapse right pane → canvas
  widens further; collapse both → canvas near-full-width; expand each back.
- Topology: pyvis canvas is not clipped/zero-width after any collapse/expand;
  node click-to-navigate still works.
- Cross-view: collapse filters sidebar → composite canvas widens; Refresh and
  all four filter switches still drive the graph; loop-highlight still works.
- Comparative: meta-graph and heatmap cards enter/exit full-screen cleanly.
- Keyboard: each sidebar toggle is reachable by Tab and operable by Enter/
  Space; `aria-expanded` reflects state (screen-reader spot-check).
- Mobile/narrow viewport: sidebars start collapsed (`open="desktop"`).

Push to `origin/main` only after the smoke checklist is green.

## 7. Files touched

- `multises_app/modules/topology.py` — `topology_ui` only (server unchanged).
- `multises_app/modules/cross_view.py` — `cross_view_ui` only (server + JS
  unchanged).
- `multises_app/modules/comparative.py` — `comparative_ui` (add `full_screen`).
- `tests/test_topology_module.py`, `tests/test_cross_view_module.py`,
  `tests/test_comparative_module.py` — structural assertion updates.
- `tests/test_cross_view_e2e.py`, `tests/test_comparative_e2e.py` — selector
  updates if needed.
- `docs/2026-05-30-chunk4c-ui-probe-results.md` (new) — Task 0 probe log.
- `docs/2026-05-30-chunk4c-ui-smoke-checklist.md` (new) — manual smoke gate.

`app.py` is **not** touched: panels are wired by id and the ids are preserved.

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| pyvis canvas mis-sizes inside a collapsible/full-screen card | Medium | Task 0 probe 3–4; smoke checks reflow explicitly; shell already carries pyvis-canvas CSS guards |
| Nested two-sidebar layout unsupported / awkward in installed bslib | Low–Med | Task 0 probe 2; documented single-sidebar fallback (§5) |
| e2e selectors brittle to DOM change | Medium | Update selectors; keep ids stable; loop-highlight invariant re-run |
| Scope creep into theming | Low | Non-goals fixed in §2; persistence + skin explicitly deferred |

## 9. Out-of-scope follow-ups (future chunks)

Theme/skin, CSS extraction to `www/mosaic-skin.css`, JS extraction, collapse
persistence, Compartments restructure, Project Setup redesign, bridge-chart
axis fix, pyvis tabular a11y fallbacks (these last two already tracked from
chunk-4a/4b deferrals).
