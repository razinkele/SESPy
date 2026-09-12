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
from sespy.data_structure import Connection, Element, IsaData, Rating, load_sample

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


def _chain(sign_ab="+", ratings_ab=None):
    return _isa([Connection("A", "B", polarity=sign_ab, strength="strong", confidence=5,
                            ratings=list(ratings_ab or [])),
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


@needs_pgmpy
def test_build_path_bbn_cpt_column_order_matches_noisy_or():
    # Two parents into "c" with asymmetric edges (one '+' strong, one '-'
    # weak) so a transposed CPT column order cannot pass by symmetry.
    isa = _isa([
        Connection("s", "p", polarity="+", strength="strong", confidence=5),
        Connection("s", "m", polarity="+", strength="strong", confidence=5),
        Connection("p", "c", polarity="+", strength="strong", confidence=5),
        Connection("m", "c", polarity="-", strength="weak", confidence=5),
    ])
    info = bayes.path_set_dag(isa, "s", "c")
    assert set(info["nodes"]) >= {"s", "p", "m", "c"}
    model, info = bayes.build_path_bbn(isa, "s", "c")
    assert model is not None

    from pgmpy.inference import VariableElimination

    cpd_c = model.get_cpds("c")
    evidence_vars = cpd_c.variables[1:]
    edges_into_c = {u: c for u, v, c in info["edges"] if v == "c"}
    parents = [(u, edges_into_c[u]) for u in evidence_vars]

    infer = VariableElimination(model)
    for sp in (0, 1):
        for sm in (0, 1):
            evidence = {"p": sp, "m": sm}
            got = infer.query(["c"], evidence=evidence, show_progress=False).values[1]
            states = tuple(evidence[v] for v in evidence_vars)
            expected = bayes.noisy_or_p_high(states, parents)
            assert math.isclose(got, expected), (evidence, got, expected)


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
    assert bayes.focus_node("s", "t", {}) == "t"
    assert bayes.focus_node("s", "t", {"s": 1}) == "t"
    assert bayes.focus_node("s", "t", {"t": 1}) == "s"
    assert bayes.focus_node("s", "t", {"s": 1, "a": 0}) == "t"
    assert bayes.focus_node("s", "t", {"s": 1, "t": 1}) is None


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
    # evidence on a node that is NOT on a route is simply not applied to it:
    # ES01 lies only on the D001-A001-P001-MPF1-ES01-GB01 route, so evidence
    # on it must move that route's row but leave the ES03 route unchanged.
    rows_es01 = bayes.attribute_paths(info, {"D001": 1, "ES01": 0}, "GB01")
    base = bayes.attribute_paths(info, {"D001": 1}, "GB01")
    by_es01 = {tuple(r["path"]): r for r in rows_es01}
    by_base = {tuple(r["path"]): r for r in base}
    es03_path = next(p for p in by_base if p[-2:] == ("ES03", "GB01"))
    es01_path = next(p for p in by_base if p[-2:] == ("ES01", "GB01"))
    assert math.isclose(by_es01[es03_path]["p_high"], by_base[es03_path]["p_high"])
    assert math.isclose(by_es01[es03_path]["delta"], by_base[es03_path]["delta"])
    assert not math.isclose(by_es01[es01_path]["p_high"], by_base[es01_path]["p_high"])
    assert not math.isclose(by_es01[es01_path]["delta"], by_base[es01_path]["delta"])


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


def test_link_params_rejects_unknown_mode():
    c = Connection("a", "b", polarity="+", strength="strong", confidence=5)
    with pytest.raises(ValueError):
        bayes.link_params(c, "Posterior")


def test_link_params_rated_unknown_polarity_is_active_in_posterior_mode():
    c = Connection("a", "b", polarity="?", strength="strong", confidence=5, ratings=[_r(i) for i in range(3)])
    assert bayes.link_params(c, "stored") == (0.0, 0.0)
    q, p = bayes.link_params(c, "posterior")
    assert p == 0.8 and math.isclose(q, 0.675, abs_tol=1e-6)


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
        assert len(got) == len(expected), node
        for g, e in zip(got, expected):
            assert math.isclose(g, e, abs_tol=1e-5), (node, got, expected)
    gb = next(x for x in bayes.query_path_bbn(model, info, {"D001": 1})["rows"] if x["id"] == "GB01")
    assert math.isclose(gb["delta"], -0.0503, abs_tol=1e-3)
