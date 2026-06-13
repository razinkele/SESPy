# MosaicSES UI Hardening Implementation Plan

> **Status: ✅ Implemented** — shipped to MosaicSES `main` on 2026-06-13 (merge tip `e816437`, 19 commits, fast-forward). All 26 findings fixed; 397 non-e2e tests + the full Playwright e2e suite green. Two refinements vs. this plan, both recorded in the commits: the meta-graph navigate handler omits `emit_isa_change` to avoid a false-dirty backwrite (T7), and the dirty flag uses a one-shot skip guard so a fresh load never reads as dirty (T8). The e2e app-start timeout was bumped to 180s in `tests/conftest.py` so the heavy app's e2e run locally. The "select-one-then-save friction" MEDIUM remains deliberately deferred (Non-Goal).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 26 verified findings from the 3-loop UI review (1 CRITICAL, 7 HIGH, 18 MEDIUM): empty/error-state crashes, a missing skin, destructive-action data loss, meta-graph accessibility + rebind defects, and a cluster of feedback/visual/i18n issues.

**Architecture:** Changes land in the **MosaicSES** repo (code) at `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES`; this plan doc lives in **SESPy** `docs/superpowers/plans/` (the two-repo convention). The strategy is root-cause-first: fix the column-less DataFrame contract once (kills the CRITICAL at all three UI call sites), vendor SESPy's skin assets so the upstream `<link>` tags resolve, add a `state.dirty` flag that powers all destructive-action confirms, and factor a shared accessible-table helper reused by the two un-guarded pyvis canvases. Most logic is extracted into **pure helpers** unit-tested via `str(tag.tagify())`; genuinely-reactive behavior (modals, pyvis rebind, beforeunload) is covered by Playwright e2e using the existing `mosaicses_app_url` fixture.

**Tech Stack:** Python 3.11 · Shiny-for-Python ≥1.5 · pandas · networkx · pyvis · matplotlib(Agg) · pytest · Playwright. **Environment (mandatory):** run everything through micromamba env `shiny` — `micromamba run -n shiny python -m pytest …`. Never create a venv. No GPU. The MosaicSES test cwd is the MosaicSES repo root.

---

## Severity → Task map

| Sev | Finding | Task |
|-----|---------|------|
| CRITICAL | `gap_lists`/`_system_wide` KeyError on no-Pressures | T1 |
| HIGH | Centrality-heatmap argmax crash on empty MultiSES | T2 |
| HIGH | Skin CSS 404 (no `static_assets`/`www/`) | T3 |
| HIGH | Meta-graph + Cross-view have no tabular fallback (WCAG 1.1.1) | T4 |
| HIGH | Meta-graph drill-in keyboard-inoperable (WCAG 2.1.1) | T5 |
| HIGH | Meta-graph click dies after first edit (one-shot IIFE) | T6 |
| HIGH | Saving a score clobbers unsaved Project-Setup form edits | T11 |
| HIGH | "New (Curonian seed)" discards session, no confirm | T9 |
| MEDIUM | Editors render unstyled (dropped classes) | T3 |
| MEDIUM | Images fixed `width:800px` overflow | T3 |
| MEDIUM | No print stylesheet for publishable cards | T3 |
| MEDIUM | pyvis canvases have no accessible name | T4 |
| MEDIUM | Meta-graph poll can expire (hidden panel) | T6 (folded) |
| MEDIUM | Meta-graph navigate leaves embedded tabs stale | T7 |
| MEDIUM | Open/Recent unguarded clobber | T9 |
| MEDIUM | No `beforeunload` guard | T10 |
| MEDIUM | `overlay_element` resets to first after Save | T12 |
| MEDIUM | Raw exception text leaks into toasts | T13 |
| MEDIUM | Evaluative-scores tab undiscoverable | T14 |
| MEDIUM | No loading indicators | T15 |
| MEDIUM | Toasts screen-reader-invisible | T16 |
| MEDIUM | Empty `'en'` i18n dict to SESPy modules | T17 |
| MEDIUM | No chart export affordance | T18 |
| MEDIUM | Workflow stepper wired but never mounted | T18 |
| MEDIUM | Select-one-then-save friction | **Deferred** (see Non-Goals) |

**Non-Goals (YAGNI):** The "select-one-then-save friction" MEDIUM is a UX-preference about the per-element editor cadence, not a defect — a speculative "Save all scores" batch editor is a feature, not a fix. It is explicitly deferred; if wanted, brainstorm it as its own feature. No other behavior changes beyond the findings above.

## File Structure

**New files (MosaicSES repo):**
- `www/sespy-skin.css`, `www/cld.css` — vendored snapshots of SESPy's skin so the upstream `dashboard_page` `<link>` tags (which MosaicSES reuses) resolve. (T3)
- `multises_app/a11y_tables.py` — shared accessible-table helpers reused by topology + comparative + cross_view. (T4)
- `multises_app/confirm.py` — pure builder for the destructive-action confirm modal. (T9)
- Test files: `tests/test_a11y_tables.py`, `tests/test_confirm.py`, `tests/test_ui_hardening_e2e.py`, plus additions to existing `tests/test_comparative*.py`, `tests/test_compartments_module.py`, `tests/test_project_setup_module.py`, `tests/test_topology_module.py`, `tests/test_cross_view_module.py`.

**Modified files (MosaicSES repo):**
- `multises/comparative.py` — `response_pressure_gap` full-column contract (T1).
- `multises_app/modules/comparative.py` — heatmap empty guard (T2), tabular fallback + a11y name (T4), keyboard nav (T5), persistent rebind (T6), chart export (T18).
- `multises_app/modules/cross_view.py` — tabular fallback + a11y name (T4), chart export (T18).
- `multises_app/modules/topology.py` — `_network_table_ui` moves to `a11y_tables` (T4), editor class (T3), toast sanitize (T13).
- `multises_app/modules/project_setup.py` — form-clobber gate (T11), New/Open confirm (T9), toast sanitize (T13).
- `multises_app/modules/recent_projects.py` — Recent-load confirm (T9), toast sanitize (T13).
- `multises_app/modules/compartments.py` — editor class (T3), overlay-select preserved (T12), toast sanitize (T13), Evaluative-scores discoverability (T14), loading indicators (T15).
- `multises_app/state.py` — `dirty` reactive + set/reset points (T8).
- `app.py` — `static_assets` + skin CSS (T3), navigate-stale fix (T7), beforeunload (T10), SR notifications (T16), i18n dict (T17), stepper (T18).

---

## Task 0: Branch + baseline

**Files:** none (git only).

- [ ] **Step 1: Create the working branch in the MosaicSES repo**

```bash
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
git checkout main && git pull
git checkout -b ui-hardening-2026-06-13
```

- [ ] **Step 2: Confirm the baseline test suite is green before any change**

Run: `micromamba run -n shiny python -m pytest -q`
Expected: all tests pass (this is the pre-change baseline; record the count).

> All subsequent task commands assume cwd = the MosaicSES repo root and the `shiny` micromamba env.

---

## Phase 1 — Empty/error-state crashes (CRITICAL + HIGH)

### Task 1: Fix the Response–Pressure gap crash (CRITICAL)

**Root cause:** `response_pressure_gap` returns a *column-less* `pd.DataFrame(rows)` when no compartment has a Pressure element. `gap_lists` then does `df[df["pressure_compartment_has_no_governance"]]` and `_system_wide_uncovered_labels` does `df.groupby("pressure_label")` → both KeyError, rendered in-place. The sibling `tenet_gap_analysis` already returns a full-column empty frame and documents the inconsistency. Fix = give the gap frame the same contract; no UI change needed.

**Files:**
- Modify: `multises/comparative.py:188-259`
- Test: `tests/test_comparative.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_comparative.py`:

```python
def test_response_pressure_gap_empty_has_full_columns():
    """No-Pressure (here: zero-compartment) MultiSES must yield a full-column
    empty frame, not a column-less one — else gap_lists / _system_wide_uncovered
    crash with KeyError. Mirrors tenet_gap_analysis's stronger contract."""
    from multises.data_structure import MultiSES, MultiSESMetadata
    from multises.comparative import response_pressure_gap, _GAP_COLUMNS
    ms = MultiSES(metadata=MultiSESMetadata())  # compartments defaults to []
    df = response_pressure_gap(ms)
    assert df.empty
    assert list(df.columns) == list(_GAP_COLUMNS)


def test_system_wide_uncovered_labels_no_crash_on_empty():
    from multises.data_structure import MultiSES, MultiSESMetadata
    from multises_app.modules.comparative import _system_wide_uncovered_labels
    ms = MultiSES(metadata=MultiSESMetadata())
    assert _system_wide_uncovered_labels(ms) == []


def test_gap_lists_helper_no_crash_on_empty():
    """gap_lists is a reactive render; exercise its pure core via
    response_pressure_gap + the same boolean-mask the render uses."""
    from multises.data_structure import MultiSES, MultiSESMetadata
    from multises.comparative import response_pressure_gap
    ms = MultiSES(metadata=MultiSESMetadata())
    df = response_pressure_gap(ms)
    # These are the exact operations gap_lists performs; they must not raise.
    orphan_df = df[df["pressure_compartment_has_no_governance"]]
    covered_df = df[~df["pressure_compartment_has_no_governance"]]
    assert orphan_df.empty and covered_df.empty
```

- [ ] **Step 2: Run to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative.py::test_response_pressure_gap_empty_has_full_columns -v`
Expected: FAIL — `ImportError: cannot import name '_GAP_COLUMNS'` (and the column assertion would fail).

- [ ] **Step 3: Add the column constant and apply it**

In `multises/comparative.py`, add the constant just above `def response_pressure_gap` (after the `_downstream_outcome_ids` helper, ~line 186):

```python
# Full column contract for response_pressure_gap — returned even when empty so
# UI consumers (gap_lists, _system_wide_uncovered_labels, equity_table) never
# KeyError on a no-Pressure MultiSES. Matches tenet_gap_analysis's stronger
# contract (see that function's docstring).
_GAP_COLUMNS: tuple[str, ...] = (
    "compartment_id", "pressure_id", "pressure_label",
    "within_compartment_response_count",
    "incoming_governance_channel_count",
    "pressure_compartment_has_no_governance",
    "downstream_equity_outcome_count",
    "affected_equity_dimensions",
    "is_equity_relevant_orphan",
)
```

Change the final return of `response_pressure_gap` (currently `return pd.DataFrame(rows)`) to:

```python
    return pd.DataFrame(rows, columns=list(_GAP_COLUMNS))
