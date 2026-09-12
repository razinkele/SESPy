# BBN Link Probabilities from Rater Posteriors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `link_mode="posterior"` to the path-set belief network so a rated connection's sign probability and expected strength come from the Option A rater posteriors, with the sign marginalised inside the noisy-OR.

**Architecture:** `sespy/bayes.py` gains `link_params` (per-edge `(q, p_plus)` for either mode), a `_noisy_or` core over resolved parameters, and a `link_mode` keyword threaded through `path_set_dag`, `model_from_dag`, `build_path_bbn` and `attribute_paths`. The Intervention module gains one checkbox, passes the mode to the worker, and prints a rated-edge count line. Stored mode is bit-identical to v1.11.0.

**Tech Stack:** Python 3.11, Shiny for Python 1.7, networkx, scipy (already a hard dependency), pgmpy ≥ 1.0 (optional extra, installed in the `shiny` env), pytest, Playwright standalone e2e scripts.

**Spec:** `docs/superpowers/specs/2026-09-12-sespy-bbn-posterior-links-design.md`

## Global Constraints

- Run Python only via `micromamba run -n shiny python ...` / `micromamba run -n shiny pytest ...`; never create a venv, never `pip install`. No python on PATH.
- Multi-line `python -c` breaks on this Windows shell: write scratch `.py` files for probes. Bash `python - <<EOF` hangs here.
- Unit gate: `micromamba run -n shiny pytest tests/ -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`
- E2E gate: `micromamba run -n shiny python tests/run_e2e.py` (full, never `-k "not e2e"`); kill any listener on port 8000 first; run nothing heavy alongside. Runs longer than 10 min die in a backgrounded shell call: launch detached with `Start-Process` from the PowerShell tool and poll the log with `Start-Sleep 60` inside bounded PowerShell calls; never rely on a background monitor.
- `sespy/translations/core.json`: keys under `"translation"`; `help.body` is the LAST entry (no trailing comma); insert new keys directly after the `"bbn.low"` line (5623). Every key needs all nine languages: en, es, fr, de, lt, pt, it, no, el. Copy each string from this plan character for character.
- pgmpy is imported only inside function bodies in `sespy/bayes.py`; `import sespy.bayes` must succeed without pgmpy; pgmpy tests carry the file's `@needs_pgmpy` marker.
- The first pgmpy import per process takes 35–65 s; do not kill a test run that looks stuck in its first model test; give pytest a 300 s timeout.
- Stored mode (`link_mode="stored"`, the default) must stay bit-identical: `_SAMPLE_CPDS` and every existing golden are unchanged.
- E2E selectors are namespaced ids (`#intervention-…`), never bare `text=`.
- Invalidate on every feeding input: the new checkbox must be read in `_invalidate_bbn`.
- Commit after every task with the trailer:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FeeVsn6xUxEtPnY7vSrijN
  ```
  Use the PowerShell tool with `$msg = @'…'@; git commit -m $msg` for multi-line messages.

---

## File map

| File | Responsibility |
|---|---|
| `sespy/bayes.py` (modify) | `LinkMode`, `link_params`, `_noisy_or`, `noisy_or_p_high(link_mode=)`, `link_mode` on `path_set_dag` / `model_from_dag` / `build_path_bbn` / `attribute_paths` |
| `tests/test_bayes.py` (modify) | Unit tests; `_chain` gains `ratings_ab` |
| `sespy/translations/core.json`, `tests/test_i18n.py` (modify) | Two keys + tests |
| `sespy/modules/analysis_intervention.py` (modify) | Checkbox, invalidation, worker `link_mode`, summary line |
| `tests/test_intervention_e2e.py` (modify) | Posterior toggle block |
| `docs/MANUAL.md`, `CHANGELOG.md`, `README.md`, `sespy/__init__.py`, `pyproject.toml` (modify) | Docs + version 1.12.0 |

Verified numbers (2026-09-12, final formula `q = s_bar`, env `shiny`; `math.isclose(abs_tol=1e-6)` unless marked exact):

| Fixture | Result |
|---|---|
| 3 unanimous conf-5 '+' strong raters | p_plus 0.8 (exact), s_bar = q = 0.675; stored q 0.8 |
| 1 '+' vs 1 '−' strong conf 5 | p_plus 0.5 (exact), q 0.65, activation high = low = 0.35875 |
| 2 '+' vs 1 '−' strong conf 5 | p_plus 0.6, q 0.675 |
| Chain A→B→C, A→B rated 1-vs-1, evidence {A:1} | stored dB 0.38, dC 0.2888; posterior dB 0.0, dC 0.0; B baseline stored 0.43, posterior 0.35875 |
| Chain, A→B rated 2-vs-1 | posterior dB 0.064125, dC 0.048735; attribute_paths single route: stored 0.2888, posterior 0.048735 |
| Cycle fixture, a→b rated (weak '+', weak '−'), b→a rated 3× strong '+' | a→b q: stored 0.8 / posterior 0.45; b→a: 0.15 / 0.675; stored cut [("b","a")], posterior cut [("a","b")]; 3 paths, 5 edges, 1 rated edge either way |
| Unknown polarity "?", strong conf 5 | stored: P(high) = LEAK in both states |
| Sample D001→GB01 | 7 edges, 0 rated; `_SAMPLE_CPDS` bit-identical in posterior mode; forward GB01 delta −0.0503 |

---

### Task 1: `link_params`, `_noisy_or`, and the sign mixture in `noisy_or_p_high`

**Files:**
- Modify: `sespy/bayes.py:17-29` (imports/typing), `:101-112` (`noisy_or_p_high`)
- Test: `tests/test_bayes.py`

**Interfaces:**
- Consumes: `network.polarity_posterior(connection)["p_plus"]`, `network.strength_posterior(connection)["mean"]` (dict weak/medium/strong), `link_probability`, `STRENGTH_LINK`, `LEAK`.
- Produces: `LinkMode = Literal["stored", "posterior"]`; `link_params(connection, link_mode="stored") -> tuple[float, float]`; `_noisy_or(states, params) -> float` with `params` a list of `(q, p_plus)`; `noisy_or_p_high(states, parents, *, link_mode="stored")` unchanged for existing callers.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bayes.py` (after the last test). `Rating` must be added to the import line 14: `from sespy.data_structure import Connection, Element, IsaData, Rating, load_sample`.

