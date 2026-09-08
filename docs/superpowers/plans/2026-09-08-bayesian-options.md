# Bayesian Options Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two opt-in Bayesian features to SESPy: conjugate rater posteriors in Rate Connections (with a posterior sign-flip mode for uncertainty scoring) and a noisy-OR path-set belief network in the Intervention panel.

**Architecture:** Option A is pure functions in `sespy/network.py` beside the existing consensus code (Beta/Dirichlet closed forms, scipy for the credible interval) plus a checkbox in Rate Connections and one in Loop Analysis. Option B is a new `sespy/bayes.py` that turns `causal_paths` output into a DAG, derives every CPT by noisy-OR from strength × confidence × polarity, and runs pgmpy variable elimination; pgmpy is imported lazily and is an optional extra. Nothing writes to the stored consensus scalars.

**Tech Stack:** Python 3.11, Shiny for Python 1.7, networkx, scipy, pandas, pgmpy ≥ 1.0 (optional extra `bayes`), pytest, Playwright standalone e2e scripts.

**Spec:** `docs/superpowers/specs/2026-09-08-sespy-bayesian-options-design.md`

## Global Constraints

- Run Python only via `micromamba run -n shiny python ...` / `micromamba run -n shiny pytest ...`; never create a venv, never `pip install`.
- Multi-line `python -c` breaks on this Windows shell: write scratch `.py` files if you need a probe.
- Unit gate: `micromamba run -n shiny pytest tests/ -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`
- E2E gate: `micromamba run -n shiny python tests/run_e2e.py` (full, never `-k "not e2e"`); kill any orphan server on port 8000 first; run nothing heavy alongside it.
- `sespy/translations/core.json`: keys live under `"translation"`; `help.body` is the LAST entry (no trailing comma) — insert new keys before it. Every key needs all nine languages: en, es, fr, de, lt, pt, it, no, el.
- `recompute_consensus` stays the SOLE writer of stored consensus scalars. No new function may write polarity/strength/confidence into `project_data`.
- pgmpy is imported only inside function bodies in `sespy/bayes.py`; `import sespy.network`, `import sespy.bayes` and every module import must succeed without pgmpy (`tests/test_no_deprecations.py` imports every module in a fresh interpreter).
- No DOIs in new docstrings in `network.py`/`dynamics.py` unless also added to Part IV of `docs/MANUAL.md` (`test_every_docstring_doi_is_in_the_references`).
- E2E selectors must be namespaced ids (`#rate-…`, `#intervention-…`), never bare `text=`.
- Commit after every task with the trailer:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01TXboKkAF84fXkFQWxURUBY
  ```
  Use the PowerShell tool (or a bash heredoc) for multi-line commit messages, never a PowerShell here-string inside the Bash tool.

---

## File map

| File | Responsibility |
|---|---|
| `sespy/network.py` (modify, near line 1313–1430) | Option A posteriors: `polarity_posterior`, `strength_posterior`, `bayesian_consensus`, `bayesian_contested`, `_flip_prob`; `displayed_pairs(..., bayesian=)`; `uncertainty_scores(..., flip_mode=)` |
| `sespy/bayes.py` (create) | Option B: `BayesUnavailable`, `LEAK`, `STRENGTH_LINK`, `link_probability`, `path_set_dag`, `noisy_or_p_high`, `build_path_bbn`, `query_path_bbn` |
| `sespy/modules/rate_connections.py` (modify) | Bayesian checkbox, posterior columns, contested switch |
| `sespy/modules/analysis_loops.py` (modify, lines 129–218) | `flip_posterior` checkbox feeding `uncertainty_scores` |
| `sespy/modules/analysis_intervention.py` (modify) | BBN block: controls, run, summary, table |
| `sespy/translations/core.json` (modify) | New keys |
| `pyproject.toml`, `README.md` (modify) | `bayes` extra |
| `docs/MANUAL.md`, `CHANGELOG.md`, `sespy/__init__.py` (modify) | Docs + version 1.10.0 |
| `tests/test_bayes_consensus.py` (create) | Option A unit tests |
| `tests/test_bayes.py` (create) | Option B unit tests |
| `tests/test_network.py`, `tests/test_i18n.py` (modify) | `displayed_pairs`, flip-mode, key-presence tests |
| `tests/test_rate_connections_e2e.py`, `tests/test_intervention_e2e.py` (modify) | e2e for each toggle |

---

### Task 1: Rater posteriors (Option A library)

**Files:**
- Modify: `sespy/network.py` — insert after `remove_rating` (ends ~line 1399)
- Test: `tests/test_bayes_consensus.py` (create)

**Interfaces:**
- Consumes: `Connection.ratings: list[Rating]`, `Rating.polarity/strength/confidence`, `_STRENGTH_RANK`, `_RANK_TO_STRENGTH` (existing, network.py ~1309).
- Produces:
  - `polarity_posterior(connection, *, prior=(1.0, 1.0)) -> dict` with keys `p_plus, ci_low, ci_high, alpha, beta, n`
  - `strength_posterior(connection, *, prior=(1.0, 1.0, 1.0)) -> dict` with keys `mean` (dict weak/medium/strong), `map` (str), `alpha` (tuple), `n`
  - `bayesian_consensus(connection) -> Connection` (copy)
  - `bayesian_contested(connection, *, band=(0.2, 0.8)) -> bool` (band unused for now; signature reserved)
  - `_rating_weight(rating) -> float`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bayes_consensus.py
"""Option A: conjugate rater posteriors (spec 2026-09-08-sespy-bayesian-options)."""
from __future__ import annotations

import math

import pytest
from scipy.stats import beta as _beta

from sespy import network
from sespy.data_structure import Connection, Rating


def _conn(*ratings):
    return Connection(source="A", target="B", polarity="+", strength="medium",
                      confidence=3, ratings=list(ratings))


def test_polarity_posterior_no_ratings_is_prior():
    p = network.polarity_posterior(_conn())
    assert p["alpha"] == 1.0 and p["beta"] == 1.0 and p["n"] == 0
    assert p["p_plus"] == 0.5
    assert math.isclose(p["ci_low"], 0.025) and math.isclose(p["ci_high"], 0.975)


def test_polarity_posterior_one_confident_plus():
    p = network.polarity_posterior(_conn(Rating("r1", polarity="+", confidence=5)))
    assert p["alpha"] == 2.0 and p["beta"] == 1.0
    assert math.isclose(p["p_plus"], 2 / 3)
    assert math.isclose(p["ci_low"], _beta.ppf(0.025, 2, 1))
    assert math.isclose(p["ci_high"], _beta.ppf(0.975, 2, 1))


def test_polarity_posterior_weights_by_confidence():
    p = network.polarity_posterior(_conn(
        Rating("r1", polarity="+", confidence=1),   # weight 0.2
        Rating("r2", polarity="-", confidence=3),   # weight 0.6
    ))
    assert math.isclose(p["alpha"], 1.2) and math.isclose(p["beta"], 1.6)
    assert math.isclose(p["p_plus"], 1.2 / 2.8)
    assert p["n"] == 2


def test_rating_weight_clamps():
    assert network._rating_weight(Rating("r", confidence=9)) == 1.0
    assert network._rating_weight(Rating("r", confidence=0)) == 0.2


def test_strength_posterior_no_ratings_is_flat_prior():
    s = network.strength_posterior(_conn())
    assert s["alpha"] == (1.0, 1.0, 1.0)
    assert all(math.isclose(v, 1 / 3) for v in s["mean"].values())
    assert s["map"] == "weak"          # tie -> lowest rank, documented
    assert s["n"] == 0


def test_strength_posterior_map_and_mean():
    s = network.strength_posterior(_conn(
        Rating("r1", strength="strong", confidence=5),
        Rating("r2", strength="medium", confidence=1),
    ))
    assert s["alpha"] == (1.0, 1.2, 2.0)
    assert s["map"] == "strong"
    assert math.isclose(s["mean"]["strong"], 2.0 / 4.2)


def test_bayesian_consensus_no_ratings_is_equivalent_copy():
    c = _conn()
    out = network.bayesian_consensus(c)
    assert out == c and out is not c


def test_bayesian_consensus_sets_posterior_values_and_never_mutates():
    c = _conn(Rating("r1", polarity="-", strength="strong", confidence=5),
              Rating("r2", polarity="-", strength="strong", confidence=5))
    out = network.bayesian_consensus(c)
    assert out.polarity == "-" and out.strength == "strong"
    assert 1 <= out.confidence <= 5
    assert out.delay == c.delay
    assert c.polarity == "+" and c.strength == "medium"     # untouched


def test_bayesian_consensus_confidence_mapping_endpoints():
    # No ratings -> interval width 0.95 -> round(1 + 4*0.05) = 1 ... but no
    # ratings returns a copy, so probe via the helper on a rated edge instead:
    wide = network.bayesian_consensus(_conn(Rating("r1", polarity="+", confidence=1)))
    narrow = network.bayesian_consensus(_conn(*[
        Rating(f"r{i}", polarity="+", confidence=5) for i in range(40)]))
    assert wide.confidence <= 2
    assert narrow.confidence == 5


def test_bayesian_contested_requires_dissent_and_straddle():
    assert network.bayesian_contested(_conn()) is False
    assert network.bayesian_contested(_conn(Rating("r1", polarity="-"))) is False
    assert network.bayesian_contested(_conn(
        Rating("r1", polarity="+"), Rating("r2", polarity="-"))) is True
    assert network.bayesian_contested(_conn(*[
        Rating(f"r{i}", polarity="+", confidence=5) for i in range(10)])) is False
    # Unanimous but few: Beta(3,1) / Beta(5,1) still straddle 0.5 (ci_low 0.292,
    # 0.478), yet the raters AGREE -> never contested. Without the dissent
    # precondition every freshly agreed edge would carry a warning.
    for n in (2, 4):
        assert network.bayesian_contested(_conn(*[
            Rating(f"r{i}", polarity="+", confidence=5) for i in range(n)])) is False
    assert network.bayesian_contested(_conn(Rating("r1"), Rating("r2"), Rating("r3"))) is False
    # Dissent that the posterior CAN resolve (12 '+' vs 1 '-', ci_low 0.661) is not contested.
    assert network.bayesian_contested(_conn(
        *[Rating(f"r{i}", polarity="+", confidence=5) for i in range(12)],
        Rating("x", polarity="-", confidence=5))) is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bayes_consensus.py -q`
Expected: FAIL with `AttributeError: module 'sespy.network' has no attribute 'polarity_posterior'`

- [ ] **Step 3: Implement in `sespy/network.py`** (insert directly after `remove_rating`)

