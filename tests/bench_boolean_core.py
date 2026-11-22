"""Benchmark for the Boolean core search (spec 2026-11-21 §6).

Not collected by pytest (the name does not match ``test_*.py``). Run:

    micromamba run -n shiny python tests/bench_boolean_core.py

Each case is run 3 times; the median wall time and the peak ``tracemalloc``
memory are reported against the gate (median <= 5 s, peak <= 300 MB).
"""
from __future__ import annotations

import statistics
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sespy import dynamics  # noqa: E402
from sespy.dynamics import (  # noqa: E402
    BOOLEAN_BASIN_BUDGET,
    BOOLEAN_MAX_ATTRACTORS,
    boolean_attractors_core,
    boolean_attractors_sampled,
    create_boolean_rules,
)
from sespy.persistent_storage import load_project  # noqa: E402

CARIBBEAN = ROOT / "sespy" / "templates" / "marinesabres" / "Caribbean_SES_Template.json"
MAX_SECONDS, MAX_PEAK_MB, RUNS = 5.0, 300.0, 3


def _ring(M: np.ndarray, nodes: list[int], w: float = 1.0) -> None:
    for a, b in zip(nodes, nodes[1:] + nodes[:1]):
        M[a, b] = w


def case_a_matrix(seed: int = 0, chords: int = 25) -> np.ndarray:
    """200 nodes: a 20-node positive ring with random chords (the core),
    60 upstream nodes feeding it, 120 read-outs below it. With
    ``chords=0`` the core is a plain positive ring: 52,488 attractors."""
    rng = np.random.default_rng(seed)
    n, k, n_up = 200, 20, 60
    perm = [int(v) for v in rng.permutation(n)]
    core, up, out = perm[:k], perm[k:k + n_up], perm[k + n_up:]
    M = np.zeros((n, n))
    _ring(M, core)
    for _ in range(chords):
        a, b = (int(v) for v in rng.choice(core, 2))
        M[a, b] = float(rng.choice((1.0, -1.0, 0.3, -0.3)))
    for j, u in enumerate(up):
        if j + 1 < len(up) and rng.random() < 0.6:
            M[u, up[j + 1]] = float(rng.choice((1.0, -1.0)))
        M[u, int(rng.choice(core))] = float(rng.choice((1.0, -1.0, 0.3)))
    for j, o in enumerate(out):
        src = out[j - 1] if j and rng.random() < 0.5 else int(rng.choice(core))
        M[src, o] = float(rng.choice((1.0, -1.0)))
    return M


def delay_chain_matrix(m: int, k: int, extra_free: int = 0) -> np.ndarray:
    """A chain of ``m`` upstream delay nodes (every start gives a distinct
    input sequence, 2^m of them) feeding a ``k``-node positive ring, which
    has several attractors. ``extra_free`` read-outs hang below the ring."""
    n = m + k + extra_free
    M = np.zeros((n, n))
    for i in range(m - 1):
        M[i, i + 1] = 1.0
    core = list(range(m, m + k))
    _ring(M, core)
    M[m - 1, core[0]] = -0.5
    for j in range(extra_free):
        M[core[j % k], m + k + j] = 1.0
    return M


def case_b_matrix() -> np.ndarray:
    # D = 2^8 sequences, 2^16 core states: D * 2^|C| = BOOLEAN_BASIN_BUDGET
    return delay_chain_matrix(m=8, k=16, extra_free=6)


def case_d_matrix() -> np.ndarray:
    # worst case for the upstream-sequence pass: |U_a| = the cap, small core
    return delay_chain_matrix(m=dynamics._BOOLEAN_MAX_UPSTREAM_ANCESTORS, k=4, extra_free=3)


def ring_chain_matrix() -> np.ndarray:
    """A plain 20-node positive ring with a 180-node read-out chain below it."""
    n = 200
    M = np.zeros((n, n))
    _ring(M, list(range(20)))
    M[0, 20] = 1.0
    for i in range(20, n - 1):
        M[i, i + 1] = 1.0
    return M


def run_case(name: str, fn, check) -> bool:
    times, peaks = [], []
    for _ in range(RUNS):
        tracemalloc.start()
        t0 = time.perf_counter()
        res = fn()
        times.append(time.perf_counter() - t0)
        peaks.append(tracemalloc.get_traced_memory()[1] / 1e6)
        tracemalloc.stop()
        check(res)
    med, peak = statistics.median(times), max(peaks)
    ok = med <= MAX_SECONDS and peak <= MAX_PEAK_MB
    print(f"{name}: median {med:.2f} s, peak {peak:.0f} MB, {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    ra = create_boolean_rules(case_a_matrix())
    rb = create_boolean_rules(case_b_matrix())
    rd = create_boolean_rules(case_d_matrix())
    p = load_project(CARIBBEAN)
    M, _ = dynamics.isa_to_numeric_matrix(p.isa_data)
    rc = create_boolean_rules(M)
    re_ = create_boolean_rules(case_a_matrix(chords=0))
    rchain = create_boolean_rules(ring_chain_matrix())

    def check_e(res):
        assert res["core_size"] == 20 and res["n_attractors"] == 52_488, res.get("error")
        assert res["truncated"] and len(res["attractors"]) == BOOLEAN_MAX_ATTRACTORS

    def check_a(res):
        assert res["core_size"] == 20 and res["n_nodes"] == 200 and res["attractors"], res.get("error")

    def check_b(res):
        assert res["basin_method"] == "exact" and len(res["attractors"]) >= 2, res["basin_method"]

    def check_c(res):
        assert res["n_nodes"] == 78 and res["n_unconverged"] == 0

    def check_d(res):
        assert res["basin_method"] == "exact" and len(res["attractors"]) >= 2
        assert res["upstream_size"] >= dynamics._BOOLEAN_MAX_UPSTREAM_ANCESTORS - 1

    ok = [
        # basin_budget=0 forces the cheap sampled basin estimate: only the attractor set is timed
        run_case("(a) 200 nodes, 20-node core, attractor set",
                 lambda: boolean_attractors_core(ra, basin_budget=0, basin_samples=1), check_a),
        run_case(f"(b) exact basin pass at budget {BOOLEAN_BASIN_BUDGET}",
                 lambda: boolean_attractors_core(rb), check_b),
        run_case("(c) sampled search, Caribbean 2000 x 1000",
                 lambda: boolean_attractors_sampled(rc, n_samples=2000, max_steps=1000), check_c),
        run_case("(d) exact basin pass, |U_a| = cap upstream ancestors",
                 lambda: boolean_attractors_core(rd), check_d),
        # default arguments, as the app calls it: the attractor cap must bound the cost
        run_case(f"(e) case (a) layout, plain 20-ring core, cap {BOOLEAN_MAX_ATTRACTORS}",
                 lambda: boolean_attractors_core(re_), check_e),
    ]
    # reported, not gated: the longest read-out depth the size cap allows
    run_case("(e') 20-ring + 180-node read-out chain, n = 200 (not gated)",
             lambda: boolean_attractors_core(rchain), check_e)
    print("ALL PASS" if all(ok) else "GATE MISSED")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
