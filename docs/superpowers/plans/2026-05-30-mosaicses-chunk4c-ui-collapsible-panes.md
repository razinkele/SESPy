# MosaicSES chunk-4c-ui — Collapsible Panes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MosaicSES's per-page control panes collapsible (Topology list + inspector, Cross-view filters) using native bslib sidebars so the graph/canvas reclaims width, with zero custom JS and all server input/output ids preserved.

**Architecture:** Convert fixed `ui.layout_columns`/toolbar control panes into native `ui.layout_sidebar` + `ui.sidebar(open="desktop", id=…)`. Topology becomes two nested `layout_sidebar`s (left list + right inspector around the canvas); Cross-view's horizontal filter toolbar moves into a collapsible left sidebar; Comparative's two graph cards gain `full_screen=True`. Only the `*_ui` functions change — servers, JS handlers, and every bound id are untouched.

**Tech Stack:** Python, Shiny for Python 1.6.1 (bslib `sidebar`/`layout_sidebar`/`card`), pyvis, pytest, Playwright (e2e).

**Spec:** `SESPy/docs/superpowers/specs/2026-05-30-mosaicses-chunk4c-ui-collapsible-panes-design.md`

**Repo:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES` (work on local `main`, per chunk-4a/4b precedent; start only after chunk-4b is pushed to `origin/main`).

**Environment:** all commands run in the `shiny` micromamba env — prefix with `micromamba run -n shiny`.

---

## Task -1: Hard start-gate (chunk-4b must be on origin first)

> **Review finding I3/I5 (Critical sequencing):** as of 2026-05-30, local `main` is **7 commits ahead** of `origin/main` — chunk-4b is NOT yet pushed. If 4c starts now, its commits stack on unpushed 4b and a single push ships both chunks together, conflating their smoke gates. This gate must pass before ANY 4c work.

- [ ] **Verify 4b is shipped.** Run:

```bash
git rev-list --count origin/main..HEAD
```

Expected: `0` (origin/main == local main, 4b pushed). **If non-zero, STOP** — the user must run the chunk-4b smoke checklist (`docs/2026-05-18-chunk4b-smoke-checklist.md`) and `git push origin main` first. Do not begin Task 0 until this returns 0.

- [ ] **Confirm clean-ish tree.** Run `git status --short`. Expected: only the intentional `M .gitignore` (user-managed `.superpowers/` entry — leave untouched) and possibly `.tmp/` scratch (gitignored). No staged changes.

### Commit hygiene (applies to every task below)

All commits use **path-scoped `git add`** with explicit file paths only — NEVER `git add -A` or `git add .`. The modified `.gitignore` and all `.tmp/` scratch files must remain untouched/unstaged. (Review finding M6.)

### Rollback path (work is on `main`, not a branch)

If the manual smoke gate (Task 5) fails: **fix forward** with a new commit when the fault is localized. If unrecoverable, `git revert` the chunk-4c commits — they are isolated to `*_ui` functions + their tests + two new docs, so a clean revert restores the 4b baseline. If the e2e suite cannot be made green (Task 4), **STOP and escalate to the user — do not push.** (Review finding I4.)

---

## Probe results (verified 2026-05-30 via `.tmp/probe_chunk4c.py`)

- `shiny.__version__ == "1.6.1"`.
- `ui.sidebar(*args, width, position, open, id, title, bg, fg, class_, gap, padding, max_height_mobile, gap_mobile, **kwargs)` — all needed kwargs supported.
- `ui.layout_sidebar(*args, fillable, **kwargs)` — the sidebar is the first positional arg; the rest is main content.
- `ui.card(...)` accepts `full_screen`.
- Nested `layout_sidebar(sidebar(left), layout_sidebar(sidebar(right, position="right"), card(full_screen=True)))` renders cleanly (6760 chars, both sidebar ids + all titles present). **The single-sidebar fallback from spec §5 is NOT needed.**

**Source facts that shape the tasks (verified in the modules, 2026-05-30):**
- `topology.py` canvas card has **no** `full_screen` today → add it.
- `cross_view.py` composite card has **no** `full_screen` today → add it. Its status output id is `composite_canvas_status` (an `output_ui`), the canvas uses `show_status=False`, bridge uses `ui.output_image("bridge_chart")`, every card carries `class_="cross-view-card"`, and the module ends with `ui.tags.script(_CROSS_VIEW_JS)` — all must be preserved.
- `comparative.py` heatmap (`output_image("heatmap")`) and meta-graph (`output_pyvis_network("meta_graph_canvas")`) cards have **no** `full_screen` today → add it; every card carries `class_="comparative-card"`.

**Runtime hazards the probe must close before coding (review finding C2 — pyvis height/transform):**

The pyvis canvas reflows *width* automatically via a `ResizeObserver` in `pyvis/shiny/bindings.js` (so collapse→widen works), but its *height* is read from `canvasDiv.offsetHeight`. Under the shell's `page_sidebar(fillable=True)` + the new nested `layout_sidebar` + `full_screen`, a host with no height floor can read 0 → blank canvas with no error. The shell CSS guard only floors `.pyvis-container` min-height (one level too deep to rescue a 0-height host) and applies `transform:none!important` to `.card:has(.pyvis-network-output)`, which can fight bslib's full-screen transform.

### Task 0 — Step 1: Probe the height/full-screen interaction and add a CSS guard if needed

- [ ] Launch the app (`micromamba run -n shiny shiny run app.py`) and, in the browser DevTools console, after navigating to Topology, run:
  `var c=document.querySelector('#topology-network canvas')||document.querySelector('.pyvis-network-output canvas'); c && [c.offsetWidth, c.offsetHeight]`
  Confirm both are non-zero (a) on load, (b) after collapsing both sidebars, (c) after entering full-screen on the canvas card. Repeat for cross-view `#cross_view-composite_canvas` and the comparative meta-graph.
