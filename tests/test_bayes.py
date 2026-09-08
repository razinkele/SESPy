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