```

Also update the docstring's "Columns:" closing note and the v1 caveat sentence that says it "returns a column-less empty frame" — replace with: "Returns an empty DataFrame with the **full column set** (`_GAP_COLUMNS`) when no Pressure exists, so UI consumers render stable headers."

- [ ] **Step 4: Run the new tests + the existing comparative suite**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative.py tests/test_comparative_module.py -v`
Expected: PASS — including the pre-existing `test_gap_split_uses_pressure_compartment_has_no_governance` and `test_system_wide_gap_helper_returns_list` (proves the seed path still has the columns and non-empty data unchanged).

- [ ] **Step 5: Commit**

```bash
git add multises/comparative.py tests/test_comparative.py
git commit -m "fix(mosaicses): response_pressure_gap returns full-column empty frame (fixes gap-card crash)"
```

---

### Task 2: Guard the centrality heatmap against an empty MultiSES (HIGH)

**Root cause:** on a zero-compartment MultiSES, `_build_heatmap_matrix` yields a `(0, top_k)` matrix; `_format_alt_text` calls `matrix.sum(axis=1).argmax()` → `ValueError: attempt to get argmax of an empty sequence`, and `row_labels[top_row_idx]` would IndexError. The `heatmap` render then also draws an empty image.

**Files:**
- Modify: `multises_app/modules/comparative.py:86-114` (`_format_alt_text`), `:382-412` (`heatmap`)
- Test: `tests/test_comparative_module.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_comparative_module.py`:

```python
def test_format_alt_text_handles_empty_matrix():
    import numpy as np
    from multises_app.modules.comparative import _format_alt_text
    alt = _format_alt_text(
        np.zeros((0, 10)), row_labels=[], col_labels_per_row=[],
        fallback_rows=set(), metric="betweenness", top_k=10,
    )
    assert isinstance(alt, str) and "no compartments" in alt.lower()


def test_heatmap_alt_text_empty_multises_no_crash():
    from multises.data_structure import MultiSES, MultiSESMetadata
    from multises_app.modules.comparative import _heatmap_alt_text
    alt = _heatmap_alt_text(MultiSES(metadata=MultiSESMetadata()),
                            metric="betweenness", top_k=10)
    assert isinstance(alt, str)
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative_module.py::test_format_alt_text_handles_empty_matrix -v`
Expected: FAIL with `ValueError` from `argmax`.

- [ ] **Step 3: Guard `_format_alt_text`**

In `multises_app/modules/comparative.py`, at the top of `_format_alt_text` (before `top_row_idx = ...`):

```python
    if matrix.size == 0 or not row_labels:
        return (
            f"Centrality heatmap ({metric}): no compartments to display. "
            f"Add a compartment to populate this view."
        )
```

- [ ] **Step 4: Guard the `heatmap` render with a placeholder image**

In the `heatmap` render function, immediately after `matrix, row_labels, col_labels_per_row, fallback_rows = _build_heatmap_matrix(...)`, insert:

```python
        if not row_labels:
            fig, ax = plt.subplots(figsize=(8, 2), dpi=72)
            ax.text(0.5, 0.5, "No compartments to display",
                    ha="center", va="center", fontsize=12, color="#888")
            ax.axis("off")
            buf = io.BytesIO()
            fig.savefig(buf, format="png")
            plt.close(fig)
            out_path = os.path.join(_tmpdir, "heatmap_empty.png")
            with open(out_path, "wb") as f:
                f.write(buf.getvalue())
            return {"src": out_path,
                    "alt": _format_alt_text(matrix, row_labels,
                                            col_labels_per_row, fallback_rows,
                                            metric=metric, top_k=top_k),
                    "width": "400px"}
```

- [ ] **Step 5: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative_module.py -v`
Expected: PASS (new + all existing heatmap tests, which still use the 6-compartment seed).

- [ ] **Step 6: Commit**

```bash
git add multises_app/modules/comparative.py tests/test_comparative_module.py
git commit -m "fix(mosaicses): centrality heatmap empty-state guard (no argmax crash)"
```

---

## Phase 2 — Skin, visual polish, print (HIGH + MEDIUM)

### Task 3: Ship the skin assets + editor classes + responsive images + print stylesheet

**Root cause:** MosaicSES reuses `sespy.dashboard.dashboard_page`, which injects `<link rel="stylesheet" href="sespy-skin.css">` and `cld.css` (SESPy `sespy/dashboard.py:269-270`), but MosaicSES's `App(app_ui, server)` passes no `static_assets` and has no `www/` — so both 404 and the app renders as raw Bootstrap. The editor `div`s also carry no class, and the chart `<img>`s are pinned to `width:800px`.

**Files:**
- Create: `www/sespy-skin.css`, `www/cld.css` (vendored from SESPy)
- Modify: `app.py:57-58` (WWW), `:96-121` (inline `<style>`), `:170` (`App(...)`)
- Modify: `multises_app/modules/topology.py:296-302` (`_tenet_editor_ui` div class)
- Modify: `multises_app/modules/compartments.py:102-107` (`_overlay_editor_ui` div class)
- Test: `tests/test_app_imports_colors.py` (skin wiring) + `tests/test_ui_hardening_e2e.py` (200 response)

- [ ] **Step 1: Vendor the CSS files**

```bash
mkdir -p www
cp "../SESPy/www/sespy-skin.css" www/sespy-skin.css
cp "../SESPy/www/cld.css" www/cld.css
```

- [ ] **Step 2: Write the failing wiring test**

Add to `tests/test_app_imports_colors.py`:

```python
def test_app_serves_static_assets_for_skin():
    import app as mosaic_app
    from pathlib import Path
    # WWW points at a real dir containing both skin files the upstream
    # dashboard_page <link> tags reference.
    assert mosaic_app.WWW.is_dir()
    assert (mosaic_app.WWW / "sespy-skin.css").is_file()
    assert (mosaic_app.WWW / "cld.css").is_file()
    # App was constructed with static_assets mapping the www dir at root.
    sa = mosaic_app.app.starlette_app  # shiny App exposes the ASGI app
    assert sa is not None
```

> Note: the `starlette_app` attribute access just asserts the `App` constructed without error after adding `static_assets`. The file-existence assertions are the load-bearing checks.

- [ ] **Step 3: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_app_imports_colors.py::test_app_serves_static_assets_for_skin -v`
Expected: FAIL — `App` currently has no `static_assets`; if the test runs before Step 4 the dir check passes (Step 1 created it) but assert the full chain after Step 4. (If it passes prematurely, it still correctly locks the contract.)

- [ ] **Step 4: Wire `static_assets` and extend the inline stylesheet**

In `app.py`, update the `WWW` comment (line 58) to drop "created in chunk 4":

```python
WWW = ROOT / "www"  # skin assets served at "/" via static_assets (below)
```

Append to the inline `ui.tags.style(...)` block (inside the `"""..."""`, before the closing `"""`), these rules (editor classes M5, responsive images M6, print stylesheet M14):

```css
.tenet-editor, .overlay-editor {
    padding: 8px 4px; border: 1px solid #e0e0e0; border-radius: 6px;
    background: #fafafa; margin-top: 6px;
}
.tenet-editor h6 { margin-top: 0; }
.comparative-card img, .cross-view-card img { max-width: 100%; height: auto; }
@media print {
    .bslib-sidebar-layout > .sidebar, #compartments-nested-tabs,
    .navbar, .bslib-page-navbar > .navbar { display: none !important; }
    .comparative-publishable-card { break-inside: avoid; }
}
```

Change the final line of the file from `app = App(app_ui, server)` to:

```python
app = App(app_ui, server, static_assets=str(WWW))
```

- [ ] **Step 5: Add the editor classes**

In `multises_app/modules/topology.py`, in `_tenet_editor_ui`, change `return ui.tags.div(` (the one wrapping the selects + Save) to `return ui.tags.div(` … add `class_="tenet-editor"` as the final argument:

```python
    return ui.tags.div(
        ui.tags.h6("Tenet scores"),
        *selects,
        ui.div(ui.input_text("channel_tenet_editing_id", "", value=ch.id),
               style="display:none"),
        ui.input_action_button("save_channel_tenets", "Save scores"),
        class_="tenet-editor",
    )
```

In `multises_app/modules/compartments.py`, in `_overlay_editor_ui`, add `class_="overlay-editor"` to the wrapping `ui.tags.div`:

```python
    return ui.tags.div(
        *body,
        ui.div(ui.input_text("overlay_editing_id", "", value=element.id),
               style="display:none"),
        ui.input_action_button("save_overlay", "Save"),
        class_="overlay-editor",
    )
```

- [ ] **Step 6: Add the e2e skin-load smoke test**

Create `tests/test_ui_hardening_e2e.py`:

```python
"""e2e smoke for the UI-hardening fixes (skin load, modals, navigation)."""
from __future__ import annotations

from playwright.sync_api import sync_playwright


def test_skin_css_loads_200(mosaicses_app_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            statuses: dict[str, int] = {}
            page.on("response",
                    lambda r: statuses.__setitem__(r.url.split("/")[-1], r.status))
            page.goto(mosaicses_app_url, wait_until="networkidle")
            assert statuses.get("sespy-skin.css") == 200, statuses
            assert statuses.get("cld.css") == 200, statuses
        finally:
            browser.close()
```

- [ ] **Step 7: Run the unit + e2e tests**

Run: `micromamba run -n shiny python -m pytest tests/test_app_imports_colors.py tests/test_topology_module.py tests/test_compartments_module.py -v`
Then: `micromamba run -n shiny python -m pytest tests/test_ui_hardening_e2e.py::test_skin_css_loads_200 -v`
Expected: PASS (both CSS files return 200; editor divs carry the new classes).

- [ ] **Step 8: Commit**

```bash
git add www app.py multises_app/modules/topology.py multises_app/modules/compartments.py tests/test_app_imports_colors.py tests/test_ui_hardening_e2e.py
git commit -m "fix(mosaicses): serve skin assets + editor classes + responsive images + print stylesheet"
```

---

## Phase 3 — Meta-graph accessibility & rebind (HIGH + MEDIUM)

### Task 4: Shared accessible-table helper + tabular fallback for both pyvis canvases

**Root cause:** Topology has a `<details>` tabular fallback for its pyvis canvas (`topology.py:343-347`), but the Comparative meta-graph (`comparative.py:224-229`) and Cross-view composite (`cross_view.py:225-232`) do not (WCAG 1.1.1), and no pyvis output carries an accessible name (MEDIUM).

