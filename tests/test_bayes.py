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