```python
def _r(i, strength="strong", polarity="+", confidence=5):
    return Rating(f"r{i}", strength=strength, confidence=confidence, polarity=polarity)


def test_link_params_stored_mode_is_link_probability_and_hard_sign():
    plus = Connection("a", "b", polarity="+", strength="strong", confidence=5)
    minus = Connection("a", "b", polarity="-", strength="weak", confidence=2)
    assert bayes.link_params(plus) == (bayes.link_probability(plus), 1.0)
    assert bayes.link_params(minus, "stored") == (bayes.link_probability(minus), 0.0)
    # unknown polarity: inactive in both states, q exactly 0 (bypasses the clamp)
    assert bayes.link_params(Connection("a", "b", polarity="?", strength="strong", confidence=5)) == (0.0, 0.0)
    # posterior mode without ratings is stored mode
    assert bayes.link_params(plus, "posterior") == bayes.link_params(plus, "stored")


def test_link_params_posterior_unanimous_three_raters():
    c = Connection("a", "b", strength="strong", confidence=5, ratings=[_r(i) for i in range(3)])
    q, p = bayes.link_params(c, "posterior")
    assert p == 0.8                                     # Beta(4,1) mean, exact
    assert math.isclose(q, 0.675, abs_tol=1e-6)         # 1/6·0.30 + 1/6·0.55 + 2/3·0.80
    assert bayes.link_params(c, "stored") == (0.8, 1.0)


def test_link_params_posterior_split_and_majority():
    split = Connection("a", "b", strength="strong", confidence=5,
                       ratings=[_r(1, polarity="+"), _r(2, polarity="-")])
    q, p = bayes.link_params(split, "posterior")
    assert p == 0.5 and math.isclose(q, 0.65, abs_tol=1e-6)
    maj = Connection("a", "b", strength="strong", confidence=5,
                     ratings=[_r(1), _r(2), _r(3, polarity="-")])
    q2, p2 = bayes.link_params(maj, "posterior")
    assert math.isclose(p2, 0.6, abs_tol=1e-9) and math.isclose(q2, 0.675, abs_tol=1e-6)


def test_noisy_or_split_sign_activates_symmetrically():
    split = Connection("a", "b", strength="strong", confidence=5,
                       ratings=[_r(1, polarity="+"), _r(2, polarity="-")])
    hi = bayes.noisy_or_p_high((1,), [("a", split)], link_mode="posterior")
    lo = bayes.noisy_or_p_high((0,), [("a", split)], link_mode="posterior")
    assert hi == lo and math.isclose(hi, 0.35875, abs_tol=1e-9)   # 1 − 0.95·(1 − 0.65·0.5)


def test_noisy_or_mixture_reduces_to_v1_10_formula_without_ratings():
    plus = Connection("p", "c", polarity="+", strength="strong", confidence=5)   # q 0.8
    minus = Connection("m", "c", polarity="-", strength="weak", confidence=5)    # q 0.3
    parents = [("p", plus), ("m", minus)]
    expected = {(0, 0): 1 - 0.95 * 0.7, (0, 1): bayes.LEAK,
                (1, 0): 1 - 0.95 * 0.2 * 0.7, (1, 1): 1 - 0.95 * 0.2}
    for states, want in expected.items():
        stored = bayes.noisy_or_p_high(states, parents)
        post = bayes.noisy_or_p_high(states, parents, link_mode="posterior")
        assert stored == post                       # bit-identical, not merely close
        assert math.isclose(stored, want)
        params = [bayes.link_params(c) for _, c in parents]
        assert bayes._noisy_or(states, params) == stored


def test_noisy_or_unknown_polarity_is_inactive_in_both_modes():
    unk = Connection("u", "c", polarity="?", strength="strong", confidence=5)
    for mode in ("stored", "posterior"):
        for s in (0, 1):
            assert math.isclose(bayes.noisy_or_p_high((s,), [("u", unk)], link_mode=mode), bayes.LEAK)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q -k "link_params or noisy_or_split or reduces_to or unknown_polarity"`
