# Social-ecological "fit" metric design

**Date:** 2026-06-24
**Status:** approved (brainstorm)
**Tracks:** GitHub issue #1.
**Motivated by:** Fang et al., *Assessing social–ecological fit of sustained
watershed environmental governance* (Dianchi Lake), Env. Impact Assessment Review
(2026), 10.1016/j.eiar.2026.108522 — see `LITERATURE/2026-06-22.md`.

## Problem

SESPy computes per-node centrality but no graph-level diagnostic of how well the
**social** subsystem couples to the **ecological** subsystem. "Fit" (a core SES
governance concept) asks whether social ties track the ecological interdependencies
they act on. Add a graph-level coupling diagnostic and surface it in the Network
Metrics module.

## Decisions (from brainstorm)

- **Partition (Q1)** — DAPSIWRM type → subsystem, a single source of truth:
  | Subsystem | Types |
  |---|---|
  | `social` | Drivers, Activities, Responses, Goods & Benefits |
  | `ecological` | Pressures, Marine Processes & Functioning, Ecosystem Services |
  The contestable boundary (ES vs G&B) is resolved ES→ecological (service-generating
  capacity), G&B→social (human-consumed benefit). Pressures→ecological (act on the
  environment). It is one editable dict.
- **Fit measure (Q2)** — headline = **cross-boundary coupling**:
  `fit = cross_edges / total_edges` (share of edges linking social ↔ ecological;
  higher = tighter integration / better fit, lower = siloed subsystems), plus the
  supporting counts. Modularity/assortativity deferred (YAGNI; its sign inverts the
  "fit" intuition).
- **Caveat (documented, accepted):** this is a *coupling/integration proxy*, not the
  full theoretical SES "fit" (which compares separate social-tie and ecological-
  interdependence matrices). A useful diagnostic, not a truth claim.

## Architecture / components

### `sespy/network.py` — partition helper + fit function (pure)
```python
_SUBSYSTEM: dict[str, str] = {
    "Drivers": "social",
    "Activities": "social",
    "Responses": "social",
    "Goods & Benefits": "social",
    "Pressures": "ecological",
    "Marine Processes & Functioning": "ecological",
    "Ecosystem Services": "ecological",
}


def subsystem(element_type: str) -> str:
    """'social' | 'ecological' | '' (unknown type, e.g. 'Measures')."""
    return _SUBSYSTEM.get(element_type, "")


def social_ecological_fit(isa) -> dict:
    """Graph-level social↔ecological coupling diagnostic. Pure.

    Classifies each element by subsystem(); over connections (self-loops and
    dangling refs skipped), counts edges WITHIN social, WITHIN ecological, and
    CROSSing the boundary. Edges touching an unclassified node are excluded from
    every tally. `fit` = cross / total (total = within_social + within_ecological +
    cross), or 0.0 when total == 0.

    Returns {n_social, n_ecological, n_other, within_social_edges,
    within_ecological_edges, cross_edges, total_edges, fit}.
    """
```
- `n_social`/`n_ecological` count classified elements; `n_other` = unclassified
  (e.g. `Measures` — same accepted-gap path as the typology feature).
- Edges keyed by `(source, target)`; a self-loop (`source == target`) or a dangling
  ref (endpoint not an element id) is skipped, mirroring `_axis_sums`/`_edge_weight`.
- `fit` is a float in [0, 1]; `0.0` for an empty/edgeless graph (never raises).

### `sespy/modules/analysis_metrics.py` — surface it
- **UI:** add `ui.output_ui("fit_summary")` at the top of the main content area
  (above `metrics.top_ranked`). Note the qualified `ui.output_ui` — the module
  imports `ui` (and `t`, `net_analysis`), NOT a bare `output_ui` name.
