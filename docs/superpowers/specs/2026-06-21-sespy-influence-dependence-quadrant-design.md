# SESPy Influence × Dependence Quadrant (QSEM Phase-1 parity) — Design

Date: 2026-06-21
Status: **Draft** (spec review gate)

**Context.** A comparison of SESPy against **QSEM** (Qualitative Systems
Exploration Model; Hulme et al., 2026, *System Dynamics Review*) found that
SESPy's structural analysis is strong on computed graph metrics (centrality,
composite leverage, loops, simulation) but lacks QSEM's **Phase 1 — System
Factor Classification**: the influence/dependence ("Vester") map that separates
*how much a factor drives* from *how much it is driven*. SESPy's leverage score
(`z(betweenness)+z(eigenvector)+z(pagerank)`, `network.py:162`) collapses this
into one dimension. This feature restores the 2-D split — computed
**automatically from graph structure**, the cheapest QSEM-parity win.

QSEM elicits impact/control/time-delay scores from workshop participants. SESPy
cannot match that elicitation cheaply, but it *can* reproduce the recognizable
**output artifact** — the four-quadrant factor map — for free from the signed,
weighted diagram it already stores. That is the whole of this feature.

## 1. Goal & scope

### 1.1 In scope
- One new pure function `influence_dependence(isa)` in `sespy/network.py`,
  sitting beside `leverage_scores`. Weighted, sign-agnostic, mean-split,
  unit-tested with plain dicts (no Shiny).
- One new standalone module `sespy/modules/analysis_quadrant.py` mirroring the
  shape of `analysis_leverage.py`: a `@module.ui` card (sidebar + main) and a
  `@module.server` reading `project_data`, recomputing on `event_bus.isa_change`.
- A matplotlib scatter (`@render.plot`) with mean cross-hairs, points coloured
  by DAPSIWRM type, four quadrant captions; plus a classification
  `@render.data_frame` table.
- Full `app.py` wiring (four edits, see §4): a `NavItem` in `NAV`, a `NAV_TO_STEP`
  entry, a `ui.nav_panel`, and the server call.
- New i18n keys in `sespy/translations/core.json` (the 11 `quadrant.*`/`card.quadrant`
  keys **plus `nav.quadrant`**), each in all 9 catalog languages, mirroring the
  `leverage.*` / `nav.leverage` coverage.
- Unit + e2e tests (no separate "module-smoke" layer — see §6).

### 1.2 Out of scope
- **No data-model / schema change.** Reads only existing
  `Connection.source/target/strength/confidence`. No `PROJECT_SCHEMA_VERSION`
  bump. `Connection.polarity` is **not** consumed by `influence_dependence` —
  the axes are magnitude-only (sign-agnostic); polarity stays the domain of the
  CLD/loop views.
- **Time-delay surfacing (the dormant `Connection.delay` field)** — a separate
  future chunk. Independent data source, and `delay` is currently only writable
  via Excel import, so it drags in a data-entry UI change. Deferred.
- **Configurable split threshold / median toggle / top-N control.** Mean split
  is a single fixed rule (see §3). A median toggle is a documented future option
  if real MarineSABRES data proves hub-skewed (§5 caveat), not built
  speculatively.
- **Click-to-inspect a plotted point.** `@render.plot` is a static image in this
  repo; interactive selection is not worth the complexity (same call as SH2).