Expected: FAIL (`AttributeError: module 'sespy.bayes' has no attribute 'link_params'` and `TypeError: ... unexpected keyword argument 'link_mode'`).

- [ ] **Step 3: Implement**

In `sespy/bayes.py` change the imports (lines 17–24) to:

```python
from __future__ import annotations

import itertools
from typing import Literal

import networkx as nx

from .data_structure import IsaData
from .network import causal_paths, polarity_posterior, strength_posterior

LinkMode = Literal["stored", "posterior"]
```

Replace `noisy_or_p_high` (lines 101–112) with:

```python
def link_params(connection, link_mode: LinkMode = "stored") -> tuple[float, float]:
    """(q, p_plus) for one edge: the noisy-OR link strength and the
    probability that the link is positive.

    "stored": q = link_probability(connection); p_plus = 1.0 for polarity
    '+', 0.0 for '-'. Any other polarity returns (0.0, 0.0) — q of exactly 0,
    bypassing link_probability's [0.01, 0.99] clamp — so the edge is inactive
    in both parent states, as the v1.10.0 noisy-OR treated it.
    "posterior", when connection.ratings is non-empty: p_plus is the Beta
    posterior mean of network.polarity_posterior and q the expected strength
    under the Dirichlet posterior of network.strength_posterior,
    s_bar = Σ_k mean[k]·STRENGTH_LINK[k], clamped to [0.01, 0.99]. Rater
    confidence enters once, as the pseudo-count weight inside both
    posteriors; no second confidence factor is applied (Decision 5 of the
    2026-09-12 design). "posterior" with no ratings is identical to
    "stored". Pure; ~3 ms for a rated edge (two scipy beta.ppf calls)."""
    if link_mode == "posterior" and connection.ratings:
        p_plus = polarity_posterior(connection)["p_plus"]
        mean = strength_posterior(connection)["mean"]
        s_bar = sum(mean[k] * STRENGTH_LINK[k] for k in STRENGTH_LINK)
        return min(0.99, max(0.01, s_bar)), float(p_plus)
    if connection.polarity == "+":
        return link_probability(connection), 1.0
    if connection.polarity == "-":
        return link_probability(connection), 0.0
    return 0.0, 0.0


def _noisy_or(states: tuple[int, ...], params: list[tuple[float, float]]) -> float:
    """P(child high | parent states) from resolved (q, p_plus) pairs.

    The sign of each link is a latent Bernoulli(p_plus) marginalised out:
    a_i = p_plus_i when the parent is high, 1 − p_plus_i when it is low, and
    P(high) = 1 − (1 − LEAK)·Π_i (1 − q_i·a_i). With p_plus ∈ {0, 1} this is
    the v1.10.0 formula exactly (an inactive parent multiplies by 1.0). At
    p_plus = 0.5 both parent states give the same activation, so the child
    is independent of that parent. Pure."""
    prod = 1.0 - LEAK
    for state, (q, p_plus) in zip(states, params):
        a = p_plus if state == 1 else 1.0 - p_plus
        prod *= 1.0 - q * a
    return 1.0 - prod


def noisy_or_p_high(states: tuple[int, ...], parents: list, *,
                    link_mode: LinkMode = "stored") -> float:
    """P(child high | parent states) for (parent_id, Connection) pairs —
    _noisy_or over link_params resolved per call. Pure."""
    return _noisy_or(states, [link_params(conn, link_mode) for _, conn in parents])
```

- [ ] **Step 4: Run the whole bayes file**

Run: `micromamba run -n shiny pytest tests/test_bayes.py tests/test_bayes_consensus.py -q`
Expected: all PASS, including the pre-existing `test_noisy_or_two_parents_plus_and_minus`, `test_build_path_bbn_cpt_column_order_matches_noisy_or` and `test_model_from_dag_matches_v1_10_cpds_on_the_sample` (stored mode bit-identical) and `test_import_bayes_does_not_import_pgmpy` (network.py imports scipy lazily inside `polarity_posterior`, and never pgmpy).

- [ ] **Step 5: Commit**

```
git add sespy/bayes.py tests/test_bayes.py
git commit -m "feat(bayes): link_params and the sign-mixture noisy-OR (posterior link mode)"
```

---

### Task 2: Thread `link_mode` through the DAG cut, the model, and the attribution

**Files:**
- Modify: `sespy/bayes.py` — `path_set_dag` (`:54-98`), `model_from_dag` (`:153-190`), `build_path_bbn` (`:193-200`), `attribute_paths` (`:225-255`)
- Test: `tests/test_bayes.py` (`_chain` at line 108 gains a parameter)

