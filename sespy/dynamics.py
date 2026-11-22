"""SES dynamics — pure-Python numerics layer for analysis modules.

Subset port of `functions/ses_dynamics.R`. No Shiny imports; safe to use
from unit tests, scripts, or future analysis modules.

Used by:
  - sespy.modules.analysis_boolean (Laplacian + Boolean attractors)
  - sespy.modules.analysis_simulation (deterministic sim + Monte Carlo)
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import chain
from typing import Any, TypedDict

import networkx as nx
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


def isa_to_dynamics_matrix(isa: IsaData) -> tuple[np.ndarray, list[str]]:
    """Build the matrix used for state iteration (``x_{t+1} = A @ x_t``).

    ``isa_to_numeric_matrix`` documents ``M[i, j]`` as the edge i->j
    (row=source, col=target) — that orientation is what ``create_boolean_rules``
    reads (input to node j = sum_i M[i, j] * x_i) and must not change.

    But ``simulate_dynamics`` computes ``x_{t+1} = A @ x_t``, i.e.
    ``x_{t+1}[i] = sum_j A[i, j] * x_t[j]`` — node i's next state depends on
    column j. To make that sum run over i's IN-edges (the nodes that
    influence i) rather than i's out-edges, ``A`` must be ``M`` transposed:
    entry ``A[i, j]`` is the influence of j on i (row=target, col=source).

    This function is exactly ``isa_to_numeric_matrix(isa)[0].T`` — it
    delegates rather than duplicating the build loop.

    Returns
    -------
    A
        ``np.ndarray`` of shape ``(n, n)``, the transpose of
        ``isa_to_numeric_matrix``'s matrix.
    node_ids
        Same ordered list of element ids as ``isa_to_numeric_matrix`` returns.
    """
    M, node_ids = isa_to_numeric_matrix(isa)
    return M.T, node_ids


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


# Server-side ceiling for library callers of boolean_attractors (R
# DYNAMICS_MAX_BOOLEAN_NODES). This pure-Python 2^N search keeps its cap for
# library callers (Nid4Ocean calls it with max_nodes=12; it is also the test
# oracle). The app uses boolean_attractors_core instead, whose limit is on
# the feedback core (BOOLEAN_MAX_CORE), not on the whole network.
BOOLEAN_MAX_NODES_CEILING = 20


def clamp_max_nodes(value: int, *, lo: int, hi: int) -> int:
    """Clamp a node cap to [lo, hi]. Shared by boolean_attractors (library
    ceiling) and the Boolean module (UI range)."""
    return max(lo, min(hi, int(value)))


def boolean_attractors(
    rules: list[dict[str, Any]],
    max_nodes: int = 12,
    *,
    ceiling: int = BOOLEAN_MAX_NODES_CEILING,
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
        rather than running (2^N grows fast). Clamped to ``[1, ceiling]``
        first; the sentinel reports the clamped value.
    ceiling
        Upper bound for ``max_nodes`` (default BOOLEAN_MAX_NODES_CEILING = 20).

    Returns
    -------
    dict
        Success: ``{"attractors": [...], "total_states": 2**n}``, where each
        attractor is ``{"type": "fixed"|"cyclic", "states": [...], "period": int,
        "basin_size": int}``. ``basin_size`` always sums to ``2^n_nodes``.

        Too-large: ``{"attractors": [], "error": "too_large", "n_nodes": int,
        "max_nodes": int, "total_states": 0}``.
    """
    max_nodes = clamp_max_nodes(max_nodes, lo=1, hi=ceiling)
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
# Boolean attractors at scale: feedback-core search (spec 2026-11-21 §3.1, §3.3)
# =============================================================================
#
# Full-network states are Python ints (bit i = node i) and never packed into
# fixed-width numpy integers, so there is no 62/64-node limit. Numpy integer
# arrays below only ever hold *compact* indices of at most 20 bits: a core
# state (bit b = node C[b], |C| <= BOOLEAN_MAX_CORE) or an upstream-input
# pattern (|Iu| <= |U_a| <= _BOOLEAN_MAX_UPSTREAM_ANCESTORS).

BOOLEAN_MAX_CORE = 20
# Core-state evaluations allowed for the exact basin pass; otherwise sampled.
BOOLEAN_BASIN_BUDGET = 1 << 24
# Sanity cap on the whole network.
BOOLEAN_MAX_NODES_TOTAL = 200

_BOOLEAN_MAX_UPSTREAM_ANCESTORS = 20  # 2^|U_a| upstream starts, simulated exactly
_BOOLEAN_CHUNK_ROWS = 1 << 20         # rows per batch in the basin pass


