"""Exact feedback-core Boolean attractor search (spec 2026-11-21 §3.1, §3.3).

``boolean_attractors`` is the oracle: it must stay unchanged, and the core
search must reproduce its attractor sets and exact basins.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

# bare import: pytest puts tests/ on sys.path (rootdir conftest, no package);
# a stray site-packages ``tests`` package can shadow ``tests.*``
from _boolean_shapes import large_multi_cluster, random_shape, shape_counts

from sespy import dynamics
from sespy.dynamics import (
    BOOLEAN_BASIN_BUDGET,
    BOOLEAN_MAX_CORE,
    BOOLEAN_MAX_NODES_TOTAL,
    _boolean_partition,
    _boolean_step,
    boolean_attractors,
    boolean_attractors_core,
    create_boolean_rules,
)
from sespy.persistent_storage import load_project

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "sespy" / "templates"
MS = TPL / "marinesabres"

RESULT_KEYS = {"method", "n_nodes", "core_size", "upstream_size", "readout_size",
               "basin_method", "attractors", "all_off_only"}
ATTRACTOR_KEYS = {"type", "states", "period", "basin_size", "basin_fraction"}

_ORACLE: dict[int, dict] = {}
_ORACLE_TPL: dict[str, dict] = {}


def _rules_of(path: Path) -> list[dict]:
    p = load_project(path)
    M, _ = dynamics.isa_to_numeric_matrix(p.isa_data)
    return create_boolean_rules(M)


def _as_sets(res):  # {frozenset(states): basin_size}
    return {frozenset(a["states"]): a["basin_size"] for a in res["attractors"]}


def _oracle_for_seed(seed: int) -> tuple[list[dict], dict]:
    rules = create_boolean_rules(random_shape(np.random.default_rng(seed)))
    if seed not in _ORACLE:
        _ORACLE[seed] = boolean_attractors(rules, max_nodes=20)
    return rules, _ORACLE[seed]


def _oracle_for_template(name: str) -> dict:
    if name not in _ORACLE_TPL:
        _ORACLE_TPL[name] = boolean_attractors(_rules_of(TPL / name), max_nodes=20)
    return _ORACLE_TPL[name]


def _reference_next(rules, s: int) -> int:
    """Per-state transition, written exactly as boolean_attractors does it."""
    n = len(rules)
    bits = [(s >> i) & 1 for i in range(n)]
    new = 0
    for j, rule in enumerate(rules):
        inflow = 0.0
        for i, w in rule["activators"]:
            inflow += w * bits[i]
        for i, w in rule["inhibitors"]:
            inflow += w * bits[i]
        if inflow > rule["threshold"]:
            new |= 1 << j
    return new


def _states_matrix(n: int) -> np.ndarray:
    idx = np.arange(1 << n)
    return np.stack([(idx >> b) & 1 for b in range(n)], axis=1).astype(np.uint8)


def _row_int(row) -> int:
    return sum(int(v) << i for i, v in enumerate(row))


# ---------------------------------------------------------------------------
# Differential test against the oracle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(200))
def test_core_equals_boolean_attractors_on_random_shapes(seed):
    rules, want = _oracle_for_seed(seed)
    got = boolean_attractors_core(rules)
    assert got["basin_method"] == "exact"
    assert _as_sets(got) == _as_sets(want)


def test_exact_basin_pass_is_chunk_invariant(monkeypatch):
    # tiny chunks force every chunk loop of the exact basin pass to split
    monkeypatch.setattr(dynamics, "_BOOLEAN_CHUNK_ROWS", 4)
    checked = 0
    for seed in range(200):
        rules, want = _oracle_for_seed(seed)
        if len(want["attractors"]) < 2:
            continue
        got = boolean_attractors_core(rules)
        assert got["basin_method"] == "exact"
        assert _as_sets(got) == _as_sets(want), seed
        checked += 1
        if checked == 40:
            break
    assert checked == 40


def test_shape_generator_exercises_multi_cluster_and_bridges():
    seeds = range(200)
    c = shape_counts(seeds)
    assert c["seeds"] == 200
    assert c["multi_cluster"] >= 50          # >= 25% have >= 2 clusters
    assert c["bridges"] >= 50
    assert c["upstream"] >= 100
    assert c["fan_in"] >= 20
    assert c["readouts"] >= 100
    assert c["up_to_readout"] >= 20
    assert c["float_weights"] >= 150
    # the basin pass is only reached with >= 2 attractors; make sure the
    # differential test covers it, including with upstream ancestors of the core
    multi = multi_with_upstream_ancestors = 0
    for seed in seeds:
        rules, want = _oracle_for_seed(seed)
        if len(want["attractors"]) < 2:
            continue
        multi += 1
        U, C, _ = _boolean_partition(rules)
        feeds_core = {i for j in C for i, _ in rules[j]["activators"] + rules[j]["inhibitors"]}
        if feeds_core & set(U):
            multi_with_upstream_ancestors += 1
    assert multi >= 50
    assert multi_with_upstream_ancestors >= 25


# ---------------------------------------------------------------------------
# Shipped networks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["minimal_demo.json", "offshore_wind.json"])
def test_core_on_shipped_multi_attractor_networks(name):
    rules = _rules_of(TPL / name)
    got = boolean_attractors_core(rules)
    want = _oracle_for_template(name)
    assert len(want["attractors"]) >= 2
    assert got["basin_method"] == "exact"
    assert _as_sets(got) == _as_sets(want)


def test_fisheries_template_is_all_off_only():
    rules = _rules_of(MS / "Fisheries_SES_Template.json")
    res = boolean_attractors_core(rules)
    assert res["n_nodes"] == 26
    assert res["core_size"] == 14
    assert res["all_off_only"] is True
    assert res["basin_method"] == "exact"
    assert res["attractors"] == [{"type": "fixed", "states": [0], "period": 1,
                                  "basin_size": 2 ** 26, "basin_fraction": 1.0}]


def _whole_network_sample(rules, n_samples: int, seed: int) -> dict[frozenset, int]:
    """Test-local whole-network sampler: random starts, step until repeat."""
    n = len(rules)
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(n_samples, n), dtype=np.uint8)
    seen = [dict() for _ in range(n_samples)]
    paths = [[] for _ in range(n_samples)]
    alive = np.arange(n_samples)
    hits: dict[frozenset, int] = {}
    cols = list(range(n))
    for _ in range(10_000):
        keep = []
        for r, row in zip(alive, X):
            s = _row_int(row)
            if s in seen[r]:
                cyc = frozenset(paths[r][seen[r][s]:])
                hits[cyc] = hits.get(cyc, 0) + 1
            else:
                seen[r][s] = len(paths[r])
                paths[r].append(s)
                keep.append(True)
                continue
            keep.append(False)
        keep = np.array(keep, dtype=bool)
        alive, X = alive[keep], X[keep]
        if alive.size == 0:
            break
        X = _boolean_step(rules, X, cols=cols, nodes=cols)
    assert alive.size == 0
    return hits


LARGE_SEED = 3  # core 17, 6 attractors; sampled at the default budget, exact at 2^26


def test_large_synthetic_multi_cluster_core_cross_checked():
    rules = create_boolean_rules(large_multi_cluster(np.random.default_rng(LARGE_SEED)))
    res = boolean_attractors_core(rules)
    assert res["n_nodes"] == 34
    assert 15 <= res["core_size"] <= 18
    assert len(res["attractors"]) >= 2
    exact = {frozenset(a["states"]): a["basin_fraction"] for a in res["attractors"]}
    n_samples = 5000
    hits = _whole_network_sample(rules, n_samples, seed=11)
    assert set(hits) <= set(exact)
    for cyc, frac in exact.items():
        assert abs(frac - hits.get(cyc, 0) / n_samples) <= 0.03
    # with a larger budget the basin pass is exact, and agrees as well
    big = boolean_attractors_core(rules, basin_budget=1 << 26)
    assert big["basin_method"] == "exact"
    assert sum(a["basin_size"] for a in big["attractors"]) == 2 ** 34
    assert {frozenset(a["states"]) for a in big["attractors"]} == set(exact)
    for a in big["attractors"]:
        cyc = frozenset(a["states"])
        assert abs(a["basin_fraction"] - hits.get(cyc, 0) / n_samples) <= 0.03
        assert abs(a["basin_fraction"] - exact[cyc]) <= 0.03



def test_single_attractor_skips_basin_pass(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("basin pass must not run for a single attractor")

    monkeypatch.setattr(dynamics, "_boolean_core_basins", boom)
    rules = _rules_of(MS / "Aquaculture_SES_Template.json")
    res = boolean_attractors_core(rules)
    assert res["upstream_size"] == 21
    assert res["n_nodes"] == 28
    assert res["basin_method"] == "exact"
    assert len(res["attractors"]) == 1
    assert res["attractors"][0]["basin_size"] == 2 ** 28


def test_non_ancestor_upstream_is_an_exact_factor():
    # 0 <-> 1 positive ring (3 attractors); read-outs 2 <- 0 and 3 <- 2;
    # upstream 4 feeds only read-out 3 (not an ancestor of the core);
    # upstream 5 -> 6 -> 0 is an ancestor chain.
    M = np.zeros((7, 7))
    M[0, 1] = M[1, 0] = 1.0
    M[0, 2] = 0.7
    M[2, 3] = 0.3
    M[4, 3] = -0.3
    M[5, 6] = 1.0
    M[6, 0] = 0.2
    rules = create_boolean_rules(M)
    U, C, R = _boolean_partition(rules)
    assert (U, C, R) == ([4, 5, 6], [0, 1], [2, 3])
    got = boolean_attractors_core(rules)
    want = boolean_attractors(rules, max_nodes=20)
    assert got["basin_method"] == "exact"
    assert _as_sets(got) == _as_sets(want)


def test_nonzero_upstream_pattern_matches_oracle():
    # a source with a negative threshold is always on, so u* != 0
    M = np.zeros((6, 6))
    M[0, 1] = M[1, 0] = 1.0       # core ring
    M[2, 3] = 1.0                 # 2 (source) -> 3 -> core
    M[3, 0] = -0.2
    M[4, 1] = 0.7                 # 4 (source) -> core
    M[1, 5] = 0.3                 # read-out
    rules = create_boolean_rules(M)
    rules[2]["threshold"] = -0.5
    got = boolean_attractors_core(rules)
    want = boolean_attractors(rules, max_nodes=20)
    assert got["basin_method"] == "exact"
    assert _as_sets(got) == _as_sets(want)
    assert all(s & 0b1100 == 0b1100 for a in got["attractors"] for s in a["states"])


def test_self_loop_on_otherwise_acyclic_node():
    M = np.zeros((5, 5))
    M[0, 1] = 1.0
    M[1, 1] = 1.0                 # self-loop: the only cycle
    M[1, 2] = 0.7
    M[2, 3] = -0.3
    M[4, 3] = 0.2
    rules = create_boolean_rules(M)
    assert _boolean_partition(rules) == ([0, 4], [1], [2, 3])
    got = boolean_attractors_core(rules)
    want = boolean_attractors(rules, max_nodes=20)
    assert got["core_size"] == 1
    assert _as_sets(got) == _as_sets(want)


# ---------------------------------------------------------------------------
# Result shape and sentinels
# ---------------------------------------------------------------------------

def test_result_shape_and_ordering():
    rules = _rules_of(TPL / "offshore_wind.json")
    res = boolean_attractors_core(rules)
    json.dumps(res)  # no numpy scalars
    assert set(res) == RESULT_KEYS
    assert res["method"] == "core"
    assert res["n_nodes"] == 19
    assert (res["upstream_size"], res["core_size"], res["readout_size"]) == (4, 6, 9)
    assert res["all_off_only"] is False
    atts = res["attractors"]
    total = 0
    for a in atts:
        assert set(a) == ATTRACTOR_KEYS
        assert all(type(s) is int for s in a["states"])
        assert type(a["basin_size"]) is int
        assert type(a["basin_fraction"]) is float
        assert a["period"] == len(a["states"]) == len(set(a["states"]))
        assert a["type"] == ("fixed" if a["period"] == 1 else "cyclic")
        assert a["states"][0] == min(a["states"])
        for s, t in zip(a["states"], a["states"][1:] + a["states"][:1]):
            assert _reference_next(rules, s) == t
        assert a["basin_fraction"] == a["basin_size"] / 2 ** 19
        total += a["basin_size"]
    assert total == 2 ** 19
    keys = [(-a["basin_fraction"], a["states"][0]) for a in atts]
    assert keys == sorted(keys)


def test_core_too_large_sentinel():
    n = 21
    M = np.zeros((n, n))
    for i in range(n):
        M[i, (i + 1) % n] = 1.0
    res = boolean_attractors_core(create_boolean_rules(M))
    assert res == {"method": "core", "attractors": [], "error": "core_too_large",
                   "n_nodes": 21, "core_size": 21, "max_core": BOOLEAN_MAX_CORE}


def test_too_large_and_empty_sentinels():
    n = BOOLEAN_MAX_NODES_TOTAL + 1
    res = boolean_attractors_core(create_boolean_rules(np.zeros((n, n))))
    assert res["error"] == "too_large"
    assert res["attractors"] == []
    assert res["n_nodes"] == n
    empty = boolean_attractors_core([])
    assert empty["attractors"] == []
    assert empty["n_nodes"] == 0
    assert "error" not in empty


def test_constants():
    assert BOOLEAN_MAX_CORE == 20
    assert BOOLEAN_BASIN_BUDGET == 1 << 24
    assert BOOLEAN_MAX_NODES_TOTAL == 200


# ---------------------------------------------------------------------------
# Kernel
# ---------------------------------------------------------------------------

def test_step_matches_reference_transition():
    rng = np.random.default_rng(5)
    n = 10
    M = np.where(rng.random((n, n)) < 0.35,
                 rng.choice([1.0, -1.0, 0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.7, -0.7], size=(n, n)), 0.0)
    rules = create_boolean_rules(M)
    X = _states_matrix(n)
    nxt = _boolean_step(rules, X, cols=range(n), nodes=range(n))
    assert nxt.dtype == np.uint8 and nxt.shape == (1 << n, n)
    want = [_reference_next(rules, s) for s in range(1 << n)]
    assert [_row_int(r) for r in nxt] == want
    # partial columns: nodes 0..5 live, 6..9 fixed, evaluate a subset of nodes
    cols, nodes = [3, 0, 5, 1, 4, 2], [7, 2, 0]
    fixed = {6: 1, 7: 0, 8: 1, 9: 1}
    base = sum(v << i for i, v in fixed.items())
    Xp = _states_matrix(6)  # column k holds node cols[k]
    out = _boolean_step(rules, Xp, cols=cols, nodes=nodes, fixed=fixed)
    assert out.shape == (64, 3)
    for r in range(64):
        s = base | sum(int(Xp[r, k]) << cols[k] for k in range(6))
        t = _reference_next(rules, s)
        assert [int(v) for v in out[r]] == [(t >> j) & 1 for j in nodes]


def test_step_float_ties_resolve_like_the_oracle():
    # 0.1 + 0.2 - 0.3 > 0 in float64 (5.55e-17); order matters
    M = np.zeros((4, 4))
    M[0, 3], M[1, 3], M[2, 3] = 0.1, 0.2, -0.3
    rules = create_boolean_rules(M)
    X = _states_matrix(3)
    out = _boolean_step(rules, X, cols=[0, 1, 2], nodes=[3])
    assert [int(v) for v in out[:, 0]] == [(_reference_next(rules, s) >> 3) & 1 for s in range(8)]
    assert out[7, 0] == 1
    # the same with node 1 fixed in its list position
    out2 = _boolean_step(rules, X[:, [0, 2]], cols=[0, 2], nodes=[3], fixed={1: 1})
    assert out2[5, 0] == 1  # row 5: node 0 = 1, node 2 = 1


def test_basin_sampled_path_when_budget_tiny():
    rules = _rules_of(TPL / "offshore_wind.json")
    want = _oracle_for_template("offshore_wind.json")
    res = boolean_attractors_core(rules, basin_budget=1, basin_samples=4000, seed=1)
    assert res["basin_method"] == "sampled"
    assert all(a["basin_size"] is None for a in res["attractors"])
    assert abs(sum(a["basin_fraction"] for a in res["attractors"]) - 1.0) < 1e-9
    assert {frozenset(a["states"]) for a in res["attractors"]} == set(_as_sets(want))
    exact = {frozenset(a["states"]): a["basin_size"] / 2 ** 19 for a in want["attractors"]}
    for a in res["attractors"]:
        assert abs(a["basin_fraction"] - exact[frozenset(a["states"])]) < 0.04
    again = boolean_attractors_core(rules, basin_budget=1, basin_samples=4000, seed=1)
    assert again == res


def test_acyclic_network_core_zero():
    rules = _rules_of(TPL / "small_scale_fisheries.json")
    res = boolean_attractors_core(rules)
    assert res["core_size"] == 0
    assert res["n_nodes"] == 18
    assert res["all_off_only"] is True
    assert res["attractors"] == [{"type": "fixed", "states": [0], "period": 1,
                                  "basin_size": 2 ** 18, "basin_fraction": 1.0}]


def test_wide_network_beyond_64_nodes():
    p = load_project(TPL / "minimal_demo.json")
    M5, _ = dynamics.isa_to_numeric_matrix(p.isa_data)
    small = boolean_attractors_core(create_boolean_rules(M5))
    assert len(small["attractors"]) >= 2
    tail = 70
    n = 5 + tail
    M = np.zeros((n, n))
    M[:5, :5] = M5
    M[0, 5] = 1.0                    # read-out chain hung off core node 0
    for i in range(5, n - 1):
        M[i, i + 1] = 1.0
    res = boolean_attractors_core(create_boolean_rules(M))
    assert res["n_nodes"] == 75
    assert res["basin_method"] == "exact"
    assert len(res["attractors"]) == len(small["attractors"])
    small_by_set = {frozenset(a["states"]): a["basin_size"] for a in small["attractors"]}
    mask = (1 << 5) - 1
    for a in res["attractors"]:
        key = frozenset(s & mask for s in a["states"])
        assert key in small_by_set
        assert a["basin_size"] == small_by_set[key] * 2 ** tail
    assert sum(a["basin_size"] for a in res["attractors"]) == 2 ** n
    assert any(s >= 2 ** 64 for a in res["attractors"] for s in a["states"])
    json.dumps(res)