```python
_STRENGTH_ORDER: tuple[str, ...] = ("weak", "medium", "strong")


def _rating_weight(rating) -> float:
    """Pseudo-count contributed by one rating: confidence/5, confidence
    clamped to [1, 5]. A confidence-5 rater is one full observation; a
    confidence-1 rater is a fifth of one."""
    return max(1, min(5, int(rating.confidence))) / 5.0


def polarity_posterior(connection, *, prior: tuple[float, float] = (1.0, 1.0)) -> dict:
    """Beta posterior for P(polarity == '+') over `connection.ratings`.

    alpha = prior[0] + Σ w_i·[r_i == '+'], beta = prior[1] + Σ w_i·[r_i == '-'],
    w_i = _rating_weight. Returns p_plus (posterior mean), a 95% equal-tailed
    credible interval, the parameters and the rating count. No ratings ->
    the prior. Pure; never reads the stored consensus scalars."""
    from scipy.stats import beta as _beta

    a, b = float(prior[0]), float(prior[1])
    for r in connection.ratings:
        w = _rating_weight(r)
        if r.polarity == "+":
            a += w
        else:
            b += w
    return {
        "p_plus": a / (a + b),
        "ci_low": float(_beta.ppf(0.025, a, b)),
        "ci_high": float(_beta.ppf(0.975, a, b)),
        "alpha": a, "beta": b, "n": len(connection.ratings),
    }


def strength_posterior(connection, *,
                       prior: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> dict:
    """Dirichlet posterior over (weak, medium, strong).

    alpha_k = prior_k + Σ w_i·[strength_i == k]. `map` is the label with the
    largest posterior mean; ties go to the lowest rank (weak < medium <
    strong) so the result is deterministic. Pure."""
    alpha = [float(x) for x in prior]
    for r in connection.ratings:
        k = _STRENGTH_RANK.get(r.strength, 2) - 1
        alpha[k] += _rating_weight(r)
    total = sum(alpha)
    mean = {lab: alpha[i] / total for i, lab in enumerate(_STRENGTH_ORDER)}
    best = max(range(3), key=lambda i: (alpha[i], -i))
    return {"mean": mean, "map": _STRENGTH_ORDER[best],
            "alpha": tuple(alpha), "n": len(connection.ratings)}


def bayesian_consensus(connection):
    """Copy of `connection` whose polarity/strength/confidence are posterior
    values: polarity '+' iff p_plus >= 0.5; strength = Dirichlet MAP;
    confidence = round(1 + 4·(1 - width)) clamped to [1, 5], width being the
    polarity credible-interval width (narrow -> confident). delay is kept.
    No ratings -> equivalent copy. NEVER the writer of stored scalars —
    recompute_consensus keeps that role; this is display/analysis-only."""
    if not connection.ratings:
        return replace(connection)
    pol = polarity_posterior(connection)
    width = pol["ci_high"] - pol["ci_low"]
    confidence = max(1, min(5, round(1 + 4 * (1 - width))))
    return replace(connection,
                   polarity="+" if pol["p_plus"] >= 0.5 else "-",
                   strength=strength_posterior(connection)["map"],
                   confidence=confidence)


def bayesian_contested(connection, *, band: tuple[float, float] = (0.2, 0.8)) -> bool:
    """True when >= 2 ratings, the raters are NOT unanimous in sign, AND the
    95% credible interval for P(+) straddles 0.5 — a disagreement the
    posterior cannot resolve. Unanimity short-circuits to False whatever n:
    with the flat Beta(1,1) prior, 2–4 unanimous confidence-5 raters still
    straddle 0.5, and that is 'sign not yet established', not a dispute.
    `band` is reserved for a future width criterion and is not read today."""
    ratings = connection.ratings
    if len(ratings) < 2 or len({r.polarity for r in ratings}) < 2:
        return False
    pol = polarity_posterior(connection)
    return pol["ci_low"] < 0.5 < pol["ci_high"]
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny pytest tests/test_bayes_consensus.py tests/test_network.py -q`
Expected: all PASS (existing consensus tests untouched).

- [ ] **Step 5: Commit**

```
git add sespy/network.py tests/test_bayes_consensus.py
git commit -m "feat(bayes): conjugate rater posteriors (Beta polarity, Dirichlet strength)"
```

---

### Task 2: Posterior flip mode for `uncertainty_scores`

**Files:**
- Modify: `sespy/network.py` — `_perturbed_connections` (~line 1411), `uncertainty_scores` (~line 1539) and its call to `_perturbed_connections`
- Test: `tests/test_bayes_consensus.py` (append)

**Interfaces:**
- Consumes: `polarity_posterior` (Task 1), `_perturb_prob`.
- Produces: `_flip_prob(c, base, flip_mode) -> float`; `_perturbed_connections(isa, base, rng, flip_mode="confidence")`; `uncertainty_scores(..., flip_mode: str = "confidence")`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_bayes_consensus.py`)

```python
from sespy.data_structure import Element, IsaData


def _isa(conns):
    ids = sorted({c.source for c in conns} | {c.target for c in conns})
    return IsaData(elements=[Element(id=i, label=i, type="Pressures") for i in ids],
                   connections=conns)


def test_flip_prob_confidence_mode_matches_perturb_prob():
    c = Connection("A", "B", confidence=3)
    assert network._flip_prob(c, 0.5, "confidence") == network._perturb_prob(3, 0.5)


def test_flip_prob_posterior_mode_is_prob_stored_sign_wrong_and_falls_with_agreement():
    two = Connection("A", "B", ratings=[Rating("r1", polarity="+", confidence=5),
                                        Rating("r2", polarity="+", confidence=5)])
    five = Connection("A", "B", ratings=[Rating(f"r{i}", polarity="+", confidence=5)
                                         for i in range(5)])
    p2 = network._flip_prob(two, 0.5, "posterior")
    p5 = network._flip_prob(five, 0.5, "posterior")
    assert math.isclose(p2, 1 / 4)         # Beta(3,1): p_plus 0.75, stored '+'
    assert p5 < p2


def test_flip_prob_posterior_mode_uses_the_stored_sign_not_the_posterior_mode():
    # recompute_consensus is an UNWEIGHTED majority (tie -> '+'); the posterior
    # weights by confidence. Here the stored sign is '+' but the posterior says
    # p_plus = 0.375, so the stored sign is wrong with probability 0.625 —
    # NOT min(p, 1-p) = 0.375.
    c = network.recompute_consensus(Connection("A", "B", ratings=[
        Rating("r1", polarity="+", confidence=1), Rating("r2", polarity="-", confidence=5)]))
    assert c.polarity == "+"
    assert math.isclose(network._flip_prob(c, 0.5, "posterior"), 0.625)


def test_flip_prob_posterior_mode_falls_back_when_unrated():
    c = Connection("A", "B", confidence=2)
    assert network._flip_prob(c, 0.5, "posterior") == network._perturb_prob(2, 0.5)


def test_uncertainty_scores_default_mode_unchanged_and_posterior_mode_runs():
    conns = [Connection("A", "B", confidence=3,
                        ratings=[Rating("r1", polarity="+"), Rating("r2", polarity="-")]),
             Connection("B", "A", confidence=5)]
    isa = _isa(conns)
    a = network.uncertainty_scores(isa, n_samples=50, seed=3)
    b = network.uncertainty_scores(isa, n_samples=50, seed=3, flip_mode="confidence")
    assert a == b
    c = network.uncertainty_scores(isa, n_samples=50, seed=3, flip_mode="posterior")
    assert set(c["leverage"]) == {"A", "B"} and c["n_samples"] == 50


def test_uncertainty_scores_rejects_unknown_flip_mode():
    with pytest.raises(ValueError):
        network.uncertainty_scores(_isa([Connection("A", "B")]), n_samples=5, flip_mode="x")
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bayes_consensus.py -q -k flip`
Expected: FAIL with `AttributeError: ... '_flip_prob'`

- [ ] **Step 3: Implement**

Insert before `_perturbed_connections`:

```python
def _flip_prob(c, base: float, flip_mode: str) -> float:
    """Per-draw sign-flip probability for one edge.

    'confidence': the D2D heuristic _perturb_prob(confidence, base).
    'posterior': probability the STORED sign is wrong under the rater
    posterior — 1 - p_plus when the stored polarity is '+', p_plus when it
    is '-'. The stored sign comes from recompute_consensus (unweighted
    majority, tie -> '+') or straight from a file, so it can disagree with
    the confidence-weighted posterior mode; such an edge then flips more
    often than not, which is the point. Edges with no ratings fall back to
    the confidence heuristic so a partially rated model still behaves."""
    if flip_mode == "posterior" and c.ratings:
        p = polarity_posterior(c)["p_plus"]
        return (1.0 - p) if c.polarity == "+" else p
    return _perturb_prob(c.confidence, base)
```

Change `_perturbed_connections`:

```python
def _perturbed_connections(isa: IsaData, base: float, rng,
                           flip_mode: str = "confidence") -> list[Connection]:
    """One Monte Carlo draw of structural uncertainty.

    Each connection independently: drops out with _perturb_prob (omitted from
    the result), or — if kept — flips polarity with _flip_prob(flip_mode).
    Pure: `isa` is never mutated; returns a fresh connection list."""
    out: list[Connection] = []
    for c in isa.connections:
        p_drop = _perturb_prob(c.confidence, base)
        if rng.random() < p_drop:
            continue  # dropped
        if rng.random() < _flip_prob(c, base, flip_mode):
            flipped = "-" if c.polarity == "+" else "+"
            out.append(replace(c, polarity=flipped))
        else:
            out.append(c)
    return out
```

In `uncertainty_scores`: add the keyword `flip_mode: str = "confidence",` after `contested_band`, add at the top of the body

```python
    if flip_mode not in ("confidence", "posterior"):
        raise ValueError(f"flip_mode must be 'confidence' or 'posterior', got {flip_mode!r}")
