"""Unit tests for sespy.dynamics.signed_propagation (weighted signed walk).

Pure numerics; no Shiny imports.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from sespy import dynamics
from sespy.data_structure import Connection, Element, IsaData


def _els(*ids):
    return [Element(id=i, label=i.lower(), type="Drivers") for i in ids]


def _isa(ids, edges):
    """edges: (src, tgt[, polarity[, strength]]) tuples."""
    conns = []
    for e in edges:
        src, tgt = e[0], e[1]
        pol = e[2] if len(e) > 2 else "+"
        stg = e[3] if len(e) > 3 else "medium"
        conns.append(Connection(source=src, target=tgt, polarity=pol, strength=stg))
    return IsaData(elements=_els(*ids), connections=conns)


def _row(res, rid):
    return next(r for r in res["rows"] if r["id"] == rid)


def _walk_kw(**over):
    kw = dict(n_steps=6, n_tokens=500, decay=0.8, stop_prob=0.15,
              transition="weighted", seed=0)
    kw.update(over)
    return kw


def test_chain_reaches_in_order():
    isa = _isa("SABC", [("S", "A"), ("A", "B"), ("B", "C")])
    r = dynamics.signed_propagation(isa, "S", n_steps=8, n_tokens=200,
                                    decay=1.0, stop_prob=0.0)
    for rid, step in (("A", 1), ("B", 2), ("C", 3)):
        row = _row(r, rid)
        assert row["reach_probability"] == 1.0
        assert row["first_arrival_min"] == step
        assert row["first_arrival_q50"] == step
        assert isinstance(row["first_arrival_q50"], int)


def test_negative_edge_flips_once():
    isa = _isa("SABC", [("S", "A", "+"), ("A", "B", "-"), ("B", "C", "+")])
    r = dynamics.signed_propagation(isa, "S", n_tokens=200, decay=1.0,
                                    stop_prob=0.0)
    assert _row(r, "A")["positive_share"] == 1.0
    assert _row(r, "B")["negative_share"] == 1.0
    assert _row(r, "C")["negative_share"] == 1.0


def test_seed_reproducible_and_distinct():
    isa = _isa("SABCD", [("S", "A"), ("S", "B", "-"), ("A", "C"), ("B", "D"),
                         ("C", "D", "-")])
    a = dynamics.signed_propagation(isa, "S", seed=0)
    b = dynamics.signed_propagation(isa, "S", seed=0)
    c = dynamics.signed_propagation(isa, "S", seed=1)
    assert a == b
    assert a != c


def test_mass_identity_random_graphs():
    rng = np.random.default_rng(123)
    params = [dict(decay=0.8, stop_prob=0.15), dict(decay=0.0, stop_prob=0.0),
              dict(decay=1.0, stop_prob=0.0), dict(decay=1.0, stop_prob=1.0),
              dict(decay=0.5, stop_prob=1.0), dict(decay=0.0, stop_prob=1.0)]
    for g in range(30):
        n = int(rng.integers(3, 9))
        ids = [f"N{i}" for i in range(n)]
        edges = [("N0", "N1", "+", "strong")]
        for _ in range(int(rng.integers(2, 14))):
            s, t = rng.integers(0, n, 2)
            edges.append((ids[s], ids[t], "-" if rng.random() < 0.4 else "+",
                          ["weak", "medium", "strong"][int(rng.integers(0, 3))]))
        isa = _isa(ids, edges)
        for p in params:
            r = dynamics.signed_propagation(isa, "N0", n_tokens=100, n_steps=7,
                                            seed=g, **p)
            assert sum(r["mass"].values()) == pytest.approx(1.0, abs=1e-9)


def test_empty_shape_mass_is_zero():
    isa = _isa("SA", [("A", "S")])  # S has no out-links
    r = dynamics.signed_propagation(isa, "S")
    assert set(r) == {"rows", "source", "n_steps", "n_tokens", "decay",
                      "stop_prob", "transition", "seed", "n_reached",
                      "n_default_strength", "n_batches", "mass"}
    assert r["mass"] == {"decayed": 0.0, "stopped": 0.0, "absorbed": 0.0,
                         "in_transit": 0.0}
    assert r["n_batches"] == 0


def test_weighted_choice_follows_strength():
    isa = _isa("SAB", [("S", "A", "+", "strong"), ("S", "B", "+", "weak")])
    r = dynamics.signed_propagation(isa, "S", n_tokens=20000, n_steps=1,
                                    stop_prob=0.0)
    assert _row(r, "A")["reach_probability"] == pytest.approx(0.80 / 1.10, abs=0.02)


def test_equal_transition_ignores_strength():
    isa = _isa("SAB", [("S", "A", "+", "strong"), ("S", "B", "+", "weak")])
    r = dynamics.signed_propagation(isa, "S", n_tokens=20000, n_steps=1,
                                    stop_prob=0.0, transition="equal")
    assert _row(r, "A")["reach_probability"] == pytest.approx(0.5, abs=0.02)
    assert r["n_default_strength"] == 0


def test_default_strength_counted():
    isa = _isa("SAB", [("S", "A", "+", "?"), ("S", "B", "+", "medium")])
    r = dynamics.signed_propagation(isa, "S", n_tokens=20000, n_steps=1,
                                    stop_prob=0.0)
    assert r["n_default_strength"] == 1
    # "?" is weighted as medium: equal to the other edge
    assert _row(r, "A")["reach_probability"] == pytest.approx(0.5, abs=0.02)


def test_default_strength_counts_deduplicated_pairs():
    isa = _isa("SA", [("S", "A", "+", "?"), ("S", "A", "+", "?")])
    r = dynamics.signed_propagation(isa, "S", n_tokens=50)
    assert r["n_default_strength"] == 1


def _all_floats(obj):
    if isinstance(obj, float):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _all_floats(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_floats(v)


def test_degenerate_parameters_no_nan():
    isa = _isa("SABC", [("S", "A"), ("A", "B", "-"), ("B", "C")])
    r0 = dynamics.signed_propagation(isa, "S", decay=0.0)
    assert r0["rows"]
    for row in r0["rows"]:
        assert row["positive_share"] is None and row["negative_share"] is None
        assert row["positive_mass"] == 0.0 and row["negative_mass"] == 0.0
    assert r0["mass"]["decayed"] == pytest.approx(1.0 * (1 - r0["mass"]["stopped"]
                                                         - r0["mass"]["absorbed"]
                                                         - r0["mass"]["in_transit"]))
    r1 = dynamics.signed_propagation(isa, "S", stop_prob=1.0)
    assert [r["id"] for r in r1["rows"]] == ["A"]
    rt = dynamics.signed_propagation(isa, "S", n_tokens=1)
    assert rt["n_batches"] == 1
    assert rt["rows"] and all(r["net_sign"] == "~" for r in rt["rows"])
    for res in (r0, r1, rt):
        assert all(math.isfinite(f) for f in _all_floats(res))


def test_balanced_node_is_tilde():
    isa = _isa(["S", "A", "B", "T"], [("S", "A", "+"), ("S", "B", "+"),
                                        ("A", "T", "+"), ("B", "T", "-")])
    for seed in (0, 1):
        r = dynamics.signed_propagation(isa, "S", n_steps=3, n_tokens=1000,
                                        decay=1.0, stop_prob=0.0, seed=seed)
        assert _row(r, "T")["net_sign"] == "~", f"seed {seed}"


def test_untouched_subtree_keeps_routes():
    ids = "SAEBCD"
    base = _isa(ids, [("S", "A"), ("A", "E"), ("S", "B"), ("B", "C"), ("B", "D")])
    pert = _isa(ids, [("S", "A"), ("S", "B"), ("B", "C"), ("B", "D")])
    kw = _walk_kw(n_tokens=2000)
    w0 = dynamics._signed_walk(base, "S", **kw)
    w1 = dynamics._signed_walk(pert, "S", **kw)
    o = w0["order"]
    # A's only out-edge was dropped, so tokens that visited A may differ;
    # tokens that never visited A must have identical routes everywhere.
    never_a = w0["first"][:, o["A"]] == 0
    assert never_a.any() and (~never_a).any()
    assert np.array_equal(w0["first"][never_a], w1["first"][never_a])
    for rid in "CD":
        assert w0["reach"][o[rid]] == w1["reach"][o[rid]]


def test_sink_absorbs_and_counts():
    isa = _isa("SA", [("S", "A")])
    r = dynamics.signed_propagation(isa, "S", decay=1.0, stop_prob=0.0,
                                    n_tokens=100)
    assert r["mass"]["absorbed"] == 1.0
    assert r["mass"]["in_transit"] == 0.0


def test_parallel_connections_last_wins():
    isa = _isa("SA", [("S", "A", "+"), ("S", "A", "-")])
    r = dynamics.signed_propagation(isa, "S", n_tokens=200, decay=1.0,
                                    stop_prob=0.0)
    assert _row(r, "A")["negative_share"] == 1.0


def test_empty_shapes():
    isa = _isa("SA", [("S", "A")])
    for res in (dynamics.signed_propagation(isa, "nope"),
                dynamics.signed_propagation(isa, "A"),
                dynamics.signed_propagation(IsaData(elements=[], connections=[]),
                                            "S")):
        assert res["rows"] == [] and res["n_reached"] == 0


def test_bad_transition_raises():
    isa = _isa("SA", [("S", "A")])
    with pytest.raises(ValueError):
        dynamics.signed_propagation(isa, "S", transition="x")


def test_clamps_echoed():
    isa = _isa("SA", [("S", "A")])
    r = dynamics.signed_propagation(isa, "S", n_steps=0, decay=2, stop_prob=-1,
                                    n_tokens=10**9)
    assert (r["n_steps"], r["decay"], r["stop_prob"], r["n_tokens"]) == (
        1, 1.0, 0.0, 100000)


def test_equal_setting_matches_token_diffusion_reach_set():
    ids = ["S", "A", "B", "C", "D", "E"]
    isa = _isa(ids, [("S", "A"), ("S", "B"), ("A", "C"), ("B", "C", "-"),
                     ("C", "D"), ("B", "E")])
    td = dynamics.token_diffusion(isa, "S", n_tokens=5000, n_steps=6, seed=0)
    sp = dynamics.signed_propagation(isa, "S", n_tokens=5000, n_steps=6,
                                     decay=1.0, stop_prob=0.0,
                                     transition="equal", seed=0)
    assert {r["id"] for r in td["rows"]} == {r["id"] for r in sp["rows"]}


def test_unchanged_map_token_indexed_reproduces():
    isa = _isa("SABC", [("S", "A"), ("S", "B", "-"), ("A", "C"), ("B", "C")])
    copy = IsaData(elements=isa.elements, connections=list(isa.connections))
    kw = _walk_kw()
    w0 = dynamics._signed_walk(isa, "S", **kw)
    w1 = dynamics._signed_walk(copy, "S", **kw)
    for key in ("reach", "first", "net_sign", "pos_mass", "neg_mass", "signed"):
        assert np.array_equal(w0[key], w1[key])
    assert w0["mass"] == w1["mass"]
