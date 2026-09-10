# BBN Free Evidence + Path Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Intervention panel's path-set belief network take extra high/low evidence on any path-set node and report, per causal route, how much the evidence moves the focus node along that route alone.

**Architecture:** `sespy/bayes.py` gains four functions: `model_from_dag` (the CPT builder factored out of `build_path_bbn`), pure `merge_evidence` and `focus_node`, and `attribute_paths` (one tiny chain model per route). The Intervention module gains a second `output_ui` with two multi-select pickers that react to the chosen pair, a worker that checks conflicts before importing pgmpy, an evidence line in the summary, and a second data frame under the node table. Nothing touches the stored project or the existing presets.

**Tech Stack:** Python 3.11, Shiny for Python 1.7, networkx, pandas, pgmpy ≥ 1.0 (optional extra `bayes`, installed in the `shiny` env), pytest, Playwright standalone e2e scripts.

**Spec:** `docs/superpowers/specs/2026-09-10-sespy-bbn-free-evidence-design.md`

## Global Constraints

- Run Python only via `micromamba run -n shiny python ...` / `micromamba run -n shiny pytest ...`; never create a venv, never `pip install`.
- Multi-line `python -c` breaks on this Windows shell: write scratch `.py` files if you need a probe. Bash `python - <<EOF` also hangs here.
- Unit gate: `micromamba run -n shiny pytest tests/ -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`
- E2E gate: `micromamba run -n shiny python tests/run_e2e.py` (full, never `-k "not e2e"`); kill any orphan server on port 8000 first (a `shiny run` that is "ready after 1s" is hitting an orphan); run nothing heavy alongside it. Runs longer than 10 min die in a backgrounded Bash call: launch detached with `Start-Process` from the PowerShell tool and Monitor the log.
- `sespy/translations/core.json`: keys live under `"translation"`; `help.body` is the LAST entry (no trailing comma) — insert new keys directly after `"bbn.about_text"` (line ~5614), before `help.body`. Every key needs all nine languages: en, es, fr, de, lt, pt, it, no, el. One key per line, same style as the neighbours.
- pgmpy is imported only inside function bodies in `sespy/bayes.py`; `import sespy.bayes` and every module import must succeed without pgmpy (`tests/test_no_deprecations.py` imports every module in a fresh interpreter; `test_import_bayes_does_not_import_pgmpy` guards this file).
- pgmpy-dependent tests carry the existing `@needs_pgmpy` marker in `tests/test_bayes.py`; the file must still collect and pass without pgmpy.
- The first pgmpy import per process takes 35–65 s in this env (torch). Do not kill a test run that looks stuck in its first model test.
- E2E selectors must be namespaced ids (`#intervention-…`), never bare `text=`. Multi-select values are set with `Shiny.setInputValue('<id>', [...], {priority: 'event'})`.
- Invalidate on every feeding input: any new input that feeds the BBN result must be read in `_invalidate_bbn`.
- Commit after every task with the trailer:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FeeVsn6xUxEtPnY7vSrijN
  ```
  Use the PowerShell tool with `$msg = @'…'@; git commit -m $msg` for multi-line messages, never a PowerShell here-string inside the Bash tool.

---

## File map

| File | Responsibility |
|---|---|
| `sespy/bayes.py` (modify) | `model_from_dag`, `merge_evidence`, `focus_node`, `attribute_paths`; `build_path_bbn` becomes a two-liner |
| `tests/test_bayes.py` (modify) | Unit tests for all four, incl. hard-coded CPD goldens and sample goldens |
| `sespy/translations/core.json` (modify) | Nine new `bbn.*` keys |
| `tests/test_i18n.py` (modify) | Key presence + placeholder consistency |
| `sespy/modules/analysis_intervention.py` (modify) | `bbn_evidence_controls` output, worker, summary lines, `bbn_paths` table |
| `tests/test_intervention_e2e.py` (modify) | Evidence + route-table + conflict assertions |
| `tests/make_docs_screenshots.py` (modify) | `intervention_bbn.png` capture |
| `docs/MANUAL.md`, `CHANGELOG.md`, `README.md`, `sespy/__init__.py`, `pyproject.toml` (modify) | Docs + version 1.11.0 |

Verified goldens (2026-09-11, sample project, pair D001→GB01, `path_set_dag` nodes `['D001','A001','P001','MPF1','ES01','ES03','GB01']`, routes `D001→A001→P001→MPF1→ES01→GB01` and `D001→A001→P001→MPF1→ES03→GB01`):

| evidence | GB01 baseline | GB01 posterior | delta |
|---|---|---|---|
| `{D001: 1}` | 0.3803 | 0.3300 | −0.0503 |
| `{D001: 1, MPF1: 0}` | 0.3803 | 0.1022 | −0.2781 |
| solo route via ES01, `{D001: 1}` | — | — | −0.030107 |
| solo route via ES03, `{D001: 1}` | — | — | −0.030107 |

---

### Task 1: Factor the CPT builder into `model_from_dag`

**Files:**
- Modify: `sespy/bayes.py:115-151` (`build_path_bbn`)
- Test: `tests/test_bayes.py`

**Interfaces:**
- Consumes: `path_set_dag(isa, s, t) -> {"nodes", "edges": [(u, v, Connection)], "cut_edges", "paths", "truncated"}`, `noisy_or_p_high(states, parents)`, `BayesUnavailable`, `_INSTALL_HINT` (all existing).
- Produces: `model_from_dag(info: dict)` → pgmpy `DiscreteBayesianNetwork` or `None` when `info["nodes"]` is empty; raises `BayesUnavailable` without pgmpy. `build_path_bbn(isa, source, target, *, max_length=8, max_paths=100)` keeps its signature and returns `(model_from_dag(info), info)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bayes.py` (after `test_bayes_unavailable_when_pgmpy_missing`):

```python
# CPD rows of every node of path_set_dag(sample, "D001", "GB01") as built by
# the v1.10.0 builder (captured 2026-09-11 before the model_from_dag refactor):
# cpd.values.flatten() order, rounded to 6 dp.
_SAMPLE_CPDS = {
    "D001": [0.5, 0.5],
    "A001": [0.95, 0.285, 0.05, 0.715],
    "P001": [0.95, 0.492812, 0.05, 0.507188],
    "MPF1": [0.19, 0.95, 0.81, 0.05],
    "ES01": [0.95, 0.285, 0.05, 0.715],
    "ES03": [0.95, 0.558125, 0.05, 0.441875],
    "GB01": [0.95, 0.285, 0.558125, 0.167437, 0.05, 0.715, 0.441875, 0.832563],
}


