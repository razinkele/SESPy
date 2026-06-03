# Analysis: Boolean & Simulation Modules — Implementation Plan

> **Status: Implemented** · shipped on `feat/analysis-boolean-simulation` (tip `a55583b`), fast-forwarded to `main` 2026-04-28. The plan's `project_data: reactive.Value[IsaData]` signature was subsequently changed to `reactive.Value[Project]` by the architectural refactor in commit `af051c1` (2026-04-30); current code reads `project_data.get().isa_data` where the plan shows `project_data.get()`. The plan's pre-flight note "Git: SESPy is **not currently a git repository**" (line 19) is now stale — SESPy was initialized as a git repo as part of executing this plan (commit `55d7640`), and every subsequent plan in this corpus was authored and executed against a git working tree.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port two analysis modules (Boolean / Laplacian + Simulation / Monte Carlo) from the R MarineSABRES SES Toolbox into the Shiny-for-Python SESPy port, sharing a new `sespy/dynamics.py` numerics layer.

**Architecture:** Single `sespy/dynamics.py` (numpy + stdlib, no Shiny imports) holds all numerics; mirrors the role of the existing `sespy/network.py`. Two thin module files (`sespy/modules/analysis_boolean.py`, `sespy/modules/analysis_simulation.py`) are UI-orchestration over that layer. They subscribe to `event_bus.isa_change` for stale-data notifications but do *not* auto-recompute (Monte Carlo is too expensive — the user clicks Run).

**Tech Stack:** Python 3.11, micromamba env `shiny`, numpy, pandas, matplotlib, Shiny for Python, networkx (already pulled), pytest, Playwright (for e2e).

**Spec reference:** `docs/superpowers/specs/2026-04-27-analysis-boolean-simulation-design.md`. When in doubt, the spec is authoritative.

**Working directory:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy`. All shell commands assume this is the cwd. Use forward slashes.

**Environment:** `micromamba run -n shiny <cmd>`. Never `pip install`.

**Git:** SESPy is **not currently a git repository**. The "Commit" steps in this plan are best-effort: if you have run `git init` once at the start, they will work; otherwise they are safe no-ops (treat them as save-points). Do NOT initialize git unless the user has explicitly authorized it. If git is unavailable, skip the `git add`/`git commit` steps and just continue to the next task.

---

## Task 0: Verify environment

**Files:** none (read-only sanity check)

- [ ] **Step 1: Verify `shiny` env is active**

Run:
```bash
micromamba run -n shiny python -c "import numpy, pandas, shiny, pyvis; print('ok')"
```
Expected: prints `ok`.

If it fails, stop and ask the user to fix the environment. Do not proceed.

- [ ] **Step 2: Verify the existing test suite is green before changes**

Run:
```bash
micromamba run -n shiny pytest tests/ -q --ignore=tests/test_full_app_e2e.py --ignore=tests/test_burger.py -k "not e2e"
```
Expected: tests pass (or all skip on import errors that are pre-existing — don't fix them, just note in your worklog).

- [ ] **Step 3: Confirm the spec exists at the documented path**

Run:
```bash
ls docs/superpowers/specs/2026-04-27-analysis-boolean-simulation-design.md
```
Expected: file exists.

---

## Task 1: `dynamics.py` — `isa_to_numeric_matrix`

**Files:**
- Create: `sespy/dynamics.py`
- Create: `tests/test_dynamics.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dynamics.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failures (module does not exist)**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: `ImportError: cannot import name 'dynamics' from 'sespy'`.

- [ ] **Step 3: Create `sespy/dynamics.py` with the implementation**

Create `sespy/dynamics.py`:

```python
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
```

- [ ] **Step 4: Run tests — expect pass**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "feat(dynamics): isa_to_numeric_matrix with strength/polarity weights"
```
(Skip if not a git repo.)

---

## Task 2: `dynamics.py` — Laplacian eigenvalues + stability

**Files:**
- Modify: `sespy/dynamics.py`
- Modify: `tests/test_dynamics.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_dynamics.py`:

```python
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
    """Asymmetric directed adjacency → row- and col-direction give different specs."""
    M = np.array([[0.0, 2.0, 0.0],
                  [0.0, 0.0, 3.0],
                  [1.0, 0.0, 0.0]])  # cycle A→B→C→A with mixed weights
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
```

- [ ] **Step 2: Run tests — expect failures**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 4 new tests fail with `AttributeError: module 'sespy.dynamics' has no attribute 'laplacian_eigenvalues'`. The 4 prior tests still pass.

- [ ] **Step 3: Add `LaplacianStability`, `laplacian_eigenvalues`, `laplacian_stability` to `sespy/dynamics.py`**

Append to `sespy/dynamics.py`:

```python
# =============================================================================
# Laplacian spectral analysis
# =============================================================================

class LaplacianStability(TypedDict):
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
    sorted_by_real = sorted(eigvals, key=lambda v: v.real)
    if len(sorted_by_real) >= 2:
        alg_conn = float(sorted_by_real[1].real)
    else:
        alg_conn = float(sorted_by_real[0].real)

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
```

- [ ] **Step 4: Run tests — expect pass**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "feat(dynamics): laplacian eigenvalues + stability characterization"
```

---

## Task 3: `dynamics.py` — `create_boolean_rules`

**Files:**
- Modify: `sespy/dynamics.py`
- Modify: `tests/test_dynamics.py`

- [ ] **Step 1: Append the failing test**

Append to `tests/test_dynamics.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py::test_create_boolean_rules_two_node_signed_split_activators_inhibitors -v
```
Expected: AttributeError on `dynamics.create_boolean_rules`.

- [ ] **Step 3: Add `create_boolean_rules` to `sespy/dynamics.py`**

Append:

```python
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
```

- [ ] **Step 4: Run tests — expect pass**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "feat(dynamics): create_boolean_rules splits signed matrix into activators/inhibitors"
```

---

## Task 4: `dynamics.py` — `boolean_attractors`

**Files:**
- Modify: `sespy/dynamics.py`
- Modify: `tests/test_dynamics.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_dynamics.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failures**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v -k boolean_attractors
```
Expected: 5 fails with AttributeError.

- [ ] **Step 3: Add `boolean_attractors` to `sespy/dynamics.py`**

Append:

```python
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
```

- [ ] **Step 4: Run tests — expect pass**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "feat(dynamics): boolean_attractors via exhaustive 2^N cycle detection"
```

---

## Task 5: `dynamics.py` — `simulate_dynamics`

**Files:**
- Modify: `sespy/dynamics.py`
- Modify: `tests/test_dynamics.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_dynamics.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failures**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v -k simulate_dynamics
```
Expected: 4 fails.

- [ ] **Step 3: Add `simulate_dynamics` to `sespy/dynamics.py`**

Append:

```python
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
```

- [ ] **Step 4: Run tests — expect pass**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "feat(dynamics): simulate_dynamics with preset and explicit initial states"
```

---

## Task 6: `dynamics.py` — `randomize_matrix`

**Files:**
- Modify: `sespy/dynamics.py`
- Modify: `tests/test_dynamics.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_dynamics.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failures**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v -k randomize_matrix
```
Expected: 3 fails.

- [ ] **Step 3: Add `randomize_matrix` to `sespy/dynamics.py`**

Append:

```python
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
```

- [ ] **Step 4: Run tests — expect pass**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 21 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "feat(dynamics): randomize_matrix with three perturbation kinds"
```

