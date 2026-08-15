# Causal Path Tracer (issue #16) — Design

**Date:** 2026-08-15. **Status:** approved in session.
**Source:** GitHub issue #16 — *A dynamic explainability method for fuzzy cognitive maps based on causal and temporal evolution analysis*, Applied Soft Computing 2026, doi:10.1016/j.asoc.2026.115925. Per the issue, only the STATIC path-enumeration + sign-arithmetic layer is in scope; the paper's temporal/dynamic simulation is not.

## Decisions (user-confirmed)

1. **Trigger: Trace button** — source/target selectors plus a "Trace paths" button, the cascade block's gating pattern: nothing computes until clicked; any `isa_change` clears the stored result.

## Function

`causal_paths(isa: IsaData, source: str, target: str, *, max_length: int = 8, max_paths: int = 100) -> dict` in `sespy/network.py`.

- Adjacency: last-wins polarity per unique `(source, target)` pair (the `_axis_sums` convention); self-loops and dangling refs skipped. All element ids are graph nodes.
- Guard: unknown `source`/`target`, or `source == target` → empty shape `{"paths": [], "counts": {"+": 0, "-": 0, "0": 0}, "truncated": False}` (never raises; issue criterion).
- Enumerate `nx.all_simple_paths(g, source, target, cutoff=max_length)` — **cutoff counts edges** (verified on networkx 3.6.1). Simple paths only, so cycles/self-loops are inherently handled (issue criterion).
- Row: `{"path": [ids...], "length": n_edges, "polarity": "+" | "-" | "0"}`. Compound polarity: `"0"` if any hop's stored polarity is not `"+"`/`"-"` (forward-looking — every current ingress emits only `"+"`/`"-"`, same unreachable-but-cheap stance as "Measures"); else `"-"` for an odd count of `"-"` hops, `"+"` otherwise.
- Collection stops at `max_paths`; `truncated: True` when more paths remained (peek semantics — never a silent cap). Rows sorted `(length, path)` — fully deterministic.
- Returns `{"paths": rows, "counts": {"+": …, "-": …, "0": …}, "truncated": bool}`. List-of-row-dicts, NOT the issue's DataFrame (`network.py` is pandas-free); signature takes `isa`, not `g` (module convention).

**Sample goldens** (computed against the repo, 2026-08-15): `D001→P001` → one path `D001→A001→P001`, length 2, `"+"`. `ES02→D001` → two length-8 paths, both `"-"`, sorted `…MPF1→ES01→GB01→D001` before `…MPF1→ES03→GB01→D001`; with `max_paths=1` → 1 row + `truncated=True`. `D001→ES02` → empty shape (no directed route exists in the sample).

## UI

Fifth block on the Network Metrics card (`analysis_metrics.py`), after cascade:

- `ui.output_ui("paths_summary")` + `ui.tags.hr()` in the card. Rendered block: heading, two `ui.input_select`s (`paths_source`, `paths_target`; choices `{id: "id · label"}` from current elements, defaults first/last element id), "Trace paths" button, result area.
- State: `_paths_result = reactive.value(None)`; reset effect on `event_bus.isa_change`; compute effect on `@reactive.event(input.trace_paths, ignore_init=True)` storing `causal_paths(isa, input.paths_source(), input.paths_target())`.
- Render states: <2 elements → muted `metrics.gov_gap_none`; result `None` → selectors + button + `metrics.cascade_hint` (reused verbatim — same meaning); result with 0 paths → selectors + button + muted `metrics.paths_none`; otherwise → summary line `metrics.paths_summary` ("{n} paths: {pos} positive, {neg} negative, {amb} ambiguous"), the table (path as label chain `A → B → C`, length, polarity columns; plain `ui.tags.table table table-sm`), truncation note `metrics.paths_truncated` when `truncated`.
- Because the selects re-render with the block, their CURRENT values persist via Shiny's input restoration; choices refresh naturally since the renderer rebuilds them from the live model on `isa_change`.
- New i18n keys (×9): `metrics.paths` (heading "Causal pathways"), `metrics.paths_trace` (button), `metrics.paths_source`, `metrics.paths_target`, `metrics.paths_summary` (params n/pos/neg/amb), `metrics.paths_none`, `metrics.paths_truncated` (param max). Seven keys; idle hint reuses `metrics.cascade_hint`.

## Testing

- Unit: the three sample goldens above; synthetic diamond (two routes, one sign-flipping — asserts `+`/`-` per route and counts); odd/even negative-count arithmetic on a chain; unknown-node and source==target empty shapes; `max_paths=1` truncation honesty on `ES02→D001`; determinism (two runs equal); cyclic graph yields only simple paths.
- i18n presence test (7 keys).
- e2e: on the sample, select `ES02` → `D001`, click trace, assert summary "2 paths: 0 positive, 2 negative, 0 ambiguous" and a known label-chain substring; scoped to `#metrics-paths_summary` / `#metrics-trace_paths`.
- Gates: CI-parity unit suite; FULL detached e2e (32 scripts), quiet machine, kill port 8000 first.

## Out of scope (YAGNI)

Temporal/dynamic FCM layer; CLD highlighting of traced paths; path weighting by edge strength; issue #17.