**Interfaces:**
- Consumes: `link_params`, `_noisy_or` (Task 1).
- Produces: `path_set_dag(isa, source, target, *, max_length=8, max_paths=100, link_mode="stored")`, `model_from_dag(info, *, link_mode="stored")`, `build_path_bbn(..., link_mode="stored")`, `attribute_paths(info, evidence, focus, *, link_mode="stored")`. Task 4 calls the first, second and fourth with the UI's mode.

- [ ] **Step 1: Write the failing tests**

Change `_chain` (line 108–110) to:

```python
def _chain(sign_ab="+", ratings_ab=None):
    return _isa([Connection("A", "B", polarity=sign_ab, strength="strong", confidence=5,
                            ratings=list(ratings_ab or [])),
                 Connection("B", "C", polarity="+", strength="strong", confidence=5)])
```

Append to `tests/test_bayes.py`:

```python
_SPLIT = [_r(1, polarity="+"), _r(2, polarity="-")]
_MAJORITY = [_r(1), _r(2), _r(3, polarity="-")]


def _forward(isa, mode):
    info = bayes.path_set_dag(isa, "A", "C", link_mode=mode)
    r = bayes.query_path_bbn(bayes.model_from_dag(info, link_mode=mode), info, {"A": 1})
    return {x["id"]: x for x in r["rows"]}


@needs_pgmpy
def test_contested_link_carries_no_information_in_posterior_mode():
    stored = _forward(_chain(ratings_ab=_SPLIT), "stored")
    post = _forward(_chain(ratings_ab=_SPLIT), "posterior")
    assert math.isclose(stored["B"]["delta"], 0.38) and math.isclose(stored["C"]["delta"], 0.2888)
    assert abs(post["B"]["delta"]) < 1e-9 and abs(post["C"]["delta"]) < 1e-9
    assert math.isclose(stored["B"]["baseline"], 0.43) and math.isclose(post["B"]["baseline"], 0.35875)


@needs_pgmpy
def test_majority_link_shrinks_the_forward_effect_in_posterior_mode():
    stored = _forward(_chain(ratings_ab=_MAJORITY), "stored")
    post = _forward(_chain(ratings_ab=_MAJORITY), "posterior")
    assert math.isclose(stored["C"]["delta"], 0.2888)
    assert math.isclose(post["B"]["delta"], 0.064125, abs_tol=1e-6)
    assert math.isclose(post["C"]["delta"], 0.048735, abs_tol=1e-6)


@needs_pgmpy
def test_attribute_paths_uses_the_link_mode_of_its_chains():
    info = bayes.path_set_dag(_chain(ratings_ab=_MAJORITY), "A", "C")
    stored = bayes.attribute_paths(info, {"A": 1}, "C")[0]["delta"]
    post = bayes.attribute_paths(info, {"A": 1}, "C", link_mode="posterior")[0]["delta"]
    assert math.isclose(stored, 0.2888) and math.isclose(post, 0.048735, abs_tol=1e-6)


@needs_pgmpy
def test_build_path_bbn_passes_link_mode_through():
    isa = _chain(ratings_ab=_MAJORITY)
    model, info = bayes.build_path_bbn(isa, "A", "C", link_mode="posterior")
    direct = bayes.model_from_dag(info, link_mode="posterior")
    assert bayes.query_path_bbn(model, info, {"A": 1}) == bayes.query_path_bbn(direct, info, {"A": 1})


def _cycle_isa_with_ratings():
    return _isa([
        Connection("s", "a"), Connection("s", "b"),
        Connection("a", "b", strength="strong", confidence=5,
                   ratings=[_r(1, strength="weak"), _r(2, strength="weak", polarity="-")]),
        Connection("b", "a", strength="weak", confidence=1, ratings=[_r(i) for i in range(3)]),
        Connection("a", "t"), Connection("b", "t"),
    ])


def test_path_set_dag_cut_follows_the_posterior_link_strength():
    isa = _cycle_isa_with_ratings()
    stored = bayes.path_set_dag(isa, "s", "t")
    post = bayes.path_set_dag(isa, "s", "t", link_mode="posterior")
    assert stored["cut_edges"] == [("b", "a")]
    assert post["cut_edges"] == [("a", "b")]
    for r in (stored, post):
        assert nx.is_directed_acyclic_graph(nx.DiGraph([(u, v) for u, v, _ in r["edges"]]))
        assert len(r["paths"]) == 3 and len(r["edges"]) == 5
        assert sum(1 for _, _, c in r["edges"] if c.ratings) == 1
    assert set(stored["nodes"]) == set(post["nodes"])      # same set; order may differ


@needs_pgmpy
def test_sample_goldens_hold_in_posterior_mode_because_nothing_is_rated():
    isa = load_sample(SAMPLE)
    info = bayes.path_set_dag(isa, "D001", "GB01", link_mode="posterior")
    assert [(u, v) for u, v, _ in info["edges"]] == [
        ("A001", "P001"), ("D001", "A001"), ("ES01", "GB01"), ("ES03", "GB01"),
        ("MPF1", "ES01"), ("MPF1", "ES03"), ("P001", "MPF1")]
    assert sum(1 for _, _, c in info["edges"] if c.ratings) == 0
    model = bayes.model_from_dag(info, link_mode="posterior")
    for node, expected in _SAMPLE_CPDS.items():
        got = [float(x) for x in model.get_cpds(node).values.flatten()]
        assert got == [float(x) for x in got] and len(got) == len(expected)
        for g, e in zip(got, expected):
            assert math.isclose(g, e, abs_tol=1e-5), (node, got, expected)
    gb = next(x for x in bayes.query_path_bbn(model, info, {"D001": 1})["rows"] if x["id"] == "GB01")
    assert math.isclose(gb["delta"], -0.0503, abs_tol=1e-3)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q -k "posterior_mode or link_mode or passes_link_mode or follows_the_posterior"`
