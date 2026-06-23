# Uncertainty-aware leverage & loop scoring — design

**Date:** 2026-06-23
**Status:** approved (brainstorm)
**Motivated by:** Uleman et al., *Diagrams-to-Dynamics (D2D): exploring causal loop
diagram leverage points under uncertainty*, BMC Medicine (2026).
<https://doi.org/10.1186/s12916-026-04971-0> — see `LITERATURE/proposed-issues.md`.

## Problem

SESPy ranks leverage points (`leverage_scores`) and classifies feedback loops
(`classify_loops`) on **point-estimate** topology. Every connection carries a
rater `confidence` (1–5), but that uncertainty never reaches these two outputs:

- `leverage_scores` is **structural** — it composes z-scores of betweenness,
  eigenvector, and PageRank centrality, all computed by `to_digraph` +
  `centrality_metrics` on an **unweighted** graph (no `weight=` argument is
  passed to any NetworkX call). `confidence` is not even an edge attribute on
  that digraph.
- `classify_loops` is **sign-based** — loop type is the product of edge
  polarities (`loop_polarity`). `confidence` is a magnitude (1–5) and cannot
  flip a sign.

So today, resampling `confidence` would change neither output. (`confidence`
currently flows only through `_edge_weight` = strength × confidence, into
`influence_dependence` and the `simplify_*` helpers.) D2D shows the value of
propagating link uncertainty into exactly these leverage/loop diagnostics; this
feature adds that channel.

## Approach

A **D2D-faithful structural Monte Carlo**. On each draw, every connection is
independently perturbed in two orthogonal ways:

- **Drop-out** — the edge vanishes from the graph (presence uncertainty).
- **Sign-flip** — the edge's polarity reverses (direction uncertainty).

Each perturbation fires with a per-draw probability that decreases in confidence:

```
p(conf) = base · (5 − conf) / 4        # conf 5 → 0,  conf 1 → base
```

Default `base = 0.5` → drop/flip probabilities of
`{1: 0.50, 2: 0.375, 3: 0.25, 4: 0.125, 5: 0.0}`. The same map is applied
independently to drop and to flip (one knob governs the whole model; YAGNI on
splitting it into two until a use case demands it).

### Why both perturbations

The two channels feed two orthogonal outputs, and the feature targets both:

- **Leverage** is structural, so it only moves when topology changes → **drop**
  is required, or leverage CIs are degenerate.
- **Loop polarity** only changes via **sign-flip** (a surviving loop keeps its
  polarity under drop alone). Drop additionally gives loop-*existence*
  probability.

Dropping either perturbation guts one of the two deliverables. The cost is
modest: two independent Bernoulli draws per edge.

### Key invariants

- **The baseline loop set is the universe.** Drop can only *remove* loops; flip
  only *recolors* them. Neither ever *creates* a cycle. So loops enumerated on
  the unperturbed graph are a superset of every draw's loops — each baseline
  loop has a stable identity to aggregate against, with no cross-draw loop
  matching.
- **Certain graph collapses to the point estimate.** With every edge at
  confidence 5 (or `base = 0`), all `p = 0`: `existence_prob = 1`, `std = 0`,
  and `mean` equals the existing `leverage_scores` / `classify_loops` output.
  This is the regression anchor.

## API

One new public function in `sespy/network.py`. The existing point-estimate
functions (`leverage_scores`, `classify_loops`, `feedback_loops`) are left
**byte-for-byte unchanged** — zero regression risk for their six readers.

```python
def uncertainty_scores(
    isa: IsaData,
    *,
    n_samples: int = 500,
    seed: int | None = None,
    base: float = 0.5,
    max_length: int = 6,
    max_loops: int = 50,
    contested_band: tuple[float, float] = (0.2, 0.8),
) -> dict:
    """Monte-Carlo leverage & loop uncertainty under edge drop + sign-flip."""
```

A single function (not two) because centrality and loop enumeration both run
**per draw**, and both outputs must come from the **same** perturbed draws to be
mutually consistent. A private generator does the perturbation once per draw and
both aggregations consume it:

```python
def _perturbed_connections(isa, base, rng) -> list[Connection]:
    """One draw: per edge, drop with p(conf) and/or flip polarity with p(conf)."""
```

`rng = np.random.default_rng(seed)` (matches the existing Monte Carlo style in
`dynamics.py::state_shift_monte_carlo`). `seed=None` → nondeterministic;
an int → reproducible (used by tests).

## Output shape

