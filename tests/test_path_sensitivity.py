"""Tests for network.path_sensitivity (spec decision 10)."""
from __future__ import annotations

import copy

import pytest

from sespy.data_structure import Connection, Element, IsaData, Rating
from sespy.network import causal_paths, path_sensitivity
from _paths_fixtures import worked_example_isa


def _isa(nodes, edges) -> IsaData:
    """edges: (source, target, polarity, strength, confidence[, ratings])."""
    conns = []
    for e in edges:
        s, t, p, w, conf = e[:5]
        ratings = e[5] if len(e) > 5 else []
        conns.append(Connection(source=s, target=t, polarity=p, strength=w,
                                confidence=conf, ratings=ratings))
    return IsaData(
        elements=[Element(id=n, label=n, type="Pressures") for n in nodes],
        connections=conns,
    )


def _probs(res):
    for r in res["paths"]:
        yield r["rank_probability"]
        yield r["polarity_probability"]
        yield r["survival_probability"]


def test_seed_reproducible():
    isa = worked_example_isa()
    a = path_sensitivity(isa, "I", "F", n_draws=200, seed=7)
    b = path_sensitivity(isa, "I", "F", n_draws=200, seed=7)
    assert a == b
    assert a["n_draws"] == 200 and a["seed"] == 7
    assert a["base"] == 0.5 and a["flip_mode"] == "confidence"


def test_result_shape_and_baseline_order():
    isa = worked_example_isa()
    before = copy.deepcopy(isa.connections)
    res = path_sensitivity(isa, "I", "F", n_draws=50)
    assert isa.connections == before  # pure
    base = causal_paths(isa, "I", "F")
    assert [r["path"] for r in res["paths"]] == [r["path"] for r in base["paths"]]
    assert [r["polarity"] for r in res["paths"]] == [r["polarity"] for r in base["paths"]]
    assert [r["score"] for r in res["paths"]] == [r["score"] for r in base["paths"]]
    assert set(res) == {"n_draws", "seed", "base", "flip_mode",
                        "paths", "fragile_edges", "truncated"}
    for r in res["paths"]:
        assert set(r) == {"path", "polarity", "score", "rank_probability",
                          "polarity_probability", "survival_probability"}
        for k in ("rank_probability", "polarity_probability", "survival_probability"):
            assert type(r[k]) is float
    assert res["truncated"] is False


def test_base_zero_is_deterministic():
    isa = worked_example_isa()
    res = path_sensitivity(isa, "I", "F", n_draws=50, base=0.0)
    assert all(p in (0.0, 1.0) for p in _probs(res))
    assert res["paths"][0]["rank_probability"] == 1.0
    for r in res["paths"]:
        assert r["survival_probability"] == 1.0
        assert r["polarity_probability"] == 1.0
    assert res["fragile_edges"] == []  # nothing changes, nothing is fragile


def test_only_path_dropped_gives_zero_rank():
    isa = _isa(["s", "m", "t"], [("s", "m", "+", "strong", 1),
                                 ("m", "t", "+", "strong", 3)])
    res = path_sensitivity(isa, "s", "t", n_draws=100, base=1.0)
    (row,) = res["paths"]
    assert row["rank_probability"] == 0.0
    assert row["survival_probability"] == 0.0
    assert row["polarity_probability"] == 0.0
    # s->m changes in every draw, so its lift is undefined: never listed.
    assert res["fragile_edges"] == []


def test_rank_probability_is_within_same_sign():
    isa = worked_example_isa()
    res = path_sensitivity(isa, "I", "F", n_draws=300, seed=1)
    pols = {r["polarity"] for r in res["paths"]}
    assert pols == {"+", "-"}
    for r in res["paths"]:
        assert r["rank_probability"] > 0.0
        assert r["rank_probability"] <= r["polarity_probability"] <= r["survival_probability"]


