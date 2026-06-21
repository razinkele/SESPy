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
- One new flat nav entry in `app.py` ("Factor Quadrant") + server wiring.
- New i18n keys in `sespy/translations/core.json` alongside the `leverage.*` /
  `card.leverage` keys.
- Unit + module-smoke + e2e tests.

### 1.2 Out of scope
- **No data-model / schema change.** Reads only existing
  `Connection.source/target/strength/confidence`. No `PROJECT_SCHEMA_VERSION`
  bump. `Connection.polarity` is read but only to confirm magnitude is taken
  sign-agnostically (polarity does **not** affect influence/dependence).
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
| Sign handling | **Sign-agnostic** (magnitude only; `+` and `-` both contribute positive weight) | Vester influence/dependence measures *how much* a factor drives/is driven, not the direction. A factor that strongly suppresses three others is highly influential; cancelling `-` edges would erase that. |
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

    influence  = Σ _edge_weight over a node's outgoing edges
    dependence = Σ _edge_weight over a node's incoming edges
    quadrant   = active | critical | reactive | buffering, split at
                 the mean of each axis (>= mean = high side).
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
3. For each connection: add `_edge_weight(c)` to `source`'s influence and to
   `target`'s dependence.
4. `mean_inf = mean(influence over all nodes)`, `mean_dep = mean(dependence)`.
5. Classify each node:
   - `active`    : inf ≥ mean_inf **and** dep <  mean_dep
   - `critical`  : inf ≥ mean_inf **and** dep ≥ mean_dep
   - `reactive`  : inf <  mean_inf **and** dep ≥ mean_dep
   - `buffering` : inf <  mean_inf **and** dep <  mean_dep

Quadrant semantics (used verbatim in UI captions / i18n):

| | Low dependence | High dependence |
|---|---|---|
| **High influence** | **Active / Driving** — best leverage | **Critical / Ambivalent** — powerful but ripples back |
| **Low influence** | **Buffering / Inert** — deprioritise | **Reactive / Dependent** — outcomes & indicators |

## 4. Module (`sespy/modules/analysis_quadrant.py`)

Mirrors `analysis_leverage.py` structure exactly.

**UI** — `ui.card(card_header(t("card.quadrant")), layout_sidebar(...))`:
- **Sidebar**: `t("quadrant.about")` heading + `t("quadrant.about_text")` muted
  blurb describing the four categories. No interactive controls in v1.
- **Main**: `ui.h4(t("quadrant.map"))` + `@render.plot` scatter, then `<hr>`,
  `ui.h4(t("quadrant.classification"))` + `@render.data_frame` table.

**Server** — `analysis_quadrant_server(input, output, session, *, project_data,
event_bus, translator=None)`:
- `@reactive.calc rows()`: touches `event_bus.isa_change`, returns
  `influence_dependence(project_data().isa_data)`.
- `@render.plot`: X = dependence, Y = influence; dashed vertical line at
  `mean_dep`, dashed horizontal at `mean_inf`; each node a point coloured by
  `ELEMENT_COLORS.get(type, DEFAULT_GROUP_COLOR)`, annotated with the element
  label; four quadrant captions in the corners; axis labels via i18n. Empty
  graph → single centered "no data" caption, no axes error.
- `@render.data_frame`: columns `rank, id, label, type, influence, dependence,
  quadrant`, sorted by influence descending, values rounded to 3 dp.

**Registration** (`app.py`):
- `from sespy.modules.analysis_quadrant import analysis_quadrant_server, analysis_quadrant_ui`
- `ui.nav_panel("Factor Quadrant", analysis_quadrant_ui("quadrant"), value="quadrant")`
  placed **after** "Leverage Points" (line 134).
- `analysis_quadrant_server("quadrant", project_data=project_data, event_bus=event_bus, translator=T)`.

**i18n** (`sespy/translations/core.json`): `card.quadrant`, `quadrant.about`,
`quadrant.about_text`, `quadrant.map`, `quadrant.classification`,
`quadrant.axis_influence`, `quadrant.axis_dependence`, and the four quadrant
display names (`quadrant.active`/`.critical`/`.reactive`/`.buffering`) — added
in every locale present in the catalog, mirroring the `leverage.*` entries.

## 5. Edge cases & error handling
Following `network.py`'s zeros-never-raise posture (`_safe_floats`, guards):
- **Empty graph** → `influence_dependence` returns `{}`; module shows empty
  table + "no data" plot caption. Never raises.
- **Isolated nodes / no edges** → all influence = dependence = 0; mean = 0; with
  `≥` rule all land `critical`. Documented as correct-but-degenerate; visually
  obvious from the empty edge set.
- **Single node** → mean equals its own value → `critical`. Trivial, fine.
- **Malformed edge attrs** → `_edge_weight` already clamps `confidence` to [1,5]
  and defaults unknown `strength` to rank 2; sums cannot crash.
- **Caveat (recorded, not fixed):** on small degree-skewed graphs the mean can be
  dominated by a hub, pushing most nodes into `reactive`/`buffering`. Accepted
  for v1; a median-split toggle is the documented future option.

## 6. Testing
1. **Unit** (`tests/test_network.py`, extend): a hand-computed 3–4 node fixture
   verifying exact influence/dependence sums and all four quadrant labels;
   empty-graph → `{}`; isolated-node → 0/0/`critical`; sign-agnosticism (a `-`
   edge contributes positive magnitude); weight reuse (strong/high-confidence
   edge outranks weak/low).
2. **Module smoke** (existing module-test pattern): server renders table + plot
   without error on a seeded sample project.
3. **e2e** (`tests/test_quadrant_e2e.py`, new): navigate to the "Factor Quadrant"
   panel, assert the table renders rows and the plot image appears, on a seeded
   project. Runs in the **full e2e gate before merge** — `pytest tests/ -q`,
   never `-k "not e2e"`.

## 7. Build order (for the plan)
1. `influence_dependence` in `network.py` + unit tests (TDD; red→green).
2. i18n keys.
3. `analysis_quadrant.py` module (UI + server).
4. `app.py` registration (import, nav_panel, server call).
5. e2e test.
6. Full-suite e2e gate → merge → push.