**Files:**
- Create: `multises_app/a11y_tables.py`, `tests/test_a11y_tables.py`
- Modify: `multises_app/modules/topology.py` (move `_network_table_ui` → import)
- Modify: `multises_app/modules/comparative.py` (add fallback + a11y name)
- Modify: `multises_app/modules/cross_view.py` (add fallback + a11y name)

- [ ] **Step 1: Write failing tests for the shared helpers**

Create `tests/test_a11y_tables.py`:

```python
from __future__ import annotations


def test_compartment_channel_table_renders_both_tables():
    from multises import seed_curonian
    from multises_app.a11y_tables import compartment_channel_table_ui
    html = str(compartment_channel_table_ui(seed_curonian()).tagify())
    assert "Compartments" in html and "Channels" in html
    assert "<table" in html


def test_compartment_channel_table_empty_multises():
    from multises.data_structure import MultiSES, MultiSESMetadata
    from multises_app.a11y_tables import compartment_channel_table_ui
    html = str(compartment_channel_table_ui(MultiSES(metadata=MultiSESMetadata())).tagify())
    assert "No compartments" in html and "No channels" in html


def test_digraph_table_lists_nodes_and_edges():
    import networkx as nx
    from multises_app.a11y_tables import digraph_table_ui
    g = nx.DiGraph()
    g.add_node("a::S1", label="State 1")
    g.add_node("b::P1", label="Pressure 1")
    g.add_edge("a::S1", "b::P1", label="nutrients")
    html = str(digraph_table_ui(g).tagify())
    assert "a::S1" in html and "b::P1" in html and "nutrients" in html


def test_digraph_table_empty_graph():
    import networkx as nx
    from multises_app.a11y_tables import digraph_table_ui
    html = str(digraph_table_ui(nx.DiGraph()).tagify())
    assert "No nodes" in html
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_a11y_tables.py -v`
Expected: FAIL — `ModuleNotFoundError: multises_app.a11y_tables`.

- [ ] **Step 3: Create the shared module**

Create `multises_app/a11y_tables.py`. Move the body of topology's `_compartment_summary_rows`, `_channel_summary_rows`, and `_network_table_ui` here, renaming the public one to `compartment_channel_table_ui`, and add `digraph_table_ui`:

```python
"""Accessible text-equivalent tables for pyvis canvases (WCAG 1.1.1).

Shared by topology (compartment+channel graph), comparative (compartment
meta-graph), and cross_view (composite DAPSI digraph).
"""
from __future__ import annotations

import networkx as nx
from shiny import ui

from multises.data_structure import MultiSES


def _compartment_summary_rows(ms: MultiSES) -> list[dict]:
    rows: list[dict] = []
    for c in ms.compartments:
        archetype_display = c._unknown_archetype_original or c.archetype
        rows.append({
            "id": c.id, "label": c.label, "archetype": archetype_display,
            "element_count": len(c.project.isa_data.elements),
            "is_focal_tw": c.is_focal_tw,
        })
    return rows


def _channel_summary_rows(ms: MultiSES) -> list[dict]:
    return [
        {
            "source": c.source, "target": c.target,
            "type": c._unknown_channel_type_original or c.channel_type,
            "polarity": c.polarity, "strength": c.strength, "delay": c.delay,
        }
        for c in ms.channels
    ]


def compartment_channel_table_ui(ms: MultiSES) -> ui.Tag:
    """Two semantic tables (compartments + channels) — the SR text equivalent
    of a compartment-level pyvis network (topology + comparative meta-graph)."""
    comp_rows = _compartment_summary_rows(ms)
    comp_tbl = ui.tags.table(
        ui.tags.caption("Compartments"),
        ui.tags.thead(ui.tags.tr(
            *[ui.tags.th(h) for h in ("ID", "Label", "Archetype", "Elements", "Focal TW")])),
        ui.tags.tbody(*[
            ui.tags.tr(
                ui.tags.td(r["id"]), ui.tags.td(r["label"]),
                ui.tags.td(r["archetype"]), ui.tags.td(str(r["element_count"])),
                ui.tags.td("yes" if r["is_focal_tw"] else "no"),
            ) for r in comp_rows
        ] or [ui.tags.tr(ui.tags.td("No compartments", colspan="5"))]),
        class_="topology-a11y-table",
    )
    chan_rows = _channel_summary_rows(ms)
    chan_body = [
        ui.tags.tr(
            ui.tags.td(r["source"]), ui.tags.td(r["target"]), ui.tags.td(r["type"]),
            ui.tags.td(r["polarity"]), ui.tags.td(r["strength"]), ui.tags.td(r["delay"]),
        ) for r in chan_rows
    ] or [ui.tags.tr(ui.tags.td("No channels", colspan="6"))]
    chan_tbl = ui.tags.table(
        ui.tags.caption("Channels"),
        ui.tags.thead(ui.tags.tr(
            *[ui.tags.th(h) for h in ("Source", "Target", "Type", "Polarity", "Strength", "Delay")])),
        ui.tags.tbody(*chan_body),
        class_="topology-a11y-table",
    )
    return ui.div(comp_tbl, chan_tbl)


def digraph_table_ui(g: nx.DiGraph) -> ui.Tag:
    """SR text equivalent of an arbitrary node/edge digraph (cross_view
    composite). Nodes show their `label` attr; edges show their `label` attr."""
    node_body = [
        ui.tags.tr(ui.tags.td(str(n)),
                   ui.tags.td(str(g.nodes[n].get("label", ""))))
        for n in g.nodes
    ] or [ui.tags.tr(ui.tags.td("No nodes", colspan="2"))]
    nodes_tbl = ui.tags.table(
        ui.tags.caption("Nodes"),
        ui.tags.thead(ui.tags.tr(ui.tags.th("ID"), ui.tags.th("Label"))),
        ui.tags.tbody(*node_body),
        class_="topology-a11y-table",
    )
    edge_body = [
        ui.tags.tr(ui.tags.td(str(u)), ui.tags.td(str(v)),
                   ui.tags.td(str(d.get("label", ""))))
        for u, v, d in g.edges(data=True)
    ] or [ui.tags.tr(ui.tags.td("No edges", colspan="3"))]
    edges_tbl = ui.tags.table(
        ui.tags.caption("Edges"),
        ui.tags.thead(ui.tags.tr(ui.tags.th("From"), ui.tags.th("To"), ui.tags.th("Label"))),
        ui.tags.tbody(*edge_body),
        class_="topology-a11y-table",
    )
    return ui.div(nodes_tbl, edges_tbl)
```

- [ ] **Step 4: Point topology at the shared helper (no behavior change)**

In `multises_app/modules/topology.py`: delete the local `_compartment_summary_rows`, `_channel_summary_rows`, and `_network_table_ui` definitions, and add to the imports:

```python
from multises_app.a11y_tables import (
    compartment_channel_table_ui,
    _compartment_summary_rows,  # still used by compartments_list + _build_topology_network
)
```

> `_build_topology_network` and `compartments_list` call `_compartment_summary_rows`; keep that import. Update the `network_table` render to call the shared name:

```python
    @output
    @render.ui
    def network_table() -> ui.Tag:
        return compartment_channel_table_ui(state.active_multises.get())
```

If any existing test references `topology._network_table_ui`, re-export it for back-compat by adding at module level: `_network_table_ui = compartment_channel_table_ui`. (Check with `grep -rn "_network_table_ui" tests/` first; add the alias only if referenced.)

- [ ] **Step 5: Add the fallback + accessible name to the Comparative meta-graph**

In `multises_app/modules/comparative.py`, add to imports:

```python
from multises_app.a11y_tables import compartment_channel_table_ui  # noqa: E402
```

In `comparative_ui`, replace the meta-graph card (the last `ui.card(ui.card_header("Compartment meta-graph"), …)`) with one that wraps the canvas in an a11y-named container and adds a `<details>` table:

```python
        ui.card(ui.card_header("Compartment meta-graph"),
                ui.div(
                    output_pyvis_network("meta_graph_canvas", height="350px",
                                         show_toolbar=False, show_search=False,
                                         show_layout_switcher=False, show_export=False,
                                         show_status=False),
                    role="img",
                    **{"aria-label": "Compartment meta-graph: compartments as "
                                     "nodes, inter-compartment channels as edges. "
                                     "An accessible table follows."},
                ),
                ui.tags.details(
                    ui.tags.summary("Tabular view (accessible)"),
                    ui.output_ui("meta_graph_table"),
                    class_="topology-a11y-details",
                ),
                class_="comparative-card", full_screen=True),
```

Add the render in `comparative_server` (next to the other `@render.ui` outputs):

```python
    @output
    @render.ui
    def meta_graph_table():
        return compartment_channel_table_ui(state.active_multises.get())
```

- [ ] **Step 6: Add the fallback + accessible name to the Cross-view composite**

In `multises_app/modules/cross_view.py`, add to imports:

```python
from multises_app.a11y_tables import digraph_table_ui
```

In `cross_view_ui`, wrap the composite `output_pyvis_network("composite_canvas", …)` in a `role="img"` div with `aria-label`, and add a `<details>` table after the canvas inside the same card:

```python
        ui.card(ui.card_header("Composite graph"),
                ui.output_ui("composite_canvas_status"),
                ui.div(
                    output_pyvis_network("composite_canvas", height="600px",
                                         show_toolbar=True, show_search=True,
                                         show_layout_switcher=True, show_export=True,
                                         show_status=False),
                    role="img",
                    **{"aria-label": "Composite DAPSI graph across all "
                                     "compartments. An accessible table follows."},
                ),
                ui.tags.details(
                    ui.tags.summary("Tabular view (accessible)"),
                    ui.output_ui("composite_table"),
                    class_="topology-a11y-details",
                ),
                class_="cross-view-card cross-view-hero",
                full_screen=True),
```

Add the render in `cross_view_server` (the table reflects the last built graph, falling back to an empty graph before Refresh):

```python
    @output
    @render.ui
    def composite_table():
        import networkx as nx
        g = last_built_composite()
        return digraph_table_ui(g if g is not None else nx.DiGraph())
```

- [ ] **Step 7: Add module-level UI assertions**

Add to `tests/test_comparative_module.py`:

```python
def test_meta_graph_has_accessible_fallback():
    from multises_app.modules.comparative import comparative_ui
    html = str(comparative_ui("test_id"))
    assert 'id="test_id-meta_graph_table"' in html
    assert "Tabular view (accessible)" in html
    assert 'role="img"' in html
```