Expected: FAIL with `TypeError: ... unexpected keyword argument 'link_mode'`.

- [ ] **Step 3: Implement**

`path_set_dag`: signature becomes

```python
def path_set_dag(isa: IsaData, source: str, target: str, *,
                 max_length: int = 8, max_paths: int = 100,
                 link_mode: LinkMode = "stored") -> dict:
```

append to its docstring: `link_mode selects the link strength used to rank edges in the cycle cut (link_params(conn, link_mode)[0]); "posterior" can cut a different edge than "stored" when raters disagree, and the node set is the same in both modes (only the topological order can differ).` Replace the ranking line 88 with:

```python
                   key=lambda uv: (link_params(conn_by[uv], link_mode)[0], uv))
```

`model_from_dag`: signature `def model_from_dag(info: dict, *, link_mode: LinkMode = "stored"):`; add to the docstring `link_mode: "stored" (v1.10.0 CPTs, bit-identical) or "posterior" (rated edges take (q, p_plus) from the rater posteriors; the sign is marginalised inside the noisy-OR). Parameters are resolved once per in-edge, not per CPT cell.` Replace lines 173–184 with:

```python
    parents: dict[str, list] = {n: [] for n in info["nodes"]}
    for u, v, c in info["edges"]:
        parents[v].append((u, link_params(c, link_mode)))
    for node in info["nodes"]:
        ps = parents[node]
        if not ps:
            model.add_cpds(TabularCPD(node, 2, [[0.5], [0.5]]))
            continue
        # pgmpy column order: itertools.product over the evidence list, last
        # variable fastest — exactly what product([0, 1], repeat=k) yields.
        params = [prm for _, prm in ps]
        highs = [_noisy_or(states, params)
                 for states in itertools.product((0, 1), repeat=len(ps))]
```

(the `evidence=[u for u, _ in ps]` line below is unchanged).

`build_path_bbn`: add `link_mode: LinkMode = "stored"` after `max_paths` and pass it to both calls:

```python
    info = path_set_dag(isa, source, target, max_length=max_length, max_paths=max_paths,
                        link_mode=link_mode)
    return model_from_dag(info, link_mode=link_mode), info
```

`attribute_paths`: signature `def attribute_paths(info: dict, evidence: dict[str, int], focus: str, *, link_mode: LinkMode = "stored") -> list[dict]:`; docstring gains `Chain models are built in `link_mode`, the same mode as the joint model.`; line 249 becomes `model = model_from_dag(sub, link_mode=link_mode)`.

Also update the module docstring's sentence "derives every conditional probability table by noisy-OR from the existing strength × confidence × polarity scores" to "... from the stored strength × confidence × polarity scores, or optionally (link_mode="posterior") from the rater posteriors with the sign marginalised".

- [ ] **Step 4: Run the whole bayes file**

Run: `micromamba run -n shiny pytest tests/test_bayes.py tests/test_no_deprecations.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```
git add sespy/bayes.py tests/test_bayes.py
git commit -m "feat(bayes): link_mode threaded through the cut, the model and attribute_paths"
```

---

### Task 3: i18n keys

**Files:**
- Modify: `sespy/translations/core.json` (insert after line 5623 `"bbn.low": {...},`)
- Test: `tests/test_i18n.py:225-241`

**Interfaces:**
- Produces keys `bbn.posterior_links`, `bbn.posterior_line` (`{rated}`, `{total}`), used by Task 4; the English `bbn.posterior_line` starts with `Links from rater posteriors:` (e2e golden).

- [ ] **Step 1: Write the failing tests**

In `test_bbn_keys_present` (lines 226–231) add `"bbn.posterior_links", "bbn.posterior_line",` to the tuple. In `test_bbn_evidence_placeholders_match_across_languages` change line 237 to:

```python
    expected = {"bbn.evidence": {"items"}, "bbn.ignored": {"ids"}, "bbn.conflict": {"ids"},
                "bbn.posterior_line": {"rated", "total"}}
