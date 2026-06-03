# MosaicSES Chunk 4a — Comparative + Cross-view modules

**Status:** design — v3 (2026-05-15, revised after **two** rounds of in-loop agent review; first round caught 12 findings, second round caught 37 across 4 lenses)
**Parent spec:** [`2026-05-08-mosaicses-design.md`](2026-05-08-mosaicses-design.md) — chunk 4 is decomposed per the parent spec §7 distinction between "substantive UI work" (chunk 4a) and "bookkeeping" (chunk 4b).
**Predecessor chunk:** [`2026-05-12-mosaicses-chunk3-shiny-shell-topology-compartments.md`](../plans/2026-05-12-mosaicses-chunk3-shiny-shell-topology-compartments.md) — chunk 3 shipped 2026-05-15 (HEAD `80d0100`, 241 tests passing).
**Sibling spec (forthcoming):** `2026-05-??-mosaicses-chunk4b-...-design.md` covering `project_setup.py`, `recent_projects.py`, `mosaic-skin.css`, the remaining 2 e2e tests, accessibility tabular fallbacks for pyvis, JS extraction, and the v1 ship checklist.

---

## 1. Goal & scope

Add the two **substantive analytical UI modules** to MosaicSES: a Comparative-grid panel (5 cards) and a Cross-view composite-graph panel (3 cards + filter toolbar). End state: the app boots with 5 of the 6 v1 nav items working (`project`, `topology`, `compartments` from chunk 3; `comparative`, `cross_view` from this chunk); 2 of the 4 v1 e2e tests pass.

### 1.1 In scope

- **`multises_app/colors.py`** (new public module) — palette constants previously inlined in chunk-3's `topology._ARCHETYPE_COLORS`. Both `topology.py` and the new `comparative.py` consume from here. **Precondition for chunk 4a, not a contingency.**
- `multises_app/modules/comparative.py` — 5-card analytical grid, fully reactive
- `multises_app/modules/cross_view.py` — 3-card composite-graph view, refresh-button-triggered for the hero card
- One library extension: `multises.composite.build_composite_digraph` gains **two new** filter kwargs (`include_dapsi: bool = True`, `include_channels: bool = True`). The existing `channel_types: set[str] | None` is reused unchanged. Call site passes `set(input.types())` to match the signature.
- `tests/test_comparative_module.py` + `tests/test_cross_view_module.py` (unit-style, no browser)
- `tests/test_comparative_e2e.py` + `tests/test_cross_view_e2e.py` (Playwright-driven)
- `tests/test_composite_filters.py` — pure-Python unit tests for the two new `build_composite_digraph` filter kwargs, **plus** a parallel-channel test (verifies a stable edge-id mapping when two channels share src/dst)
- `tests/_curonian_fixtures.py` — test-shared module that *introspects* `seed_curonian()` at test-collection time to derive expected-uncovered-Pressure labels and expected-balancing-loop labels (avoids hard-coding fragile string literals)
- `pyproject.toml` additions: `playwright>=1.45`, `pytest-playwright>=0.5` (dev deps)
- `tests/conftest.py` extension for the app-under-test fixture
- README addition documenting the one-time `playwright install chromium` step

### 1.2 Out of scope (deferred to chunk 4b)

- `multises_app/modules/project_setup.py` — Project Setup metadata form. **Requires `MultiSESState.update_metadata(...)` mutator** (see §3 forward note); 4b owns landing it.
- `multises_app/modules/recent_projects.py` — thin wrapper over `sespy.recent_projects`
- `www/mosaic-skin.css` — CSS skinning; **4a uses an inline `<style id="mosaicses-chunk4a-stub">` block in `app.py.head_content`** so 4b can grep-locate and delete it in one commit. Palette constants in `multises_app/colors.py` (added in 4a) become CSS custom properties on `:root` in 4b.
- **Tabular fallbacks for pyvis canvases** (cross-view composite + Comparative card-5 meta-graph) — `<details><summary>Tabular view</summary><table>...</table></details>` carrying the same data as a `@render.data_frame`. WCAG SC 1.1.1 + 2.1.1 fix; chunk 4a's a11y baseline holds via `alt` text on matplotlib outputs and `aria-live` on the dirty hint; pyvis-canvas fallback is the chunk-4b accessibility deliverable.
- **JS extraction** — chunk 4a keeps the cross-view highlight handler as inline `ui.tags.script(...)`; chunk 4b moves it to `multises_app/static/cross_view_highlight.js` (linter visibility, IDE support) when the static-assets pattern lands alongside `mosaic-skin.css`.
- **External-API contract tests** — a new `tests/test_external_api_contracts.py` that imports Shiny/pyvis/playwright load-bearing symbols and asserts shape; alarms on quiet upstream drift. Chunk-4b polish; not blocking 4a.
- LOAC-hierarchical topology layout polish (parent spec §7.2); chunk 4b promotes (note: pattern question — see §3 forward note on whether 4b's single-toggle layout uses cross-view's refresh-button idiom or plain reactivity).
- `tests/test_topology_e2e.py` + `tests/test_compartments_e2e.py` — the other two v1-required e2e tests
- CI integration for browser pre-install
- v1 ship checklist

### 1.3 Non-goals

- No export functionality (PNG download, CSV) — phase 2 per parent spec §1.3
- No write paths in 4a's modules — both Comparative and Cross-view are pure read-only consumers of `state.active_multises`. Write paths for the Project Setup form are 4b.
- No new event-bus emissions — `event_bus.isa_change` remains scoped to chunk-3's Compartments module
- No app-level shared composite cache — module-local builds (Approach A, see §2)

---

## 2. Decisions baked in (during brainstorming 2026-05-15; revised after two review rounds 2026-05-15)