- [ ] **If any height reads 0 or a full-screen canvas is scaled/offset:** add a height floor to the shell skin OR set an explicit `height=`/`min_height=` on the affected card. The minimal guard (add to `app.py`'s inline `<style>` block, which already holds chunk-4a stubs):
  ```css
  .card:has(.pyvis-network-output) .pyvis-network-output { min-height: 400px; }
  ```
  If the full-screen transform conflict appears, scope the existing `transform:none` guard to exclude the full-screen state (e.g. `.card:not(.bslib-full-screen):has(.pyvis-network-output){transform:none!important}`). Record exactly which guard (if any) was needed.
- [ ] Record results (the three offset checks per canvas + any guard added) in `docs/2026-05-30-chunk4c-ui-probe-results.md` alongside the bullet facts above, then delete the scratch probe: `rm .tmp/probe_chunk4c.py`.

- [ ] **Commit** (include the CSS guard in app.py only if Step 1 found it necessary)

```bash
git add docs/2026-05-30-chunk4c-ui-probe-results.md
# git add app.py   # ONLY if a CSS guard was required
git commit -m "docs(mosaicses): chunk-4c-ui Task 0 probe results"
```

---

## Task 1: Topology — two collapsible sidebars around the canvas

Convert `topology_ui`'s `ui.layout_columns(col_widths=[3,6,3])` into two nested `layout_sidebar`s and add `full_screen=True` to the canvas card. The wrapping `<div id="topology-compartments-list|topology-canvas|topology-inspector">` ids disappear (they were only `layout_columns` scaffolding), so the existing structural test is updated to assert the new sidebar ids. Server is untouched: ids `compartments_list`, `network`, `inspector_target`, `inspector_detail` all survive.

**Files:**
- Modify: `multises_app/modules/topology.py` (the `topology_ui` function only, ~lines 200-234)
- Test: `tests/test_topology_module.py` (update `test_topology_ui_contains_three_column_cards`, add one test)

- [ ] **Step 1: Update the now-stale structural test and add the new one**

In `tests/test_topology_module.py`, REPLACE `test_topology_ui_contains_three_column_cards` (lines 21-29) with:

```python
def test_topology_ui_uses_collapsible_sidebars():
    """The 3-column layout is now two nested collapsible sidebars (left
    Compartments list + right Inspector) around the canvas. Assert the new
    sidebar ids, the bslib sidebar markup, and that the three section titles
    plus all four server-bound ids survive the conversion."""
    # NOTE: layout_sidebar() returns a CardItem, NOT a Tag — str() on it gives a
    # bare object repr (~54 chars), so we MUST .tagify() to get real HTML. (This
    # is why the current test could use str() directly: layout_columns returns a
    # Tag. Review finding, verified in shiny 1.6.1.)
    html = str(topology.topology_ui("topology").tagify())
    # bslib sidebar layout present (the inspector is on the RIGHT, and both
    # sidebars are collapsible + open-on-desktop — the whole point of the chunk)
    assert "bslib-sidebar-layout" in html
    assert "sidebar-right" in html                       # inspector on the right
    assert 'data-open-desktop="open"' in html            # open on desktop
    assert "collapse-toggle" in html                     # actually collapsible
    # stable sidebar ids — bslib namespaces the id with the module prefix, so
    # the rendered id/aria-controls is "topology-<id>" (verified, shiny 1.6.1).
    assert 'aria-controls="topology-topology_inspector_sb"' in html
    assert "topology_list_sb" in html
    assert "topology_inspector_sb" in html
    # server-bound ids preserved — assert the module-namespaced container ids so
    # the check can't pass via an incidental CSS class (e.g. "pyvis-network").
    assert 'id="topology-network"' in html
    assert "compartments_list" in html
    assert "inspector_target" in html
    assert "inspector_detail" in html
    # section titles preserved (sidebar titles + card header)
    assert "Compartments" in html
    assert "Inspector" in html
    assert "Topology" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `micromamba run -n shiny pytest tests/test_topology_module.py::test_topology_ui_uses_collapsible_sidebars -v`
Expected: FAIL — `bslib-sidebar-layout` / `topology_list_sb` not present (still `layout_columns`). (The test renders via `.tagify()`, so this is a true red — the markers are genuinely absent, not hidden behind a bare-`str` repr.)

- [ ] **Step 3: Replace the `topology_ui` body**

In `multises_app/modules/topology.py`, replace the entire `topology_ui` function (from `@module.ui` through the closing `)` of the `return`) with:

```python
@module.ui
def topology_ui() -> ui.Tag:
    """Collapsible-pane layout: left Compartments sidebar + right Inspector
    sidebar (both collapse on a chevron, open on desktop) around the central
    pyvis canvas. Server-bound ids are unchanged from the chunk-3 layout."""
    return ui.layout_sidebar(
        ui.sidebar(
            ui.output_ui("compartments_list"),
            id="topology_list_sb",
            title="Compartments",
            position="left",
            open="desktop",
            width=300,
        ),
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_select(
                    "inspector_target",
                    "Inspect:",
                    choices={},  # populated reactively by _update_inspector_choices
                ),
                ui.output_ui("inspector_detail"),
                id="topology_inspector_sb",
                title="Inspector",
                position="right",
                open="desktop",
                width=320,
            ),
            ui.card(
                ui.card_header("Topology"),
                output_pyvis_network("network", height="650px",
                                     show_toolbar=False, show_search=False,
                                     show_layout_switcher=False, show_export=True,
                                     show_status=False),
                full_screen=True,
            ),
        ),
    )
