"""SES dynamics — pure-Python numerics layer for analysis modules.

Subset port of `functions/ses_dynamics.R`. No Shiny imports; safe to use
from unit tests, scripts, or future analysis modules.

Used by:
  - sespy.modules.analysis_boolean (Laplacian + Boolean attractors)
  - sespy.modules.analysis_simulation (deterministic sim + Monte Carlo)
"""
from __future__ import annotations

from typing import Any, TypedDict

import numpy as np

from . import network as _net  # for _STRENGTH_RANK
from .data_structure import IsaData

# =============================================================================
# Matrix construction
# =============================================================================

def isa_to_numeric_matrix(isa: IsaData) -> tuple[np.ndarray, list[str]]:
    """Build signed weighted adjacency matrix from ISA data.

    Convention: ``M[i, j] = polarity_sign * strength_rank`` for edge i→j
    (row=source, col=target). Multiple edges between the same pair are summed.
    Self-loops (source == target) are summed onto the diagonal; downstream
    Laplacian and dynamics functions handle that case correctly.

    Returns
    -------
    M
        ``np.ndarray`` of shape ``(n, n)`` with float entries.
    node_ids
        Ordered list of element ids. ``M[i, j]`` corresponds to the edge from
        ``node_ids[i]`` to ``node_ids[j]``.

    Raises
    ------
    ValueError
        If a connection references an element id not present in ``isa.elements``.
    """
    node_ids = [el.id for el in isa.elements]
    n = len(node_ids)
    if n == 0:
        return np.zeros((0, 0)), []

    idx = {nid: i for i, nid in enumerate(node_ids)}
    M = np.zeros((n, n), dtype=float)
    for c in isa.connections:
        if c.source not in idx or c.target not in idx:
            raise ValueError(
                f"Connection references unknown element: "
                f"{c.source!r} -> {c.target!r}"
            )
        sign = 1.0 if c.polarity == "+" else -1.0
        weight = float(_net._STRENGTH_RANK.get(c.strength, 2))
        M[idx[c.source], idx[c.target]] += sign * weight
    return M, node_ids


# =============================================================================
# Laplacian spectral analysis
# =============================================================================

class LaplacianStability(TypedDict):
    """Result of :func:`laplacian_stability`.

    Fields:
        eigenvalues: All Laplacian eigenvalues, sorted ascending by real part.
        dominant: The eigenvalue with the largest modulus |λ|.
        spectral_radius: max |λ| over the spectrum.
        algebraic_connectivity: real part of the second-smallest eigenvalue.
        stability_class: ``"connected"`` (alg_conn > 1e-9), ``"disconnected"`` (≤),
            or ``"trivial"`` (empty matrix).
    """
    eigenvalues: np.ndarray
    dominant: complex
    spectral_radius: float
    algebraic_connectivity: float
    stability_class: str


def laplacian_eigenvalues(mat: np.ndarray, direction: str = "cols") -> np.ndarray:
    """Eigenvalues of the graph Laplacian ``L = D - A``.

    The signed weighted matrix is converted to a magnitude graph
    (``A = |mat|``) before forming the Laplacian; signs encode CLD polarity
    not graph topology.

    Parameters
    ----------
    mat
        Square ``(n, n)`` numpy array.
    direction
        ``"cols"`` (default) — degrees are column sums (in-degrees).
        ``"rows"`` — degrees are row sums (out-degrees).

    Returns
    -------
    np.ndarray of complex eigenvalues, sorted ascending by real part.

    Raises
    ------
    ValueError
        If ``mat`` is not square or ``direction`` is invalid.
    """
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError(f"Matrix must be square; got shape {mat.shape}")
    if direction not in ("cols", "rows"):
        raise ValueError(f"direction must be 'cols' or 'rows', got {direction!r}")
    A = np.abs(mat)
    d = A.sum(axis=0) if direction == "cols" else A.sum(axis=1)
    L = np.diag(d) - A
    eigvals = np.linalg.eigvals(L)
    return np.array(sorted(eigvals, key=lambda v: v.real))