- No change to `analysis_leverage.py` or any other existing module.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Axis weighting | **Weighted** by the existing `_edge_weight(c)` = `strength_rank × confidence` (`network.py:216`) | One edge-weight definition across the app (already used by `simplify_top_n_edges`). Binary degree would merely duplicate the Metrics module's in/out-degree. |
| Sign handling | **Sign-agnostic** (magnitude only; `+` and `-` both contribute positive weight) | Vester influence/dependence measures *how much* a factor drives/is driven, not the direction. A factor that strongly suppresses three others is highly influential; cancelling `-` edges would erase that. **Acknowledged cost:** magnitude-only axes collapse reinforcing vs. opposing influence — a node driving 3 factors up and 3 down looks identical to one driving 6 up. Net polarity is *not* represented here; read it from the signed diagram / loop analysis. The `about` blurb states this. |
| Parallel/duplicate edges | **Deduplicate** — sum over a `{(source,target): weight}` map (last-wins), not raw `isa.connections` | Every other metric routes through `to_digraph` (`network.py:15-21`), which collapses parallel `(src,tgt)` edges to one. JSON and Excel import accept duplicate pairs (manual entry blocks them at `isa_data_entry.py:240`); summing raw connections would double-count and shift the mean cross-hairs, diverging from every other metric. Dedup keeps the quadrant consistent with the graph the rest of the app analyses. |
| Self-loops (`source == target`) | **Skip** — contribute to neither axis | A self-loop would inflate *both* a node's influence and its dependence from one reflexive edge. Vester active/passive sums are defined over edges to/from *other* factors. Mirrors the AI path, which already drops self-loops (`claude_backend.py:422-423`). |
| Influence (activity) | Σ `_edge_weight` over a node's **outgoing** edges | Standard Vester active sum. |
| Dependence (passivity) | Σ `_edge_weight` over a node's **incoming** edges | Standard Vester passive sum. |
| Split rule | Cross-hairs at the **mean** of each axis, fixed (no slider) | Canonical Vester convention; preserves absolute meaning ("above-average influence"). Median would force a ~25/25/25/25 split and *manufacture* drivers where none stand out — a trap for a leverage-finding tool. |
| Tie handling | `≥ mean` counts as the **high** side (deterministic) | No node is ever left unclassified; a node exactly at the mean lands in a defined quadrant. |
| Rendering | matplotlib via `@render.plot` | SESPy's established plot convention (metrics/boolean/simulation/bot/leverage). No plotly/pyvis for X-Y space. |
| Point colour | by **DAPSIWRM type** via `ELEMENT_COLORS` | Lets users cross-reference framework semantics against structure ("my Welfare element is Critical"). Free — `ELEMENT_COLORS` already exists. |
| Placement | **Standalone flat nav panel**, not a tab in Leverage | The quadrant's whole point is the 2-D split the 1-D leverage score collapses; folding it in invites "more of the same ranking". Independent testability matches the 16-module layout. |
| Pure-helper location | `sespy/network.py` beside `leverage_scores` | Mirrors `leverage_scores`/`top_n_by_metric`; classification lives in the pure fn so it is unit-testable without reactivity. |

## 2. No data-model change
This feature adds **nothing** to `sespy/data_structure.py`. It consumes
`Connection.source`, `.target`, `.strength`, `.confidence` (all already present)
via the existing `_edge_weight`. `Element.id`/`.label`/`.type` drive the table
and point colours. Isolated elements (no edges) get influence = dependence = 0.

## 3. Pure function (`sespy/network.py`, append; no Shiny/matplotlib)

```python
def influence_dependence(isa: IsaData) -> dict[str, dict]:
    """Vester influence × dependence per node, weighted & sign-agnostic.

    influence  = Σ _edge_weight over a node's outgoing edges (to OTHERS)
    dependence = Σ _edge_weight over a node's incoming edges (from OTHERS)
    quadrant   = active | critical | reactive | buffering, split at
                 the mean of each axis (>= mean = high side); or
                 'undetermined' when the system has no differentiation.
    Returns {} for an empty graph; never raises.
    """
```

Returned shape, one row per element id:
```python
{"N01": {"influence": 7.0, "dependence": 3.0, "quadrant": "active"}, ...}
```

Algorithm:
1. If `isa.elements` is empty → return `{}`.
2. Initialise every element id to `influence=0.0, dependence=0.0` (isolated nodes
   must appear).
3. **Deduplicate edges** into a `weight_by_pair: {(source, target): _edge_weight}`
   map (last-wins), so parallel `(src,tgt)` edges collapse to one — matching
   `to_digraph` (`network.py:15-21`), which every other metric uses. **Skip
   self-loops** (`if source == target: continue`).
4. For each `(source, target) -> w` in `weight_by_pair`: add `w` to `source`'s
   influence and to `target`'s dependence.
5. `mean_inf = mean(influence over all nodes)`, `mean_dep = mean(dependence)`.
6. **Degeneracy guard:** if the deduplicated, self-loop-free edge set is empty,
   **or** both axes have ~zero variance (every node tied — e.g. an all-isolated
   graph or a uniform-weight ring), classify **every** node as `undetermined`
   and return. This mirrors the `_zscore` `std == 0` guard already in
   `network.py:157-158`, and avoids the false "everything is Critical" label
   the `>=` tie rule would otherwise produce for a system with no differentiation.
7. Otherwise classify each node:
   - `active`    : inf ≥ mean_inf **and** dep <  mean_dep
   - `critical`  : inf ≥ mean_inf **and** dep ≥ mean_dep
   - `reactive`  : inf <  mean_inf **and** dep ≥ mean_dep
   - `buffering` : inf <  mean_inf **and** dep <  mean_dep

