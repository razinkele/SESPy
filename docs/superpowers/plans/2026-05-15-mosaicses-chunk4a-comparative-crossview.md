# MosaicSES Chunk 4a — Comparative + Cross-view Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Comparative-grid panel (5 cards, fully reactive) and Cross-view composite-graph panel (3 cards + filter toolbar, refresh-gated for the hero) to MosaicSES, satisfying 2 of 4 v1-required e2e tests and unblocking chunk 4b's ship-checklist work.

**Architecture:** Two new Shiny modules (`comparative.py`, `cross_view.py`) decorated with `@module.ui`/`@module.server` mirroring chunk-3's topology/compartments shape. Read-only consumers of `state.active_multises` (read via `.get()` inside reactive contexts); no new top-level reactive.value. One library extension (two new filter kwargs on `build_composite_digraph`). One new public palette module (`multises_app/colors.py`) refactored out of chunk-3's private `_ARCHETYPE_COLORS`.

**Tech Stack:** Shiny for Python 1.5.1, pyvis (via `pyvis.shiny.render_pyvis_network`), NetworkX, matplotlib (dpi=72 explicit), Playwright + pytest-playwright for e2e. Python managed by `micromamba run -n shiny` (no venv, no pip-install — per user CLAUDE.md).

**Spec (source of truth):** [`../specs/2026-05-15-mosaicses-chunk4a-comparative-crossview-design.md`](../specs/2026-05-15-mosaicses-chunk4a-comparative-crossview-design.md) v3 — references like "spec §4.2" point there.

**Working directory for all commands:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES` (the MosaicSES git repo). Run pytest with `micromamba run -n shiny pytest tests/ -q`.

**Baseline at start of plan:** main branch at `80d0100`; `241 passed`.

**Pytest count expectations — read this before every `Expected: N passed` line.** Each task documents an approximate count (e.g., `Expected: 246 passed`) for orientation. The **load-bearing assertion is "no FAILED, no ERROR"** — exact counts may drift by ±2 if intermediate tasks add internal helper tests, or if a single test gets split during TDD. Treat counts as informational; reject the run only on actual failures/errors.

---

## Phase A — Task 0: Pre-implementation probes

Each probe is a 2–5-line micro-script run from the MosaicSES repo with `micromamba run -n shiny python -c "..."`. If any probe fails, **stop and revise the spec before proceeding** — this is the chunk-3 pre-spike pattern. None of these probes commit code; they capture knowledge into `docs/2026-05-15-chunk4a-probe-results.md`.

### Task 0: Run 14 probes capturing environment + API assumptions

**Files:**
- Create: `MosaicSES/docs/2026-05-15-chunk4a-probe-results.md` (probe log)

- [ ] **Step 1: Probe 1 — `build_composite_digraph` extensibility**

Run:
```powershell
micromamba run -n shiny python -c "import inspect; from multises.composite import build_composite_digraph; print(inspect.signature(build_composite_digraph))"
```
Expected: signature includes `channel_types: set[str] | None = None`. Append to probe log: confirms the existing kwarg can be reused; the two new kwargs can be added without renaming.

- [ ] **Step 2: Probe 2 — `response_pressure_gap` actual columns**

Run:
```powershell
micromamba run -n shiny python -c "from multises import seed_curonian; from multises.comparative import response_pressure_gap; df = response_pressure_gap(seed_curonian()); print(list(df.columns)); print('uncovered:', df['pressure_compartment_has_no_governance'].sum())"
```
Expected: columns include `pressure_compartment_has_no_governance`; uncovered count ≥ 2. Append to probe log.

- [ ] **Step 3: Probe 3 — Shiny 1.5 `@render.data_frame` selection API**

Run:
```powershell
micromamba run -n shiny python -c "import inspect; from shiny import render; print('DataGrid params:', list(inspect.signature(render.DataGrid).parameters))"
```
Expected: `selection_mode` is a `DataGrid` parameter. If absent, capture the actual selection API and adjust Task 12 accordingly.

- [ ] **Step 4: Probe 4 — `pyvis.shiny.render_pyvis_network` DOM convention**

Run:
```powershell
micromamba run -n shiny python -c "from pyvis.shiny import render_pyvis_network, output_pyvis_network; import inspect; print(inspect.getsourcefile(render_pyvis_network))"
```
Then read the printed source-file path with your IDE/editor and capture:
(a) the DOM id/selector emitted for the canvas,
(b) the JS-side global or attribute name used to access the vis.js `Network`.

Append capture to probe log. The JS handler in Task 10 and the `page.evaluate` calls in Task 19 use whatever this captures — adjust verbatim.

- [ ] **Step 5: Probe 5 — Shiny 1.5.1 test surface (`shiny.playwright` + `shiny.pytest` + `shiny.run.ShinyAppProc`)**

Run:
```powershell
micromamba run -n shiny python -c "import shiny; print('shiny', shiny.__version__); from shiny.run import ShinyAppProc; from shiny.playwright import controller; from shiny.pytest import create_app_fixture; print('OK: ShinyAppProc, playwright.controller, pytest.create_app_fixture')"
```
Expected: prints `shiny 1.5.1` and `OK: ...`. **`shiny.testing` does NOT exist in Shiny 1.5.1** — the real surfaces are `shiny.playwright` (DOM controllers like `controller.InputText`, `controller.OutputUI`), `shiny.pytest` (`create_app_fixture`), and `shiny.run` (`ShinyAppProc`, used by `create_app_fixture` internally). Task 16's fixture uses `create_app_fixture` directly. If this probe fails, capture the error and stop — chunk-4a's e2e plan depends on this surface.

- [ ] **Step 6: Probe 6 — `reactive.event` + `reactive.isolate` non-trigger**

Save the following as `MosaicSES/.tmp/probe6.py`:
```python
from shiny import App, ui, reactive, render
app_ui = ui.page_fluid(ui.input_action_button("r", "Refresh"), ui.input_text("u", "U"), ui.output_text("o"))
fired = [0]
def server(input, output, session):
    @reactive.effect
    @reactive.event(input.r)
    def _():
        with reactive.isolate():
            _ = input.u()
        fired[0] += 1
    @output
    @render.text
    def o():
        return str(fired[0])
app = App(app_ui, server)
```
Then run:
```powershell
micromamba run -n shiny python -c "exec(open('.tmp/probe6.py').read()); print('app constructed OK')"
```
Expected: app constructs without exception.

- [ ] **Step 7: Probe 7 — Capture `_ARCHETYPE_COLORS` contents**

Run:
```powershell
micromamba run -n shiny python -c "from multises_app.modules.topology import _ARCHETYPE_COLORS; print(repr(_ARCHETYPE_COLORS))"
```
Copy the printed `dict` literal into the probe log — Task 2 pastes it verbatim into `multises_app/colors.py`.

- [ ] **Step 8: Probe 8 — channels-JSON rendering metadata**

Run:
```powershell
micromamba run -n shiny python -c "from multises.channels import get_channel_types; ct = get_channel_types(); first = list(ct)[0]; print('channel type', first, '->', ct[first])"
```
Expected: dict-like access. If the accessor name differs, capture the actual public function name — Task 9 (card 5) + Task 11 (cross-view card 1) use it.

- [ ] **Step 9: Probe 9 — Playwright headless launch**

Run:
```powershell
micromamba run -n shiny playwright install chromium
```
Then:
```powershell
micromamba run -n shiny python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); print('launched:', b.version); b.close(); p.stop()"
```
Expected: prints a chromium version string. The `playwright install` downloads ~150 MB; one-time per dev machine.

- [ ] **Step 10: Probe 10 — `CrossLoop` dataclass shape (documentation-only)**

Run:
```powershell
micromamba run -n shiny python -c "from multises.composite import CrossLoop; import dataclasses; print([f.name for f in dataclasses.fields(CrossLoop)])"
```
Expected: `['id', 'nodes', 'compartments_visited', 'length', 'polarity_type', 'channel_types_used', 'polarity_string']`. Append to probe log.

- [ ] **Step 11: Probe 11 — `MultiSES.__eq__` semantics**

Run:
```powershell
micromamba run -n shiny python -c "from multises import seed_curonian; a = seed_curonian(); b = seed_curonian(); print('a is b:', a is b); print('a == b:', a == b)"
```
Expected: `a is b: False`. Record whether `a == b: True` (structural equality) or `False` (referential). Either is fine; the spec's `id(ms)` choice in the dirty-hint tuple is consistent with both.

- [ ] **Step 12: Probe 12 — heatmap render-cost benchmark**

Save the following as `MosaicSES/.tmp/probe12.py`:
```python
import time, io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from multises import seed_curonian
from multises.composite import build_composite_digraph
import networkx as nx

ms = seed_curonian()
g = build_composite_digraph(ms)
cent = nx.betweenness_centrality(g)
top_k = 10
compartments = [c.id for c in ms.compartments][:6]
rows = []
for cid in compartments:
    members = [(n, cent.get(n, 0.0)) for n in g.nodes if n.startswith(f"{cid}::")]
    members.sort(key=lambda x: -x[1])
    rows.append([v for _, v in members[:top_k]] + [0.0] * max(0, top_k - len(members)))
matrix = np.array(rows)