---

## Task 7: `dynamics.py` — `state_shift_monte_carlo`

**Files:**
- Modify: `sespy/dynamics.py`
- Modify: `tests/test_dynamics.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_dynamics.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failures**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v -k state_shift_monte_carlo
```
Expected: 5 fails.

- [ ] **Step 3: Add `state_shift_monte_carlo` to `sespy/dynamics.py`**

Append:

```python
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
                sd=float(col.std()),
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
```

- [ ] **Step 4: Run tests — expect pass**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 26 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "feat(dynamics): state_shift_monte_carlo with finite-aware accounting"
```

---

## Task 8: `dynamics.py` — edge cases

**Files:**
- Modify: `tests/test_dynamics.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_dynamics.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect pass**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 30 passed.

The threshold-strict semantics in `boolean_attractors` (from Task 4) is what makes `test_all_zero_matrix_single_absorbing_attractor` pass and what makes the three-node ring test in Task 4 produce period-3 cycles. Do NOT add an `inflow == threshold → keep current state` tiebreaker — that breaks the ring oscillator. The spec edge-case wording was literally inconsistent with the spec ring test; this plan picks the version that matches the canonical Boolean network model used in textbooks.

- [ ] **Step 3: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "test(dynamics): cross-function edge cases (non-square, all-zero, single-node)"
```

---

## Task 9: i18n translation keys

**Files:**
- Modify: `sespy/translations/core.json`

- [ ] **Step 1: Read the existing file to find the right insertion point**

Run:
```bash
micromamba run -n shiny python -c "import json; print(list(json.load(open('sespy/translations/core.json'))['translation'].keys())[:20])"
```
Expected: list begins with `ui.brand.title`, `ui.app.title`, then `nav.*` keys, etc.

- [ ] **Step 2: Add the new keys**

Open `sespy/translations/core.json`. Inside the top-level `"translation": {...}` object, add the following keys. Place them after the existing `analysis.common.*` block if present, or alphabetically among the `nav.*` and other `analysis.*` keys. The exact placement is cosmetic; correctness is the JSON validity and key namespace.

```json
"nav.boolean": {
  "en": "Boolean & Laplacian", "es": "Boolean & Laplaciano", "fr": "Boolean & Laplacien",
  "de": "Boolean & Laplace", "lt": "Boolean & Laplaso", "pt": "Boolean & Laplaciano",
  "it": "Boolean & Laplaciano", "no": "Boolean & Laplace", "el": "Boolean & Laplace"
},
"nav.simulation": {
  "en": "Dynamic Simulation", "es": "Simulación Dinámica", "fr": "Simulation Dynamique",
  "de": "Dynamische Simulation", "lt": "Dinaminė Simuliacija", "pt": "Simulação Dinâmica",
  "it": "Simulazione Dinamica", "no": "Dynamisk Simulering", "el": "Δυναμική Προσομοίωση"
},

"analysis.common.data_changed_rerun": {
  "en": "Data changed — re-run analysis to update results",
  "es": "Data changed — re-run analysis to update results",
  "fr": "Data changed — re-run analysis to update results",
  "de": "Data changed — re-run analysis to update results",
  "lt": "Data changed — re-run analysis to update results",
  "pt": "Data changed — re-run analysis to update results",
  "it": "Data changed — re-run analysis to update results",
  "no": "Data changed — re-run analysis to update results",
  "el": "Data changed — re-run analysis to update results"
},

