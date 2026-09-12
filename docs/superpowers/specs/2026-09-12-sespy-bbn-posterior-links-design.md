# Path-set BBN: link probabilities from rater posteriors — design

**Origin:** owner request 2026-09-12 to continue the Bayesian work after
v1.11.0. Of four candidate directions (posterior-driven CPTs, BBN
intervention ranking, two-slice dynamic BN, polish of deferred minors) the
owner picked posterior-driven CPTs: unify Option A (rater posteriors,
v1.10.0) and Option B (path-set BBN, v1.10.0 + v1.11.0) so rater
disagreement is visible in inference.

**Status:** design approved in conversation 2026-09-12; revised the same
day after two parallel reviews (consistency/feasibility, testability with
computed numbers). Revision decisions: the sign mixture is documented as the
exact marginalisation of a latent sign per link (with its consequence at
P(+) = 0.5 stated); the interval-width confidence factor is dropped from
`q` (it double-counted rater confidence); unknown polarities stay inactive;
parameters are resolved once per edge; the rated-edge count is inlined
with its post-cut domain stated. Implementation plan:
`docs/superpowers/plans/2026-09-12-bbn-posterior-links.md`.

---

## What this is

An opt-in `link_mode="posterior"` for the path-set belief network. Today
every conditional probability table is derived from the stored scalars of a
connection (polarity, strength, confidence). Under the new mode a *rated*
connection instead contributes

- **P(+)**: the Beta posterior mean from `polarity_posterior` (Option A), and
- **q**: the expected link strength under the Dirichlet posterior,
  `s_bar = Σ_k mean_k · STRENGTH_LINK[k]`,

and the noisy-OR treats the sign as a latent variable per link: a parent
pushes the child high with probability `q · P(+)` when it is high and
`q · (1 − P(+))` when it is low. This is the exact marginalisation of an
independent Bernoulli sign per link out of the v1.10.0 noisy-OR (each sign
variable has exactly one child, so marginalising it leaves a valid CPT), and
with a certain sign (P(+) ∈ {0, 1}) it is bit-identical to today's formula.

Two consequences the manual must state:

- **A contested link carries no information.** At P(+) = 0.5 the two parent
  states give the same activation, so the child becomes independent of that
  parent (forward delta exactly 0) while the always-on `q/2` term still
  feeds its marginal. Rater disagreement therefore *severs* a link for
  inference rather than halving it; baselines under posterior mode are not
  comparable with stored-mode baselines.
- **Few raters mean shrunk links.** The Dirichlet mean sits near the flat
  prior until ratings accumulate: one confidence-5 "strong" rater gives
  `s_bar ≈ 0.49` against a stored 0.80; three unanimous give 0.675. Rater
  confidence enters once, as the pseudo-count weight of `_rating_weight`;
  no second confidence factor is applied to `q` (the v1.10.0 stored formula
  scales by the *stored* confidence, which is a different quantity).

Unrated connections fall back to the stored scalars, the same rule
`uncertainty_scores(flip_mode="posterior")` uses, so a partially rated model
still behaves.

## Decisions (made by the owner 2026-09-12; revision decisions by the controller)

| # | Decision | Rationale |
|---|---|---|
| 1 | Opt-in toggle, default off; stored mode unchanged | Same blast-radius discipline as the v1.10.0 toggles; every existing golden and e2e assertion stays valid. |
| 2 | Sign enters the noisy-OR as a mixture (latent sign marginalised), not as a hard posterior-mode sign | Exact under the model; a 1-vs-1 split then correctly carries no directional information instead of picking a side. `bayesian_consensus`'s hard sign stays a display convenience. |
| 3 | Unrated edges use stored values, and the summary says how many edges were rated | On the sample project (no ratings) the toggle changes nothing; without the line a user cannot tell whether it worked. |
| 4 | The cycle cut uses the posterior `q` too | One consistent notion of link strength per query; a different cut is possible and is reported, never hidden. |
| 5 | `q = s_bar`, no interval-width confidence factor (revision) | Rater confidence is already the pseudo-count weight in both posteriors; scaling again by the credible-interval width would count it twice and halve every rated link with fewer than four raters. |
| 6 | Unknown polarity (neither '+' nor '−') is inactive in both modes (revision) | That is what `noisy_or_p_high` does today; any two-valued P(+) would change it. Keeps stored mode bit-identical for every polarity value. |

---

## Library (`sespy/bayes.py`)