```

and pass `flip_mode=flip_mode` at the single `_perturbed_connections(isa, base, rng)` call inside the sampling loop (grep for `_perturbed_connections(` inside the function). Extend the docstring with one line: `flip_mode='posterior' flips by rater posterior (see _flip_prob).`

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny pytest tests/test_bayes_consensus.py tests/test_network.py -q`
Expected: all PASS; the existing `uncertainty_scores` seeded-reproducibility tests still pass (random-draw order per edge is unchanged: drop then flip).

- [ ] **Step 5: Commit**

```
git add sespy/network.py tests/test_bayes_consensus.py
git commit -m "feat(bayes): flip_mode='posterior' for uncertainty_scores"
```

---

### Task 3: Rate Connections Bayesian toggle (UI + i18n + e2e)

**Files:**
- Modify: `sespy/network.py` — `displayed_pairs` (~line 1376)
- Modify: `sespy/modules/rate_connections.py`
- Modify: `sespy/translations/core.json`
- Modify: `tests/test_network.py` (append), `tests/test_i18n.py` (append), `tests/test_rate_connections_e2e.py` (append before `await browser.close()`)

**Interfaces:**
- Consumes: `bayesian_contested`, `polarity_posterior`, `strength_posterior` (Task 1).
- Produces: `displayed_pairs(connections, *, contested_only, bayesian=False)`.

- [ ] **Step 1: Write the failing unit tests**

Append to `tests/test_network.py`:

```python
def test_displayed_pairs_bayesian_switch_uses_posterior_criterion():
    from sespy.data_structure import Rating
    # 1 '+' vs 1 '-' is contested under BOTH criteria; 3 '+' vs 1 '-' at
    # confidence 5 is not unanimous (legacy: contested) but its Beta(4,2)
    # interval still straddles 0.5 (bayesian: contested); 12 '+' vs 1 '-'
    # is legacy-contested but NOT bayesian-contested.
    c1 = Connection("A", "B", ratings=[Rating("r1", polarity="+"), Rating("r2", polarity="-")])
    c2 = Connection("B", "C", ratings=[Rating(f"r{i}", polarity="+", confidence=5) for i in range(12)]
                    + [Rating("x", polarity="-", confidence=5)])
    # Two unanimous confident raters: Beta(3,1) straddles 0.5 but there is no
    # dissent -> contested under NEITHER criterion.
    c3 = Connection("C", "D", ratings=[Rating("r1", polarity="+", confidence=5),
                                       Rating("r2", polarity="+", confidence=5)])
    conns = [c1, c2, c3]
    legacy = network.displayed_pairs(conns, contested_only=True)
    bayes = network.displayed_pairs(conns, contested_only=True, bayesian=True)
    assert [i for i, _ in legacy] == [0, 1]
    assert [i for i, _ in bayes] == [0]
    assert len(network.displayed_pairs(conns, contested_only=False, bayesian=True)) == 3
```

Append to `tests/test_i18n.py`:

```python
def test_bayesian_keys_present(translations):
    for key in ("rate.bayesian", "rate.p_plus", "rate.strength_post",
                "rate.bayesian_legend", "uncertainty.flip_posterior"):
        assert key in translations
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_network.py -q -k bayesian_switch; micromamba run -n shiny pytest tests/test_i18n.py -q -k bayesian`
Expected: `TypeError: displayed_pairs() got an unexpected keyword argument 'bayesian'` and `AssertionError` on the keys.

- [ ] **Step 3: Library change** — replace `displayed_pairs`:

```python
def displayed_pairs(connections, *, contested_only: bool, bayesian: bool = False):
    """Pure core of the C3 index contract: (true_idx, connection) pairs — all
    connections when not contested_only, else only contested ones. true_idx
    is always the position in `connections`, so a contested row keeps its
    true full-list index after filtering (the lookup the UI persists by).
    `bayesian` switches the contested criterion from 'raters not unanimous'
    to 'raters not unanimous AND the posterior credible interval straddles
    0.5' (bayesian_contested) — a lone dissenter among many is discounted."""
    pairs = list(enumerate(connections))
    if not contested_only:
        return pairs
    if bayesian:
        return [(i, c) for i, c in pairs if bayesian_contested(c)]
    return [(i, c) for i, c in pairs
            if connection_disagreement(c)["polarity_contested"]]
```

- [ ] **Step 4: i18n keys** — insert before the `"help.body"` line of `sespy/translations/core.json` (each on one line, comma-terminated):

```json
    "rate.bayesian": {"en": "Bayesian consensus (posteriors)", "es": "Consenso bayesiano (posteriores)", "fr": "Consensus bayésien (a posteriori)", "de": "Bayesscher Konsens (Posteriors)", "lt": "Bajeso konsensusas (posteriorai)", "pt": "Consenso bayesiano (posteriores)", "it": "Consenso bayesiano (posteriori)", "no": "Bayesiansk konsensus (posteriorer)", "el": "Μπεϋζιανή συναίνεση (εκ των υστέρων)"},
    "rate.p_plus": {"en": "P(+)", "es": "P(+)", "fr": "P(+)", "de": "P(+)", "lt": "P(+)", "pt": "P(+)", "it": "P(+)", "no": "P(+)", "el": "P(+)"},
    "rate.strength_post": {"en": "posterior strength", "es": "fuerza posterior", "fr": "force a posteriori", "de": "Posterior-Stärke", "lt": "posteriorinis stiprumas", "pt": "força posterior", "it": "forza a posteriori", "no": "posterior styrke", "el": "εκ των υστέρων ισχύς"},
    "rate.bayesian_legend": {"en": "P(+) is the posterior probability of a positive sign with its 95% credible interval; posterior strength is the most probable strength. Ratings are weighted by rater confidence. The stored consensus is not changed.", "es": "P(+) es la probabilidad posterior de signo positivo con su intervalo creíble del 95 %; la fuerza posterior es la más probable. Las valoraciones se ponderan por la confianza del evaluador. El consenso guardado no cambia.", "fr": "P(+) est la probabilité a posteriori d'un signe positif avec son intervalle de crédibilité à 95 % ; la force a posteriori est la plus probable. Les évaluations sont pondérées par la confiance de l'évaluateur. Le consensus enregistré n'est pas modifié.", "de": "P(+) ist die Posterior-Wahrscheinlichkeit eines positiven Vorzeichens mit 95-%-Glaubwürdigkeitsintervall; die Posterior-Stärke ist die wahrscheinlichste Stärke. Bewertungen werden nach Konfidenz gewichtet. Der gespeicherte Konsens bleibt unverändert.", "lt": "P(+) – posteriorinė teigiamo ženklo tikimybė su 95 % patikimumo intervalu; posteriorinis stiprumas – labiausiai tikėtinas stiprumas. Vertinimai sveriami pagal vertintojo pasitikėjimą. Išsaugotas konsensusas nekeičiamas.", "pt": "P(+) é a probabilidade posterior de sinal positivo com o seu intervalo de credibilidade de 95 %; a força posterior é a mais provável. As avaliações são ponderadas pela confiança do avaliador. O consenso guardado não é alterado.", "it": "P(+) è la probabilità a posteriori di segno positivo con il suo intervallo di credibilità al 95 %; la forza a posteriori è la più probabile. Le valutazioni sono pesate per la confidenza del valutatore. Il consenso salvato non cambia.", "no": "P(+) er posteriorsannsynligheten for positivt fortegn med 95 % troverdighetsintervall; posterior styrke er den mest sannsynlige styrken. Vurderinger vektes etter vurdererens tillit. Lagret konsensus endres ikke.", "el": "Το P(+) είναι η εκ των υστέρων πιθανότητα θετικού προσήμου με διάστημα αξιοπιστίας 95 %· η εκ των υστέρων ισχύς είναι η πιθανότερη. Οι αξιολογήσεις σταθμίζονται με τη βεβαιότητα του αξιολογητή. Η αποθηκευμένη συναίνεση δεν αλλάζει."},
    "uncertainty.flip_posterior": {"en": "Flip signs by rater posterior", "es": "Invertir signos según el posterior de los evaluadores", "fr": "Inverser les signes selon l'a posteriori des évaluateurs", "de": "Vorzeichen nach Bewerter-Posterior umkehren", "lt": "Keisti ženklus pagal vertintojų posteriorą", "pt": "Inverter sinais pelo posterior dos avaliadores", "it": "Inverti i segni secondo il posteriori dei valutatori", "no": "Snu fortegn etter vurderernes posterior", "el": "Αντιστροφή προσήμων κατά την εκ των υστέρων κατανομή των αξιολογητών"},
```

Validate: `micromamba run -n shiny python -c "import json;json.load(open('sespy/translations/core.json',encoding='utf-8'));print('json ok')"`

- [ ] **Step 5: UI change** in `sespy/modules/rate_connections.py`

In `rate_connections_ui`, after the `blind_mode` checkbox add:

```python
                ui.input_checkbox("bayesian", t("rate.bayesian"), value=False),
```

and replace the static legend line with:

```python
                ui.output_ui("table_legend"),
```

In the server:

```python
    @reactive.calc
    def displayed_connections():
        event_bus.isa_change.get()
        return network.displayed_pairs(
            project_data.get().isa_data.connections,
            contested_only=input.contested_only(),
            bayesian=input.bayesian(),
        )
```

Replace the body of `connections_table` from `cols = [...]` to the `return`:

```python
        bayes = input.bayesian()
        cols = ["source", "target", "polarity", "strength", "confidence", "delay",
                "#ratings", "mine", "disagreement"]
        p_col, s_col = t("rate.p_plus"), t("rate.strength_post")
        if bayes:
            cols += [p_col, s_col]
        rows = []
        for _true_idx, c in displayed_connections():
            # Only the sign criterion changes under the toggle; the strength /
            # confidence spreads (the '~' legend) stay truthful.
            d = network.connection_disagreement(c)
            if bayes:
                d = {**d, "polarity_contested": network.bayesian_contested(c)}
            row = {
                "source": f"{c.source} · {by_id.get(c.source, '?')}",
                "target": f"{c.target} · {by_id.get(c.target, '?')}",
                "polarity": c.polarity,
                "strength": c.strength,
                "confidence": c.confidence,
                "delay": c.delay,
                "#ratings": len(c.ratings),
                "mine": "✓" if rater and any(r.rater_id == rater for r in c.ratings) else "—",
                "disagreement": network.disagreement_cell(d, contested_label=contested_label),
            }
            if bayes:
                pol = network.polarity_posterior(c)
                st = network.strength_posterior(c)
                row[p_col] = f"{pol['p_plus']:.2f} [{pol['ci_low']:.2f}–{pol['ci_high']:.2f}]"
                row[s_col] = f"{st['map']} {st['mean'][st['map']]:.2f}"
            rows.append(row)
        return render.DataGrid(
            pd.DataFrame(rows or [{k: "" for k in cols}], columns=cols),
            selection_mode="row", height="260px",
        )
```

Add a legend output and make the count follow the switch:

```python
    @output
    @render.ui
    def table_legend():
        base = ui.tags.small("⚠ contested sign · ~ strength/confidence spread (0–2 / 0–4)",
                             class_="text-muted")
        if not input.bayesian():
            return base
        return ui.div(base, ui.tags.br(),
                      ui.tags.small(t("rate.bayesian_legend"), class_="text-muted"))
```

```python
    @output
    @render.ui
    def contested_count():
        event_bus.isa_change.get()
        conns = project_data.get().isa_data.connections
        if input.bayesian():
            n = sum(1 for c in conns if network.bayesian_contested(c))
        else:
            n = sum(1 for c in conns
                    if network.connection_disagreement(c)["polarity_contested"])
        return ui.tags.p(t("rate.contested_count", n=n),
                         class_="text-muted", style="margin-bottom:4px;")
```

Add a selection reset on the new switch (a re-rendered grid loses its row):

```python
    @reactive.effect
    @reactive.event(input.bayesian)
    def _reset_selection_on_bayesian():
        sel_idx.set(None)
```

- [ ] **Step 6: Run unit + i18n tests**

Run: `micromamba run -n shiny pytest tests/test_network.py tests/test_i18n.py tests/test_bayes_consensus.py -q`
Expected: PASS.

- [ ] **Step 7: Extend the e2e** — in `tests/test_rate_connections_e2e.py`, before `await browser.close()`:

```python
        # --- Option A: Bayesian toggle adds posterior columns, keeps stored values ---
        await page.uncheck("#rate-contested_only")
        await page.check("#rate-bayesian")
        headers = []
        for _ in range(20):
            await page.wait_for_timeout(500)
            headers = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#rate-connections_table table thead th')).map(th => th.textContent.trim())"
            )
            if any("P(+)" in h for h in headers):
                break
        assert any("P(+)" in h for h in headers), f"P(+) column missing: {headers}"
        cells_b = await page.evaluate(
            "() => Array.from(document.querySelectorAll("
            "'#rate-connections_table table tbody tr:first-child td')).map(td => td.textContent.trim())"
        )
        assert any("[" in c and "–" in c for c in cells_b), f"no credible interval cell: {cells_b}"
        assert "2" in cells_b and any("⚠" in c for c in cells_b), \
            f"stored #ratings / contested marker changed under the toggle: {cells_b}"
        count_b = await page.evaluate(
            "() => document.getElementById('rate-contested_count').textContent")
        assert "1" in count_b, f"bayesian contested count wrong: {count_b!r}"
        await page.uncheck("#rate-bayesian")
        for _ in range(20):
            await page.wait_for_timeout(500)
            headers = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#rate-connections_table table thead th')).map(th => th.textContent.trim())"
            )
            if not any("P(+)" in h for h in headers):
                break
        assert not any("P(+)" in h for h in headers), "P(+) column persisted after toggle-off"
        print("rate connections bayesian toggle: OK")
```

- [ ] **Step 8: Run this e2e alone against a live server**

Kill anything on port 8000 first (`netstat -ano | findstr :8000` then `taskkill /PID <pid> /F` via PowerShell). Then in PowerShell: `Start-Process -NoNewWindow micromamba -ArgumentList 'run','-n','shiny','shiny','run','app.app','--port','8000'`; wait until `http://127.0.0.1:8000` answers; run `micromamba run -n shiny python tests/test_rate_connections_e2e.py`. First two attempts on a cold server may fail on warm-up (known flake); a third failure is real.
Expected: prints `rate connections bayesian toggle: OK`. Stop the server afterwards (kill by port).

- [ ] **Step 9: Commit**

```
git add sespy/network.py sespy/modules/rate_connections.py sespy/translations/core.json tests/test_network.py tests/test_i18n.py tests/test_rate_connections_e2e.py
git commit -m "feat(rate): Bayesian consensus toggle with posterior columns"
```

---

### Task 4: Loop Analysis posterior-flip checkbox

**Files:**
- Modify: `sespy/modules/analysis_loops.py` lines 129–131 (sidebar) and 196–218 (`_unc_task`, `_unc_trigger`)

**Interfaces:**
- Consumes: `uncertainty_scores(..., flip_mode=)` (Task 2), key `uncertainty.flip_posterior` (Task 3).

- [ ] **Step 1: Sidebar** — after the `n_samples` numeric input add:

```python
            ui.input_checkbox("flip_posterior", t("uncertainty.flip_posterior"), value=False),
```

- [ ] **Step 2: Task + trigger** — change the extended task and its call so the mode is a feeding input (any change re-runs; a stale result is never shown):

```python
    @reactive.extended_task
    async def _unc_task(isa, cycles, n_samples, flip_mode, gen):
        result = await asyncio.to_thread(
            net_analysis.uncertainty_scores, isa,
            cycles=cycles, n_samples=n_samples, seed=0, flip_mode=flip_mode,
        )
        return (gen, result)
```

and in `_unc_trigger`, replace the last three lines with:

```python
        n = int(input.n_samples() or 100)
        flip_mode = "posterior" if input.flip_posterior() else "confidence"
        unc_state.set(_COMPUTING)
        _unc_task(isa, cycles, n, flip_mode, gen)
```

- [ ] **Step 3: Verify** — unit gate subset plus the loops e2e:

Run: `micromamba run -n shiny pytest tests/test_no_deprecations.py tests/test_i18n.py -q`; then start a server on 8000 as in Task 3 Step 8 and run `micromamba run -n shiny python tests/test_loops_e2e.py`.
Expected: both green (the loops e2e does not touch the new checkbox; it proves nothing regressed in the block).

- [ ] **Step 4: Commit**

```
git add sespy/modules/analysis_loops.py
git commit -m "feat(loops): posterior sign-flip option for Monte Carlo uncertainty"
```

---

### Task 5: `sespy/bayes.py` — link probabilities and the path-set DAG (no pgmpy)

**Files:**
- Create: `sespy/bayes.py`
- Test: `tests/test_bayes.py` (create)

**Interfaces:**
- Consumes: `network.causal_paths(isa, source, target, *, max_length, max_paths) -> {"paths": [{"path": [ids], "length", "polarity"}], "counts", "truncated"}`.
- Produces: `BayesUnavailable`, `LEAK`, `STRENGTH_LINK`, `link_probability(connection) -> float`, `path_set_dag(isa, source, target, *, max_length=8, max_paths=100) -> dict` with keys `nodes` (lexicographic topological order), `edges` (list of `(u, v, Connection)`), `cut_edges` (list of `(u, v)`), `paths`, `truncated`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bayes.py
"""Option B: path-set Bayesian belief network (spec 2026-09-08-sespy-bayesian-options)."""
from __future__ import annotations

import importlib.util
import math
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

from sespy import bayes
from sespy.data_structure import Connection, Element, IsaData, load_sample

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_ses.json"


def _isa(conns):
    ids = sorted({c.source for c in conns} | {c.target for c in conns})
    return IsaData(elements=[Element(id=i, label=i, type="Pressures") for i in ids],
                   connections=conns)


def test_link_probability_endpoints_and_clamp():
    assert math.isclose(bayes.link_probability(Connection("a", "b", strength="strong", confidence=5)), 0.80)
    assert math.isclose(bayes.link_probability(Connection("a", "b", strength="strong", confidence=1)), 0.40)
    assert math.isclose(bayes.link_probability(Connection("a", "b", strength="weak", confidence=3)), 0.30 * 0.75)
    assert bayes.link_probability(Connection("a", "b", strength="???", confidence=3)) == \
        bayes.link_probability(Connection("a", "b", strength="medium", confidence=3))
    assert 0.01 <= bayes.link_probability(Connection("a", "b", strength="weak", confidence=-4)) <= 0.99


def test_path_set_dag_empty_shapes():
    isa = _isa([Connection("A", "B")])
    for s, t in (("A", "A"), ("Z", "B"), ("B", "A")):
        r = bayes.path_set_dag(isa, s, t)
        assert r == {"nodes": [], "edges": [], "cut_edges": [], "paths": [], "truncated": False}


def test_path_set_dag_chain_is_topological_and_keeps_connections():
    isa = _isa([Connection("A", "B", polarity="-"), Connection("B", "C")])
    r = bayes.path_set_dag(isa, "A", "C")
    assert r["nodes"] == ["A", "B", "C"]
    assert [(u, v) for u, v, _ in r["edges"]] == [("A", "B"), ("B", "C")]
    assert r["edges"][0][2].polarity == "-"
    assert r["cut_edges"] == [] and len(r["paths"]) == 1


def test_path_set_dag_cuts_the_weaker_edge_of_a_union_cycle():
    # s->a->b->t and s->b->a->t: union contains a<->b. b->a is weaker, so it is cut.
    conns = [Connection("s", "a"), Connection("s", "b"),
             Connection("a", "b", strength="strong", confidence=5),
             Connection("b", "a", strength="weak", confidence=1),
             Connection("a", "t"), Connection("b", "t")]
    r = bayes.path_set_dag(_isa(conns), "s", "t")
    assert r["cut_edges"] == [("b", "a")]
    g = nx.DiGraph([(u, v) for u, v, _ in r["edges"]])
    assert nx.is_directed_acyclic_graph(g)
    assert ("b", "a") not in g.edges and ("a", "b") in g.edges
    # causal_paths enumerates 4 simple paths; s->b->a->t crosses the cut edge
    # and is no longer in the model, so only 3 are reported.
    assert len(r["paths"]) == 3
    assert all(("b", "a") not in zip(p["path"], p["path"][1:]) for p in r["paths"])


@pytest.mark.parametrize("s,t", [("D001", "GB01"), ("D002", "GB02"), ("A001", "ES03")])
def test_path_set_dag_sample_is_acyclic(s, t):
    r = bayes.path_set_dag(load_sample(SAMPLE), s, t)
    assert r["nodes"], "expected a path on the sample"
    assert nx.is_directed_acyclic_graph(nx.DiGraph([(u, v) for u, v, _ in r["edges"]]))
    assert r["nodes"][0] == s and r["nodes"][-1] == t
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q`
Expected: `ModuleNotFoundError: No module named 'sespy.bayes'`

- [ ] **Step 3: Create `sespy/bayes.py`**

```python
"""Path-set Bayesian belief network (Option B of the 2026-09-08 Bayesian
options design).

A causal loop diagram has feedback loops; a belief network must be a DAG.
Rather than cut the whole diagram, this module answers one question at a
time: for a chosen source and target it takes the simple causal paths
between them (network.causal_paths), unions them into a small graph, makes
that graph acyclic by greedily removing the weakest link on each cycle found
(always reported, never silent), derives every
conditional probability table by noisy-OR from the existing strength ×
confidence × polarity scores, and runs exact inference with pgmpy.

pgmpy is optional (`pip install "sespy[bayes]"` / `micromamba install -n
shiny pgmpy`) and is imported lazily inside the two functions that need it;
importing this module never requires it.
"""
from __future__ import annotations

import itertools

import networkx as nx

from .data_structure import IsaData
from .network import causal_paths

#: P(child high | no active parent) — the noisy-OR leak.
LEAK: float = 0.05
#: Base link strength per strength rank before confidence scaling.
STRENGTH_LINK: dict[str, float] = {"weak": 0.30, "medium": 0.55, "strong": 0.80}

_INSTALL_HINT = ('Bayesian inference needs the optional pgmpy package: '
                 'pip install "sespy[bayes]"  or  micromamba install -n shiny pgmpy')


class BayesUnavailable(ImportError):
    """pgmpy is not installed. str(exc) carries the install hint."""


def link_probability(connection) -> float:
    """Noisy-OR link strength q for one edge: STRENGTH_LINK[strength] scaled
    by confidence, q = s·(0.5 + 0.5·(conf − 1)/4); confidence 5 gives s,
    confidence 1 gives s/2. Unknown strength counts as medium; confidence is
    clamped to [1, 5]; q is clamped to [0.01, 0.99]. Pure."""
    s = STRENGTH_LINK.get(connection.strength, STRENGTH_LINK["medium"])
    conf = max(1, min(5, int(connection.confidence)))
    q = s * (0.5 + 0.5 * (conf - 1) / 4.0)
    return min(0.99, max(0.01, q))


def _empty_dag() -> dict:
    return {"nodes": [], "edges": [], "cut_edges": [], "paths": [], "truncated": False}


def path_set_dag(isa: IsaData, source: str, target: str, *,
                 max_length: int = 8, max_paths: int = 100) -> dict:
    """Union of the simple source→target paths, made acyclic.

    Returns {"nodes": [ids in lexicographic topological order],
             "edges": [(u, v, Connection)], "cut_edges": [(u, v)],
             "paths": the causal_paths rows still intact after cuts,
             "truncated": bool}; the empty shape when there is no path. The
    union of simple paths is NOT always a DAG (s→a→b→t and s→b→a→t contain
    a⇄b): while a cycle remains, the edge on it with the lowest
    link_probability (ties: lexicographic (u, v)) is removed greedily and
    recorded in cut_edges — never silently (greedy, not minimal: a shared
    edge on two cycles may be spared in favour of two weaker ones). A node
    whose in-edges were all cut becomes a parentless 0.5-prior root. Parallel
    (source, target) connections deduplicate last-wins, matching
    causal_paths. Pure."""
    cp = causal_paths(isa, source, target, max_length=max_length, max_paths=max_paths)
    if not cp["paths"]:
        return _empty_dag()
    conn_by: dict[tuple[str, str], object] = {}
    for c in isa.connections:
        conn_by[(c.source, c.target)] = c
    g = nx.DiGraph()
    for row in cp["paths"]:
        p = row["path"]
        for u, v in zip(p, p[1:]):
            g.add_edge(u, v)
    cut: list[tuple[str, str]] = []
    while True:
        try:
            cycle = nx.find_cycle(g)
        except nx.NetworkXNoCycle:
            break
        u, v = min(((e[0], e[1]) for e in cycle),
                   key=lambda uv: (link_probability(conn_by[uv]), uv))
        g.remove_edge(u, v)
        cut.append((u, v))
    nodes = list(nx.lexicographical_topological_sort(g))
    edges = [(u, v, conn_by[(u, v)]) for u, v in sorted(g.edges())]
    # Only paths whose every hop survived the cuts are still IN the model;
    # n_paths in the UI must count those, not the pre-cut enumeration.
    paths = [r for r in cp["paths"]
             if all(g.has_edge(a, b) for a, b in zip(r["path"], r["path"][1:]))]
    return {"nodes": nodes, "edges": edges, "cut_edges": cut,
            "paths": paths, "truncated": cp["truncated"]}
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add sespy/bayes.py tests/test_bayes.py
git commit -m "feat(bayes): link probabilities and acyclic path-set DAG"
```

---

### Task 6: CPT derivation, model build, inference, packaging

**Files:**
- Modify: `sespy/bayes.py` (append), `pyproject.toml` (optional-dependencies), `README.md` (Install section)
- Test: `tests/test_bayes.py` (append)

**Interfaces:**
- Consumes: `path_set_dag`, `link_probability`, `LEAK` (Task 5).
- Produces:
  - `noisy_or_p_high(states: tuple[int, ...], parents: list[tuple[str, Connection]]) -> float`
  - `build_path_bbn(isa, source, target, *, max_length=8, max_paths=100) -> tuple[model | None, dag_info]`
  - `query_path_bbn(model, dag_info, evidence: dict[str, int]) -> dict` with keys `rows` (list of `{id, baseline, p_high, delta}` sorted by |delta| desc then id), `evidence`, `n_paths`, `truncated`, `cut_edges`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_bayes.py`)