| Decision | Choice | Rationale |
|---|---|---|
| **Comparative render strategy** | Fully reactive **with `dpi=72` + no `bbox_inches='tight'` on the heatmap** | Performance review measured `dpi=100` + `bbox_inches='tight'` at ~1.8s/render — defeats "fully reactive". `dpi=72` without bbox-tight is ~200ms. Other cards are cheap (45ms summary, 54ms leverage, 2ms gap, ~200ms meta-graph pyvis). Per-edit fan-out cost ~500ms (Hidden-5 documented in §5). Falls back to a per-card refresh button in chunk 4b if real-world data scales worse. |
| **Comparative card layout** | Stacked full-width | Card 4 (response–pressure gap) is "publishable" per parent spec §7.4. Heatmap looks meaningful at full width. Simplest e2e test. |
| **Cross-view layout + filter placement** | Hero card 1 + 2-card bottom row; filter toolbar above card 1 with right-aligned Refresh button | Refresh stays in view while user scrolls between the three cards; matches "view with controls" mental model. |
| **Cross-view loop click-to-highlight intensity** | Balanced — colour + halo + thickness + **redundant size/shape change on nodes** + dim others to 30% opacity; no animation, no pan | Edges get 3 cues (red + 3× width + opacity); nodes need parity for deuteranope users — added size 1.4× + diamond shape (Maint-8). 30% dim is the chunk-4a default; chunk 4b may tune to 15%+grayscale if scientific user reports visibility issues on dense graphs. |
| **E2E framework** | `shiny.pytest.create_app_fixture` + `shiny.playwright.controller` + raw Playwright drop-down | Shiny 1.5.1 surface (`shiny.testing` doesn't exist): `shiny.pytest.create_app_fixture` spawns the app under test; `shiny.playwright.controller` provides DOM helpers for inputs/outputs; raw `page.evaluate` reserved for pyvis-canvas assertions. Adds ~150MB headless chromium one-time. |
| **Shared state / caching** | Module-local builds, no shared cache | `build_composite_digraph` measured at 3.1–4.0ms on Curonian seed. Module-local is fine; the chunk-3 `cross_compartment_loops(g=...)` hook earns its keep within the cross-view module. |
| **Centrality heatmap controls** | Dropdown: `betweenness` (default) / `degree` / `closeness` / `eigenvector`; slider: top-K, range 5–20, default 10 | **Default changed from `degree` to `betweenness`** (Domain-1): in the composite digraph (channels become synthetic→synthetic edges, DAPSI elements carry only within-compartment connectivity), degree reveals only local connectivity; betweenness reveals Driver→Pressure→Response chains that cross compartments — the EG/DAPSI(W)R(M) value proposition. |
| **Heatmap shape** | **Per-compartment top-K** (each row shows its own top-K central elements with type/archetype colour-coding) | **Changed from global top-K** (Domain-2): "global top-K" produces a structurally-sparse matrix because each DAPSI element belongs to exactly one compartment — 5/6 rows always zero. Per-compartment top-K fills every row and tells a meaningful "which element-types appear across compartments" story. |
| **Eigenvector centrality fallback** | `try nx.eigenvector_centrality(g) except PowerIterationFailedConvergence: nx.eigenvector_centrality_numpy(g)` | Hidden-3: composite digraph has many isolates (Curonian seed: 118/129 isolated). Plain power-iteration may fail to converge. NumPy variant handles sparse cases. |
| **Bridge bar chart** | **3-bar group per compartment** — `channel_in_degree`, `channel_out_degree`, `betweenness` (from `inter_compartment_metrics`) | **Changed from single betweenness** (Domain-6): betweenness on a 6-node graph saturates trivially; the in/out-degree counts already in `inter_compartment_metrics` add real comparative signal. |
| **Card 4 "publishable view" treatment** | Sticky disclaimer **above** the two lists; lists labelled `<ul class="comparative-publishable orphan">` ("Pressures whose compartment has no incoming governance channels") and `<ul class="comparative-publishable covered">` ("Pressures whose compartment has incoming governance channels"). Plus a **system-wide governance gap badge** (Domain-3): "Pressure labels with zero governance coverage in *any* compartment: N". No export buttons in chunk 4a. | Per-compartment caveat is sticky so it travels in screenshots (Risk 10). System-wide reading addresses the policy-targeting question the per-compartment view obscures. "Publishable" remains screenshot-able. |
| **"Highlight cross-compartment cycles only" toolbar filter** | Included as `ui.input_switch("cycles_only", value=False)` in the cross-view filter toolbar | Parent spec §7.5 card 1 requirement. Implemented by intersecting `build_composite_digraph` output with edges/nodes participating in any `cross_compartment_loops` result. **Loops list cached as a third `reactive.value` (`last_built_loops`)** so card 1's restriction and card 2's table are guaranteed-consistent (Risk 3). |
| **Refresh-effect cleanup contract** | On Refresh, the effect MUST: (a) compute the new graph, (b) update `last_built_composite` + `last_built_loops` + `last_applied`, (c) send `mosaicses:clear_highlight` message, (d) clear DataGrid `cell_selection` via the appropriate Shiny 1.5 API (Task 0 probe captures). | Risk 1 (chunk-3-Invariant-3 analog): without this, a stale loop selection from before the rebuild paints highlights onto a fresh network using a stale JS-side `originalEdges` snapshot. Verified by e2e: select-Refresh-assert-no-red. |
| **Cross-loops calc dependency** | `cross_loops_calc` reads `last_built_composite()` and `last_built_loops()` only — NOT `state.active_multises.get()` directly | Risk 2: reading both would compute card-2 against the new `ms` with stale cached `g` between Refresh events. When `state.active_multises` changes, the refresh effect's invalidator sets `last_built_composite` and `last_built_loops` to `None`, causing card 2 to fall back to a fresh `g=None` build via the chunk-3 task 1.5 hook; an explicit "data changed — click Refresh to re-render canvas" hint accompanies. |
| **Pre-Refresh placeholder** | Card 1's render function checks `last_built_composite() is None` and emits `ui.HTML('<div class="placeholder">Click Refresh ⟳ to build the composite graph.</div>')` | Risk 6: `@reactive.event(input.refresh)` doesn't fire on initial mount (default `ignore_init=True`). Without the placeholder, card 1 is silently empty. |
| **Empty-filter-combo placeholder** | When the rebuilt graph has zero nodes/edges (e.g. `include_channels=False AND cycles_only=True`), card 1 renders `<p class="placeholder">Current filter combination shows nothing. Try enabling channels or relaxing the cycles-only filter.</p>` | Domain-8: blank canvas is indistinguishable from a render bug. |
| **Empty-result phrasing on uncovered Pressures** | "No Pressures sit in compartments without incoming governance channels. If governance channels haven't been authored yet, this may indicate missing data rather than complete coverage." | Domain-9: neutral, signposts the limitation. The library docstring already documents the same nuance. |
| **Accessibility — image `alt` text** | `@render.image` outputs must specify dynamic `alt` text built from underlying data (e.g. "Centrality heatmap: 6 compartments × top-10 betweenness elements. Highest: curonian_lagoon. Lowest: klaipeda_strait."). Spec includes an `alt_text_*()` helper per card. | Maint-5 (WCAG SC 1.1.1 Level A). Chunk-3 a11y baseline (lang attr + visually-hidden h1) requires we don't regress here. |
| **Accessibility — dirty-hint live region** | The dirty-hint slot wraps content in `<div role="status" aria-live="polite">…</div>` | Maint-7: screen-reader users get an announcement when filter changes require Refresh. |
| **Module-decorator pattern** | `@module.ui` + `@module.server` from `shiny.module` (chunk-3's `topology.py` convention) | Call sites: `comparative_server("comparative", state=state)` per chunk-3 `topology_server("topology", state=state)`. |
| **pyvis rendering pattern** | `pyvis.shiny.render_pyvis_network` decorator (chunk-3 convention) | Chunk-3's `topology.py` already imports it. Ensures Shiny owns the DOM lifecycle, gives a deterministic emitted canvas id (Task 0 probe 4 captures the exact convention). |
| **Reactive-isolation pattern for refresh-gated card 1** | `@reactive.event(input.refresh)` on the effect + `with reactive.isolate()` around every filter-input read inside the effect body | Plain `.get()` / `input.x()` access registers a reactive dependency in Shiny-for-Python; `reactive.isolate()` is required to read without subscribing (chunk-3 `compartments.py:289–292` idiom). Without isolate, filter toggles would defeat the refresh-gating. |
| **JS handler registration timing** | Top-level `<script>` in `cross_view_ui()`, before pyvis HTML loads. Handlers reset `originalEdges = originalNodes = null` on every `clear_highlight` so post-rebuild state is fresh. | Mitigates the known race + Risk 1's stale-closure failure mode. |

---

## 3. Architecture

**Two new Shiny modules** + **one new helper module** (`colors.py`), all decorated with `@module.ui` / `@module.server` to match chunk-3's convention:

```python
# multises_app/colors.py — NEW shared palette
ARCHETYPE_COLORS: dict[str, str] = { ... }   # moved from topology._ARCHETYPE_COLORS
CHANNEL_TYPE_RENDER: dict[str, dict] = { ... }   # color + dash patterns, sourced from channels.json
```

```python
# multises_app/modules/comparative.py
from shiny import module, ui, render, reactive
from multises_app.state import MultiSESState
from multises_app.colors import ARCHETYPE_COLORS

@module.ui
def comparative_ui() -> ui.Tag: ...

@module.server
def comparative_server(input, output, session, *, state: MultiSESState) -> None: ...

# multises_app/modules/cross_view.py — same shape
@module.ui
def cross_view_ui() -> ui.Tag: ...

@module.server
def cross_view_server(input, output, session, *, state: MultiSESState) -> None: ...
```

**Call sites in `app.py`**:

```python
comparative_server("comparative", state=state)
cross_view_server("cross_view", state=state)
```

**Wiring** (changes outside the two new module files):

- `multises_app/colors.py` — new file. `multises_app/modules/topology.py` imports `from multises_app.colors import ARCHETYPE_COLORS` (refactor of chunk-3's inline `_ARCHETYPE_COLORS`).
- `multises_app/dashboard.py`'s `NAV` list gains two entries: `NavItem(id="comparative", icon="chart-line", label="Comparative")` and `NavItem(id="cross_view", icon="circle-nodes", label="Cross-view")`. Position: between `compartments` and where `recent` will land in chunk 4b. (Real `NavItem` signature per `sespy/dashboard.py`: `id: str, icon: str, label: str, label_key: str | None = None` — `label_key` is the i18n hook; chunk-3 NAV entries don't use it, so chunk-4a doesn't either.)
- `multises_app/dashboard.py`'s `STEPPER` list is **unchanged**. Both new panels map to the existing `drill` stepper step.
- `multises_app/dashboard.py`'s `NAV_TO_STEP` dict gains `"comparative" → "drill"` and `"cross_view" → "drill"`.
- `app.py` gets two new `ui.nav_panel(...)` entries inside `PANELS` and two new server calls. `app.py.head_content` gets the inline `<style id="mosaicses-chunk4a-stub">` block carrying `.comparative-publishable` rules (4b grep-deletes and migrates to CSS file).
- **No new top-level `reactive.value`** at the app level. Only mutable state remains chunk-3's `MultiSESState`.

**Forward note for chunk 4b — write paths.** Chunk 4a establishes the read-only consumer pattern. Chunk 4b's `project_setup_server` will need write paths to mutate the active MultiSES's metadata (name, river_basin, regional_sea, focal_issue, scales). The intentional 4b deliverable is a `state.update_metadata(**fields) -> None` mutator on `MultiSESState`; chunk 4a deliberately does not introduce one. Locating this decision here makes the omission a documented design choice rather than a future archaeology problem.

**Forward note for chunk 4b — refresh-pattern scope.** Cross-view's refresh-gated pattern is for multi-input composite rebuilds (filter toolbar feeding one expensive build). Chunk 4b's LOAC-hierarchical-layout toggle on topology is a single boolean affecting an existing canvas — that's plain reactive, NOT refresh-gated. Two patterns for two different needs; the spec records this so 4b doesn't reuse refresh-gate inappropriately.

**Architectural-rule tests** auto-cover the new modules — `tests/test_multises_app_imports.py`'s AST allow-list scanner already includes `multises.composite` and `multises.comparative` (chunk 2). The no-Shiny-in-library scanner doesn't apply (no library changes).

---

## 4. Components

### 4.1 Comparative module — 5 stacked cards

Each card is wrapped in a `ui.card(...)` with class `comparative-card` for the architectural-rule test to detect.

1. **Vital signs** — Calls `multises.comparative.compartment_summary(ms)`; rendered via `@render.data_frame` for sortability. ~6 rows × 8 columns on the Curonian seed.

2. **Centrality heatmap** —
   - UI: `ui.input_select("metric", choices=["betweenness", "degree", "closeness", "eigenvector"], selected="betweenness")` + `ui.input_slider("top_k", min=5, max=20, value=10, step=1)`.
   - Server: builds composite locally via `build_composite_digraph(state.active_multises.get())`. Computes the chosen centrality across the full graph (eigenvector path with convergence fallback per §2). **For each compartment**, selects that compartment's own top-K DAPSI-element nodes by centrality (per-compartment top-K, not global). Matrix shape: 6 rows × K columns — but each row has its own column-labels (the compartment's top-K elements). Rendered as either a stacked-row visualization (each row a small heatmap strip; element labels per row) or as 6 separate rows in a single matplotlib figure with rotated labels. Cell colour = centrality value normalized within the row.
   - Render: matplotlib `imshow` to PNG via `@render.image`. **`dpi=72`, `bbox_inches=None`** (Cost-1 mitigation). Width 800px, height proportional to compartment count.
   - **`alt` text**: built dynamically — e.g. `"Centrality heatmap (betweenness): top compartments by per-compartment central elements: curonian_lagoon (nutrient_load, eutrophication, ...), nemunas_delta (..., ...)."` (Maint-5).

3. **Global leverage** — Calls `multises.comparative.leverage_hotspots(ms)`; slices top 20; rendered as `@render.data_frame`. Sortable.

4. **Response–Pressure gap** — the "publishable view":
   - Server: calls `multises.comparative.response_pressure_gap(ms)`. The returned DataFrame has columns `compartment_id, pressure_id, pressure_label, within_compartment_response_count, incoming_governance_channel_count, pressure_compartment_has_no_governance`. Splits on the boolean `pressure_compartment_has_no_governance` — `True` rows go to the left ("uncovered in this compartment"), `False` rows to the right ("covered in this compartment").
   - **Sticky disclaimer** above the two lists (NOT a subtitle below them — so it travels in screenshots): `<figcaption class="sticky-disclaimer">Coverage shown is per-compartment. A Pressure may be uncovered in one compartment and covered in another. See system-wide badge below for "no governance anywhere" Pressures.</figcaption>`.
   - UI: a `ui.row(ui.column(6, ...), ui.column(6, ...))` rendered as two `<ul>` lists with distinguishing classes for testability: `<ul class="comparative-publishable orphan">` (heading: *"Pressures whose compartment has no incoming governance channels"*) on the left and `<ul class="comparative-publishable covered">` (heading: *"Pressures whose compartment has incoming governance channels"*) on the right. Each `<li>` shows `<span class="dot" style="background:{archetype_color}"></span> {compartment_label} — {pressure_label}` (sourced from `Compartment.label`, the real field name per `multises/data_structure.py:305`).
   - **System-wide governance gap badge** (below the lists): derived client-side by grouping the DataFrame on `pressure_label` and asking `all(pressure_compartment_has_no_governance) for each label`. Renders as `<span class="badge">{N} Pressure label(s) have zero governance coverage in ANY compartment: {labels...}</span>`. Addresses Domain-3 — the policy-targeting reading the per-compartment view obscures.
   - CSS class `comparative-publishable` is defined inline in `app.py.head_content` (`<style id="mosaicses-chunk4a-stub">`); chunk 4b moves it to `www/mosaic-skin.css`.
   - Empty-result handling: zero-orphan case renders the neutral phrasing in §2 ("No Pressures sit in compartments without incoming governance channels. If governance channels haven't been authored yet, this may indicate missing data rather than complete coverage.").

5. **Compartment-level meta-graph** — pyvis `Network`:
   - Nodes: one per compartment. `size = 10 + 2 * element_count`. Colors imported from `multises_app.colors.ARCHETYPE_COLORS`.
   - Edges: one per channel. Color + dash pattern from `multises_app.colors.CHANNEL_TYPE_RENDER` (or directly from channels.json via the same accessor chunk-3's topology.py uses).
   - Layout: force-directed (pyvis default). LOAC-hierarchical layout is chunk 4b polish.
   - Rendered via `@render_pyvis_network` (chunk-3 `topology.py:18` convention).
   - **Accessibility deferred to chunk 4b**: `<details><summary>Tabular view</summary>…</details>` with a `@render.data_frame` shadowing the same nodes + edges.

### 4.2 Cross-view module — filter toolbar + 3 cards

**Filter toolbar** (above card 1, full-width row):

- `ui.input_switch("dapsi", "DAPSI elements", value=True)`
- `ui.input_switch("channels", "Channels", value=True)`
- `ui.input_switch("cycles_only", "Cross-compartment cycles only", value=False)`
- `ui.input_selectize("types", "Channel types", choices=list(CHANNEL_TYPES), multiple=True, selected=list(CHANNEL_TYPES))`
- Right-aligned `ui.input_action_button("refresh", "Refresh ⟳", class_="btn-primary")`
- **A live region for the dirty hint**: `ui.tags.div(ui.output_ui("dirty_hint"), role="status", aria_live="polite")`. When toolbar inputs differ from `last_applied`, displays `<span class="text-muted">filters changed — click Refresh</span>`. When `state.active_multises` changed since `last_applied`, displays `<span class="text-warning">data changed — click Refresh to re-render canvas</span>`.

**Card 1 — Composite graph viewer** (hero):

```python
last_built_composite = reactive.value[nx.DiGraph | None](None)
last_built_loops     = reactive.value[list[CrossLoop] | None](None)
last_applied         = reactive.value[tuple | None](None)

@reactive.effect
@reactive.event(input.refresh)
async def _rebuild_composite():
    with reactive.isolate():
        ms = state.active_multises.get()
        include_dapsi    = input.dapsi()
        include_channels = input.channels()
        cycles_only      = input.cycles_only()
        types_tuple      = tuple(sorted(input.types() or ()))
        types_arg        = set(types_tuple) if types_tuple else None
    g = build_composite_digraph(
        ms,
        include_dapsi=include_dapsi,
        include_channels=include_channels,
        channel_types=types_arg,
    )
    loops = cross_compartment_loops(ms, g=g)  # computed ONCE per rebuild
    if cycles_only:
        keep_nodes = {n for loop in loops for n in loop.nodes}
        keep_edges = {
            (loop.nodes[i], loop.nodes[i + 1])
            for loop in loops
            for i in range(loop.length)
        }
        g = _restrict_digraph(g, keep_nodes, keep_edges)  # module-local helper in cross_view.py
    last_built_composite.set(g)
    last_built_loops.set(loops)
    last_applied.set((include_dapsi, include_channels, cycles_only, types_tuple, id(ms)))
    # Cleanup contract — Risk 1 mitigation
    await session.send_custom_message("mosaicses:clear_highlight", {})
    # Clear DataGrid cell_selection per Task 0 probe 3
    # (exact API verified in Task 0; placeholder: loops_table.update_cell_selection({"rows": (), "cols": ()}))

# Invalidate cached graph when underlying data changes — Risk 2 mitigation
@reactive.effect
def _invalidate_cache_on_data_change():
    state.active_multises.get()  # subscribe
    with reactive.isolate():
        applied = last_applied()
    if applied is not None and applied[-1] != id(state.active_multises.get()):
        last_built_composite.set(None)
        last_built_loops.set(None)
```

**Card 1 render — paired outputs** (the `@render_pyvis_network` decorator returns a `pyvis.network.Network`, not HTML; placeholder text must live in a sibling `@render.ui` output, per chunk-3 `topology.py:284-289` pattern):

```python
# UI side (inside cross_view_ui):
ui.output_ui("composite_canvas_status"),
output_pyvis_network("composite_canvas", height="600px", ...),

# Server side:
@output
@render.ui
def composite_canvas_status():
    applied = last_applied()
    if applied is None:
        return ui.HTML('<div class="placeholder">Click Refresh ⟳ to build the composite graph.</div>')
    g = last_built_composite()
    if g is not None and g.number_of_nodes() == 0:
        return ui.HTML('<p class="placeholder">Current filter combination shows nothing. Try enabling channels or relaxing the cycles-only filter.</p>')
    return ui.HTML("")

@output(id="composite_canvas")
@render_pyvis_network(height="600px", ...)
def _composite_canvas() -> pyvis.network.Network:
    g = last_built_composite()
    net = pyvis.network.Network(directed=True, notebook=False)
    if g is None or g.number_of_nodes() == 0:
        return net  # empty Network — placeholder shown via composite_canvas_status
    # populate net from g (nodes + edges)
    return net
```

`_restrict_digraph(g, keep_nodes, keep_edges)` is a small module-local helper (~10 lines) declared inside `cross_view.py`, not promoted to the library.

**Card 2 — Cross-compartment loops table**:

```python
# Reads only the cached state — guarantees consistency with card 1 (Risk 2 + Risk 3)
cross_loops_calc = reactive.calc(lambda: last_built_loops() or ())

@render.data_frame
def loops_table():
    loops = cross_loops_calc()
    if not loops:
        # First load (pre-Refresh) — show informational row, not empty
        return render.DataGrid(
            pd.DataFrame([{"info": "Click Refresh ⟳ on the toolbar above to detect cross-compartment loops."}]),
            selection_mode="none",
        )
    df = pd.DataFrame([
        {"id": l.id, "length": l.length, "polarity_type": l.polarity_type,
         "compartments": " → ".join(l.compartments_visited), "polarity_string": l.polarity_string}
        for l in loops
    ])
    return render.DataGrid(df, selection_mode="row")
```

**Loop click handler**:

```python
@reactive.effect
async def _on_loop_selection():
    sel = loops_table.cell_selection()  # Shiny 1.5 selection API per Task 0 probe 3
    rows = sel.get("rows", ()) if sel else ()
    if rows:
        loop = cross_loops_calc()[rows[0]]
        await session.send_custom_message("mosaicses:highlight_loop", {
            "edge_ids": [edge_dom_id(loop.nodes[i], loop.nodes[i + 1]) for i in range(loop.length)],
            "node_ids": list(set(loop.nodes)),
        })
    else:
        await session.send_custom_message("mosaicses:clear_highlight", {})
```

`loop.nodes` are composite-graph node ids in cycle order with a repeated closing node; `loop.length` is the distinct-edge count. `edge_dom_id(u, v)` maps a `(source, target)` pair to whatever edge id `render_pyvis_network`/vis.js emits — Task 0 probe 4 captures the convention.

**Card 3 — Bridge bar chart**:

- Server: calls `inter_compartment_metrics(ms)` (returns `dict[compartment_id, {"channel_in_degree": int, "channel_out_degree": int, "betweenness": float}]`); renders matplotlib **grouped bar chart**: 6 compartments × 3 bars each (in, out, betweenness). `dpi=72`, `bbox_inches=None`. PNG via `@render.image`.
- `alt` text: `"Bridge metrics by compartment: each compartment has three bars showing channel_in_degree, channel_out_degree, and betweenness. Highest betweenness: <X>; highest in-degree: <Y>; highest out-degree: <Z>."` (Maint-5).
- Reactive on `state.active_multises.get()` directly (cheap; no refresh gate).

**JS handler block** (top-level in `cross_view_ui()`, embedded as `ui.tags.script(...)`):

```javascript
(function () {
  // Convention captured by Task 0 probe 4 — pyvis.shiny.render_pyvis_network attachment
  function getNetwork() {
    return window.__mosaicses_get_cross_view_network?.() ?? null;
  }
  let originalEdges = null, originalNodes = null;

  Shiny.addCustomMessageHandler("mosaicses:highlight_loop", (msg) => {
    const net = getNetwork(); if (!net) return;
    if (originalEdges === null) {
      originalEdges = net.body.data.edges.get();
      originalNodes = net.body.data.nodes.get();
    }
    net.body.data.edges.update(originalEdges.map(e => ({
      id: e.id,
      color: msg.edge_ids.includes(e.id) ? "#e74c3c" : { opacity: 0.3, color: e.color },
      width: msg.edge_ids.includes(e.id) ? 3 : 1,
    })));
    net.body.data.nodes.update(originalNodes.map(n => ({
      id: n.id,
      // Three redundant cues (color, opacity, size+shape) for deuteranope users
      opacity: msg.node_ids.includes(n.id) ? 1.0 : 0.3,
      borderWidth: msg.node_ids.includes(n.id) ? 2 : 1,
      color: msg.node_ids.includes(n.id)
        ? { border: "#e74c3c", background: n.color?.background ?? "#fff" }
        : n.color,
      size: msg.node_ids.includes(n.id) ? (n.size ?? 25) * 1.4 : (n.size ?? 25),
      shape: msg.node_ids.includes(n.id) ? "diamond" : (n.shape ?? "dot"),
    })));
  });

  Shiny.addCustomMessageHandler("mosaicses:clear_highlight", () => {
    const net = getNetwork();
    if (net && originalEdges !== null) {
      net.body.data.edges.update(originalEdges);
      net.body.data.nodes.update(originalNodes);
    }
    // Risk 1 mitigation: null the captured state so a post-rebuild highlight
    // recaptures the NEW network's baseline, not the old one's.
    originalEdges = null;
    originalNodes = null;
  });
})();
```

---

## 5. Data flow

**Upstream source of truth:** `state.active_multises: reactive.value[MultiSES]` from chunk-3's `multises_app/state.py`. Both modules are pure read-only consumers.

**Comparative — fully reactive:**

```
state.active_multises       →  all 5 cards re-render
input.metric              →  card 2 only
input.top_k               →  card 2 only
```

**Per-edit fan-out cost** (Hidden-5): one `state.active_multises` write triggers the 5 cards' total budget. Measured budgets (Curonian seed, warm, with dpi=72):
- Card 1 vital signs: ~45ms
- Card 2 heatmap matplotlib: ~200ms (with dpi=72; ~1.8s with dpi=100+bbox-tight — the rationale for the §2 decision)
- Card 3 leverage: ~54ms
- Card 4 gap: ~2ms
- Card 5 pyvis meta-graph: ~200ms
- **Total per-edit cost: ~500ms.** Cold first-mount adds ~1s of sespy import + Agg-backend init.

**Cross-view — refresh-gated for card 1, cached-derived for cards 2 + 3:**

```
state.active_multises       →  card 3 re-renders (cheap)
state.active_multises       →  cache-invalidation effect sets last_built_composite/loops to None
                         →  card 2 re-renders showing "click Refresh" informational row
                         →  dirty-hint flips to "data changed — click Refresh"
input.dapsi/channels/cycles_only/types →  dirty-hint flips; card 1 unchanged
input.refresh             →  card 1 rebuilds composite + loops; updates caches; sends clear_highlight + clears DataGrid selection
```

**Loop click → highlight flow:**

```
user clicks loop row N in cross-view card 2
  ↓
loops_table.cell_selection() observed by _on_loop_selection
  ↓
sends "mosaicses:highlight_loop" via session.send_custom_message
  ↓
JS handler (registered at module-mount time, BEFORE pyvis HTML loads):
    if originalEdges === null: capture from CURRENT network
    apply red+thickness+opacity to edges
    apply red+opacity+size+shape to nodes
  ↓
on Refresh: send mosaicses:clear_highlight → JS restores AND nulls originalEdges/Nodes
```

**No telemetry / event_bus emissions** from these modules.

---

## 6. Error handling

- **Library function exceptions** are NOT caught inside the Shiny modules; tracebacks reach the dev console.
- **Eigenvector convergence failure** (Hidden-3): card 2 wraps the eigenvector path in `try ... except nx.PowerIterationFailedConvergence: fall back to nx.eigenvector_centrality_numpy(g)`. If numpy variant also fails (unlikely on real graphs), card 2 renders `<p class="placeholder">Eigenvector centrality does not converge on this graph; try a different metric.</p>`.
- **Empty-result rendering** is NOT an error: zero-uncovered-Pressures, zero-cross-loops, single-compartment-degenerate-bridge are all valid outcomes with their own placeholder rendering (per §2 phrasing decisions).
- **matplotlib render failures** bubble up; `@render.image` returns trace to dev console.
- **pyvis render failures** bubble up; YAGNI on user-facing fallback.
- **JS handler race** is mitigated structurally — handlers registered in a top-level `<script>`, not inside pyvis HTML.
- **`originalEdges` stale-after-rebuild race** (Risk 1): mitigated by the Refresh effect sending `clear_highlight` (which nulls the JS-side cache) AND clearing the DataGrid `cell_selection`.

---

## 7. Testing

### 7.1 Unit tests (Python-only, fast)

**`tests/test_composite_filters.py`** — pure-library tests:
- `test_include_dapsi_false_drops_dapsi_nodes`
- `test_include_channels_false_drops_channel_edges`
- `test_channel_types_filter_restricts_to_named_types`
- `test_default_kwargs_match_chunk3_behavior` — regression guard
- `test_parallel_channels_keep_one_edge_id_stable` (Risk 9) — synthetic 2-parallel-channel fixture; assert exactly one edge survives; verify `edge_dom_id` returns a stable id for the kept channel

**`tests/_curonian_fixtures.py`** — test-shared introspection (Risk 11):

```python
"""Derive expected-test-state from seed_curonian() at collection time
so renaming a seeded Pressure doesn't silently break e2e asserts."""
from multises import seed_curonian
from multises.comparative import response_pressure_gap
from multises.composite import cross_compartment_loops

_SEED = seed_curonian()
_GAP = response_pressure_gap(_SEED)
_LOOPS = cross_compartment_loops(_SEED)

EXPECTED_UNCOVERED_PRESSURE_LABELS: tuple[str, ...] = tuple(sorted(set(
    _GAP[_GAP["pressure_compartment_has_no_governance"]]["pressure_label"]
)))
EXPECTED_BALANCING_LOOP_LABELS: tuple[str, ...] = tuple(
    " → ".join(l.compartments_visited) for l in _LOOPS if l.polarity_type == "Balancing"
)

# Sanity: parent spec §10.5 requires ≥ 2 uncovered Pressures on Curonian seed
assert len(EXPECTED_UNCOVERED_PRESSURE_LABELS) >= 2, (
    "Curonian seed no longer satisfies parent spec §10.5 acceptance criterion "
    "(≥ 2 uncovered Pressures). Seed drifted — investigate before changing fixture."
)
assert len(EXPECTED_BALANCING_LOOP_LABELS) >= 1, (
    "Curonian seed no longer has the eutrophication–governance balancing loop "
    "(parent spec §10.5 / §8.4 Loop 1)."
)
```

**`tests/test_comparative_module.py`** — imports `multises_app.modules.comparative`:
- `test_comparative_ui_renders_5_cards` — asserts 5 `.comparative-card` descendants.
- `test_comparative_server_registers_5_outputs` — Shiny module-server registration test using `shiny.pytest.create_app_fixture` + `seed_curonian()`; verifies the 5 output names (`vital_signs`, `heatmap`, `leverage`, `gap_disclaimer`/`gap_lists`/`gap_systemwide_badge`, `meta_graph_canvas`) are registered.
- `test_centrality_controls_defaults_and_bounds` — metric choices exact list; default `selected="betweenness"`; top-K slider min=5/max=20/value=10.
- `test_centrality_eigenvector_fallback_to_numpy` — synthetic graph that fails power-iteration; assert fallback path called; assert result is a dict.
- `test_response_pressure_gap_lists_labelled` — drives a fixture MultiSES and asserts `<ul.orphan>` heading text and `<ul.covered>` heading text are present.
- `test_system_wide_gap_badge_renders_when_pressure_uncovered_everywhere` — fixture where one Pressure label is uncovered in all 6 compartments; assert badge text contains that label.

**`tests/test_cross_view_module.py`** — imports `multises_app.modules.cross_view`:
- `test_cross_view_ui_renders_filter_toolbar_and_3_cards` — 4 switches (dapsi/channels/cycles_only/types) + refresh + 3 cards.
- `test_dirty_hint_toggles_on_input_change_and_refresh`.
- `test_dirty_hint_has_aria_live_polite` — assert the wrapping `<div>` carries `role="status" aria-live="polite"`.
- `test_pre_refresh_state_card_1_placeholder` — without firing Refresh, `last_built_composite()` is None and the render emits the placeholder div.
- `test_empty_filter_combo_placeholder` — set `include_channels=False`, `cycles_only=True`; assert card 1 renders the empty-combo placeholder.
- `test_cache_invalidation_on_data_change` — set `state.active_multises` to a new MultiSES; assert `last_built_composite` becomes None.
- The JS message dispatch is NOT asserted here.

### 7.2 E2E tests (`shiny.pytest.create_app_fixture` + `shiny.playwright.controller` + raw Playwright)

**`tests/test_comparative_e2e.py`**:
- Boot app via fixture; nav to `#comparative`.
- Assert exactly 5 `.comparative-card`.
- Assert sticky disclaimer text is present ABOVE both lists (selector `figcaption.sticky-disclaimer`).
- Assert `ul.comparative-publishable.orphan` heading reads `"Pressures whose compartment has no incoming governance channels"`.
- Assert ≥ 2 `<li>` in `ul.comparative-publishable.orphan`; assert each `<li>` text contains a label from `_curonian_fixtures.EXPECTED_UNCOVERED_PRESSURE_LABELS`.
- Assert system-wide-gap-badge presence (badge element may say "0" — only the badge's existence is acceptance-required, not a specific count).
- Default-selected metric is `betweenness`.
- Change metric to `degree`; assert heatmap `<img>` src changes AND `<img>` `naturalWidth > 0`.
- Heatmap `<img>` has non-empty `alt` attribute.
- Card 3 bridge `<img>` has non-empty `alt`.
- Card 5 pyvis canvas present.

**`tests/test_cross_view_e2e.py`**:
- Boot app; nav to `#cross_view`.
- Pre-Refresh: assert card 1 shows the placeholder text `"Click Refresh ⟳ to build the composite graph."`; card 2 shows the informational row `"Click Refresh ⟳ on the toolbar above to detect cross-compartment loops."`.
- Dirty-hint container has `role="status"` and `aria-live="polite"`.
- Click Refresh; wait for pyvis canvas visible.
- `page.evaluate(...)` (Task 0 probe 4 convention): `network.body.data.nodes.get().filter(n => n.group === 'compartment').length === 6`.
- Search ALL loops-table rows for one whose `compartments` text matches a label tuple in `_curonian_fixtures.EXPECTED_BALANCING_LOOP_LABELS` AND whose `polarity_type` column reads `Balancing`.
- Click that row.
- Read `network.body.data.edges.get()` via `page.evaluate`; assert exactly `loop.length` edges have `color === '#e74c3c'`; assert at least one non-loop edge has `opacity === 0.3` (opacity-dim verification); assert a highlighted node has `shape === 'diamond'` (redundant-cue verification — Maint-8).
- **Refresh-after-select cleanup** (Risk 1 acceptance test): click another filter (e.g. toggle DAPSI); click Refresh; assert NO edges have `color === '#e74c3c'`; assert `loops_table.cell_selection().rows === ()`.
- Toggle `cycles_only` on; click Refresh; assert rebuilt network has strictly fewer nodes than pre-toggle.
- Set channels=off + cycles_only=on; click Refresh; assert the empty-filter-combo placeholder text is visible.
- Toggle a filter; assert dirty-hint string visible. Click Refresh; assert dirty-hint disappears.

### 7.3 Architectural-rule tests

Already in place from chunk 3. AST allow-list scanner auto-covers the new modules.

### 7.4 pyproject.toml additions

```toml
[project.optional-dependencies]
dev = [
    # ... existing dev deps ...
    "playwright>=1.45",
    "pytest-playwright>=0.5",
]
```

### 7.5 README addition

Append a "Run the e2e tests" section after the existing "Run the app" section:

````
## Run the e2e tests

```powershell
micromamba run -n shiny playwright install chromium
micromamba run -n shiny pytest tests/test_*_e2e.py -q
```

The `playwright install chromium` step downloads ~150 MB of browser binaries
and is required once per dev machine. CI integration is deferred to chunk 4b.
````

### 7.6 Verification-strength contract

Every acceptance-critical assertion in §7.2 is **identity-anchored**, not position-anchored:

- "Loops table contains the eutrophication–governance balancing loop" → label+polarity tuple match across all rows, sourced from introspected `_curonian_fixtures`.
- "6 compartments render" → `=== 6` via `page.evaluate` on vis.js's data model.
- "Loop highlight uses red + dim others + diamond on nodes" → THREE assertions: red color, 0.3 opacity, diamond shape (all three redundant cues).
- "Heatmap re-renders on metric change" → src change AND `naturalWidth > 0` (catches blank-canvas regression).
- "Refresh clears selection state" → cell_selection.rows AND zero red edges.

The verification-strength contract exists because earlier draft tests would have passed under silent regressions (wrong column shown, blank PNG, stale highlight surviving Refresh).

---

## 8. Acceptance criteria (chunk 4a subset of v1 §10.5)

| Criterion (parent §10.5) | Covered by | Strength |
|---|---|---|
| `multises.validate(seed_curonian()) == []` | chunk-1 tests | STRONG |
| App opens cleanly | chunk-3 `test_app_module_loads` | STRONG |
| Comparative all 5 cards render | `test_comparative_e2e.py` (5 `.comparative-card`) | STRONG |
| `response_pressure_gap()` shows ≥ 2 uncovered Pressures | `test_comparative_e2e.py` (`ul.orphan` count + introspected labels) | STRONG |
| Cross-view composite digraph renders 6 compartments | `test_cross_view_e2e.py` (`page.evaluate` `=== 6`) | STRONG |
| Cross-loop table includes eutrophication–governance balancing loop | `test_cross_view_e2e.py` (label+polarity search, position-independent) | STRONG |
| Save → reload → identical-via-deep-equal | chunk-1 tests | STRONG |
| 4 e2e tests pass against `shiny run app.py` | **2 of 4 from chunk 4a**; the remaining 2 ship in chunk 4b | n/a (gate) |

**Chunk-4a ship gate:** §7.1 + §7.2 tests pass + manual smoke verification of the loop-highlight cleanup-on-Refresh on the Curonian seed (Risk 1 is a chunk-3-Invariant-3-class load-bearing runtime check, consistent with the verify-before-push pattern from the saved feedback memory).

---

## 9. Implementation hint — Task 0 of the plan

Each probe is a 2–5-line script with a pass/fail expectation. Any failure is a design-revision trigger before the rest of the plan executes.

1. **`build_composite_digraph` extensibility** — verify the current signature accepts the two new kwargs cleanly; existing 241-test suite must stay green after the change.
2. **`response_pressure_gap` actual columns** — call `response_pressure_gap(seed_curonian())`; print `.columns`; confirm `pressure_compartment_has_no_governance` boolean is the split key; capture which Pressures land on each side.
3. **Shiny 1.5 `@render.data_frame` selection API** — verify `render.DataGrid(df, selection_mode="row")` and confirm `data_frame_output.cell_selection()` shape (`{"rows": (...), "cols": (...)}` or actual); confirm a write-side `update_cell_selection({"rows": ()})` (or equivalent) exists for the Refresh cleanup contract.
4. **`pyvis.shiny.render_pyvis_network`** — confirm import works in installed pyvis; capture (a) the DOM id/selector for the canvas, (b) the JS-side accessor for the vis.js `Network` (global registry, element attr, or other). The §4.2 JS handler is rewritten to match.
5. **`shiny.pytest.create_app_fixture` + `shiny.run.ShinyAppProc` + `shiny.playwright.controller`** — Shiny 1.5.1 verified surface (see plan Task 0 Probe 5). `shiny.testing` does NOT exist in this Shiny version. The fixture returns a `ShinyAppProc` with a `.url` attribute; Playwright `page.goto(app.url)` drives the navigation.
6. **`reactive.event` + `reactive.isolate` interaction** — 10-line probe app; toggling `unrelated` does NOT trigger an effect decorated with `@reactive.event(input.refresh)` + `with reactive.isolate(): input.unrelated()`.
7. **`multises_app/colors.py` precondition** — land the new module first; `topology.py` refactored to import from it; existing 241-test suite green.
8. **Channels-JSON rendering metadata** — confirm chunk-3 `topology.py`'s pattern is reusable in `comparative.py` card 5 and `cross_view.py` card 1.
9. **Playwright headless launch** — `playwright install chromium`; one-line `shiny run app.py` subprocess; verify headless chromium can reach the URL.
10. **`CrossLoop` dataclass shape** — already verified inline against `composite.py:144–167`: fields `id`, `nodes` (with closing node), `compartments_visited`, `length` (distinct-edge count), `polarity_type` (`"Reinforcing"`|`"Balancing"`), `channel_types_used`, `polarity_string`. No `loop.edges` attribute; edges derived from consecutive `nodes` pairs.
11. **`MultiSES.__eq__` semantics** (Risk 12) — verify whether equality is structural or reference; if structural, the dirty-hint tuple stores `id(ms)` (already encoded in `_rebuild_composite` per §4.2); confirm assumption holds.
12. **Heatmap render-cost benchmark** (Cost-1 / Hidden-1) — run the heatmap matplotlib path at `dpi=72` with `bbox_inches=None` against the Curonian seed; benchmark; assert under 500ms per render. If slower, demote card 2 to a per-card refresh button (escape hatch documented in §2).
13. **`inter_compartment_metrics` return shape** (Domain-6) — confirm `channel_in_degree`, `channel_out_degree`, `betweenness` are all present per compartment; capture key names for the bar-chart server code.
14. **`nx.eigenvector_centrality` convergence** (Hidden-3) — run against the Curonian-seed composite; if `PowerIterationFailedConvergence` raised, confirm `nx.eigenvector_centrality_numpy` returns a valid dict.

---

## 10. Hand-off

After this design is approved, invoke `superpowers:writing-plans` to produce the chunk-4a implementation plan. The plan's terminal state is the chunk-4a ship gate per §8.

---

## 11. Revision history

- **2026-05-15 v1** — first version after brainstorming session.
- **2026-05-15 v2 (in-loop review revision)** — 3 parallel review agents (spec-compliance, architectural-soundness, test-coverage) flagged 12 findings. Addressed: module decorator pattern, `response_pressure_gap` column, `build_composite_digraph` kwarg count, reactive isolation, `@render.data_frame` selection API, `pyvis.shiny.render_pyvis_network`, cycles-only filter, reactive.value scoping, test verification strength, `tests/test_composite_filters.py`, Task 0 probes expanded from 4 to 10, `CrossLoop` shape.
- **2026-05-15 v3 (multi-angle review revision)** — 4 parallel review agents (risk/silent-corruption, performance/cost, scientific/domain-UX, maintainability/cross-chunk/a11y) flagged 37 findings. ~25 applied autonomously into v3 (Critical + Important with clear fixes); ~12 deferred to chunk 4b polish or plan-execution time. Major changes:
  - **Risk 1 (chunk-3-Invariant-3 analog)**: Refresh effect now sends `clear_highlight` + clears DataGrid `cell_selection`; JS handler nulls `originalEdges`/`originalNodes` so post-rebuild highlights recapture the new network's baseline.
  - **Risk 2 (stale `cross_loops_calc`)**: `cross_loops_calc` now reads only `last_built_loops()`; new `_invalidate_cache_on_data_change` effect sets caches to None on upstream edit, surfacing a "data changed — click Refresh" warning.
  - **Risk 3 (cycles_only inconsistency)**: new `last_built_loops` `reactive.value` — single source of truth for both card 1's restriction and card 2's table.
  - **Cost-1 / Hidden-1 (matplotlib slowness)**: `dpi=72` + `bbox_inches=None`; measured at ~200ms; per-card refresh-button is the documented escape hatch if real-world data scales worse.
  - **Domain-2 (global top-K heatmap structurally sparse)**: switched to **per-compartment top-K** — each compartment row shows its own top-K central elements; no more 5/6 rows of zeros.
  - **Domain-1 (centrality default)**: changed from `degree` to `betweenness` — reveals cross-compartment Driver→Pressure→Response chains, the EG/DAPSI(W)R(M) value proposition.
  - **Domain-6 (bridge bar chart degenerate)**: 3-bar group per compartment (in-degree / out-degree / betweenness) instead of single betweenness on a 6-node graph.
  - **Domain-3 (system-wide governance gap missing)**: new badge listing Pressure labels with zero governance coverage in any compartment.
  - **Hidden-3 (eigenvector convergence)**: explicit fallback to `nx.eigenvector_centrality_numpy`.
  - **Maint-2 (`_ARCHETYPE_COLORS` private import)**: promoted to public `multises_app/colors.py` as a chunk-4a precondition.
  - **Maint-3 (4b write paths)**: forward note documenting `MultiSESState.update_metadata(...)` as a 4b deliverable.
  - **Maint-5 (alt text on @render.image)**: dynamic `alt` text contract for heatmap and bridge bar chart.
  - **Maint-7 (aria-live dirty-hint)**: wrapped in `<div role="status" aria-live="polite">`.
  - **Maint-8 (loop highlight node parity)**: nodes get size 1.4× + diamond shape as redundant cues alongside color + opacity + border-width.
  - **Risk 6 / Domain-8**: pre-Refresh placeholder + empty-filter-combo placeholder.
  - **Risk 10**: sticky disclaimer ABOVE the orphan/covered lists (travels in screenshots); list headings explicitly per-compartment-scoped.
  - **Risk 11**: introspected `tests/_curonian_fixtures.py` derives expected labels from `seed_curonian()` itself; assertions anchor on those constants so seed drift surfaces as a deliberate sanity-check failure, not a stealth e2e break.
  - Task 0 probes expanded from 10 to 14 (added heatmap benchmark, eigenvector convergence, inter_compartment_metrics shape, MultiSES `__eq__`).
  - Deferred to chunk 4b: pyvis tabular fallbacks for SR users, JS extraction to `/static/`, external-API contract tests, dim-intensity tuning if 30% proves insufficient on the Curonian seed.