"boolean.controls": {
  "en": "Controls", "es": "Controles", "fr": "Contrôles",
  "de": "Steuerung", "lt": "Valdymas", "pt": "Controles",
  "it": "Controlli", "no": "Kontroller", "el": "Ελέγχοι"
},
"boolean.direction": {
  "en": "Laplacian direction", "es": "Laplacian direction", "fr": "Laplacian direction",
  "de": "Laplacian direction", "lt": "Laplacian direction", "pt": "Laplacian direction",
  "it": "Laplacian direction", "no": "Laplacian direction", "el": "Laplacian direction"
},
"boolean.cols": {
  "en": "Columns (in-degree)", "es": "Columns (in-degree)", "fr": "Columns (in-degree)",
  "de": "Columns (in-degree)", "lt": "Columns (in-degree)", "pt": "Columns (in-degree)",
  "it": "Columns (in-degree)", "no": "Columns (in-degree)", "el": "Columns (in-degree)"
},
"boolean.rows": {
  "en": "Rows (out-degree)", "es": "Rows (out-degree)", "fr": "Rows (out-degree)",
  "de": "Rows (out-degree)", "lt": "Rows (out-degree)", "pt": "Rows (out-degree)",
  "it": "Rows (out-degree)", "no": "Rows (out-degree)", "el": "Rows (out-degree)"
},
"boolean.max_nodes": {
  "en": "Max nodes (cap on 2^N search)",
  "es": "Max nodes (cap on 2^N search)",
  "fr": "Max nodes (cap on 2^N search)",
  "de": "Max nodes (cap on 2^N search)",
  "lt": "Max nodes (cap on 2^N search)",
  "pt": "Max nodes (cap on 2^N search)",
  "it": "Max nodes (cap on 2^N search)",
  "no": "Max nodes (cap on 2^N search)",
  "el": "Max nodes (cap on 2^N search)"
},
"boolean.run": {
  "en": "Run analysis", "es": "Ejecutar análisis", "fr": "Lancer l'analyse",
  "de": "Analyse starten", "lt": "Vykdyti analizę", "pt": "Executar análise",
  "it": "Esegui analisi", "no": "Kjør analyse", "el": "Εκτέλεση ανάλυσης"
},
"boolean.tab_laplacian": {
  "en": "Laplacian", "es": "Laplaciano", "fr": "Laplacien",
  "de": "Laplace", "lt": "Laplaso", "pt": "Laplaciano",
  "it": "Laplaciano", "no": "Laplace", "el": "Laplace"
},
"boolean.tab_boolean": {
  "en": "Boolean attractors", "es": "Boolean attractors", "fr": "Boolean attractors",
  "de": "Boolean attractors", "lt": "Boolean attractors", "pt": "Boolean attractors",
  "it": "Boolean attractors", "no": "Boolean attractors", "el": "Boolean attractors"
},
"boolean.eigenvalue_index": {
  "en": "Eigenvalue index", "es": "Eigenvalue index", "fr": "Eigenvalue index",
  "de": "Eigenvalue index", "lt": "Eigenvalue index", "pt": "Eigenvalue index",
  "it": "Eigenvalue index", "no": "Eigenvalue index", "el": "Eigenvalue index"
},
"boolean.real_part": {
  "en": "Real part", "es": "Real part", "fr": "Real part",
  "de": "Real part", "lt": "Real part", "pt": "Real part",
  "it": "Real part", "no": "Real part", "el": "Real part"
},
"boolean.spectral_radius": {
  "en": "Spectral radius", "es": "Spectral radius", "fr": "Spectral radius",
  "de": "Spectral radius", "lt": "Spectral radius", "pt": "Spectral radius",
  "it": "Spectral radius", "no": "Spectral radius", "el": "Spectral radius"
},
"boolean.algebraic_connectivity": {
  "en": "Algebraic connectivity",
  "es": "Algebraic connectivity",
  "fr": "Algebraic connectivity",
  "de": "Algebraic connectivity",
  "lt": "Algebraic connectivity",
  "pt": "Algebraic connectivity",
  "it": "Algebraic connectivity",
  "no": "Algebraic connectivity",
  "el": "Algebraic connectivity"
},
"boolean.stability_class": {
  "en": "Stability class", "es": "Stability class", "fr": "Stability class",
  "de": "Stability class", "lt": "Stability class", "pt": "Stability class",
  "it": "Stability class", "no": "Stability class", "el": "Stability class"
},
"boolean.click_run": {
  "en": "Click 'Run analysis' to compute results.",
  "es": "Click 'Run analysis' to compute results.",
  "fr": "Click 'Run analysis' to compute results.",
  "de": "Click 'Run analysis' to compute results.",
  "lt": "Click 'Run analysis' to compute results.",
  "pt": "Click 'Run analysis' to compute results.",
  "it": "Click 'Run analysis' to compute results.",
  "no": "Click 'Run analysis' to compute results.",
  "el": "Click 'Run analysis' to compute results."
},
"boolean.no_attractors": {
  "en": "No attractors found.", "es": "No attractors found.", "fr": "No attractors found.",
  "de": "No attractors found.", "lt": "No attractors found.", "pt": "No attractors found.",
  "it": "No attractors found.", "no": "No attractors found.", "el": "No attractors found."
},
"boolean.cap_below_12": {
  "en": "Network has {n} nodes. Raise the cap slider to at least {n} and re-run.",
  "es": "Network has {n} nodes. Raise the cap slider to at least {n} and re-run.",
  "fr": "Network has {n} nodes. Raise the cap slider to at least {n} and re-run.",
  "de": "Network has {n} nodes. Raise the cap slider to at least {n} and re-run.",
  "lt": "Network has {n} nodes. Raise the cap slider to at least {n} and re-run.",
  "pt": "Network has {n} nodes. Raise the cap slider to at least {n} and re-run.",
  "it": "Network has {n} nodes. Raise the cap slider to at least {n} and re-run.",
  "no": "Network has {n} nodes. Raise the cap slider to at least {n} and re-run.",
  "el": "Network has {n} nodes. Raise the cap slider to at least {n} and re-run."
},
"boolean.cap_above_12": {
  "en": "Network has {n} nodes. Exhaustive Boolean attractor search is hard-capped at 12. Use Simplify Network first.",
  "es": "Network has {n} nodes. Exhaustive Boolean attractor search is hard-capped at 12. Use Simplify Network first.",
  "fr": "Network has {n} nodes. Exhaustive Boolean attractor search is hard-capped at 12. Use Simplify Network first.",
  "de": "Network has {n} nodes. Exhaustive Boolean attractor search is hard-capped at 12. Use Simplify Network first.",
  "lt": "Network has {n} nodes. Exhaustive Boolean attractor search is hard-capped at 12. Use Simplify Network first.",
  "pt": "Network has {n} nodes. Exhaustive Boolean attractor search is hard-capped at 12. Use Simplify Network first.",
  "it": "Network has {n} nodes. Exhaustive Boolean attractor search is hard-capped at 12. Use Simplify Network first.",
  "no": "Network has {n} nodes. Exhaustive Boolean attractor search is hard-capped at 12. Use Simplify Network first.",
  "el": "Network has {n} nodes. Exhaustive Boolean attractor search is hard-capped at 12. Use Simplify Network first."
},
"boolean.no_data": {
  "en": "Add elements and connections in Edit Data before running this analysis.",
  "es": "Add elements and connections in Edit Data before running this analysis.",
  "fr": "Add elements and connections in Edit Data before running this analysis.",
  "de": "Add elements and connections in Edit Data before running this analysis.",
  "lt": "Add elements and connections in Edit Data before running this analysis.",
  "pt": "Add elements and connections in Edit Data before running this analysis.",
  "it": "Add elements and connections in Edit Data before running this analysis.",
  "no": "Add elements and connections in Edit Data before running this analysis.",
  "el": "Add elements and connections in Edit Data before running this analysis."
},
"boolean.error_label": {
  "en": "Error", "es": "Error", "fr": "Erreur",
  "de": "Fehler", "lt": "Klaida", "pt": "Erro",
  "it": "Errore", "no": "Feil", "el": "Σφάλμα"
},