def laplacian_stability(mat: np.ndarray, direction: str = "cols") -> LaplacianStability:
    """Spectral characterization of a Laplacian.

    For asymmetric (directed) magnitude Laplacians, eigenvalues may be complex.
    `algebraic_connectivity` and `spectral_radius` use the real part / modulus
    respectively; imaginary components are discarded silently.

    Returns
    -------
    dict matching :class:`LaplacianStability`. Empty matrices return zeroed
    fields with ``stability_class == "trivial"``.
    """
    eigvals = laplacian_eigenvalues(mat, direction)
    if eigvals.size == 0:
        return LaplacianStability(
            eigenvalues=eigvals,
            dominant=0 + 0j,
            spectral_radius=0.0,
            algebraic_connectivity=0.0,
            stability_class="trivial",
        )

    abs_eig = np.abs(eigvals)
    spectral_radius = float(abs_eig.max())
    dominant = eigvals[int(np.argmax(abs_eig))]

    # Algebraic connectivity: second-smallest eigenvalue by real part
    # eigvals is already sorted ascending by real part (laplacian_eigenvalues guarantees this)
    if eigvals.size >= 2:
        alg_conn = float(eigvals[1].real)
    else:
        alg_conn = float(eigvals[0].real)

    # For a graph Laplacian: algebraic_connectivity > tolerance ⇔ connected
    if alg_conn > 1e-9:
        cls = "connected"
    else:
        cls = "disconnected"

    return LaplacianStability(
        eigenvalues=eigvals,
        dominant=dominant,
        spectral_radius=spectral_radius,
        algebraic_connectivity=alg_conn,
        stability_class=cls,
    )


# =============================================================================
# Boolean rules + attractors
# =============================================================================

def create_boolean_rules(mat: np.ndarray) -> list[dict[str, Any]]:
    """Build Boolean update rules from a signed weighted matrix.

    For each node ``j`` (column), input at next step is
    ``sum_i M[i, j] * x_i``. Activators are nodes ``i`` with ``M[i, j] > 0``;
    inhibitors have ``M[i, j] < 0``. Threshold defaults to 0 — node ``j`` is
    on at the next step iff input > threshold.

    Returns one dict per node:
        ``{"node_id": int, "activators": [(i, w), ...],
           "inhibitors": [(i, w), ...], "threshold": float}``
    """
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError(f"Matrix must be square; got shape {mat.shape}")
    n = mat.shape[0]
    rules: list[dict[str, Any]] = []
    for j in range(n):
        activators = [(i, float(mat[i, j])) for i in range(n) if mat[i, j] > 0]
        inhibitors = [(i, float(mat[i, j])) for i in range(n) if mat[i, j] < 0]
        rules.append({
            "node_id": j,
            "activators": activators,
            "inhibitors": inhibitors,
            "threshold": 0.0,
        })
    return rules