@needs_pgmpy
def test_model_from_dag_matches_v1_10_cpds_on_the_sample():
    info = bayes.path_set_dag(load_sample(SAMPLE), "D001", "GB01")
    model = bayes.model_from_dag(info)
    assert model is not None and model.check_model()
    assert set(info["nodes"]) == set(_SAMPLE_CPDS)
    for node, expected in _SAMPLE_CPDS.items():
        got = [float(x) for x in model.get_cpds(node).values.flatten()]
        assert len(got) == len(expected), node
        for g, e in zip(got, expected):
            assert math.isclose(g, e, abs_tol=1e-5), (node, got, expected)


@needs_pgmpy
def test_build_path_bbn_is_path_set_dag_plus_model_from_dag():
    isa = load_sample(SAMPLE)
    model, info = bayes.build_path_bbn(isa, "D001", "GB01")
    assert info == bayes.path_set_dag(isa, "D001", "GB01")
    assert bayes.query_path_bbn(model, info, {"D001": 1}) == \
        bayes.query_path_bbn(bayes.model_from_dag(info), info, {"D001": 1})


@needs_pgmpy
def test_model_from_dag_returns_none_on_empty_info():
    assert bayes.model_from_dag(bayes.path_set_dag(_isa([Connection("A", "B")]), "B", "A")) is None


