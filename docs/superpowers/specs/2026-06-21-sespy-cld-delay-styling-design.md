# SESPy Graph-View Delay Styling (QSEM time-delay, "B2") — Design

Date: 2026-06-21
Status: **Draft** (spec review gate, rev. 2 — widened after in-loop review)

**Context.** Improvement **B** (delay-aware Loop Analysis, merged `2e83bb0`)
made `Connection.delay` a first-class 3-level field and styled delayed edges
(dashed) in the **Loop Analysis** loop network. **B2** applies the same cue to the
**other node-link graph views** so the delay signal is consistent everywhere the
graph is drawn — not just in the loop drill-down.

**Scope widened (rev. 2):** the in-loop spec review found that the *same* graph
is rendered by **five** edge-build sites — CLD, Leverage, Metrics, Simplify,
Intervention — all using the identical `for c in isa.connections: add_edge(...)`
idiom. Dashing only the CLD would make a delayed edge appear dashed in CLD/Loop
but **solid** in Leverage/Metrics — the exact shared-treatment drift that caused
a prior regression (`.comparative-card`). So B2 introduces **one shared helper**
applied at all five sites: a single definition of the delay cue, drift-proof.

## 1. Goal & scope

### 1.1 In scope
- A shared pure helper `delay_edge_kwargs(c)` in `sespy/network.py` returning the
  vis.js edge kwargs that encode delay: `{"title": f"{c.polarity} · {delay}",
  "dashes": delay != "immediate"}` (`delay = normalize_delay(c.delay)`).
- Spread `**delay_edge_kwargs(c)` into the `add_edge(...)` call at all **five**
  full-graph builders: `_build_pyvis_network` (cld_visualization), and
  `_build_leverage_network`, `_build_metrics_network`, `_build_simplified_network`,
  `_build_intervention_network`.
- A one-line **"dashed = delayed" caption** under the CLD canvas (the primary
  diagram), i18n key `cld.delay_legend`, teaching the cue once.
- Unit tests (helper + every builder applies it) + a new CLD e2e.

### 1.2 Out of scope
- **No data-model / schema change.** Reads existing `Connection.delay`. No
  `PROJECT_SCHEMA_VERSION` bump.
- **The Loop Analysis loop network is unchanged** — B already dashed it. Its edge
  construction iterates *cycle* edges by `(src,tgt)` lookup (not `Connection`
  objects), so it keeps its existing inline `dashes`/`title`; both use the same
  `normalize_delay` and `f"{polarity} · {delay}"` format. (Not refactored to the
  helper because the signature doesn't fit; the shared *predicate/format* is the
  thing that matters and is identical.)
- **Legend caption only on the CLD**, not repeated under every view — the cue is
  visually identical everywhere (shared helper), and the per-edge **tooltip**
  (`· short`/`· long`) gives confirmation in every view; one caption on the
  primary diagram teaches it. A per-view legend is a deferred fast-follow.
- **One new i18n key** (`cld.delay_legend`) — the *edge tooltip* uses the raw
  delay level (no key), matching B's loop network.