"simulation.controls": {
  "en": "Simulation controls", "es": "Simulation controls", "fr": "Simulation controls",
  "de": "Simulation controls", "lt": "Simulation controls", "pt": "Simulation controls",
  "it": "Simulation controls", "no": "Simulation controls", "el": "Simulation controls"
},
"simulation.n_iter": {
  "en": "Iterations", "es": "Iteraciones", "fr": "Itérations",
  "de": "Iterationen", "lt": "Iteracijos", "pt": "Iterações",
  "it": "Iterazioni", "no": "Iterasjoner", "el": "Επαναλήψεις"
},
"simulation.initial_state": {
  "en": "Initial state", "es": "Initial state", "fr": "Initial state",
  "de": "Initial state", "lt": "Initial state", "pt": "Initial state",
  "it": "Initial state", "no": "Initial state", "el": "Initial state"
},
"simulation.init_zeros": {
  "en": "Zeros", "es": "Zeros", "fr": "Zeros",
  "de": "Zeros", "lt": "Zeros", "pt": "Zeros",
  "it": "Zeros", "no": "Zeros", "el": "Zeros"
},
"simulation.init_random": {
  "en": "Random (Gaussian)", "es": "Random (Gaussian)", "fr": "Random (Gaussian)",
  "de": "Random (Gaussian)", "lt": "Random (Gaussian)", "pt": "Random (Gaussian)",
  "it": "Random (Gaussian)", "no": "Random (Gaussian)", "el": "Random (Gaussian)"
},
"simulation.init_uniform": {
  "en": "Uniform 1.0", "es": "Uniform 1.0", "fr": "Uniform 1.0",
  "de": "Uniform 1.0", "lt": "Uniform 1.0", "pt": "Uniform 1.0",
  "it": "Uniform 1.0", "no": "Uniform 1.0", "el": "Uniform 1.0"
},
"simulation.seed": {
  "en": "Seed (optional)", "es": "Seed (optional)", "fr": "Seed (optional)",
  "de": "Seed (optional)", "lt": "Seed (optional)", "pt": "Seed (optional)",
  "it": "Seed (optional)", "no": "Seed (optional)", "el": "Seed (optional)"
},
"simulation.run_sim": {
  "en": "Run simulation", "es": "Run simulation", "fr": "Run simulation",
  "de": "Run simulation", "lt": "Run simulation", "pt": "Run simulation",
  "it": "Run simulation", "no": "Run simulation", "el": "Run simulation"
},
"simulation.mc_controls": {
  "en": "Monte Carlo controls", "es": "Monte Carlo controls", "fr": "Monte Carlo controls",
  "de": "Monte Carlo controls", "lt": "Monte Carlo controls", "pt": "Monte Carlo controls",
  "it": "Monte Carlo controls", "no": "Monte Carlo controls", "el": "Monte Carlo controls"
},
"simulation.n_simulations": {
  "en": "Number of simulations", "es": "Number of simulations",
  "fr": "Number of simulations", "de": "Number of simulations",
  "lt": "Number of simulations", "pt": "Number of simulations",
  "it": "Number of simulations", "no": "Number of simulations",
  "el": "Number of simulations"
},
"simulation.kind": {
  "en": "Perturbation kind", "es": "Perturbation kind", "fr": "Perturbation kind",
  "de": "Perturbation kind", "lt": "Perturbation kind", "pt": "Perturbation kind",
  "it": "Perturbation kind", "no": "Perturbation kind", "el": "Perturbation kind"
},
"simulation.kind_uniform": {
  "en": "Uniform ±20%", "es": "Uniform ±20%", "fr": "Uniform ±20%",
  "de": "Uniform ±20%", "lt": "Uniform ±20%", "pt": "Uniform ±20%",
  "it": "Uniform ±20%", "no": "Uniform ±20%", "el": "Uniform ±20%"
},
"simulation.kind_sign_flip": {
  "en": "Sign flip (10%)", "es": "Sign flip (10%)", "fr": "Sign flip (10%)",
  "de": "Sign flip (10%)", "lt": "Sign flip (10%)", "pt": "Sign flip (10%)",
  "it": "Sign flip (10%)", "no": "Sign flip (10%)", "el": "Sign flip (10%)"
},
"simulation.kind_gaussian": {
  "en": "Gaussian σ=0.1", "es": "Gaussian σ=0.1", "fr": "Gaussian σ=0.1",
  "de": "Gaussian σ=0.1", "lt": "Gaussian σ=0.1", "pt": "Gaussian σ=0.1",
  "it": "Gaussian σ=0.1", "no": "Gaussian σ=0.1", "el": "Gaussian σ=0.1"
},
"simulation.run_mc": {
  "en": "Run Monte Carlo", "es": "Run Monte Carlo", "fr": "Run Monte Carlo",
  "de": "Run Monte Carlo", "lt": "Run Monte Carlo", "pt": "Run Monte Carlo",
  "it": "Run Monte Carlo", "no": "Run Monte Carlo", "el": "Run Monte Carlo"
},
"simulation.tab_trajectories": {
  "en": "Trajectories", "es": "Trayectorias", "fr": "Trajectoires",
  "de": "Trajektorien", "lt": "Trajektorijos", "pt": "Trajetórias",
  "it": "Traiettorie", "no": "Baner", "el": "Τροχιές"
},
"simulation.tab_final_state": {
  "en": "Final state", "es": "Final state", "fr": "Final state",
  "de": "Final state", "lt": "Final state", "pt": "Final state",
  "it": "Final state", "no": "Final state", "el": "Final state"
},
"simulation.tab_mc": {
  "en": "Monte Carlo", "es": "Monte Carlo", "fr": "Monte Carlo",
  "de": "Monte Carlo", "lt": "Monte Carlo", "pt": "Monte Carlo",
  "it": "Monte Carlo", "no": "Monte Carlo", "el": "Monte Carlo"
},
"simulation.no_data": {
  "en": "Add elements and connections in Edit Data before running this analysis.",
  "es": "Add elements and connections in Edit Data before running this analysis.",
  "fr": "Add elements and connections in Edit Data before running this analysis.",
  "de": "Add elements and connections in Edit Data before running this analysis.",
  "lt": "Add elements and connections in Edit Data before running this analysis.",
  "pt": "Add elements and connections in Edit Data before running this analysis.",
  "it": "Add elements and connections in Edit Data before running this analysis.",
  "no": "Add elements and connections in Edit Data before running this analysis.",
  "el": "Add elements and connections in Edit Data before running this analysis."
},
"simulation.click_run": {
  "en": "Click 'Run simulation' or 'Run Monte Carlo' to compute results.",
  "es": "Click 'Run simulation' or 'Run Monte Carlo' to compute results.",
  "fr": "Click 'Run simulation' or 'Run Monte Carlo' to compute results.",
  "de": "Click 'Run simulation' or 'Run Monte Carlo' to compute results.",
  "lt": "Click 'Run simulation' or 'Run Monte Carlo' to compute results.",
  "pt": "Click 'Run simulation' or 'Run Monte Carlo' to compute results.",
  "it": "Click 'Run simulation' or 'Run Monte Carlo' to compute results.",
  "no": "Click 'Run simulation' or 'Run Monte Carlo' to compute results.",
  "el": "Click 'Run simulation' or 'Run Monte Carlo' to compute results."
},
"simulation.completed": {
  "en": "Simulations completed: {ok} of {n} ({failed} diverged)",
  "es": "Simulations completed: {ok} of {n} ({failed} diverged)",
  "fr": "Simulations completed: {ok} of {n} ({failed} diverged)",
  "de": "Simulations completed: {ok} of {n} ({failed} diverged)",
  "lt": "Simulations completed: {ok} of {n} ({failed} diverged)",
  "pt": "Simulations completed: {ok} of {n} ({failed} diverged)",
  "it": "Simulations completed: {ok} of {n} ({failed} diverged)",
  "no": "Simulations completed: {ok} of {n} ({failed} diverged)",
  "el": "Simulations completed: {ok} of {n} ({failed} diverged)"
}
```

- [ ] **Step 3: Verify the JSON is still valid**

Run:
```bash
micromamba run -n shiny python -c "import json; json.load(open('sespy/translations/core.json')); print('valid json')"
```
Expected: `valid json`.

- [ ] **Step 4: Commit**

```bash
git add sespy/translations/core.json
git commit -m "feat(i18n): add boolean and simulation analysis module keys"
```

---

## Task 10: `analysis_boolean` module

**Files:**
- Create: `sespy/modules/analysis_boolean.py`

- [ ] **Step 1: Create the module file**

Create `sespy/modules/analysis_boolean.py`:

```python
"""Boolean / Laplacian analysis module.

Mirrors `modules/analysis_boolean.R`. Two tabs:
  - Laplacian: bar chart of eigenvalue spectrum + stability summary card.
  - Boolean: attractor table from exhaustive 2^N state-space search.

Pattern matches `analysis_metrics.py` (matplotlib via @render.plot, no pyvis).
"""
from __future__ import annotations

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from .. import dynamics
from ..data_structure import IsaData
from ..event_bus import EventBus
from ..i18n import Translator, t


def _format_state(state_int: int, n: int) -> str:
    """Format integer state as fixed-width binary string, MSB-first by node index."""
    return format(state_int, f"0{n}b")[::-1]  # reverse so bit i = node i