t0 = time.perf_counter()
for _ in range(3):
    fig, ax = plt.subplots(figsize=(8, 4), dpi=72)
    ax.imshow(matrix, aspect="auto")
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
t1 = time.perf_counter()
print(f"3 renders in {t1 - t0:.3f}s; per-render {(t1 - t0)/3*1000:.0f}ms")
```
Then:
```powershell
micromamba run -n shiny python .tmp/probe12.py
```
Expected: per-render under 500ms. If over, escalate — Task 6 (card 2) must demote to a per-card refresh button. Record the actual number.

- [ ] **Step 13: Probe 13 — `inter_compartment_metrics` return shape**

Run:
```powershell
micromamba run -n shiny python -c "from multises import seed_curonian; from multises.composite import inter_compartment_metrics; m = inter_compartment_metrics(seed_curonian()); first = next(iter(m.items())); print('compartment:', first[0]); print('keys:', list(first[1].keys()))"
```
Expected: keys include `channel_in_degree`, `channel_out_degree`, `betweenness`. If named differently, capture the exact names — Task 13 uses them verbatim.

- [ ] **Step 14: Probe 14 — `nx.eigenvector_centrality` convergence on Curonian composite**

Run:
```powershell
micromamba run -n shiny python -c "import networkx as nx; from multises import seed_curonian; from multises.composite import build_composite_digraph; g = build_composite_digraph(seed_curonian()); 
try:
    r = nx.eigenvector_centrality(g); print('power-iter OK; non-zero:', sum(1 for v in r.values() if v > 0))
except Exception as e:
    print('power-iter FAILED:', type(e).__name__); r = nx.eigenvector_centrality_numpy(g); print('numpy OK; non-zero:', sum(1 for v in r.values() if v > 0))
"
```
Expected: prints either `power-iter OK` or `power-iter FAILED ... numpy OK`. Either is fine — Task 6 handles both via try/except.

- [ ] **Step 15: Write probe log**

Create `MosaicSES/docs/2026-05-15-chunk4a-probe-results.md` with one line per probe summarising what each captured (signatures, conventions, benchmark numbers, errors observed).

- [ ] **Step 16: Commit the probe log**

```powershell
git add docs/2026-05-15-chunk4a-probe-results.md
git commit -m "docs(mosaicses): chunk-4a Task 0 probe results"
```

---

## Phase B — Library extension

### Task 1: Add `include_dapsi` + `include_channels` kwargs to `build_composite_digraph`

**Files:**
- Modify: `multises/composite.py` (the `build_composite_digraph` function around lines 46–141)
- Test: `tests/test_composite_filters.py` (new)

- [ ] **Step 1: Write failing tests in `tests/test_composite_filters.py`**

```python
"""Filter kwargs added to build_composite_digraph in chunk 4a."""
from __future__ import annotations
import pytest
import networkx as nx
from multises import seed_curonian
from multises.composite import build_composite_digraph


def test_include_dapsi_false_drops_dapsi_nodes():
    ms = seed_curonian()
    g = build_composite_digraph(ms, include_dapsi=False)
    dapsi_nodes = [n for n in g.nodes if "::" in n]
    assert dapsi_nodes == []


def test_include_channels_false_drops_channel_edges():
    ms = seed_curonian()
    g = build_composite_digraph(ms, include_channels=False)
    cross_compartment_edges = [
        (u, v) for u, v in g.edges
        if "::" not in u and "::" not in v
    ]
    assert cross_compartment_edges == []


def test_channel_types_filter_restricts_to_named_types():
    ms = seed_curonian()
    g = build_composite_digraph(ms, channel_types={"nutrients"})
    edge_types = {
        g.edges[u, v].get("channel_type")
        for u, v in g.edges
        if g.edges[u, v].get("channel_type") is not None
    }
    assert edge_types <= {"nutrients"}


def test_default_kwargs_match_chunk3_behavior():
    ms = seed_curonian()
    g_default = build_composite_digraph(ms)
    g_explicit = build_composite_digraph(ms, include_dapsi=True, include_channels=True, channel_types=None)
    assert set(g_default.nodes) == set(g_explicit.nodes)
    assert set(g_default.edges) == set(g_explicit.edges)


def test_parallel_channels_keep_one_edge_id_stable():
    """If two channels share src/dst, only one DiGraph edge survives (composite
    is a simple DiGraph). Verifies edge identity is stable for cross_view
    click-handler mapping."""
    from multises.data_structure import MultiSES, MultiSESMetadata, Compartment, Channel
    from sespy.data_structure import Project, ProjectMetadata, IsaData
    p1 = Project(metadata=ProjectMetadata.new("p1"), isa_data=IsaData(elements=[], connections=[]))
    p2 = Project(metadata=ProjectMetadata.new("p2"), isa_data=IsaData(elements=[], connections=[]))
    c1 = Compartment(id="c1", label="c1", archetype="estuary", project=p1)
    c2 = Compartment(id="c2", label="c2", archetype="lagoon", project=p2)
    ch_a = Channel(id="ch_a", source="c1", target="c2", channel_type="nutrients", polarity="+", strength="medium")
    ch_b = Channel(id="ch_b", source="c1", target="c2", channel_type="nutrients", polarity="-", strength="strong")
    ms = MultiSES(metadata=MultiSESMetadata(name="ms"), compartments=[c1, c2], channels=[ch_a, ch_b])
    g = build_composite_digraph(ms)
    cross_edges = [(u, v) for u, v in g.edges if u == "c1" and v == "c2"]
    assert len(cross_edges) == 1, f"expected 1 edge after parallel-channel collapse, got {len(cross_edges)}"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
micromamba run -n shiny pytest tests/test_composite_filters.py -v
```
Expected: FAIL — first 3 tests TypeError on unknown kwargs; test 4 passes; test 5 may pass or fail. Capture which.

- [ ] **Step 3: Add the two kwargs to `build_composite_digraph` signature**

In `multises/composite.py`, locate the function signature and add the two new kwargs **immediately after `channel_types`**:

```python
def build_composite_digraph(
    ms: MultiSES,
    *,
    channel_types: set[str] | None = None,
    include_dapsi: bool = True,
    include_channels: bool = True,
    # ... rest of existing kwargs ...
) -> nx.DiGraph:
```

Then in the function body, **before the DAPSI-element loop**, guard with `if include_dapsi:`. **Before the cross-compartment channel-edge loop**, guard with `if include_channels:`.

(Read the current function structure during implementation — exact line numbers depend on the chunk-3 state at HEAD `80d0100`.)

- [ ] **Step 4: Run tests to verify they pass**

```powershell
micromamba run -n shiny pytest tests/test_composite_filters.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Run full suite — regression guard**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `246 passed` (was 241, +5 new). If any existing test breaks, the guards are over-broad — review the body restructure.

- [ ] **Step 6: Commit**

```powershell
git add multises/composite.py tests/test_composite_filters.py
git commit -m "feat(mosaicses): build_composite_digraph filter kwargs (include_dapsi, include_channels)"
```

---

## Phase C — App-level scaffolding

### Task 2: Create `multises_app/colors.py` + refactor topology.py

**Files:**
- Create: `multises_app/colors.py`
- Modify: `multises_app/modules/topology.py`
- Test: `tests/test_app_imports_colors.py` (new)

- [ ] **Step 1: Write failing test**

```python
# tests/test_app_imports_colors.py
def test_archetype_colors_importable_and_dict():
    from multises_app.colors import ARCHETYPE_COLORS
    assert isinstance(ARCHETYPE_COLORS, dict)
    assert len(ARCHETYPE_COLORS) >= 6

def test_topology_uses_colors_module():
    from multises_app.colors import ARCHETYPE_COLORS as canonical
    import multises_app.modules.topology as topology_mod
    if hasattr(topology_mod, "_ARCHETYPE_COLORS"):
        assert topology_mod._ARCHETYPE_COLORS == canonical
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
micromamba run -n shiny pytest tests/test_app_imports_colors.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `multises_app/colors.py`**

Paste the `_ARCHETYPE_COLORS` dict literal from Task 0 Probe 7's capture:

```python
"""Public palette module — palette constants used by Shiny modules.

Extracted from chunk-3's private topology._ARCHETYPE_COLORS so comparative.py's
compartment meta-graph (card 5) can reuse them without reaching across module
boundaries. Chunk 4b will mirror these as CSS custom properties on :root in
www/mosaic-skin.css.
"""
from __future__ import annotations

ARCHETYPE_COLORS: dict[str, str] = {
    # ... paste literal from Task 0 Probe 7 here ...
}
```

- [ ] **Step 4: Refactor `multises_app/modules/topology.py`**

Replace the inline `_ARCHETYPE_COLORS = {...}` block with:

```python
from multises_app.colors import ARCHETYPE_COLORS as _ARCHETYPE_COLORS
```

(Keep the private-named alias so the rest of topology.py stays unchanged.)

- [ ] **Step 5: Run tests**

```powershell
micromamba run -n shiny pytest tests/test_app_imports_colors.py tests/test_topology_module.py -v
```
Expected: both PASS.

- [ ] **Step 6: Run full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `248 passed`.

- [ ] **Step 7: Commit**

```powershell
git add multises_app/colors.py multises_app/modules/topology.py tests/test_app_imports_colors.py
git commit -m "refactor(mosaicses): extract _ARCHETYPE_COLORS to public multises_app.colors"
```

### Task 3: Add `comparative` + `cross_view` to dashboard NAV + NAV_TO_STEP

**Files:**
- Modify: `multises_app/dashboard.py`
- Modify: `tests/test_multises_app_imports.py`

- [ ] **Step 1: Extend the existing dashboard NAV test**

In `tests/test_multises_app_imports.py`, modify `test_dashboard_nav_items_exist`:

```python
def test_dashboard_nav_items_exist():
    from multises_app.dashboard import NAV
    ids = {item.id for item in NAV}
    assert "topology" in ids
    assert "compartments" in ids
    assert "comparative" in ids       # NEW chunk 4a
    assert "cross_view" in ids        # NEW chunk 4a