def boolean_attractors(
    rules: list[dict[str, Any]],
    max_nodes: int = 12,
) -> dict[str, Any]:
    """Exhaustive ``2^N`` state-space search for Boolean network attractors.

    Each state is encoded as an integer 0..2^N-1 where bit ``i`` is the value
    of node ``i``. The deterministic update map ``next_state[s]`` is computed
    once, then attractors are found via cycle detection: walk forward from
    each unvisited state, stop on revisit, classify the cycle.

    Parameters
    ----------
    rules
        Output of :func:`create_boolean_rules`.
    max_nodes
        Hard cap on ``len(rules)``; networks above it return an error sentinel
        rather than running (2^N grows fast).

    Returns
    -------
    dict
        Success: ``{"attractors": [...], "total_states": 2**n}``, where each
        attractor is ``{"type": "fixed"|"cyclic", "states": [...], "period": int,
        "basin_size": int}``. ``basin_size`` always sums to ``2^n_nodes``.

        Too-large: ``{"attractors": [], "error": "too_large", "n_nodes": int,
        "max_nodes": int, "total_states": 0}``.
    """
    n = len(rules)
    if n > max_nodes:
        return {
            "attractors": [],
            "error": "too_large",
            "n_nodes": n,
            "max_nodes": max_nodes,
            "total_states": 0,
        }
    if n == 0:
        return {"attractors": [], "total_states": 0}

    n_states = 1 << n  # 2**n

    # Precompute the deterministic transition function s -> next(s).
    next_state = np.zeros(n_states, dtype=np.int64)
    for s in range(n_states):
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
        next_state[s] = new

    # Cycle detection. Each state ends up labeled with an attractor id.
    attractor_id = np.full(n_states, -1, dtype=np.int64)
    attractors: list[dict[str, Any]] = []

    for start in range(n_states):
        if attractor_id[start] != -1:
            continue
        # Walk forward, recording the path as a stack with index lookup.
        path: list[int] = []
        position: dict[int, int] = {}
        cur = start
        while attractor_id[cur] == -1 and cur not in position:
            position[cur] = len(path)
            path.append(cur)
            cur = int(next_state[cur])

        if attractor_id[cur] != -1:
            # Joined an already-known basin; label all path states.
            aid = int(attractor_id[cur])
            for s in path:
                attractor_id[s] = aid
        else:
            # Found a new cycle starting at `cur`.
            cycle_start_idx = position[cur]
            cycle_states = path[cycle_start_idx:]
            aid = len(attractors)
            attractors.append({
                "type": "fixed" if len(cycle_states) == 1 else "cyclic",
                "states": list(cycle_states),
                "period": len(cycle_states),
                "basin_size": 0,  # filled below
            })
            for s in path:
                attractor_id[s] = aid

    # Count basin sizes from the labeling.
    counts = np.bincount(attractor_id, minlength=len(attractors))
    for a, c in zip(attractors, counts):
        a["basin_size"] = int(c)

    return {"attractors": attractors, "total_states": n_states}


# =============================================================================
# Deterministic simulation
# =============================================================================

def simulate_dynamics(
    mat: np.ndarray,
    n_iter: int = 200,
    initial_state: str | np.ndarray = "zeros",
    seed: int | None = None,
) -> np.ndarray:
    """Linear matrix iteration ``x_{t+1} = M @ x_t``.

    Parameters
    ----------
    mat
        Square ``(n, n)`` array.
    n_iter
        Number of iterations. The returned trajectory has ``n_iter + 1`` rows.
    initial_state
        ``"zeros"`` (default) → ``np.zeros(n)``.
        ``"uniform"`` → ``np.ones(n)``.
        ``"random"`` → ``rng.standard_normal(n)``; ``seed`` is required for
        reproducibility.
        Otherwise an explicit ``(n,)`` array.
    seed
        Only used when ``initial_state == "random"``.

    Returns
    -------
    np.ndarray of shape ``(n_iter + 1, n)``.
    """
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError(f"Matrix must be square; got shape {mat.shape}")
    n = mat.shape[0]

    if isinstance(initial_state, str):
        if initial_state == "zeros":
            x = np.zeros(n)
        elif initial_state == "uniform":
            x = np.ones(n)
        elif initial_state == "random":
            rng = np.random.default_rng(seed)
            x = rng.standard_normal(n)
        else:
            raise ValueError(
                f"Unknown initial_state preset: {initial_state!r} "
                "(expected 'zeros', 'uniform', 'random', or an ndarray)"
            )
    else:
        x = np.asarray(initial_state, dtype=float)
        if x.shape != (n,):
            raise ValueError(
                f"initial_state shape {x.shape} != ({n},)"
            )

    traj = np.empty((n_iter + 1, n), dtype=float)
    traj[0] = x
    for t in range(n_iter):
        traj[t + 1] = mat @ traj[t]
    return traj


# =============================================================================
# Stochastic perturbation + Monte Carlo
# =============================================================================