```

and append after its last assert:

```python
    assert translations["bbn.posterior_line"]["en"].startswith("Links from rater posteriors:")
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_i18n.py -q -k bbn`
Expected: 2 FAIL.

- [ ] **Step 3: Add the keys**

Insert these two lines directly after the `"bbn.low"` line (keep its trailing comma; `help.body` stays last without one):

```json
    "bbn.posterior_links": {"en": "Link probabilities from rater posteriors", "es": "Probabilidades de enlace a partir de las posteriores de los evaluadores", "fr": "Probabilités de lien issues des a posteriori des évaluateurs", "de": "Linkwahrscheinlichkeiten aus den Bewerter-Posteriors", "lt": "Ryšių tikimybės iš vertintojų posteriorų", "pt": "Probabilidades de ligação a partir das posteriores dos avaliadores", "it": "Probabilità di collegamento dalle posteriori dei valutatori", "no": "Koblingssannsynligheter fra vurderernes posteriorer", "el": "Πιθανότητες δεσμών από τις εκ των υστέρων κατανομές των αξιολογητών"},
    "bbn.posterior_line": {"en": "Links from rater posteriors: {rated} of {total} rated; unrated links use stored values", "es": "Enlaces desde las posteriores de los evaluadores: {rated} de {total} evaluados; los no evaluados usan los valores guardados", "fr": "Liens issus des a posteriori des évaluateurs : {rated} sur {total} évalués ; les liens non évalués gardent les valeurs enregistrées", "de": "Links aus den Bewerter-Posteriors: {rated} von {total} bewertet; unbewertete Links nutzen die gespeicherten Werte", "lt": "Ryšiai iš vertintojų posteriorų: įvertinta {rated} iš {total}; neįvertinti ryšiai naudoja išsaugotas reikšmes", "pt": "Ligações a partir das posteriores dos avaliadores: {rated} de {total} avaliadas; as não avaliadas usam os valores guardados", "it": "Collegamenti dalle posteriori dei valutatori: {rated} su {total} valutati; quelli non valutati usano i valori memorizzati", "no": "Koblinger fra vurderernes posteriorer: {rated} av {total} vurdert; uvurderte koblinger bruker lagrede verdier", "el": "Δεσμοί από τις εκ των υστέρων κατανομές των αξιολογητών: {rated} από {total} αξιολογημένοι· οι μη αξιολογημένοι χρησιμοποιούν τις αποθηκευμένες τιμές"},
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny pytest tests/test_i18n.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```
git add sespy/translations/core.json tests/test_i18n.py
git commit -m "i18n: keys for BBN posterior link mode"
```

---

### Task 4: Intervention UI — checkbox, worker mode, summary line

**Files:**
- Modify: `sespy/modules/analysis_intervention.py` — sidebar `:170-178`, `_bbn_work`/`_bbn_task` `:432-457`, `_invalidate_bbn` `:523-524`, `_run_bbn` `:549-553`, `bbn_summary` after line 587. Line numbers refer to the file before this task's edits; locate by the quoted code.

**Interfaces:**
- Consumes: `bayes.path_set_dag(..., link_mode=)`, `bayes.model_from_dag(info, link_mode=)`, `bayes.attribute_paths(..., link_mode=)` (Task 2); keys from Task 3.
- Produces for Task 5: `#intervention-bbn_posterior` checkbox; summary line "Links from rater posteriors: 0 of 7 rated; unrated links use stored values" on the sample's D001→GB01 run.

There is no unit test for Shiny renders in this repo; Task 5's e2e is the test. Step 4 smoke-runs the app.

- [ ] **Step 1: UI**

After the `bbn_direction` radio (the `ui.input_radio_buttons(... selected="forward",\n                ),` block ending at line 175) and before `ui.input_action_button("run_bbn", ...)`, insert:

```python
                ui.input_checkbox("bbn_posterior", t("bbn.posterior_links"), value=False),
```

- [ ] **Step 2: Worker and task**

Replace `_bbn_work` and `_bbn_task` (lines 432–457) with:

```python
    def _bbn_work(isa, src, tgt, direction, high, low, link_mode):
        """Runs in a worker thread: the lazy pgmpy import lives here. Order
        matters: the conflict check needs only path_set_dag, so a conflict
        is reported instantly even before the engine has ever been loaded.
        link_mode ("stored" | "posterior") reaches every model built for
        this query: the cut, the joint model and the per-route chains."""
        info = bayes.path_set_dag(isa, src, tgt, link_mode=link_mode)
        if not info["nodes"]:
            return {"error": "bbn.no_path"}
        preset = {src: 1} if direction == "forward" else {tgt: 1}
        merged = bayes.merge_evidence(preset, high, low, info["nodes"])
        if merged["conflicts"]:
            return {"error": "bbn.conflict", "ids": merged["conflicts"]}
        try:
            model = bayes.model_from_dag(info, link_mode=link_mode)
        except bayes.BayesUnavailable:
            return {"error": "bbn.unavailable"}
        r = bayes.query_path_bbn(model, info, merged["evidence"])
        r["ignored"] = merged["ignored"]
        r["focus"] = bayes.focus_node(src, tgt, merged["evidence"])
        r["paths"] = (bayes.attribute_paths(info, merged["evidence"], r["focus"], link_mode=link_mode)
                      if r["focus"] else [])
        r["source"], r["target"] = src, tgt
        r["link_mode"] = link_mode
        # Edges still IN the model; an edge removed by the cycle cut is not
        # counted here (the bbn.cut line reports those).
        r["rated"] = sum(1 for _, _, c in info["edges"] if c.ratings)
        r["total"] = len(info["edges"])
        return r

    @reactive.extended_task
    async def _bbn_task(isa, src, tgt, direction, high, low, link_mode, gen):
        return (gen, await asyncio.to_thread(_bbn_work, isa, src, tgt, direction,
                                             high, low, link_mode))
```