```

- [ ] **Step 4: Update the now-stale module docstring (review finding I2)**

The conversion makes the "3-column layout" language false. In `multises_app/modules/topology.py`:
- Module header (lines ~6-11): change "3-column layout — compartments list (left), pyvis canvas (centre), inspector (right)" to describe the collapsible-sidebar layout (left Compartments sidebar + right Inspector sidebar around the canvas).
- The `topology_ui` one-liner was already replaced in Step 3 (no longer `"""3-column layout shell."""`). Confirm no other in-file comment still says "3-column".

- [ ] **Step 5: Run the topology module suite**

Run: `micromamba run -n shiny pytest tests/test_topology_module.py -v`
Expected: PASS — the new test plus all unchanged helper tests (`test_topology_ui_returns_a_tag`, `_compartment_summary_rows`, `_build_topology_network*`, `_inspector_node_info*`).

- [ ] **Step 6: Commit**

```bash
git add multises_app/modules/topology.py tests/test_topology_module.py
git commit -m "feat(mosaicses): topology collapsible list+inspector sidebars (chunk-4c-ui)"
```

---

## Task 2: Cross-view — filter toolbar → collapsible left sidebar

Move the filter toolbar (`dapsi`/`channels`/`cycles_only` switches, `types` selectize, `refresh` button, `dirty_hint` aria-live status) into a collapsible left `ui.sidebar`. Keep the composite/loops/bridge cards as the `layout_sidebar` main content, preserving their `cross-view-card` classes, the `composite_canvas_status` output, `output_image("bridge_chart")`, the `_CROSS_VIEW_JS` script tag, and adding `full_screen=True` to the composite card. Server + JS untouched.

**Files:**
- Modify: `multises_app/modules/cross_view.py` (the `cross_view_ui` function only, lines 167-204)
- Test: `tests/test_cross_view_module.py` (add one test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cross_view_module.py`:

