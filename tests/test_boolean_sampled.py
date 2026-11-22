"""Sampled whole-network Boolean attractor search (spec 2026-11-21 §3.4)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

# bare import: pytest puts tests/ on sys.path (see test_boolean_core.py)
from _boolean_shapes import random_shape

from sespy import dynamics
from sespy.dynamics import (
    BOOLEAN_MAX_NODES_TOTAL,
    boolean_attractors,
    boolean_attractors_sampled,
    create_boolean_rules,
)
from sespy.persistent_storage import load_project

ROOT = Path(__file__).resolve().parents[1]
CARIBBEAN = ROOT / "sespy" / "templates" / "marinesabres" / "Caribbean_SES_Template.json"

TOP_KEYS = {"method", "attractors", "n_samples", "n_unconverged", "seed",
            "max_steps", "n_nodes"}
ATTRACTOR_KEYS = {"type", "states", "period", "hits", "basin_fraction"}


def _ring(n: int, w: float = 1.0) -> list[dict]:
    M = np.zeros((n, n))
    for i in range(n):
        M[i, (i + 1) % n] = w
    return create_boolean_rules(M)


def test_sampled_result_shape():
    res = boolean_attractors_sampled(_ring(3), n_samples=50, seed=4)
    assert set(res) == TOP_KEYS
    assert res["method"] == "sampled"
    assert res["n_samples"] == 50 and res["seed"] == 4 and res["n_nodes"] == 3
    assert res["max_steps"] == 1000
    assert res["attractors"]
    for a in res["attractors"]:
        assert set(a) == ATTRACTOR_KEYS
        assert a["type"] == ("fixed" if a["period"] == 1 else "cyclic")
        assert a["period"] == len(a["states"])
        assert all(isinstance(s, int) for s in a["states"])
        assert a["states"][0] == min(a["states"])  # rotated to the minimum
    assert "basin_size" not in json.dumps(res)
    hits = [(-a["hits"], a["states"][0]) for a in res["attractors"]]
    assert hits == sorted(hits)  # hits descending, then minimum state


def test_sampled_state_encoding_is_bit_i_is_node_i():
    # 2-node chain 0 -> 1 with node 0 a positive self-loop: fixed points are
    # 00 (0) and 11 (3). A 1-node self-loop on node 1 only gives state 2.
    M = np.zeros((2, 2))
    M[1, 1] = 1.0
    res = boolean_attractors_sampled(create_boolean_rules(M), n_samples=200, seed=0)
    assert {tuple(a["states"]) for a in res["attractors"]} == {(0,), (2,)}
    # a 9-node self-loop on node 8 crosses a byte boundary: state 1 << 8
    M = np.zeros((9, 9))
    M[8, 8] = 1.0
    res = boolean_attractors_sampled(create_boolean_rules(M), n_samples=200, seed=0)
    assert {tuple(a["states"]) for a in res["attractors"]} == {(0,), (256,)}
    # a 3-ring has two 3-cycles: one-hot and two-hot, each rotated to its minimum
    res = boolean_attractors_sampled(_ring(3), n_samples=300, seed=0)
    cyc = [a for a in res["attractors"] if a["period"] == 3]
    assert sorted(a["states"] for a in cyc) == [[1, 2, 4], [3, 6, 5]]


@pytest.mark.parametrize("seed", range(30))
def test_sampled_attractors_subset_of_exact(seed):
    rules = create_boolean_rules(random_shape(np.random.default_rng(seed)))
    exact = {frozenset(a["states"]) for a in boolean_attractors(rules, max_nodes=20)["attractors"]}
    res = boolean_attractors_sampled(rules, n_samples=300, seed=seed)
    assert res["n_unconverged"] == 0
    assert {frozenset(a["states"]) for a in res["attractors"]} <= exact


def test_sampled_hits_sum():
    rules = create_boolean_rules(random_shape(np.random.default_rng(7)))
    res = boolean_attractors_sampled(rules, n_samples=400, seed=2)
    assert sum(a["hits"] for a in res["attractors"]) + res["n_unconverged"] == 400
    for a in res["attractors"]:
        assert a["basin_fraction"] == a["hits"] / 400


def test_sampled_deterministic_for_seed():
    rules = create_boolean_rules(random_shape(np.random.default_rng(11)))
    a = boolean_attractors_sampled(rules, n_samples=300, seed=5)
    b = boolean_attractors_sampled(rules, n_samples=300, seed=5)
    assert a == b


def test_sampled_unconverged_counted():
    res = boolean_attractors_sampled(_ring(3), n_samples=200, max_steps=1, seed=0)
    assert res["n_unconverged"] > 0
    assert sum(a["hits"] for a in res["attractors"]) + res["n_unconverged"] == 200
    assert res["max_steps"] == 1


def test_sampled_caribbean_78_nodes():
    p = load_project(CARIBBEAN)
    M, _ = dynamics.isa_to_numeric_matrix(p.isa_data)
    rules = create_boolean_rules(M)
    assert len(rules) == 78
    t0 = time.perf_counter()
    res = boolean_attractors_sampled(rules, n_samples=2000, max_steps=1000)
    elapsed = time.perf_counter() - t0
    assert elapsed < 15, elapsed
    assert res["n_nodes"] == 78 and res["n_unconverged"] == 0
    assert sum(a["hits"] for a in res["attractors"]) == 2000
    assert sum(1 for a in res["attractors"] if a["type"] == "cyclic") >= 2
    assert all(isinstance(s, int) and 0 <= s < 2 ** 78
               for a in res["attractors"] for s in a["states"])
    # every reported cycle really is a cycle of the network
    cols = list(range(78))
    for a in res["attractors"]:
        for s, t in zip(a["states"], a["states"][1:] + a["states"][:1]):
            row = np.array([[(s >> i) & 1 for i in cols]], dtype=np.uint8)
            nxt = dynamics._boolean_step(rules, row, cols=cols, nodes=cols)[0]
            assert sum(int(v) << i for i, v in enumerate(nxt)) == t


def test_sampled_history_budget_lowers_max_steps():
    res = boolean_attractors_sampled(_ring(3), n_samples=1000, max_steps=100_000)
    assert res["max_steps"] == 10 ** 7 // 1000 - 1
    res = boolean_attractors_sampled(_ring(3), n_samples=1000, max_steps=50)
    assert res["max_steps"] == 50  # within budget: unchanged


def test_sampled_clamps_and_too_large():
    res = boolean_attractors_sampled(_ring(3), n_samples=0, max_steps=0)
    assert res["n_samples"] == 1 and res["max_steps"] == 1
    res = boolean_attractors_sampled(_ring(3), n_samples=10 ** 7, max_steps=10)
    assert res["n_samples"] == 100_000
    n = BOOLEAN_MAX_NODES_TOTAL + 1
    res = boolean_attractors_sampled(_ring(n), n_samples=10)
    assert res["method"] == "sampled" and res["attractors"] == []
    assert res["error"] == "too_large" and res["n_nodes"] == n
    assert res["max_nodes"] == BOOLEAN_MAX_NODES_TOTAL