def _boolean_step(
    rules: list[dict[str, Any]],
    X: np.ndarray,
    *,
    cols: Sequence[int],
    nodes: Sequence[int],
    fixed: Mapping[int, int] | None = None,
) -> np.ndarray:
    """One synchronous update of ``nodes`` for every row of ``X``.

    ``X`` is a ``(S, len(cols))`` uint8 matrix whose column ``k`` holds node
    ``cols[k]``; ``fixed`` gives a constant 0/1 for every other node that an
    evaluated rule reads. Returns the ``(S, len(nodes))`` uint8 matrix of next
    values.

    For node ``j`` the inflow starts at ``0.0`` and adds ``w * x_i`` for each
    activator in list order, then each inhibitor in list order, with a fixed
    node's constant added in its list position. The node is on iff
    ``inflow > threshold``. This is the exact float64 summation of
    :func:`boolean_attractors` (no matmul, no pre-summed bias), so float ties
    resolve identically.
    """
    X = np.asarray(X)
    if X.dtype != np.uint8:
        X = X.astype(np.uint8)
    n_rows = X.shape[0]
    pos = {int(node): k for k, node in enumerate(cols)}
    fixed = {} if fixed is None else fixed
    nodes = list(nodes)
    out = np.empty((n_rows, len(nodes)), dtype=np.uint8)
    for o, j in enumerate(nodes):
        rule = rules[j]
        inflow: Any = 0.0  # a Python float until the first live column
        for i, w in chain(rule["activators"], rule["inhibitors"]):
            k = pos.get(i)
            if k is None:
                inflow = inflow + w * int(fixed[i])
            elif isinstance(inflow, np.ndarray):
                inflow += np.multiply(X[:, k], w, dtype=np.float64)
            else:
                inflow = inflow + np.multiply(X[:, k], w, dtype=np.float64)
        out[:, o] = inflow > rule["threshold"]
    return out


def _boolean_inputs(rules: list[dict[str, Any]], j: int) -> list[int]:
    rule = rules[j]
    return [int(i) for i, _w in chain(rule["activators"], rule["inhibitors"])]


def _boolean_reach(start: set[int], adj: list[list[int]]) -> set[int]:
    seen = set(start)
    stack = list(start)
    while stack:
        v = stack.pop()
        for w in adj[v]:
            if w not in seen:
                seen.add(w)
                stack.append(w)
    return seen


def _boolean_partition(rules: list[dict[str, Any]]) -> tuple[list[int], list[int], list[int]]:
    """Split nodes into upstream U, feedback core C and read-outs R.

    A node is on a cycle if its strongly connected component has more than
    one node or a self-loop. U: not downstream of any cycle. C: downstream
    and upstream of a cycle (cycle nodes included). R: downstream only.
    Each list is sorted.
    """
    n = len(rules)
    g = nx.DiGraph()
    g.add_nodes_from(range(n))
    preds: list[list[int]] = [[] for _ in range(n)]
    succs: list[list[int]] = [[] for _ in range(n)]
    for j in range(n):
        for i in _boolean_inputs(rules, j):
            g.add_edge(i, j)
            preds[j].append(i)
            succs[i].append(j)
    cyc: set[int] = set()
    for comp in nx.strongly_connected_components(g):
        if len(comp) > 1 or any(g.has_edge(v, v) for v in comp):
            cyc |= comp
    down = _boolean_reach(cyc, succs)
    up = _boolean_reach(cyc, preds)
    upstream = sorted(set(range(n)) - down)
    core = sorted(down & up)
    readout = sorted(down - up)
    return upstream, core, readout


def _boolean_states_matrix(k: int, idx: np.ndarray | None = None) -> np.ndarray:
    """States as a ``(len(idx), k)`` uint8 matrix, row ``r`` = bits of
    ``idx[r]`` (default: all ``2^k`` states in order). Built column by column
    to avoid a ``(2^k, k)`` int64 temporary."""
    if idx is None:
        idx = np.arange(1 << k, dtype=np.int64)
    X = np.empty((len(idx), k), dtype=np.uint8)
    for b in range(k):
        X[:, b] = (idx >> b) & 1
    return X


def _boolean_compact_index(X: np.ndarray) -> np.ndarray:
    """Rows of a ``(S, k)`` 0/1 matrix as compact indices (k <= 20 bits)."""
    packed = np.packbits(X, axis=1, bitorder="little")  # (S, ceil(k / 8))
    idx = np.zeros(X.shape[0], dtype=np.int64)
    for byte in range(packed.shape[1]):
        idx |= packed[:, byte].astype(np.int64) << (8 * byte)
    return idx


def _boolean_row_int(packed_row: bytes) -> int:
    """A row packed with ``np.packbits(..., bitorder="little")`` as a Python
    int with bit i = node i (no width limit)."""
    return int.from_bytes(packed_row, "little")


def _boolean_upstream_fixed(rules: list[dict[str, Any]], U: list[int]) -> dict[int, int]:
    """Constant pattern u* of the upstream part. U reads only U and is
    acyclic, so any start settles within |U| steps."""
    if not U:
        return {}
    x = np.zeros((1, len(U)), dtype=np.uint8)
    for _ in range(len(U) + 1):
        x = _boolean_step(rules, x, cols=U, nodes=U)
    again = _boolean_step(rules, x, cols=U, nodes=U)
    if not np.array_equal(x, again):  # pragma: no cover - structural invariant
        raise RuntimeError("upstream part did not settle to a fixed pattern")
    return {u: int(v) for u, v in zip(U, x[0])}