- **Server:** add an `@output` / `@render.ui def fit_summary():` (the pattern used
  by `analysis_loops.py`'s `classification_summary`): touch `event_bus.isa_change.get()`
  for the reactive dep, compute
  `r = net_analysis.social_ecological_fit(project_data.get().isa_data)`, then:
  ```python
  if r["total_edges"] == 0:
      return ui.p(t("metrics.fit_none"), class_="text-muted")
  return ui.div(
      ui.h5(t("metrics.fit")),
      ui.tags.strong(f"{r['fit']:.2f}"),
      ui.p(t("metrics.fit_caption", cross=r["cross_edges"], total=r["total_edges"]),
           class_="text-muted", style="font-size: 0.85rem;"),
  )
  ```
  → renders e.g. heading "Social-ecological fit", value `0.40`, caption
  "8 of 20 edges cross the social–ecological boundary".
- No change to the existing metric-picker / top-N table / histogram / network.

### i18n — `sespy/translations/core.json`
3 new keys × 9 languages: `metrics.fit` ("Social-ecological fit"),
`metrics.fit_caption` ("{cross} of {total} edges cross the social–ecological
boundary", `{cross}`/`{total}` interpolation — supported), `metrics.fit_none`
("no classifiable cross-boundary edges to assess" — "classifiable" so the message
is also accurate for a pure-unclassified graph, see Error handling).

## Data flow

`fit_summary` reads `event_bus.isa_change` so it refreshes on any edit; the metric
is recomputed from the current `isa_data` at render time (O(edges), cheap). No
persistence, no new analysis beyond the pure function.

## Error handling / edge cases

- Empty graph / no edges → `total_edges == 0` → `fit == 0.0`, summary shows the
  `fit_none` message.
- All-social or all-ecological graph → `cross_edges == 0` → `fit == 0.0` (genuinely
  siloed / single-subsystem), shown as `0.00`.
- Unclassified node type (`Measures`/unknown) → `n_other`; edges touching it are
  excluded from the tally (documented), so they neither help nor hurt `fit`.
- **Pure-unclassified graph** (e.g. only `Measures` elements *with* connections) →
  every edge excluded → `total_edges == 0` → `fit_none` fires despite visible
  connections. The broadened message ("no *classifiable* cross-boundary edges to
  assess") reads accurately for this path as well as the empty-graph path; `n_other`
  is the signal that distinguishes it from a genuinely empty graph.
- Self-loops and dangling refs skipped (consistent with the other network helpers).
- Directed edges: a cross edge counts once regardless of direction (social→eco and
  eco→social are both "cross").

## Testing

`tests/test_network.py`:
- `subsystem` returns the right label for each of the 7 types; `""` for `Measures`
  and unknown.
- `social_ecological_fit` golden values on hand-built graphs — assert **every**
  count, not just `fit`. Cases:
  - **fully-crossed**: 1 social + 1 ecological node, one cross edge → `cross==1,
    total==1, fit==1.0`.
  - **siloed (both subsystems present)**: 2 social nodes (`Drivers`,`Activities`)
    with one within-social edge AND 2 ecological nodes (`Pressures`,
    `Ecosystem Services`) with one within-ecological edge → `n_social==2,
    n_ecological==2, n_other==0, within_social_edges==1, within_ecological_edges==1,
    cross_edges==0, total_edges==2, fit==0.0`. (Both subsystems present so the
    cross-detection branch actually runs — an all-`Drivers` graph would pass
    `fit==0.0` trivially without exercising it.)
  - **empty graph**: all zeros, `fit==0.0`.
  - **`Measures` excluded**: a `Measures` node with an edge to a social node →
    `n_other==1` and that edge counted in no tally (`total_edges` unchanged).
  - **self-loop / dangling ref skipped**.
- Sample-fixture anchor: `social_ecological_fit` on `data/sample_ses.json` returns
  `fit==0.40` with `cross_edges==8, within_social_edges==6, within_ecological_edges==6,
  total_edges==20, n_social, n_ecological` summing to all classified nodes — a golden
  assertion that catches a numerator/denominator swap and guards against silent
  sample drift.

`tests/test_metrics_e2e.py` (extend — this file is a standalone `asyncio.run(main())`
script, NOT a pytest-asyncio module; there is no conftest/`asyncio_mode`):
- Add the assertion block at the END of the existing `main()` coroutine (after the
  last existing block, before `await browser.close()`). Do NOT add an
  `async def test_*` function.
- Navigate to Network Metrics; read `#metrics-fit_summary` (outputs are id-prefixed
  `metrics-`, as with `#metrics-metrics_table`); assert the `metrics.fit` heading
  ("Social-ecological fit") is present AND the rendered value is exactly **`0.40`**
  (the locked golden value for `sample_ses.json`: 8 of 20 cross-boundary edges) —
  a `\d\.\d\d` regex alone would silently survive sample drift, so assert `0.40`.
- i18n presence: add `test_metrics_fit_keys_present` to `tests/test_i18n.py`
  asserting the 3 new keys exist (the loader test only checks completeness, not
  presence — same gate as the typology feature).

## Out of scope (YAGNI)

- Modularity / assortativity / chance-corrected (expected-value) normalization.
- Per-node or per-subsystem fit breakdowns; a fit time-series.
- Configurable partition UI (it is an editable dict in code).
- Any change to the metric-picker, centrality table, histogram, or network graph.
- Graph styling by subsystem.
