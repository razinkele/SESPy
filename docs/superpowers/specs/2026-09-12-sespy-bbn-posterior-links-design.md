# Path-set BBN: link probabilities from rater posteriors — design

**Origin:** owner request 2026-09-12 to continue the Bayesian work after
v1.11.0. Of four candidate directions (posterior-driven CPTs, BBN
intervention ranking, two-slice dynamic BN, polish of deferred minors) the
owner picked posterior-driven CPTs: unify Option A (rater posteriors,
v1.10.0) and Option B (path-set BBN, v1.10.0 + v1.11.0) so rater
disagreement is visible in inference.

**Status:** design approved in conversation 2026-09-12. Implementation
plan not yet written.

---

## What this is

An opt-in `link_mode="posterior"` for the path-set belief network. Today
every conditional probability table is derived from the stored scalars of a
connection (polarity, strength, confidence). Under the new mode a *rated*
connection instead contributes

- **P(+)**: the Beta posterior mean from `polarity_posterior` (Option A), and
- **q**: the expected link strength under the Dirichlet posterior, scaled by
  the posterior confidence,

and the noisy-OR treats the sign as uncertain: a parent pushes the child
high with probability `q · P(+)` when it is high and `q · (1 − P(+))` when it
is low. With a certain sign (P(+) ∈ {0, 1}) this is exactly today's formula,
so the default mode is bit-identical. Unrated connections fall back to the
stored scalars, the same rule `uncertainty_scores(flip_mode="posterior")`
uses, so a partially rated model still behaves.

## Decisions (made by the owner, 2026-09-12)

| # | Decision | Rationale |
|---|---|---|
| 1 | Opt-in toggle, default off; stored mode unchanged | Same blast-radius discipline as the v1.10.0 toggles; every existing golden and e2e assertion stays valid. |
| 2 | Sign enters the noisy-OR as a mixture, not as a hard posterior-mode sign | A 1-vs-1 split should weaken the link symmetrically, not pick a side; `bayesian_consensus`'s hard sign is a display convenience, inference should carry the uncertainty. |
| 3 | Unrated edges use stored values, and the summary says how many edges were rated | On the sample project (no ratings) the toggle changes nothing; without the line a user cannot tell whether it worked. |
| 4 | The cycle cut uses the posterior `q` too | One consistent notion of link strength per query; a different cut is possible and is reported, never hidden. |

---

## Library (`sespy/bayes.py`)

```python
LinkMode = Literal["stored", "posterior"]

def link_params(connection, link_mode: LinkMode = "stored") -> tuple[float, float]:
    """(q, p_plus) for one edge.

    "stored": q = link_probability(connection); p_plus = 1.0 if polarity is
    '+' else 0.0 (any other polarity counts as '+', as noisy_or_p_high did).
    "posterior", when connection.ratings is non-empty:
      pol = network.polarity_posterior(connection); p_plus = pol["p_plus"];
      st  = network.strength_posterior(connection);
      s_bar = Σ_k st["mean"][k] · STRENGTH_LINK[k]           (expected strength)
      width = pol["ci_high"] - pol["ci_low"];
      conf  = max(1, min(5, round(1 + 4·(1 - width))))       (as bayesian_consensus)
      q = clamp(s_bar · (0.5 + 0.5·(conf - 1)/4), 0.01, 0.99)  (same scaling as link_probability)
    "posterior" with no ratings: identical to "stored". Pure."""

def noisy_or_p_high(states, parents, *, link_mode: LinkMode = "stored") -> float:
    """P(child high | parent states) with an uncertain sign per parent:
    a_i = p_plus_i if state_i == 1 else 1 - p_plus_i
    P(high) = 1 − (1 − LEAK) · Π_i (1 − q_i · a_i)
    With p_plus ∈ {0, 1} this equals the v1.10.0 formula exactly. Pure."""
```

`path_set_dag(..., link_mode="stored")`: the greedy cycle cut ranks edges by
`link_params(conn, link_mode)[0]` instead of `link_probability`. Ties and the
lexicographic order are unchanged. The `causal_paths` rows and their
compound polarity still come from the stored sign (they describe the
diagram, not the inference).

`model_from_dag(info, *, link_mode="stored")`, `build_path_bbn(..., link_mode=)`
and `attribute_paths(info, evidence, focus, *, link_mode=)` pass it through;
`attribute_paths` builds its chain models in the same mode as the joint
model. `link_probability` and `query_path_bbn` are unchanged.

`model_from_dag` additionally records on the returned model nothing; the
count the UI needs is computed by a small pure helper:

```python
def rated_edge_count(info) -> tuple[int, int]:
    """(rated, total) over info["edges"]: rated = edges whose Connection has
    at least one rating. Pure."""
```

Determinism and caps are unchanged. The worker cost is unchanged (two
closed-form posteriors per edge, tens of edges).