```python
def test_noisy_or_two_parents_plus_and_minus():
    plus = Connection("p", "c", polarity="+", strength="strong", confidence=5)   # q 0.8
    minus = Connection("m", "c", polarity="-", strength="weak", confidence=5)    # q 0.3
    parents = [("p", plus), ("m", minus)]
    # p low, m low: only the '-' parent is active (low activates a '-' edge)
    assert math.isclose(bayes.noisy_or_p_high((0, 0), parents), 1 - 0.95 * 0.7)
    # p low, m high: nothing active -> leak
    assert math.isclose(bayes.noisy_or_p_high((0, 1), parents), bayes.LEAK)
    # p high, m low: both active
    assert math.isclose(bayes.noisy_or_p_high((1, 0), parents), 1 - 0.95 * 0.2 * 0.7)
    # p high, m high: only '+' active
    assert math.isclose(bayes.noisy_or_p_high((1, 1), parents), 1 - 0.95 * 0.2)


# NOT a module-level pytest.importorskip: that raises Skipped at collection
# and silently skips the WHOLE file (the pgmpy-free Task 5 tests included) on
# every CI job, none of which installs the `bayes` extra. Mark only the five
# tests that build a real model.
needs_pgmpy = pytest.mark.skipif(importlib.util.find_spec("pgmpy") is None,
                                 reason="optional bayes extra (pgmpy) not installed")


def test_import_bayes_does_not_import_pgmpy():
    # Global constraint: pgmpy only inside function bodies (pgmpy 1.1 pulls
    # torch, ~40 s). Fresh interpreter, single-line -c (multi-line -c breaks on
    # this Windows shell).
    out = subprocess.run(
        [sys.executable, "-c", "import sys, sespy.bayes; print('pgmpy' in sys.modules)"],
        cwd=str(SAMPLE.parents[1]), capture_output=True, text=True, check=True,
    )
    assert out.stdout.strip() == "False"


def _chain(sign_ab="+"):
    return _isa([Connection("A", "B", polarity=sign_ab, strength="strong", confidence=5),
                 Connection("B", "C", polarity="+", strength="strong", confidence=5)])


@needs_pgmpy
def test_build_path_bbn_returns_valid_model_and_none_without_path():
    model, info = bayes.build_path_bbn(_chain(), "A", "C")
    assert model is not None and model.check_model()
    assert info["nodes"] == ["A", "B", "C"]
    model2, info2 = bayes.build_path_bbn(_chain(), "C", "A")
    assert model2 is None and info2["nodes"] == []


@needs_pgmpy
def test_forward_query_raises_target_on_positive_chain():
    model, info = bayes.build_path_bbn(_chain(), "A", "C")
    r = bayes.query_path_bbn(model, info, {"A": 1})
    by = {row["id"]: row for row in r["rows"]}
    assert by["A"]["p_high"] == 1.0
    assert math.isclose(by["B"]["p_high"], 1 - 0.95 * 0.2)
    assert math.isclose(by["B"]["baseline"], 0.5 * (1 - 0.95 * 0.2) + 0.5 * bayes.LEAK)
    assert by["C"]["delta"] > 0
    assert r["n_paths"] == 1 and r["cut_edges"] == [] and r["truncated"] is False
    assert [row["id"] for row in r["rows"]][0] == "A"       # largest |delta| first


@needs_pgmpy
def test_negative_edge_flips_the_delta_sign():
    model, info = bayes.build_path_bbn(_chain("-"), "A", "C")
    r = bayes.query_path_bbn(model, info, {"A": 1})
    by = {row["id"]: row for row in r["rows"]}
    assert by["C"]["delta"] < 0


@needs_pgmpy
def test_diagnostic_query_infers_source():
    model, info = bayes.build_path_bbn(_chain(), "A", "C")
    r = bayes.query_path_bbn(model, info, {"C": 1})
    by = {row["id"]: row for row in r["rows"]}
    assert by["A"]["p_high"] > 0.5 and by["C"]["p_high"] == 1.0


@needs_pgmpy
def test_query_is_deterministic_on_the_sample():
    isa = load_sample(SAMPLE)
    m1, i1 = bayes.build_path_bbn(isa, "D001", "GB01")
    m2, i2 = bayes.build_path_bbn(isa, "D001", "GB01")
    assert bayes.query_path_bbn(m1, i1, {"D001": 1}) == bayes.query_path_bbn(m2, i2, {"D001": 1})
    assert i1["cut_edges"] == [] and len(i1["paths"]) == 2


def test_bayes_unavailable_when_pgmpy_missing(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake(name, *a, **k):
        if name.startswith("pgmpy"):
            raise ImportError("no pgmpy")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(bayes.BayesUnavailable) as exc:
        bayes.build_path_bbn(_chain(), "A", "C")
    assert "sespy[bayes]" in str(exc.value)
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q`
Expected: FAIL with `AttributeError: module 'sespy.bayes' has no attribute 'noisy_or_p_high'`