def test_dashboard_nav_to_step_covers_new_panels():
    from multises_app.dashboard import NAV_TO_STEP
    assert NAV_TO_STEP.get("comparative") == "drill"
    assert NAV_TO_STEP.get("cross_view") == "drill"
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
micromamba run -n shiny pytest tests/test_multises_app_imports.py -v -k "dashboard"
```
Expected: FAIL on missing entries.

- [ ] **Step 3: Update `multises_app/dashboard.py`**

Add to `NAV`:
```python
NavItem(id="comparative", icon="chart-line",        label="Comparative"),
NavItem(id="cross_view",  icon="circle-nodes",      label="Cross-view"),
```

Add to `NAV_TO_STEP`:
```python
"comparative": "drill",
"cross_view":  "drill",
```

- [ ] **Step 4: Run tests to verify pass**

```powershell
micromamba run -n shiny pytest tests/test_multises_app_imports.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/dashboard.py tests/test_multises_app_imports.py
git commit -m "feat(mosaicses): NAV + NAV_TO_STEP entries for comparative + cross_view"
```

---

## Phase D — Comparative module

### Task 4: `comparative.py` shell — module decorators + 5 card containers

**Files:**
- Create: `multises_app/modules/comparative.py`
- Test: `tests/test_comparative_module.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_comparative_module.py
from __future__ import annotations


def test_comparative_module_importable():
    from multises_app.modules import comparative  # noqa


def test_comparative_ui_renders_5_cards():
    from multises_app.modules.comparative import comparative_ui
    html = str(comparative_ui("test_id"))
    assert html.count("comparative-card") >= 5


def test_comparative_server_callable():
    from multises_app.modules.comparative import comparative_server
    assert callable(comparative_server)
```

- [ ] **Step 2: Run tests to verify fail**

```powershell
micromamba run -n shiny pytest tests/test_comparative_module.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create the module shell**

```python
# multises_app/modules/comparative.py
"""Comparative module — 5-card analytical grid (chunk 4a).

Cards (stacked full-width per spec §4.1):
  1. Vital signs                  — compartment_summary table
  2. Centrality heatmap           — per-compartment top-K matrix (dpi=72)
  3. Global leverage              — leverage_hotspots top 20 table
  4. Response-Pressure gap        — publishable orphan/covered with disclaimer + system-wide badge
  5. Compartment meta-graph       — pyvis canvas via render_pyvis_network

Fully reactive on state.active_multises.get() — every upstream edit re-renders all 5 cards.
"""
from __future__ import annotations
from shiny import module, ui, render, reactive
from pyvis.shiny import output_pyvis_network, render_pyvis_network

from multises_app.state import MultiSESState


@module.ui
def comparative_ui() -> ui.Tag:
    return ui.div(
        ui.card(ui.card_header("Vital signs"),
                ui.output_data_frame("vital_signs"),
                class_="comparative-card"),
        ui.card(ui.card_header("Centrality heatmap"),
                ui.input_select("metric", "Metric",
                                choices=["betweenness", "degree", "closeness", "eigenvector"],
                                selected="betweenness"),
                ui.input_slider("top_k", "Top-K elements per compartment",
                                min=5, max=20, value=10, step=1),
                ui.output_image("heatmap"),
                class_="comparative-card"),
        ui.card(ui.card_header("Global leverage (top 20)"),
                ui.output_data_frame("leverage"),
                class_="comparative-card"),
        ui.card(ui.card_header("Response–Pressure gap"),
                ui.output_ui("gap_disclaimer"),
                ui.output_ui("gap_lists"),
                ui.output_ui("gap_systemwide_badge"),
                class_="comparative-card comparative-publishable-card"),
        ui.card(ui.card_header("Compartment meta-graph"),
                output_pyvis_network("meta_graph_canvas", height="350px",
                                     show_toolbar=False, show_search=False,
                                     show_layout_switcher=False, show_export=False,
                                     show_status=False),
                class_="comparative-card"),
        class_="comparative-stack",
    )


@module.server
def comparative_server(input, output, session, *, state: MultiSESState) -> None:
    # Card servers filled in subsequent tasks.
    pass
```

- [ ] **Step 4: Run tests + full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `251 passed`.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/comparative.py tests/test_comparative_module.py
git commit -m "feat(mosaicses): comparative module shell (5 card containers)"
```

### Task 5: Comparative card 1 — vital signs

**Files:**
- Modify: `multises_app/modules/comparative.py`
- Modify: `tests/test_comparative_module.py`

- [ ] **Step 1: Add library-level smoke test**

Append to `tests/test_comparative_module.py`:

```python
def test_vital_signs_library_returns_dataframe_with_6_rows():
    import pandas as pd
    from multises import seed_curonian
    from multises.comparative import compartment_summary
    df = compartment_summary(seed_curonian())
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 6
```

- [ ] **Step 2: Run test to verify pass**

```powershell
micromamba run -n shiny pytest tests/test_comparative_module.py::test_vital_signs_library_returns_dataframe_with_6_rows -v
```
Expected: PASS.

- [ ] **Step 3: Add the card 1 server**

In `comparative_server`, replace `pass` with:

```python
    from multises.comparative import compartment_summary

    @output
    @render.data_frame
    def vital_signs():
        return compartment_summary(state.active_multises.get())
```

- [ ] **Step 4: Run full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `252 passed`.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/comparative.py tests/test_comparative_module.py
git commit -m "feat(mosaicses): comparative card 1 — vital signs"
```

### Task 6: Comparative card 2 — centrality heatmap

**Files:**
- Modify: `multises_app/modules/comparative.py`
- Modify: `tests/test_comparative_module.py`

- [ ] **Step 1: Add failing tests for the matrix builder + alt-text helper + eigenvector fallback**

```python
def test_per_compartment_topk_matrix_no_zero_rows():
    from multises import seed_curonian
    from multises_app.modules.comparative import _build_heatmap_matrix
    import numpy as np
    matrix, row_labels, col_labels = _build_heatmap_matrix(
        seed_curonian(), metric="betweenness", top_k=10
    )
    assert matrix.shape == (6, 10)
    assert len(row_labels) == 6
    assert (matrix.sum(axis=1) > 0).all(), "per-compartment top-K should have no all-zero rows"


def test_heatmap_alt_text_dynamic():
    from multises import seed_curonian
    from multises_app.modules.comparative import _heatmap_alt_text
    alt = _heatmap_alt_text(seed_curonian(), metric="betweenness", top_k=10)
    assert "betweenness" in alt.lower()
    assert "compartment" in alt.lower()
    assert len(alt) > 30


def test_eigenvector_centrality_fallback():
    import networkx as nx
    from multises_app.modules.comparative import _centrality
    g = nx.DiGraph()
    g.add_nodes_from(["a", "b", "c", "d"])
    g.add_edges_from([("c", "d"), ("d", "c")])
    result = _centrality(g, metric="eigenvector")
    assert isinstance(result, dict)
```

- [ ] **Step 2: Run tests to verify fail**

```powershell
micromamba run -n shiny pytest tests/test_comparative_module.py -v -k "topk or alt_text or eigenvector"
```
Expected: 3 FAIL.

- [ ] **Step 3: Implement helpers + card 2 server**

In `multises_app/modules/comparative.py`:

```python
import io
import os
import tempfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from multises.composite import build_composite_digraph


def _centrality(g: nx.DiGraph, *, metric: str) -> dict[str, float]:
    if metric == "degree":
        return nx.degree_centrality(g)
    if metric == "betweenness":
        return nx.betweenness_centrality(g)
    if metric == "closeness":
        return nx.closeness_centrality(g)
    if metric == "eigenvector":
        try:
            return nx.eigenvector_centrality(g)
        except nx.PowerIterationFailedConvergence:
            return nx.eigenvector_centrality_numpy(g)
    raise ValueError(f"Unknown metric: {metric}")


def _compartment_of(node_id: str) -> str | None:
    return node_id.split("::", 1)[0] if "::" in node_id else None


def _build_heatmap_matrix(ms, *, metric: str, top_k: int):
    g = build_composite_digraph(ms)
    cent = _centrality(g, metric=metric)
    row_labels = [c.id for c in ms.compartments]
    matrix = np.zeros((len(row_labels), top_k))
    col_labels_per_row: list[list[str]] = []
    for r, cid in enumerate(row_labels):
        members = [(n, cent.get(n, 0.0)) for n in g.nodes if _compartment_of(n) == cid]
        members.sort(key=lambda x: -x[1])
        top = members[:top_k]
        for c, (_node, val) in enumerate(top):
            matrix[r, c] = val
        col_labels_per_row.append([n for n, _ in top] + [""] * max(0, top_k - len(top)))
    return matrix, row_labels, col_labels_per_row


def _heatmap_alt_text(ms, *, metric: str, top_k: int) -> str:
    matrix, rows, cols = _build_heatmap_matrix(ms, metric=metric, top_k=top_k)
    top_row_idx = int(matrix.sum(axis=1).argmax())
    return (
        f"Centrality heatmap ({metric}): {len(rows)} compartments x top-{top_k} "
        f"elements per compartment. Highest-centrality compartment: {rows[top_row_idx]}."
    )
```

Then in `comparative_server`:

```python
    _tmpdir = tempfile.mkdtemp(prefix="mosaicses_heatmap_")

    @output
    @render.image
    def heatmap():
        ms = state.active_multises.get()
        metric = input.metric()
        top_k = int(input.top_k())
        matrix, row_labels, _cols = _build_heatmap_matrix(ms, metric=metric, top_k=top_k)
        fig, ax = plt.subplots(figsize=(8, max(2, len(row_labels) * 0.6)), dpi=72)
        im = ax.imshow(matrix, aspect="auto")
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels)
        ax.set_xticks([])
        ax.set_xlabel(f"top-{top_k} elements per compartment (by {metric})")
        fig.colorbar(im, ax=ax)
        buf = io.BytesIO()
        fig.savefig(buf, format="png")  # NO bbox_inches='tight' — spec Cost-1 mitigation
        plt.close(fig)
        out_path = os.path.join(_tmpdir, f"heatmap_{metric}_{top_k}.png")
        with open(out_path, "wb") as f:
            f.write(buf.getvalue())
        return {
            "src": out_path,
            "alt": _heatmap_alt_text(ms, metric=metric, top_k=top_k),
            "width": "800px",
        }
```