@module.ui
def analysis_boolean_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.boolean")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("boolean.controls")),
                ui.input_radio_buttons(
                    "direction",
                    t("boolean.direction"),
                    {"cols": t("boolean.cols"), "rows": t("boolean.rows")},
                    selected="cols",
                ),
                ui.input_slider(
                    "max_nodes",
                    t("boolean.max_nodes"),
                    min=4, max=12, value=12, step=1,
                ),
                ui.tags.hr(),
                ui.input_action_button(
                    "run_boolean",
                    t("boolean.run"),
                    class_="btn btn-primary btn-block",
                ),
                width=280,
            ),
            ui.navset_tab(
                ui.nav_panel(
                    t("boolean.tab_laplacian"),
                    ui.output_plot("eigenvalue_plot", height="280px"),
                    ui.tags.hr(),
                    ui.output_ui("stability_summary"),
                ),
                ui.nav_panel(
                    t("boolean.tab_boolean"),
                    ui.output_ui("attractor_panel"),
                ),
                id="boolean_tabs",
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_boolean_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[IsaData],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    result_store: reactive.Value[dict | None] = reactive.value(None)

    @reactive.effect
    @reactive.event(input.run_boolean, ignore_init=True)
    def _run() -> None:
        try:
            isa = project_data.get()
            if not isa.elements:
                result_store.set({"error": t("boolean.no_data"), "stability": None,
                                  "attractors": None, "node_ids": []})
                return
            M, node_ids = dynamics.isa_to_numeric_matrix(isa)
            stability = dynamics.laplacian_stability(M, direction=input.direction() or "cols")
            rules = dynamics.create_boolean_rules(M)
            attractors = dynamics.boolean_attractors(rules, max_nodes=int(input.max_nodes() or 12))
            result_store.set({
                "error": None,
                "stability": stability,
                "attractors": attractors,
                "node_ids": node_ids,
            })
        except ValueError as exc:
            result_store.set({
                "error": str(exc),
                "stability": None,
                "attractors": None,
                "node_ids": [],
            })

    @reactive.effect
    def _stale_warning() -> None:
        # Subscribe ONLY to ISA changes. The reactive read of result_store
        # must be isolated — otherwise this effect re-fires when Run sets
        # result_store and would post a spurious "data changed" notification
        # immediately after a successful run.
        event_bus.isa_change.get()
        with reactive.isolate():
            if result_store.get() is not None:
                ui.notification_show(
                    t("analysis.common.data_changed_rerun"),
                    duration=5,
                    type="warning",
                )

    @output
    @render.plot
    def eigenvalue_plot():
        import matplotlib.pyplot as plt

        r = result_store.get()
        fig, ax = plt.subplots(figsize=(8, 2.6))
        if r is None:
            ax.text(0.5, 0.5, t("boolean.click_run"), ha="center", va="center",
                    transform=ax.transAxes)
            ax.axis("off")
            fig.tight_layout()
            return fig
        if r.get("error"):
            ax.text(0.5, 0.5, r["error"], ha="center", va="center",
                    color="#a02020", transform=ax.transAxes, wrap=True)
            ax.axis("off")
            fig.tight_layout()
            return fig
        eigvals = r["stability"]["eigenvalues"]
        reals = [v.real for v in eigvals]
        ax.bar(range(len(reals)), reals, color="#4a90b8", edgecolor="#2d5a7b")
        ax.set_xlabel(t("boolean.eigenvalue_index"))
        ax.set_ylabel(t("boolean.real_part"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    @output
    @render.ui
    def stability_summary():
        r = result_store.get()
        if r is None or r.get("error") or r.get("stability") is None:
            return ui.tags.p(t("boolean.click_run"), class_="text-muted")
        s = r["stability"]
        return ui.tags.dl(
            ui.tags.dt(t("boolean.spectral_radius")),
            ui.tags.dd(f"{s['spectral_radius']:.4f}"),
            ui.tags.dt(t("boolean.algebraic_connectivity")),
            ui.tags.dd(f"{s['algebraic_connectivity']:.4f}"),
            ui.tags.dt(t("boolean.stability_class")),
            ui.tags.dd(s["stability_class"]),
        )

    @output
    @render.ui
    def attractor_panel():
        import pandas as pd

        r = result_store.get()
        if r is None:
            return ui.tags.p(t("boolean.click_run"), class_="text-muted")
        if r.get("error"):
            return ui.tags.div(r["error"], class_="alert alert-danger")
        a = r["attractors"]
        node_ids = r["node_ids"]
        n = len(node_ids)

        if a.get("error") == "too_large":
            n_n = a.get("n_nodes", 0)
            if n_n <= 12:
                msg = t("boolean.cap_below_12").format(n=n_n)
            else:
                msg = t("boolean.cap_above_12").format(n=n_n)
            return ui.tags.div(msg, class_="alert alert-warning")

        rows = []
        for att in a.get("attractors", []):
            states = att["states"]
            first = _format_state(states[0], n) if states else ""
            extra = f" + {att['period'] - 1} more" if att["period"] > 1 else ""
            rows.append({
                "type": att["type"],
                "period": att["period"],
                "basin_size": att["basin_size"],
                "representative state": first + extra,
            })
        if not rows:
            return ui.tags.p(t("boolean.no_attractors"))
        df = pd.DataFrame(rows)
        return ui.HTML(df.to_html(index=False, classes="table table-sm table-striped"))
```

- [ ] **Step 2: Sanity check the import**

Run:
```bash
micromamba run -n shiny python -c "from sespy.modules.analysis_boolean import analysis_boolean_ui, analysis_boolean_server; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/analysis_boolean.py
git commit -m "feat(modules): analysis_boolean — Laplacian + Boolean attractors UI"
```

---

## Task 11: `analysis_simulation` module

**Files:**
- Create: `sespy/modules/analysis_simulation.py`

- [ ] **Step 1: Create the module file**

Create `sespy/modules/analysis_simulation.py`:

```python
"""Dynamic Simulation analysis module.

Mirrors the deterministic-sim + Monte Carlo state-shift parts of
`modules/analysis_simulation.R`. Two run buttons:
  - Run Simulation: deterministic linear iteration; trajectories + final state.
  - Run Monte Carlo: perturbed-matrix sampling; per-node summary + histograms.

Pattern matches `analysis_metrics.py` (matplotlib via @render.plot).
"""
from __future__ import annotations

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from .. import dynamics
from ..data_structure import IsaData
from ..event_bus import EventBus
from ..i18n import Translator, t


@module.ui
def analysis_simulation_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.simulation")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("simulation.controls")),
                ui.input_slider(
                    "n_iter", t("simulation.n_iter"),
                    min=50, max=2000, value=200, step=50,
                ),
                ui.input_radio_buttons(
                    "initial_state", t("simulation.initial_state"),
                    {
                        "zeros": t("simulation.init_zeros"),
                        "random": t("simulation.init_random"),
                        "uniform": t("simulation.init_uniform"),
                    },
                    selected="random",
                ),
                ui.input_numeric(
                    "sim_seed", t("simulation.seed"), value=42, min=0,
                ),
                ui.input_action_button(
                    "run_sim", t("simulation.run_sim"),
                    class_="btn btn-primary btn-block",
                ),
                ui.tags.hr(),
                ui.h5(t("simulation.mc_controls")),
                ui.input_slider(
                    "n_simulations", t("simulation.n_simulations"),
                    min=10, max=500, value=100, step=10,
                ),
                ui.input_radio_buttons(
                    "kind", t("simulation.kind"),
                    {
                        "uniform": t("simulation.kind_uniform"),
                        "sign_flip": t("simulation.kind_sign_flip"),
                        "gaussian": t("simulation.kind_gaussian"),
                    },
                    selected="uniform",
                ),
                ui.input_numeric(
                    "mc_seed", t("simulation.seed"), value=42, min=0,
                ),
                ui.input_action_button(
                    "run_mc", t("simulation.run_mc"),
                    class_="btn btn-primary btn-block",
                ),
                width=300,
            ),
            ui.navset_tab(
                ui.nav_panel(
                    t("simulation.tab_trajectories"),
                    ui.output_plot("trajectory_plot", height="400px"),
                ),
                ui.nav_panel(
                    t("simulation.tab_final_state"),
                    ui.output_plot("final_state_plot", height="320px"),
                ),
                ui.nav_panel(
                    t("simulation.tab_mc"),
                    ui.output_ui("mc_summary"),
                    ui.output_plot("mc_histograms", height="500px"),
                ),
                id="simulation_tabs",
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_simulation_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[IsaData],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    sim_store: reactive.Value[dict | None] = reactive.value(None)
    mc_store: reactive.Value[dict | None] = reactive.value(None)

    def _build_matrix() -> tuple | None:
        isa = project_data.get()
        if not isa.elements:
            return None
        try:
            return dynamics.isa_to_numeric_matrix(isa)
        except ValueError as exc:
            return ("error", str(exc))

    @reactive.effect
    @reactive.event(input.run_sim, ignore_init=True)
    def _run_sim() -> None:
        built = _build_matrix()
        if built is None:
            sim_store.set({"error": t("simulation.no_data"), "traj": None,
                           "node_ids": []})
            return
        if isinstance(built, tuple) and len(built) == 2 and built[0] == "error":
            sim_store.set({"error": built[1], "traj": None, "node_ids": []})
            return
        M, node_ids = built
        traj = dynamics.simulate_dynamics(
            M, n_iter=int(input.n_iter() or 200),
            initial_state=input.initial_state() or "random",
            seed=int(input.sim_seed() or 42),
        )
        sim_store.set({"error": None, "traj": traj, "node_ids": node_ids})

    @reactive.effect
    @reactive.event(input.run_mc, ignore_init=True)
    def _run_mc() -> None:
        built = _build_matrix()
        if built is None:
            mc_store.set({"error": t("simulation.no_data"), "result": None,
                          "node_ids": []})
            return
        if isinstance(built, tuple) and len(built) == 2 and built[0] == "error":
            mc_store.set({"error": built[1], "result": None, "node_ids": []})
            return
        M, node_ids = built
        try:
            res = dynamics.state_shift_monte_carlo(
                M, n_simulations=int(input.n_simulations() or 100),
                n_iter=int(input.n_iter() or 200),
                kind=input.kind() or "uniform",
                seed=int(input.mc_seed() or 42),
            )
            mc_store.set({"error": None, "result": res, "node_ids": node_ids})
        except ValueError as exc:
            mc_store.set({"error": str(exc), "result": None, "node_ids": []})

    @reactive.effect
    def _stale_warning() -> None:
        # Subscribe ONLY to ISA changes; isolate the result-store reads so
        # this effect doesn't re-fire when Run* updates a store.
        event_bus.isa_change.get()
        with reactive.isolate():
            if sim_store.get() is not None or mc_store.get() is not None:
                ui.notification_show(
                    t("analysis.common.data_changed_rerun"),
                    duration=5,
                    type="warning",
                )

    # ---- Trajectory plot ----

    @output
    @render.plot
    def trajectory_plot():
        import matplotlib.pyplot as plt

        s = sim_store.get()
        fig, ax = plt.subplots(figsize=(10, 4.5))
        if s is None:
            ax.text(0.5, 0.5, t("simulation.click_run"), ha="center", va="center",
                    transform=ax.transAxes)
            ax.axis("off")
            return fig
        if s.get("error"):
            ax.text(0.5, 0.5, s["error"], ha="center", va="center",
                    transform=ax.transAxes, color="#a02020", wrap=True)
            ax.axis("off")
            return fig
        traj = s["traj"]
        node_ids = s["node_ids"]
        n_iter, n_nodes = traj.shape
        cmap = plt.get_cmap("viridis")
        for j in range(n_nodes):
            ax.plot(
                range(n_iter), traj[:, j],
                color=cmap(j / max(1, n_nodes - 1)),
                label=node_ids[j] if j < len(node_ids) else str(j),
                linewidth=1.2,
            )
        ax.set_xlabel("iteration")
        ax.set_ylabel("value")
        if n_nodes <= 18:
            ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
                      fontsize=8, frameon=False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    # ---- Final-state bar chart ----

    @output
    @render.plot
    def final_state_plot():
        import matplotlib.pyplot as plt

        s = sim_store.get()
        fig, ax = plt.subplots(figsize=(10, 3.5))
        if s is None or s.get("error") or s.get("traj") is None:
            ax.axis("off")
            return fig
        traj = s["traj"]
        final = traj[-1]
        node_ids = s["node_ids"]
        ax.bar(range(len(final)), final, color="#4a90b8", edgecolor="#2d5a7b")
        ax.set_xticks(range(len(final)))
        ax.set_xticklabels(node_ids, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("final value")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    # ---- Monte Carlo summary + histograms ----

    @output
    @render.ui
    def mc_summary():
        m = mc_store.get()
        if m is None:
            return ui.tags.p(t("simulation.click_run"), class_="text-muted")
        if m.get("error"):
            return ui.tags.div(m["error"], class_="alert alert-danger")
        res = m["result"]
        ok = res["n_simulations"] - res["n_failed"]
        msg = t("simulation.completed").format(
            ok=ok, n=res["n_simulations"], failed=res["n_failed"]
        )
        # Per-node summary table
        import pandas as pd

        node_ids = m["node_ids"]
        rows = []
        for i, nid in enumerate(node_ids):
            s = res["summary"][i]
            rows.append({
                "node": nid,
                "mean": f"{s['mean']:.4f}",
                "sd": f"{s['sd']:.4f}",
                "p5": f"{s['p5']:.4f}",
                "p95": f"{s['p95']:.4f}",
            })
        df = pd.DataFrame(rows)
        return ui.tags.div(
            ui.tags.p(msg, class_="text-info"),
            ui.HTML(df.to_html(index=False, classes="table table-sm table-striped")),
        )

    @output
    @render.plot
    def mc_histograms():
        import matplotlib.pyplot as plt

        m = mc_store.get()
        if m is None or m.get("error") or m.get("result") is None:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.axis("off")
            return fig
        res = m["result"]
        node_ids = m["node_ids"]
        n_nodes = len(node_ids)
        if res["final_states"].size == 0:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.text(0.5, 0.5, "All simulations diverged.", ha="center", va="center",
                    transform=ax.transAxes)
            ax.axis("off")
            return fig
        # Small multiples: up to 4 cols, ceil(n/4) rows
        ncols = min(4, n_nodes)
        nrows = (n_nodes + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols, figsize=(10, 2.4 * nrows),
                                  squeeze=False)
        for i in range(n_nodes):
            r, c = divmod(i, ncols)
            ax = axes[r][c]
            ax.hist(res["final_states"][:, i], bins=15,
                    color="#4a90b8", edgecolor="#2d5a7b", alpha=0.85)
            ax.set_title(node_ids[i], fontsize=9)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
        # Hide unused axes
        for k in range(n_nodes, nrows * ncols):
            r, c = divmod(k, ncols)
            axes[r][c].axis("off")
        fig.tight_layout()
        return fig
```

- [ ] **Step 2: Sanity check the import**

Run:
```bash
micromamba run -n shiny python -c "from sespy.modules.analysis_simulation import analysis_simulation_ui, analysis_simulation_server; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/analysis_simulation.py
git commit -m "feat(modules): analysis_simulation — deterministic + Monte Carlo state-shift"
```

---

## Task 12: Wire-up — register modules in `app.py`

**Files:**
- Modify: `app.py`

The existing `app.py` registers each module in five places: an import block, the `NAV` list, the `NAV_TO_STEP` mapping, the `PANELS` tuple, and a server-side `<module>_server(...)` call. (No `dashboard.py` change is needed — `NAV` is defined in `app.py`, and `dashboard.py` simply renders whatever it's given.) The existing `analysis_intervention` registration is the closest analog. Mirror it for both new modules.

- [ ] **Step 1: Add imports**

In `app.py`, after the existing module imports (around line 41), add:

```python
from sespy.modules.analysis_boolean import (
    analysis_boolean_server,
    analysis_boolean_ui,
)
from sespy.modules.analysis_simulation import (
    analysis_simulation_server,
    analysis_simulation_ui,
)
```

- [ ] **Step 2: Add NAV entries**

In the `NAV: list[NavItem] = [...]` block, insert two new entries between `leverage` and `intervention` (matches the spec's "between Leverage Points and Intervention" ordering):

```python
    NavItem(id="boolean",     icon="square-root-variable", label="Boolean & Laplacian", label_key="nav.boolean"),
    NavItem(id="simulation",  icon="wave-square",         label="Dynamic Simulation",  label_key="nav.simulation"),
```

The complete updated NAV list should look like:

```python
NAV: list[NavItem] = [
    NavItem(id="templates", icon="layer-group",    label="Templates",         label_key="nav.templates"),
    NavItem(id="entry",    icon="pen-to-square",   label="Edit Data",         label_key="nav.entry"),
    NavItem(id="cld",      icon="diagram-project", label="CLD Visualization", label_key="nav.cld"),
    NavItem(id="loops",    icon="rotate-right",    label="Loop Analysis",     label_key="nav.loops"),
    NavItem(id="metrics",  icon="chart-line",      label="Network Metrics",   label_key="nav.metrics"),
    NavItem(id="leverage", icon="bullseye",        label="Leverage Points",   label_key="nav.leverage"),
    NavItem(id="boolean",     icon="square-root-variable", label="Boolean & Laplacian", label_key="nav.boolean"),
    NavItem(id="simulation",  icon="wave-square",         label="Dynamic Simulation",  label_key="nav.simulation"),
    NavItem(id="intervention", icon="hand-pointer", label="Intervention",     label_key="nav.intervention"),
    NavItem(id="simplify",  icon="scissors",        label="Simplify Network",  label_key="nav.simplify"),
    NavItem(id="import",   icon="file-excel",      label="Import Data",       label_key="nav.import"),
    NavItem(id="recent",   icon="folder-open",     label="Recent Projects",   label_key="nav.recent"),
    NavItem(id="report",   icon="file-pdf",        label="Export Report",     label_key="nav.report"),
]
```

- [ ] **Step 3: Add `NAV_TO_STEP` entries**

Update `NAV_TO_STEP` to include both new ids in the "analyze" stage:

```python
NAV_TO_STEP = {
    "templates": "create",
    "entry": "create",
    "cld": "visualize", "loops": "analyze", "metrics": "analyze",
    "leverage": "analyze", "boolean": "analyze", "simulation": "analyze",
    "intervention": "analyze", "simplify": "analyze",
    "import": "create",
    "recent": "start", "report": "report",
}
```

- [ ] **Step 4: Add PANEL entries**

Update the `PANELS = (...)` tuple to include the two new modules in the same order as in `NAV`:

```python
PANELS = (
    ui.nav_panel("Templates",         templates_ui("templates"),                   value="templates"),
    ui.nav_panel("Edit Data",         isa_data_entry_ui("entry"),                  value="entry"),
    ui.nav_panel("CLD Visualization", cld_viz_ui("cld"),                          value="cld"),
    ui.nav_panel("Loop Analysis",     analysis_loops_ui("loops"),                  value="loops"),
    ui.nav_panel("Network Metrics",   analysis_metrics_ui("metrics"),              value="metrics"),
    ui.nav_panel("Leverage Points",   analysis_leverage_ui("leverage"),            value="leverage"),
    ui.nav_panel("Boolean & Laplacian", analysis_boolean_ui("boolean"),            value="boolean"),
    ui.nav_panel("Dynamic Simulation",  analysis_simulation_ui("simulation"),      value="simulation"),
    ui.nav_panel("Intervention",      analysis_intervention_ui("intervention"),    value="intervention"),
    ui.nav_panel("Simplify Network",  analysis_simplify_ui("simplify"),            value="simplify"),
    ui.nav_panel("Import Data",       import_data_ui("import"),                    value="import"),
    ui.nav_panel("Recent Projects",   recent_projects_ui("recent"),                value="recent"),
    ui.nav_panel("Export Report",     report_export_ui("report"),                  value="report"),
)
```

- [ ] **Step 5: Add server registrations**

In the `def server(input, output, session)` function, after the existing `analysis_leverage_server(...)` call and before `analysis_intervention_server(...)`, add:

```python
    analysis_boolean_server(
        "boolean",
        project_data=project_data,
        event_bus=event_bus,
        translator=T,
    )
    analysis_simulation_server(
        "simulation",
        project_data=project_data,
        event_bus=event_bus,
        translator=T,
    )
```

- [ ] **Step 6: Manual smoke test**

Run:
```bash
micromamba run -n shiny shiny run --port 8000 app.py
```

In a separate terminal/browser, open `http://127.0.0.1:8000`. Verify:
- Two new nav buttons appear: "Boolean & Laplacian" and "Dynamic Simulation".
- Clicking each loads the module.
- Clicking Run on Boolean produces an eigenvalue bar chart and an attractor table.
- Clicking Run Simulation on Simulation produces a trajectory plot.
- Clicking Run Monte Carlo with `n_simulations=20` produces a summary table and histograms.

Stop the server (Ctrl+C) once verified.

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "wire(app): register Boolean & Simulation analysis modules"
```

---

## Task 13: E2E test — Boolean module

**Files:**
- Create: `tests/test_boolean_e2e.py`

- [ ] **Step 1: Create the e2e test**

Create `tests/test_boolean_e2e.py`:

```python
"""E2E for the Boolean / Laplacian module: navigate, click Run, verify
eigenvalue plot renders and attractor table populates."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await page.wait_for_selector("#sespy_nav_boolean", timeout=15000)
        await page.click("#sespy_nav_boolean")
        await page.wait_for_timeout(1500)

        # Run analysis
        await page.click("#boolean-run_boolean")
        await page.wait_for_timeout(3000)

        # Eigenvalue plot rendered (img tag inside the plot output)
        plot_visible = await page.evaluate(
            "() => !!document.querySelector('#boolean-eigenvalue_plot img')"
        )
        print(f"eigenvalue plot rendered: {plot_visible}")
        assert plot_visible, "eigenvalue plot did not render"

        # Switch to the Boolean attractors tab
        await page.click("text=Boolean attractors")
        await page.wait_for_timeout(1500)

        # Attractor table has at least one row
        n_rows = await page.evaluate(
            "() => document.querySelectorAll('#boolean-attractor_panel table tbody tr').length"
        )
        print(f"attractor table rows: {n_rows}")
        assert n_rows >= 1, f"expected >=1 attractor row, got {n_rows}"

        # No error alert visible
        error_visible = await page.evaluate(
            "() => !!document.querySelector('#boolean-attractor_panel .alert-danger')"
        )
        assert not error_visible, "unexpected error alert in Boolean tab"

        await page.screenshot(path="tests/screenshots/boolean.png")
        print("\nboolean e2e assertions pass")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Run the e2e test (server must be running)**

In one terminal:
```bash
micromamba run -n shiny shiny run --port 8000 app.py
```

In another terminal:
```bash
mkdir -p tests/screenshots
micromamba run -n shiny python tests/test_boolean_e2e.py
```
Expected: prints `boolean e2e assertions pass`. Screenshot saved.

If it fails, the most likely culprits are:
1. Selector mismatch — Playwright's `#boolean-run_boolean` assumes the Shiny module id namespacing puts the module name as a prefix. Inspect the actual DOM with `page.content()` or browser dev tools.
2. Sample data may not have the right shape for the analysis. The default sample at `data/sample_ses.json` should have multiple connected nodes; if not, populate via Edit Data first or use a template.

Stop the server when done.

- [ ] **Step 3: Commit**

```bash
git add tests/test_boolean_e2e.py
git commit -m "test(e2e): boolean module renders eigenvalue plot and attractor table"
```

---

## Task 14: E2E test — Simulation module

**Files:**
- Create: `tests/test_simulation_e2e.py`

- [ ] **Step 1: Create the e2e test**

Create `tests/test_simulation_e2e.py`:

```python
"""E2E for the Dynamic Simulation module: navigate, click Run Simulation
and Run Monte Carlo, verify both result panels populate."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 1000})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await page.wait_for_selector("#sespy_nav_simulation", timeout=15000)
        await page.click("#sespy_nav_simulation")
        await page.wait_for_timeout(1500)

        # ---- Deterministic simulation ----
        await page.click("#simulation-run_sim")
        await page.wait_for_timeout(2500)

        traj_visible = await page.evaluate(
            "() => !!document.querySelector('#simulation-trajectory_plot img')"
        )
        print(f"trajectory plot rendered: {traj_visible}")
        assert traj_visible

        # Switch to Final state tab
        await page.click("text=Final state")
        await page.wait_for_timeout(1000)
        final_visible = await page.evaluate(
            "() => !!document.querySelector('#simulation-final_state_plot img')"
        )
        assert final_visible, "final state plot did not render"

        # ---- Monte Carlo ----
        # Note: the n_simulations control is an ion-rangeslider, which doesn't
        # respond to plain JS .value assignment. Leave the slider at its default
        # (100) and accept the longer wait. ~10-15s on a small sample dataset.
        await page.click("#simulation-run_mc")
        await page.wait_for_timeout(20000)

        # Switch to Monte Carlo tab
        await page.click("text=Monte Carlo")
        await page.wait_for_timeout(1500)

        # Summary table populated
        n_rows = await page.evaluate(
            "() => document.querySelectorAll('#simulation-mc_summary table tbody tr').length"
        )
        print(f"MC summary rows: {n_rows}")
        assert n_rows >= 1

        # Completion message visible (looks for "Simulations completed:")
        msg_seen = await page.evaluate(
            "() => Array.from(document.querySelectorAll('#simulation-mc_summary p'))"
            "  .some(p => p.textContent.includes('Simulations completed'))"
        )
        assert msg_seen, "MC completion message not found"

        # Histogram plot visible
        hist_visible = await page.evaluate(
            "() => !!document.querySelector('#simulation-mc_histograms img')"
        )
        assert hist_visible, "MC histograms plot did not render"

        await page.screenshot(path="tests/screenshots/simulation.png")
        print("\nsimulation e2e assertions pass")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Run the e2e test**

Server must be running on port 8000.

```bash
micromamba run -n shiny python tests/test_simulation_e2e.py
```
Expected: prints `simulation e2e assertions pass`. The Monte Carlo step takes ~10–15s with the default `n_simulations=100` on a small sample dataset; the test waits 20s, which is generous.

- [ ] **Step 3: Commit**

```bash
git add tests/test_simulation_e2e.py
git commit -m "test(e2e): simulation module renders trajectories, final state, MC summary"
```

---

## Task 15: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full unit test pass**

Run:
```bash
micromamba run -n shiny pytest tests/test_dynamics.py -v
```
Expected: 30 passed.

- [ ] **Step 2: Existing test suite still green**

Run:
```bash
micromamba run -n shiny pytest tests/ -q -k "not e2e"
```
Expected: at minimum the previously-passing tests still pass; no new failures introduced.

- [ ] **Step 3: Full e2e pass (server running)**

In one terminal:
```bash
micromamba run -n shiny shiny run --port 8000 app.py
```

In another:
```bash
micromamba run -n shiny python tests/test_boolean_e2e.py
micromamba run -n shiny python tests/test_simulation_e2e.py
```
Expected: both print "assertions pass".

- [ ] **Step 4: Update README's module count**

Open `README.md`. Find the line that says "**11 modules**" (currently in the opening summary). Replace with "**13 modules**". Find the modules table; add two rows in the same style as the existing entries:

```markdown
| **Boolean / Laplacian** (`sespy/modules/analysis_boolean.py`) | `modules/analysis_boolean.R` | Laplacian eigenvalue spectrum + Boolean attractor enumeration via exhaustive 2^N state-space search (capped at 12 nodes). |
| **Dynamic Simulation** (`sespy/modules/analysis_simulation.py`) | `modules/analysis_simulation.R` | Deterministic linear-matrix iteration + Monte Carlo state-shift analysis with finite-aware divergence accounting. |
```

- [ ] **Step 5: Commit the README update**

```bash
git add README.md
git commit -m "docs(readme): note Boolean & Simulation modules (now 13 modules)"
```

---

## Self-review notes

Spec coverage check (run before declaring done):
- Section 2 architecture (new files, wire-up changes, no new deps): Tasks 1–14 cover all six new files; Task 9 modifies `core.json`, Task 12 modifies `app.py`. No `dashboard.py` change needed (NAV is in `app.py`).
- Section 3 components (8 functions in dynamics.py, two module files): Tasks 1–7 implement the 8 functions; Tasks 10–11 implement the modules.
- Section 4 data flow (freshness via event_bus, compute pipeline per Run): Tasks 10/11 implement `_stale_warning` reactives (with `reactive.isolate()` around result-store reads to avoid spurious notifications) and use `@reactive.event(..., ignore_init=True)` per spec.
- Section 5 error handling (5 surfaces): all five are present in Tasks 10/11 — empty ISA gate, `ValueError` catch on matrix construction, `too_large` branch with the spec's two-pronged message, NaN/Inf handled inside `state_shift_monte_carlo` (Task 7) and surfaced in `mc_summary`, stale notification on `event_bus.isa_change`.
- Section 6 testing: 26 unit tests across Tasks 1–7 (Tasks 4 and 7 each contribute 5) + 4 edge-case tests (Task 8) = 30 unit tests; 2 e2e tests (Tasks 13–14). The all-zero edge case in Task 8 deviates from a literal reading of spec §6 — see Task 8 inline note for the resolved math.
- Section 7 implementation order: this plan follows the spec's order exactly.
- Section 8 non-goals: nothing in this plan touches `sespy/network.py`, project schema, autosave, or other existing modules.