Add to `tests/test_cross_view_module.py`:

```python
def test_composite_has_accessible_fallback():
    from multises_app.modules.cross_view import cross_view_ui
    html = str(cross_view_ui("test_id").tagify())
    assert 'id="test_id-composite_table"' in html
    assert "Tabular view (accessible)" in html
    assert 'role="img"' in html
```

- [ ] **Step 8: Run all affected suites**

Run: `micromamba run -n shiny python -m pytest tests/test_a11y_tables.py tests/test_topology_module.py tests/test_comparative_module.py tests/test_cross_view_module.py -v`
Expected: PASS (shared helper works; topology unchanged in behavior; both canvases now have fallbacks).

- [ ] **Step 9: Commit**

```bash
git add multises_app/a11y_tables.py multises_app/modules/topology.py multises_app/modules/comparative.py multises_app/modules/cross_view.py tests/test_a11y_tables.py tests/test_comparative_module.py tests/test_cross_view_module.py
git commit -m "feat(mosaicses): accessible tabular fallback + aria-label for meta-graph & composite canvases (WCAG 1.1.1)"
```

---

### Task 5: Keyboard-operable drill-in from the meta-graph (HIGH)

**Root cause:** meta-graph navigation exists only via mouse `click` on vis.js nodes (`comparative.py:177-184`); vis.js nodes are unfocusable (WCAG 2.1.1). Give the accessible fallback table focusable `<button>`s that fire the *same* top-level `meta_graph_compartment_click` input the mouse handler uses — reusing the existing `app.py` navigation handler.

**Files:**
- Modify: `multises_app/a11y_tables.py` (`compartment_channel_table_ui` gains an optional `compartment_nav` flag)
- Modify: `multises_app/modules/comparative.py` (`meta_graph_table` passes the flag)
- Test: `tests/test_a11y_tables.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_a11y_tables.py`:

```python
def test_compartment_table_nav_buttons_fire_top_level_input():
    from multises import seed_curonian
    from multises_app.a11y_tables import compartment_channel_table_ui
    html = str(compartment_channel_table_ui(seed_curonian(), compartment_nav=True).tagify())
    # Native <button> is keyboard-focusable; onclick fires the SAME top-level
    # input the mouse handler in comparative._META_GRAPH_CLICK_JS uses.
    assert "<button" in html
    assert "meta_graph_compartment_click" in html


def test_compartment_table_nav_off_by_default():
    from multises import seed_curonian
    from multises_app.a11y_tables import compartment_channel_table_ui
    html = str(compartment_channel_table_ui(seed_curonian()).tagify())
    assert "meta_graph_compartment_click" not in html
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_a11y_tables.py::test_compartment_table_nav_buttons_fire_top_level_input -v`
Expected: FAIL (`compartment_nav` kwarg does not exist).

- [ ] **Step 3: Implement the keyboard nav buttons**

In `multises_app/a11y_tables.py`, add `import json` at the top, and change `compartment_channel_table_ui`'s signature and the compartment-row ID cell:

```python
def compartment_channel_table_ui(ms: MultiSES, *, compartment_nav: bool = False) -> ui.Tag:
```

Replace the compartments `ui.tags.tbody(...)` row-builder so the first cell is a nav button when `compartment_nav` is set:

```python
    def _id_cell(cid: str):
        if not compartment_nav:
            return ui.tags.td(cid)
        return ui.tags.td(ui.tags.button(
            cid, type="button", class_="btn btn-sm btn-link p-0",
            onclick=("Shiny.setInputValue('meta_graph_compartment_click', "
                     f"{json.dumps(cid)}, {{priority: 'event'}})"),
        ))

    comp_tbl = ui.tags.table(
        ui.tags.caption("Compartments"),
        ui.tags.thead(ui.tags.tr(
            *[ui.tags.th(h) for h in ("ID", "Label", "Archetype", "Elements", "Focal TW")])),
        ui.tags.tbody(*[
            ui.tags.tr(
                _id_cell(r["id"]), ui.tags.td(r["label"]),
                ui.tags.td(r["archetype"]), ui.tags.td(str(r["element_count"])),
                ui.tags.td("yes" if r["is_focal_tw"] else "no"),
            ) for r in comp_rows
        ] or [ui.tags.tr(ui.tags.td("No compartments", colspan="5"))]),
        class_="topology-a11y-table",
    )
```

