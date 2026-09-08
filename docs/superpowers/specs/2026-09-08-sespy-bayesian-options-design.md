# Bayesian options for SESPy — design

**Origin:** owner request 2026-09-08 after a check of the weekly literature
alerts (`LITERATURE/`): no weekly file has ever recommended Bayesian
modelling for SES, and nothing in `sespy/` is Bayesian. The closest existing
machinery is Monte-Carlo edge perturbation (`uncertainty_scores`) and a
confidence-weighted-mean rater consensus (`recompute_consensus`). The owner
asked for both of the following as *options*, i.e. opt-in, not replacements.

**Status:** design approved in conversation 2026-09-08. Implementation plan
not yet written.

---

## What this is

Two independent, opt-in features:

- **Option A — Bayesian multi-rater consensus.** Conjugate posteriors over a
  connection's per-rater ratings (Beta for polarity, Dirichlet for strength),
  shown in Rate Connections beside the existing consensus and optionally fed
  into `uncertainty_scores` as the sign-flip probability.
- **Option B — Path-set Bayesian belief network (BBN).** For a chosen source
  and target, build a discrete BBN over the acyclic causal paths between them
  (reusing `causal_paths`), derive every CPT from existing strength ×
  confidence × polarity scores by noisy-OR, and answer forward ("push the
  source high, what happens downstream?") and diagnostic ("the target is
  high, what does that say about the source?") queries by exact inference.

## Decisions (made by the owner, 2026-09-08)

| # | Decision | Rationale |
|---|---|---|
| 1 | BBN covers only the source→target path set, never the whole CLD | CLDs have feedback loops; a BBN must be a DAG. Cutting edges across the whole diagram would misrepresent it, and a dynamic two-slice BN doubles the model and is hard for stakeholders to read. The path set is a question practitioners already ask via the causal-path tracer. It is usually acyclic, but not always (see `path_set_dag`); the rare local cuts it needs are reported, not hidden. |
| 2 | CPTs are derived from existing scores; no CPT editor | Stakeholders do not fill conditional probability tables. Derivation keeps the feature usable on every existing project with no new data entry. |
| 3 | Bayesian consensus is an opt-in toggle beside the stored consensus | `recompute_consensus` remains the sole writer of the stored scalars; projects on disk are untouched. Blast radius stays inside the toggle. |
| 4 | Inference engine: pgmpy variable elimination, as an optional extra `sespy[bayes]` | Exact; the query itself is ~0.1 s on path-set graphs (tens of nodes), but the first call per server process pays the pgmpy import (seconds, or 35–65 s when torch is installed, as in the `shiny` env), so the UI runs it in an extended task. Already installed in the `shiny` env. Optional so the pip/CI library layer stays installable without it, like the `pdf` extra. PyMC rejected: sampling is overkill for binary noisy-OR nodes and heavy on the 16 GB / no-GPU target machine. Option A needs no library (closed-form conjugate updates). |

---

## Option A — Bayesian multi-rater consensus

### Library (`sespy/network.py`, beside `recompute_consensus`)

Ratings weight the update by rater confidence: a rating with confidence
`c ∈ [1,5]` contributes a pseudo-count of `w = c / 5` (confidence 5 = one
full observation, confidence 1 = one fifth). All functions are pure and
never mutate the connection.

```python
def polarity_posterior(connection, *, prior: tuple[float, float] = (1.0, 1.0)) -> dict:
    """Beta posterior for P(polarity == '+').

    alpha = prior[0] + Σ w_i·[r_i == '+'];  beta = prior[1] + Σ w_i·[r_i == '-'].
    Returns {"p_plus": alpha/(alpha+beta), "ci_low", "ci_high" (95% equal-tailed
    credible interval via scipy.stats.beta.ppf), "alpha", "beta", "n": len(ratings)}.
    No ratings -> the prior (p_plus 0.5, interval (0.025, 0.975), n 0)."""

def strength_posterior(connection, *, prior: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> dict:
    """Dirichlet posterior over (weak, medium, strong).

    alpha_k = prior_k + Σ w_i·[rank(r_i) == k].
    Returns {"mean": {"weak": .., "medium": .., "strong": ..}, "map": <strength label
    of the largest mean; ties by rank order weak<medium<strong>, "alpha": (...), "n"}."""

def bayesian_consensus(connection):
    """Copy of `connection` with polarity/strength/confidence set to posterior
    values. polarity = '+' iff p_plus >= 0.5; strength = strength_posterior MAP;
    confidence = round(1 + 4 * (1 - width)) clamped [1,5], where width is the
    polarity credible-interval width (narrow interval -> high confidence).
    delay is unchanged (mode is kept, as in recompute_consensus). No ratings ->
    equivalent copy. Never writes to the stored project."""

def bayesian_contested(connection, *, band: tuple[float, float] = (0.2, 0.8)) -> bool:
    """True when n >= 2, the raters are NOT unanimous in sign, AND the polarity
    credible interval straddles 0.5 — a disagreement the posterior cannot
    resolve. Unanimity short-circuits to False: with the flat prior 2–4
    unanimous confidence-5 raters still straddle 0.5, and that is 'sign not
    yet established', not a dispute. A lone dissenter among many (12 '+' vs
    1 '-') is discounted: the interval clears 0.5, so not contested."""
```

`uncertainty_scores` gains `flip_mode: Literal["confidence", "posterior"] = "confidence"`.
Under `"posterior"`, `_perturbed_connections` uses as per-edge flip probability
the posterior probability that the STORED sign is wrong: `1 - p_plus` for a
stored '+', `p_plus` for a stored '-' (the stored sign is an unweighted
majority from `recompute_consensus`, or comes from a file, so it can disagree
with the confidence-weighted posterior mode; such an edge then flips more
often than not). The drop probability is unchanged (the posterior says nothing
about existence). Edges without ratings fall back to `_perturb_prob` so a
partially rated model still behaves. A new private `_flip_prob(c, base, flip_mode)`
is the single place this choice lives.

Existing tests for `recompute_consensus`, `uncertainty_scores` (default mode)
and the contested-edges view must pass unchanged.

### UI (`sespy/modules/rate_connections.py`)

- New `ui.input_checkbox("bayesian", t("rate.bayesian"), value=False)` next to
  `contested_only`.
- When on, the connections table gains columns `P(+)` (formatted
  `0.83 [0.61–0.96]`) and `strength*` (the Dirichlet MAP with its mean
  probability, e.g. `strong 0.62`), and `disagreement` is computed from
  `bayesian_contested` instead of `connection_disagreement(...)["polarity_contested"]`.
  The `contested_only` filter and `contested_count` follow the same switch:
  `displayed_pairs` gains a `bayesian: bool` keyword, pure and unit-tested.
- The stored consensus scalars are never written under the toggle; the
  small-print legend gets one more line explaining the posterior columns.
- The Loop Analysis uncertainty block gets a matching
  `ui.input_checkbox("flip_posterior", t("uncertainty.flip_posterior"))` that
  passes `flip_mode="posterior"`. Any change to it invalidates the cached
  uncertainty result (the "invalidate on every feeding input" rule).

New i18n keys (inserted before `help.body` in each `core.json`):
`rate.bayesian`, `rate.p_plus`, `rate.strength_post`, `rate.bayesian_legend`,
`uncertainty.flip_posterior`, plus the Option B keys listed below.

---

## Option B — Path-set BBN

### Library (new `sespy/bayes.py`)

pgmpy is imported lazily inside the functions. `build_path_bbn` raises
`BayesUnavailable(ImportError)` with the install hint
`pip install "sespy[bayes]"` / `micromamba install -n shiny pgmpy` when it is
missing; everything else in `sespy` continues to import without pgmpy.

```python
LEAK: float = 0.05          #: P(child high | all parents low)
STRENGTH_LINK = {"weak": 0.30, "medium": 0.55, "strong": 0.80}

def link_probability(connection) -> float:
    """Noisy-OR link strength for one edge: STRENGTH_LINK[strength] scaled by
    confidence, q = s * (0.5 + 0.5 * (conf - 1) / 4). Confidence 5 -> s;
    confidence 1 -> s/2. Clamped to [0.01, 0.99]. Pure."""

def path_set_dag(isa, source, target, *, max_length=8, max_paths=100) -> dict:
    """Union of the edges of causal_paths(...)['paths'] as a node/edge set,
    made acyclic. Returns {"nodes": [...], "edges": [(u, v, connection)],
    "cut_edges": [(u, v)], "paths": the causal_paths rows still intact after
    cuts (n_paths in the UI counts these), "truncated": bool}. Empty shape
    when causal_paths is empty.

    The union of simple source->target paths is NOT always a DAG (paths
    s->a->b->t and s->b->a->t together contain a<->b). When the union has
    cycles, drop edges greedily: while nx.find_cycle succeeds, remove the
    edge of that cycle with the lowest link_probability (ties: lexicographic
    (u, v) so the result is deterministic) and record it in cut_edges. Greedy,
    not minimal: a shared edge on two cycles may be spared in favour of two
    weaker ones; a node whose in-edges were all cut becomes a 0.5-prior root.
    Cuts are local to the question asked, are expected to be rare (none on
    any sample-project pair), and are always reported in the UI summary —
    never silent. Asserted DAG in tests."""

def build_path_bbn(isa, source, target, *, max_length=8, max_paths=100):
    """pgmpy DiscreteBayesianNetwork over path_set_dag. Every node is binary
    (state 0 = low, 1 = high). The source (no parents inside the DAG) gets
    P(high) = 0.5. Each other node's CPT is noisy-OR over its parents:
      P(high | parents) = 1 - (1 - LEAK) * Π_{active parents} (1 - q_i)
    where a parent is 'active' when it is high and the edge is '+', or low
    and the edge is '-' (a negative edge pushes the child high when the
    parent is low, i.e. noisy-OR on the complement). Parents inside the
    path set only; edges from nodes outside it are ignored (they are not
    part of the question). Returns (model, dag_info)."""

def query_path_bbn(model, dag_info, evidence: dict[str, int]) -> dict:
    """Variable elimination. Returns per node
    {"p_high", "baseline" (no-evidence marginal), "delta"} for every node in
    the path set, sorted by |delta| descending, plus {"evidence", "n_paths",
    "truncated"}. Evidence nodes report p_high = the evidence value."""
```

Forward query = `{source: 1}`; diagnostic query = `{target: 1}`. Both are
plain evidence dicts, so no separate code path.

Determinism: variable elimination is exact; results are reproducible with no
seed. Path-set size is bounded by `max_paths` (default 100) and `max_length`
(8), inherited from `causal_paths`; a truncated path set is reported, never
hidden.

### UI (`sespy/modules/analysis_intervention.py`)

A new block under the diffusion section of the Intervention card (the card
already owns source pickers and the causal-path tracer pattern):

- Sidebar: `ui.h5(t("bbn.title"))`, `ui.output_ui("bbn_controls")` rendering
  `bbn_source` and `bbn_target` selects with the same isolate()-restore
  pattern as `diffusion_controls`; `ui.input_radio_buttons("bbn_direction",
  ...)` with `forward` / `diagnostic`; `ui.input_action_button("run_bbn", ...)`.
- Main: `ui.output_ui("bbn_summary")` (n paths, truncated flag, cut edges if any, or the
  install hint when pgmpy is missing, or "no path" when the path set is
  empty) and `ui.output_data_frame("bbn_table")` with columns
  `id, label, type, baseline, posterior, delta`, delta colour-coded by sign
  through the existing data-frame styling helper if one exists, else plain.
- A `_bbn_result` reactive value, reset on `isa_change` and on any change of
  the three inputs (same invalidation discipline as diffusion). The build and
  query run in a `reactive.extended_task` on a worker thread with a
  generation counter (the Loop Analysis uncertainty pattern): pgmpy 1.1
  imports torch when installed, measured 35–65 s on the first import per
  server process, and a synchronous effect would freeze every session of
  that worker. A `_COMPUTING` sentinel shows a "computing" line meanwhile.
- Help panel: served by the contextual Help offcanvas via manual section 19
  (Intervention), which the release extends; there is no per-feature help
  slot, so no `help.bbn` key.

New i18n keys: `bbn.title`, `bbn.source`, `bbn.target`, `bbn.direction`,
`bbn.forward`, `bbn.diagnostic`, `bbn.run`, `bbn.hint`, `bbn.computing`,
`bbn.no_path`, `bbn.unavailable`, `bbn.summary` (with `n`, `source`,
`target`, `trunc` placeholders), `bbn.truncated`, `bbn.cut`,
`bbn.target_line`, `bbn.about_text`.

### Packaging

`pyproject.toml`: `bayes = ["pgmpy>=1.0"]` in optional-dependencies
(`DiscreteBayesianNetwork` was introduced in 1.0; the `shiny` env has 1.1.0);
README "Install it" gets one line. `deploy.sh` is unchanged: the laguna env
must gain pgmpy via `micromamba install -n shiny pgmpy` as a one-off before
the release that ships this (record in the release notes; verify with
`python3 -s` as the shiny user, per the v1.8.2 outage lesson).

---

## Testing

Unit (`tests/test_bayes_consensus.py`, `tests/test_bayes.py`):

- Beta posterior against hand-computed alpha/beta for: no ratings (prior),
  one confidence-5 '+' rating (alpha 2, beta 1, p_plus 2/3), mixed
  confidences (weights 0.2 … 1.0), and the credible-interval endpoints
  matching `scipy.stats.beta.ppf` directly.
- Dirichlet MAP tie-breaking and the no-ratings prior.
- `bayesian_consensus` returns an equivalent copy with no ratings; never
  mutates; confidence mapping endpoints (width→1 gives 1, width→0 gives 5).
- `bayesian_contested` false for a single rating; true for 1×'+' vs 1×'-';
  false for 2–4 unanimous confidence-5 raters; false for 12×'+' vs 1×'-'.
- `uncertainty_scores(flip_mode="posterior")`: the per-edge flip probability
  is the posterior probability the stored sign is wrong, which with the
  Beta(1,1) prior never reaches zero (three unanimous confidence-5 raters
  still leave 0.2) but falls monotonically with the number of agreeing
  raters; an edge stored '+' by tie-break whose posterior is 0.375 flips
  with 0.625; unrated edges fall back to the confidence heuristic; the
  default mode is bit-for-bit unchanged.
- `link_probability` endpoints and clamping.
- `path_set_dag` is a DAG on the sample project for several (s, t) pairs,
  returns the empty shape for unknown / equal endpoints, and on the
  four-node s→a→b→t / s→b→a→t fixture cuts exactly one edge (the weaker of
  a→b, b→a) and reports it in `cut_edges`.
- Noisy-OR CPT rows on a two-parent node (one '+', one '-') checked
  numerically against the formula.
- Forward and diagnostic queries on a three-node chain A→B→C: P(C high | A
  high) > baseline; P(A high | C high) > 0.5; with a '-' edge the delta
  flips sign.
- `BayesUnavailable` raised when `pgmpy` import is monkeypatched away, and
  `import sespy.network` succeeds without pgmpy.

E2E (Playwright, namespaced selectors, one script per toggle):

- Rate Connections: tick the Bayesian checkbox, assert the `P(+)` header
  appears and the stored consensus of a rated connection is unchanged
  after toggling off.
- Intervention: pick source/target on the sample project, run forward, assert
  the table renders rows and the summary reports a path count.

Gate: full unit suite + full e2e (never `-k "not e2e"`), with no other heavy
process running on the machine.

---

## Out of scope

- CPT editing UI, continuous nodes, dynamic (time-sliced) BNs, whole-CLD
  BBNs, learning CPTs from data, and any change to the stored consensus
  writer. Each would be a separate design.
