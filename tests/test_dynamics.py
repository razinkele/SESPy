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
