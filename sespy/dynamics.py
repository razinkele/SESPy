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
from .bayes import STRENGTH_LINK
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
# Attractors reported (and reconstructed) by boolean_attractors_core; the rest
# are counted in n_attractors. Plain reinforcing loops have huge counts
# (a 20-node positive ring alone has 52,488).
BOOLEAN_MAX_ATTRACTORS = 1000
_BOOLEAN_SAMPLE_CAP = 100_000       # clamp for sample counts, max_steps and max_attractors
_BOOLEAN_SAMPLE_HISTORY = 10 ** 7   # n_samples * (max_steps + 1) packed rows

_BOOLEAN_MAX_UPSTREAM_ANCESTORS = 16  # 2^|U_a| upstream starts, simulated exactly (benchmark: 18 misses the 5 s gate)
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
    rules: list[dict[str, Any]], C: list[int], ustar: Mapping[int, int],
    *, return_map: bool = False,
) -> tuple[np.ndarray, ...]:
    """Label every core state with its core attractor.

    Returns ``(att_of, reps)``: ``att_of[s]`` is the attractor position of
    compact core state ``s``, and ``reps[a]`` is the minimum compact state on
    attractor ``a``'s cycle (ascending). With ``return_map`` the compact core
    map ``nxt`` (int32) is appended. Vectorised: pointer doubling with an
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
    if return_map:
        return att_of.reshape(-1), reps, nxt.astype(np.int32)
    return att_of.reshape(-1), reps


def _boolean_core_periods(nxt: np.ndarray, reps: np.ndarray) -> np.ndarray:
    """Cycle length of each representative on the compact core map
    (vectorised over representatives)."""
    reps = reps.astype(np.int64)
    period = np.ones(len(reps), dtype=np.int64)
    cur = nxt[reps].astype(np.int64)
    active = np.flatnonzero(cur != reps)
    while active.size:
        cur[active] = nxt[cur[active]]
        period[active] += 1
        active = active[cur[active] != reps[active]]
    return period


def _boolean_readout_order(rules: list[dict[str, Any]], R: list[int]) -> list[int]:
    """Read-outs in topological order of the edges among them (R is acyclic
    and reads only C, U and R)."""
    Rset = set(R)
    g = nx.DiGraph()
    g.add_nodes_from(R)
    for j in R:
        for i in _boolean_inputs(rules, j):
            if i in Rset:
                g.add_edge(i, j)
    return list(nx.lexicographical_topological_sort(g))


def _boolean_lex_less(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise ``int(a) < int(b)`` for rows packed little-endian
    (``np.packbits(..., bitorder="little")``), without building ints."""
    diff = a != b
    if diff.shape[1] == 0:
        return np.zeros(len(a), dtype=bool)
    rev = diff[:, ::-1]
    top = diff.shape[1] - 1 - np.argmax(rev, axis=1)  # most significant differing byte
    rows = np.arange(len(a))
    return rev.any(axis=1) & (a[rows, top] < b[rows, top])