- [ ] **Step 4: Run tests + full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `255 passed`.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/comparative.py tests/test_comparative_module.py
git commit -m "feat(mosaicses): comparative card 2 — per-compartment top-K heatmap + alt text + eigenvector fallback"
```

### Task 7: Comparative card 3 — global leverage table

**Files:**
- Modify: `multises_app/modules/comparative.py`

- [ ] **Step 1: Add the card 3 server inside `comparative_server`**

```python
    from multises.comparative import leverage_hotspots

    @output
    @render.data_frame
    def leverage():
        return leverage_hotspots(state.active_multises.get()).head(20)
```

- [ ] **Step 2: Run full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: still `255 passed` (no new tests).

- [ ] **Step 3: Commit**

```powershell
git add multises_app/modules/comparative.py
git commit -m "feat(mosaicses): comparative card 3 — global leverage top 20"
```

### Task 8: Comparative card 4 — Response–Pressure gap (publishable view)

**Files:**
- Modify: `multises_app/modules/comparative.py`
- Modify: `tests/test_comparative_module.py`

- [ ] **Step 1: Add failing tests**

```python
def test_gap_split_uses_pressure_compartment_has_no_governance():
    from multises import seed_curonian
    from multises.comparative import response_pressure_gap
    df = response_pressure_gap(seed_curonian())
    assert "pressure_compartment_has_no_governance" in df.columns
    assert df["pressure_compartment_has_no_governance"].sum() >= 2


def test_system_wide_gap_helper_returns_list():
    from multises import seed_curonian
    from multises_app.modules.comparative import _system_wide_uncovered_labels
    labels = _system_wide_uncovered_labels(seed_curonian())
    assert isinstance(labels, list)


def test_disclaimer_text_mentions_per_compartment():
    from multises_app.modules.comparative import _disclaimer_text
    txt = _disclaimer_text()
    assert "per-compartment" in txt.lower()
```

- [ ] **Step 2: Run tests to verify fail**

```powershell
micromamba run -n shiny pytest tests/test_comparative_module.py -v -k "gap or system_wide or disclaimer"
```
Expected: 2 FAIL, 1 PASS.

- [ ] **Step 3: Implement helpers + servers**

```python
from multises.comparative import response_pressure_gap


def _disclaimer_text() -> str:
    return (
        "Coverage shown is per-compartment. A Pressure may be uncovered in one "
        "compartment and covered in another. See the system-wide badge below for "
        "Pressures with zero governance coverage in ANY compartment."
    )


def _system_wide_uncovered_labels(ms) -> list[str]:
    df = response_pressure_gap(ms)
    out: list[str] = []
    for label, group in df.groupby("pressure_label"):
        if group["pressure_compartment_has_no_governance"].all():
            out.append(label)
    return sorted(out)
```

Then in `comparative_server`:

```python
    from multises_app.colors import ARCHETYPE_COLORS

    @output
    @render.ui
    def gap_disclaimer():
        return ui.tags.figcaption(_disclaimer_text(), class_="sticky-disclaimer")

    @output
    @render.ui
    def gap_lists():
        ms = state.active_multises.get()
        df = response_pressure_gap(ms)
        archetype_by_cmpt = {c.id: c.archetype for c in ms.compartments}

        def _li(row):
            color = ARCHETYPE_COLORS.get(archetype_by_cmpt.get(row["compartment_id"]), "#aaa")
            return ui.tags.li(
                ui.tags.span(class_="dot", style=f"background:{color}"),
                f" {row['compartment_id']} — {row['pressure_label']}",
            )

        orphan_df = df[df["pressure_compartment_has_no_governance"]]
        covered_df = df[~df["pressure_compartment_has_no_governance"]]

        if orphan_df.empty:
            orphan_block = ui.tags.p(
                "No Pressures sit in compartments without incoming governance channels. "
                "If governance channels haven't been authored yet, this may indicate "
                "missing data rather than complete coverage.",
                class_="placeholder",
            )
        else:
            orphan_block = ui.tags.ul(
                [_li(row) for _, row in orphan_df.iterrows()],
                class_="comparative-publishable orphan",
            )

        covered_block = ui.tags.ul(
            [_li(row) for _, row in covered_df.iterrows()],
            class_="comparative-publishable covered",
        )

        return ui.row(
            ui.column(6,
                ui.tags.h4("Pressures whose compartment has no incoming governance channels"),
                orphan_block,
            ),
            ui.column(6,
                ui.tags.h4("Pressures whose compartment has incoming governance channels"),
                covered_block,
            ),
        )

    @output
    @render.ui
    def gap_systemwide_badge():
        labels = _system_wide_uncovered_labels(state.active_multises.get())
        if not labels:
            return ui.tags.span(
                "0 Pressure labels have zero governance coverage in any compartment.",
                class_="badge badge-success",
            )
        return ui.tags.span(
            f"{len(labels)} Pressure label(s) have zero governance coverage in ANY compartment: "
            f"{', '.join(labels)}",
            class_="badge badge-warning",
        )
```

- [ ] **Step 4: Run tests + full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `258 passed`.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/comparative.py tests/test_comparative_module.py
git commit -m "feat(mosaicses): comparative card 4 — publishable gap with disclaimer + system-wide badge"
```

### Task 9: Comparative card 5 — compartment meta-graph

**Files:**
- Modify: `multises_app/modules/comparative.py`
- Modify: `tests/test_comparative_module.py`

- [ ] **Step 1: Add failing test**

```python
def test_build_meta_graph_returns_pyvis_network_with_6_nodes():
    from multises import seed_curonian
    from multises_app.modules.comparative import _build_meta_graph
    net = _build_meta_graph(seed_curonian())
    assert len(net.nodes) == 6
    assert len(net.edges) >= 1
```

- [ ] **Step 2: Run test to verify fail**

```powershell
micromamba run -n shiny pytest tests/test_comparative_module.py::test_build_meta_graph_returns_pyvis_network_with_6_nodes -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `_build_meta_graph` + card 5 server**

```python
import pyvis.network
# render_pyvis_network is already imported at module top (see Task 4).
from multises_app.colors import ARCHETYPE_COLORS


def _build_meta_graph(ms) -> pyvis.network.Network:
    net = pyvis.network.Network(directed=True, notebook=False)
    for c in ms.compartments:
        size = 10 + 2 * len(c.project.isa_data.elements)
        color = ARCHETYPE_COLORS.get(c.archetype, "#aaaaaa")
        net.add_node(c.id, label=c.label, size=size, color=color, title=c.archetype)
    for ch in ms.channels:
        net.add_edge(ch.source, ch.target, label=ch.channel_type, title=f"polarity {ch.polarity}")
    return net
```

In `comparative_server` — use the chunk-3 paired pattern (see `topology.py:284-289`): `@output(id=...)` + `@render_pyvis_network(...)` with matching kwargs to the UI-side `output_pyvis_network`. Decorated function returns a `pyvis.network.Network`:

```python
    @output(id="meta_graph_canvas")
    @render_pyvis_network(height="350px", show_toolbar=False, show_search=False,
                          show_layout_switcher=False, show_export=False,
                          show_status=False)
    def _meta_graph_canvas() -> pyvis.network.Network:
        return _build_meta_graph(state.active_multises.get())
```

- [ ] **Step 4: Run tests + full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `259 passed`.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/comparative.py tests/test_comparative_module.py
git commit -m "feat(mosaicses): comparative card 5 — compartment meta-graph"
```

---

## Phase E — Cross-view module

### Task 10: `cross_view.py` shell — filter toolbar + 3 card containers + JS handler block

**Files:**
- Create: `multises_app/modules/cross_view.py`
- Test: `tests/test_cross_view_module.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cross_view_module.py
from __future__ import annotations


def test_cross_view_module_importable():
    from multises_app.modules import cross_view  # noqa


def test_cross_view_ui_renders_filter_toolbar_and_3_cards():
    from multises_app.modules.cross_view import cross_view_ui
    html = str(cross_view_ui("test_id"))
    for switch_id in ("dapsi", "channels", "cycles_only", "types"):
        assert switch_id in html
    assert "refresh" in html.lower()
    assert html.count("cross-view-card") >= 3


def test_dirty_hint_container_has_aria_live():
    from multises_app.modules.cross_view import cross_view_ui
    html = str(cross_view_ui("test_id"))
    assert ("aria-live" in html and "polite" in html)
    assert ("role" in html and "status" in html)
```

- [ ] **Step 2: Run tests to verify fail**

```powershell
micromamba run -n shiny pytest tests/test_cross_view_module.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create the module shell**

```python
# multises_app/modules/cross_view.py
"""Cross-view module — composite-graph viewer + cross-loops table + bridge bar chart.

Card 1 refresh-gated (parent spec §7.5, this spec §2). Cards 2 + 3 read from
cached state set by the refresh effect. JS handler for click-to-highlight
registered at module-mount time, BEFORE pyvis loads (chunk-3-Invariant-3
analog mitigation per Risk 1).
"""
from __future__ import annotations
from shiny import module, ui, render, reactive
from pyvis.shiny import output_pyvis_network, render_pyvis_network

from multises_app.state import MultiSESState