def test_fragile_edges_bounded_and_sorted():
    isa = worked_example_isa()
    # Confidence 3 at base 0.5: every hop changes in some draws but not all.
    res = path_sensitivity(isa, "I", "F", n_draws=300, seed=3, base=0.5)
    fe = res["fragile_edges"]
    assert 0 < len(fe) <= 5
    keys = [(-e["lift"], -e["share"], e["source"], e["target"]) for e in fe]
    assert keys == sorted(keys)
    on_path = {(a, b) for r in res["paths"] for a, b in zip(r["path"], r["path"][1:])}
    for e in fe:
        assert set(e) == {"source", "target", "share", "lift"}
        assert 0.0 < e["share"] <= 1.0
        assert 0.0 < e["lift"] <= 1.0
        assert (e["source"], e["target"]) in on_path


def test_off_path_edge_never_fragile():
    isa = worked_example_isa()
    isa.connections.append(Connection(source="W", target="A", polarity="+",
                                      strength="strong", confidence=1))
    for seed in range(5):
        res = path_sensitivity(isa, "I", "F", n_draws=100, seed=seed, base=1.0)
        assert all((e["source"], e["target"]) != ("W", "A")
                   for e in res["fragile_edges"])


def test_flipped_path_does_not_count_towards_rank():
    isa = _isa(["s", "t"], [("s", "t", "+", "strong", 3)])
    res = path_sensitivity(isa, "s", "t", n_draws=400, base=1.0, seed=2)
    (row,) = res["paths"]
    # p_drop 0.5, p_flip 0.5 when kept: survival ~0.5, polarity ~0.25
    assert 0.0 < row["polarity_probability"] < row["survival_probability"]
    assert row["rank_probability"] == row["polarity_probability"]


def test_duplicate_pair_earlier_connection_winning_counts_as_flip():
    # The last s->t connection (confidence 1, "+") wins the baseline; when it
    # drops, the earlier "-" connection (confidence 5) wins: a flip, not a drop.
    isa = _isa(["s", "t"], [("s", "t", "-", "strong", 5),
                            ("s", "t", "+", "strong", 1)])
    res = path_sensitivity(isa, "s", "t", n_draws=50, base=1.0)
    (row,) = res["paths"]
    assert row["polarity"] == "+"
    assert row["survival_probability"] == 1.0
    assert row["polarity_probability"] == 0.0
    assert row["rank_probability"] == 0.0
    # Flipped in every draw: lift undefined, so not listed.
    assert res["fragile_edges"] == []


def test_no_route_returns_empty_shape():
    isa = worked_example_isa()
    for src, tgt in (("F", "I"), ("I", "nope"), ("I", "I")):
        res = path_sensitivity(isa, src, tgt, n_draws=10, seed=4)
        assert res == {"n_draws": 10, "seed": 4, "base": 0.5,
                       "flip_mode": "confidence", "paths": [],
                       "fragile_edges": [], "truncated": False}


def test_draw_strength_uses_ratings_only_when_rated():
    weak = [Rating(rater_id="r1", strength="weak", confidence=5, polarity="+"),
            Rating(rater_id="r2", strength="weak", confidence=5, polarity="+")]
    isa = _isa(["s", "a", "b", "t"], [
        ("s", "a", "+", "strong", 5, weak),
        ("a", "t", "+", "strong", 5),
        ("s", "b", "+", "medium", 5),   # unrated: keeps its stored strength
        ("b", "t", "+", "strong", 5),
    ])
    off = path_sensitivity(isa, "s", "t", n_draws=30)
    on = path_sensitivity(isa, "s", "t", n_draws=30, draw_strength=True)
    assert [r["path"] for r in off["paths"]] == [["s", "a", "t"], ["s", "b", "t"]]
    assert [r["rank_probability"] for r in off["paths"]] == [1.0, 0.0]
    assert [r["rank_probability"] for r in on["paths"]] == [0.0, 1.0]
    # Survival and polarity are untouched by strength draws.
    assert all(r["survival_probability"] == 1.0 for r in on["paths"])
    # The stored model is never mutated.
    assert isa.connections[0].strength == "strong"


def test_draw_strength_off_consumes_no_rng():
    isa = worked_example_isa()
    a = path_sensitivity(isa, "I", "F", n_draws=100, seed=5)
    b = path_sensitivity(isa, "I", "F", n_draws=100, seed=5, draw_strength=True)
    assert a == b  # no rated edges: the flag changes nothing