```python
LinkMode = Literal["stored", "posterior"]

def link_params(connection, link_mode: LinkMode = "stored") -> tuple[float, float]:
    """(q, p_plus) for one edge.

    "stored": q = link_probability(connection) and p_plus = 1.0 for polarity
    '+', 0.0 for '-'. Any other polarity returns (0.0, 0.0) — q of exactly 0,
    bypassing link_probability's [0.01, 0.99] clamp — so the edge is inactive
    in both parent states, as noisy_or_p_high has always treated it.
    "posterior", when connection.ratings is non-empty:
      p_plus = network.polarity_posterior(connection)["p_plus"]
      mean   = network.strength_posterior(connection)["mean"]
      s_bar  = Σ_k mean[k] · STRENGTH_LINK[k]
      q      = clamp(s_bar, 0.01, 0.99)
    "posterior" with no ratings: identical to "stored". Pure; ~3 ms per
    rated edge (two scipy beta.ppf calls), microseconds otherwise."""

def _noisy_or(states, params) -> float:
    """P(child high | parent states) from resolved (q, p_plus) pairs:
    a_i = p_plus_i if state_i == 1 else 1 - p_plus_i
    P(high) = 1 − (1 − LEAK) · Π_i (1 − q_i · a_i). Pure."""

def noisy_or_p_high(states, parents, *, link_mode: LinkMode = "stored") -> float:
    """Convenience wrapper over _noisy_or for (parent_id, Connection)
    pairs — resolves link_params per call. With p_plus ∈ {0, 1} it equals
    the v1.10.0 formula exactly (asserted on the two-parent fixture). Pure."""
```

Thread-through, all keyword-only with default `"stored"`:

- `path_set_dag(..., link_mode=)`: the greedy cut ranks edges by
  `link_params(conn, link_mode)[0]`, resolved once per cycle iteration.
  Ties and lexicographic order unchanged. `causal_paths` rows and their
  compound polarity still come from the stored sign (they describe the
  diagram, not the inference); the node *set* is the same in both modes,
  only the topological order can differ.
- `model_from_dag(info, *, link_mode=)`: resolves `(q, p_plus)` once per
  in-edge and builds every CPT row through `_noisy_or` — two posteriors per
  edge, not per CPT cell.
- `build_path_bbn(..., link_mode=)` (API pass-through; the UI does not call
  it) and `attribute_paths(info, evidence, focus, *, link_mode=)`, whose chain
  models are built in the same mode as the joint model.
- `link_probability` and `query_path_bbn` are unchanged.

Rated-edge count: no helper; `_bbn_work` computes
`rated = sum(1 for _, _, c in info["edges"] if c.ratings); total = len(info["edges"])`
over the edges still *in* the model. An edge removed by the cycle cut is not
counted (the `bbn.cut` line reports those).

---

## UI (`sespy/modules/analysis_intervention.py`)

- Sidebar, directly after the `bbn_direction` radio and before the run
  button: `ui.input_checkbox("bbn_posterior", t("bbn.posterior_links"), value=False)`.
  It joins the read tuple in `_invalidate_bbn`.
- `_run_bbn` reads `input.bbn_posterior()` directly (static sidebar UI like
  `bbn_direction`; no try/except needed) and passes
  `link_mode = "posterior" if on else "stored"`.
- `_bbn_task(isa, src, tgt, direction, high, low, link_mode, gen)` — the new
  argument goes before the trailing positional `gen`.
- `_bbn_work(isa, src, tgt, direction, high, low, link_mode)`: `path_set_dag`,
  `model_from_dag` and `attribute_paths` receive `link_mode`; the result gains
  `r["link_mode"]`, `r["rated"]`, `r["total"]`.
- `bbn_summary`: when `r["link_mode"] == "posterior"`, one muted line after
  the evidence line: `t("bbn.posterior_line", rated=…, total=…)`.
- The route table's `polarity` column keeps describing the stored diagram
  and can disagree in sign with a posterior-mode solo delta; the manual says
  so. Everything else is unchanged.