CHANNEL_TYPES_DEFAULT: list[str] = [
    "nutrients", "water_discharge", "organisms_marine_estuarine",
    "organisms_diadromous", "sediment", "governance",
    "economic_telecoupling", "energy", "knowledge_transfer",
]


@module.ui
def cross_view_ui() -> ui.Tag:
    return ui.div(
        # Filter toolbar
        ui.div(
            ui.row(
                ui.column(2, ui.input_switch("dapsi", "DAPSI elements", value=True)),
                ui.column(2, ui.input_switch("channels", "Channels", value=True)),
                ui.column(3, ui.input_switch("cycles_only", "Cross-compartment cycles only", value=False)),
                ui.column(3, ui.input_selectize("types", "Channel types",
                                                choices=CHANNEL_TYPES_DEFAULT,
                                                multiple=True,
                                                selected=CHANNEL_TYPES_DEFAULT)),
                ui.column(2, ui.input_action_button("refresh", "Refresh ⟳", class_="btn-primary")),
            ),
            ui.tags.div(ui.output_ui("dirty_hint"), role="status", **{"aria-live": "polite"}),
            class_="cross-view-toolbar",
        ),
        # Card 1: hero composite viewer
        ui.card(ui.card_header("Composite graph"),
                ui.output_ui("composite_canvas_status"),
                output_pyvis_network("composite_canvas", height="600px",
                                     show_toolbar=True, show_search=True,
                                     show_layout_switcher=True, show_export=True,
                                     show_status=False),
                class_="cross-view-card cross-view-hero"),
        # Cards 2 + 3 in bottom row
        ui.row(
            ui.column(6, ui.card(ui.card_header("Cross-compartment loops"),
                                 ui.output_data_frame("loops_table"),
                                 class_="cross-view-card")),
            ui.column(6, ui.card(ui.card_header("Bridge metrics"),
                                 ui.output_image("bridge_chart"),
                                 class_="cross-view-card")),
        ),
        # JS handler block (Risk 1: registered BEFORE pyvis loads; nulls
        # originalEdges on clear_highlight so post-rebuild highlights
        # recapture the new network's baseline)
        ui.tags.script("""
        (function () {
          function getNetwork() {
            // Convention captured by Task 0 Probe 4 — replace per probe result
            return window.__mosaicses_get_cross_view_network && window.__mosaicses_get_cross_view_network() || null;
          }
          let originalEdges = null, originalNodes = null;
          Shiny.addCustomMessageHandler("mosaicses:highlight_loop", function (msg) {
            const net = getNetwork(); if (!net) return;
            if (originalEdges === null) {
              originalEdges = net.body.data.edges.get();
              originalNodes = net.body.data.nodes.get();
            }
            net.body.data.edges.update(originalEdges.map(function (e) {
              return {
                id: e.id,
                color: msg.edge_ids.includes(e.id) ? "#e74c3c" : { opacity: 0.3, color: e.color },
                width: msg.edge_ids.includes(e.id) ? 3 : 1,
              };
            }));
            net.body.data.nodes.update(originalNodes.map(function (n) {
              const lit = msg.node_ids.includes(n.id);
              return {
                id: n.id,
                opacity: lit ? 1.0 : 0.3,
                borderWidth: lit ? 2 : 1,
                color: lit ? { border: "#e74c3c", background: (n.color && n.color.background) || "#fff" } : n.color,
                size: lit ? (n.size || 25) * 1.4 : (n.size || 25),
                shape: lit ? "diamond" : (n.shape || "dot"),
              };
            }));
          });
          Shiny.addCustomMessageHandler("mosaicses:clear_highlight", function () {
            const net = getNetwork();
            if (net && originalEdges !== null) {
              net.body.data.edges.update(originalEdges);
              net.body.data.nodes.update(originalNodes);
            }
            originalEdges = null;
            originalNodes = null;
          });
        })();
        """),
    )


@module.server
def cross_view_server(input, output, session, *, state: MultiSESState) -> None:
    # Reactive plumbing + per-card servers filled in subsequent tasks.
    pass
```

- [ ] **Step 4: Run tests + full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `262 passed`.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/cross_view.py tests/test_cross_view_module.py
git commit -m "feat(mosaicses): cross_view module shell — toolbar + 3 card containers + JS handler block"
```

### Task 11: Cross-view card 1 — refresh-gated composite viewer + cache invalidation + dirty hint

**Files:**
- Modify: `multises_app/modules/cross_view.py`
- Modify: `tests/test_cross_view_module.py`

- [ ] **Step 1: Add failing tests**

```python
def test_restrict_digraph_keeps_only_listed():
    import networkx as nx
    from multises_app.modules.cross_view import _restrict_digraph
    g = nx.DiGraph()
    g.add_edges_from([("a", "b"), ("b", "c"), ("c", "a"), ("a", "d")])
    h = _restrict_digraph(g, {"a", "b", "c"}, {("a", "b"), ("b", "c"), ("c", "a")})
    assert set(h.nodes) == {"a", "b", "c"}
    assert set(h.edges) == {("a", "b"), ("b", "c"), ("c", "a")}
```

- [ ] **Step 2: Run test to verify fail**

```powershell
micromamba run -n shiny pytest tests/test_cross_view_module.py::test_restrict_digraph_keeps_only_listed -v
```
Expected: FAIL.

- [ ] **Step 3: Add the helper + reactive plumbing**

```python
import networkx as nx
from multises.composite import build_composite_digraph, cross_compartment_loops


def _restrict_digraph(g: nx.DiGraph, keep_nodes: set, keep_edges: set) -> nx.DiGraph:
    h = nx.DiGraph()
    for n in g.nodes:
        if n in keep_nodes:
            h.add_node(n, **g.nodes[n])
    for (u, v) in g.edges:
        if (u, v) in keep_edges:
            h.add_edge(u, v, **g.edges[u, v])
    return h
```

Then in `cross_view_server`, replace `pass`:

```python
    last_built_composite = reactive.value(None)
    last_built_loops     = reactive.value(None)
    last_applied         = reactive.value(None)

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
        loops = cross_compartment_loops(ms, g=g)
        if cycles_only:
            keep_nodes = {n for loop in loops for n in loop.nodes}
            keep_edges = {
                (loop.nodes[i], loop.nodes[i + 1])
                for loop in loops
                for i in range(loop.length)
            }
            g = _restrict_digraph(g, keep_nodes, keep_edges)
        last_built_composite.set(g)
        last_built_loops.set(loops)
        last_applied.set((include_dapsi, include_channels, cycles_only, types_tuple, id(ms)))
        # Risk 1 mitigation — cleanup contract
        await session.send_custom_message("mosaicses:clear_highlight", {})

    @reactive.effect
    def _invalidate_cache_on_data_change():
        ms = state.active_multises.get()
        with reactive.isolate():
            applied = last_applied()
        if applied is not None and applied[-1] != id(ms):
            last_built_composite.set(None)
            last_built_loops.set(None)

    # Card 1 split into two outputs: a status/placeholder UI (shown via
    # `composite_canvas_status` output) and the pyvis canvas itself (paired
    # `@output(id="composite_canvas")` + `@render_pyvis_network(...)`).
    # The decorator must return a pyvis.network.Network; HTML placeholders
    # cannot share that output. See chunk-3 `topology.py:284-289`.

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
    @render_pyvis_network(height="600px", show_toolbar=True, show_search=True,
                          show_layout_switcher=True, show_export=True,
                          show_status=False)
    def _composite_canvas() -> "pyvis.network.Network":
        import pyvis.network
        g = last_built_composite()
        net = pyvis.network.Network(directed=True, notebook=False)
        if g is None or g.number_of_nodes() == 0:
            # Empty Network — placeholder text shown via `composite_canvas_status`.
            return net
        for n, attrs in g.nodes(data=True):
            net.add_node(n, **{k: v for k, v in attrs.items() if k in ("label", "color", "size", "title")})
        for u, v, attrs in g.edges(data=True):
            net.add_edge(u, v, **{k: val for k, val in attrs.items() if k in ("label", "color", "title")})
        return net

    @output
    @render.ui
    def dirty_hint():
        applied = last_applied()
        if applied is None:
            return ui.tags.span("Click Refresh ⟳ to build the composite graph.", class_="text-muted")
        current = (input.dapsi(), input.channels(), input.cycles_only(),
                   tuple(sorted(input.types() or ())), id(state.active_multises.get()))
        if current[-1] != applied[-1]:
            return ui.tags.span("data changed — click Refresh to re-render canvas", class_="text-warning")
        if current[:-1] != applied[:-1]:
            return ui.tags.span("filters changed — click Refresh", class_="text-muted")
        return ui.tags.span("")
```

- [ ] **Step 4: Run tests + full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `263 passed`.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/cross_view.py tests/test_cross_view_module.py
git commit -m "feat(mosaicses): cross_view card 1 — refresh-gated composite + cache invalidation + dirty hint"
```

### Task 12: Cross-view card 2 — loops table + click handler

**Files:**
- Modify: `multises_app/modules/cross_view.py`
- Modify: `tests/test_cross_view_module.py`

- [ ] **Step 1: Add failing test**

```python
def test_loops_dataframe_columns():
    from multises import seed_curonian
    from multises.composite import cross_compartment_loops
    from multises_app.modules.cross_view import _loops_dataframe
    df = _loops_dataframe(cross_compartment_loops(seed_curonian()))
    assert list(df.columns) == ["id", "length", "polarity_type", "compartments", "polarity_string"]
```

- [ ] **Step 2: Run test to verify fail**

```powershell
micromamba run -n shiny pytest tests/test_cross_view_module.py::test_loops_dataframe_columns -v
```
Expected: FAIL.

- [ ] **Step 3: Add `_loops_dataframe`, `_edge_dom_id` + card 2 server + click handler**

```python
import pandas as pd