def test_clamps():
    chain = _isa(["s", "t"], [("s", "t", "+", "strong", 3)])
    assert path_sensitivity(chain, "s", "t", n_draws=0)["n_draws"] == 1
    assert path_sensitivity(chain, "s", "t", n_draws=-5)["n_draws"] == 1
    assert path_sensitivity(chain, "t", "s", n_draws=10**6)["n_draws"] == 10000
    assert path_sensitivity(chain, "s", "t", n_draws=5, base=-1.0)["base"] == 0.0
    assert path_sensitivity(chain, "s", "t", n_draws=5, base=2.0)["base"] == 1.0
    with pytest.raises(ValueError, match="flip_mode"):
        path_sensitivity(chain, "s", "t", flip_mode="bogus")
    with pytest.raises(ValueError, match="flip_mode"):
        path_sensitivity(chain, "t", "s", flip_mode="bogus")  # no route still validates
    res = path_sensitivity(chain, "s", "t", n_draws=5, flip_mode="posterior")
    assert res["flip_mode"] == "posterior"


def test_fragile_edges_need_positive_lift():
    # The top path's s->a (confidence 1, base 1.0) drops in every draw, so the
    # top changes in every draw: no edge's change makes it more likely.
    isa = _isa(["s", "a", "b", "t"], [("s", "a", "+", "strong", 1),
                                      ("a", "t", "+", "strong", 3),
                                      ("s", "b", "+", "medium", 3),
                                      ("b", "t", "+", "medium", 5)])
    res = path_sensitivity(isa, "s", "t", n_draws=200, base=1.0, seed=1)
    assert res["fragile_edges"] == []


def test_fragile_edges_rank_by_lift_not_drop_rate():
    # Top path s->a->t with two confidence-4 hops; the weaker route's s->b has
    # confidence 1, so it changes in most draws (high share) but never decides
    # whether the top changes (lift ~ 0). The top-path hops lead.
    isa = _isa(["s", "a", "b", "t"], [("s", "a", "+", "strong", 4),
                                      ("a", "t", "+", "strong", 4),
                                      ("s", "b", "+", "medium", 1),
                                      ("b", "t", "+", "medium", 5)])
    res = path_sensitivity(isa, "s", "t", n_draws=2000, seed=0)
    fe = res["fragile_edges"]
    edges = [(e["source"], e["target"]) for e in fe]
    assert set(edges[:2]) == {("s", "a"), ("a", "t")}
    for e in fe[:2]:
        assert e["lift"] > 0.5
    lift = {(e["source"], e["target"]): e for e in fe}
    if ("s", "b") in lift:
        assert lift[("s", "b")]["lift"] < 0.1
    for e in fe:
        assert e["lift"] > 0.0


def test_exact_score_tie_shares_rank_credit():
    # Two identical "+" routes, never perturbed: they tie on score in every
    # draw, so each gets half the rank credit.
    isa = _isa(["s", "a", "b", "t"], [("s", "a", "+", "strong", 5),
                                      ("a", "t", "+", "strong", 5),
                                      ("s", "b", "+", "strong", 5),
                                      ("b", "t", "+", "strong", 5)])
    res = path_sensitivity(isa, "s", "t", n_draws=40)
    assert [r["rank_probability"] for r in res["paths"]] == [0.5, 0.5]
    assert all(r["polarity_probability"] == 1.0 for r in res["paths"])


def test_tie_credit_keeps_invariant_under_perturbation():
    isa = _isa(["s", "a", "b", "c", "t"], [("s", "a", "+", "strong", 3),
                                           ("a", "t", "+", "strong", 3),
                                           ("s", "b", "+", "strong", 2),
                                           ("b", "t", "+", "strong", 4),
                                           ("s", "c", "-", "strong", 3),
                                           ("c", "t", "+", "strong", 3)])
    res = path_sensitivity(isa, "s", "t", n_draws=500, seed=9)
    tied = [r for r in res["paths"] if r["polarity"] == "+"]
    assert len(tied) == 2 and tied[0]["score"] == tied[1]["score"]
    for r in res["paths"]:
        assert 0.0 < r["rank_probability"] <= r["polarity_probability"] <= r["survival_probability"]
    # Credits for one sign never exceed the share of draws with that sign present.
    assert sum(r["rank_probability"] for r in tied) <= 1.0
