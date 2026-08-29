"""Unit tests for sespy.dynamics — pure-Python numerics layer.

No Shiny imports; tests must run with plain pytest.
"""
from __future__ import annotations

import numpy as np
import pytest

from sespy import dynamics
from sespy.data_structure import Connection, Element, IsaData

# ============================================================
# isa_to_numeric_matrix
# ============================================================

def _isa(elements, connections):
    return IsaData(elements=list(elements), connections=list(connections))


def test_isa_to_numeric_matrix_two_node_signed():
    """A→B (+, medium) and B→A (-, strong) → 2×2 with correct signs/weights."""
    isa = _isa(
        [Element(id="A", label="A", type="D"), Element(id="B", label="B", type="P")],
        [
            Connection(source="A", target="B", polarity="+", strength="medium"),
            Connection(source="B", target="A", polarity="-", strength="strong"),
        ],
    )
    M, ids = dynamics.isa_to_numeric_matrix(isa)
    assert ids == ["A", "B"]
    assert M.shape == (2, 2)
    # Row=source, col=target. _STRENGTH_RANK: weak=1, medium=2, strong=3.
    assert M[0, 1] == 2.0   # A→B positive medium
    assert M[1, 0] == -3.0  # B→A negative strong
    assert M[0, 0] == 0.0
    assert M[1, 1] == 0.0


def test_isa_to_numeric_matrix_multiple_edges_sum():
    """Two parallel edges between same pair → weights sum."""
    isa = _isa(
        [Element(id="A", label="A", type="D"), Element(id="B", label="B", type="P")],
        [
            Connection(source="A", target="B", polarity="+", strength="medium"),
            Connection(source="A", target="B", polarity="+", strength="weak"),
        ],
    )
    M, _ = dynamics.isa_to_numeric_matrix(isa)
    assert M[0, 1] == 3.0  # 2 + 1


def test_isa_to_numeric_matrix_isolated_node_zero_row_col():
    """A node with no connections has zero row and column but is still in node list."""
    isa = _isa(
        [
            Element(id="A", label="A", type="D"),
            Element(id="B", label="B", type="P"),
            Element(id="C", label="C", type="I"),
        ],
        [Connection(source="A", target="B", polarity="+", strength="medium")],
    )
    M, ids = dynamics.isa_to_numeric_matrix(isa)
    assert ids == ["A", "B", "C"]
    assert M.shape == (3, 3)
    assert (M[2, :] == 0).all()
    assert (M[:, 2] == 0).all()


def test_isa_to_numeric_matrix_empty_isa():
    """Empty ISA → (0,0) array and empty list."""
    M, ids = dynamics.isa_to_numeric_matrix(IsaData())
    assert M.shape == (0, 0)
    assert ids == []


def test_isa_to_numeric_matrix_raises_on_unknown_node():
    """Connection referencing an element id not in elements list → ValueError."""
    isa = _isa(
        [Element(id="A", label="A", type="D")],
        [Connection(source="A", target="ghost", polarity="+", strength="medium")],
    )
    with pytest.raises(ValueError, match="ghost"):
        dynamics.isa_to_numeric_matrix(isa)


def test_isa_to_numeric_matrix_unknown_strength_falls_back_to_medium():
    """Connection with an unrecognised strength string falls back to medium (rank 2)."""
    isa = _isa(
        [Element(id="A", label="A", type="D"), Element(id="B", label="B", type="P")],
        [Connection(source="A", target="B", polarity="+", strength="bogus")],
    )
    M, _ = dynamics.isa_to_numeric_matrix(isa)
    assert M[0, 1] == 2.0  # default rank for unknown strength


# ============================================================
# isa_to_dynamics_matrix
# ============================================================

def test_isa_to_dynamics_matrix_propagates_along_edge_direction():
    """A -> B (+): seeding A only must move B, not A, at t=1.

    This is the direction bug: simulate_dynamics computes
    x_{t+1} = M @ x_t, which needs row=target/col=source to propagate
    forward. isa_to_numeric_matrix is row=source/col=target, so the raw
    matrix must be transposed before iteration. isa_to_dynamics_matrix is
    that transpose.
    """
    isa = _isa(
        [Element(id="A", label="A", type="D"), Element(id="B", label="B", type="P")],
        [Connection(source="A", target="B", polarity="+", strength="medium")],
    )
    A, ids = dynamics.isa_to_dynamics_matrix(isa)
    assert ids == ["A", "B"]
    x0 = np.array([1.0, 0.0])
    traj = dynamics.simulate_dynamics(A, n_iter=1, initial_state=x0)
    assert traj[1, 1] != 0.0, "B (the target) must receive influence from A at t=1"
    assert traj[1, 0] == 0.0, "A (the source) must not move from a one-way edge"