```python
def test_cross_view_filters_in_collapsible_sidebar():
    """The filter toolbar moves into a collapsible left sidebar. All filter
    input ids, the three card output ids, the cross-view-card classes, and the
    JS handler script must survive."""
    from multises_app.modules.cross_view import cross_view_ui
    # layout_sidebar returns a CardItem (not a Tag) → str() gives a bare repr;
    # MUST .tagify() to get HTML. (Verified shiny 1.6.1.)
    html = str(cross_view_ui("cv").tagify())
    # the filters live in a collapsible, open-on-desktop LEFT sidebar
    assert "bslib-sidebar-layout" in html
    assert "collapse-toggle" in html                  # actually collapsible
    assert 'data-open-desktop="open"' in html         # open on desktop
    assert "cross_view_filters_sb" in html
    # filter input ids preserved — assert module-namespaced ids so the check
    # can't pass via incidental label text (e.g. the button label "Refresh").
    for _id in ("cv-dapsi", "cv-channels", "cv-cycles_only", "cv-types", "cv-refresh"):
        assert f'id="{_id}"' in html
    # content-pane output ids preserved (composite_canvas distinct from _status)
    assert 'id="cv-composite_canvas"' in html
    for _id in ("composite_canvas_status", "loops_table", "bridge_chart", "dirty_hint"):
        assert _id in html
    # the aria-live status wrapper survives the move into the sidebar
    assert 'role="status"' in html and 'aria-live="polite"' in html
    assert html.count("cross-view-card") == 3
    assert "Composite graph" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `micromamba run -n shiny pytest tests/test_cross_view_module.py::test_cross_view_filters_in_collapsible_sidebar -v`
Expected: FAIL — `bslib-sidebar-layout` / `cross_view_filters_sb` not present (current body is a `ui.div` with `cross-view-toolbar`). Test renders via `.tagify()`, so this is a true red.

- [ ] **Step 3: Replace the `cross_view_ui` body**

In `multises_app/modules/cross_view.py`, replace the entire `cross_view_ui` function (lines 167-204, `@module.ui` through the closing `)`) with:

```python
@module.ui
def cross_view_ui() -> ui.Tag:
    """Collapsible-pane layout: filters live in a left sidebar that collapses on
    a chevron (open on desktop), freeing the composite-graph canvas to reclaim
    width. All filter + output ids and the JS handler are unchanged from
    chunk-4a; the composite card gains full_screen."""
    return ui.layout_sidebar(
        ui.sidebar(
            ui.input_switch("dapsi", "DAPSI elements", value=True),
            ui.input_switch("channels", "Channels", value=True),
            ui.input_switch("cycles_only", "Cross-compartment cycles only", value=False),
            ui.input_selectize("types", "Channel types",
                               choices=CHANNEL_TYPES_DEFAULT,
                               multiple=True,
                               selected=CHANNEL_TYPES_DEFAULT),
            ui.input_action_button("refresh", "Refresh ⟳", class_="btn-primary"),
            ui.tags.div(ui.output_ui("dirty_hint"), role="status",
                        **{"aria-live": "polite"}),
            id="cross_view_filters_sb",
            title="Filters",
            position="left",
            open="desktop",
            width=300,
        ),
        # Main content pane — reclaims width when the sidebar collapses.
        # Card 1: hero composite viewer (now full-screen capable).
        ui.card(ui.card_header("Composite graph"),
                ui.output_ui("composite_canvas_status"),
                output_pyvis_network("composite_canvas", height="600px",
                                     show_toolbar=True, show_search=True,
                                     show_layout_switcher=True, show_export=True,
                                     show_status=False),
                class_="cross-view-card cross-view-hero",
                full_screen=True),
        # Cards 2 + 3 in bottom row
        ui.row(
            ui.column(6, ui.card(ui.card_header("Cross-compartment loops"),
                                 ui.output_data_frame("loops_table"),
                                 class_="cross-view-card")),
            ui.column(6, ui.card(ui.card_header("Bridge metrics"),
                                 ui.output_image("bridge_chart"),
                                 class_="cross-view-card")),
        ),
        # JS handler block (unchanged — loop-highlight custom message handlers)
        ui.tags.script(_CROSS_VIEW_JS),
    )