def _loops_dataframe(loops) -> pd.DataFrame:
    if not loops:
        return pd.DataFrame(columns=["id", "length", "polarity_type", "compartments", "polarity_string"])
    return pd.DataFrame([
        {
            "id": l.id,
            "length": l.length,
            "polarity_type": l.polarity_type,
            "compartments": " → ".join(l.compartments_visited),
            "polarity_string": l.polarity_string,
        }
        for l in loops
    ])


def _edge_dom_id(u: str, v: str) -> str:
    # Convention captured by Task 0 Probe 4 — adjust per probe result
    return f"{u}::{v}"
```

In `cross_view_server`:

```python
    cross_loops_calc = reactive.calc(lambda: last_built_loops() or [])

    @output
    @render.data_frame
    def loops_table():
        loops = cross_loops_calc()
        if not loops:
            return render.DataGrid(
                pd.DataFrame([{"info": "Click Refresh ⟳ on the toolbar to detect cross-compartment loops."}]),
                selection_mode="none",
            )
        return render.DataGrid(_loops_dataframe(loops), selection_mode="row")

    @reactive.effect
    async def _on_loop_selection():
        sel = loops_table.cell_selection()
        rows = sel.get("rows", ()) if sel else ()
        if rows:
            loops = cross_loops_calc()
            if rows[0] < len(loops):
                loop = loops[rows[0]]
                await session.send_custom_message("mosaicses:highlight_loop", {
                    "edge_ids": [_edge_dom_id(loop.nodes[i], loop.nodes[i + 1])
                                 for i in range(loop.length)],
                    "node_ids": list(set(loop.nodes)),
                })
        else:
            await session.send_custom_message("mosaicses:clear_highlight", {})
```

- [ ] **Step 4: Run tests + full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `264 passed`.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/cross_view.py tests/test_cross_view_module.py
git commit -m "feat(mosaicses): cross_view card 2 — loops table + click-to-highlight dispatch"
```

### Task 13: Cross-view card 3 — bridge bar chart (in/out/betweenness)

**Files:**
- Modify: `multises_app/modules/cross_view.py`
- Modify: `tests/test_cross_view_module.py`

- [ ] **Step 1: Add failing test**

```python
def test_bridge_chart_alt_text_includes_top():
    from multises import seed_curonian
    from multises_app.modules.cross_view import _bridge_chart_alt_text
    alt = _bridge_chart_alt_text(seed_curonian())
    assert "betweenness" in alt.lower()
```

- [ ] **Step 2: Run test to verify fail**

```powershell
micromamba run -n shiny pytest tests/test_cross_view_module.py::test_bridge_chart_alt_text_includes_top -v
```
Expected: FAIL.

- [ ] **Step 3: Implement chart renderer + alt-text helper**

```python
import io
import os
import tempfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from multises.composite import inter_compartment_metrics


def _bridge_chart_alt_text(ms) -> str:
    m = inter_compartment_metrics(ms)
    if not m:
        return "Bridge metrics: no inter-compartment channels."
    top_bet = max(m.items(), key=lambda x: x[1].get("betweenness", 0.0))
    return (
        f"Bridge metrics by compartment: each compartment shows three bars — "
        f"channel_in_degree, channel_out_degree, betweenness. "
        f"Highest betweenness: {top_bet[0]} ({top_bet[1].get('betweenness', 0):.3f})."
    )
```

In `cross_view_server`:

```python
    _bridge_tmpdir = tempfile.mkdtemp(prefix="mosaicses_bridge_")

    @output
    @render.image
    def bridge_chart():
        ms = state.active_multises.get()
        m = inter_compartment_metrics(ms)
        compartments = list(m.keys())
        in_deg  = [m[c].get("channel_in_degree", 0)  for c in compartments]
        out_deg = [m[c].get("channel_out_degree", 0) for c in compartments]
        between = [m[c].get("betweenness", 0.0)      for c in compartments]
        x = np.arange(len(compartments))
        w = 0.25
        fig, ax = plt.subplots(figsize=(8, 4), dpi=72)
        ax.bar(x - w, in_deg,  width=w, label="in-degree")
        ax.bar(x,     out_deg, width=w, label="out-degree")
        ax.bar(x + w, between, width=w, label="betweenness")
        ax.set_xticks(x); ax.set_xticklabels(compartments, rotation=30, ha="right")
        ax.legend()
        ax.set_ylabel("value")
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        out_path = os.path.join(_bridge_tmpdir, "bridge.png")
        with open(out_path, "wb") as f:
            f.write(buf.getvalue())
        return {"src": out_path, "alt": _bridge_chart_alt_text(ms), "width": "800px"}
```

- [ ] **Step 4: Run tests + full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `265 passed`.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/cross_view.py tests/test_cross_view_module.py
git commit -m "feat(mosaicses): cross_view card 3 — bridge bar chart (in/out/betweenness) with alt text"
```

---

## Phase F — App wiring

### Task 14: Wire the two new panels into `app.py` + inline CSS stub

**Files:**
- Modify: `app.py`
- Modify: `multises_app/modules/__init__.py`
- Modify: `tests/test_multises_app_imports.py`

- [ ] **Step 1: Extend the chunk-3 app smoke test**

In `tests/test_multises_app_imports.py`, find `test_app_module_loads` and add at the end (after the existing `assert hasattr(mod, "app")`):

```python
    panels = getattr(mod, "PANELS", None)
    panel_ids = []
    if panels is not None:
        for p in panels:
            for attr in ("value", "_value", "id"):
                if hasattr(p, attr) and getattr(p, attr):
                    panel_ids.append(getattr(p, attr))
                    break
    assert "comparative" in panel_ids, f"missing in PANELS: {panel_ids}"
    assert "cross_view"  in panel_ids, f"missing in PANELS: {panel_ids}"
```

- [ ] **Step 2: Run test to verify fail**

```powershell
micromamba run -n shiny pytest tests/test_multises_app_imports.py::test_app_module_loads -v
```
Expected: FAIL.

- [ ] **Step 3: Re-export the new modules from `multises_app/modules/__init__.py`**

Append:
```python
from .comparative import comparative_ui, comparative_server
from .cross_view  import cross_view_ui,  cross_view_server
```

- [ ] **Step 4: Modify `app.py`**

Add imports near the top:
```python
from multises_app.modules import comparative_ui, comparative_server, cross_view_ui, cross_view_server
```

In the `PANELS` tuple, insert two new entries after the existing `compartments` entry:
```python
ui.nav_panel("Comparative", comparative_ui("comparative"), value="comparative"),
ui.nav_panel("Cross-view",  cross_view_ui("cross_view"),  value="cross_view"),
```

In the server function, add after the existing module-server calls:
```python
comparative_server("comparative", state=state)
cross_view_server("cross_view",   state=state)
```

In the `ui.head_content(...)` block, add the inline `<style>` stub (Maint-1 — chunk 4b grep-deletes by id):

```python
ui.tags.style("""
.comparative-publishable.orphan li, .comparative-publishable.covered li {
    list-style: none; padding: 2px 0;
}
.comparative-publishable .dot {
    display: inline-block; width: 10px; height: 10px;
    border-radius: 50%; margin-right: 4px; vertical-align: middle;
}
.sticky-disclaimer {
    font-size: 0.9em; padding: 4px 8px; background: #f5f5dc;
    border-left: 3px solid #c0a060; margin-bottom: 8px;
}
.placeholder { color: #888; font-style: italic; padding: 8px; }
.badge.badge-success { background: #d4edda; color: #155724; padding: 4px 8px; border-radius: 4px; }
.badge.badge-warning { background: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; }
""", id="mosaicses-chunk4a-stub"),
```

- [ ] **Step 5: Run the app-loads test**

```powershell
micromamba run -n shiny pytest tests/test_multises_app_imports.py::test_app_module_loads -v
```
Expected: PASS.

- [ ] **Step 6: Manual smoke — boot the app**

In a separate terminal:
```powershell
micromamba run -n shiny shiny run --launch-browser app.py
```
Verify: all 5 nav panels visible (Project / Topology / Compartments / Comparative / Cross-view); Comparative renders 5 cards; Cross-view shows the pre-Refresh placeholder. Stop the dev server (Ctrl+C).

- [ ] **Step 7: Run full suite**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: still `265 passed`.

- [ ] **Step 8: Commit**

```powershell
git add app.py multises_app/modules/__init__.py tests/test_multises_app_imports.py
git commit -m "feat(mosaicses): wire comparative + cross_view into app.py + inline CSS stub"
```

---

## Phase G — Test infrastructure + e2e

### Task 15: `tests/_curonian_fixtures.py` — introspected expected-state

**Files:**
- Create: `tests/_curonian_fixtures.py`

- [ ] **Step 1: Create the fixture module**

```python
# tests/_curonian_fixtures.py
"""Derive expected-test-state from seed_curonian() at collection time so
renaming a seeded Pressure doesn't silently break e2e asserts. Risk-11
mitigation from chunk-4a spec.
"""
from __future__ import annotations
from multises import seed_curonian
from multises.comparative import response_pressure_gap
from multises.composite import cross_compartment_loops

_SEED = seed_curonian()
_GAP = response_pressure_gap(_SEED)
_LOOPS = cross_compartment_loops(_SEED)

EXPECTED_UNCOVERED_PRESSURE_LABELS: tuple[str, ...] = tuple(sorted(set(
    _GAP[_GAP["pressure_compartment_has_no_governance"]]["pressure_label"]
)))

