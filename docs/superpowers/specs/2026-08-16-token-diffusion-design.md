# Stochastic Token Diffusion (issue #17) — Design

**Date:** 2026-08-16. **Status:** approved in session.
**Source:** GitHub issue #17 — Donlan, Arteaga-Bengoa & Carrasco (2026), *A systems thinking approach to improve participatory processes in small-scale fisheries management*, Research Square preprint, doi:10.21203/rs.3.rs-10397797/v1. Step 2 of their three-step framework (participatory CLD → token diffusion → centrality); SESPy already has steps 1 and 3.

## Problem

Nothing in SESPy answers "if I intervene at node X, which nodes does the effect reach, how fast, and with what net sign?". `leverage_scores` is source-independent, `causal_paths` (#16) is structural rather than dynamic, `uncertainty_scores` perturbs structure rather than propagation, and `intervention_impact` measures centrality deltas from ablation rather than reach.

## Decisions (user-confirmed)

1. **Placement: the existing Intervention card**, as a second block beside the ablation analysis — same practitioner question, existing reactive wiring, and it keeps the Network Metrics card from growing to six blocks.

## Function

`token_diffusion(isa: IsaData, source: str, *, n_steps: int = 10, n_tokens: int = 1000, seed: int | None = None) -> dict` in `sespy/dynamics.py`.

- **Adjacency**: CSR-style numpy arrays built once — `indptr` (per-node offsets into a flat neighbour array), `indices` (target node indices), `flip` (bool: the edge polarity is `"-"`). Parallel `(source, target)` edges deduplicate last-wins (the `_axis_sums` convention); self-loops and dangling refs skipped. Only `"-"` flips a token; anything else is sign-preserving (every current ingress emits `"+"`/`"-"`).
- **Simulation**: `pos` (int array, all `source`) and `sign` (int8 array, all `+1`), `n_tokens` long. Per step, for tokens whose node has out-degree > 0, `slot = indptr[pos] + floor(rng.random(k) * outdeg[pos])`; `pos = indices[slot]`, `sign *= where(flip[slot], -1, 1)`. Tokens at sinks stay put and stop contributing arrivals (issue acceptance criterion). Fully vectorised — 5000 tokens × 30 steps is 30 numpy ops, not 150 000 Python iterations.
- **Recording**: per node ≠ source, `tokens_received` = arrivals summed across all steps (a token that returns counts again), `pos_count`/`neg_count` from the token's polarity ON arrival, `first_arrival_step` = 1-based step of first arrival. Nodes never reached are omitted from rows entirely (they carry no information; `n_reached` and the model's element count give the denominator).
- **`net_sign`**: `"+"`, `"-"`, or `"~"` when `abs(pos - neg) / total <= 0.05` (the issue's 5 % contested margin).
- **Return**: `{"rows": [{"id", "label", "tokens_received", "net_sign", "first_arrival_step"}], "source": str, "n_tokens": int, "n_steps": int, "n_reached": int}`. Rows sorted by `tokens_received` descending, ties in `isa.elements` order (stable sort) — deterministic given a seed.
- **Degenerate inputs** → `{"rows": [], "source": source, "n_tokens": …, "n_steps": …, "n_reached": 0}`: unknown source, empty model, `n_tokens <= 0`, `n_steps <= 0`, or a source with no outgoing edges (sink source: every token stays put, nothing is ever received). Never raises.
- **Reproducibility**: `np.random.default_rng(seed)`; identical results for identical `(isa, source, n_steps, n_tokens, seed)`.
- Dict-of-row-dicts, NOT the issue's DataFrame: `dynamics.py` is numpy + TypedDict, pandas-free (the module layer builds any DataFrame it needs).

## UI

Second block in `sespy/modules/analysis_intervention.py` (which is `ui.card` + `layout_sidebar`):

- **Sidebar** (after the existing ablation controls + `hr`): `ui.output_ui("diffusion_controls")` rendering a source `input_select` (choices `id · label`, refreshed on `isa_change`, current value preserved across re-render via the `reactive.isolate()` restore pattern from #16), `input_slider("n_steps", 3–30, default 10)`, `input_slider("n_tokens", 100–5000, step 100, default 1000)`, and a `Run simulation` action button.
- **Main column** (after the existing network): `ui.output_ui("diffusion_summary")` + `ui.output_plot("diffusion_chart", height="260px")`.
- **State**: `_diffusion_result = reactive.value(None)`; reset effect on `event_bus.isa_change`; compute effect on `@reactive.event(input.run_diffusion, ignore_init=True)`.
- **Fixed seed**: the UI calls `token_diffusion(..., seed=0)`. Deliberate — comparing two candidate interventions is the stated use case, and a fixed seed means the difference between them is structural rather than RNG noise. It also makes the e2e assertable. Documented in the block's caption.
- **States**: <2 elements → muted `metrics.gov_gap_none`; result `None` → controls + `diffusion.hint`; result with no rows → `diffusion.none` (unreached/sink source); otherwise summary line `diffusion.summary` (`{reached}` of `{total}` elements reached by `{tokens}` tokens in `{steps}` steps), plain `table table-sm` (`id · label`, tokens, net sign, first step), and the bar chart.
- **Chart**: matplotlib bar chart (mirrors `metrics_hist`), height = `tokens_received`, colour by `net_sign` (`+` green `#2e7d32`, `-` red `#c62828`, `~` grey `#757575`), top 12 rows, x labels = element labels rotated. Empty result → an empty axes, never an exception.
- **i18n** (×9 languages): `diffusion.title`, `diffusion.source`, `diffusion.steps`, `diffusion.tokens`, `diffusion.run`, `diffusion.hint`, `diffusion.none`, `diffusion.summary` (params reached/total/tokens/steps), `diffusion.caption` (fixed-seed note). Nine keys.

## Testing

- Unit (`tests/test_dynamics.py`): manual-trace chain A→B→C→D with a negative B→C edge — every token follows the only route, so counts, `first_arrival_step` (1, 2, 3) and the sign flip at C/D are exactly predictable (issue acceptance criterion "consistent with manual trace"); sink behaviour (D has no out-edges, tokens stop); seed reproducibility (same seed identical, different seed differs on a branching graph); `"~"` classification on a 50/50 branch; source excluded from rows; degenerate shapes (unknown source, empty model, sink source, `n_tokens=0`); a `sample_ses.json` golden at `seed=0`.
- i18n presence test (9 keys).
- e2e: extend an intervention e2e — open the Intervention tab, click `#intervention-run_diffusion`, assert the summary line and a known top row appear in `#intervention-diffusion_summary`, and that the plot image rendered. Scoped ids only.
- Gates: CI-parity unit suite; FULL detached e2e (32 scripts) on an idle machine, port 8000 cleared first.

## Out of scope (YAGNI)

Edge-weight-magnitude propagation (the method is deliberately qualitative); multi-source seeding; overlaying the diffusion field on the CLD; exposing `seed` in the UI.