- [ ] **Step 3: Invalidation, run, summary**

In `_invalidate_bbn` change the tuple (lines 523–524) to:

```python
        for read in (input.bbn_source, input.bbn_target, input.bbn_direction,
                     input.bbn_high, input.bbn_low, input.bbn_posterior):
```

In `_run_bbn` replace the final call (lines 552–553) with:

```python
        link_mode = "posterior" if input.bbn_posterior() else "stored"
        _bbn_task(project_data.get().isa_data, src, tgt, input.bbn_direction(),
                  high, low, link_mode, _bbn_gen[0])
```

(`bbn_posterior` is static sidebar UI like `bbn_direction`, so it needs no try/except.)

In `bbn_summary`, directly after the evidence line (line 587 `lines.append(ui.p(t("bbn.evidence", ...)))`), insert:

```python
        if r.get("link_mode") == "posterior":
            lines.append(ui.p(t("bbn.posterior_line", rated=r["rated"], total=r["total"]),
                              class_="text-muted", style="font-size: 0.85rem;"))
```

- [ ] **Step 4: Smoke test**

Confirm nothing listens on port 8000 (`Get-NetTCPConnection -LocalPort 8000 -State Listen`; Stop-Process any listener). From the PowerShell tool: `Start-Process -NoNewWindow -RedirectStandardOutput smoke.log -RedirectStandardError smoke.err micromamba -ArgumentList 'run','-n','shiny','python','-m','shiny','run','--port','8000','app.py'`; check `smoke.err` shows "Uvicorn running" and no traceback. Run `micromamba run -n shiny python tests/test_intervention_e2e.py` (300 s timeout): it must still pass unchanged (retry once only for a failure before the BBN block). Then stop the server by its PID and delete smoke.log/smoke.err (never commit them).

- [ ] **Step 5: Unit gate**

Run the unit gate from Global Constraints. Expected: all PASS (`test_no_deprecations` imports the module cold).

- [ ] **Step 6: Commit**

```
git add sespy/modules/analysis_intervention.py
git commit -m "feat(intervention): BBN link probabilities from rater posteriors toggle"
```

---

### Task 5: E2E — posterior toggle on the sample

**Files:**
- Modify: `tests/test_intervention_e2e.py` — insert after line 138 (`assert n_paths == 2, f"expected 2 route rows, got {n_paths}"`) and before line 139 (`# selectize hides the underlying <select> ...`).

- [ ] **Step 1: Add the block**

```python
        # --- Posterior link mode (design 2026-09-12). The sample has no
        # ratings, so every link falls back to stored values: the golden
        # delta is unchanged and the summary says 0 of 7 rated. ---
        await page.check("#intervention-bbn_posterior")
        for _ in range(20):
            await page.wait_for_timeout(500)
            if "not computed" in (await page.inner_text("#intervention-bbn_summary")):
                break
        assert "not computed" in (await page.inner_text("#intervention-bbn_summary")), \
            "stale BBN result survived the posterior toggle"
        await page.click("#intervention-run_bbn")
        await page.wait_for_function(
            "() => (document.getElementById('intervention-bbn_summary')?.innerText || '')"
            ".includes('causal paths')", timeout=60000)
        post_text = (await page.inner_text("#intervention-bbn_summary")).strip()
        assert "Links from rater posteriors: 0 of 7 rated" in post_text, \
            f"expected the rated-edge line: {post_text!r}"
        assert "(-0.05)" in post_text, f"posterior mode must not change an unrated model: {post_text!r}"
        # Back to stored mode, recomputed, so the evidence block below starts
        # from the same state as before this block.
        await page.uncheck("#intervention-bbn_posterior")
        for _ in range(20):
            await page.wait_for_timeout(500)
            if "not computed" in (await page.inner_text("#intervention-bbn_summary")):
                break
        assert "not computed" in (await page.inner_text("#intervention-bbn_summary")), \
            "stale BBN result survived untoggling posterior mode"
        await page.click("#intervention-run_bbn")
        await page.wait_for_function(
            "() => (document.getElementById('intervention-bbn_summary')?.innerText || '')"
            ".includes('causal paths')", timeout=60000)
        assert "Links from rater posteriors" not in (await page.inner_text("#intervention-bbn_summary"))
        print(f"intervention bbn posterior: OK ({post_text[:80]!r})")
```