---

## UI (`sespy/modules/analysis_intervention.py`)

- Sidebar, directly after the `bbn_direction` radio and before the run
  button: `ui.input_checkbox("bbn_posterior", t("bbn.posterior_links"), value=False)`.
  It joins `_invalidate_bbn` (invalidate on every feeding input).
- `_run_bbn` reads it (try/except like the others; missing → False) and
  passes `link_mode = "posterior" if on else "stored"` to `_bbn_task`.
- `_bbn_work(isa, src, tgt, direction, high, low, link_mode)`: `path_set_dag`,
  `model_from_dag` and `attribute_paths` all receive `link_mode`; the result
  gains `r["link_mode"]` and `r["rated"], r["total"] = rated_edge_count(info)`.
- `bbn_summary`: when `r["link_mode"] == "posterior"`, one muted line after
  the evidence line: `t("bbn.posterior_line", rated=…, total=…)`.
- Everything else (pickers, tables, errors) is unchanged.

i18n (`sespy/translations/core.json`, nine languages, inserted after
`bbn.low`, before `help.body`): `bbn.posterior_links` ("Link probabilities
from rater posteriors"), `bbn.posterior_line` ("Links from rater posteriors:
{rated} of {total} rated; unrated links use stored values").
`tests/test_i18n.py::test_bbn_keys_present` gains both keys and the
placeholder test gains `bbn.posterior_line: {rated, total}`.

Docs: `docs/MANUAL.md` section 19 Controls gains the checkbox; section 43
"Path-set belief network" paragraph gains two sentences (rated links can
take their sign probability and expected strength from the rater posteriors
of section 43's first paragraph, the sign then enters the noisy-OR as a
mixture; unrated links keep the stored values and the summary says how many
were rated). `CHANGELOG.md` `## [1.12.0]`, README "What's new in v1.12.0",
`__version__`/`pyproject` 1.12.0, manual version line. No new screenshot;
the existing captures do not show the checkbox and need no rerun.

---

## Testing

Unit (`tests/test_bayes.py`; pgmpy tests keep `@needs_pgmpy`):

- `link_params` stored: equals `(link_probability(c), 1.0)` for '+' and
  `(…, 0.0)` for '-'; posterior with no ratings identical to stored.
- Posterior with three unanimous confidence-5 '+' strong raters:
  `p_plus = 4/5` (Beta(4,1) mean), `s_bar` close to STRENGTH_LINK["strong"]
  weighted by the Dirichlet mean (4/6·0.80 + 1/6·0.55 + 1/6·0.30), `q` uses the
  width-derived confidence; hand-computed values asserted to 1e-6.
- One '+' vs one '-' rating (confidence 5 each): `p_plus == 0.5`, and
  `noisy_or_p_high((1,), …, link_mode="posterior") == noisy_or_p_high((0,), …)`
  (symmetric activation).
- Mixture reduces to the old formula: for every state vector of the
  existing two-parent fixture, `noisy_or_p_high(states, parents)` equals
  `noisy_or_p_high(states, parents, link_mode="posterior")` when the parents
  have no ratings, and equals the v1.10.0 closed form.
- Chain A→B→C with B←A rated 1-vs-1: forward delta at C under posterior mode
  is smaller in magnitude than under stored mode.
- Sample CPD goldens (`_SAMPLE_CPDS`) hold with `link_mode="posterior"` (no
  ratings on the sample); `rated_edge_count` on D001→GB01 is `(0, 7)`.
- Cycle-cut fixture from `test_path_set_dag_cuts_the_weaker_edge_of_a_union_cycle`
  with ratings added so the posterior reverses which of a→b / b→a is weaker:
  stored mode cuts b→a, posterior mode cuts a→b; both reported.
- `BayesUnavailable` unaffected; `import sespy.bayes` still pgmpy-free.

E2E (`tests/test_intervention_e2e.py`, id-scoped): after the existing
forward run and before the evidence block, tick `#intervention-bbn_posterior`,
wait for "not computed" (invalidation), run, wait for "causal paths", assert
the summary contains "Links from rater posteriors: 0 of 7 rated" and the
target line still contains `(-0.05)`; untick, wait for "not computed", run,
wait for "causal paths" so the evidence block that follows starts from the
same state as today. (Path-set edges for D001→GB01: D001→A001, A001→P001,
P001→MPF1, MPF1→ES01, MPF1→ES03, ES01→GB01, ES03→GB01.)

Gate: full unit suite + full e2e, nothing heavy alongside. Release v1.12.0:
bump, gates, tag, push, deploy, live probe, MosaicSES verify_live.

---

## Out of scope

Posterior-driven `LEAK`, per-rater networks, learning link strengths from
data, changing the stored consensus writer, and the other two candidate
directions (BBN intervention ranking, two-slice dynamic BN).