def test_isa_to_dynamics_matrix_is_transpose_of_numeric_matrix():
    """isa_to_dynamics_matrix is exactly isa_to_numeric_matrix's matrix, transposed."""
    isa = _isa(
        [Element(id="A", label="A", type="D"), Element(id="B", label="B", type="P")],
        [
            Connection(source="A", target="B", polarity="+", strength="medium"),
            Connection(source="B", target="A", polarity="-", strength="strong"),
        ],
    )
    M, ids_m = dynamics.isa_to_numeric_matrix(isa)
    A, ids_a = dynamics.isa_to_dynamics_matrix(isa)
    assert ids_a == ids_m
    assert np.array_equal(A, M.T)


def test_create_boolean_rules_reads_numeric_matrix_orientation_unchanged():
    """Pin create_boolean_rules' current (correct) reading of
    isa_to_numeric_matrix's row=source/col=target orientation, so a future
    'consistency' refactor cannot flip it onto the dynamics-matrix transpose."""
    isa = _isa(
        [Element(id="A", label="A", type="D"), Element(id="B", label="B", type="P")],
        [
            Connection(source="A", target="B", polarity="+", strength="medium"),
            Connection(source="B", target="A", polarity="-", strength="strong"),
        ],
    )
    M, _ = dynamics.isa_to_numeric_matrix(isa)
    rules = dynamics.create_boolean_rules(M)
    assert len(rules) == 2

    rule_a = rules[0]
    assert rule_a["node_id"] == 0
    assert rule_a["activators"] == []
    assert rule_a["inhibitors"] == [(1, -3.0)]

    rule_b = rules[1]
    assert rule_b["node_id"] == 1
    assert rule_b["activators"] == [(0, 2.0)]
    assert rule_b["inhibitors"] == []


# ============================================================
# laplacian_eigenvalues / laplacian_stability
# ============================================================

def test_laplacian_path_p3_closed_form_eigenvalues():
    """P_3 path graph (Laplacian L=D-A) has closed-form eigenvalues {0, 1, 3}.

    Closed-form means: P_n has eigenvalues 2(1-cos(k*pi/n)) for k=0..n-1.
    For n=3: {0, 1, 3}. Match within 1e-9. Not derived from numpy.linalg.eig
    (that would be circular).
    """
    # Symmetric adjacency: A↔B, B↔C. Use bidirectional positive medium edges.
    isa = _isa(
        [
            Element(id="A", label="A", type="D"),
            Element(id="B", label="B", type="D"),
            Element(id="C", label="C", type="D"),
        ],
        [
            Connection(source="A", target="B", polarity="+", strength="medium"),
            Connection(source="B", target="A", polarity="+", strength="medium"),
            Connection(source="B", target="C", polarity="+", strength="medium"),
            Connection(source="C", target="B", polarity="+", strength="medium"),
        ],
    )
    M, _ = dynamics.isa_to_numeric_matrix(isa)
    # Normalize so adjacency rank = 1 (medium=2, divide by 2)
    A = np.abs(M) / 2.0
    eigvals = dynamics.laplacian_eigenvalues(A, direction="cols")
    sorted_real = sorted(v.real for v in eigvals)
    expected = [0.0, 1.0, 3.0]
    for got, want in zip(sorted_real, expected):
        assert abs(got - want) < 1e-9, f"eigenvalue {got} != {want}"


def test_laplacian_direction_rows_vs_cols_differ_for_asymmetric():
    """Asymmetric directed adjacency → row- and col-direction give different specs.

    Note: a directed cycle has in/out-degree multisets that match (every node
    has one in and one out), so its row- and col-Laplacians share a spectrum.
    Use a hub-and-spoke + extra edge so the degree multisets genuinely differ.
    """
    # Out-degrees (rows): [4, 0, 1]; In-degrees (cols): [0, 3, 2]
    M = np.array([[0.0, 3.0, 1.0],
                  [0.0, 0.0, 0.0],
                  [0.0, 0.0, 2.0]])
    cols = np.array(sorted(v.real for v in dynamics.laplacian_eigenvalues(M, "cols")))
    rows = np.array(sorted(v.real for v in dynamics.laplacian_eigenvalues(M, "rows")))
    assert not np.allclose(cols, rows)