- [ ] **Step 3: Append to `sespy/bayes.py`**

```python
def noisy_or_p_high(states: tuple[int, ...], parents: list) -> float:
    """P(child high | parent states) under noisy-OR.

    A parent is *active* when it is high and its edge is '+', or low and its
    edge is '-' (a negative link pushes the child high when the parent is
    low). P(high) = 1 − (1 − LEAK)·Π_active (1 − q_i). Pure."""
    prod = 1.0 - LEAK
    for state, (_, conn) in zip(states, parents):
        active = (state == 1 and conn.polarity == "+") or (state == 0 and conn.polarity == "-")
        if active:
            prod *= 1.0 - link_probability(conn)
    return 1.0 - prod


def build_path_bbn(isa: IsaData, source: str, target: str, *,
                   max_length: int = 8, max_paths: int = 100):
    """(pgmpy DiscreteBayesianNetwork, dag_info) over path_set_dag; (None,
    empty dag_info) when there is no path. Every node is binary (0 low,
    1 high). Parentless nodes (the source, and any node whose in-edges were
    all cut) get P(high) = 0.5; every other
    CPT is noisy-OR over its parents *inside the path set*. Raises
    BayesUnavailable when pgmpy is missing."""
    try:
        from pgmpy.factors.discrete import TabularCPD
        from pgmpy.models import DiscreteBayesianNetwork
    except ImportError as exc:
        raise BayesUnavailable(_INSTALL_HINT) from exc

    info = path_set_dag(isa, source, target, max_length=max_length, max_paths=max_paths)
    if not info["nodes"]:
        return None, info
    model = DiscreteBayesianNetwork([(u, v) for u, v, _ in info["edges"]])
    parents: dict[str, list] = {n: [] for n in info["nodes"]}
    for u, v, c in info["edges"]:
        parents[v].append((u, c))
    for node in info["nodes"]:
        ps = parents[node]
        if not ps:
            model.add_cpds(TabularCPD(node, 2, [[0.5], [0.5]]))
            continue
        # pgmpy column order: itertools.product over the evidence list, last
        # variable fastest — exactly what product([0, 1], repeat=k) yields.
        highs = [noisy_or_p_high(states, ps)
                 for states in itertools.product((0, 1), repeat=len(ps))]
        model.add_cpds(TabularCPD(
            node, 2, [[1.0 - p for p in highs], highs],
            evidence=[u for u, _ in ps], evidence_card=[2] * len(ps),
        ))
    model.check_model()
    return model, info


def query_path_bbn(model, info: dict, evidence: dict[str, int]) -> dict:
    """Exact posterior P(high) for every path-set node given `evidence`
    ({node_id: 0|1}), by variable elimination, against the no-evidence
    baseline. rows sort by |delta| descending then id; evidence nodes report
    p_high equal to their evidence value. Deterministic (no sampling)."""
    from pgmpy.inference import VariableElimination

    ve = VariableElimination(model)
    ev = {k: int(v) for k, v in evidence.items()}
    rows = []
    for n in info["nodes"]:
        base = float(ve.query([n], show_progress=False).values[1])
        if n in ev:
            p = float(ev[n])
        else:
            p = float(ve.query([n], evidence=ev, show_progress=False).values[1])
        rows.append({"id": n, "baseline": base, "p_high": p, "delta": p - base})
    rows.sort(key=lambda r: (-abs(r["delta"]), r["id"]))
    return {"rows": rows, "evidence": ev, "n_paths": len(info["paths"]),
            "truncated": info["truncated"], "cut_edges": list(info["cut_edges"])}
```

- [ ] **Step 4: Packaging** — in `pyproject.toml` `[project.optional-dependencies]`, after the `pdf` entry add:

```toml
# Path-set Bayesian belief network (Intervention panel). DiscreteBayesianNetwork
# exists from pgmpy 1.0. Optional: the app degrades to an install hint without it.
bayes = ["pgmpy>=1.0"]
```