def _boolean_cycle_walk(
    rules: list[dict[str, Any]], n: int, U: list[int], C: list[int], R_order: list[int],
    ustar: Mapping[int, int], reps: np.ndarray, nxt: np.ndarray, periods: np.ndarray,
    *, record: bool,
) -> list:
    """Full attractor cycles of the given core representatives, solved on
    their periodic phases directly (no transient is simulated).

    On an attractor the core runs its cycle (phase 0 = the representative,
    phase φ+1 = ``nxt`` of phase φ), U sits at u*, and each read-out has the
    same period, with ``r(φ) = rule_r(state(φ - 1 mod p))``. Taking read-outs
    in topological order, every input of ``r`` is known at all phases when
    ``r`` is evaluated, so one kernel call per read-out (over attractors ×
    phases, inputs only) gives the exact cycle.

    ``record=False`` returns, per row, the packed minimum full state of the
    cycle (``(len(reps), ceil(n / 8))`` uint8). ``record=True`` returns, per
    row, the cycle as Python ints in update order, rotated to start at its
    minimum state.
    """
    A = len(reps)
    nbytes = (n + 7) // 8
    out_min = np.zeros((A, nbytes), dtype=np.uint8)
    out_cyc: list[list[int]] = [[] for _ in range(A)]
    inputs = {r: sorted(set(_boolean_inputs(rules, r))) for r in R_order}
    for p in np.unique(periods).tolist():
        rows_p = np.flatnonzero(periods == p)
        per = max(1, (_BOOLEAN_CHUNK_ROWS // 4) // p)  # attractors per chunk
        for a0 in range(0, len(rows_p), per):
            rows = rows_p[a0:a0 + per]
            m = len(rows)
            # V[a * p + φ] = full state of attractor a at phase φ
            V = np.zeros((m * p, n), dtype=np.uint8)
            for u in U:
                V[:, u] = ustar[u]
            cphase = np.empty((m, p), dtype=np.int64)
            cur = reps[rows].astype(np.int64)
            for phi in range(p):
                cphase[:, phi] = cur
                cur = nxt[cur].astype(np.int64)
            flat = cphase.reshape(-1)
            for b, c in enumerate(C):
                V[:, c] = (flat >> b) & 1
            # row of the previous phase (φ - 1 mod p) of the same attractor
            base = np.repeat(np.arange(m, dtype=np.int64) * p, p)
            prev = base + (np.tile(np.arange(p, dtype=np.int64), m) - 1) % p
            for r in R_order:
                ins = inputs[r]
                Xr = V[np.ix_(prev, ins)] if ins else np.zeros((m * p, 0), dtype=np.uint8)
                V[:, r] = _boolean_step(rules, Xr, cols=ins, nodes=[r])[:, 0]
            packed = np.packbits(V, axis=1, bitorder="little").reshape(m, p, nbytes)
            del V
            if record:
                for i, r_glob in enumerate(rows.tolist()):
                    cyc = [_boolean_row_int(packed[i, phi].tobytes()) for phi in range(p)]
                    lo = cyc.index(min(cyc))
                    out_cyc[r_glob] = cyc[lo:] + cyc[:lo]
            else:
                best = packed[:, 0].copy()
                for phi in range(1, p):
                    lt = _boolean_lex_less(packed[:, phi], best)
                    best[lt] = packed[lt, phi]
                out_min[rows] = best
    return out_cyc if record else out_min


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
    max_attractors: int = BOOLEAN_MAX_ATTRACTORS,
) -> dict[str, Any]:
    """Exact Boolean attractors via the feedback core (spec 2026-11-21 §3.3).

    Only the feedback core C (nodes downstream and upstream of a cycle)
    determines the attractors: the upstream part U settles to a constant
    pattern u*, and read-outs R follow the core. The ``2^|C|`` core states
    are searched exhaustively, so the whole-network size does not matter;
    the limit is ``|C| <= max_core``. Same update rules and float summation
    as :func:`boolean_attractors`.

    Parameters
    ----------
    max_core
        Core-size limit, clamped to ``[0, BOOLEAN_MAX_CORE]``.
    basin_budget
        Core-state evaluations allowed for the exact basin pass.
    basin_samples
        Random starts for the sampled basin estimate, clamped to
        ``[1, 100000]``.
    seed
        Seed for the sampled basin estimate. Must be a non-negative int
        (``numpy.random.default_rng`` rejects negative seeds).
    max_attractors
        How many attractors to report, clamped to ``[1, 100000]`` (default
        ``BOOLEAN_MAX_ATTRACTORS``). The top ones in the result order are
        kept, and only those are reconstructed; ``n_attractors`` counts all.

    Returns
    -------
    dict
        ``{"method": "core", "n_nodes", "core_size", "upstream_size",
        "readout_size", "basin_method": "exact" | "sampled", "attractors":
        [{"type": "fixed" | "cyclic", "states": [int, ...], "period": int,
        "basin_size": int | None, "basin_fraction": float}], "all_off_only":
        bool, "n_attractors": int, "truncated": bool}``. States are Python
        ints with bit ``i`` for node ``i``; cycles start at their minimum
        state; attractors are ordered by ``basin_fraction`` descending, then
        minimum state. ``basin_size`` is exact (the sizes of *all* attractors
        sum to ``2^n``) only when ``basin_method == "exact"``; when
        ``"sampled"`` the result also has ``basin_samples`` (effective, after
        the clamp) and ``basin_seed``. ``truncated`` is true when
        ``n_attractors > len(attractors)``.

        Sentinels: core above ``max_core`` gives ``{"method": "core",
        "attractors": [], "error": "core_too_large", "n_nodes", "core_size",
        "max_core"}`` (``max_core`` after the clamp); ``n >
        BOOLEAN_MAX_NODES_TOTAL`` gives ``"error": "too_large"`` (with
        ``n_nodes`` and ``max_nodes``); ``n == 0`` gives an empty result with
        no attractors (``n_attractors`` 0).
    """
    max_core = min(max(int(max_core), 0), BOOLEAN_MAX_CORE)
    basin_samples = min(max(int(basin_samples), 1), _BOOLEAN_SAMPLE_CAP)
    max_attractors = min(max(int(max_attractors), 1), _BOOLEAN_SAMPLE_CAP)
    n = len(rules)
    if n > BOOLEAN_MAX_NODES_TOTAL:
        return {"method": "core", "attractors": [], "error": "too_large",
                "n_nodes": n, "max_nodes": BOOLEAN_MAX_NODES_TOTAL}
    if n == 0:
        return {"method": "core", "n_nodes": 0, "core_size": 0, "upstream_size": 0,
                "readout_size": 0, "basin_method": "exact", "attractors": [],
                "all_off_only": False, "n_attractors": 0, "truncated": False}
    U, C, R = _boolean_partition(rules)
    k = len(C)
    if k > max_core:
        return {"method": "core", "attractors": [], "error": "core_too_large",
                "n_nodes": n, "core_size": k, "max_core": max_core}

    ustar = _boolean_upstream_fixed(rules, U)
    att_of, reps, nxt = _boolean_core_labels(rules, C, ustar, return_map=True)
    n_att = len(reps)

    sizes: list[int] | None
    if n_att == 1:
        # One attractor: its basin is the whole state space by definition.
        basin_method, sizes, fractions = "exact", [1 << n], [1.0]
    else:
        basin_method, sizes, fractions = _boolean_core_basins(
            rules, n, U, C, ustar, att_of, n_att, basin_budget, basin_samples, seed)
    del att_of

    # Choose the attractors to report before reconstructing any of them:
    # order is (basin_fraction desc, minimum full state). Everything above the
    # cut-off fraction is kept; the tie group at the cut-off is ranked by its
    # minimum full state, which needs only a min-only walk.
    periods = _boolean_core_periods(nxt, reps)
    R_order = _boolean_readout_order(rules, R)
    frac = np.asarray(fractions, dtype=np.float64)
    if n_att <= max_attractors:
        kept = np.arange(n_att)
    else:
        cutoff = np.sort(frac)[::-1][max_attractors - 1]
        above = np.flatnonzero(frac > cutoff)
        tie = np.flatnonzero(frac == cutoff)
        mins = _boolean_cycle_walk(rules, n, U, C, R_order, ustar, reps[tie], nxt, periods[tie],
                                   record=False)
        order = np.lexsort(tuple(mins[:, b] for b in range(mins.shape[1])))
        kept = np.concatenate([above, tie[order[:max_attractors - len(above)]]])
    cycles = _boolean_cycle_walk(rules, n, U, C, R_order, ustar, reps[kept], nxt, periods[kept],
                                 record=True)

    attractors = [
        {
            "type": "fixed" if len(cyc) == 1 else "cyclic",
            "states": cyc,
            "period": len(cyc),
            "basin_size": None if sizes is None else sizes[a],
            "basin_fraction": float(fractions[a]),
        }
        for a, cyc in zip(kept.tolist(), cycles)
    ]
    attractors.sort(key=lambda a: (-a["basin_fraction"], a["states"][0]))
    all_off_only = (n_att == 1 and attractors[0]["type"] == "fixed"
                    and attractors[0]["states"] == [0])
    res: dict[str, Any] = {
        "method": "core",
        "n_nodes": n,
        "core_size": k,
        "upstream_size": len(U),
        "readout_size": len(R),
        "basin_method": basin_method,
        "attractors": attractors,
        "all_off_only": all_off_only,
        "n_attractors": n_att,
        "truncated": n_att > len(attractors),
    }
    if basin_method == "sampled":
        res["basin_samples"] = basin_samples
        res["basin_seed"] = seed
    return res


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
    ``seed`` must be a non-negative int (``numpy.random.default_rng`` rejects
    negative seeds). An empty network (``n == 0``) gives no attractors.

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
    if n == 0:
        return {"method": "sampled", "attractors": [], "n_samples": n_samples,
                "n_unconverged": 0, "seed": seed, "max_steps": max_steps, "n_nodes": 0}

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


_PROPAGATION_MASS_KEYS = ("decayed", "stopped", "absorbed", "in_transit")
_SIGN_LABEL = {1: "+", -1: "-", 0: "~"}


def _propagation_graph(isa: IsaData, transition: str):
    """CSR graph for the signed walk: out-edges of each node ordered by
    target position, with per-node normalised cumulative weights."""
    order = {el.id: i for i, el in enumerate(isa.elements)}
    n = len(isa.elements)
    pairs: dict[tuple[str, str], Any] = {}
    for c in isa.connections:
        if c.source == c.target or c.source not in order or c.target not in order:
            continue
        pairs[(c.source, c.target)] = c  # parallel edges: last wins
    nbrs: list[list[tuple[int, bool, float]]] = [[] for _ in range(n)]
    n_default = 0
    for (src, tgt), c in pairs.items():
        if transition == "weighted":
            w = STRENGTH_LINK.get(c.strength)
            if w is None:
                w = STRENGTH_LINK["medium"]
                n_default += 1
        else:
            w = 1.0
        nbrs[order[src]].append((order[tgt], c.polarity == "-", w))
    for lst in nbrs:
        lst.sort(key=lambda x: x[0])
    indptr = np.zeros(n + 1, dtype=np.int64)
    for i, lst in enumerate(nbrs):
        indptr[i + 1] = indptr[i] + len(lst)
    flat = [x for lst in nbrs for x in lst]
    tgt = np.array([x[0] for x in flat], dtype=np.int64)
    flip = np.array([x[1] for x in flat], dtype=bool)
    w = np.array([x[2] for x in flat], dtype=float)
    cum = np.zeros(len(flat))
    for i in range(n):
        lo, hi = indptr[i], indptr[i + 1]
        if hi > lo:
            cs = np.cumsum(w[lo:hi])
            cum[lo:hi] = cs / cs[-1]
    return order, n, indptr, tgt, flip, cum, n_default


def _signed_walk(
    isa: IsaData, source: str, *, n_steps: int, n_tokens: int, decay: float,
    stop_prob: float, transition: str, seed: int | None,
) -> dict | None:
    """The walk behind `signed_propagation` (parameters already clamped).

    Returns None for the empty case (unknown source, no out-links), else a
    dict of per-element arrays: `reach`, `signed` (signed mass per token),
    `net_sign` (-1/0/+1), `pos_mass`, `neg_mass` (per token), `first`
    (per-token first-visit step, int16, 0 = never; shape n_tokens x n),
    `mass` (shares of n_tokens), plus `order`, `n`, `n_default`,
    `n_batches`. Draws are token-indexed: every step consumes exactly
    n_tokens uniforms for the choice and n_tokens for the stop test.
    """
    order, n, indptr, tgt, flip, cum, n_default = _propagation_graph(isa, transition)
    if source not in order:
        return None
    src = order[source]
    outdeg = np.diff(indptr)
    if outdeg[src] == 0:
        return None

    n_batches = min(_DIFFUSION_BATCHES, n_tokens)
    batch_of = (np.arange(n_tokens) * n_batches) // n_tokens
    rng = np.random.default_rng(seed)
    pos = np.full(n_tokens, src, dtype=np.int64)
    sign = np.ones(n_tokens, dtype=np.int8)
    mass = np.ones(n_tokens)
    live = np.ones(n_tokens, dtype=bool)
    first = np.zeros((n_tokens, n), dtype=np.int16)
    pos_mass = np.zeros(n)
    neg_mass = np.zeros(n)
    signed_b = np.zeros((n_batches, n))
    acc = dict.fromkeys(_PROPAGATION_MASS_KEYS, 0.0)

    for step in range(1, n_steps + 1):
        u_choice = rng.random(n_tokens)
        u_stop = rng.random(n_tokens)
        idx = np.nonzero(live)[0]
        if idx.size == 0:
            continue  # draws are consumed regardless (token-indexed)
        here = pos[idx]
        k = np.empty(idx.size, dtype=np.int64)
        for node in np.unique(here):
            m = here == node
            lo, hi = indptr[node], indptr[node + 1]
            kk = np.searchsorted(cum[lo:hi], u_choice[idx[m]], side="right")
            k[m] = np.minimum(kk, hi - lo - 1)
        slot = indptr[here] + k
        pos[idx] = tgt[slot]
        sign[idx] = sign[idx] * np.where(flip[slot], -1, 1).astype(np.int8)
        acc["decayed"] += float((mass[idx] * (1.0 - decay)).sum())
        mass[idx] = mass[idx] * decay
        landed = pos[idx]
        unseen = first[idx, landed] == 0
        first[idx[unseen], landed[unseen]] = step
        m_here = mass[idx]
        sg = sign[idx]
        np.add.at(pos_mass, landed[sg > 0], m_here[sg > 0])
        np.add.at(neg_mass, landed[sg < 0], m_here[sg < 0])
        np.add.at(signed_b, (batch_of[idx], landed), m_here * sg)
        stop = u_stop[idx] < stop_prob
        acc["stopped"] += float(m_here[stop].sum())
        live[idx[stop]] = False
        rest = idx[~stop]
        sink = outdeg[pos[rest]] == 0
        acc["absorbed"] += float(mass[rest[sink]].sum())
        live[rest[sink]] = False
    acc["in_transit"] = float(mass[live].sum())

    reach = (first > 0).sum(axis=0) / n_tokens
    reach[src] = 0.0
    if n_batches > 1:
        from scipy import stats  # lazy: scipy is a hard dep but a heavy import

        crit = float(stats.t.ppf(0.975, n_batches - 1))
        se = np.sqrt(n_batches * signed_b.var(axis=0, ddof=1))
        net = signed_b.sum(axis=0)
        net_sign = np.where(np.abs(net) <= crit * se, 0, np.sign(net)).astype(np.int8)
    else:
        net_sign = np.zeros(n, dtype=np.int8)
    return {"order": order, "n": n, "n_default": n_default, "n_batches": n_batches,
            "reach": reach, "first": first, "net_sign": net_sign,
            "pos_mass": pos_mass / n_tokens, "neg_mass": neg_mass / n_tokens,
            "signed": (pos_mass - neg_mass) / n_tokens,
            "mass": {key: v / n_tokens for key, v in acc.items()}}


def signed_propagation(
    isa: IsaData, source: str, *,
    n_steps: int = 8, n_tokens: int = 1000, decay: float = 0.8,
    stop_prob: float = 0.15, transition: str = "weighted",
    seed: int | None = 0,
) -> dict:
    """Weighted signed propagation from an intervention node (development
    note section 3.2); the weighted successor of `token_diffusion`, which
    stays unchanged.

    n_tokens tokens start at `source` with sign +1 and mass 1. Each step,
    every live token, in this order: moves along one out-edge (chosen in
    proportion to its weight), multiplies its sign by the edge sign, decays
    (mass *= decay; the loss goes to `decayed`), deposits its mass at the
    node it landed on (positive or negative mass by sign; every arrival
    deposits, so revisits count, discounted by decay), then stops with
    probability stop_prob (mass to `stopped`) or, if it did not stop and the
    node has no out-links, is absorbed (mass to `absorbed`). Tokens still
    live after the last step add their mass to `in_transit`. `mass` holds
    the four buckets as shares of n_tokens and sums to 1 for non-empty
    results (all 0.0 in the empty shape: no token moved).

    transition="weighted" uses bayes.STRENGTH_LINK[strength]; a missing or
    unknown strength counts as medium and is tallied in n_default_strength
    (kept connections, after dedup). transition="equal" picks uniformly.
    Any other value raises ValueError, the only way this function raises.

    Rows (one per non-source element with reach_probability > 0) carry
    reach_probability, first_arrival_min / _q50 (median first-visit step
    over visiting tokens), positive_mass / negative_mass (sum over tokens /
    n_tokens), signed_mass_mean, positive_share / negative_share (None when
    both masses are 0, e.g. decay=0) and net_sign. net_sign is "+"/"-" only
    when the signed mass is distinguishable from 0 at 95% (Student's t over
    min(20, n_tokens) batch means, as in `token_diffusion`), else "~"; with
    one batch it is always "~". Rows sort by reach_probability descending,
    ties in isa.elements order.

    Graph conventions as `token_diffusion`: parallel edges deduplicate
    last-wins, self-loops and dangling refs are skipped, only "-" flips a
    sign. Out-edges are ordered by target position in isa.elements.

    Draws are token-indexed (n_tokens uniforms for the choice and n_tokens
    for the stop test every step, live or not), so a token that never
    visits a node whose out-edge set or weights changed keeps its route in
    a perturbed map. n_steps is clamped to [1, 100], n_tokens to
    [1, 100000], decay and stop_prob to [0, 1]; the clamped values are
    echoed. Unknown source, empty model or a source without out-links
    return the empty shape. Identical inputs reproduce bit-for-bit. Pure
    apart from the seeded RNG.
    """
    if transition not in ("weighted", "equal"):
        raise ValueError(
            f"transition must be 'weighted' or 'equal', got {transition!r}")
    n_steps = max(1, min(100, int(n_steps)))
    n_tokens = max(1, min(100000, int(n_tokens)))
    decay = max(0.0, min(1.0, float(decay)))
    stop_prob = max(0.0, min(1.0, float(stop_prob)))
    result: dict = {
        "rows": [], "source": source, "n_steps": n_steps, "n_tokens": n_tokens,
        "decay": decay, "stop_prob": stop_prob, "transition": transition,
        "seed": seed, "n_reached": 0, "n_default_strength": 0, "n_batches": 0,
        "mass": dict.fromkeys(_PROPAGATION_MASS_KEYS, 0.0)}
    walk = _signed_walk(
        isa, source, n_steps=n_steps, n_tokens=n_tokens, decay=decay,
        stop_prob=stop_prob, transition=transition, seed=seed)
    if walk is None:
        return result

    rows: list[dict] = []
    for el in isa.elements:
        i = walk["order"][el.id]
        if walk["reach"][i] <= 0:
            continue
        steps = walk["first"][:, i]
        steps = steps[steps > 0]
        pos_m, neg_m = float(walk["pos_mass"][i]), float(walk["neg_mass"][i])
        total = pos_m + neg_m
        rows.append({
            "id": el.id, "label": el.label,
            "reach_probability": float(walk["reach"][i]),
            "first_arrival_min": int(steps.min()),
            "first_arrival_q50": int(np.quantile(steps, 0.5, method="lower")),
            "positive_mass": pos_m, "negative_mass": neg_m,
            "signed_mass_mean": pos_m - neg_m,
            "positive_share": pos_m / total if total > 0 else None,
            "negative_share": neg_m / total if total > 0 else None,
            "net_sign": _SIGN_LABEL[int(walk["net_sign"][i])]})
    rows.sort(key=lambda r: -r["reach_probability"])
    result.update(rows=rows, n_reached=len(rows),
                  n_default_strength=walk["n_default"],
                  n_batches=walk["n_batches"], mass=walk["mass"])
    return result


def propagation_sensitivity(
    isa: IsaData, source: str, *,
    n_runs: int = 200, base: float = 0.5, flip_mode: str = "confidence",
    draw_strength: bool = False, seed: int = 0,
    n_steps: int = 8, n_tokens: int = 1000, decay: float = 0.8,
    stop_prob: float = 0.15, transition: str = "weighted",
) -> dict:
    """Robustness of `signed_propagation` to doubt about the map.

    The baseline is `signed_propagation(isa, source, ..., seed=seed)` on the
    map as given, at the same token count as the variants; the rows follow
    its rows, in their order, and carry its `id`, `label`,
    `reach_probability` and `net_sign`. Each of n_runs variants perturbs the
    map with `network._perturbed_connections(isa, base, rng, flip_mode)`
    (drop with base*(5-confidence)/4, flip by confidence or, with
    flip_mode="posterior", by the rater posterior), where run k uses
    rng = default_rng(SeedSequence(seed).spawn(n_runs)[k]). With
    draw_strength=True each rated kept edge takes the strength of one
    uniformly drawn rating, as in `path_sensitivity`. The walk then runs
    with the baseline's own seed.

    Why a shared walk seed: draws are token-indexed, so a variant whose map
    is unchanged reproduces the baseline exactly (a confidence-5 map reads
    100% reached, 100% sign held). It is not claimed to cut token noise on
    perturbed maps; there the noise protection comes from the sign rule: a
    variant counts as "held" only when its own batch-means net_sign equals
    the baseline's.

    Added per row:
      - "reached_share": share of runs with reach > 0;
      - "sign_holds_share": share of runs whose own net_sign equals the
        baseline's; computed only when the baseline net_sign is "+" or "-",
        else None (balanced). A variant that is "~", unreached or of the
        opposite sign counts as NOT held, a conservative reading;
      - "reach_q05/q50/q95" and "signed_mass_q05/q50/q95": quantiles over
        all runs, unreached runs counting as 0.
    A run where the source lost every out-link counts as zero reach and zero
    signed mass for every element; it is never skipped. Elements reached
    only in variants are not listed (as in `path_sensitivity`).

    n_runs is clamped to [1, 2000] and base to [0, 1]; both are echoed
    clamped. flip_mode must be "confidence" or "posterior" (ValueError).
    "n_default_confidence" counts connections whose confidence int() fails
    (None or non-numeric text); out-of-range values are clamped and not
    counted. An empty baseline returns the full shape with rows []. Same
    seed, same output. Pure apart from the seeded RNGs.
    """
    from dataclasses import replace

    from .network import _perturbed_connections

    if flip_mode not in ("confidence", "posterior"):
        raise ValueError(
            f"flip_mode must be 'confidence' or 'posterior', got {flip_mode!r}")
    n_runs = max(1, min(2000, int(n_runs)))
    base = max(0.0, min(1.0, float(base)))
    seed = int(seed)

    n_default_conf = 0
    for c in isa.connections:
        try:
            int(c.confidence)
        except (TypeError, ValueError):
            n_default_conf += 1

    baseline = signed_propagation(
        isa, source, n_steps=n_steps, n_tokens=n_tokens, decay=decay,
        stop_prob=stop_prob, transition=transition, seed=seed)
    out = {
        "rows": [], "source": source, "n_runs": n_runs, "base": base,
        "flip_mode": flip_mode, "draw_strength": bool(draw_strength),
        "seed": seed, "n_steps": baseline["n_steps"],
        "n_tokens": baseline["n_tokens"], "decay": baseline["decay"],
        "stop_prob": baseline["stop_prob"], "transition": transition,
        "n_default_confidence": n_default_conf,
        "n_default_strength": baseline["n_default_strength"]}
    brows = baseline["rows"]
    if not brows:
        return out

    order = {el.id: i for i, el in enumerate(isa.elements)}
    idx = np.array([order[r["id"]] for r in brows])
    want = np.array([{"+": 1, "-": -1}.get(r["net_sign"], 0) for r in brows])
    nrow = len(brows)
    reach = np.zeros((n_runs, nrow))
    signed = np.zeros((n_runs, nrow))
    held = np.zeros((n_runs, nrow), dtype=bool)
    walk_kw = dict(n_steps=out["n_steps"], n_tokens=out["n_tokens"],
                   decay=out["decay"], stop_prob=out["stop_prob"],
                   transition=transition, seed=seed)
    for k, child in enumerate(np.random.SeedSequence(seed).spawn(n_runs)):
        rng = np.random.default_rng(child)
        pert = _perturbed_connections(isa, base, rng, flip_mode)
        if draw_strength:
            pert = [replace(c, strength=rng.choice(c.ratings).strength)
                    if c.ratings else c for c in pert]
        walk = _signed_walk(
            IsaData(elements=isa.elements, connections=pert), source, **walk_kw)
        if walk is None:
            continue  # source cut: zero reach, zero mass, sign "~" (not held)
        reach[k] = walk["reach"][idx]
        signed[k] = walk["signed"][idx]
        held[k] = walk["net_sign"][idx] == want

    qs = (0.05, 0.5, 0.95)
    rq = np.quantile(reach, qs, axis=0)
    sq = np.quantile(signed, qs, axis=0)
    reached = (reach > 0).mean(axis=0)
    holds = held.mean(axis=0)
    for j, r in enumerate(brows):
        row = {key: r[key] for key in ("id", "label", "reach_probability",
                                       "net_sign")}
        row["reached_share"] = float(reached[j])
        row["sign_holds_share"] = float(holds[j]) if want[j] != 0 else None
        for name, arr in (("reach", rq), ("signed_mass", sq)):
            for qi, tag in enumerate(("q05", "q50", "q95")):
                row[f"{name}_{tag}"] = float(arr[qi, j])
        out["rows"].append(row)
    return out