EXPECTED_BALANCING_LOOP_COMPARTMENT_TUPLES: tuple[tuple[str, ...], ...] = tuple(
    tuple(l.compartments_visited)
    for l in _LOOPS
    if l.polarity_type == "Balancing"
)

assert len(EXPECTED_UNCOVERED_PRESSURE_LABELS) >= 2, (
    "Curonian seed no longer satisfies parent spec §10.5 acceptance "
    "(≥ 2 uncovered Pressures). Seed drifted."
)
assert len(EXPECTED_BALANCING_LOOP_COMPARTMENT_TUPLES) >= 1, (
    "Curonian seed no longer has any Balancing cross-compartment loops "
    "(parent spec §10.5 / §8.4 Loop 1)."
)
```

- [ ] **Step 2: Verify fixture loads without raising**

```powershell
micromamba run -n shiny python -c "from tests import _curonian_fixtures as f; print('uncovered:', f.EXPECTED_UNCOVERED_PRESSURE_LABELS); print('balancing tuples:', len(f.EXPECTED_BALANCING_LOOP_COMPARTMENT_TUPLES))"
```
Expected: non-empty outputs. If an assertion fires, stop and reconcile with the seed authors.

- [ ] **Step 3: Commit**

```powershell
git add tests/_curonian_fixtures.py
git commit -m "test(mosaicses): introspected Curonian fixtures for chunk-4a e2e"
```

### Task 16: `tests/conftest.py` — app-under-test fixture

**Files:**
- Modify: `tests/conftest.py`

Per Probe 5 (Step 5), Shiny 1.5.1 exposes `create_app_fixture` from `shiny.pytest`. The fixture returns a `ShinyAppProc` (from `shiny.run`) that has a `.url` attribute and is itself a context manager. The chunk-4a e2e tests consume this via the `mosaicses_app_proc` fixture below and pass `app.url` to Playwright's `page.goto()`.

- [ ] **Step 1: Append the fixture**

```python
import pytest
from shiny.pytest import create_app_fixture

# Path is relative to repo root (the directory pytest is invoked from);
# `app.py` is MosaicSES's entrypoint at the repo root.
mosaicses_app_proc = create_app_fixture("app.py")


@pytest.fixture(scope="session")
def mosaicses_app_url(mosaicses_app_proc):
    """Convenience accessor — the URL Playwright should navigate to."""
    return mosaicses_app_proc.url
```

The `create_app_fixture` helper handles port allocation, process spawn, readiness polling, and teardown — equivalent to the chunk-3 subprocess pattern, but maintained upstream. If at the time of implementation the API has shifted (Shiny's testing surface is pre-1.0 stable), the chunk-3 `tests/conftest.py` subprocess pattern (`shiny run --port <free> --host 127.0.0.1 app.py` + `urllib.request.urlopen` readiness poll + `terminate()` on teardown) is the documented fallback — copy that idiom rather than improvising.

- [ ] **Step 2: Verify import**

```powershell
micromamba run -n shiny python -c "import tests.conftest; print('conftest imports OK')"
```
Expected: prints OK.

- [ ] **Step 3: Commit**

```powershell
git add tests/conftest.py
git commit -m "test(mosaicses): mosaicses_app_url fixture for chunk-4a e2e"
```

### Task 17: `pyproject.toml` + README — Playwright dev deps + Run the e2e tests

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: Add dev deps to `pyproject.toml`**

```toml
[project.optional-dependencies]
dev = [
    # ... existing dev deps ...
    "playwright>=1.45",
    "pytest-playwright>=0.5",
]
```

- [ ] **Step 2: Verify env has the deps**

```powershell
micromamba run -n shiny python -c "import playwright, pytest_playwright; print('playwright', playwright.__version__); print('pytest_playwright', pytest_playwright.__version__)"
```
Expected: both print versions. If absent:
```powershell
micromamba install -n shiny -c conda-forge playwright pytest-playwright
```
(Per user CLAUDE.md — `micromamba install`, NOT `pip install`.)

- [ ] **Step 3: Append "Run the e2e tests" to `README.md`**

After the existing "Run the app" section, add:

````markdown
## Run the e2e tests

```powershell
micromamba run -n shiny playwright install chromium
micromamba run -n shiny pytest tests/test_*_e2e.py -q
```

The `playwright install chromium` step downloads ~150 MB of browser binaries
and is required once per dev machine. CI integration is deferred to chunk 4b.
````

- [ ] **Step 4: Verify regression-free**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `265 passed`.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml README.md
git commit -m "docs(mosaicses): chunk-4a e2e dev deps + README run-the-e2e section"
```

### Task 18: `tests/test_comparative_e2e.py` — Playwright e2e

**Files:**
- Create: `tests/test_comparative_e2e.py`

- [ ] **Step 1: Write the e2e test**

```python
# tests/test_comparative_e2e.py
"""Comparative panel e2e — 1 of 2 chunk-4a e2e tests."""
from __future__ import annotations
from playwright.sync_api import sync_playwright, expect

from tests._curonian_fixtures import EXPECTED_UNCOVERED_PRESSURE_LABELS


def test_comparative_panel_e2e(mosaicses_app_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.click('text="Comparative"')
            page.wait_for_selector(".comparative-card", timeout=10_000)

            cards = page.locator(".comparative-card")
            assert cards.count() == 5

            disc = page.locator(".sticky-disclaimer").first
            expect(disc).to_be_visible()
            assert "per-compartment" in (disc.text_content() or "").lower()

            orphan_items = page.locator("ul.comparative-publishable.orphan li")
            assert orphan_items.count() >= 2
            orphan_text = " ".join(orphan_items.all_text_contents()).lower()
            assert any(lbl.lower() in orphan_text for lbl in EXPECTED_UNCOVERED_PRESSURE_LABELS)

            badge = page.locator(".badge.badge-success, .badge.badge-warning").first
            expect(badge).to_be_visible()

            select = page.locator("select").filter(has_text="").nth(0)
            # Default metric is betweenness
            metric_select = page.locator('select[id$="-metric"]')
            assert metric_select.input_value() == "betweenness"

            heatmap_img = page.locator('img[id$="-heatmap"]').first
            heatmap_alt = heatmap_img.get_attribute("alt") or ""
            assert len(heatmap_alt) > 0

            old_src = heatmap_img.get_attribute("src")
            metric_select.select_option("degree")
            page.wait_for_timeout(2000)
            new_src = heatmap_img.get_attribute("src")
            assert new_src != old_src
        finally:
            browser.close()
```

- [ ] **Step 2: Run the e2e test**

```powershell
micromamba run -n shiny pytest tests/test_comparative_e2e.py -v
```
Expected: PASS. If a selector fails because @module's id-prefix scheme differs, inspect via `page.content()` and adjust.

- [ ] **Step 3: Commit**

```powershell
git add tests/test_comparative_e2e.py
git commit -m "test(mosaicses): comparative panel e2e (Playwright)"
```

### Task 19: `tests/test_cross_view_e2e.py` — Playwright e2e

**Files:**
- Create: `tests/test_cross_view_e2e.py`

- [ ] **Step 1: Write the e2e test**

```python
# tests/test_cross_view_e2e.py
"""Cross-view panel e2e — 2 of 2 chunk-4a e2e tests."""
from __future__ import annotations
from playwright.sync_api import sync_playwright, expect

from tests._curonian_fixtures import EXPECTED_BALANCING_LOOP_COMPARTMENT_TUPLES


def test_cross_view_panel_e2e(mosaicses_app_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.click('text="Cross-view"')
            page.wait_for_selector(".cross-view-toolbar", timeout=10_000)

            placeholder = page.locator(".placeholder").filter(has_text="Click Refresh").first
            expect(placeholder).to_be_visible()

            dirty = page.locator('[role="status"][aria-live="polite"]')
            assert dirty.count() >= 1

            page.click('button:has-text("Refresh")')
            page.wait_for_timeout(2000)
            page.wait_for_selector("canvas, .vis-network", timeout=10_000)

            n_compartments = page.evaluate("""() => {
              const acc = window.__mosaicses_get_cross_view_network;
              const net = acc && acc();
              if (!net) return -1;
              return net.body.data.nodes.get().filter(n => (n.group || '') === 'compartment' || (!n.id.includes('::'))).length;
            }""")
            assert n_compartments == 6, f"expected 6 compartment nodes, got {n_compartments}"

            loops_rows = page.locator("table tbody tr")
            assert loops_rows.count() >= 1
            balancing_row_idx = None
            for i in range(loops_rows.count()):
                text = loops_rows.nth(i).text_content() or ""
                if "Balancing" in text:
                    for tup in EXPECTED_BALANCING_LOOP_COMPARTMENT_TUPLES:
                        if all(c in text for c in tup):
                            balancing_row_idx = i
                            break
                    if balancing_row_idx is not None:
                        break
            assert balancing_row_idx is not None

            loops_rows.nth(balancing_row_idx).click()
            page.wait_for_timeout(500)

            metrics = page.evaluate("""() => {
              const acc = window.__mosaicses_get_cross_view_network;
              const net = acc && acc();
              if (!net) return null;
              const edges = net.body.data.edges.get();
              const nodes = net.body.data.nodes.get();
              return {
                red: edges.filter(e => e.color === '#e74c3c').length,
                dimmed: edges.filter(e => e.color && e.color.opacity === 0.3).length,
                diamonds: nodes.filter(n => n.shape === 'diamond').length,
              };
            }""")
            assert metrics is not None
            assert metrics["red"] >= 2
            assert metrics["dimmed"] >= 1
            assert metrics["diamonds"] >= 2

            # Risk 1 acceptance — Refresh clears the highlight
            page.click('button:has-text("Refresh")')
            page.wait_for_timeout(2000)
            post = page.evaluate("""() => {
              const acc = window.__mosaicses_get_cross_view_network;
              const net = acc && acc();
              if (!net) return -1;
              return net.body.data.edges.get().filter(e => e.color === '#e74c3c').length;
            }""")
            assert post == 0, f"after Refresh, {post} red edges remain (Risk 1 regression)"

            # cycles_only shrinks the graph
            n_before = page.evaluate("() => { const net = window.__mosaicses_get_cross_view_network(); return net.body.data.nodes.get().length; }")
            page.click('input[id$="-cycles_only"]')
            page.click('button:has-text("Refresh")')
            page.wait_for_timeout(2000)
            n_after = page.evaluate("() => { const net = window.__mosaicses_get_cross_view_network(); return net.body.data.nodes.get().length; }")
            assert n_after < n_before, f"cycles_only did not shrink graph: {n_before} -> {n_after}"

            # Empty-filter-combo placeholder
            page.click('input[id$="-channels"]')
            page.click('button:has-text("Refresh")')
            page.wait_for_timeout(1000)
            empty = page.locator(".placeholder").filter(has_text="filter combination").first
            expect(empty).to_be_visible()
        finally:
            browser.close()
```