def test_laplacian_stability_k4_spectral_radius():
    """K_4 Laplacian: eigenvalues {0, 4, 4, 4}; spectral radius = 4."""
    A = np.ones((4, 4)) - np.eye(4)  # all-1s off-diagonal
    s = dynamics.laplacian_stability(A, direction="cols")
    assert abs(s["spectral_radius"] - 4.0) < 1e-9


def test_laplacian_stability_kn_algebraic_connectivity():
    """K_n Laplacian's algebraic connectivity = n. Test n=4 and n=5."""
    for n in (4, 5):
        A = np.ones((n, n)) - np.eye(n)
        s = dynamics.laplacian_stability(A, direction="cols")
        assert abs(s["algebraic_connectivity"] - float(n)) < 1e-9, \
            f"K_{n}: got {s['algebraic_connectivity']}, want {n}"


# ============================================================
# create_boolean_rules
# ============================================================

def test_create_boolean_rules_two_node_signed_split_activators_inhibitors():
    """A→B positive, B→A negative, then check rules:
    rule[0] = node A: activators=[], inhibitors=[(1, -3)]
    rule[1] = node B: activators=[(0, 2)], inhibitors=[]
    """
    M = np.array([[0.0, 2.0],
                  [-3.0, 0.0]])  # A→B = +2, B→A = -3
    rules = dynamics.create_boolean_rules(M)
    assert len(rules) == 2

    # Node A (column 0): only inflow is M[1,0] = -3 (B inhibits A).
    rule_a = rules[0]
    assert rule_a["node_id"] == 0
    assert rule_a["activators"] == []
    assert rule_a["inhibitors"] == [(1, -3.0)]
    assert rule_a["threshold"] == 0.0

    # Node B (column 1): only inflow is M[0,1] = +2 (A activates B).
    rule_b = rules[1]
    assert rule_b["node_id"] == 1
    assert rule_b["activators"] == [(0, 2.0)]
    assert rule_b["inhibitors"] == []


# ============================================================
# boolean_attractors
# ============================================================

def test_boolean_attractors_self_loop_basin_conservation():
    """1-node positive self-loop: at least one fixed-point attractor;
    basin sizes sum to 2^1 = 2."""
    M = np.array([[1.0]])
    rules = dynamics.create_boolean_rules(M)
    res = dynamics.boolean_attractors(rules, max_nodes=12)
    assert res.get("error") is None
    assert any(a["type"] == "fixed" for a in res["attractors"])
    total = sum(a["basin_size"] for a in res["attractors"])
    assert total == 2


def test_boolean_attractors_mutual_inhibition_basin_conservation():
    """2-node mutual inhibition: basin sizes sum to 4 regardless of attractor count."""
    M = np.array([[0.0, -1.0],
                  [-1.0, 0.0]])
    rules = dynamics.create_boolean_rules(M)
    res = dynamics.boolean_attractors(rules, max_nodes=12)
    assert res.get("error") is None
    total = sum(a["basin_size"] for a in res["attractors"])
    assert total == 4


def test_boolean_attractors_three_node_positive_ring_has_cycle():
    """3-node positive ring A→B→C→A: at least one cyclic attractor with period >= 2."""
    M = np.array([[0.0, 1.0, 0.0],
                  [0.0, 0.0, 1.0],
                  [1.0, 0.0, 0.0]])
    rules = dynamics.create_boolean_rules(M)
    res = dynamics.boolean_attractors(rules, max_nodes=12)
    assert res.get("error") is None
    total = sum(a["basin_size"] for a in res["attractors"])
    assert total == 8
    # Conservation always; cycle existence is the headline assertion:
    assert any(a["period"] >= 2 for a in res["attractors"])


def test_boolean_attractors_too_large_returns_error_no_exception():
    """Network larger than max_nodes returns an error sentinel; no exception."""
    n = 5
    M = np.eye(n)
    rules = dynamics.create_boolean_rules(M)
    res = dynamics.boolean_attractors(rules, max_nodes=4)
    assert res["error"] == "too_large"
    assert res["n_nodes"] == 5
    assert res["max_nodes"] == 4
    assert res["attractors"] == []


def test_boolean_attractors_basin_conservation_invariant():
    """For any network within max_nodes, basin sizes sum to 2^n_nodes."""
    # Random-ish 4-node network with mixed signs
    rng = np.random.default_rng(42)
    M = rng.standard_normal((4, 4))
    rules = dynamics.create_boolean_rules(M)
    res = dynamics.boolean_attractors(rules, max_nodes=12)
    assert res.get("error") is None
    total = sum(a["basin_size"] for a in res["attractors"])
    assert total == 2 ** 4