In `README.md` after the line `pip install ".[pdf]"     # + WeasyPrint ...` add:

```
pip install ".[bayes]"   # + pgmpy for the Intervention panel's Bayesian inference
```

- [ ] **Step 5: Run to verify they pass**

Run: `micromamba run -n shiny pytest tests/test_bayes.py tests/test_no_deprecations.py -q`
Expected: PASS (pgmpy's own FutureWarning at import is not a ShinyDeprecationWarning and does not trip the guard). Wall-clock: the first model test pays the pgmpy import, measured 35–65 s in this env because pgmpy 1.1 loads torch; do not kill the run. In an environment without pgmpy the five `@needs_pgmpy` tests skip and everything else in the file (DAG, noisy-OR, `BayesUnavailable`, lazy-import) must still pass — a wholly skipped file is a regression.

- [ ] **Step 6: Commit**

```
git add sespy/bayes.py tests/test_bayes.py pyproject.toml README.md
git commit -m "feat(bayes): noisy-OR path-set BBN with exact inference; pgmpy as optional extra"
```

---

### Task 7: Intervention panel BBN block (UI + i18n + e2e)

**Files:**
- Modify: `sespy/modules/analysis_intervention.py` (UI lines 145–172; server after the diffusion handlers)
- Modify: `sespy/translations/core.json`
- Modify: `tests/test_i18n.py` (append), `tests/test_intervention_e2e.py` (append before the final print)

**Interfaces:**
- Consumes: `bayes.build_path_bbn`, `bayes.query_path_bbn`, `bayes.BayesUnavailable` (Task 6).

- [ ] **Step 1: Failing i18n test** (append to `tests/test_i18n.py`)

```python
def test_bbn_keys_present(translations):
    for key in ("bbn.title", "bbn.source", "bbn.target", "bbn.direction", "bbn.forward",
                "bbn.diagnostic", "bbn.run", "bbn.hint", "bbn.computing", "bbn.no_path",
                "bbn.unavailable", "bbn.summary", "bbn.truncated", "bbn.cut",
                "bbn.target_line", "bbn.about_text"):
        assert key in translations
```

Run: `micromamba run -n shiny pytest tests/test_i18n.py -q -k bbn` → FAIL.

- [ ] **Step 2: i18n keys** — insert before `"help.body"`:

```json
    "bbn.title": {"en": "Bayesian inference (path set)", "es": "Inferencia bayesiana (conjunto de rutas)", "fr": "Inférence bayésienne (ensemble de chemins)", "de": "Bayessche Inferenz (Pfadmenge)", "lt": "Bajeso išvados (kelių aibė)", "pt": "Inferência bayesiana (conjunto de caminhos)", "it": "Inferenza bayesiana (insieme di percorsi)", "no": "Bayesiansk inferens (stisett)", "el": "Μπεϋζιανή συμπερασματολογία (σύνολο διαδρομών)"},
    "bbn.source": {"en": "From", "es": "Desde", "fr": "De", "de": "Von", "lt": "Iš", "pt": "De", "it": "Da", "no": "Fra", "el": "Από"},
    "bbn.target": {"en": "To", "es": "Hasta", "fr": "Vers", "de": "Nach", "lt": "Į", "pt": "Para", "it": "A", "no": "Til", "el": "Προς"},
    "bbn.direction": {"en": "Query", "es": "Consulta", "fr": "Requête", "de": "Abfrage", "lt": "Užklausa", "pt": "Consulta", "it": "Interrogazione", "no": "Spørring", "el": "Ερώτημα"},
    "bbn.forward": {"en": "Forward: source is high", "es": "Directa: el origen está alto", "fr": "Directe : la source est haute", "de": "Vorwärts: Quelle ist hoch", "lt": "Tiesioginė: šaltinis aukštas", "pt": "Direta: a origem está alta", "it": "Diretta: la sorgente è alta", "no": "Forover: kilden er høy", "el": "Εμπρόσθια: η πηγή είναι υψηλή"},
    "bbn.diagnostic": {"en": "Diagnostic: target is high", "es": "Diagnóstica: el destino está alto", "fr": "Diagnostique : la cible est haute", "de": "Diagnostisch: Ziel ist hoch", "lt": "Diagnostinė: tikslas aukštas", "pt": "Diagnóstica: o destino está alto", "it": "Diagnostica: il bersaglio è alto", "no": "Diagnostisk: målet er høyt", "el": "Διαγνωστική: ο στόχος είναι υψηλός"},
    "bbn.run": {"en": "Run inference", "es": "Ejecutar inferencia", "fr": "Lancer l'inférence", "de": "Inferenz ausführen", "lt": "Vykdyti išvedimą", "pt": "Executar inferência", "it": "Esegui inferenza", "no": "Kjør inferens", "el": "Εκτέλεση συμπερασματολογίας"},
    "bbn.hint": {"en": "not computed for the current model — run to compute", "es": "no calculado para el modelo actual: ejecute para calcular", "fr": "non calculé pour le modèle actuel — lancez le calcul", "de": "für das aktuelle Modell nicht berechnet — zum Berechnen ausführen", "lt": "dabartiniam modeliui neapskaičiuota — paleiskite skaičiavimą", "pt": "não calculado para o modelo atual — execute para calcular", "it": "non calcolato per il modello attuale — eseguire per calcolare", "no": "ikke beregnet for gjeldende modell — kjør for å beregne", "el": "δεν έχει υπολογιστεί για το τρέχον μοντέλο — εκτελέστε για υπολογισμό"},
    "bbn.computing": {"en": "computing Bayesian inference… (the first run loads the inference engine and can take a minute)", "es": "calculando la inferencia bayesiana… (la primera ejecución carga el motor y puede tardar un minuto)", "fr": "calcul de l'inférence bayésienne… (la première exécution charge le moteur et peut prendre une minute)", "de": "Bayessche Inferenz wird berechnet… (der erste Lauf lädt die Engine und kann eine Minute dauern)", "lt": "skaičiuojamos Bajeso išvados… (pirmas paleidimas įkelia variklį ir gali užtrukti minutę)", "pt": "a calcular a inferência bayesiana… (a primeira execução carrega o motor e pode demorar um minuto)", "it": "calcolo dell'inferenza bayesiana… (la prima esecuzione carica il motore e può richiedere un minuto)", "no": "beregner bayesiansk inferens… (første kjøring laster motoren og kan ta et minutt)", "el": "υπολογισμός μπεϋζιανής συμπερασματολογίας… (η πρώτη εκτέλεση φορτώνει τη μηχανή και μπορεί να πάρει ένα λεπτό)"},
    "bbn.no_path": {"en": "no causal path between the chosen elements", "es": "no hay ruta causal entre los elementos elegidos", "fr": "aucun chemin causal entre les éléments choisis", "de": "kein Kausalpfad zwischen den gewählten Elementen", "lt": "tarp pasirinktų elementų nėra priežastinio kelio", "pt": "não há caminho causal entre os elementos escolhidos", "it": "nessun percorso causale tra gli elementi scelti", "no": "ingen årsakssti mellom de valgte elementene", "el": "δεν υπάρχει αιτιώδης διαδρομή μεταξύ των επιλεγμένων στοιχείων"},
    "bbn.unavailable": {"en": "Bayesian inference needs the optional pgmpy package: pip install \"sespy[bayes]\"", "es": "La inferencia bayesiana necesita el paquete opcional pgmpy: pip install \"sespy[bayes]\"", "fr": "L'inférence bayésienne nécessite le paquet optionnel pgmpy : pip install \"sespy[bayes]\"", "de": "Bayessche Inferenz benötigt das optionale Paket pgmpy: pip install \"sespy[bayes]\"", "lt": "Bajeso išvadoms reikia pasirenkamo paketo pgmpy: pip install \"sespy[bayes]\"", "pt": "A inferência bayesiana precisa do pacote opcional pgmpy: pip install \"sespy[bayes]\"", "it": "L'inferenza bayesiana richiede il pacchetto opzionale pgmpy: pip install \"sespy[bayes]\"", "no": "Bayesiansk inferens trenger den valgfrie pakken pgmpy: pip install \"sespy[bayes]\"", "el": "Η μπεϋζιανή συμπερασματολογία χρειάζεται το προαιρετικό πακέτο pgmpy: pip install \"sespy[bayes]\""},
    "bbn.summary": {"en": "{n} causal paths from {source} to {target}{trunc}", "es": "{n} rutas causales de {source} a {target}{trunc}", "fr": "{n} chemins causaux de {source} vers {target}{trunc}", "de": "{n} Kausalpfade von {source} nach {target}{trunc}", "lt": "{n} priežastiniai keliai iš {source} į {target}{trunc}", "pt": "{n} caminhos causais de {source} para {target}{trunc}", "it": "{n} percorsi causali da {source} a {target}{trunc}", "no": "{n} årsaksstier fra {source} til {target}{trunc}", "el": "{n} αιτιώδεις διαδρομές από {source} προς {target}{trunc}"},
    "bbn.truncated": {"en": " (truncated at the path cap)", "es": " (truncado en el límite de rutas)", "fr": " (tronqué au plafond de chemins)", "de": " (an der Pfadobergrenze abgeschnitten)", "lt": " (nukirpta ties kelių riba)", "pt": " (truncado no limite de caminhos)", "it": " (troncato al limite dei percorsi)", "no": " (avkortet ved stitaket)", "el": " (περικομμένο στο όριο διαδρομών)"},
    "bbn.cut": {"en": "{n} links cut to break cycles inside the path set: {edges}", "es": "{n} enlaces cortados para romper ciclos dentro del conjunto de rutas: {edges}", "fr": "{n} liens coupés pour rompre des cycles dans l'ensemble de chemins : {edges}", "de": "{n} Verbindungen entfernt, um Zyklen in der Pfadmenge aufzubrechen: {edges}", "lt": "{n} ryšiai nutraukti, kad kelių aibėje neliktų ciklų: {edges}", "pt": "{n} ligações cortadas para quebrar ciclos no conjunto de caminhos: {edges}", "it": "{n} collegamenti tagliati per rompere cicli nell'insieme di percorsi: {edges}", "no": "{n} koblinger kuttet for å bryte sykluser i stisettet: {edges}", "el": "{n} δεσμοί κόπηκαν για να σπάσουν κύκλοι στο σύνολο διαδρομών: {edges}"},
    "bbn.target_line": {"en": "{id} · {label}: P(high) {base} → {post} ({delta})", "es": "{id} · {label}: P(alto) {base} → {post} ({delta})", "fr": "{id} · {label} : P(haut) {base} → {post} ({delta})", "de": "{id} · {label}: P(hoch) {base} → {post} ({delta})", "lt": "{id} · {label}: P(aukštas) {base} → {post} ({delta})", "pt": "{id} · {label}: P(alto) {base} → {post} ({delta})", "it": "{id} · {label}: P(alto) {base} → {post} ({delta})", "no": "{id} · {label}: P(høy) {base} → {post} ({delta})", "el": "{id} · {label}: P(υψηλό) {base} → {post} ({delta})"},
    "bbn.about_text": {"en": "A binary belief network over the acyclic causal paths between two elements. Link probabilities come from strength × confidence, the direction of effect from polarity (noisy-OR). Baseline is the marginal with no evidence.", "es": "Una red de creencias binaria sobre las rutas causales acíclicas entre dos elementos. Las probabilidades de enlace vienen de fuerza × confianza; la dirección del efecto, de la polaridad (noisy-OR). La línea base es el marginal sin evidencia.", "fr": "Un réseau de croyances binaire sur les chemins causaux acycliques entre deux éléments. Les probabilités de lien viennent de force × confiance, le sens de l'effet de la polarité (noisy-OR). La référence est la marginale sans évidence.", "de": "Ein binäres Bayes-Netz über die azyklischen Kausalpfade zwischen zwei Elementen. Linkwahrscheinlichkeiten aus Stärke × Konfidenz, Wirkungsrichtung aus der Polarität (Noisy-OR). Basis ist die Randverteilung ohne Evidenz.", "lt": "Dvejetainis tikėjimo tinklas virš aciklinių priežastinių kelių tarp dviejų elementų. Ryšių tikimybės iš stiprumo × pasitikėjimo, poveikio kryptis iš poliškumo (noisy-OR). Bazinė reikšmė – marginalas be įrodymų.", "pt": "Uma rede de crenças binária sobre os caminhos causais acíclicos entre dois elementos. As probabilidades de ligação vêm de força × confiança; a direção do efeito, da polaridade (noisy-OR). A linha de base é a marginal sem evidência.", "it": "Una rete bayesiana binaria sui percorsi causali aciclici tra due elementi. Le probabilità di collegamento derivano da forza × confidenza, la direzione dell'effetto dalla polarità (noisy-OR). La base è la marginale senza evidenza.", "no": "Et binært trosnettverk over de asykliske årsaksstiene mellom to elementer. Koblingssannsynligheter fra styrke × tillit, virkningsretning fra polaritet (noisy-OR). Grunnlinjen er marginalen uten evidens.", "el": "Ένα δυαδικό δίκτυο πεποιθήσεων πάνω στις ακυκλικές αιτιώδεις διαδρομές μεταξύ δύο στοιχείων. Οι πιθανότητες δεσμών προκύπτουν από ισχύ × βεβαιότητα, η κατεύθυνση επίδρασης από την πολικότητα (noisy-OR). Η γραμμή βάσης είναι η περιθώρια χωρίς ένδειξη."},
```

Validate the JSON as in Task 3 Step 4; run the i18n test → PASS.

**Spec deviation (intentional):** the spec's `help.bbn` key is NOT created. The v1.9 Help offcanvas has no per-feature slot — `tb_help_section` in `sespy/modules/topbar_actions.py` renders `manual_section("Intervention")`, i.e. section 19 of `docs/MANUAL.md`, which Task 8 Step 2 extends with the BBN controls, outputs and caveats. A `help.bbn` key would be an unwired translation entry that no test can detect. The spec is amended in Task 8 Step 3.

- [ ] **Step 3: UI** — in `analysis_intervention_ui`, after the `run_diffusion` button (inside the sidebar) add:

```python
                ui.tags.hr(),
                ui.h5(t("bbn.title")),
                ui.p(t("bbn.about_text"), class_="text-muted", style="font-size: 0.8rem;"),
                ui.output_ui("bbn_controls"),
                ui.input_radio_buttons(
                    "bbn_direction", t("bbn.direction"),
                    {"forward": t("bbn.forward"), "diagnostic": t("bbn.diagnostic")},
                    selected="forward",
                ),
                ui.input_action_button(
                    "run_bbn", t("bbn.run"),
                    class_="btn btn-sm btn-outline-primary",
                ),
```

and in the main column after `ui.output_plot("diffusion_chart", ...)`:

```python
                ui.tags.hr(),
                ui.h4(t("bbn.title")),
                ui.output_ui("bbn_summary"),
                ui.output_data_frame("bbn_table"),
```

- [ ] **Step 4: Server** — add `import asyncio`, `import logging`, `from shiny.types import SilentException` and `from .. import bayes` to the imports, and near the top of the module (after the imports):

```python
#: Sentinel for "BBN task in flight". pgmpy 1.1 imports torch when installed:
#: measured 35–65 s on the FIRST import per server process. The import must
#: therefore run off the event loop (extended task + thread), never at module
#: level (tests/test_no_deprecations.py imports every module cold).
_COMPUTING = object()
```

The pattern below mirrors `sespy/modules/analysis_loops.py` (`_unc_task` / `_unc_trigger` / `_unc_observe`): a plain generation cell drops results that arrive after the inputs changed. Append after `diffusion_chart`:

```python
    _bbn_result = reactive.value(None)     # None | _COMPUTING | {"error": key} | query dict
    _bbn_gen = [0]                          # plain cell, NOT reactive (avoids a self-loop)

    def _bbn_work(isa, src, tgt, direction):
        """Runs in a worker thread: the lazy pgmpy import lives here."""
        try:
            model, info = bayes.build_path_bbn(isa, src, tgt)
        except bayes.BayesUnavailable:
            return {"error": "bbn.unavailable"}
        if model is None:
            return {"error": "bbn.no_path"}
        evidence = {src: 1} if direction == "forward" else {tgt: 1}
        r = bayes.query_path_bbn(model, info, evidence)
        r["source"], r["target"] = src, tgt
        return r

    @reactive.extended_task
    async def _bbn_task(isa, src, tgt, direction, gen):
        return (gen, await asyncio.to_thread(_bbn_work, isa, src, tgt, direction))

    @output
    @render.ui
    def bbn_controls():
        event_bus.isa_change.get()
        els = project_data.get().isa_data.elements
        if len(els) < 2:
            return ui.div()
        choices = {el.id: f"{el.id} · {el.label}" for el in els}
        with reactive.isolate():
            try:
                cur_s = input.bbn_source()
            except Exception:
                cur_s = None
            try:
                cur_t = input.bbn_target()
            except Exception:
                cur_t = None
        return ui.div(
            ui.input_select("bbn_source", t("bbn.source"), choices,
                            selected=cur_s if cur_s in choices else els[0].id),
            ui.input_select("bbn_target", t("bbn.target"), choices,
                            selected=cur_t if cur_t in choices else els[-1].id),
        )

    @reactive.effect
    def _invalidate_bbn():
        # Any feeding input change clears the previous result (same rule as
        # diffusion): a table computed for another pair must never be read
        # as the current one's.
        event_bus.isa_change.get()
        for read in (input.bbn_source, input.bbn_target, input.bbn_direction):
            try:
                read()
            except Exception:
                pass
        _bbn_gen[0] += 1          # an in-flight result for the old inputs is now stale
        _bbn_result.set(None)

    @reactive.effect
    @reactive.event(input.run_bbn, ignore_init=True)
    def _run_bbn():
        try:
            src, tgt = input.bbn_source(), input.bbn_target()
        except Exception:
            return
        if not src or not tgt:
            return
        _bbn_gen[0] += 1
        _bbn_result.set(_COMPUTING)
        _bbn_task(project_data.get().isa_data, src, tgt, input.bbn_direction(), _bbn_gen[0])

    @reactive.effect
    def _bbn_observe():
        try:
            gen, r = _bbn_task.result()
        except SilentException:
            raise
        except Exception:                       # noqa: BLE001 — real task error: clear, don't crash
            logging.getLogger(__name__).exception("intervention bbn task failed")
            _bbn_result.set(None)
            return
        if gen != _bbn_gen[0]:
            return
        _bbn_result.set(r)

    @output
    @render.ui
    def bbn_summary():
        r = _bbn_result.get()
        if r is None:
            return ui.p(t("bbn.hint"), class_="text-muted", style="font-size: 0.85rem;")
        if r is _COMPUTING:       # must precede `"error" in r`: `in` on object() raises TypeError
            return ui.p(t("bbn.computing"), class_="text-muted", style="font-size: 0.85rem;")
        if "error" in r:
            return ui.p(t(r["error"]), class_="text-muted")
        by_id = {el.id: el.label for el in project_data.get().isa_data.elements}
        focus = r["target"] if r["evidence"].get(r["source"]) == 1 else r["source"]
        row = next(x for x in r["rows"] if x["id"] == focus)
        lines = [ui.p(ui.tags.strong(t(
            "bbn.summary", n=r["n_paths"], source=r["source"], target=r["target"],
            trunc=t("bbn.truncated") if r["truncated"] else "")))]
        lines.append(ui.p(t("bbn.target_line", id=focus, label=by_id.get(focus, focus),
                            base=f"{row['baseline']:.2f}", post=f"{row['p_high']:.2f}",
                            delta=f"{row['delta']:+.2f}")))
        if r["cut_edges"]:
            lines.append(ui.p(t("bbn.cut", n=len(r["cut_edges"]),
                                edges=", ".join(f"{u}→{v}" for u, v in r["cut_edges"])),
                              class_="text-warning", style="font-size: 0.85rem;"))
        return ui.div(*lines)

    @output
    @render.data_frame
    def bbn_table():
        import pandas as pd

        r = _bbn_result.get()
        cols = ["id", "label", "type", "baseline", "posterior", "delta"]
        if not isinstance(r, dict) or "error" in r:     # None, _COMPUTING, or an error
            return pd.DataFrame(columns=cols)
        by_id = {el.id: el for el in project_data.get().isa_data.elements}
        return pd.DataFrame([{
            "id": x["id"],
            "label": by_id[x["id"]].label if x["id"] in by_id else x["id"],
            "type": by_id[x["id"]].type if x["id"] in by_id else "",
            "baseline": round(x["baseline"], 3),
            "posterior": round(x["p_high"], 3),
            "delta": round(x["delta"], 3),
        } for x in r["rows"]], columns=cols)
```

- [ ] **Step 5: e2e** — in `tests/test_intervention_e2e.py`, before `print("\nintervention e2e assertions pass")`:

```python
        # --- Option B: path-set BBN, forward query D001 -> GB01 (2 paths, one
        # '-' hop each, so the target's P(high) must FALL) ---
        await page.wait_for_selector("#intervention-bbn_summary", timeout=15000)
        assert "not computed" in (await page.inner_text("#intervention-bbn_summary"))
        await page.select_option("#intervention-bbn_source", "D001")
        await page.select_option("#intervention-bbn_target", "GB01")
        await page.click("#intervention-run_bbn")
        # The task runs off the flush, so the "computing" line must appear
        # promptly (proves the event loop was not blocked by the import)...
        await page.wait_for_function(
            "() => (document.getElementById('intervention-bbn_summary')?.innerText || '')"
            ".includes('computing')", timeout=10000)
        # ...and the result may take up to ~65 s on a fresh server: the first
        # pgmpy import loads torch. 120 s stays under run_e2e's SCRIPT_TIMEOUT.
        await page.wait_for_function(
            "() => { const s = document.getElementById('intervention-bbn_summary')?.innerText || '';"
            " return s.includes('causal paths') || s.includes('pgmpy'); }", timeout=120000)
        bbn_text = (await page.inner_text("#intervention-bbn_summary")).strip()
        assert "2 causal paths from D001 to GB01" in bbn_text, f"unexpected summary: {bbn_text!r}"
        assert "GB01" in bbn_text and "(-" in bbn_text, \
            f"expected a negative delta on GB01: {bbn_text!r}"
        n_rows = await page.evaluate(
            "() => document.querySelectorAll('#intervention-bbn_table table tbody tr').length")
        assert n_rows == 7, f"expected 7 path-set nodes in the table, got {n_rows}"
        # Changing the direction invalidates the result.
        await page.click("#intervention-bbn_direction input[value='diagnostic']")
        for _ in range(20):
            await page.wait_for_timeout(500)
            if "not computed" in (await page.inner_text("#intervention-bbn_summary")):
                break
        assert "not computed" in (await page.inner_text("#intervention-bbn_summary")), \
            "stale BBN result survived a direction change"
        print(f"intervention bbn: OK ({bbn_text[:80]!r})")
```

(Path set D001→GB01 on the sample: D001, A001, P001, MPF1, ES01, ES03, GB01 = 7 nodes.)

- [ ] **Step 6: Run the e2e alone** as in Task 3 Step 8 with `tests/test_intervention_e2e.py`.
Expected: prints `intervention bbn: OK` on the FIRST attempt against a fresh server (the script now takes up to ~90 s cold). The "rerun once for the cold-server warm-up flake" advice does NOT apply to the BBN assertions: a rerun would pass only because pgmpy is already cached in the server process, which would mask a real freeze. Kill the server afterwards.

- [ ] **Step 7: Commit**

```
git add sespy/modules/analysis_intervention.py sespy/translations/core.json tests/test_i18n.py tests/test_intervention_e2e.py
git commit -m "feat(intervention): Bayesian inference block over the source→target path set"
```

---

### Task 8: Manual, changelog, version, full gate

**Files:**
- Modify: `docs/MANUAL.md` (Contents list ~lines 11–33; section 10 ~line 158; section 12 ~line 184; section 19 ~line 294; new Part III section inserted after the section 42 paragraph and BEFORE the `---` that precedes `# Part IV — References`, with 43→44 and 44→45 renumbered), `docs/screenshots/*.png` (regenerated), `CHANGELOG.md`, `sespy/__init__.py`, `pyproject.toml` (`version`)

- [ ] **Step 1: Check nothing cross-references the two renumbered sections**

Run: `grep -n "section 43\|section 44\|Section 43\|Section 44" docs/MANUAL.md README.md sespy -r`
Expected: no hits (if there are, update them to 44/45 in the same edit).

- [ ] **Step 2: Manual edits**

Section 10, `**Controls.**` paragraph: after the blind-mode sentence add: `"Bayesian consensus (posteriors)" adds two columns, P(+) with its 95% credible interval and the most probable strength, weights every rating by its rater's confidence, and switches the contested criterion to "the interval straddles 0.5" (section 43). The stored consensus is not changed.`

Section 19, `**Purpose.**`: change to `Three what-if tools: remove elements and watch centrality shift, inject tokens at one element and watch them spread (section 39), and ask a Bayesian belief network how likely a change at one element makes a change at another (section 43).` Append to `**Controls.**`: `In "Bayesian inference (path set)": "From", "To", "Query" (forward: the source is high; diagnostic: the target is high), "Run inference".` Append to `**Outputs.**`: `"Bayesian inference" reports the number of causal paths used, the focus element's baseline and posterior probability of being high, any links cut to break cycles, and a table of baseline, posterior and change for every element on the paths.` Append to `**Caveats.**`: `The belief network covers only the acyclic paths between the two chosen elements, not the whole diagram, and needs the optional pgmpy package.`

Section 12 (Loop Analysis) `**Controls.**`: append `"Flip signs by rater posterior" makes the Monte Carlo sign flips follow the rater posterior (section 43) instead of the confidence heuristic.`

Section 19 note: these section 19 additions ARE the Help offcanvas content for the BBN block (`manual_section` renders the active panel's manual section by nav label); no `help.bbn` key exists, see Task 7.

New Part III section. Placement matters: `## 43. Foundations` sits INSIDE Part IV (after the `# Part IV — References` header and its preamble), so do NOT anchor on it. Insert the block immediately after the section 42 paragraph (`## 42. Stakeholder power × interest`, ~line 444–446) and before the `---` that precedes `# Part IV — References` (~line 448). Then renumber `## 43. Foundations` → `## 44. Foundations` and `## 44. Literature that shaped v1.0 to v1.7` → `## 45. Literature that shaped v1.0 to v1.7`. In the Contents list (~lines 22–26): append ` · 43. Bayesian options: rater posteriors and the path-set belief network` to the Part III line and change the Part IV line to `44. Foundations · 45. Literature that shaped v1.0 to v1.7` (Contents entries use the full heading text, matching the existing convention).

```markdown
## 43. Bayesian options: rater posteriors and the path-set belief network

Both are opt-in and neither writes to the stored consensus.

**Rater posteriors.** Each rating of a connection is treated as a partial observation weighted by the rater's confidence (confidence 5 counts as one observation, confidence 1 as a fifth). The sign gets a Beta(1,1) prior updated by the weighted counts of "+" and "−" ratings; the panel shows the posterior probability of a positive sign with its 95% credible interval. The strength gets a Dirichlet(1,1,1) prior over weak, medium and strong; the panel shows the most probable strength and its posterior mean. A connection is contested under this view when raters disagree on the sign and the credible interval still straddles 0.5; a unanimous edge is never marked contested, however few its raters, and a lone dissenter among many is discounted. With the flat prior a unanimous edge never reaches certainty: three confidence-5 raters still leave a one-in-five chance the sign is wrong, and that residual shrinks as raters accumulate. On the Loop Analysis panel the Monte Carlo option can flip each edge with the posterior probability that its stored sign is wrong, instead of the confidence heuristic of section 37; an edge whose stored majority sign disagrees with the confidence-weighted posterior therefore flips more often than not, and edges nobody has rated keep the heuristic.

**Path-set belief network.** A belief network must be acyclic, and a causal loop diagram is not. SESPy therefore builds one per question: for a chosen source and target it takes the simple causal paths between them (section 35), unions them, and if the union still contains a cycle removes the weakest link on it, says so, and counts only the paths left intact. Inference is exact but the engine is loaded on first use, so the first run in a session can take up to a minute. Every element on the paths becomes a binary node (low, high). Its probability of being high given its parents follows a noisy-OR: each parent that is "active" (high through a positive link, or low through a negative one) independently pushes the child high with a link probability derived from strength and confidence (weak 0.30, medium 0.55, strong 0.80 at confidence 5, halved at confidence 1), and a leak of 0.05 stands for everything outside the paths. Inference is exact (variable elimination), so the answer is reproducible. A forward query fixes the source high and reads the change everywhere downstream; a diagnostic query fixes the target high and asks how likely that makes the source. Read the change against the baseline: the baseline is the marginal with nothing observed, so a small change on a strongly connected element is still a real signal.
```

Bump the version line at the top: `**Version 1.10.0 · September 2026**`.

- [ ] **Step 3: Changelog + version**

`CHANGELOG.md`, new entry at the top:

```markdown
## [1.10.0] — 2026-09-08

- **Bayesian consensus (Rate Connections).** Opt-in checkbox showing a Beta
  posterior P(+) with its 95% credible interval and a Dirichlet posterior
  strength per connection, ratings weighted by rater confidence. The
  contested criterion under the toggle is "interval straddles 0.5". The
  stored consensus is untouched. Library: `polarity_posterior`,
  `strength_posterior`, `bayesian_consensus`, `bayesian_contested`.
- **Posterior sign flips (Loop Analysis).** `uncertainty_scores(flip_mode=
  "posterior")` flips edge signs by the rater posterior instead of the
  confidence heuristic; unrated edges keep the heuristic.
- **Bayesian inference (Intervention).** A binary noisy-OR belief network
  over the acyclic causal paths between two chosen elements, exact
  inference via pgmpy (new optional extra `sespy[bayes]`), forward and
  diagnostic queries, cut links reported. Library: `sespy/bayes.py`.
- Manual: sections 10, 12, 19 updated; new section 43 (Bayesian options);
  screenshots regenerated.
- Deployment note: the laguna env needs `micromamba install -n shiny pgmpy`
  once (run as the env owner), verified as the `shiny` user with
  `python3 -s`, before this release. conda-forge pgmpy does not pull
  pytorch; if pytorch is present in the env the first inference per worker
  takes 35–65 s in a background thread (~350 MB RSS), otherwise a few
  seconds.
```

`sespy/__init__.py`: `__version__ = "1.10.0"`; `pyproject.toml`: `version = "1.10.0"`.

The spec was already amended to match this plan on 2026-09-08 after the workflow review (contested criterion, stored-sign flip probability, intact-path count, extended task, no `help.bbn`); no spec edit is needed in this task.

- [ ] **Step 4: Unit gate**

Run: `micromamba run -n shiny pytest tests/ -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`
Expected: all PASS, including `test_manual_version_line_matches_package`, `test_every_nav_panel_has_a_manual_section`, `test_no_deprecations`.

- [ ] **Step 5: Full e2e gate**

Kill any process on port 8000. Run detached (PowerShell): `Start-Process -NoNewWindow -RedirectStandardOutput e2e.log -RedirectStandardError e2e.err micromamba -ArgumentList 'run','-n','shiny','python','tests/run_e2e.py'` and Monitor `e2e.log` until the summary line. Nothing else heavy may run meanwhile.
Expected: `32/32 e2e scripts passed` (30 discovered scripts + wizard no-key + wizard fake-key). If a script fails, rerun it alone once (cold-server warm-up flake) before treating it as a regression — EXCEPT a failure in the intervention script's BBN assertions, which is a real regression (the retry would pass on the warm server and hide it; see Task 7 Step 6). The intervention script now takes up to ~90 s cold, within `SCRIPT_TIMEOUT = 300`.

- [ ] **Step 5b: Regenerate the manual screenshots**

The three panels the manual rewrites (Rate Connections, Loop Analysis, Intervention) all gained sidebar controls, so the Sep 5 captures would contradict the new **Controls** text; `deploy.sh` ships them to laguna. Kill any process on port 8000, start a server as in Task 3 Step 8, then run:

`micromamba run -n shiny python tests/make_docs_screenshots.py --port 8000`

(~2.5 min, rewrites all 24 PNGs). Kill the server afterwards.
Expected: exit 0, no FAIL lines. Open `docs/screenshots/rate.png` and `loops.png` and confirm the "Bayesian consensus (posteriors)" and "Flip signs by rater posterior" checkboxes are visible. In `intervention.png` the BBN block is at the bottom of the sidebar and may fall below the 900 px fold; if so, say that in the commit body — a dedicated capture is a follow-up, not part of this task.

- [ ] **Step 6: Commit**

```
git add docs/MANUAL.md docs/screenshots/*.png CHANGELOG.md sespy/__init__.py pyproject.toml
git commit -m "chore(release): v1.10.0 — Bayesian consensus + path-set BBN"
```

Tagging, pushing and deploying are the owner's release steps and are not part of this plan.