```

- [ ] **Step 4: Run the cross_view module suite**

Run: `micromamba run -n shiny pytest tests/test_cross_view_module.py -v`
Expected: PASS — the new test plus the pre-existing `test_cross_view_ui_renders_filter_toolbar_and_3_cards` (filter ids + ≥3 `cross-view-card`) and `test_dirty_hint_container_has_aria_live` (the dirty_hint div keeps `role="status"` + `aria-live="polite"`).

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/cross_view.py tests/test_cross_view_module.py
git commit -m "feat(mosaicses): cross-view filters in collapsible sidebar (chunk-4c-ui)"
```

---

## Task 3: Comparative — full-screen the two graph cards

Add `full_screen=True` to the centrality-heatmap card and the meta-graph card so the user can maximize them. No layout restructure; `class_="comparative-card"` preserved on every card; server untouched.

**Files:**
- Modify: `multises_app/modules/comparative.py` (the `comparative_ui` function, the heatmap card ~lines 197-204 and meta-graph card ~lines 213-218)
- Test: `tests/test_comparative_module.py` (add one test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_comparative_module.py`:

```python
def test_comparative_graph_cards_are_full_screen():
    """The heatmap and meta-graph cards expose bslib's full-screen control.
    The 5-card count and comparative-card classes are unchanged."""
    from multises_app.modules.comparative import comparative_ui
    # comparative_ui returns a ui.div (a Tag), so str() expands to HTML here —
    # no .tagify() needed (unlike the layout_sidebar tasks). Verified 1.6.1.
    html = str(comparative_ui("test_id"))
    # EXACTLY two cards become full-screen capable (heatmap + meta-graph) — the
    # count guards against a stray third full_screen card. bslib emits both the
    # data attribute and the enter-toggle class for full_screen=True.
    assert html.count("bslib-full-screen-enter") == 2
    assert html.count('data-full-screen="false"') == 2
    # five cards total, unchanged (matches the e2e == 5 invariant)
    assert html.count("comparative-card") == 5
    # both graph outputs still present
    assert 'id="test_id-heatmap"' in html
    assert 'id="test_id-meta_graph_canvas"' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `micromamba run -n shiny pytest tests/test_comparative_module.py::test_comparative_graph_cards_are_full_screen -v`
Expected: FAIL — `bslib-full-screen-enter` count is 0 (no card is full_screen yet), so the `== 2` assertion fails.

- [ ] **Step 3: Add `full_screen=True` to the two graph cards**

In `multises_app/modules/comparative.py`, in `comparative_ui`, change the heatmap card — find:

```python
        ui.card(ui.card_header("Centrality heatmap"),
                ui.input_select("metric", "Metric",
                                choices=["betweenness", "degree", "closeness", "eigenvector"],
                                selected="betweenness"),
                ui.input_slider("top_k", "Top-K elements per compartment",
                                min=5, max=20, value=10, step=1),
                ui.output_image("heatmap"),
                class_="comparative-card"),
```

replace its trailing `class_="comparative-card"),` with `class_="comparative-card", full_screen=True),`.

Then the meta-graph card — find:

```python
        ui.card(ui.card_header("Compartment meta-graph"),
                output_pyvis_network("meta_graph_canvas", height="350px",
                                     show_toolbar=False, show_search=False,
                                     show_layout_switcher=False, show_export=False,
                                     show_status=False),
                class_="comparative-card"),
```

replace its trailing `class_="comparative-card"),` with `class_="comparative-card", full_screen=True),`.

(Leave the Vital signs, Global leverage, and Response–Pressure gap cards unchanged.)

- [ ] **Step 4: Run the comparative module suite**

Run: `micromamba run -n shiny pytest tests/test_comparative_module.py -v`
Expected: PASS — the new test plus the pre-existing `test_comparative_ui_renders_5_cards` and all helper tests.

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/comparative.py tests/test_comparative_module.py
git commit -m "feat(mosaicses): full-screen heatmap + meta-graph cards (chunk-4c-ui)"
```

---

## Task 4: Full unit suite + e2e regression check

The conversions change the DOM. Run the whole suite, then the Playwright e2e tests. **One e2e selector break is certain, not contingent** (review finding C1) — fix it as a mandatory step. No behavioral assertions change (spec §6) — only locators move.

**Files (mandatory edit — see Step 3):**
- `tests/test_cross_view_e2e.py`
- `tests/test_comparative_e2e.py` (verify only; expected no change)

- [ ] **Step 1: Run the full unit suite (excluding e2e)**

Run: `micromamba run -n shiny pytest tests/ -q --ignore=tests/test_cross_view_e2e.py --ignore=tests/test_comparative_e2e.py`
Expected: PASS. Baseline chunk-4b was 272 unit (verified at HEAD 52bcadb); this adds 3 new tests and replaces 1 (topology 1-for-1) → **275 unit**. If any non-e2e test fails on old structure, update only its structural assertion (keep behavior identical) and re-run.

- [ ] **Step 2: MANDATORY pre-emptive e2e selector fix (review finding C1)**

`tests/test_cross_view_e2e.py:33` does `page.wait_for_selector(".cross-view-toolbar", timeout=10_000)`. Task 2 **removed** that wrapper div (`cross-view-toolbar` now exists nowhere — grep confirms it lived only in the source line removed + this test line), so this wait WILL time out and fail before the loop-highlight invariant is even reached. Fix it now — replace line 33's selector with one that exists in the new DOM. Prefer the preserved aria-live status (stable, not layout-coupled):

```python
    page.wait_for_selector("[role='status'][aria-live='polite']", timeout=10_000)
```

(Alternative if a more specific anchor is wanted: `input[id$='-dapsi']`, a preserved filter input.) Do NOT change any assertion — only this locator. Scan the rest of `test_cross_view_e2e.py` and `test_comparative_e2e.py` for any other `.cross-view-toolbar` / column-index locator; the other cross-view locators (`#cross_view-composite_canvas .vis-network`, `button:has-text("Refresh")`, `input[id$="-cycles_only"]`, `[role="status"]`, `table tbody tr`) and all comparative locators are preserved (verified) and need no change.

- [ ] **Step 3: Run the e2e suite**

Run: `micromamba run -n shiny pytest tests/test_cross_view_e2e.py tests/test_comparative_e2e.py -v`
Expected: 2 PASS (~70-120s, full app boot). The chunk-4a loop-highlight invariant in `test_cross_view_e2e.py` MUST still pass. **Note:** `test_comparative_e2e.py:34` asserts `cards.count() == 5` (exact). Task 3 only adds `full_screen` to existing cards (adds no card), so this stays at 5 — **do NOT loosen `== 5` to `>= 5`** to match the unit test (review finding I6). If a comparative locator unexpectedly broke, fix the locator only; if `== 5` genuinely changed, STOP — that means a card was added/removed, which is out of scope.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cross_view_e2e.py
git commit -m "test(mosaicses): update cross-view e2e selector for collapsible filters (chunk-4c-ui)"
```

---

## Task 5: Manual smoke checklist doc (ship gate)

Per `[[feedback_runtime_verify_before_shared_state]]`, collapse-reflow is render state the unit/e2e tests cannot fully observe. Author the checklist; the USER runs it in a real browser before push.

**Files:**
- Create: `docs/2026-05-30-chunk4c-ui-smoke-checklist.md`

- [ ] **Step 1: Write the checklist**

Create `docs/2026-05-30-chunk4c-ui-smoke-checklist.md`:

```markdown
# Chunk-4c-ui manual smoke checklist

Launch: `micromamba run -n shiny shiny run --launch-browser app.py`

## Topology
- [ ] Left "Compartments" sidebar shows the compartment list; chevron collapses it; canvas widens.
- [ ] Right "Inspector" sidebar shows the inspect dropdown + detail; chevron collapses it; canvas widens further.
- [ ] Collapse BOTH → canvas near-full-width. Expand each back → list + inspector return.
- [ ] **DevTools height check (review finding C2):** with DevTools console, run `var c=document.querySelector('.pyvis-network-output canvas'); c&&[c.offsetWidth,c.offsetHeight]` — both non-zero after (a) load, (b) collapse-both, (c) full-screen enter. A zero height = the height-guard from Task 0 was needed and is missing.
- [ ] Inspector dropdown still selects compartments/channels and the detail updates.
- [ ] Canvas full-screen toggle works; graph fills the overlay (not scaled/offset — watch the transform-guard interaction); exits cleanly back to in-card size.
- [ ] **Full-screen WHILE a sidebar is collapsed:** collapse left + right, then enter full-screen on the canvas → graph fills overlay correctly.

## Cross-view
- [ ] "Filters" left sidebar holds the 3 switches + channel-type selectize + Refresh; chevron collapses it; composite canvas widens.
- [ ] All 4 filters + Refresh still drive the composite graph.
- [ ] Selecting a loop still highlights edges (chunk-4a loop-highlight invariant); Refresh clears it.
- [ ] dirty-hint status text appears when filters change before Refresh.
- [ ] Composite card full-screen toggle works; graph fills overlay; exits cleanly.

## Comparative
- [ ] Centrality-heatmap card enters/exits full-screen cleanly.
- [ ] Meta-graph card enters/exits full-screen cleanly; node click-to-navigate to Compartments still works (the one path no e2e covers — verify deliberately).

## Accessibility
- [ ] Each sidebar collapse toggle is reachable by Tab and operable with Enter/Space.
- [ ] Screen-reader spot-check: toggle announces expanded/collapsed (aria-expanded).

## Responsive (stale-width reflow — review finding C2)
- [ ] Narrow window / mobile width: sidebars start collapsed (open="desktop").
- [ ] At mobile width, on BOTH Topology and Cross-view: expand a sidebar that started collapsed, then collapse it again → the canvas (first laid out while collapsed) re-fits each time and is never clipped or zero-size.

## Ship
- [ ] All above green → `git push origin main`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/2026-05-30-chunk4c-ui-smoke-checklist.md
git commit -m "docs(mosaicses): chunk-4c-ui manual smoke checklist"
```

---

## Definition of done

- [ ] Topology renders two collapsible sidebars (list + inspector) around a full-screen-capable canvas; all 4 ids preserved.
- [ ] Cross-view filters live in a collapsible left sidebar; all filter + output ids + `_CROSS_VIEW_JS` preserved; composite card full-screen.
- [ ] Comparative heatmap + meta-graph cards are full-screen capable; 5-card layout intact.
- [ ] `app.py` untouched.
- [ ] Full unit suite green (275 unit) + 2 e2e green, loop-highlight invariant intact.
- [ ] Probe doc + smoke checklist committed.
- [ ] User runs smoke checklist → green → `git push origin main`.

## Spec-coverage self-check

- Spec §4.1 Topology two sidebars → Task 1 ✓
- Spec §4.2 Cross-view toolbar→sidebar → Task 2 ✓
- Spec §4.3 Comparative full_screen → Task 3 ✓ (spec said "already present"; source shows it was NOT — corrected to a real task)
- Spec §4.4/4.5 Compartments/Project Setup untouched → no task (correct) ✓
- Spec §5 Task-0 probe → done + recorded in Task 0 ✓
- Spec §6 tests + smoke → Tasks 1-5 ✓
- Spec §7 files touched → matches Tasks 1-5 (comparative.py IS modified, refining the spec which assumed full_screen pre-existed) ✓

## Type/name consistency self-check

- Sidebar ids used consistently: `topology_list_sb`, `topology_inspector_sb` (Task 1), `cross_view_filters_sb` (Task 2).
- Preserved output/input ids match source exactly: `compartments_list`, `network`, `inspector_target`, `inspector_detail` (topology); `dapsi`, `channels`, `cycles_only`, `types`, `refresh`, `dirty_hint`, `composite_canvas`, `composite_canvas_status`, `loops_table`, `bridge_chart` (cross-view); `heatmap`, `meta_graph_canvas` (comparative).
- `_CROSS_VIEW_JS` script tag retained in Task 2 (loop-highlight handlers depend on it).
```