# ============================================================
# simulate_dynamics
# ============================================================

def test_simulate_dynamics_identity_keeps_initial_state_constant():
    """M = I, x0 != 0 → trajectory is constant (every row equals x0)."""
    M = np.eye(3)
    x0 = np.array([1.0, 2.0, 3.0])
    traj = dynamics.simulate_dynamics(M, n_iter=10, initial_state=x0)
    assert traj.shape == (11, 3)
    for t in range(11):
        assert np.allclose(traj[t], x0)


def test_simulate_dynamics_stable_eigenvalue_decays():
    """1×1 with |λ|<1: trajectory decays toward zero."""
    M = np.array([[0.5]])
    traj = dynamics.simulate_dynamics(M, n_iter=20, initial_state=np.array([1.0]))
    assert traj[-1, 0] < 1e-3
    # Monotonic decay
    diffs = np.abs(np.diff(traj[:, 0]))
    assert (diffs[1:] <= diffs[:-1] + 1e-12).all()


def test_simulate_dynamics_unstable_eigenvalue_grows():
    """1×1 with |λ|>1: trajectory magnitude grows."""
    M = np.array([[1.5]])
    traj = dynamics.simulate_dynamics(M, n_iter=10, initial_state=np.array([1.0]))
    assert abs(traj[-1, 0]) > abs(traj[0, 0])


def test_simulate_dynamics_random_initial_state_seed_reproducibility():
    """Same seed with initial_state='random' → identical trajectory."""
    M = np.array([[0.5, 0.1], [0.0, 0.5]])
    a = dynamics.simulate_dynamics(M, n_iter=5, initial_state="random", seed=123)
    b = dynamics.simulate_dynamics(M, n_iter=5, initial_state="random", seed=123)
    assert np.allclose(a, b)
    c = dynamics.simulate_dynamics(M, n_iter=5, initial_state="random", seed=124)
    assert not np.allclose(a, c)


# ============================================================
# randomize_matrix
# ============================================================

def test_randomize_matrix_sign_flip_only_changes_signs():
    """kind='sign_flip' must only multiply by ±1 — magnitudes stay the same."""
    M = np.array([[1.0, -2.0, 0.0],
                  [3.0, 0.0, -4.0]])
    rng = np.random.default_rng(7)
    out = dynamics.randomize_matrix(M, kind="sign_flip", rng=rng)
    # Same magnitudes
    assert np.allclose(np.abs(out), np.abs(M))
    # Zeros remain zeros
    assert (out[M == 0] == 0).all()


def test_randomize_matrix_uniform_preserves_zeros():
    """kind='uniform' must perturb only non-zero entries."""
    M = np.array([[0.0, 2.0],
                  [0.0, 0.0]])
    rng = np.random.default_rng(7)
    out = dynamics.randomize_matrix(M, kind="uniform", rng=rng)
    assert out[0, 0] == 0
    assert out[1, 0] == 0
    assert out[1, 1] == 0
    assert out[0, 1] != 2.0  # changed (very high probability)


def test_randomize_matrix_unknown_kind_raises():
    """Invalid `kind` raises ValueError."""
    with pytest.raises(ValueError):
        dynamics.randomize_matrix(np.ones((2, 2)), kind="bogus")


# ============================================================
# state_shift_monte_carlo
# ============================================================

def test_state_shift_monte_carlo_seed_reproducibility():
    """Same seed → identical final_states array (stable matrix → no failures)."""
    M = np.array([[0.5, 0.1], [0.0, 0.5]])
    a = dynamics.state_shift_monte_carlo(M, n_simulations=20, n_iter=50, seed=42)
    b = dynamics.state_shift_monte_carlo(M, n_simulations=20, n_iter=50, seed=42)
    assert np.allclose(a["final_states"], b["final_states"])
    assert a["n_failed"] == b["n_failed"]


def test_state_shift_monte_carlo_summary_keys_present():
    """Per-node summary has mean/sd/p5/p95."""
    M = np.eye(3) * 0.5
    res = dynamics.state_shift_monte_carlo(M, n_simulations=30, n_iter=20, seed=1)
    for i in range(3):
        s = res["summary"][i]
        for k in ("mean", "sd", "p5", "p95"):
            assert k in s