```python
{
  "n_samples": 500,
  "leverage": {                          # one row per node id
     "<id>": {"mean": float, "ci_low": float, "ci_high": float, "std": float},
     ...
  },
  "loops": [                             # one row per BASELINE loop
     {"id": "L001", "nodes": [...], "path": "A → B → C → A",
      "existence_prob": float,           # fraction of draws the loop survives
      "reinforcing_prob": float,         # P(Reinforcing | exists); 0.0 if never exists
      "balancing_prob": float,           # 1 − reinforcing_prob when it exists else 0.0
      "contested": bool},                # reinforcing_prob within contested_band
     ...
  ],
}
```

- **CIs are 95% percentile intervals** (2.5 / 97.5) over the resampled values —
  robust on the skewed z-score composite, no Gaussian assumption.
- Per draw, leverage is the composite z-score recomputed on the perturbed graph;
  the per-node arrays are reduced to mean / percentiles / std at the end.
- `reinforcing_prob` / `balancing_prob` are conditioned on existence; a loop that
  never survives reports `existence_prob = 0` and both polarity probs `0.0`,
  `contested = False`.
- `contested` is the headline signal: polarity probability sitting in the
  uncertain middle band means the loop's reinforcing/balancing character is not
  robust to rater uncertainty.

## UI surfacing

Off-by-default toggle in **both** modules; a single `uncertainty_scores` call
per module feeds its table so leverage CIs and loop probabilities a user sees are
computed from the *same* draws.

### Leverage Points (`modules/analysis_leverage.py`)
- Sidebar: a checkbox "Show uncertainty (Monte Carlo)" + an `n_samples` numeric
  input (default 500).
- When on: append a CI column (e.g. `mean ± half-width`, or `[ci_low, ci_high]`)
  to `leverage_table`, and flag nodes whose CI straddles zero (ranking unstable).
- When off: unchanged — renders the cheap `leverage_scores` point estimate.

### Loop Analysis (`modules/analysis_loops.py`)
- Same toggle + `n_samples` input.
- When on: add `existence %` and `reinforcing % / balancing %` columns to
  `loops_table`, plus a **"contested"** badge for contested loops.
- When off: unchanged.

### i18n
All new strings (toggle label, column headers, "contested", "unstable") go
through `t()` with keys added across all 9 languages in
`sespy/translations/core.json`, consistent with the quadrant / median-toggle /
delay-loop work.

## Performance

The per-draw cost is centrality + loop enumeration. The toggle is **off by
default**, so the expensive path is only taken on explicit opt-in. Sample graphs
are small (tens of nodes), so `n_samples=500` is snappy on the target laptop
(16 GB, no GPU); `n_samples` is user-tunable for larger graphs.

## Testing

Golden-value and property unit tests in `tests/test_network.py`:

- **Regression anchor:** all-confidence-5 graph (or `base=0`) →
  `uncertainty_scores` leverage `mean` matches `leverage_scores`; every
  `existence_prob == 1.0`; loop polarity probs match `classify_loops`
  (reinforcing→1.0 / balancing→0.0); all `std == 0`.
- **Both channels live:** test the private `_perturbed_connections(isa, base, rng)`
  generator directly — over many draws on a confidence-1 graph, assert that some
  edges drop *and* some edges flip polarity, and that on a confidence-5 graph
  neither ever happens. (Validates both Bernoulli channels fire, governed by the
  single `base` knob; no per-channel toggle exists by design.)
- **Channel → output mapping:** on a graph with edges but no cycles, drops move
  leverage CIs while `loops` stays empty; on a graph whose only structural
  variation is a flippable 2-cycle of high-confidence-except-one edges, loop
  polarity probs move. (Validates drop→leverage and flip→polarity routing without
  needing to disable a channel.)
- **Determinism:** same `seed` → identical output; different `seed` → different.
- **Monotonicity:** lower confidence on a pivotal edge widens its CI / lowers its
  loop's `existence_prob`.
- **Edge cases:** empty graph → `{"n_samples": N, "leverage": {}, "loops": []}`;
  no cycles → empty `loops`; self-loops and dangling refs skipped as elsewhere.
- **Contested band:** a hand-constructed near-50/50 polarity loop reports
  `contested = True`; a robust loop reports `False`.

i18n test: new keys present in all 9 languages (existing `tests/test_i18n*`
pattern). e2e: toggle on in each module, assert the new columns / contested badge
render (existing Playwright pattern).

## Out of scope (YAGNI)

- Weighting centrality by `strength × confidence` (would change the R-parity
  point estimate of `leverage_scores` — deliberately avoided).
- Separate drop vs flip probability knobs.
- Resampling into the quadrant / metrics / simplify modules (separate features).
- Persisting MC results to the project file.
