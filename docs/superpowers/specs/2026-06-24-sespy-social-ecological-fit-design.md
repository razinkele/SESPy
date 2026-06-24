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
- Add `output_ui("fit_summary")` at the top of the main content area (above
  `metrics.top_ranked`). The server computes
  `net_analysis.social_ecological_fit(project_data.get().isa_data)` (depends on
  `event_bus.isa_change`) and renders a compact block:
  - heading `t("metrics.fit")` ("Social-ecological fit")
  - the value formatted `f"{fit:.2f}"`
  - caption `t("metrics.fit_caption", cross=cross_edges, total=total_edges)`
    → e.g. "12 of 28 edges cross the social–ecological boundary"
  - when `total_edges == 0` → render `t("metrics.fit_none")` ("no cross-boundary
    edges to assess") instead of a numeric value.
- No change to the existing metric-picker / top-N table / histogram / network.

### i18n — `sespy/translations/core.json`
3 new keys × 9 languages: `metrics.fit` ("Social-ecological fit"),
`metrics.fit_caption` ("{cross} of {total} edges cross the social–ecological
boundary", `{cross}`/`{total}` interpolation — supported), `metrics.fit_none`
("no cross-boundary edges to assess").

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
- Self-loops and dangling refs skipped (consistent with the other network helpers).
- Directed edges: a cross edge counts once regardless of direction (social→eco and
  eco→social are both "cross").

## Testing

`tests/test_network.py`:
- `subsystem` returns the right label for each of the 7 types; `""` for `Measures`
  and unknown.
- `social_ecological_fit` golden values on a hand-built graph with known
  social/ecological nodes and a known mix of within/cross edges — assert each count
  and `fit`. Cases: a fully-crossed graph (`fit == 1.0`); a siloed graph
  (`cross == 0`, `fit == 0.0`); empty graph (all zeros, `fit == 0.0`); a graph with
  a `Measures` node whose edges are excluded (`n_other == 1`, those edges not in any
  tally); self-loop/dangling skipped.

`tests/test_metrics_e2e.py` (extend):
- Navigate to Network Metrics; assert the fit summary renders — the `metrics.fit`
  heading is present and a numeric `fit` value (e.g. matches a `\d\.\d\d` pattern)
  shows for the sample project (which has cross-boundary edges).
- i18n presence: add `test_metrics_fit_keys_present` to `tests/test_i18n.py`
  asserting the 3 new keys exist (the loader test only checks completeness, not
  presence — same gate as the typology feature).

## Out of scope (YAGNI)

- Modularity / assortativity / chance-corrected (expected-value) normalization.
- Per-node or per-subsystem fit breakdowns; a fit time-series.
- Configurable partition UI (it is an editable dict in code).
- Any change to the metric-picker, centrality table, histogram, or network graph.
- Graph styling by subsystem.