Do not reassign `bbn_text`: the closing print at the end of the script reuses it.

- [ ] **Step 2: Run the script alone against a fresh server**

Start a server as in Task 4 Step 4, run `micromamba run -n shiny python tests/test_intervention_e2e.py`. Expected: prints `intervention bbn posterior: OK (...)`, `intervention bbn evidence: OK (...)` and `intervention e2e assertions pass`. Retry once only for a failure before the BBN block; a failure inside the BBN blocks on a warm server is a regression (report the assertion and captured text; do not loosen). Stop the server, delete the logs.

- [ ] **Step 3: Commit**

```
git add tests/test_intervention_e2e.py
git commit -m "test(e2e): BBN posterior link mode on the unrated sample"
```

---

### Task 6: Manual, changelog, README, version, full gate

**Files:**
- Modify: `docs/MANUAL.md` (line 3; section 19 Controls line 300; section 43 "Path-set belief network" paragraph line 456), `CHANGELOG.md` (top), `README.md` (line 43), `sespy/__init__.py`, `pyproject.toml`

- [ ] **Step 1: Manual**

Line 3: `**Version 1.12.0 · September 2026**`.

Section 19 Controls (line 300): change `"Query" (forward: the source is high; diagnostic: the target is high), "Run inference".` to `"Query" (forward: the source is high; diagnostic: the target is high), "Link probabilities from rater posteriors", "Run inference".`

Section 43, append to the end of the "Path-set belief network" paragraph (line 456, after "...is still a real signal."):

` With "Link probabilities from rater posteriors" on, a link that has ratings takes its sign probability and its expected strength from the rater posteriors of the paragraph above, and the sign is marginalised inside the noisy-OR: a parent pushes its child with the link strength times the probability that the link points that way. A link whose raters split evenly therefore carries no information at all rather than half as much, and because every uncertain link also feeds its child a little regardless of the parent's state, baselines under this option are not comparable with the stored-value baselines. With few raters the expected strength sits near the middle value, so rated links are weaker than their stored strength until ratings accumulate. Links nobody has rated keep the stored values, the summary says how many links were rated, and in the per-route table the polarity column is still the diagram's sign while the change is the inference's.`

- [ ] **Step 2: Changelog, README, version**

`CHANGELOG.md`, new entry at the top:

```markdown
## [1.12.0] — 2026-09-12

- **BBN link probabilities from rater posteriors (Intervention).** An
  opt-in checkbox derives each rated link's sign probability (Beta
  posterior) and expected strength (Dirichlet posterior) from the Option A
  rater posteriors, with the sign marginalised inside the noisy-OR; an
  evenly split link carries no information, unrated links keep the stored
  values, and the summary counts the rated links. The cycle cut and the
  per-route chains use the same mode. Library: `link_params`, `_noisy_or`,
  `link_mode` on `path_set_dag`, `model_from_dag`, `build_path_bbn`,
  `attribute_paths`. Stored mode is bit-identical to v1.11.0.
- Manual: sections 19 and 43 updated.
```

`README.md`: insert directly above `## What's new in v1.11.0` (line 43):

```markdown
## What's new in v1.12.0

- **Link probabilities from rater posteriors** (Intervention). A checkbox
  lets the path-set belief network take each rated link's sign probability
  and expected strength from the rater posteriors instead of the stored
  scalars, with the sign marginalised in the noisy-OR; unrated links keep
  the stored values and the summary counts the rated ones.
- See manual sections 19 and 43.

```

`sespy/__init__.py`: `__version__ = "1.12.0"`; `pyproject.toml`: `version = "1.12.0"`.

- [ ] **Step 3: Unit gate**

Run the unit gate from Global Constraints. Expected: all PASS, including `test_manual_version_line_matches_package`.

- [ ] **Step 4: Full e2e gate**

Confirm nothing listens on 8000. From the PowerShell tool: `Start-Process -NoNewWindow -RedirectStandardOutput e2e.log -RedirectStandardError e2e.err micromamba -ArgumentList 'run','-n','shiny','python','tests/run_e2e.py'`; poll `Get-Content e2e.log -Tail 5` with `Start-Sleep 60` inside bounded PowerShell calls until the summary line. Expected: `32/32 e2e scripts passed`. A failing script may be rerun alone once (cold-server warm-up flake) EXCEPT a failure inside the intervention script's BBN blocks, which is a regression. Delete e2e.log/e2e.err afterwards.

- [ ] **Step 5: Commit**

```
git add docs/MANUAL.md CHANGELOG.md README.md sespy/__init__.py pyproject.toml
git commit -m "chore(release): v1.12.0 — BBN link probabilities from rater posteriors"
```

Tagging, pushing and deploying are the owner's release steps and are not part of this plan.