def test_state_shift_monte_carlo_n_failed_accounting():
    """Deliberately divergent matrix: n_failed > 0 and final_states shape
    matches n_succeeded."""
    M = np.eye(2) * 100.0  # large positive eigenvalues → divergent under perturbation
    res = dynamics.state_shift_monte_carlo(M, n_simulations=10, n_iter=200, seed=0)
    assert res["n_simulations"] == 10
    n_failed = res["n_failed"]
    n_succ = 10 - n_failed
    assert res["final_states"].shape == (n_succ, 2)
    assert n_failed >= 1, "expected at least some divergent runs"


def test_state_shift_monte_carlo_empty_matrix_raises():
    """Empty matrix raises ValueError."""
    with pytest.raises(ValueError):
        dynamics.state_shift_monte_carlo(np.zeros((0, 0)), n_simulations=5)


def test_state_shift_monte_carlo_returns_n_simulations_field():
    """Result includes n_simulations field set from input."""
    res = dynamics.state_shift_monte_carlo(np.eye(2) * 0.5, n_simulations=7, seed=0)
    assert res["n_simulations"] == 7


# ============================================================
# Edge cases (cross-function)
# ============================================================

def test_simulate_dynamics_non_square_raises():
    M = np.zeros((2, 3))
    with pytest.raises(ValueError):
        dynamics.simulate_dynamics(M, n_iter=1)


def test_laplacian_non_square_raises():
    M = np.zeros((2, 3))
    with pytest.raises(ValueError):
        dynamics.laplacian_eigenvalues(M)


def test_all_zero_matrix_single_absorbing_attractor():
    """All-zero N×N: every state has zero inflow and `0 > 0` is False under
    threshold-strict semantics, so every state maps to state-zero. Result: a
    single fixed-point attractor at state-zero with basin = 2^N.

    NOTE: this contradicts a literal reading of the spec section 6 edge case
    that claims 2^N fixed points. That spec wording was based on a tiebreaker
    semantics ('keep current state when inflow == threshold') which makes the
    spec's three-node ring oscillator test impossible. We picked
    threshold-strict (matches the ring test, which is the canonical Boolean
    network behaviour) and accept that the all-zero edge case becomes a
    single absorbing attractor."""
    M = np.zeros((3, 3))
    rules = dynamics.create_boolean_rules(M)
    res = dynamics.boolean_attractors(rules, max_nodes=12)
    assert len(res["attractors"]) == 1
    assert res["attractors"][0]["type"] == "fixed"
    assert res["attractors"][0]["basin_size"] == 2 ** 3
    assert res["attractors"][0]["states"] == [0]


def test_single_node_network_handled_by_every_function():
    """1-node network must work end-to-end."""
    M = np.array([[0.5]])
    # Laplacian
    s = dynamics.laplacian_stability(M)
    assert "spectral_radius" in s
    # Simulate
    traj = dynamics.simulate_dynamics(M, n_iter=5, initial_state=np.array([1.0]))
    assert traj.shape == (6, 1)
    # Boolean
    rules = dynamics.create_boolean_rules(M)
    res = dynamics.boolean_attractors(rules, max_nodes=12)
    assert sum(a["basin_size"] for a in res["attractors"]) == 2
    # Monte Carlo
    mc = dynamics.state_shift_monte_carlo(M, n_simulations=5, n_iter=10, seed=0)
    assert mc["n_simulations"] == 5


# ============================================================
# Bit-encoding contract test
# ============================================================

def test_boolean_attractors_state_encoding_bit_zero_is_node_zero():
    """The integer state encoding in `boolean_attractors` must place node i
    at bit i of the integer (LSB-first by node index).

    This is implicitly contracted by `_format_state` in
    `sespy.modules.analysis_boolean` which reverses the binary string so
    character index 0 corresponds to bit 0. If anyone ever flips the
    convention in either direction, this test catches the desync.
    """
    # Single-node positive self-loop: state 1 (bit 0 set) must be a fixed
    # point (the active state stays active).
    M = np.array([[1.0]])
    rules = dynamics.create_boolean_rules(M)
    res = dynamics.boolean_attractors(rules, max_nodes=12)
    fixed_states = [a["states"][0] for a in res["attractors"] if a["type"] == "fixed"]
    assert 1 in fixed_states, (
        f"expected state=1 (bit 0 = on) to be a fixed point, got fixed states {fixed_states}"
    )

    # Two-node network where ONLY node 1 has a positive self-loop:
    # M[1, 1] = 1, all other entries = 0. Then state with bit 1 set
    # (i.e., integer 2) must be a fixed point; state with bit 0 set
    # (integer 1) must not be (no self-loop on node 0 → goes to 0).
    M = np.array([[0.0, 0.0],
                  [0.0, 1.0]])
    rules = dynamics.create_boolean_rules(M)
    res = dynamics.boolean_attractors(rules, max_nodes=12)
    fixed_states = [a["states"][0] for a in res["attractors"] if a["type"] == "fixed"]
    # State 2 = 0b10 = node 1 is on → keeps itself active (self-loop)
    assert 2 in fixed_states, (
        f"expected state=2 (bit 1 = on) to be fixed when only node 1 has self-loop; "
        f"got fixed states {fixed_states}"
    )