def randomize_matrix(
    mat: np.ndarray,
    kind: str = "uniform",
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Perturb the non-zero entries of ``mat`` to make a perturbed matrix.

    Used by :func:`state_shift_monte_carlo` to generate sampled neighbours of
    the given matrix. Zero entries are preserved (they represent absent edges,
    not noisy zero-weight edges).

    Parameters
    ----------
    mat
        Square or rectangular numpy array.
    kind
        ``"uniform"`` — multiplicative ±20% uniform noise.
        ``"sign_flip"`` — each non-zero entry has 10% chance to flip sign.
        ``"gaussian"`` — multiplicative Gaussian noise, σ=0.1.
    rng
        Numpy ``Generator``. The caller is responsible for passing a
        single ``rng`` across many calls (otherwise reseeding from the same
        seed every call yields identical perturbations across simulations).

    Returns
    -------
    np.ndarray of the same shape as ``mat``.
    """
    if rng is None:
        rng = np.random.default_rng()
    out = mat.copy()
    nz = mat != 0
    n_nz = int(nz.sum())
    if n_nz == 0:
        return out

    if kind == "uniform":
        factors = 1.0 + 0.2 * (rng.random(n_nz) * 2 - 1)
        out[nz] = out[nz] * factors
    elif kind == "sign_flip":
        flips = rng.random(n_nz) < 0.1
        signs = np.where(flips, -1.0, 1.0)
        out[nz] = out[nz] * signs
    elif kind == "gaussian":
        out[nz] = out[nz] * (1.0 + 0.1 * rng.standard_normal(n_nz))
    else:
        raise ValueError(
            f"Unknown perturbation kind: {kind!r} "
            "(expected 'uniform', 'sign_flip', or 'gaussian')"
        )
    return out


class StateShiftSummary(TypedDict):
    mean: float
    sd: float
    p5: float
    p95: float


class StateShiftResult(TypedDict):
    final_states: np.ndarray
    summary: dict[int, StateShiftSummary]
    n_simulations: int
    n_failed: int


def state_shift_monte_carlo(
    mat: np.ndarray,
    n_simulations: int = 100,
    n_iter: int = 200,
    kind: str = "uniform",
    seed: int | None = None,
) -> StateShiftResult:
    """Monte Carlo state-shift analysis.

    Runs ``n_simulations`` iterations of: perturb ``mat`` via
    :func:`randomize_matrix`, simulate from a random initial state, record
    the final state. Diverging runs (any non-finite entry in the final
    state) are counted in ``n_failed`` and dropped from aggregates.

    Returns
    -------
    dict
        ``final_states`` is shape ``(n_succeeded, n_nodes)``; ``summary[i]``
        gives ``mean/sd/p5/p95`` for node ``i`` across succeeded runs.

    Raises
    ------
    ValueError
        For empty or non-square matrices.
    """
    if mat.size == 0:
        raise ValueError("Cannot run Monte Carlo on empty matrix")
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError(f"Matrix must be square; got shape {mat.shape}")

    rng = np.random.default_rng(seed)
    n = mat.shape[0]
    finals: list[np.ndarray] = []
    n_failed = 0
    for _ in range(n_simulations):
        perturbed = randomize_matrix(mat, kind=kind, rng=rng)
        x0 = rng.standard_normal(n)
        traj = simulate_dynamics(perturbed, n_iter=n_iter, initial_state=x0)
        final = traj[-1]
        if np.isfinite(final).all():
            finals.append(final)
        else:
            n_failed += 1

    if finals:
        final_states = np.array(finals)
    else:
        final_states = np.zeros((0, n))

    summary: dict[int, StateShiftSummary] = {}
    for i in range(n):
        col = final_states[:, i] if final_states.size else np.array([])
        if col.size:
            summary[i] = StateShiftSummary(
                mean=float(col.mean()),
                sd=float(col.std(ddof=1)) if col.size > 1 else 0.0,
                p5=float(np.percentile(col, 5)),
                p95=float(np.percentile(col, 95)),
            )
        else:
            summary[i] = StateShiftSummary(
                mean=float("nan"),
                sd=float("nan"),
                p5=float("nan"),
                p95=float("nan"),
            )

    return StateShiftResult(
        final_states=final_states,
        summary=summary,
        n_simulations=n_simulations,
        n_failed=n_failed,
    )