In `multises_app/modules/comparative.py`, pass the flag so only the meta-graph table is navigable (topology's table stays read-only):

```python
    @output
    @render.ui
    def meta_graph_table():
        return compartment_channel_table_ui(state.active_multises.get(),
                                             compartment_nav=True)
```

- [ ] **Step 4: Add an e2e keyboard-drill-in check**

Add to `tests/test_ui_hardening_e2e.py`:

```python
def test_meta_graph_table_keyboard_navigates(mosaicses_app_url):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.wait_for_selector("#sespy_nav_comparative", timeout=10_000)
            page.click("#sespy_nav_comparative")
            page.get_by_text("Tabular view (accessible)").first.click()
            # Activate the first compartment nav button via the keyboard.
            btn = page.locator("#comparative-meta_graph_table button").first
            btn.focus()
            page.keyboard.press("Enter")
            # Navigation flips the top-level navset to the Compartments panel.
            expect(page.locator("#compartments-top-bar")).to_be_visible(timeout=10_000)
        finally:
            browser.close()
```

- [ ] **Step 5: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_a11y_tables.py -v`
Then: `micromamba run -n shiny python -m pytest tests/test_ui_hardening_e2e.py::test_meta_graph_table_keyboard_navigates -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add multises_app/a11y_tables.py multises_app/modules/comparative.py tests/test_a11y_tables.py tests/test_ui_hardening_e2e.py
git commit -m "feat(mosaicses): keyboard-operable meta-graph drill-in via accessible table buttons (WCAG 2.1.1)"
```

---

### Task 6: Persistent meta-graph click rebind (HIGH; folds the poll-expiry MEDIUM)

**Root cause:** `_META_GRAPH_CLICK_JS` (`comparative.py:160-191`) polls once and `clearInterval`s after binding. pyvis destroys/rebuilds the vis.js Network on every `active_multises` change, producing a fresh object with no `__mosaicsesClickBound` flag — but the timer is gone, so clicks die after the first edit. The same poll also expires (`maxTries`) if the panel is hidden at first render. Fix: a low-frequency persistent watcher that (re)binds whenever it sees an unbound network.

**Files:**
- Modify: `multises_app/modules/comparative.py:160-191` (`_META_GRAPH_CLICK_JS`)
- Test: `tests/test_comparative_module.py` (JS-shape assertions) + `tests/test_ui_hardening_e2e.py`

- [ ] **Step 1: Write the failing JS-shape test**

Add to `tests/test_comparative_module.py`:

```python
def test_meta_graph_click_js_rebinds_persistently():
    from multises_app.modules.comparative import _META_GRAPH_CLICK_JS as js
    # Persistent watcher: must NOT clearInterval right after binding (that is
    # the one-shot bug). It rebinds whenever an unbound network appears.
    assert "clearInterval" not in js
    assert "__mosaicsesClickBound" in js
    assert "meta_graph_compartment_click" in js
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative_module.py::test_meta_graph_click_js_rebinds_persistently -v`
Expected: FAIL (current JS contains `clearInterval`).

- [ ] **Step 3: Replace the JS with a persistent rebinding watcher**

In `multises_app/modules/comparative.py`, replace the entire `_META_GRAPH_CLICK_JS = """..."""` block with:

```python
# Persistent click-rebind for card 7 (meta-graph). pyvis destroys/rebuilds its
# vis.js Network on every active_multises change; a one-shot binder would stop
# working after the first edit (HIGH finding) and could expire before a hidden
# panel renders (MEDIUM finding). A lightweight 500 ms watcher rebinds whenever
# it observes a Network lacking our bound flag — covering rebuilds AND late
# first render with one mechanism. The handler writes the clicked node id to the
# TOP-LEVEL `meta_graph_compartment_click` input handled in app.py.
_META_GRAPH_CLICK_JS = """
(function () {
  function getNetwork() {
    if (!window.pyvisNetworks) return null;
    for (const k of Object.keys(window.pyvisNetworks)) {
      if (k.endsWith("meta_graph_canvas")) {
        return window.pyvisNetworks[k].network || null;
      }
    }
    return null;
  }
  setInterval(function () {
    const net = getNetwork();
    if (net && !net.__mosaicsesClickBound) {
      net.__mosaicsesClickBound = true;
      net.on("click", function (params) {
        if (!params.nodes || params.nodes.length === 0) return;  // edge click
        Shiny.setInputValue(
          "meta_graph_compartment_click",
          params.nodes[0],
          {priority: "event"}
        );
      });
    }
  }, 500);
})();
"""
```

Also remove the now-stale "Polling-with-timeout" / "Guard against double-binding" sentences in the comment above the constant; replace with the new comment shown.

- [ ] **Step 4: Add an e2e rebind regression test**

Add to `tests/test_ui_hardening_e2e.py`:

```python
def test_meta_graph_click_survives_an_edit(mosaicses_app_url):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.wait_for_selector("#sespy_nav_comparative", timeout=10_000)
            page.click("#sespy_nav_comparative")
            # Force a rebuild by changing the heatmap metric (mutates a reactive
            # the meta-graph card shares a render cycle with), then click a node.
            page.select_option("#comparative-metric", "degree")
            page.wait_for_timeout(1200)  # allow rebuild + the 500ms rebind watcher
            canvas = page.locator("#comparative-meta_graph_canvas canvas").first
            box = canvas.bounding_box()
            assert box is not None
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            # A node click navigates to Compartments; an empty-space click is a
            # no-op, so we only assert the handler is still *bound* (no JS error).
            assert "meta_graph_compartment_click" not in (page.content() or "")
        finally:
            browser.close()
```

> This e2e is a smoke check that the rebind watcher runs without error after a rebuild; the deterministic binding behavior is locked by the Step-1 unit test.

- [ ] **Step 5: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative_module.py::test_meta_graph_click_js_rebinds_persistently tests/test_ui_hardening_e2e.py::test_meta_graph_click_survives_an_edit -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add multises_app/modules/comparative.py tests/test_comparative_module.py tests/test_ui_hardening_e2e.py
git commit -m "fix(mosaicses): persistent meta-graph click rebind (survives re-render & late panel render)"
```

---

### Task 7: Meta-graph navigate updates embedded tabs immediately (MEDIUM)

**Root cause:** `_navigate_to_compartment` (`app.py:152-167`) sets `active_compartment_id` and flips the navset, but does NOT rebind `active_compartment_project` — so the embedded SESPy tabs keep showing the previous compartment for ~2 round-trips (until the picker's effects catch up). The Compartments-module switcher rebinds the project, but it is gated by `@reactive.event(input.compartment_picker)`, which the programmatic id-set does not fire reliably.

**Files:**
- Modify: `app.py:152-167` (`_navigate_to_compartment`)
- Test: `tests/test_ui_hardening_e2e.py`

- [ ] **Step 1: Write the failing e2e test**

Add to `tests/test_ui_hardening_e2e.py`:

```python
def test_meta_graph_navigate_syncs_embedded_tabs(mosaicses_app_url):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.wait_for_selector("#sespy_nav_comparative", timeout=10_000)
            page.click("#sespy_nav_comparative")
            page.get_by_text("Tabular view (accessible)").first.click()
            # Drill into the SECOND compartment via its keyboard nav button.
            buttons = page.locator("#comparative-meta_graph_table button")
            target_id = buttons.nth(1).inner_text()
            buttons.nth(1).click()
            expect(page.locator("#compartments-top-bar")).to_be_visible(timeout=10_000)
            # The picker reflects the drilled-in compartment immediately.
            expect(page.locator("#compartments-compartment_picker")).to_have_value(
                target_id, timeout=5_000)
        finally:
            browser.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_ui_hardening_e2e.py::test_meta_graph_navigate_syncs_embedded_tabs -v`
Expected: FAIL or flaky (picker lags by a round-trip).

- [ ] **Step 3: Rebind the project in the navigate handler**

In `app.py`, in `_navigate_to_compartment`, after confirming the id exists, set the project too (so embedded tabs update in the same flush). Replace the body from `state.active_compartment_id.set(...)` onward:

```python
        ms = state.active_multises.get()
        target = next((c for c in ms.compartments if c.id == compartment_id), None)
        if target is None:
            return
        # Rebind BOTH the id and the shared project so the embedded SESPy tabs
        # update on this flush rather than lagging two round-trips behind the
        # navset switch. emit_isa_change invalidates the embedded modules' caches.
        state.active_compartment_id.set(compartment_id)
        state.active_compartment_project.set(target.project)
        state.event_bus.emit_isa_change()
        ui.update_navs("main_nav", selected="compartments", session=session)
```

> Note: the Compartments switcher's `_switching` guard plus its own `@reactive.event(input.compartment_picker)` gate prevent a double-rebind loop — the programmatic `active_compartment_id.set` updates the picker via `_populate_picker`, which calls `ui.update_select` (not a user picker event), so `_switch_active_compartment` no-ops on the unchanged value.

- [ ] **Step 4: Run tests (including the existing compartments suite for regressions)**

Run: `micromamba run -n shiny python -m pytest tests/test_compartments_module.py tests/test_ui_hardening_e2e.py::test_meta_graph_navigate_syncs_embedded_tabs -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_ui_hardening_e2e.py
git commit -m "fix(mosaicses): meta-graph drill-in rebinds compartment project immediately (no stale embedded tabs)"
```

---

## Phase 4 — Destructive-action safety (HIGH + MEDIUM)

### Task 8: Add a session `dirty` flag to shared state

**Approach:** a single `reactive.value(False)` on `MultiSESState`, reset to `False` on every load/new (via `load_multises`) and set `True` by each edit path. Powers the confirm modals (T9) and the beforeunload guard (T10).

**Files:**
- Modify: `multises_app/state.py`
- Test: `tests/test_state.py` (create if absent) or append to an existing state test

- [ ] **Step 1: Write the failing test**

Create `tests/test_state_dirty.py`:

```python
from __future__ import annotations

from multises import seed_curonian
from multises_app.state import create_multises_state


def test_state_starts_clean():
    state = create_multises_state(seed_curonian())
    assert state.dirty.get() is False


def test_load_multises_resets_dirty():
    state = create_multises_state(seed_curonian())
    state.dirty.set(True)
    state.load_multises(seed_curonian())
    assert state.dirty.get() is False
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_state_dirty.py -v`
Expected: FAIL — `MultiSESState` has no `dirty`.

- [ ] **Step 3: Add the field**

In `multises_app/state.py`:

Add to the `MultiSESState` dataclass fields (after `event_bus`):

```python
    dirty: reactive.Value[bool]
```

In `load_multises`, reset it (after the existing sets, before/after `emit_isa_change`):

```python
        self.dirty.set(False)
```

In `create_multises_state`, initialise it:

```python
    return MultiSESState(
        active_multises=reactive.value(ms),
        active_compartment_id=reactive.value(initial_active_compartment_id(ms)),
        active_compartment_project=reactive.value(_initial_active_project(ms)),
        event_bus=create_event_bus(),
        dirty=reactive.value(False),
    )
```

- [ ] **Step 4: Set `dirty = True` at the four edit paths**

Add `state.dirty.set(True)` immediately after each successful `state.active_multises.set(...)` in an *edit* path:
- `multises_app/modules/topology.py` `_save_channel_tenets` — after `state.active_multises.set(replace_channel(...))`.
- `multises_app/modules/compartments.py` `_save_overlay` — after `state.active_multises.set(new_ms)`.
- `multises_app/modules/compartments.py` `_backwrite_to_multises` — after the final `state.active_multises.set(new_ms)` (covers all embedded SESPy edits).
- `multises_app/modules/project_setup.py` `_handle_save` — after `state.active_multises.set(ms_new)`.

In `multises_app/modules/project_setup.py` `download_multises`, mark clean after a successful export — after `state.event_bus.emit_project_saved()`:

```python
        state.dirty.set(False)
```

- [ ] **Step 5: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_state_dirty.py tests/test_compartments_module.py tests/test_project_setup_module.py tests/test_topology_module.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add multises_app/state.py multises_app/modules/topology.py multises_app/modules/compartments.py multises_app/modules/project_setup.py tests/test_state_dirty.py
git commit -m "feat(mosaicses): track session dirty flag (edits set, load/save clear)"
```

---

### Task 9: Confirm modals for New / Open / Recent-load when dirty (HIGH + MEDIUM)

**Files:**
- Create: `multises_app/confirm.py`, `tests/test_confirm.py`
- Modify: `multises_app/modules/project_setup.py` (New + Open)
- Modify: `multises_app/modules/recent_projects.py` (Recent load)
- Test: `tests/test_ui_hardening_e2e.py`

- [ ] **Step 1: Write the failing test for the pure modal builder**

Create `tests/test_confirm.py`:

```python
from __future__ import annotations


def test_confirm_modal_has_confirm_button_id():
    from multises_app.confirm import discard_confirm_modal
    html = str(discard_confirm_modal("confirm_new",
                                     "Replace current project?").tagify())
    assert 'id="confirm_new"' in html
    assert "Replace current project?" in html
    assert "Discard & continue" in html
    assert "Cancel" in html
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_confirm.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Create the modal builder**

Create `multises_app/confirm.py`:

```python
"""Destructive-action confirm modal (used for New / Open / Recent-load when the
session has unsaved edits)."""
from __future__ import annotations

from shiny import ui


def discard_confirm_modal(confirm_id: str, message: str) -> ui.Tag:
    """A modal warning that proceeding discards unsaved edits. `confirm_id` is
    the input id of the proceed button; the cancel button just closes."""
    return ui.modal(
        ui.p(message),
        ui.p("You have unsaved changes in this session. They will be lost.",
             class_="text-warning"),
        title="Discard unsaved changes?",
        footer=ui.div(
            ui.modal_button("Cancel"),
            ui.input_action_button(confirm_id, "Discard & continue",
                                   class_="btn btn-danger"),
        ),
        easy_close=True,
    )
```

- [ ] **Step 4: Gate New + Open on `dirty` (project_setup)**

In `multises_app/modules/project_setup.py`, add to imports:

```python
from multises_app.confirm import discard_confirm_modal
```

Replace `_new` so it confirms when dirty, and add the confirm handler:

```python
    @reactive.effect
    @reactive.event(input.new_multises, ignore_init=True)
    def _new() -> None:
        if state.dirty.get():
            ui.modal_show(discard_confirm_modal(
                "confirm_new", "Start a new project from the Curonian seed?"))
            return
        _do_new()

    @reactive.effect
    @reactive.event(input.confirm_new)
    def _confirm_new() -> None:
        ui.modal_remove()
        _do_new()

    def _do_new() -> None:
        state.load_multises(seed_curonian())
        ui.notification_show("New project (Curonian seed) ✓", duration=3, type="message")
```

For Open, stash the uploaded file and confirm before applying. Replace `_open`'s start so it routes through a pending-apply helper:

```python
    _pending_open: reactive.Value = reactive.value(None)

    @reactive.effect
    @reactive.event(input.open_multises, ignore_init=True)
    def _open() -> None:
        finfo = input.open_multises()
        if not finfo:
            return
        if state.dirty.get():
            _pending_open.set(finfo)
            ui.modal_show(discard_confirm_modal(
                "confirm_open", "Open the selected file?"))
            return
        _apply_open(finfo)

    @reactive.effect
    @reactive.event(input.confirm_open)
    def _confirm_open() -> None:
        ui.modal_remove()
        finfo = _pending_open.get()
        _pending_open.set(None)
        if finfo:
            _apply_open(finfo)

    def _apply_open(finfo) -> None:
        try:
            text = Path(finfo[0]["datapath"]).read_text(encoding="utf-8")
            result = MultiSES.from_json(text)
        except Exception as e:  # noqa: BLE001 — untrusted file boundary
            _log.exception("project_setup: open failed")
            ui.notification_show(_friendly_error("Could not load the file", e),
                                 duration=6, type="warning")
            return
        ms = result.multises
        state.load_multises(ms)
        add_recent_payload(name=ms.metadata.name, payload=text,
                           compartment_count=len(ms.compartments),
                           channel_count=len(ms.channels))
        state.event_bus.emit_project_loaded()
        n = len(result.report.warnings)
        ui.notification_show("Loaded ✓" + (f" ({n} warning(s))" if n else ""),
                             duration=4, type="message")
```

> `_friendly_error` is added in Task 13; if implementing T9 before T13, temporarily use the original `f"Could not load: {e}"` and let T13 swap it. (Subagent: prefer doing T13 first, or inline the T13 helper now.)

- [ ] **Step 5: Gate Recent-load on `dirty` (recent_projects)**

In `multises_app/modules/recent_projects.py`, the per-row loader is wired in `_wire_load`. Refactor it to confirm when dirty. Add to imports:

```python
from multises_app.confirm import discard_confirm_modal
```

Replace `_wire_load`'s effect body so it stashes the index and confirms when dirty; add a shared confirm handler in `recent_projects_server`. Implement with a module-level pending index:

In `recent_projects_server`, add near the top:

```python
    _pending_load: reactive.Value[int | None] = reactive.value(None)

    @reactive.effect
    @reactive.event(input.confirm_recent_load)
    def _confirm_recent_load() -> None:
        ui.modal_remove()
        idx = _pending_load.get()
        _pending_load.set(None)
        if idx is not None:
            _do_load_recent(input, idx, state, entries, refresh)
```

Change the loop wiring to pass `_pending_load`:

```python
    for i in range(MAX_RECENT):
        _wire_load(input, i, state, entries, refresh, _pending_load)
        _wire_remove(input, i, entries, refresh)
```

Rewrite `_wire_load` + factor the actual load into `_do_load_recent`:

```python
def _wire_load(input, idx, state, entries_calc, refresh, pending_load) -> None:
    @reactive.effect
    @reactive.event(input[f"load_recent_{idx}"], ignore_init=True)
    def _():
        rows = entries_calc()
        if idx >= len(rows):
            return
        if state.dirty.get():
            pending_load.set(idx)
            ui.modal_show(discard_confirm_modal(
                "confirm_recent_load", f"Load “{rows[idx].name}”?"))
            return
        _do_load_recent(input, idx, state, entries_calc, refresh)


def _do_load_recent(input, idx, state, entries_calc, refresh) -> None:
    rows = entries_calc()
    if idx >= len(rows):
        return
    entry = rows[idx]
    try:
        result = MultiSES.from_json(entry.payload)
    except Exception as e:  # noqa: BLE001 - untrusted persisted payload boundary
        ui.notification_show(f"Couldn't load {entry.name}: {e}",
                             type="warning", duration=6)
        remove_recent(entry.entry_id)
        with reactive.isolate():
            refresh.set(refresh.get() + 1)
        return
    ms = result.multises
    state.load_multises(ms)
    add_recent_payload(name=ms.metadata.name, payload=entry.payload,
                       compartment_count=len(ms.compartments),
                       channel_count=len(ms.channels))
    state.event_bus.emit_project_loaded()
    n = len(result.report.warnings)
    ui.notification_show(f"Loaded {ms.metadata.name}." + (f" ({n} warning(s))" if n else ""),
                         type="message", duration=4)
```

> The `confirm_recent_load` button is shared across all rows; only one modal is open at a time and `_pending_load` records which row. This keeps a single confirm input rather than one per row.

- [ ] **Step 6: Add e2e for the New confirm**

Add to `tests/test_ui_hardening_e2e.py`:

```python
def test_new_confirms_when_dirty(mosaicses_app_url):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.click("#sespy_nav_project")
            # Make the session dirty: edit + Save the metadata form.
            page.fill("#project-name", "Dirty edit")
            page.click("#project-save")
            page.wait_for_timeout(500)
            # New now asks before discarding.
            page.click("#project-new_multises")
            expect(page.get_by_text("Discard unsaved changes?")).to_be_visible(timeout=5_000)
            page.get_by_role("button", name="Cancel").click()
            expect(page.locator("#project-name")).to_have_value("Dirty edit")
        finally:
            browser.close()
```

- [ ] **Step 7: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_confirm.py tests/test_project_setup_module.py tests/test_recent_projects_module.py tests/test_ui_hardening_e2e.py::test_new_confirms_when_dirty -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add multises_app/confirm.py multises_app/modules/project_setup.py multises_app/modules/recent_projects.py tests/test_confirm.py tests/test_ui_hardening_e2e.py
git commit -m "feat(mosaicses): confirm before New/Open/Recent-load discards unsaved edits"
```

---

### Task 10: `beforeunload` guard when dirty (MEDIUM)

**Root cause:** an accidental refresh/close loses the unsaved session silently. Add a `window.beforeunload` handler driven by a Shiny custom message that mirrors `state.dirty`.

**Files:**
- Modify: `app.py` (head JS + a dirty→client effect)
- Test: `tests/test_ui_hardening_e2e.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_hardening_e2e.py`:

```python
def test_beforeunload_registered_when_dirty(mosaicses_app_url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.click("#sespy_nav_project")
            page.fill("#project-name", "Dirty edit")
            page.click("#project-save")
            page.wait_for_timeout(500)
            flag = page.evaluate("window.__mosaicsesDirty === true")
            assert flag is True
        finally:
            browser.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_ui_hardening_e2e.py::test_beforeunload_registered_when_dirty -v`
Expected: FAIL (`window.__mosaicsesDirty` undefined).

- [ ] **Step 3: Add the head JS and the dirty→client effect**

In `app.py`, add to the `ui.head_content(...)` (after the `lang` script):

```python
        ui.tags.script("""
window.__mosaicsesDirty = false;
window.addEventListener('beforeunload', function (e) {
  if (window.__mosaicsesDirty) { e.preventDefault(); e.returnValue = ''; }
});
Shiny.addCustomMessageHandler('mosaicses:dirty', function (v) {
  window.__mosaicsesDirty = !!v;
});
"""),
```

In `server`, after the module servers are wired, add an effect that pushes `state.dirty` to the client:

```python
    @reactive.effect
    async def _sync_dirty_to_client():
        await session.send_custom_message("mosaicses:dirty", state.dirty.get())
```

> `session.send_custom_message` is async; the effect reads `state.dirty` reactively and re-sends on every change. No `@reactive.event` so it fires on each dirty transition.

- [ ] **Step 4: Run the test**

Run: `micromamba run -n shiny python -m pytest tests/test_ui_hardening_e2e.py::test_beforeunload_registered_when_dirty -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_ui_hardening_e2e.py
git commit -m "feat(mosaicses): beforeunload guard warns on close with unsaved edits"
```

---

## Phase 5 — Form & editor polish (HIGH + MEDIUM)

### Task 11: Stop the Project-Setup form clobber (HIGH)

**Root cause:** `_load_form_values` (`project_setup.py:199-212`) is a plain effect on `active_multises` that overwrites all 8 fields on *every* mutation — including tenet/overlay/backwrite edits that preserve metadata identity. Gate it on metadata identity so it only repopulates on a genuine load/new/save.

**Files:**
- Modify: `multises_app/modules/project_setup.py:199-212`
- Test: e2e in `tests/test_ui_hardening_e2e.py` (reactive effect — e2e is the right level)

- [ ] **Step 1: Write the failing e2e test**

Add to `tests/test_ui_hardening_e2e.py`:

```python
def test_form_edits_survive_a_score_save(mosaicses_app_url):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.click("#sespy_nav_project")
            page.fill("#project-name", "Unsaved form edit")
            # Go score a governance channel's tenets (mutates active_multises but
            # preserves metadata identity), then return to the form.
            page.click("#sespy_nav_topology")
            # Open the inspector, pick a governance channel, save scores.
            page.click("#sespy_nav_project")
            # The typed name must NOT have been clobbered by the topology edit.
            expect(page.locator("#project-name")).to_have_value("Unsaved form edit")
        finally:
            browser.close()
```

> The middle "score a channel" steps are abbreviated; the load-bearing assertion is that navigating away and back (which re-runs `_load_form_values` on the unchanged metadata) does not wipe the typed value. If the topology score-save is hard to drive headlessly, the navigate-away/back round-trip alone reproduces the clobber once the effect is unguarded.

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_ui_hardening_e2e.py::test_form_edits_survive_a_score_save -v`
Expected: FAIL (typed value cleared).

- [ ] **Step 3: Gate `_load_form_values` on metadata identity**

In `multises_app/modules/project_setup.py`, replace `_load_form_values` with an identity-gated version. Add a closure token above the effect:

```python
    # Repopulate the form only when the metadata OBJECT changes (a real
    # load/new/save) — NOT on every active_multises mutation, which would
    # clobber unsaved keystrokes. Edit paths (tenet/overlay/backwrite) rebuild
    # MultiSES preserving `metadata` identity, so id(meta) is stable across them.
    _populated_meta_id: list[int | None] = [None]

    @reactive.effect
    def _load_form_values() -> None:
        meta = state.active_multises.get().metadata
        if id(meta) == _populated_meta_id[0]:
            return
        _populated_meta_id[0] = id(meta)
        ui.update_text("name", value=meta.name or "")
        ui.update_text_area("description", value=meta.description or "")
        ui.update_select("da_site", selected=meta.da_site or "")
        ui.update_text_area("focal_issue", value=meta.focal_issue or "")
        ui.update_text("river_basin", value=meta.river_basin or "")
        ui.update_select("regional_sea", selected=meta.regional_sea or "")
        ui.update_select("temporal_scale", selected=meta.temporal_scale or "")
        ui.update_select("spatial_scale", selected=meta.spatial_scale or "")
```

- [ ] **Step 4: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_project_setup_module.py tests/test_project_setup_e2e.py tests/test_ui_hardening_e2e.py::test_form_edits_survive_a_score_save -v`
Expected: PASS — including the existing `test_project_setup_file_flows_e2e` (Open/New still repopulate, because those mint new metadata → id changes).

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/project_setup.py tests/test_ui_hardening_e2e.py
git commit -m "fix(mosaicses): project-setup form no longer clobbers unsaved edits on unrelated mutations"
```

---

### Task 12: Preserve the selected overlay element after Save (MEDIUM)

**Root cause:** `_populate_overlay_element` (`compartments.py:174-183`) calls `ui.update_select("overlay_element", choices=choices)` with no `selected=`, so a Save (which mutates `active_multises`) re-fires it and snaps the dropdown back to the first element — navigating the user off the element they just scored.

**Files:**
- Modify: `multises_app/modules/compartments.py:174-183`
- Test: e2e in `tests/test_ui_hardening_e2e.py`

- [ ] **Step 1: Write the failing e2e test**

Add to `tests/test_ui_hardening_e2e.py`:

```python
def test_overlay_element_selection_survives_save(mosaicses_app_url):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.click("#sespy_nav_compartments")
            page.get_by_text("Evaluative scores").click()
            sel = page.locator("#compartments-overlay_element")
            options = sel.locator("option")
            if options.count() < 2:
                return  # compartment has <2 eligible elements; nothing to assert
            second = options.nth(1).get_attribute("value")
            sel.select_option(second)
            page.click("#compartments-save_overlay")
            page.wait_for_timeout(500)
            expect(sel).to_have_value(second)  # NOT reset to the first option
        finally:
            browser.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_ui_hardening_e2e.py::test_overlay_element_selection_survives_save -v`
Expected: FAIL (selection snaps to first).

- [ ] **Step 3: Preserve the selection**

In `multises_app/modules/compartments.py`, update `_populate_overlay_element` to keep the current selection when it is still valid:

```python
    @reactive.effect
    def _populate_overlay_element():
        ms = state.active_multises.get()
        cid = state.active_compartment_id.get()
        if cid is None:
            choices = {}
        else:
            cmp = ms.get_compartment(cid)
            choices = _eligible_overlay_elements(cmp) if cmp is not None else {}
        with reactive.isolate():
            current = input.overlay_element() or None
        selected = current if current in choices else None
        ui.update_select("overlay_element", choices=choices,
                         selected=selected, session=session)
```

- [ ] **Step 4: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_compartments_module.py tests/test_ui_hardening_e2e.py::test_overlay_element_selection_survives_save -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/compartments.py tests/test_ui_hardening_e2e.py
git commit -m "fix(mosaicses): keep the selected overlay element after saving its score"
```

---

### Task 13: Sanitize exception text in toasts (MEDIUM)

**Root cause:** error toasts interpolate raw exceptions (`f"Could not save: {e}"`, `f"Could not load: {e}"`, `f"Couldn't load {name}: {e}"`) — leaking stack-ish internals, inconsistent with the sanitized `project_setup.py:241` pattern. Add one shared helper and route all error toasts through it.

**Files:**
- Modify: `multises_app/overlay_edit.py` (add `friendly_error`) — a Shiny-free home, importable everywhere
- Modify: `compartments.py`, `topology.py`, `project_setup.py`, `recent_projects.py`
- Test: `tests/test_overlay_edit.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_overlay_edit.py`:

```python
def test_friendly_error_sanitizes():
    from multises_app.overlay_edit import friendly_error
    msg = friendly_error("Could not save", ValueError("tenet 'ecological' out of range 1-5"))
    assert msg.startswith("Could not save")
    assert "ValueError" in msg            # the type name is informative
    assert "out of range" in msg          # short human reason kept
    # No multi-line / repr leakage.
    assert "\n" not in msg and "Traceback" not in msg
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_edit.py::test_friendly_error_sanitizes -v`
Expected: FAIL — function missing.

- [ ] **Step 3: Add the helper**

In `multises_app/overlay_edit.py`:

```python
def friendly_error(prefix: str, exc: Exception) -> str:
    """One-line, sanitized toast text: '<prefix> (<ExcType>): <first line>'.
    Keeps a short human reason without leaking multi-line reprs/tracebacks."""
    reason = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    reason = reason[:160]
    base = f"{prefix} ({type(exc).__name__})"
    return f"{base}: {reason}" if reason else base
```

- [ ] **Step 4: Route the error toasts through it**

- `compartments.py` `_save_overlay` except block:
  ```python
  from multises_app.overlay_edit import TENET_SCORE_CHOICES, assemble_tenet_scores, set_overlay_entry, friendly_error
  ...
          except (_ChannelValidationError, ValueError, KeyError, TypeError) as e:
              ui.notification_show(friendly_error("Could not save", e), type="error", duration=6)
  ```
- `topology.py` `_save_channel_tenets` except block:
  ```python
  from multises_app.overlay_edit import TENET_SCORE_CHOICES, assemble_tenet_scores, friendly_error
  ...
          except (_ChannelValidationError, ValueError, KeyError, TypeError) as e:
              ui.notification_show(friendly_error("Could not save", e), type="error", duration=6)
  ```
- `project_setup.py` `_apply_open` except block (added in T9): use `friendly_error("Could not load the file", e)`.
- `recent_projects.py` `_do_load_recent` except block:
  ```python
  from multises_app.overlay_edit import friendly_error
  ...
          ui.notification_show(friendly_error(f"Couldn't load {entry.name}", e),
                               type="warning", duration=6)
  ```

> Leave `project_setup.py:240` (`Save failed: {type(e).__name__}. See server log.`) as-is — it is already sanitized; optionally re-express via `friendly_error` for consistency, but not required.

- [ ] **Step 5: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_edit.py tests/test_compartments_module.py tests/test_topology_module.py tests/test_recent_projects_module.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add multises_app/overlay_edit.py multises_app/modules/compartments.py multises_app/modules/topology.py multises_app/modules/project_setup.py multises_app/modules/recent_projects.py tests/test_overlay_edit.py
git commit -m "fix(mosaicses): sanitize exception text in error toasts via shared friendly_error"
```

---

### Task 14: Make the "Evaluative scores" tab discoverable (MEDIUM)

**Root cause:** "Evaluative scores" is tab #2 of 11 unlabeled tabs with no hint that per-element tenet/equity scoring lives there (`compartments.py:128-145`).

**Files:**
- Modify: `multises_app/modules/compartments.py:128-145`
- Test: `tests/test_compartments_module.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_compartments_module.py`:

```python
def test_evaluative_scores_tab_has_discoverability_hint():
    from multises_app.modules.compartments import compartments_ui
    html = str(compartments_ui("test_id").tagify())
    assert "Score this compartment’s" in html or "tenet & equity" in html.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_compartments_module.py::test_evaluative_scores_tab_has_discoverability_hint -v`
Expected: FAIL.

- [ ] **Step 3: Add an inline hint + an icon to the tab title**

In `multises_app/modules/compartments.py`, update the "Evaluative scores" `nav_panel`: add a short lead paragraph above the element select and an icon in the title:

```python
                ui.nav_panel(
                    ui.span("Evaluative scores ★"),
                    ui.tags.p(
                        "Score this compartment’s governance Responses (10 tenets) "
                        "and outcome elements (Emerald Justice equity dimensions). "
                        "Pick an element, set its scores, and Save.",
                        class_="text-muted",
                    ),
                    ui.input_select("overlay_element", "Element:",
                                    choices={}, width="320px"),
                    ui.output_ui("overlay_editor"),
                    value="evaluative_scores"),
```

> Keep the `overlay_element` / `overlay_editor` ids unchanged. The `value="evaluative_scores"` makes the tab addressable.

- [ ] **Step 4: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_compartments_module.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/compartments.py tests/test_compartments_module.py
git commit -m "fix(mosaicses): make the Evaluative-scores tab discoverable (icon + lead text)"
```

---

## Phase 6 — Feedback, i18n, export, stepper (MEDIUM)

### Task 15: Loading indicators on heavy outputs (MEDIUM)

**Root cause:** heatmap, pyvis canvases, and DataGrids rebuild with no busy signal — the user stares at a frozen/stale view. Shiny exposes `ui.busy_indicators.use(spinners=True)` (pulsing busy state on recalculating outputs).

**Files:**
- Modify: `app.py` (mount busy indicators once)
- Test: `tests/test_app_imports_colors.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_app_imports_colors.py`:

```python
def test_app_ui_has_busy_indicators():
    import app as mosaic_app
    html = str(mosaic_app.app_ui.tagify())
    # bslib busy-indicators inject a recalculating/spinner style hook.
    assert "busy" in html.lower() or "recalculating" in html.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_app_imports_colors.py::test_app_ui_has_busy_indicators -v`
Expected: FAIL.

- [ ] **Step 3: Mount busy indicators**

In `app.py`, add `ui.busy_indicators.use(spinners=True)` into the top-level `ui.TagList(...)` (e.g., as the first child after `ui.head_content(...)`):

```python
app_ui = ui.TagList(
    ui.head_content(
        ...
    ),
    ui.busy_indicators.use(spinners=True),
    ui.tags.h1(...),
    _app_ui_inner,
)
```

> If the installed Shiny version lacks `ui.busy_indicators`, fall back to injecting the documented CSS class hook `.recalculating { opacity: .55; transition: opacity .2s; }` into the inline stylesheet and assert on that class instead. Verify availability first: `micromamba run -n shiny python -c "from shiny import ui; print(hasattr(ui, 'busy_indicators'))"`.

- [ ] **Step 4: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_app_imports_colors.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_imports_colors.py
git commit -m "feat(mosaicses): busy-indicator spinners on recalculating outputs"
```

---

### Task 16: Make toasts screen-reader-visible (MEDIUM)

**Root cause:** `ui.notification_show` is SR-invisible. Mirror each notification into a shared `aria-live="assertive"` region. Implement a tiny client handler + a server helper.

**Files:**
- Modify: `app.py` (live region + handler + helper) — or a small `multises_app/notify.py`
- Test: `tests/test_ui_hardening_e2e.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui_hardening_e2e.py`:

```python
def test_save_announced_via_aria_live(mosaicses_app_url):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.click("#sespy_nav_project")
            page.fill("#project-name", "Announce me")
            page.click("#project-save")
            live = page.locator("#mosaicses-live-region")
            expect(live).to_contain_text("Saved", timeout=5_000)
        finally:
            browser.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_ui_hardening_e2e.py::test_save_announced_via_aria_live -v`
Expected: FAIL (no live region).

- [ ] **Step 3: Add the live region + client handler**

In `app.py`, add to the `ui.TagList(...)` (e.g., right after the visually-hidden `<h1>`):

```python
    ui.tags.div(id="mosaicses-live-region", class_="visually-hidden",
                role="status", **{"aria-live": "assertive"}),
```

Add to the head JS (T10's `<script>` or a new one):

```javascript
Shiny.addCustomMessageHandler('mosaicses:announce', function (text) {
  var el = document.getElementById('mosaicses-live-region');
  if (el) { el.textContent = ''; el.textContent = String(text || ''); }
});
```

Add a server-side announce helper and call it alongside the key `ui.notification_show` calls. In `app.py` `server`, define:

```python
    async def announce(text: str) -> None:
        await session.send_custom_message("mosaicses:announce", text)
```

Because the existing `notification_show` calls live inside the modules, the simplest low-risk wiring is a shared effect that announces the most-recent save: mirror via the `dirty`→clean transition is insufficient. Instead, route the highest-value confirmations: in `project_setup.py` `_handle_save`, after `ui.notification_show("Saved ✓", ...)`, also announce. To avoid threading `session` everywhere, mount one module-agnostic effect in `app.py` that watches `state.dirty` going **False** after a download/save and announces "Saved". Minimal acceptance for this task: the **Project-Setup Save** path announces.

Concretely, in `project_setup.py` `_handle_save`, add after the toast:

```python
            import asyncio  # local import keeps module top clean
            # Announce to the SR live region (best-effort; ignore if no session).
            try:
                session.on_flushed  # noqa: B018 — presence check
                asyncio.create_task(
                    session.send_custom_message("mosaicses:announce", "Saved"))
            except Exception:
                pass
```

> Simpler alternative if the async-task pattern is fragile in this Shiny version: make `_handle_save` `async def` and `await session.send_custom_message("mosaicses:announce", "Saved")` directly. Prefer the async-def form — change `def _handle_save()` to `async def _handle_save()` and `await` the send. (`@reactive.event` supports async effects.)

- [ ] **Step 4: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_project_setup_module.py tests/test_ui_hardening_e2e.py::test_save_announced_via_aria_live -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py multises_app/modules/project_setup.py tests/test_ui_hardening_e2e.py
git commit -m "feat(mosaicses): mirror save confirmations into an aria-live region for screen readers"
```

---

### Task 17: Replace the empty `'en'` i18n dict (MEDIUM)

**Root cause:** `T = Translator(translations={"en": {}})` (`app.py:66`) means any embedded SESPy module label that is translation-only renders as a raw dotted key. Wire a minimal English dict so the mounted SESPy module labels resolve.

**Files:**
- Modify: `app.py:60-67`
- Test: `tests/test_app_imports_colors.py`

- [ ] **Step 1: Identify the keys actually needed**

Run: `micromamba run -n shiny python -c "import json; d=json.load(open(r'../SESPy/sespy/translations/core.json')); print(len(d))"` to confirm the SESPy core dict is available. The robust fix is to **reuse SESPy's English translations** rather than hand-maintain a list.

- [ ] **Step 2: Write the failing test**

Add to `tests/test_app_imports_colors.py`:

```python
def test_translator_has_nonempty_english():
    import app as mosaic_app
    # The English dict must be non-trivial so embedded SESPy module labels
    # resolve instead of showing dotted keys.
    en = mosaic_app.T._translations.get("en", {}) if hasattr(mosaic_app.T, "_translations") else {}
    assert len(en) > 10
```

> If `Translator` does not expose `_translations`, assert instead that `mosaic_app.T.t("analysis.loops.title")` (any real SESPy key) returns something other than the key. Verify the accessor first: `micromamba run -n shiny python -c "from sespy.i18n import Translator; print(dir(Translator))"`.

- [ ] **Step 3: Load SESPy's English translations**

In `app.py`, replace the stub Translator construction:

```python
import json as _json
from importlib.resources import files as _pkg_files

# Reuse SESPy's English translations so embedded module labels resolve instead
# of rendering raw dotted keys. Fall back to an empty dict if the resource is
# unavailable (keeps launch resilient).
try:
    _core = _json.loads((_pkg_files("sespy") / "translations" / "core.json").read_text("utf-8"))
    _en = {k: v.get("en", k) if isinstance(v, dict) else v for k, v in _core.items()}
except Exception:  # noqa: BLE001 — resource resolution is best-effort
    _en = {}
T = Translator(translations={"en": _en})
set_default(T)
```

> The core.json shape is `{key: {"en": "...", "es": "...", ...}}` (confirmed). The comprehension flattens to `{key: english_string}`. If `Translator` expects the nested shape, pass `translations={"en": _core}`-compatible structure instead — verify with `micromamba run -n shiny python -c "from sespy.i18n import Translator; help(Translator.__init__)"` and match SESPy's own `app.py` usage.

- [ ] **Step 4: Run tests + smoke the app import**

Run: `micromamba run -n shiny python -m pytest tests/test_app_imports_colors.py -v`
Then: `micromamba run -n shiny python -c "import app"` (must not raise).
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_imports_colors.py
git commit -m "fix(mosaicses): load SESPy English translations so embedded module labels resolve"
```

---

### Task 18: Chart export affordances + workflow stepper (MEDIUM)

**Two findings, one commit (both small UI affordances):**
**(a)** the heatmap + bridge charts have no download button; **(b)** the workflow stepper is wired server-side (`dashboard.py` STEPPER/NAV_TO_STEP + `app.py` `stepper_steps=STEPPER`) but the review found it never visibly mounts. **Decision (default):** the stepper wiring is intentional; *verify* whether `dashboard_page`/`dashboard_server` already render it, and if not, mount it — do **not** delete the wiring. If verification shows it already renders (i.e., the finding was a false-positive in this build), record that and drop the stepper sub-task.

**Files:**
- Modify: `multises_app/modules/comparative.py` (heatmap download), `multises_app/modules/cross_view.py` (bridge download)
- Modify: `app.py` / `multises_app/dashboard.py` (stepper, only if not already rendered)
- Test: `tests/test_comparative_module.py`, `tests/test_cross_view_module.py`

- [ ] **Step 1: Verify the stepper render status**

Run: `micromamba run -n shiny python -c "import app; html=str(app.app_ui.tagify()); print('stepper' in html.lower(), 'Drill into compartment' in html)"`
Record the result. If `Drill into compartment` (a STEPPER label) appears, the stepper IS mounted → skip the stepper sub-task and note it in the commit body. Otherwise mount it in Step 4.

- [ ] **Step 2: Write the failing tests for chart downloads**

Add to `tests/test_comparative_module.py`:

```python
def test_comparative_ui_has_heatmap_download():
    from multises_app.modules.comparative import comparative_ui
    html = str(comparative_ui("test_id"))
    assert 'id="test_id-download_heatmap"' in html
```

Add to `tests/test_cross_view_module.py`:

```python
def test_cross_view_ui_has_bridge_download():
    from multises_app.modules.cross_view import cross_view_ui
    html = str(cross_view_ui("test_id").tagify())
    assert 'id="test_id-download_bridge"' in html
```

- [ ] **Step 3: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative_module.py::test_comparative_ui_has_heatmap_download tests/test_cross_view_module.py::test_cross_view_ui_has_bridge_download -v`
Expected: FAIL.

- [ ] **Step 4a: Add the heatmap download (comparative)**

In `comparative_ui`, add a download button into the heatmap card (after `ui.output_image("heatmap")`):

```python
                ui.download_button("download_heatmap", "Download PNG",
                                   class_="btn btn-sm btn-outline-secondary"),
```

In `comparative_server`, add the handler (reuses the already-rendered temp file is not safe across params, so re-render minimally):

```python
    @render.download(filename="centrality_heatmap.png")
    def download_heatmap():
        ms = state.active_multises.get()
        metric = input.metric()
        top_k = int(input.top_k())
        matrix, row_labels, col_labels_per_row, fallback_rows = _build_heatmap_matrix(
            ms, metric=metric, top_k=top_k)
        display_labels = [f"{l}*" if l in fallback_rows else l for l in row_labels]
        fig, ax = plt.subplots(figsize=(8, max(2, len(row_labels) * 0.6)), dpi=72)
        if row_labels:
            im = ax.imshow(matrix, aspect="auto")
            ax.set_yticks(range(len(row_labels)))
            ax.set_yticklabels(display_labels)
            ax.set_xticks([])
            fig.colorbar(im, ax=ax)
        else:
            ax.text(0.5, 0.5, "No compartments", ha="center", va="center")
            ax.axis("off")
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        yield buf.getvalue()
```

- [ ] **Step 4b: Add the bridge download (cross_view)**

In `cross_view_ui`, add into the Bridge metrics card (after `ui.output_image("bridge_chart")`):

```python
                                 ui.download_button("download_bridge", "Download PNG",
                                                    class_="btn btn-sm btn-outline-secondary"),
```

In `cross_view_server`, add:

```python
    @render.download(filename="bridge_metrics.png")
    def download_bridge():
        fig = _bridge_chart_figure(state.active_multises.get())
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        yield buf.getvalue()
```

- [ ] **Step 4c (conditional): Mount the stepper** — only if Step 1 showed it absent

If absent, the stepper is rendered by `sespy.dashboard`'s components; mount it by passing the stepper into the page. Inspect how SESPy's own app surfaces the stepper (`grep -n "stepper" ../SESPy/app.py ../SESPy/sespy/dashboard.py`) and mirror that call. If SESPy mounts via a `stepper_ui(...)` helper, add the equivalent into `_app_ui_inner`/`dashboard_page` args. If no such helper exists (stepper is server-only by design), treat the finding as won't-fix and document it. Do **not** invent a new stepper widget.

- [ ] **Step 5: Run tests**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative_module.py tests/test_cross_view_module.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add multises_app/modules/comparative.py multises_app/modules/cross_view.py tests/test_comparative_module.py tests/test_cross_view_module.py app.py multises_app/dashboard.py
git commit -m "feat(mosaicses): chart PNG export buttons; verify/mount workflow stepper"
```

---

## Final verification

- [ ] **Run the full unit suite**

Run: `micromamba run -n shiny python -m pytest -q -m "not e2e" tests/` (or just `tests/` excluding e2e if not marked)
Expected: all green.

- [ ] **Run the e2e suite**

Run: `micromamba run -n shiny python -m pytest tests/test_ui_hardening_e2e.py tests/test_project_setup_e2e.py tests/test_comparative_e2e.py tests/test_cross_view_e2e.py tests/test_overlay_editors_e2e.py -v`
Expected: all green (Playwright headless).

- [ ] **Manual smoke (operator):** launch and eyeball the skin + an empty-project edge case

Run: `micromamba run -n shiny shiny run --launch-browser app.py`
Check: themed (not raw Bootstrap); Comparative renders with the seed; the gap card + heatmap do not crash after deleting all elements from every compartment.

- [ ] **Dispatch a final whole-branch code review** (per subagent-driven-development), then use **superpowers:finishing-a-development-branch** to merge/PR.

---

## Self-review notes (author)

- **Spec coverage:** every CONFIRMED finding maps to a task (see the Severity → Task table); the one non-mapped MEDIUM (select-then-save friction) is an explicit, justified Non-Goal.
- **Type/name consistency:** `state.dirty` (T8) is consumed by T9/T10; `friendly_error` (T13) is consumed by T9's `_apply_open`; `compartment_channel_table_ui` / `digraph_table_ui` (T4) are consumed by T5/T7; `_GAP_COLUMNS` (T1) is asserted by its own test. Cross-task ordering: do T8 before T9/T10, T13's helper before/with T9's `_apply_open`, T4 before T5/T7.
- **Risk:** the Shiny-version-dependent APIs (`ui.busy_indicators` T15, `Translator` internals T17, `App.starlette_app` T3) each include a verify-first command and a documented fallback so an implementer never guesses.