- [ ] **Step 2: Run the e2e test**

```powershell
micromamba run -n shiny pytest tests/test_cross_view_e2e.py -v
```
Expected: PASS. If the `window.__mosaicses_get_cross_view_network` accessor doesn't match the `pyvis.shiny.render_pyvis_network` emission (per probe-4), adjust both the JS handler in `cross_view.py` AND the `page.evaluate` calls. This is the load-bearing integration detail.

- [ ] **Step 3: Commit**

```powershell
git add tests/test_cross_view_e2e.py
git commit -m "test(mosaicses): cross_view panel e2e (Playwright)"
```

---

## Phase H — Final integration

### Task 20: Smoke checklist file + final pytest sweep

**Files:**
- Create: `MosaicSES/docs/2026-05-15-chunk4a-smoke-checklist.md`

- [ ] **Step 1: Final pytest sweep**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: `267 passed` (241 chunk-3 + 26 chunk-4a; ±2 depending on intermediate test count). All must pass.

- [ ] **Step 2: Write the smoke checklist file**

Create `MosaicSES/docs/2026-05-15-chunk4a-smoke-checklist.md`:

```markdown
# Chunk 4a Smoke Checklist (2026-05-15)

Run before pushing to origin/main. Ship gate per spec §8 + saved feedback memory
`feedback_runtime_verify_before_shared_state.md`.

Launch:
\`\`\`powershell
micromamba run -n shiny shiny run --launch-browser app.py
\`\`\`

## App boot
- [ ] App boots without console errors
- [ ] All 5 nav panels visible: Project / Topology / Compartments / Comparative / Cross-view
- [ ] Default landing is Topology

## Comparative panel
- [ ] All 5 cards render within ~3s on first navigation (cold-start tax per Hidden-2)
- [ ] Vital signs table shows 6 compartment rows
- [ ] Centrality heatmap renders; default metric is "betweenness"; top-K slider default 10
- [ ] Changing metric to "degree" updates the heatmap image
- [ ] Changing top-K slider updates the heatmap image (per-compartment top-K — no empty rows)
- [ ] Global leverage table shows ≤ 20 rows
- [ ] Response–Pressure gap card: sticky disclaimer at top
- [ ] Orphan list (left column) has ≥ 2 items
- [ ] Covered list (right column) has ≥ 1 item
- [ ] System-wide governance gap badge renders (success or warning style)
- [ ] Compartment meta-graph pyvis canvas renders with 6 visible compartment nodes
- [ ] Edit a compartment in Topology, return to Comparative — all 5 cards reflect the edit (fully reactive)

## Cross-view panel
- [ ] Filter toolbar shows 4 controls (DAPSI, Channels, cycles_only, types) + Refresh button
- [ ] Pre-Refresh: card 1 shows "Click Refresh ⟳ to build the composite graph."
- [ ] Pre-Refresh: card 2 (loops table) shows informational row
- [ ] Bridge bar chart (card 3) renders 3 bars per compartment
- [ ] Click Refresh → composite renders; 6 compartment nodes visible
- [ ] Click a Balancing loop row → loop edges turn red, non-loop edges fade, loop nodes become diamond
- [ ] Click a different row → highlight switches
- [ ] Click selected row to deselect → highlight clears
- [ ] **CHUNK-3-INVARIANT-3 ANALOG**: Select a loop → click Refresh → highlight clears (no red edges survive)
- [ ] Toggle cycles_only on → click Refresh → composite shrinks visibly
- [ ] Channels off + cycles_only on → click Refresh → empty-filter-combo placeholder appears
- [ ] Toggle a filter without clicking Refresh → dirty-hint text appears
- [ ] Edit data in Topology → return to Cross-view → "data changed — click Refresh" hint visible
- [ ] Refresh → hint disappears

## Accessibility spot-check
- [ ] Tab key navigates through filter toolbar controls in order
- [ ] Heatmap <img> has a non-empty alt attribute (inspect via dev tools)
- [ ] Bridge bar chart <img> has a non-empty alt attribute
- [ ] Dirty-hint container has role="status" and aria-live="polite"

## Persistence
- [ ] Save/reload still works (chunks 1–3 persistence tests pass via pytest)
```

- [ ] **Step 3: Commit**

```powershell
git add docs/2026-05-15-chunk4a-smoke-checklist.md
git commit -m "docs(mosaicses): chunk-4a manual smoke checklist"
```

### Task 21: Ship gate — push pending manual smoke pass

- [ ] **Step 1: Verify state ahead of origin/main**

```powershell
git -C "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES" status --short --branch
git -C "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES" log --oneline origin/main..HEAD
```
Expected: clean tree; ~21 commits ahead of `origin/main`.

- [ ] **Step 2: Final pytest sweep**

```powershell
micromamba run -n shiny pytest tests/ -q
```
Expected: all passing.

- [ ] **Step 3: HUMAN GATE — run smoke checklist**

Run the smoke checklist from Task 20 in a real browser. **Do not push until every item is ticked.** Per the saved feedback memory `feedback_runtime_verify_before_shared_state.md`: shared-state actions (push) gate on real-runtime verification, not just unit tests. The chunk-3-Invariant-3-analog item (highlight-survives-Refresh) is the load-bearing one — verify it deliberately.

- [ ] **Step 4: On smoke pass — push to origin**

```powershell
git -C "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES" push origin main
```
Expected: fast-forward push, no force, no `--no-verify`.

- [ ] **Step 5: Chunk 4a shipped**

Update the memory file `chunk3_status.md` (or rename to `chunk4a_status.md`) to record the new HEAD + remaining work for chunk 4b. Suggest invoking `superpowers:brainstorming` for chunk 4b when ready.

---

## Self-review

**Spec coverage:**

| Spec section | Plan task |
|---|---|
| §1.1 in-scope items | Tasks 1 + 2 + 3 + 4–9 + 10–13 + 14 + 15–17 + 18–19 + 20 |
| §1.2 out-of-scope deferrals | Documented at top + Task 14 inline-style stub with id |
| §2 decisions table (17 rows) | Each decision honoured: matplotlib dpi=72 (Task 6), betweenness default (Task 6 server), per-compartment top-K (Task 6 helpers), refresh-effect cleanup (Task 11), last_built_loops (Task 11), aria-live (Task 10), redundant node cues (Task 10 JS), sticky disclaimer (Task 8), system-wide badge (Task 8), and so on |
| §3 architecture | Tasks 2 + 3 + 4 + 10 + 14 |
| §4.1 cards 1–5 | Tasks 5 + 6 + 7 + 8 + 9 |
| §4.2 toolbar + cards 1–3 + JS handler | Tasks 10 + 11 + 12 + 13 |
| §5 data flow | Task 11 (refresh effect + invalidation effect + dirty hint) |
| §6 error handling | Task 6 (eigenvector fallback); placeholders in Tasks 8, 11 |
| §7 testing | Tasks 15–19 |
| §8 acceptance criteria | Tasks 18 + 19 e2e + Task 20 smoke |
| §9 Task 0 probes (14 probes) | Task 0 (one step per probe) |
| §10 hand-off | Task 21 ship gate |
| §11 revision history | n/a (plan-level) |

**Placeholder scan:** no "TBD"/"TODO"/"fill in later"/"add error handling" appear. The closest are:
- "replace per probe result" in Task 10 JS — explicit substitution gated on Task 0 Probe 4's *capture*
- "paste literal from Task 0 Probe 7" in Task 2 — explicit substitution gated on probe data

Both are concrete instructions, not placeholders.

**Type consistency:**
- `last_built_composite`, `last_built_loops`, `last_applied` — introduced Task 11, consumed Task 12 — same names, same shapes.
- `_edge_dom_id(u, v)` — introduced Task 12, referenced in Task 10 JS — naming consistent.
- `_restrict_digraph(g, keep_nodes, keep_edges)` — introduced Task 11, called in same task — signature consistent.
- `_centrality`, `_compartment_of`, `_build_heatmap_matrix`, `_heatmap_alt_text` — introduced Task 6, consistent throughout.
- `_loops_dataframe`, `_bridge_chart_alt_text` — introduced Tasks 12, 13.

**Gap check:** all spec-flagged risks (R1, R2, R3 from the multi-angle review) have explicit mitigations in plan tasks. ✅

---

## Execution handoff

**Plan complete and saved to** `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESPy\docs\superpowers\plans\2026-05-15-mosaicses-chunk4a-comparative-crossview.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task with the two-stage (spec compliance → code quality) review pattern that caught the chunk-3 plan defect.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans` with batch checkpoints.

Which approach?