i18n (`sespy/translations/core.json`, nine languages, inserted after
`bbn.low`, before `help.body`): `bbn.posterior_links` ("Link probabilities
from rater posteriors"), `bbn.posterior_line` ("Links from rater posteriors:
{rated} of {total} rated; unrated links use stored values"). In
`tests/test_i18n.py`, `test_bbn_keys_present` gains both keys and
`test_bbn_evidence_placeholders_match_across_languages` gains
`"bbn.posterior_line": {"rated", "total"}` (it compares placeholder sets for
equality in every language).

Docs: `docs/MANUAL.md` section 19 Controls gains the checkbox; section 43
"Path-set belief network" paragraph gains four sentences: rated links can
take their sign probability and expected strength from the rater posteriors
(sign marginalised in the noisy-OR); a link whose raters split evenly
carries no information and baselines are not comparable across modes; few
raters mean links shrunk toward the mid strength; unrated links keep the
stored values, the summary counts the rated ones, and the route table's
polarity column is the diagram's sign while the delta is the inference's.
`CHANGELOG.md` `## [1.12.0]`, README "What's new in v1.12.0",
`__version__`/`pyproject` 1.12.0, manual version line. No new screenshot.

---

## Testing

Verified numbers (2026-09-12, final formula, env `shiny`; use
`math.isclose(abs_tol=1e-6)` unless marked exact):

| Fixture | Result |
|---|---|
| 3 unanimous conf-5 '+' strong raters | p_plus 0.8 (exact), Dirichlet mean (1/6, 1/6, 2/3), s_bar = q = 0.675; stored q 0.8 |
| 1 '+' vs 1 '−', strong, conf 5 | p_plus 0.5 (exact), q 0.65, activation high = low = 0.35875 |
| 2 '+' vs 1 '−', strong, conf 5 | p_plus 0.6, q 0.675 |
| Chain A→B→C (strong conf-5 '+' edges), A→B rated 1-vs-1, evidence {A:1} | stored dB 0.38, dC 0.2888; posterior dB 0.0, dC 0.0 (exactly); B baseline stored 0.43, posterior 0.35875 |
| Same chain, A→B rated 2-vs-1 | posterior dB 0.064125, dC 0.048735; `attribute_paths` single route: stored delta 0.2888, posterior 0.048735 |
| Cycle fixture with a→b rated (weak '+', weak '−') and b→a rated 3× strong '+' | a→b: stored q 0.8, posterior 0.45; b→a: stored 0.15, posterior 0.675; stored cut [("b","a")], posterior cut [("a","b")]; 3 paths and 5 edges either way, 1 rated edge left either way |
| Unknown polarity, strong conf 5, stored mode | P(high) = LEAK for both parent states |
| Sample D001→GB01 | 7 edges (A001→P001, D001→A001, ES01→GB01, ES03→GB01, MPF1→ES01, MPF1→ES03, P001→MPF1), 0 rated; `_SAMPLE_CPDS` bit-identical in posterior mode; forward GB01 delta −0.0503 |

Unit (`tests/test_bayes.py`; pgmpy tests keep `@needs_pgmpy`; `_chain`
gains a `ratings_ab=None` parameter):

- `link_params` stored: `(link_probability(c), 1.0)` for '+', `(…, 0.0)` for
  '−', `(0.0, 0.0)` for polarity "?"; posterior with no ratings identical to
  stored; the three rated cases from the table.
- Symmetric activation at 1-vs-1; the two-parent inline `parents` list of
  `test_noisy_or_two_parents_plus_and_minus` gives identical values in
  stored and posterior mode (no ratings) for all four state vectors, and
  `_noisy_or` with resolved params equals `noisy_or_p_high`.
- 1-vs-1 chain: dB and dC are 0 within 1e-9; 2-vs-1 chain: the posterior
  deltas from the table, and stored deltas unchanged.
- `attribute_paths(..., link_mode="posterior")` on the 2-vs-1 chain gives
  0.048735 vs 0.2888 stored (this is the only test that catches a dropped
  `link_mode` in the chain models).
- Cycle fixture: cut edges per mode, acyclic, `len(paths) == 3`; do not
  assert the `nodes` order.
- `build_path_bbn(link_mode=)` returns a model whose query equals
  `model_from_dag(info, link_mode=)`'s.
- Sample goldens hold in posterior mode; rated count `(0, 7)` on the sample
  and `(1, 5)` on the stored-cut cycle fixture (computed inline as the
  worker does).
- `import sespy.bayes` still pgmpy-free.

E2E (`tests/test_intervention_e2e.py`, id-scoped): insert after the
`assert n_paths == 2` that closes the forward-run checks and before the
`wait_for_selector("#intervention-bbn_low", state="attached")` line. Use
`page.check("#intervention-bbn_posterior")`, wait for "not computed", run,
wait for "causal paths", assert "Links from rater posteriors: 0 of 7 rated"
and `(-0.05)` in a new variable `post_text` (do not reassign `bbn_text`,
which the closing print reuses); `page.uncheck(...)`, wait for "not
computed", run, wait for "causal paths" so the evidence block that follows
starts from a computed forward result as today.

Gate: full unit suite + full e2e, nothing heavy alongside. Release v1.12.0:
bump, gates, tag, push, deploy, live probe, MosaicSES verify_live.

---

## Out of scope

Posterior-driven `LEAK`, per-rater networks, learning link strengths from
data, changing the stored consensus writer, and the other two candidate
directions (BBN intervention ranking, two-slice dynamic BN).