# NOTE: test_token_diffusion_contested_sign and _sample_golden pin numpy's
# PCG64 stream (seeded draws). numpy's stream-stability guarantee for
# default_rng is softer than RandomState's, so a numpy upgrade could change
# these numbers without any bug in token_diffusion — re-derive the goldens
# rather than hunting a phantom regression. The chain and sink tests are
# stream-independent (out-degree 1 everywhere) and remain valid.
# ============================================================
# token_diffusion (issue #17)
# ============================================================


def _chain_isa():
    """A -> B -(-)-> C -> D: a single route, so every token's itinerary is
    known in advance and the whole result is hand-checkable."""
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABCD"]
    conns = [Connection(source="A", target="B", polarity="+"),
             Connection(source="B", target="C", polarity="-"),
             Connection(source="C", target="D", polarity="+")]
    return _isa(els, conns)


def test_token_diffusion_matches_manual_trace():
    r = dynamics.token_diffusion(_chain_isa(), "A",
                                 n_steps=5, n_tokens=100, seed=0)
    assert r["source"] == "A" and r["n_reached"] == 3
    assert r["n_batches"] == 20
    assert r["rows"] == [
        {"id": "B", "label": "b", "tokens_received": 100, "margin": 0,
         "net_sign": "+", "first_arrival_step": 1, "rank": 1},
        {"id": "C", "label": "c", "tokens_received": 100, "margin": 0,
         "net_sign": "-", "first_arrival_step": 2, "rank": 1},
        {"id": "D", "label": "d", "tokens_received": 100, "margin": 0,
         "net_sign": "-", "first_arrival_step": 3, "rank": 1},
    ]


def test_token_diffusion_sink_tokens_stop():
    # T has no outgoing edges: its 50 tokens arrive once at step 2 and are
    # NOT re-counted on steps 3-6. A regression that keeps sinks "live"
    # would credit T four more times.
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in ("A", "B", "T")]
    conns = [Connection(source="A", target="B", polarity="+"),
             Connection(source="B", target="T", polarity="+")]
    r = dynamics.token_diffusion(_isa(els, conns), "A",
                                 n_steps=6, n_tokens=50, seed=0)
    assert [(x["id"], x["tokens_received"], x["first_arrival_step"])
            for x in r["rows"]] == [("B", 50, 1), ("T", 50, 2)]


def test_token_diffusion_contested_sign():
    # Equal-probability +/- routes converge on T: the split lands inside
    # the 5% margin at this seed, so T is contested rather than signed.
    els = [Element(id=i, label=i.lower(), type="Drivers")
           for i in ("A", "X", "Y", "T")]
    conns = [Connection(source="A", target="X", polarity="+"),
             Connection(source="A", target="Y", polarity="-"),
             Connection(source="X", target="T", polarity="+"),
             Connection(source="Y", target="T", polarity="+")]
    r = dynamics.token_diffusion(_isa(els, conns), "A",
                                 n_steps=3, n_tokens=1000, seed=1)
    by_id = {x["id"]: x for x in r["rows"]}
    assert by_id["T"]["net_sign"] == "~"
    assert by_id["T"]["tokens_received"] == 1000
    assert by_id["X"]["net_sign"] == "+" and by_id["Y"]["net_sign"] == "-"
    assert by_id["X"]["tokens_received"] + by_id["Y"]["tokens_received"] == 1000


def test_token_diffusion_seed_reproducible_and_distinct():
    isa = _isa([Element(id=i, label=i.lower(), type="Drivers")
                for i in ("A", "X", "Y", "T")],
               [Connection(source="A", target="X"),
                Connection(source="A", target="Y"),
                Connection(source="X", target="T"),
                Connection(source="Y", target="T")])
    a = dynamics.token_diffusion(isa, "A", n_tokens=500, seed=3)
    b = dynamics.token_diffusion(isa, "A", n_tokens=500, seed=3)
    c = dynamics.token_diffusion(isa, "A", n_tokens=500, seed=4)
    assert a == b
    assert a != c