- No change to edge colour, width, opacity, layout, or node sizing in any view.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Shared helper | `delay_edge_kwargs(c) -> dict` in `network.py` | One definition of the delay cue, spread into all 5 builders — impossible to drift; any future builder just spreads it. Reuses B's `normalize_delay`. |
| Cue channel | vis.js `dashes` (line style) via the `add_edge(..., **kwargs)` **keyword path** (NOT `EdgeOptions`/`options=`) | Orthogonal to the `width` (strength, in Simplify) and `color.opacity` (ablation, in Intervention) cues those views overload — composes without conflict. Keyword path propagates `dashes` to the vis.js edge so `e.dashes` is readable (proven by B's shipped loop e2e). |
| Tooltip | `title=f"{c.polarity} · {delay}"` | Same format as B's loop network. |
| Legend | one CLD-canvas caption (`cld.delay_legend`, i18n) | A dashed edge with no key is opaque; one caption on the primary view teaches the cue; tooltip confirms per-edge elsewhere. |

## 2. No data-model change
`data_structure.py` untouched. The helper and builders read the existing
`Connection.delay`/`.polarity`. No schema bump.

## 3. Implementation

### 3.1 Helper (`sespy/network.py`, append)
```python
def delay_edge_kwargs(c) -> dict:
    """vis.js edge kwargs encoding a connection's delay as a dashed line + a
    delay tooltip. Spread into add_edge(...) at every full-graph edge builder
    (CLD, Leverage, Metrics, Simplify, Intervention) so the delay cue is one
    definition, identical across views. `dashes` is an orthogonal channel — it
    composes with the width/opacity cues some of those views overload."""
    from .constants import normalize_delay
    delay = normalize_delay(c.delay)
    return {"title": f"{c.polarity} · {delay}", "dashes": delay != "immediate"}
```

### 3.2 Apply at the five builders
At each builder's `net.add_edge(c.source, c.target, label=c.polarity, color=…,
arrows="to", width=…)` call, add `**net_analysis.delay_edge_kwargs(c)` as the
last argument (none of the five currently set `title`/`dashes`, so no conflict):
- `cld_visualization.py:230` (`_build_pyvis_network`) — width=2
- `analysis_leverage.py:68` (`_build_leverage_network`) — width=1.5
- `analysis_metrics.py:98` (`_build_metrics_network`) — width=1.5
- `analysis_simplify.py:60` (`_build_simplified_network`) — width encodes strength
- `analysis_intervention.py:104` (`_build_intervention_network`) — color is a dict with opacity

Each module already imports `from .. import network as net_analysis` *except*
`cld_visualization.py` — add that import there (or `from ..network import
delay_edge_kwargs`).

### 3.3 CLD legend caption
Under the CLD `output_pyvis_network(...)` in `cld_viz_ui`, add
`ui.tags.small(t("cld.delay_legend"), class_="text-muted")`. New i18n key
`cld.delay_legend` (English "Dashed edges = delayed links") in all 9 languages.

## 4. Edge cases & backward compatibility
- **No delayed edges** (most projects) → every edge `dashes=False`; visually
  identical to today across all views. Backward-compatible.
- **`normalize_delay`** (from B) handles empty/None/free-text/sentinels, so
  malformed delay can't break any builder.
- **Topology unchanged** — `dashes`/`title` are presentation-only; node/edge
  counts, colours, widths, opacity, and layout are unaffected, so existing e2e
  that assert `cld-network`/other network node-or-edge *counts* still pass.
- **`title` override** — none of the five builders currently set `title`, so the
  helper's title introduces no conflict.

## 5. Testing
1. **Unit — helper (`tests/test_network.py`, extend; pure):** `delay_edge_kwargs`
   on `Connection(polarity="+", delay="short")` → `{"dashes": True, "title":
   "+ · short"}`; `delay="immediate"` → `{"dashes": False, "title": "+ ·
   immediate"}`; a `polarity="-"` case; assert `dashes` with `is True`/`is False`
   (identity, not truthiness).
2. **Unit — every builder applies it (`tests/test_cld.py`, new; pure):** build a
   2-edge fixture (one `delay="short"`, one `delay="immediate"`); call each of the
   five builders with minimal valid args; for each, `nodes, edges, *_ =
   net.get_network_data()`, key `by = {(e["from"], e["to"]): e["dashes"] for e in
   edges}`, and assert the delayed edge is `True` and the immediate edge is
   `False`. (Pins that NO builder forgot the spread — the drift guard.)
3. **Sample guard (`tests/test_network.py`):** assert the sample has ≥1 delayed
   connection (`sum(normalize_delay(c.delay) != "immediate" for c in
   isa.connections) >= 1`) — fast-fails if the seed is ever removed, so the e2e
   red would be unambiguous.
4. **e2e (`tests/test_cld_e2e.py`, new, standalone asyncio Playwright):** on the
   default CLD tab (no element-type filter → all 17 nodes / 20 edges, per the
   existing `test_data_entry_e2e.py` baseline), **poll** the network like
   `tests/test_loops_e2e.py` does — predicate `s && s.edges` with a bounded retry
   (16 × 500 ms) before reading — then `dashes = s.edges.get().map(e => e.dashes
   === true)`; assert `s.edges.length === 20` (distinguishes an edge-filter
   regression from a styling one) **and** `some(d => d === true)` **and**
   `some(d => d === false)`. Full gate via `python tests/run_e2e.py` (never
   `-k "not e2e"` / `pytest` on the e2e scripts).

## 6. Build order (for the plan)
1. `delay_edge_kwargs` helper in `network.py` + unit tests (TDD).
2. `cld.delay_legend` i18n key (9 languages); `pytest tests/test_i18n.py` green.
3. Spread the helper into all five builders + the CLD legend caption; the
   "every builder applies it" unit test (`tests/test_cld.py`) + sample guard.
4. `tests/test_cld_e2e.py` + full e2e gate → merge → push.