Quadrant semantics (used verbatim in UI captions / i18n):

| | Low dependence | High dependence |
|---|---|---|
| **High influence** | **Active / Driving** — best leverage | **Critical / Ambivalent** — powerful but ripples back |
| **Low influence** | **Buffering / Inert** — deprioritise | **Reactive / Dependent** — outcomes & indicators |

`undetermined` is a fifth, non-quadrant state for a system with no structural
differentiation; the UI shows a "no differentiation" caption rather than placing
points (see §4, §5).

## 4. Module (`sespy/modules/analysis_quadrant.py`)

Mirrors `analysis_leverage.py` structure exactly.

**UI** — `ui.card(card_header(t("card.quadrant")), layout_sidebar(...))`:
- **Sidebar**: `t("quadrant.about")` heading + `t("quadrant.about_text")` muted
  blurb describing the four categories. No interactive controls in v1.
- **Main**: `ui.h4(t("quadrant.map"))` + `@render.plot` scatter, then `<hr>`,
  `ui.h4(t("quadrant.classification"))` + `@render.data_frame` table.

UI text uses the **module-level `t()` imported from `..i18n`** (the global
default translator), exactly like `analysis_leverage.py` — no translator-bound
calls. The `translator` server param below is accepted only for signature parity
with the sibling modules and is otherwise unused.

**Server** — `analysis_quadrant_server(input, output, session, *, project_data,
event_bus, translator=None)`:
- `@reactive.calc rows()`: touches `event_bus.isa_change`, returns
  `influence_dependence(project_data().isa_data)`.
- `@render.plot`: build with `fig, ax = plt.subplots(...)` and **`return fig`** —
  no `plt.close`; `@render.plot` owns the figure lifecycle (matches
  `analysis_metrics`/`bot`). X = dependence, Y = influence; dashed vertical line
  at `mean_dep`, dashed horizontal at `mean_inf`; each node a point coloured by
  `ELEMENT_COLORS.get(type, DEFAULT_GROUP_COLOR)`, annotated with the element
  label; four quadrant captions in the corners; axis labels via i18n. **Empty
  graph or `undetermined` (all rows undetermined)** → single centered
  "no data" / "no differentiation" caption, no axes error.
- `@render.data_frame`: columns `rank, id, label, type, influence, dependence,
  quadrant`, sorted by influence descending, values rounded to 3 dp. **When
  `rows()` is empty, return `pd.DataFrame(columns=[...])`** with those exact
  column names (mirrors `analysis_leverage.py:157-159`) so the grid renders
  headers, not a column-less frame.

**Registration** (`app.py`) — **four** edits (a bare `nav_panel` is not enough;
the clickable sidebar button and stepper highlight come from `NAV`/`NAV_TO_STEP`,
which feed `dashboard.py`):
1. Import: `from sespy.modules.analysis_quadrant import analysis_quadrant_server, analysis_quadrant_ui`.
2. `NAV` (app.py:78-96): append `NavItem(id="quadrant", icon=<fa-icon>,
   label="Factor Quadrant", label_key="nav.quadrant")` after the `leverage`
   entry — this generates the `#sespy_nav_quadrant` sidebar button the e2e clicks.
3. `NAV_TO_STEP` (app.py:111-123): add `"quadrant": "analyze"` so the DAPSI
   stepper highlights correctly on this panel.
4. `PANELS` + server: `ui.nav_panel("Factor Quadrant",
   analysis_quadrant_ui("quadrant"), value="quadrant")` after "Leverage Points"
   (line 134), and `analysis_quadrant_server("quadrant",
   project_data=project_data, event_bus=event_bus, translator=T)`.

**i18n** (`sespy/translations/core.json`, the single catalog, 9 languages):
`card.quadrant`, `quadrant.about`, `quadrant.about_text`, `quadrant.map`,
`quadrant.classification`, `quadrant.axis_influence`, `quadrant.axis_dependence`,
the four quadrant display names (`quadrant.active`/`.critical`/`.reactive`/
`.buffering`), `quadrant.undetermined`, **and `nav.quadrant`** (the sidebar
label, required by the `NavItem` in edit 2) — each added in all 9 catalog
languages, mirroring `leverage.*` / `nav.leverage` coverage.

## 5. Edge cases & error handling
Following `network.py`'s zeros-never-raise posture (`_safe_floats`, guards):
- **Empty graph (no elements)** → `influence_dependence` returns `{}`; module
  shows empty table (with headers) + "no data" plot caption. Never raises.