def test_token_diffusion_sample_golden():
    from pathlib import Path

    from sespy.data_structure import load_sample

    root = Path(__file__).resolve().parents[1]
    r = dynamics.token_diffusion(load_sample(root / "data" / "sample_ses.json"),
                                 "D001", seed=0)
    assert r["n_reached"] == 7
    assert r["n_steps"] == 10 and r["n_tokens"] == 1000
    assert [(x["rank"], x["id"], x["tokens_received"], x["margin"],
             x["net_sign"], x["first_arrival_step"]) for x in r["rows"]] == [
        (1, "P001", 2000, 0, "+", 2),
        (1, "MPF1", 2000, 0, "-", 3),
        (3, "GB01", 1501, 32, "-", 5),
        (3, "A001", 1499, 32, "+", 1),
        (5, "ES03", 1002, 44, "-", 4),
        (5, "ES01", 998, 44, "-", 4),
        (7, "R002", 501, 32, "-", 6),
    ]
    assert all(x["id"] != "D001" for x in r["rows"])  # source excluded


def test_token_diffusion_degenerate_shapes():
    chain = _chain_isa()
    for kwargs in ({"n_tokens": 0}, {"n_steps": 0}):
        r = dynamics.token_diffusion(chain, "A", seed=0, **kwargs)
        assert r["rows"] == [] and r["n_reached"] == 0
    # unknown source
    assert dynamics.token_diffusion(chain, "NOPE", seed=0)["rows"] == []
    # empty model
    assert dynamics.token_diffusion(IsaData(), "A", seed=0)["rows"] == []
    # sink SOURCE: nothing can leave, so nothing is ever received
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in ("A", "B")]
    r = dynamics.token_diffusion(_isa(els, [Connection(source="B", target="A")]),
                                 "A", n_steps=5, n_tokens=10, seed=0)
    assert r == {"rows": [], "source": "A", "n_tokens": 10,
                 "n_steps": 5, "n_reached": 0, "n_batches": 0}


def test_token_diffusion_balanced_node_is_contested_at_both_seeds():
    # THE regression test for issue #19: the old fixed 5% margin called
    # this structurally balanced node "-" at seed 0 (a 473/527 split is
    # well inside sampling error at n=1000). The t-test must say "~" at
    # both seeds.
    els = [Element(id=i, label=i.lower(), type="Drivers")
           for i in ("A", "X", "Y", "T")]
    conns = [Connection(source="A", target="X", polarity="+"),
             Connection(source="A", target="Y", polarity="-"),
             Connection(source="X", target="T", polarity="+"),
             Connection(source="Y", target="T", polarity="+")]
    isa = _isa(els, conns)
    for seed in (0, 1):
        r = dynamics.token_diffusion(isa, "A", n_steps=3, n_tokens=1000,
                                     seed=seed)
        t_row = next(x for x in r["rows"] if x["id"] == "T")
        assert t_row["net_sign"] == "~", f"seed {seed} misread a tie as signed"
        assert t_row["tokens_received"] == 1000 and t_row["margin"] == 0
        # X and Y are genuinely signed and tie with each other on count.
        x_row = next(x for x in r["rows"] if x["id"] == "X")
        y_row = next(x for x in r["rows"] if x["id"] == "Y")
        assert x_row["net_sign"] == "+" and y_row["net_sign"] == "-"
        assert x_row["rank"] == y_row["rank"]


def test_token_diffusion_ties_share_a_rank():
    # GB01 1501 +/-32 and A001 1499 +/-32 overlap almost entirely: the
    # review measured that ordering flipping in 20 of 50 seeds, so they
    # must not be presented as distinct ranks.
    from pathlib import Path

    from sespy.data_structure import load_sample

    root = Path(__file__).resolve().parents[1]
    r = dynamics.token_diffusion(load_sample(root / "data" / "sample_ses.json"),
                                 "D001", seed=0)
    by_id = {x["id"]: x for x in r["rows"]}
    assert by_id["GB01"]["rank"] == by_id["A001"]["rank"] == 3
    assert by_id["ES03"]["rank"] == by_id["ES01"]["rank"] == 5
    assert by_id["R002"]["rank"] == 7  # clear of the pair above it
    # A margin must never be negative, and a deterministic count has none.
    assert all(x["margin"] >= 0 for x in r["rows"])
    assert by_id["P001"]["margin"] == 0