def _boolean_core_labels(
    rules: list[dict[str, Any]], C: list[int], ustar: Mapping[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    """Label every core state with its core attractor.

    Returns ``(att_of, reps)``: ``att_of[s]`` is the attractor position of
    compact core state ``s``, and ``reps[a]`` is the minimum compact state on
    attractor ``a``'s cycle (ascending). Vectorised: pointer doubling with an
    orbit minimum on the compact core map, no Python loop over states.
    """
    k = len(C)
    X = _boolean_states_matrix(k)
    nxt = _boolean_compact_index(_boolean_step(rules, X, cols=C, nodes=C, fixed=ustar))
    del X
    # After j rounds: m[s] = min of the first 2^j states of the orbit of s and
    # fp = f^(2^j). After k rounds fp[s] lies on the cycle (transient + period
    # <= 2^k), and m[fp[s]] covers 2^k >= period cycle states.
    m = np.arange(1 << k, dtype=np.int32)  # compact core indices fit in int32
    fp = nxt.astype(np.int32)
    for _ in range(max(k, 1)):
        m = np.minimum(m, m[fp])
        fp = fp[fp]
    label = m[fp]
    reps, att_of = np.unique(label, return_inverse=True)
    return att_of.reshape(-1), reps


def _boolean_reconstruct(
    rules: list[dict[str, Any]], n: int, U: list[int], C: list[int],
    ustar: Mapping[int, int], reps: np.ndarray,
) -> list[list[int]]:
    """Full attractor cycles (read-outs included) from core representatives.

    Every representative is stepped at once from (u*, core state, R = 0)
    until its full state repeats. Each cycle is returned in update order,
    rotated to start at its minimum state.
    """
    A = len(reps)
    X = np.zeros((A, n), dtype=np.uint8)
    for u in U:
        X[:, u] = ustar[u]
    for b, c in enumerate(C):
        X[:, c] = (reps >> b) & 1
    allnodes = list(range(n))
    seen: list[dict[bytes, int]] = [dict() for _ in range(A)]
    paths: list[list[bytes]] = [[] for _ in range(A)]
    cycles: list[list[int]] = [[] for _ in range(A)]
    alive = np.arange(A)
    while alive.size:
        packed = np.packbits(X, axis=1, bitorder="little")
        keep = np.ones(alive.size, dtype=bool)
        for r, (a, row) in enumerate(zip(alive, packed)):
            key = row.tobytes()
            hit = seen[a].get(key)
            if hit is None:
                seen[a][key] = len(paths[a])
                paths[a].append(key)
            else:
                cyc = [_boolean_row_int(p) for p in paths[a][hit:]]
                lo = cyc.index(min(cyc))
                cycles[a] = cyc[lo:] + cyc[:lo]
                keep[r] = False
        alive, X = alive[keep], X[keep]
        if alive.size:
            X = _boolean_step(rules, X, cols=allnodes, nodes=allnodes)
    return cycles


def _boolean_input_sequences(
    rules: list[dict[str, Any]], Ua: list[int], Iu: list[int], ustar: Mapping[int, int],
    max_distinct: int,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Distinct transient sequences of the core's upstream inputs.

    Simulates the upstream ancestors U_a alone from all ``2^|U_a|`` starts
    (U_a is acyclic and ancestor-closed, so it settles to u* within |U_a|
    steps) and groups the starts by the values ``Iu`` (the upstream nodes the
    core reads) take at t = 0 .. T-1, where from T on every start has
    ``Iu = u*``. Returns ``(pid, mult)``: ``pid[d, t]`` is the compact
    Iu-pattern of sequence ``d`` at time ``t`` (shape ``(D, T)``) and
    ``mult[d]`` how many upstream starts produce it (summing to
    ``2^|U_a|``). Returns None when ``D > max_distinct``.
    """
    m = len(Ua)
    one = (np.zeros((1, 0), dtype=np.int64), np.array([1 << m], dtype=np.int64))
    if not Iu:
        return one
    icol = [Ua.index(i) for i in Iu]
    tgt = int(sum(ustar[i] << b for b, i in enumerate(Iu)))
    width = len(Iu)
    uvec = np.array([ustar[u] for u in Ua], dtype=np.uint8)
    X = _boolean_states_matrix(m)
    h = _boolean_compact_index(X[:, icol])
    # group: running id of each start's input sequence so far (< 2^m). A time
    # step at which every start shows u* is constant and needs no regrouping.
    # The number of groups only grows, so exceeding max_distinct is final.
    group, n_groups = h, len(np.unique(h))
    T = 1 if n_groups > 1 or np.any(h != tgt) else 0  # 1 + last time inputs differ from u*
    settled = bool(np.all(X == uvec))
    for t in range(1, m + 2):
        if n_groups > max(1, max_distinct):
            return None
        if settled:  # every start is at u*: later steps are all constant
            break
        X = _boolean_step(rules, X, cols=Ua, nodes=Ua)
        h = _boolean_compact_index(X[:, icol])
        if np.any(h != tgt):
            T = t + 1
            _, group = np.unique(group * (1 << width) + h, return_inverse=True)
            group = group.reshape(-1).astype(np.int64)
            n_groups = int(group.max()) + 1
        settled = bool(np.all(X == uvec))
    del X
    if not settled:  # pragma: no cover - structural invariant
        raise RuntimeError("upstream ancestors did not settle to u*")
    if T == 0:
        return one
    _, first, mult = np.unique(group, return_index=True, return_counts=True)
    if len(first) > max_distinct:
        return None
    # replay one representative start per distinct sequence to record it
    Y = _boolean_states_matrix(m, first)
    pid = np.empty((len(first), T), dtype=np.int64)
    for t in range(T):
        pid[:, t] = _boolean_compact_index(Y[:, icol])
        Y = _boolean_step(rules, Y, cols=Ua, nodes=Ua)
    return pid, mult.astype(np.int64)


def _boolean_drive_exact(
    rules: list[dict[str, Any]], U: list[int], C: list[int], Iu: list[int],
    ustar: Mapping[int, int], att_of: np.ndarray, n_att: int,
    pid: np.ndarray, mult: np.ndarray,
) -> list[int]:
    """Exact basin counts over (upstream-ancestor start, core start) pairs.

    One compact core map ``F_v`` is built per observed upstream-input pattern
    ``v``; each distinct input sequence then drives all core states by index
    composition, and the final core state's label gives the attractor.

    ``F_v`` is assembled node by node: core nodes that read no upstream input
    are evaluated once for all patterns, and a node that does is evaluated
    once per distinct value of *its own* inputs from Iu (each evaluation is a
    plain :func:`_boolean_step` call, so the float summation is unchanged).
    """
    k = len(C)
    n_core = 1 << k
    D, T = pid.shape
    totals = np.zeros(n_att, dtype=np.int64)
    if T == 0:
        totals += np.bincount(att_of, minlength=n_att).astype(np.int64) * int(mult[0])
        return [int(t) for t in totals]
    patterns, pos = np.unique(pid, return_inverse=True)
    pos = pos.reshape(D, T)
    Iset = set(Iu)
    ibit = {i: b for b, i in enumerate(Iu)}
    others = {u: ustar[u] for u in U if u not in Iset}
    core_X = _boolean_states_matrix(k)
    per = max(1, _BOOLEAN_CHUNK_ROWS // n_core)
    plain = [j for j in C if not Iset.intersection(_boolean_inputs(rules, j))]
    driven = [j for j in C if Iset.intersection(_boolean_inputs(rules, j))]
    base = np.zeros(n_core, dtype=np.int32)
    if plain:
        out = _boolean_step(rules, core_X, cols=C, nodes=plain, fixed=others)
        for q, j in enumerate(plain):
            base |= out[:, q].astype(np.int32) << C.index(j)
    fmaps = np.empty((len(patterns), n_core), dtype=np.int32)  # compact core indices
    fmaps[:] = base
    for j in driven:
        Ij = sorted(Iset.intersection(_boolean_inputs(rules, j)))
        sub = np.zeros(len(patterns), dtype=np.int64)
        for q, i in enumerate(Ij):
            sub |= ((patterns >> ibit[i]) & 1) << q
        subs, inv = np.unique(sub, return_inverse=True)
        inv = inv.reshape(-1)
        # table[s, c]: next value of j from core state c with its inputs Ij = subs[s];
        # Ij are live columns here, evaluated in batches of subs
        table = np.empty((len(subs), n_core), dtype=np.uint8)
        cols_j = list(C) + Ij
        for s0 in range(0, len(subs), per):
            ss = subs[s0:s0 + per]
            Xc = np.empty((len(ss) * n_core, len(cols_j)), dtype=np.uint8)
            Xc[:, :k] = np.tile(core_X, (len(ss), 1))
            for q in range(len(Ij)):
                Xc[:, k + q] = np.repeat((ss >> q) & 1, n_core)
            out = _boolean_step(rules, Xc, cols=cols_j, nodes=[j], fixed=others)
            table[s0:s0 + len(ss)] = out[:, 0].reshape(len(ss), n_core)
        shift = C.index(j)
        for p0 in range(0, len(patterns), per):
            fmaps[p0:p0 + per] |= table[inv[p0:p0 + per]].astype(np.int32) << shift
    del core_X
    start = np.arange(n_core, dtype=np.int64)
    for d0 in range(0, D, per):
        dc = min(per, D - d0)
        idx = np.broadcast_to(start, (dc, n_core))
        for t in range(T):
            idx = fmaps[pos[d0:d0 + dc, t][:, None], idx]
        lab = att_of[idx] + n_att * np.arange(dc, dtype=np.int64)[:, None]
        counts = np.bincount(lab.ravel(), minlength=dc * n_att).reshape(dc, n_att)
        totals += (counts.astype(np.int64) * mult[d0:d0 + dc, None]).sum(axis=0)
    return [int(t) for t in totals]


def _boolean_sample_basins(
    rules: list[dict[str, Any]], n: int, U: list[int], C: list[int],
    att_of: np.ndarray, n_att: int, basin_samples: int, seed: int,
) -> list[float]:
    """Basin fractions from random full starts. Each start is stepped until
    the upstream part has settled (|U| + 1 steps); its core state then lies
    in a labelled basin of the autonomous core map."""
    S = max(1, int(basin_samples))
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(S, n), dtype=np.uint8)
    cols = list(U) + list(C)
    Y = X[:, cols]
    del X
    for _ in range(len(U) + 1):
        Y = _boolean_step(rules, Y, cols=cols, nodes=cols)
    hits = np.bincount(att_of[_boolean_compact_index(Y[:, len(U):])], minlength=n_att)
    return [int(h) / S for h in hits]


def _boolean_core_basins(
    rules: list[dict[str, Any]], n: int, U: list[int], C: list[int],
    ustar: Mapping[int, int], att_of: np.ndarray, n_att: int,
    basin_budget: int, basin_samples: int, seed: int,
) -> tuple[str, list[int] | None, list[float]]:
    """Basins of ``n_att >= 2`` core attractors (spec §3.3 step 5).

    Read-outs and upstream nodes that are not ancestors of the core never
    affect which attractor is reached, so with ``f`` such nodes every basin is
    multiplied by exactly ``2^f``. The upstream ancestors U_a perturb the
    core during their transient: their distinct input sequences drive every
    core state when ``D * 2^|C| <= basin_budget``; otherwise fractions are
    estimated from ``basin_samples`` random full starts.

    Returns ``(basin_method, sizes or None, fractions)``.
    """
    Cset, Uset = set(C), set(U)
    Iu = sorted({i for j in C for i in _boolean_inputs(rules, j) if i in Uset})
    preds = [_boolean_inputs(rules, j) for j in range(n)]
    Ua = sorted(_boolean_reach(set(Iu), preds)) if Iu else []
    assert not (set(Ua) & Cset)
    k = len(C)
    if len(Ua) <= _BOOLEAN_MAX_UPSTREAM_ANCESTORS:
        seqs = _boolean_input_sequences(rules, Ua, Iu, ustar, max(0, basin_budget) >> k)
        if seqs is not None and seqs[0].shape[0] * (1 << k) <= basin_budget:
            pid, mult = seqs
            counts = _boolean_drive_exact(rules, U, C, Iu, ustar, att_of, n_att, pid, mult)
            free = n - k - len(Ua)
            sizes = [c << free for c in counts]
            total = 1 << n
            return "exact", sizes, [s / total for s in sizes]
    return "sampled", None, _boolean_sample_basins(
        rules, n, U, C, att_of, n_att, basin_samples, seed)


def boolean_attractors_core(
    rules: list[dict[str, Any]],
    *,
    max_core: int = BOOLEAN_MAX_CORE,
    basin_budget: int = BOOLEAN_BASIN_BUDGET,
    basin_samples: int = 10_000,
    seed: int = 0,
) -> dict[str, Any]:
    """Exact Boolean attractors via the feedback core (spec 2026-11-21 §3.3).

    Only the feedback core C (nodes downstream and upstream of a cycle)
    determines the attractors: the upstream part U settles to a constant
    pattern u*, and read-outs R follow the core. The ``2^|C|`` core states
    are searched exhaustively, so the whole-network size does not matter;
    the limit is ``|C| <= max_core``. Same update rules and float summation
    as :func:`boolean_attractors`.

    Returns
    -------
    dict
        ``{"method": "core", "n_nodes", "core_size", "upstream_size",
        "readout_size", "basin_method": "exact" | "sampled", "attractors":
        [{"type": "fixed" | "cyclic", "states": [int, ...], "period": int,
        "basin_size": int | None, "basin_fraction": float}], "all_off_only":
        bool}``. States are Python ints with bit ``i`` for node ``i``; cycles
        start at their minimum state; attractors are ordered by
        ``basin_fraction`` descending, then minimum state. ``basin_size`` is
        set (summing to ``2^n``) only when ``basin_method == "exact"``.

        Sentinels: core above ``max_core`` gives ``{"method": "core",
        "attractors": [], "error": "core_too_large", "n_nodes", "core_size",
        "max_core"}``; ``n > BOOLEAN_MAX_NODES_TOTAL`` gives ``"error":
        "too_large"`` (with ``n_nodes`` and ``max_nodes``); ``n == 0`` gives
        an empty result with no attractors.
    """
    n = len(rules)
    if n > BOOLEAN_MAX_NODES_TOTAL:
        return {"method": "core", "attractors": [], "error": "too_large",
                "n_nodes": n, "max_nodes": BOOLEAN_MAX_NODES_TOTAL}
    if n == 0:
        return {"method": "core", "n_nodes": 0, "core_size": 0, "upstream_size": 0,
                "readout_size": 0, "basin_method": "exact", "attractors": [],
                "all_off_only": False}
    U, C, R = _boolean_partition(rules)
    k = len(C)
    if k > max_core:
        return {"method": "core", "attractors": [], "error": "core_too_large",
                "n_nodes": n, "core_size": k, "max_core": max_core}

    ustar = _boolean_upstream_fixed(rules, U)
    att_of, reps = _boolean_core_labels(rules, C, ustar)
    cycles = _boolean_reconstruct(rules, n, U, C, ustar, reps)

    sizes: list[int] | None
    if len(cycles) == 1:
        # One attractor: its basin is the whole state space by definition.
        basin_method, sizes, fractions = "exact", [1 << n], [1.0]
    else:
        basin_method, sizes, fractions = _boolean_core_basins(
            rules, n, U, C, ustar, att_of, len(cycles),
            basin_budget, basin_samples, seed)

    attractors = [
        {
            "type": "fixed" if len(cyc) == 1 else "cyclic",
            "states": cyc,
            "period": len(cyc),
            "basin_size": None if sizes is None else sizes[a],
            "basin_fraction": float(fractions[a]),
        }
        for a, cyc in enumerate(cycles)
    ]
    attractors.sort(key=lambda a: (-a["basin_fraction"], a["states"][0]))
    all_off_only = (len(attractors) == 1 and attractors[0]["type"] == "fixed"
                    and attractors[0]["states"] == [0])
    return {
        "method": "core",
        "n_nodes": n,
        "core_size": k,
        "upstream_size": len(U),
        "readout_size": len(R),
        "basin_method": basin_method,
        "attractors": attractors,
        "all_off_only": all_off_only,
    }


_BOOLEAN_SAMPLE_CAP = 100_000       # clamp for n_samples and max_steps
_BOOLEAN_SAMPLE_HISTORY = 10 ** 7   # n_samples * (max_steps + 1) packed rows


def boolean_attractors_sampled(
    rules: list[dict[str, Any]],
    n_samples: int = 2000,
    *,
    max_steps: int = 1000,
    seed: int = 0,
) -> dict[str, Any]:
    """Sampled whole-network Boolean attractor search (spec 2026-11-21 §3.4).

    For networks whose feedback core is above the exact limit. Uniform random
    start states are stepped together with :func:`_boolean_step`; a
    trajectory converges at its first repeated state, and one that has not
    repeated after ``max_steps`` steps is counted as unconverged. History is
    kept as packed rows, so ``n_samples * (max_steps + 1)`` is held to
    ``10**7`` by lowering ``max_steps`` (the effective value is echoed).

    Returns
    -------
    dict
        ``{"method": "sampled", "attractors": [{"type": "fixed" | "cyclic",
        "states": [int, ...], "period": int, "hits": int, "basin_fraction":
        float}], "n_samples", "n_unconverged", "seed", "max_steps",
        "n_nodes"}``. States are Python ints with bit ``i`` for node ``i``;
        cycles start at their minimum state; attractors are ordered by
        ``hits`` descending, then minimum state. ``basin_fraction`` is
        ``hits / n_samples``. There is no ``basin_size``: samples do not give
        exact basins. ``n_samples`` and ``max_steps`` are clamped to
        ``[1, 100000]``. ``n > BOOLEAN_MAX_NODES_TOTAL`` gives ``{"method":
        "sampled", "attractors": [], "error": "too_large", "n_nodes",
        "max_nodes"}``.
    """
    n = len(rules)
    if n > BOOLEAN_MAX_NODES_TOTAL:
        return {"method": "sampled", "attractors": [], "error": "too_large",
                "n_nodes": n, "max_nodes": BOOLEAN_MAX_NODES_TOTAL}
    n_samples = min(max(int(n_samples), 1), _BOOLEAN_SAMPLE_CAP)
    max_steps = min(max(int(max_steps), 1), _BOOLEAN_SAMPLE_CAP)
    max_steps = min(max_steps, _BOOLEAN_SAMPLE_HISTORY // n_samples - 1)

    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(n_samples, n), dtype=np.uint8)
    cols = list(range(n))
    seen: list[dict[bytes, int]] = [{} for _ in range(n_samples)]
    alive = list(range(n_samples))
    hits: dict[tuple[int, ...], int] = {}
    for t in range(max_steps + 1):
        packed = np.packbits(X, axis=1, bitorder="little")
        keep: list[int] = []
        for r, (sample, row) in enumerate(zip(alive, packed)):
            key = row.tobytes()
            first = seen[sample].get(key)
            if first is None:
                seen[sample][key] = t
                keep.append(r)
                continue
            cyc = [_boolean_row_int(k) for k in list(seen[sample])[first:]]
            m = cyc.index(min(cyc))
            cyc = tuple(cyc[m:] + cyc[:m])
            hits[cyc] = hits.get(cyc, 0) + 1
            seen[sample] = {}  # release this trajectory's history
        if not keep:
            alive = []
            break
        if len(keep) < len(alive):
            X = X[keep]
            alive = [alive[r] for r in keep]
        if t < max_steps:
            X = _boolean_step(rules, X, cols=cols, nodes=cols)
    n_unconverged = len(alive)

    attractors = [
        {"type": "fixed" if len(cyc) == 1 else "cyclic", "states": list(cyc),
         "period": len(cyc), "hits": h, "basin_fraction": h / n_samples}
        for cyc, h in hits.items()
    ]
    attractors.sort(key=lambda a: (-a["hits"], a["states"][0]))
    return {"method": "sampled", "attractors": attractors, "n_samples": n_samples,
            "n_unconverged": n_unconverged, "seed": seed, "max_steps": max_steps,
            "n_nodes": n}


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


# Batch count for token_diffusion's standard errors. 20 gives 19 degrees of
# freedom (t = 2.093 at 95%) while keeping batches large enough for the CLT.
_DIFFUSION_BATCHES = 20


def _assign_ranks(rows: list[dict], quantified: bool,
                  crit: float, n_batches: int) -> None:
    """Assign `rank` in place over rows already sorted by tokens_received desc.

    A row shares its group's rank until it separates from the group LEADER.
    Two things matter here, and they are independent:

    * Grouping is against the LEADER, never the immediate predecessor.
      Separation is not transitive, so chaining it merged groups that are
      cleanly apart end to end, collapsing a gently-decreasing list toward
      a single rank (#21).
    * Separation is a PAIRED test on the per-batch difference, not a
      comparison of the two display intervals. Both elements are fed by the
      same token draws, so their batch totals are correlated and the paired
      difference carries the correct variance where two independent margins
      do not: competing sinks are negatively correlated (the honest verdict
      is MORE ties than the intervals suggest), while elements on a shared
      upstream path are positively correlated (fewer ties). Comparing whether
      two 95% intervals overlap is a different and weaker question.

    Var(sum of differences) = B * Var(per-batch difference), the same
    batch-means structure the `margin` column uses. Zero variance falls out
    correctly: identical deterministic counts tie, unequal ones separate.
    """
    leader = None
    for idx, row in enumerate(rows):
        if leader is None:
            row["rank"] = 1
            leader = row
            continue
        if not quantified:
            row["rank"] = leader["rank"]
            continue
        d = row["_batches"] - leader["_batches"]
        se_diff = float(np.sqrt(n_batches * d.var(ddof=1)))
        if abs(float(d.sum())) <= crit * se_diff:
            row["rank"] = leader["rank"]
        else:
            row["rank"] = idx + 1
            leader = row


def token_diffusion(
    isa: IsaData, source: str, *,
    n_steps: int = 10, n_tokens: int = 1000, seed: int | None = None,
) -> dict:
    """Stochastic token diffusion from an intervention node — step 2 of the
    Donlan et al. 2026 participatory framework (doi:10.21203/rs.3.rs-10397797/v1).

    n_tokens positive tokens start at `source`. Each step, every token whose
    node has outgoing edges hops to ONE uniformly-random out-neighbour;
    traversing a "-" edge flips the token's polarity. Tokens reaching a sink
    stay there and stop contributing arrivals. Per node (excluding the
    source) we accumulate arrivals across all steps, the polarity split on
    arrival, and the 1-based step of first arrival — a reach-and-speed
    profile that ranks which parts of the system an intervention at `source`
    actually touches, how fast, and with what net sign.

    net_sign is "+"/"-" only when the polarity imbalance is distinguishable
    from zero at 95% (Student's t over the batch means); otherwise "~".
    This replaces a fixed 5% band, which mislabelled structurally balanced
    nodes in ~12% of seeds because 5% of n_tokens is comparable to the
    sampling error itself (issue #19).

    Counts are one Monte-Carlo sample, so each row carries `margin`, the
    95% half-width on tokens_received from a batch-means estimate (tokens
    are i.i.d., so Var(total) = B * Var(batch totals)), and `rank`, in
    which a row shares a group's rank until it separates from the group
    LEADER — the highest-counted member. `margin` describes each element's
    own total and is what the table displays; grouping does NOT compare the
    two margins, because both elements are fed by the same token draws and
    a paired test on their per-batch difference carries the right variance
    where two independent intervals do not (issue #21). Separation is also
    never chained from row to row: it is not transitive, so comparing each
    row only with its predecessor merged groups that are cleanly separated
    end to end, collapsing a gently-decreasing list toward a single rank.
    A deterministic count has margin 0.

    With only one batch (n_tokens == 1) there is no spread to estimate, so
    every net_sign is "~" and every rank is 1 rather than claiming certainty
    the sample cannot support; the empty shape reports n_batches 0.

    Nodes never reached are omitted. Rows sort by tokens_received
    descending, ties in isa.elements order. Parallel edges deduplicate
    last-wins (the _axis_sums convention); self-loops and dangling refs are
    skipped; only "-" flips a token.

    Vectorised: one rng draw per STEP over the live tokens, not per token,
    so 5000 tokens x 30 steps is 30 numpy ops. Identical (isa, source,
    n_steps, n_tokens, seed) reproduce exactly. Unknown source, empty model,
    non-positive n_steps/n_tokens, or a source with no outgoing edges return
    the empty shape; never raises. Pure apart from the seeded RNG.
    """
    empty = {"rows": [], "source": source, "n_tokens": n_tokens,
             "n_steps": n_steps, "n_reached": 0, "n_batches": 0}
    order = {el.id: i for i, el in enumerate(isa.elements)}
    if source not in order or n_tokens <= 0 or n_steps <= 0:
        return empty

    n = len(isa.elements)
    pairs: dict[tuple[str, str], str] = {}
    for c in isa.connections:
        if c.source == c.target or c.source not in order or c.target not in order:
            continue
        pairs[(c.source, c.target)] = c.polarity
    neighbours: list[list[tuple[int, bool]]] = [[] for _ in range(n)]
    for (src, tgt), polarity in pairs.items():
        neighbours[order[src]].append((order[tgt], polarity == "-"))

    indptr = np.zeros(n + 1, dtype=np.int64)
    for i, lst in enumerate(neighbours):
        indptr[i + 1] = indptr[i] + len(lst)
    flat = [x for lst in neighbours for x in lst]
    indices = np.array([t for t, _ in flat], dtype=np.int64) if flat \
        else np.zeros(0, dtype=np.int64)
    flips = np.array([f for _, f in flat], dtype=bool) if flat \
        else np.zeros(0, dtype=bool)
    outdeg = np.diff(indptr)
    if outdeg[order[source]] == 0:
        return empty

    # Batch means: tokens are i.i.d., so B independent batches give an
    # honest standard error with no distributional assumption and
    # O(B x elements) memory. The RNG draw order is unchanged.
    n_batches = min(_DIFFUSION_BATCHES, n_tokens)
    batch_of = (np.arange(n_tokens) * n_batches) // n_tokens

    rng = np.random.default_rng(seed)
    pos = np.full(n_tokens, order[source], dtype=np.int64)
    sign = np.ones(n_tokens, dtype=np.int8)
    arrivals = np.zeros((n_batches, n), dtype=np.int64)
    signed = np.zeros((n_batches, n), dtype=np.int64)
    first = np.full(n, -1, dtype=np.int64)

    for step in range(1, n_steps + 1):
        live = np.nonzero(outdeg[pos] > 0)[0]
        if live.size == 0:
            break
        here = pos[live]
        slot = indptr[here] + (rng.random(live.size) * outdeg[here]).astype(np.int64)
        pos[live] = indices[slot]
        sign[live] = sign[live] * np.where(flips[slot], -1, 1).astype(np.int8)
        landed, landed_sign = pos[live], sign[live]
        np.add.at(arrivals, (batch_of[live], landed), 1)
        np.add.at(signed, (batch_of[live], landed), landed_sign.astype(np.int64))
        arrived = np.unique(landed)
        first[arrived[first[arrived] < 0]] = step

    if n_batches > 1:
        from scipy import stats  # lazy: scipy is a hard dep but a heavy import

        crit = float(stats.t.ppf(0.975, n_batches - 1))
        se_total = np.sqrt(n_batches * arrivals.var(axis=0, ddof=1))
        se_net = np.sqrt(n_batches * signed.var(axis=0, ddof=1))
        quantified = True
    else:
        # A single batch gives no spread to estimate: report the counts but
        # never claim a sign or a distinct rank from them.
        crit = 0.0
        se_total = np.zeros(n)
        se_net = np.zeros(n)
        quantified = False
    total = arrivals.sum(axis=0)
    net = signed.sum(axis=0)

    rows: list[dict] = []
    src_index = order[source]
    for el in isa.elements:
        i = order[el.id]
        if i == src_index or total[i] == 0:
            continue
        if not quantified or abs(net[i]) <= crit * se_net[i]:
            net_sign = "~"
        else:
            net_sign = "+" if net[i] > 0 else "-"
        rows.append({"id": el.id, "label": el.label,
                     "tokens_received": int(total[i]),
                     "margin": int(round(crit * se_total[i])),
                     "net_sign": net_sign,
                     "first_arrival_step": int(first[i]),
                     # Transient: the element's own per-batch arrivals, used
                     # for the paired rank comparison and popped before
                     # return. Carried ON the row so the sort below cannot
                     # silently desync it from its element.
                     "_batches": arrivals[:, i]})
    rows.sort(key=lambda r: -r["tokens_received"])
    _assign_ranks(rows, quantified, crit, n_batches)
    for row in rows:
        row.pop("_batches", None)
    return {"rows": rows, "source": source, "n_tokens": n_tokens,
            "n_steps": n_steps, "n_reached": len(rows),
            "n_batches": n_batches}