- **No edges / all-isolated nodes** → all influence = dependence = 0; the
  degeneracy guard (§3 step 6) classifies all as `undetermined`; UI shows a
  "no differentiation" caption rather than painting every node `critical`.
- **Uniform graph** (every edge equal weight, e.g. a ring/lattice) → all nodes
  tie at the mean on both axes → ~zero variance → degeneracy guard → all
  `undetermined`. This is the *common* degenerate case and the reason the guard
  exists.
- **Single node** → no edges → `undetermined` (via the guard).
- **Self-loops** (`source == target`) → skipped in accumulation (§3 step 3);
  contribute to neither axis.
- **Parallel/duplicate `(src,tgt)` edges** → deduplicated (last-wins, §3 step 3)
  so they cannot inflate the sums or shift the mean.
- **Malformed edge attrs** → `_edge_weight` already clamps `confidence` to [1,5]
  and defaults unknown `strength` to rank 2; sums cannot crash.
- **Hub-skew caveat (recorded, not fixed):** because each axis is an unbounded
  Σ of edge weights (un-standardised, unlike `leverage_scores` which z-scores
  first), a single high-degree hub raises the mean and can push the long tail
  below it into `reactive`/`buffering`, hiding secondary leverage points. Mean
  remains the right *default* (it preserves "above-average influence" and keeps
  the Active/Critical quadrant sparse when drivers genuinely are few; median
  would manufacture drivers). Future option: a computable skew flag (e.g.
  `max(influence) > k · median(influence)`) surfacing a one-line "distribution is
  hub-skewed — consider median split" UI warning, making the median toggle
  data-triggered rather than speculative. Out of scope for v1.

Two layers — pure-function unit tests + a browser e2e — matching how the sibling
Leverage/Metrics modules are actually covered (neither has a Shiny module-server
"smoke" test; no such harness exists in this repo, so this spec does not invent
one).

1. **Unit** (`tests/test_network.py`, extend — pure `pytest` of
   `influence_dependence`, no Shiny): a hand-computed 3–4 node fixture verifying
   exact influence/dependence sums and all four quadrant labels; empty-graph →
   `{}`; all-isolated → all `undetermined`; uniform-weight ring → all
   `undetermined`; **self-loop is ignored** (a node with only a self-loop reads
   0/0); **parallel `(src,tgt)` edges deduplicate** (two A→B edges count once,
   last-wins weight); sign-agnosticism (a `-` edge contributes positive
   magnitude); weight reuse (strong/high-confidence edge outranks weak/low).
2. **e2e** (`tests/test_quadrant_e2e.py`, new) — model **exactly** on
   `tests/test_leverage_e2e.py`: a standalone `asyncio.run(main())` Playwright
   script (NOT a pytest test) that opens a browser, `goto`
   `http://127.0.0.1:8000`, clicks `#sespy_nav_quadrant`, waits for the
   `@render.data_frame` rows and the `@render.plot` `<img>`, asserts, screenshots.
   It runs against the app's default project (`data/sample_ses.json`, ~17 nodes
   — there is no per-test seeding helper). **Gate:** `python tests/run_e2e.py`
   (auto-discovers `test_*_e2e.py`, boots `shiny run app.py`, runs each script as
   a subprocess). **Run the FULL e2e suite before merge — never `-k "not e2e"`,
   and never `pytest tests/ -q` for the e2e scripts** (pytest would import them at
   collection and fire `asyncio.run()` with no server up).

## 7. Build order (for the plan)
1. `influence_dependence` in `network.py` (dedup + self-loop skip + degeneracy
   guard) + unit tests (TDD; red→green).
2. i18n keys — the 11 `quadrant.*`/`card.quadrant` keys **+ `nav.quadrant`**,
   each in all 9 `core.json` languages, mirroring `leverage.*`/`nav.leverage`.
3. `analysis_quadrant.py` module (UI + server; module-level `t()`; plot returns
   `fig`; empty-frame columns).
4. `app.py` registration — **four edits**: import, `NavItem` in `NAV`,
   `"quadrant": "analyze"` in `NAV_TO_STEP`, `ui.nav_panel` + server call.
5. `tests/test_quadrant_e2e.py` (standalone asyncio Playwright, modelled on
   `test_leverage_e2e.py`).
6. Full e2e gate via `python tests/run_e2e.py` (never `-k "not e2e"` / `pytest`
   on the e2e scripts) → merge → push.