def _rows(*batch_vectors):
    """Build rank-rule input rows from per-batch arrival vectors."""
    import numpy as _np

    rows = [{"tokens_received": int(sum(v)), "margin": 0,
             "_batches": _np.array(v, dtype=float)} for v in batch_vectors]
    rows.sort(key=lambda r: -r["tokens_received"])
    return rows


_CRIT4 = 3.182  # t(0.975, df=3) for the 4-batch fixtures below


def test_assign_ranks_does_not_chain_separation_transitively():
    # Separation is not transitive: A can tie B and B tie C while A and C
    # are cleanly apart. Comparing each row only with its immediate
    # predecessor chained the tie down the list, so a gently-decreasing
    # profile collapsed toward a single rank (issue #21).
    #
    # Totals 400 / 368 / 336. Each adjacent difference averages 8 but swings
    # between 2 and 14, so neither pair separates. The two swings are
    # anticorrelated, so they cancel: the leader-to-third difference is a
    # rock-steady 16 every batch and separates decisively. Chaining would
    # return 1,1,1 here; comparing against the leader returns 1,1,3.
    rows = _rows([100, 100, 100, 100], [98, 86, 98, 86], [84, 84, 84, 84])
    dynamics._assign_ranks(rows, True, _CRIT4, 4)
    assert [r["rank"] for r in rows] == [1, 1, 3]


def test_assign_ranks_unquantified_claims_no_distinct_rank():
    # A single batch has no spread to estimate; every row must stay rank 1.
    rows = _rows([9], [5], [1])
    dynamics._assign_ranks(rows, False, 0.0, 1)
    assert [r["rank"] for r in rows] == [1, 1, 1]


def test_assign_ranks_separates_cleanly_disjoint_rows():
    rows = _rows([100, 100, 100, 100], [50, 50, 50, 50], [10, 10, 10, 10])
    dynamics._assign_ranks(rows, True, _CRIT4, 4)
    assert [r["rank"] for r in rows] == [1, 2, 3]


def test_assign_ranks_identical_deterministic_counts_tie():
    # Zero variance, zero difference: a tie, not a spurious separation.
    rows = _rows([50, 50, 50, 50], [50, 50, 50, 50])
    dynamics._assign_ranks(rows, True, _CRIT4, 4)
    assert [r["rank"] for r in rows] == [1, 1]


def test_assign_ranks_pairing_beats_independent_margins():
    # The point of pairing. Both fixtures have the SAME totals and the same
    # per-element spread, so any rule reading only the two display intervals
    # must return the same answer for both. The paired difference does not,
    # because the correlation between the columns differs.
    #
    # Positively correlated (elements share an upstream path): the batches
    # move together, so the difference is rock steady at 20 -> separated.
    together = _rows([100, 120, 80, 100], [80, 100, 60, 80])
    dynamics._assign_ranks(together, True, _CRIT4, 4)
    assert [r["rank"] for r in together] == [1, 2]

    # Negatively correlated (competing sinks: a token reaching one did not
    # reach the other). Same totals, same per-element variance, but the
    # difference now swings wildly -> honestly a tie.
    competing = _rows([100, 120, 80, 100], [80, 60, 100, 80])
    dynamics._assign_ranks(competing, True, _CRIT4, 4)
    assert [r["rank"] for r in competing] == [1, 1]

    # Guard the premise: the two fixtures really are indistinguishable to a
    # rule that only reads totals and per-element spread.
    assert ([r["tokens_received"] for r in together]
            == [r["tokens_received"] for r in competing])
    assert ([round(float(r["_batches"].var(ddof=1)), 6) for r in together]
            == [round(float(r["_batches"].var(ddof=1)), 6) for r in competing])


def test_token_diffusion_batches_adapt_to_small_token_counts():
    r = dynamics.token_diffusion(_chain_isa(), "A", n_steps=3, n_tokens=5,
                                 seed=0)
    assert r["n_batches"] == 5           # fewer tokens than the 20 default
    assert all(x["margin"] == 0 for x in r["rows"])


def test_token_diffusion_single_token_claims_no_certainty():
    # One token = one batch = no spread to estimate. Reporting a firm sign
    # or a distinct rank off a single sample is the failure this feature
    # exists to prevent.
    r = dynamics.token_diffusion(_chain_isa(), "A", n_steps=3, n_tokens=1,
                                 seed=0)
    assert r["n_batches"] == 1
    assert all(x["net_sign"] == "~" for x in r["rows"])
    assert all(x["rank"] == 1 for x in r["rows"])
    assert all(x["margin"] == 0 for x in r["rows"])