def test_model_from_dag_unavailable_when_pgmpy_missing(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake(name, *a, **k):
        if name.startswith("pgmpy"):
            raise ImportError("no pgmpy")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(bayes.BayesUnavailable):
        bayes.model_from_dag(bayes.path_set_dag(_chain(), "A", "C"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q -k "model_from_dag or plus_model"`
Expected: 4 FAIL with `AttributeError: module 'sespy.bayes' has no attribute 'model_from_dag'` (the first pgmpy test may take up to a minute on the import).

- [ ] **Step 3: Refactor**

Replace the whole `build_path_bbn` function in `sespy/bayes.py` (lines 115–151) with:

```python
def model_from_dag(info: dict):
    """pgmpy DiscreteBayesianNetwork over a path_set_dag result (or any dict
    with the same "nodes"/"edges" shape); None when info has no nodes.
    Every node is binary (0 low, 1 high). Parentless nodes (the source, and
    any node whose in-edges were all cut) get P(high) = 0.5; every other CPT
    is noisy-OR over its in-edges via noisy_or_p_high. This is the single
    place the CPT derivation lives: build_path_bbn and attribute_paths both
    call it. Raises BayesUnavailable when pgmpy is missing (checked before
    the empty test, so the caller learns about a missing engine even with
    no path)."""
    try:
        from pgmpy.factors.discrete import TabularCPD
        from pgmpy.models import DiscreteBayesianNetwork
    except ImportError as exc:
        raise BayesUnavailable(_INSTALL_HINT) from exc

    if not info["nodes"]:
        return None
    model = DiscreteBayesianNetwork([(u, v) for u, v, _ in info["edges"]])
    model.add_nodes_from(info["nodes"])
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
    return model


def build_path_bbn(isa: IsaData, source: str, target: str, *,
                   max_length: int = 8, max_paths: int = 100):
    """(pgmpy DiscreteBayesianNetwork, dag_info) over path_set_dag; (None,
    empty dag_info) when there is no path. Equivalent to
    (model_from_dag(info), info) with info = path_set_dag(...). Raises
    BayesUnavailable when pgmpy is missing."""
    info = path_set_dag(isa, source, target, max_length=max_length, max_paths=max_paths)
    return model_from_dag(info), info
```

- [ ] **Step 4: Run the whole bayes file**

Run: `micromamba run -n shiny pytest tests/test_bayes.py tests/test_no_deprecations.py -q`
Expected: all PASS (the pre-existing `test_bayes_unavailable_when_pgmpy_missing` still passes because `model_from_dag` imports pgmpy first).

- [ ] **Step 5: Commit**

```
git add sespy/bayes.py tests/test_bayes.py
git commit -m "refactor(bayes): factor the noisy-OR CPT builder into model_from_dag"
```

---

### Task 2: `merge_evidence` and `focus_node` (pure)

**Files:**
- Modify: `sespy/bayes.py` — insert after `noisy_or_p_high` (ends line ~112), before `model_from_dag`
- Test: `tests/test_bayes.py`

**Interfaces:**
- Produces: `merge_evidence(preset: dict[str, int], high, low, nodes: list[str]) -> {"evidence": dict[str, int], "ignored": list[str], "conflicts": list[str]}` and `focus_node(source: str, target: str, evidence: dict[str, int]) -> str | None`. Both pure, no pgmpy.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bayes.py`:

```python
def test_merge_evidence_plain_merge_and_none_pickers():
    nodes = ["s", "a", "b", "t"]
    r = bayes.merge_evidence({"s": 1}, ["a"], ["b"], nodes)
    assert r == {"evidence": {"s": 1, "a": 1, "b": 0}, "ignored": [], "conflicts": []}
    assert bayes.merge_evidence({"s": 1}, None, None, nodes) == \
        {"evidence": {"s": 1}, "ignored": [], "conflicts": []}
    assert bayes.merge_evidence({"t": 1}, (), [], nodes)["evidence"] == {"t": 1}


def test_merge_evidence_ignores_ids_outside_the_path_set_before_conflicts():
    r = bayes.merge_evidence({"s": 1}, ["zz", "a"], ["zz"], ["s", "a", "t"])
    # zz is outside the set: ignored, never a conflict even though it is in both pickers
    assert r["ignored"] == ["zz"] and r["conflicts"] == []
    assert r["evidence"] == {"s": 1, "a": 1}


def test_merge_evidence_same_id_in_both_pickers_is_a_conflict():
    r = bayes.merge_evidence({"s": 1}, ["a", "b"], ["b"], ["s", "a", "b", "t"])
    assert r["conflicts"] == ["b"]


def test_merge_evidence_picker_against_preset_is_a_conflict_agreeing_is_not():
    nodes = ["s", "a", "t"]
    assert bayes.merge_evidence({"s": 1}, [], ["s"], nodes)["conflicts"] == ["s"]
    assert bayes.merge_evidence({"t": 1}, [], ["t"], nodes)["conflicts"] == ["t"]
    ok = bayes.merge_evidence({"s": 1}, ["s"], [], nodes)
    assert ok["conflicts"] == [] and ok["evidence"] == {"s": 1}


def test_merge_evidence_lists_are_sorted_and_deduplicated():
    r = bayes.merge_evidence({"s": 1}, ["b", "a", "a"], ["zz", "yy", "zz"], ["s", "a", "b", "t"])
    assert r["ignored"] == ["yy", "zz"]
    assert list(r["evidence"]) == ["s", "a", "b"]      # preset first, then sorted picks


def test_focus_node_rule():
    assert bayes.focus_node("s", "t", {"s": 1}) == "t"
    assert bayes.focus_node("s", "t", {"t": 1}) == "s"
    assert bayes.focus_node("s", "t", {"s": 1, "a": 0}) == "t"
    assert bayes.focus_node("s", "t", {"s": 1, "t": 1}) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q -k "merge_evidence or focus_node"`
Expected: 6 FAIL with `AttributeError`.

- [ ] **Step 3: Implement**

Insert into `sespy/bayes.py` after `noisy_or_p_high`:

```python
def merge_evidence(preset: dict[str, int], high, low, nodes: list[str]) -> dict:
    """Merge the preset evidence with the user's extra picks. `high`/`low`
    are any iterable of node ids or None (a multi-select with nothing chosen
    is None in Shiny). Returns {"evidence": {id: 0|1}, "ignored": [ids],
    "conflicts": [ids]}. Rules, per id: (1) not in `nodes` → ignored (outside
    the path set: not part of the question), checked first so an unknown id
    is never a conflict; (2) in both pickers → conflict; (3) in a picker with
    the opposite state to the preset → conflict (agreeing is fine); (4)
    otherwise merged, preset first. Lists are sorted and deduplicated. Any
    conflict means the caller must not run inference. Pure."""
    known = set(nodes)
    hi = sorted({str(x) for x in (high or ())})
    lo = sorted({str(x) for x in (low or ())})
    ignored = sorted({x for x in hi + lo if x not in known})
    hi = [x for x in hi if x in known]
    lo = [x for x in lo if x in known]
    conflicts = set(hi) & set(lo)
    conflicts |= {x for x in hi if preset.get(x) == 0}
    conflicts |= {x for x in lo if preset.get(x) == 1}
    evidence = dict(preset)
    for x in hi:
        evidence.setdefault(x, 1)
    for x in lo:
        evidence.setdefault(x, 0)
    return {"evidence": evidence, "ignored": ignored, "conflicts": sorted(conflicts)}


def focus_node(source: str, target: str, evidence: dict[str, int]) -> str | None:
    """The node whose posterior the summary and the attribution are about:
    the target unless it is in evidence, then the source; None when both
    are in evidence (no focus line, no attribution). Pure."""
    if target not in evidence:
        return target
    if source not in evidence:
        return source
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q -k "merge_evidence or focus_node"`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```
git add sespy/bayes.py tests/test_bayes.py
git commit -m "feat(bayes): merge_evidence and focus_node for free BBN evidence"
```

---

### Task 3: `attribute_paths` (solo-path effect)

**Files:**
- Modify: `sespy/bayes.py` — append after `query_path_bbn` (end of file)
- Test: `tests/test_bayes.py`

**Interfaces:**
- Consumes: `model_from_dag(info)` (Task 1), `query_path_bbn(model, info, evidence)` (existing), `info["paths"]` rows `{"path": [ids], "length": int, "polarity": "+"|"-"|"0"}`.
- Produces: `attribute_paths(info: dict, evidence: dict[str, int], focus: str) -> list[dict]` rows `{"path", "length", "polarity", "baseline", "p_high", "delta"}` sorted by `(-round(|delta|, 9), path)`; `ValueError` when `focus in evidence`; `[]` when `info["paths"]` is empty; `BayesUnavailable` without pgmpy.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bayes.py`:

```python
@needs_pgmpy
def test_attribute_paths_sample_two_routes_tie_and_sort_by_path():
    isa = load_sample(SAMPLE)
    info = bayes.path_set_dag(isa, "D001", "GB01")
    rows = bayes.attribute_paths(info, {"D001": 1}, "GB01")
    assert [r["path"] for r in rows] == [
        ["D001", "A001", "P001", "MPF1", "ES01", "GB01"],
        ["D001", "A001", "P001", "MPF1", "ES03", "GB01"],
    ]
    for r in rows:
        assert r["length"] == 5 and r["polarity"] == "-"
        assert math.isclose(r["delta"], -0.030107, abs_tol=1e-5)
        assert r["delta"] < 0 and 0 < r["baseline"] < 1 and 0 < r["p_high"] < 1
    # sub-additivity on this fixture: |joint| <= sum |solo|
    joint = next(x for x in bayes.query_path_bbn(bayes.model_from_dag(info), info, {"D001": 1})["rows"]
                 if x["id"] == "GB01")["delta"]
    assert math.isclose(joint, -0.0503, abs_tol=1e-3)
    assert abs(joint) <= sum(abs(r["delta"]) for r in rows) + 1e-9


@needs_pgmpy
def test_attribute_paths_intermediate_evidence_restricted_to_the_route():
    isa = load_sample(SAMPLE)
    info = bayes.path_set_dag(isa, "D001", "GB01")
    rows = bayes.attribute_paths(info, {"D001": 1, "MPF1": 0}, "GB01")
    base = bayes.attribute_paths(info, {"D001": 1}, "GB01")
    # MPF1 is on both routes: each solo delta moves further from zero
    assert all(abs(r["delta"]) > abs(b["delta"]) for r, b in zip(rows, base))
    # the joint model with MPF1 low is the e2e golden
    model = bayes.model_from_dag(info)
    gb = next(x for x in bayes.query_path_bbn(model, info, {"D001": 1, "MPF1": 0})["rows"]
              if x["id"] == "GB01")
    assert math.isclose(gb["delta"], -0.2781, abs_tol=1e-3)
    # evidence on a node that is NOT on a route is simply not applied to it
    fwd = next(x for x in bayes.query_path_bbn(model, info, {"D001": 1})["rows"] if x["id"] == "GB01")
    assert math.isclose(fwd["delta"], -0.0503, abs_tol=1e-3)


@needs_pgmpy
def test_attribute_paths_chain_with_intermediate_low_lowers_target():
    info = bayes.path_set_dag(_chain(), "A", "C")
    fwd = bayes.attribute_paths(info, {"A": 1}, "C")[0]
    mid = bayes.attribute_paths(info, {"A": 1, "B": 0}, "C")[0]
    assert mid["p_high"] < fwd["p_high"]
    assert math.isclose(fwd["baseline"], mid["baseline"])       # same chain, same baseline


@needs_pgmpy
def test_attribute_paths_diagnostic_focus_is_the_source():
    info = bayes.path_set_dag(_chain(), "A", "C")
    row = bayes.attribute_paths(info, {"C": 1}, "A")[0]
    assert row["p_high"] > 0.5 and row["delta"] > 0


def test_attribute_paths_focus_in_evidence_raises_and_empty_info_is_empty():
    # pgmpy-free on purpose: the ValueError fires before any model is built,
    # and with no routes model_from_dag is never called.
    info = bayes.path_set_dag(_chain(), "A", "C")
    with pytest.raises(ValueError):
        bayes.attribute_paths(info, {"A": 1, "C": 1}, "C")
    empty = bayes.path_set_dag(_chain(), "C", "A")
    assert bayes.attribute_paths(empty, {"C": 1}, "A") == []


def test_attribute_paths_unavailable_when_pgmpy_missing(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake(name, *a, **k):
        if name.startswith("pgmpy"):
            raise ImportError("no pgmpy")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    info = bayes.path_set_dag(_chain(), "A", "C")
    with pytest.raises(bayes.BayesUnavailable):
        bayes.attribute_paths(info, {"A": 1}, "C")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q -k attribute_paths`
Expected: 6 FAIL with `AttributeError`.

- [ ] **Step 3: Implement**

Append to `sespy/bayes.py`:

```python
def attribute_paths(info: dict, evidence: dict[str, int], focus: str) -> list[dict]:
    """Solo-path effect: for each route still intact in info["paths"], build
    a chain model over that route's edges only (model_from_dag), apply the
    evidence restricted to the route's nodes, and read the focus node.
    Rows {"path": [ids], "length", "polarity", "baseline", "p_high",
    "delta"} sorted by (-round(|delta|, 9), path); the explicit rounding
    makes the lexicographic tiebreak deterministic when routes tie (the
    sample's two D001→GB01 routes both give −0.0301). `baseline` is the
    chain's own no-evidence marginal and differs from the joint baseline.
    The values are computed on the chain ALONE and do NOT sum to the joint
    delta of query_path_bbn (noisy-OR is sub-additive; routes share edges).
    Precondition: focus ∉ evidence (focus_node guarantees it) — ValueError
    otherwise. [] when there are no routes. Raises BayesUnavailable when
    pgmpy is missing. Deterministic."""
    if focus in evidence:
        raise ValueError("attribute_paths: the focus node must not be in evidence")
    conn_by = {(u, v): c for u, v, c in info["edges"]}
    rows: list[dict] = []
    for r in info["paths"]:
        p = list(r["path"])
        on_route = set(p)
        sub = {"nodes": p,
               "edges": [(u, v, conn_by[(u, v)]) for u, v in zip(p, p[1:])],
               "cut_edges": [], "paths": [r], "truncated": False}
        model = model_from_dag(sub)
        q = query_path_bbn(model, sub, {k: v for k, v in evidence.items() if k in on_route})
        row = next(x for x in q["rows"] if x["id"] == focus)
        rows.append({"path": p, "length": r["length"], "polarity": r["polarity"],
                     "baseline": row["baseline"], "p_high": row["p_high"], "delta": row["delta"]})
    rows.sort(key=lambda x: (-round(abs(x["delta"]), 9), x["path"]))
    return rows
```

`model_from_dag` is only reached inside the loop, so with no routes `attribute_paths` returns `[]` without pgmpy, and the ValueError precondition fires first; the focus/empty test therefore runs on the pgmpy-free CI job too.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny pytest tests/test_bayes.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```
git add sespy/bayes.py tests/test_bayes.py
git commit -m "feat(bayes): attribute_paths — solo-path effect per causal route"
```

---

### Task 4: i18n keys

**Files:**
- Modify: `sespy/translations/core.json` (insert after the `"bbn.about_text"` line, ~5614, before `"help.body"`)
- Test: `tests/test_i18n.py:225-230` (`test_bbn_keys_present`) and a new placeholder test after it

**Interfaces:**
- Produces keys used by Task 5: `bbn.also_high`, `bbn.also_low`, `bbn.evidence` (`{items}`), `bbn.ignored` (`{ids}`), `bbn.conflict` (`{ids}`), `bbn.paths_title`, `bbn.paths_legend`, `bbn.high`, `bbn.low`. English texts are the e2e goldens: the evidence line starts with `Evidence:`, the conflict line starts with `Conflicting evidence`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_i18n.py`, extend `test_bbn_keys_present` (the tuple at lines 226–229) with:

```python
                "bbn.also_high", "bbn.also_low", "bbn.evidence", "bbn.ignored",
                "bbn.conflict", "bbn.paths_title", "bbn.paths_legend", "bbn.high", "bbn.low",
```

and add after it:

```python
def test_bbn_evidence_placeholders_match_across_languages(translations):
    import re
    expected = {"bbn.evidence": {"items"}, "bbn.ignored": {"ids"}, "bbn.conflict": {"ids"}}
    for key, names in expected.items():
        for lang, text in translations[key].items():
            assert set(re.findall(r"\{(\w+)\}", text)) == names, (key, lang, text)
    assert translations["bbn.evidence"]["en"].startswith("Evidence:")
    assert translations["bbn.conflict"]["en"].startswith("Conflicting evidence")
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_i18n.py -q -k bbn`
Expected: 2 FAIL (`assert key in translations` / `KeyError`).

- [ ] **Step 3: Add the keys**

Insert these nine lines into `sespy/translations/core.json` directly after the `"bbn.about_text": {...},` line (keep the trailing comma on `bbn.about_text`; `help.body` remains last without one):

```json
    "bbn.also_high": {"en": "Also high", "es": "También alto", "fr": "Aussi haut", "de": "Ebenfalls hoch", "lt": "Taip pat aukštas", "pt": "Também alto", "it": "Anche alto", "no": "Også høy", "el": "Επίσης υψηλό"},
    "bbn.also_low": {"en": "Also low", "es": "También bajo", "fr": "Aussi bas", "de": "Ebenfalls niedrig", "lt": "Taip pat žemas", "pt": "Também baixo", "it": "Anche basso", "no": "Også lav", "el": "Επίσης χαμηλό"},
    "bbn.evidence": {"en": "Evidence: {items}", "es": "Evidencia: {items}", "fr": "Évidence : {items}", "de": "Evidenz: {items}", "lt": "Įrodymai: {items}", "pt": "Evidência: {items}", "it": "Evidenza: {items}", "no": "Evidens: {items}", "el": "Ένδειξη: {items}"},
    "bbn.ignored": {"en": "Ignored (not on the causal paths): {ids}", "es": "Ignorados (fuera de las rutas causales): {ids}", "fr": "Ignorés (hors des chemins causaux) : {ids}", "de": "Ignoriert (nicht auf den Kausalpfaden): {ids}", "lt": "Nepaisyta (ne priežastiniuose keliuose): {ids}", "pt": "Ignorados (fora dos caminhos causais): {ids}", "it": "Ignorati (fuori dai percorsi causali): {ids}", "no": "Ignorert (ikke på årsaksstiene): {ids}", "el": "Αγνοήθηκαν (εκτός αιτιωδών διαδρομών): {ids}"},
    "bbn.conflict": {"en": "Conflicting evidence, nothing computed: {ids}", "es": "Evidencia contradictoria, nada calculado: {ids}", "fr": "Évidence contradictoire, rien calculé : {ids}", "de": "Widersprüchliche Evidenz, nichts berechnet: {ids}", "lt": "Prieštaringi įrodymai, nieko neapskaičiuota: {ids}", "pt": "Evidência contraditória, nada calculado: {ids}", "it": "Evidenza contraddittoria, nulla calcolato: {ids}", "no": "Motstridende evidens, ingenting beregnet: {ids}", "el": "Αντικρουόμενη ένδειξη, δεν υπολογίστηκε τίποτα: {ids}"},
    "bbn.paths_title": {"en": "Effect per route", "es": "Efecto por ruta", "fr": "Effet par chemin", "de": "Wirkung je Pfad", "lt": "Poveikis pagal kelią", "pt": "Efeito por caminho", "it": "Effetto per percorso", "no": "Effekt per sti", "el": "Επίδραση ανά διαδρομή"},
    "bbn.paths_legend": {"en": "Each row applies the evidence along that route alone. Solo baselines are the route's own no-evidence values; solo changes do not add up to the joint change above.", "es": "Cada fila aplica la evidencia solo a lo largo de esa ruta. Las líneas base individuales son los valores sin evidencia de la propia ruta; los cambios individuales no suman el cambio conjunto de arriba.", "fr": "Chaque ligne applique l'évidence le long de ce seul chemin. Les références individuelles sont les valeurs sans évidence du chemin lui-même ; les changements individuels ne s'additionnent pas au changement conjoint ci-dessus.", "de": "Jede Zeile wendet die Evidenz nur entlang dieses Pfads an. Einzel-Basiswerte sind die evidenzfreien Werte des Pfads selbst; die Einzeländerungen summieren sich nicht zur gemeinsamen Änderung oben.", "lt": "Kiekviena eilutė taiko įrodymus tik tuo keliu. Atskiros bazinės reikšmės yra paties kelio reikšmės be įrodymų; atskiri pokyčiai nesusideda į bendrą pokytį aukščiau.", "pt": "Cada linha aplica a evidência apenas ao longo desse caminho. As linhas de base individuais são os valores sem evidência do próprio caminho; as alterações individuais não somam a alteração conjunta acima.", "it": "Ogni riga applica l'evidenza solo lungo quel percorso. Le basi individuali sono i valori senza evidenza del percorso stesso; le variazioni individuali non si sommano alla variazione congiunta sopra.", "no": "Hver rad bruker evidensen bare langs den stien. Enkeltgrunnlinjer er stiens egne verdier uten evidens; enkeltendringer summerer ikke til den samlede endringen ovenfor.", "el": "Κάθε γραμμή εφαρμόζει την ένδειξη μόνο κατά μήκος αυτής της διαδρομής. Οι μεμονωμένες γραμμές βάσης είναι οι τιμές της ίδιας της διαδρομής χωρίς ένδειξη· οι μεμονωμένες μεταβολές δεν αθροίζονται στη συνολική μεταβολή παραπάνω."},
    "bbn.high": {"en": "high", "es": "alto", "fr": "haut", "de": "hoch", "lt": "aukštas", "pt": "alto", "it": "alto", "no": "høy", "el": "υψηλό"},
    "bbn.low": {"en": "low", "es": "bajo", "fr": "bas", "de": "niedrig", "lt": "žemas", "pt": "baixo", "it": "basso", "no": "lav", "el": "χαμηλό"},
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny pytest tests/test_i18n.py -q`
Expected: all PASS (including `test_loader_handles_all_supported_languages`, which fails if any key misses a language, and JSON validity).

- [ ] **Step 5: Commit**

```
git add sespy/translations/core.json tests/test_i18n.py
git commit -m "i18n: keys for BBN extra evidence and per-route effect"
```

---

### Task 5: Intervention UI — evidence pickers, worker, summary, route table

**Files:**
- Modify: `sespy/modules/analysis_intervention.py` — UI at lines 167–178 (sidebar) and 198–200 (main); server at lines 425–552. All line numbers below refer to the file BEFORE this task's edits; locate by the quoted code, not the number, once Step 1 has shifted things.

**Interfaces:**
- Consumes: `bayes.path_set_dag`, `bayes.model_from_dag`, `bayes.merge_evidence`, `bayes.focus_node`, `bayes.attribute_paths`, `bayes.query_path_bbn`, `bayes.BayesUnavailable`; i18n keys from Task 4.
- Produces (for the e2e in Task 6): inputs `#intervention-bbn_high`, `#intervention-bbn_low` (multi selectize, values = element ids); output `#intervention-bbn_paths` (data frame, 2 rows on D001→GB01); summary `#intervention-bbn_summary` containing `Evidence: D001 high, MPF1 low` and the target line `(-0.28)` for the golden run, `Conflicting evidence, nothing computed: MPF1` on a conflict.

There is no unit test for Shiny render functions in this repo; the e2e in Task 6 is the test. Steps 1–4 here are the implementation; Step 5 smoke-runs the app.

- [ ] **Step 1: UI**

In the sidebar (line 169, right after `ui.output_ui("bbn_controls"),`) insert:

```python
                ui.output_ui("bbn_evidence_controls"),
```

In the main column, replace lines 198–200

```python
                ui.h4(t("bbn.title")),
                ui.output_ui("bbn_summary"),
                ui.output_data_frame("bbn_table"),
```

with

```python
                ui.h4(t("bbn.title")),
                ui.output_ui("bbn_summary"),
                ui.output_data_frame("bbn_table"),
                ui.h5(t("bbn.paths_title"), class_="mt-3"),
                ui.p(t("bbn.paths_legend"), class_="text-muted", style="font-size: 0.8rem;"),
                ui.output_data_frame("bbn_paths"),
```

- [ ] **Step 2: Evidence controls output and invalidation**

Insert after the `bbn_controls` render function (after line 467) — a SEPARATE output that reacts to the pair (design decision 4: `bbn_controls` keeps its isolate and is not modified):

```python
    @output
    @render.ui
    def bbn_evidence_controls():
        # Reacts to the pair (NOT isolated): the picker choices are the
        # path-set nodes for the current source/target. bbn_controls stays
        # isolated because it renders the very selects read here.
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        try:
            src, tgt = input.bbn_source(), input.bbn_target()
        except Exception:
            return ui.div()
        if not src or not tgt:
            return ui.div()
        info = bayes.path_set_dag(isa, src, tgt)     # networkx only, ≤3 ms on shipped projects
        if not info["nodes"]:
            return ui.p(t("bbn.no_path"), class_="text-muted", style="font-size: 0.8rem;")
        by_id = {el.id: el.label for el in isa.elements}
        choices = {n: f"{n} · {by_id.get(n, n)}" for n in info["nodes"] if n not in (src, tgt)}
        with reactive.isolate():
            def _prev(read):
                try:
                    v = read()
                except Exception:
                    v = None
                return [x for x in (list(v) if v else []) if x in choices]
            prev_hi, prev_lo = _prev(input.bbn_high), _prev(input.bbn_low)
        return ui.div(
            ui.input_selectize("bbn_high", t("bbn.also_high"), choices,
                               multiple=True, selected=prev_hi),
            ui.input_selectize("bbn_low", t("bbn.also_low"), choices,
                               multiple=True, selected=prev_lo),
        )
```

In `_invalidate_bbn` (line 475) change the tuple to include the pickers:

```python
        for read in (input.bbn_source, input.bbn_target, input.bbn_direction,
                     input.bbn_high, input.bbn_low):
```

- [ ] **Step 3: Worker and run effect**

Replace `_bbn_work` and `_bbn_task` (lines 428–443) with:

```python
    def _bbn_work(isa, src, tgt, direction, high, low):
        """Runs in a worker thread: the lazy pgmpy import lives here. Order
        matters: the conflict check needs only path_set_dag, so a conflict
        is reported instantly even before the engine has ever been loaded."""
        info = bayes.path_set_dag(isa, src, tgt)
        if not info["nodes"]:
            return {"error": "bbn.no_path"}
        preset = {src: 1} if direction == "forward" else {tgt: 1}
        merged = bayes.merge_evidence(preset, high, low, info["nodes"])
        if merged["conflicts"]:
            return {"error": "bbn.conflict", "ids": merged["conflicts"]}
        try:
            model = bayes.model_from_dag(info)
        except bayes.BayesUnavailable:
            return {"error": "bbn.unavailable"}
        r = bayes.query_path_bbn(model, info, merged["evidence"])
        r["ignored"] = merged["ignored"]
        r["focus"] = bayes.focus_node(src, tgt, merged["evidence"])
        r["paths"] = (bayes.attribute_paths(info, merged["evidence"], r["focus"])
                      if r["focus"] else [])
        r["source"], r["target"] = src, tgt
        return r

    @reactive.extended_task
    async def _bbn_task(isa, src, tgt, direction, high, low, gen):
        return (gen, await asyncio.to_thread(_bbn_work, isa, src, tgt, direction, high, low))
```

Replace the body of `_run_bbn` (lines 485–494) with:

```python
    def _run_bbn():
        try:
            src, tgt = input.bbn_source(), input.bbn_target()
        except Exception:
            return
        if not src or not tgt:
            return

        def _picks(read):            # multi selectize: None when nothing chosen
            try:
                v = read()
            except Exception:
                v = None
            return list(v) if v else []

        high, low = _picks(input.bbn_high), _picks(input.bbn_low)
        _bbn_gen[0] += 1
        _bbn_result.set(_COMPUTING)
        _bbn_task(project_data.get().isa_data, src, tgt, input.bbn_direction(),
                  high, low, _bbn_gen[0])
```

- [ ] **Step 4: Summary and route table**

Replace `bbn_summary` (lines 510–533) with:

```python
    @output
    @render.ui
    def bbn_summary():
        r = _bbn_result.get()
        if r is None:
            return ui.p(t("bbn.hint"), class_="text-muted", style="font-size: 0.85rem;")
        if r is _COMPUTING:       # must precede `"error" in r`: `in` on object() raises TypeError
            return ui.p(t("bbn.computing"), class_="text-muted", style="font-size: 0.85rem;")
        if "error" in r:
            cls = "text-danger" if r["error"] == "bbn.conflict" else "text-muted"
            # str.format ignores unused kwargs, so `ids` is safe on every key
            return ui.p(t(r["error"], ids=", ".join(r.get("ids", []))), class_=cls)
        by_id = {el.id: el.label for el in project_data.get().isa_data.elements}
        lines = [ui.p(ui.tags.strong(t(
            "bbn.summary", n=r["n_paths"], source=r["source"], target=r["target"],
            trunc=t("bbn.truncated") if r["truncated"] else "")))]
        items = ", ".join(f"{k} {t('bbn.high') if v == 1 else t('bbn.low')}"
                          for k, v in sorted(r["evidence"].items()))
        lines.append(ui.p(t("bbn.evidence", items=items), style="font-size: 0.85rem;"))
        focus = r.get("focus")
        if focus:
            row = next(x for x in r["rows"] if x["id"] == focus)
            lines.append(ui.p(t("bbn.target_line", id=focus, label=by_id.get(focus, focus),
                                base=f"{row['baseline']:.2f}", post=f"{row['p_high']:.2f}",
                                delta=f"{row['delta']:+.2f}")))
        if r.get("ignored"):
            lines.append(ui.p(t("bbn.ignored", ids=", ".join(r["ignored"])),
                              class_="text-muted", style="font-size: 0.85rem;"))
        if r["cut_edges"]:
            lines.append(ui.p(t("bbn.cut", n=len(r["cut_edges"]),
                                edges=", ".join(f"{u}→{v}" for u, v in r["cut_edges"])),
                              class_="text-warning", style="font-size: 0.85rem;"))
        return ui.div(*lines)
```

Append after `bbn_table` (end of the server function):

```python
    @output
    @render.data_frame
    def bbn_paths():
        import pandas as pd

        r = _bbn_result.get()
        cols = ["path", "length", "polarity", "solo baseline", "solo posterior", "solo delta"]
        if not isinstance(r, dict) or "error" in r:     # None, _COMPUTING, or an error
            return pd.DataFrame(columns=cols)
        by_id = {el.id: el.label for el in project_data.get().isa_data.elements}
        return pd.DataFrame([{
            "path": " → ".join(by_id.get(n, n) for n in x["path"]),
            "length": x["length"],
            "polarity": x["polarity"],
            "solo baseline": round(x["baseline"], 3),
            "solo posterior": round(x["p_high"], 3),
            "solo delta": round(x["delta"], 3),
        } for x in r.get("paths", [])], columns=cols)
```

- [ ] **Step 5: Smoke test in the app**

Kill anything on port 8000, then start a server from the PowerShell tool:

```
Start-Process -NoNewWindow -RedirectStandardOutput smoke.log -RedirectStandardError smoke.err micromamba -ArgumentList 'run','-n','shiny','python','-m','shiny','run','--port','8000','app.py'
```

(check `Get-Content smoke.err -Tail 5` shows "Uvicorn running", not a traceback — a traceback here means `server()` died, see memory `sespy-clientdata-reactive-context`). Then run the existing e2e script alone (it must still pass before Task 6 extends it): `micromamba run -n shiny python tests/test_intervention_e2e.py`. Expected: prints `intervention bbn: OK` and `intervention e2e assertions pass`. If the first attempt fails on the cold server, run once more (warm-up flake); a second failure is a regression. Stop the server afterwards (kill by port).

- [ ] **Step 6: Unit gate**

Run: `micromamba run -n shiny pytest tests/ -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`
Expected: all PASS (`test_no_deprecations` imports the module cold).

- [ ] **Step 7: Commit**

```
git add sespy/modules/analysis_intervention.py
git commit -m "feat(intervention): BBN extra evidence pickers and per-route effect table"
```

---

### Task 6: E2E — evidence, route table, conflict

**Files:**
- Modify: `tests/test_intervention_e2e.py` — insert between line 131 (`assert n_rows == 7 …`) and line 132 (`# Changing the direction invalidates the result.`)

**Interfaces:**
- Consumes the ids and texts produced by Task 5.

- [ ] **Step 1: Add the assertions**

Insert after line 131:

```python
        # --- Free evidence + per-route effect (design 2026-09-10). Goldens
        # verified 2026-09-11: forward GB01 delta -0.0503; with MPF1 (on both
        # routes) low, -0.2781; both solo routes tie at -0.0301. ---
        assert "(-0.05)" in bbn_text, f"expected the forward golden on GB01: {bbn_text!r}"
        n_paths = await page.evaluate(
            "() => document.querySelectorAll('#intervention-bbn_paths table tbody tr').length")
        assert n_paths == 2, f"expected 2 route rows, got {n_paths}"
        # selectize hides the underlying <select> (display:none), so the default
        # visible-state wait would time out: wait for presence only.
        await page.wait_for_selector("#intervention-bbn_low", state="attached", timeout=10000)
        await page.evaluate(
            "() => Shiny.setInputValue('intervention-bbn_low', ['MPF1'], {priority: 'event'})")
        for _ in range(20):
            await page.wait_for_timeout(500)
            if "not computed" in (await page.inner_text("#intervention-bbn_summary")):
                break
        assert "not computed" in (await page.inner_text("#intervention-bbn_summary")), \
            "stale BBN result survived an evidence change"
        await page.click("#intervention-run_bbn")
        # engine already loaded by the run above: no cold-import budget needed
        await page.wait_for_function(
            "() => (document.getElementById('intervention-bbn_summary')?.innerText || '')"
            ".includes('Evidence')", timeout=60000)
        ev_text = (await page.inner_text("#intervention-bbn_summary")).strip()
        assert "Evidence: D001 high, MPF1 low" in ev_text, f"unexpected evidence line: {ev_text!r}"
        assert "(-0.28)" in ev_text, f"expected the MPF1-low golden on GB01: {ev_text!r}"
        n_paths = await page.evaluate(
            "() => document.querySelectorAll('#intervention-bbn_paths table tbody tr').length")
        assert n_paths == 2, f"expected 2 route rows after the evidence run, got {n_paths}"
        # The same node high AND low is a conflict: reported, nothing computed,
        # and reported instantly (checked before the engine is touched).
        await page.evaluate(
            "() => Shiny.setInputValue('intervention-bbn_high', ['MPF1'], {priority: 'event'})")
        for _ in range(20):
            await page.wait_for_timeout(500)
            if "not computed" in (await page.inner_text("#intervention-bbn_summary")):
                break
        await page.click("#intervention-run_bbn")
        await page.wait_for_function(
            "() => (document.getElementById('intervention-bbn_summary')?.innerText || '')"
            ".includes('Conflicting evidence')", timeout=30000)
        conflict_text = (await page.inner_text("#intervention-bbn_summary")).strip()
        assert "MPF1" in conflict_text, f"conflict line should name MPF1: {conflict_text!r}"
        n_paths = await page.evaluate(
            "() => document.querySelectorAll('#intervention-bbn_paths table tbody tr').length")
        assert n_paths == 0, f"route table must be empty on a conflict, got {n_paths}"
        # Clear the pickers so the direction-change step below sees the original setup.
        await page.evaluate(
            "() => { Shiny.setInputValue('intervention-bbn_high', [], {priority: 'event'});"
            " Shiny.setInputValue('intervention-bbn_low', [], {priority: 'event'}); }")
        await page.wait_for_timeout(1000)
        print(f"intervention bbn evidence: OK ({ev_text[:80]!r})")
```

The existing direction-change block that follows stays byte-for-byte; the result is already cleared by the picker reset, so its "not computed" assertion still holds.

- [ ] **Step 2: Run the script alone against a fresh server**

Start a server as in Task 5 Step 5, then: `micromamba run -n shiny python tests/test_intervention_e2e.py`
Expected: prints `intervention bbn evidence: OK (...)` and `intervention e2e assertions pass`. On a fresh server the first one or two attempts can fail before the BBN block (warm-up flake, memory `sespy-e2e-cold-server-warmup-flake`); a failure INSIDE the new block on a warm server is a real regression. Stop the server afterwards.

- [ ] **Step 3: Commit**

```
git add tests/test_intervention_e2e.py
git commit -m "test(e2e): BBN extra evidence, route table and conflict assertions"
```

---

### Task 7: Screenshot, manual, changelog, version, full gate

**Files:**
- Modify: `tests/make_docs_screenshots.py` (`gate_intervention` ~line 251–280; the `run()` per-panel branch ~line 340–364), `docs/MANUAL.md` (version line 3; section 19 lines 296–306; section 43 lines 448–454), `CHANGELOG.md` (top), `README.md` (line 43), `sespy/__init__.py` (`__version__`), `pyproject.toml` (`version`)
- Create (generated): `docs/screenshots/intervention_bbn.png`

`tests/test_manual.py::test_every_manual_image_exists` requires the PNG before the manual references it, so generate the screenshot (Step 1–2) before editing the manual (Step 3).

- [ ] **Step 1: Screenshot capture code**

In `tests/make_docs_screenshots.py`, add a method after `gate_intervention`:

```python
    async def gate_intervention_bbn(self) -> None:
        """Forward query D001 -> GB01 with MPF1 low, so the evidence line and
        the per-route table are both populated for intervention_bbn.png."""
        if not await self.poll_sel("#intervention-bbn_source"):
            self.warn("intervention: bbn source select missing; run skipped")
            return
        await self.page.select_option("#intervention-bbn_source", "D001")
        await self.page.select_option("#intervention-bbn_target", "GB01")
        # The pickers already exist for the initial pair (D001 -> R002) and are
        # re-rendered for the new pair; a pick sent before the new selectize
        # binds is overwritten by its empty initial value. Let the render land.
        await self.page.wait_for_timeout(1500)
        if not await self.poll_sel("#intervention-bbn_low"):
            self.warn("intervention: bbn evidence pickers missing; run skipped")
            return
        # Drive the widget itself so the pick shows in the control on the shot
        # (the ablate pattern above); Shiny.setInputValue is the fallback.
        try:
            await self.page.click("#intervention-bbn_low + .selectize-control")
            await self.page.click(
                ".selectize-dropdown-content [data-selectable][data-value='MPF1']", timeout=3000)
            await self.page.keyboard.press("Escape")
        except Exception:
            self.warn("intervention: bbn selectize pick failed, using Shiny.setInputValue")
            await self.page.evaluate(
                "() => Shiny.setInputValue('intervention-bbn_low', ['MPF1'], {priority: 'event'})")
        await self.page.wait_for_timeout(500)
        await self.page.click("#intervention-run_bbn")
        # The first inference per server process loads pgmpy (35-65 s here).
        if not await self.poll_text("#intervention-bbn_summary",
                                    lambda t: "Evidence" in t or "pgmpy" in t, n=160, ms=500):
            self.warn("intervention: bbn result did not render")
```

and a scrolled-capture helper after `shot`:

```python
    async def shot_at(self, sel: str, name: str) -> None:
        """Screenshot with the first boxed descendant of `sel` parked under
        the topbar (the metrics cascade capture pattern)."""
        scroll_y = await self.page.eval_on_selector(
            sel,
            "el => { const box = Array.from(el.querySelectorAll('*'))"
            "    .find(c => c.getBoundingClientRect().height > 0) || el;"
            "  const y = box.getBoundingClientRect().top + window.scrollY - 90;"
            "  window.scrollTo({top: y, behavior: 'instant'}); return window.scrollY; }")
        await self.page.wait_for_timeout(500)
        if not scroll_y:
            self.warn(f"{name}: {sel} did not scroll into view")
        path = self.out / f"{name}.png"
        await self.page.screenshot(path=str(path), full_page=False)
        print(f"wrote {path} ({path.stat().st_size} bytes)")
        self.written.append(path)
```

In `run()`, after the `elif value == "simulation": … self.shot("simulation_montecarlo")` branch (line ~364) add:

```python
                elif value == "intervention":
                    await self.gate_intervention_bbn()
                    await self.hide_notifications()
                    await self.shot_at("#intervention-bbn_summary", "intervention_bbn")
```

Leave the metrics cascade block as is (not refactored to `shot_at` in this task).

- [ ] **Step 2: Generate the screenshots**

Kill anything on port 8000, start a server as in Task 5 Step 5, then run (detached via `Start-Process`, ~3 min):
`micromamba run -n shiny python tests/make_docs_screenshots.py --port 8000`
Expected: exit 0, no FAIL lines, `wrote …intervention_bbn.png`. Open `docs/screenshots/intervention_bbn.png` and confirm the "Evidence: D001 high, MPF1 low" line, the target line and the "Effect per route" table with two rows are visible. Stop the server.

- [ ] **Step 3: Manual**

`docs/MANUAL.md` line 3: `**Version 1.11.0 · September 2026**`.

Section 19 `**Controls.**` (line 300): change `"From", "To", "Query" (forward: the source is high; diagnostic: the target is high), "Run inference".` to `"From", "To", "Also high" and "Also low" (extra evidence on elements of the causal paths), "Query" (forward: the source is high; diagnostic: the target is high), "Run inference".`

Section 19 `**Outputs.**` (line 302): append ` The summary also lists the evidence used and any picked element that lies outside the paths, and an "Effect per route" table gives, for each causal path on its own, the baseline, posterior and change of the focus element.` Then, on a new line after the Outputs paragraph, add:

```markdown
![Bayesian inference with extra evidence and the per-route table](docs/screenshots/intervention_bbn.png)
```

Section 19 `**Caveats.**` (line 306): append ` Picking the same element as both high and low, or against the query preset, is a conflict: it is reported and nothing is computed.`

Section 43, after the "Path-set belief network" paragraph (line 454), add two paragraphs:

```markdown
**Extra evidence.** Besides the preset (source high or target high) any other element on the paths can be fixed high or low. The evidence is merged into one query: an element outside the paths is ignored and listed as such, and an element picked as both high and low, or against the preset, is a conflict that blocks the run. The summary names the focus element (the target, or the source when the target is fixed); with both fixed there is no focus and no per-route table.

**Per-route effect.** For every causal path left intact, SESPy builds a belief network over that path alone, applies the part of the evidence that lies on it, and reports the focus element's baseline, posterior and change along that single route. These are solo values: the baseline is the route's own no-evidence marginal, and because a noisy-OR is sub-additive and routes share links, the solo changes do not add up to the joint change reported above. Routes are ordered by the size of their solo change; ties keep path order.
```

- [ ] **Step 4: Changelog + version**

`CHANGELOG.md`, new entry at the top:

```markdown
## [1.11.0] — 2026-09-11

- **BBN extra evidence (Intervention).** "Also high" / "Also low" pickers
  fix further path-set elements alongside the forward/diagnostic preset;
  elements outside the paths are ignored and listed, conflicting picks
  block the run. Library: `merge_evidence`, `focus_node`.
- **Effect per route.** A second table gives, for each causal path on its
  own, the focus element's baseline, posterior and change (solo values
  that do not add up to the joint change). Library: `attribute_paths`,
  `model_from_dag` (the CPT builder factored out of `build_path_bbn`).
- Manual: section 19 and 43 updated; new screenshot `intervention_bbn.png`.
```

`sespy/__init__.py`: `__version__ = "1.11.0"`; `pyproject.toml`: `version = "1.11.0"`.

`README.md`: insert a new section directly above `## What's new in v1.10.0` (line 43), keeping the v1.10.0 section below it unchanged (the README keeps one section per release):

```markdown
## What's new in v1.11.0

- **Extra evidence for the path-set belief network** (Intervention). "Also
  high" / "Also low" pickers fix further elements of the causal paths
  alongside the forward/diagnostic preset; picks outside the paths are
  listed as ignored, conflicting picks block the run.
- **Effect per route.** A second table gives, for each causal path on its
  own, the focus element's baseline, posterior and change — solo values
  that do not add up to the joint change.
- See manual sections 19 and 43.

```

- [ ] **Step 5: Unit gate**

Run: `micromamba run -n shiny pytest tests/ -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`
Expected: all PASS, including `test_manual_version_line_matches_package` and `test_every_manual_image_exists`.

- [ ] **Step 6: Full e2e gate**

Kill any process on port 8000. From the PowerShell tool: `Start-Process -NoNewWindow -RedirectStandardOutput e2e.log -RedirectStandardError e2e.err micromamba -ArgumentList 'run','-n','shiny','python','tests/run_e2e.py'` and Monitor `e2e.log` until the summary line. Nothing else heavy may run meanwhile.
Expected: `32/32 e2e scripts passed`. A failing script may be rerun alone once (cold-server warm-up flake) EXCEPT a failure inside the intervention script's BBN assertions, which is a regression.

- [ ] **Step 7: Commit**

```
git add tests/make_docs_screenshots.py docs/MANUAL.md docs/screenshots/*.png CHANGELOG.md README.md sespy/__init__.py pyproject.toml
git commit -m "chore(release): v1.11.0 — BBN extra evidence + effect per route"
```

Tagging, pushing and deploying (deploy/deploy.sh, verify_live, MosaicSES re-check) are the owner's release steps and are not part of this plan.
