# Governance Actor Influence (issue #14) — Design

**Date:** 2026-08-13. **Status:** approved in session (design presented and accepted).
**Source:** GitHub issue #14 — *Unpacking power dynamics and actor interactions across fisheries and MPA governance* (Maritime Studies, 2026, doi:10.1007/s40152-026-00501-z).

## Problem

`governance_gap()` (#13, shipped) detects *whether* governance elements are linked into the ecological subsystem. Nothing quantifies *how influential* each governance element is within the whole network — the power-asymmetry diagnostic the source paper motivates (dominant vs. peripheral governance actors in co-management).

## Decisions (user-confirmed)

1. **UI placement:** third block on the Network Metrics card, after the governance-gap summary.
2. **Standardisation:** whole-network z-scores — each centrality is z-scored over ALL nodes, then rows are filtered to governance elements. A governance actor's score therefore reads "influence relative to the whole system", is stable under changes to the governance subset, and is definitionally consistent with `leverage_scores()`.

## Function

`governance_actor_influence(isa: IsaData) -> list[dict]` in `sespy/network.py`, placed near `leverage_scores`.

- Compute `centrality_metrics(isa)` once (full graph — cross-boundary influence must count).
- Z-score `betweenness`, `eigenvector`, `pagerank` over all nodes via the existing `_zscore`.
- One row per element whose `type` is in the existing module-private `_GOVERNANCE` frozenset (`{"Responses", "Measures"}` — Measures forward-compatible automatically, per #13's locked decision 9).
- Row shape: `{"id": str, "label": str, "type": str, "betweenness": float, "eigenvector": float, "pagerank": float, "influence": float}` where the metric columns are the RAW centrality values (readable in the table) and `influence` is the z-score sum — **equal by construction to `leverage_scores(isa)[id]`**: one definition, two views. A unit test pins this parity.
- Sort: `influence` descending; ties broken by `isa.elements` order (determinism).
- Degenerate inputs return `[]` (no governance elements, empty graph); no NaN anywhere (inherited from `_safe_floats` + `_zscore` guards); never raises.
- Return type is a list of row-dicts (the `top_n_by_metric` convention) — NOT a pandas DataFrame; the issue text's DataFrame suggestion loses to repo convention (network.py is pandas-free).

## UI

In `sespy/modules/analysis_metrics.py`:

- `analysis_metrics_ui`: `ui.output_ui("actor_influence_summary")` + `ui.tags.hr()` directly after the governance-gap pair.
- Server renderer `actor_influence_summary`, subscribing `event_bus.isa_change.get()` first (module rule):
  - `n_edges_considered`-style zero-structure guard: reuse `governance_gap(isa)["n_edges_considered"] == 0` → muted `t("metrics.gov_gap_none")` (consistency with the gap block; avoids an all-zeros table on a connections-free model).
  - No governance rows → muted `t("metrics.gov_gap_no_gov")` (existing string fits verbatim; no new key).
  - Otherwise: `ui.h5(t("metrics.actor_influence"))` + a plain HTML table built with `ui.tags.table` inside the same `output_ui` (NOT `render.data_frame` — `<shiny-data-frame>` renders into shadow DOM, which `page.inner_text` cannot see, so the e2e's R001/R002 text assertions would go blind; a static table also fits a list this small). Columns: `id · label`, the three centralities, `influence`, all numbers `:.2f`, rows already sorted. Bootstrap classes `table table-sm` for styling consistency.
  - Caption `t("metrics.actor_influence_caption")` explaining the composite ("z-score sum of betweenness, eigenvector and PageRank over the whole network").
- New i18n keys (×9 languages): `metrics.actor_influence`, `metrics.actor_influence_caption`. Presence test added.

## Testing

- Unit (`tests/test_network.py`): sample golden (exactly rows R001, R002; parity `influence == leverage_scores()[id]`); no-governance → `[]`; empty graph → `[]`; Measures element counted (synthetic-IsaData forward-compat precedent); deterministic tie order; disconnected graph yields finite values.
- i18n presence test for the 2 keys.
- e2e: extend `tests/test_metrics_e2e.py`, scoped to `#metrics-actor_influence_summary`, asserting the heading and that both `R001` and `R002` appear.
- Gates: CI-parity unit suite; FULL e2e suite (never a subset), kill port 8000 first.

## Out of scope (YAGNI)

Out-degree quartiles and signed-degree ratios from the source paper (repo centralities are unweighted/unsigned); plots; exposing the function to other modules; issue #15.
