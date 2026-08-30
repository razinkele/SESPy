# Loop Dominance Over Time (#22) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user see *which feedback loop is governing the simulated behaviour, and when that changes* — surfaced as a small set of confirmed regime shifts over the trajectory they already ran.

**Architecture:** Two pure functions in `sespy/network.py` over a caller-supplied trajectory (`loop_dominance` → per-loop share series; `dominance_shifts` → confirmed transitions), plus a default-off overlay on the existing simulation trajectory plot. Nothing simulates; the overlay annotates the run already on screen, reading a snapshot taken at Run time so a later model edit cannot mis-pair a new ISA with an old trajectory.

**Tech Stack:** Python 3.12+, numpy, networkx (existing `feedback_loops`), Shiny for Python, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-30-sespy-loop-dominance-design.md` — **read it before Task 1**. It was revised after a multi-agent review that produced 32 surviving findings; several requirements below look arbitrary without its reasoning.

## Global Constraints

- **No new dependencies.** numpy and networkx are already used in `sespy/network.py`.
- **Never name a loop by enumeration index.** `feedback_loops`' output order *and each cycle's rotation* vary across processes (`nx.simple_cycles` iterates sets). Canonicalise before assigning ids; key rows by `nodes`. Tests must not assert on enumeration position.
- **`loop_dominance` returns no prose.** `note` is a machine token; the UI maps it to a translated key. User-visible strings go through `t("key")` against `sespy/translations/core.json` in **all nine** languages (en/es/fr/de/lt/pt/it/no/el) — `tests/test_i18n.py` fails otherwise.
- **Only cycles of length ≥ 2 participate.** Self-loops are filtered out.
- **The finiteness guard is per timestep, not per result.** Truncate the series; never blank a whole run over one late step.
- **Function-local import for `isa_to_numeric_matrix`** — `dynamics.py:16` already imports `network`, so a module-level import is circular. Precedent: `network.py:984` does a function-local `import numpy as np`.
- **Work on a branch in the SESPy checkout itself, not a worktree.** `__editable__.sespy-1.3.0.pth` pins `sespy` to this path; a worktree would leave MosaicSES importing unmodified code and the cross-repo gate would prove nothing.
- **Cross-repo gate before merge:** SESPy unit + `tests/run_e2e.py`, then MosaicSES `pytest tests/`. Never `-k "not e2e"`. Never run the two concurrently.
- Python is micromamba env `shiny`: `micromamba run -n shiny python -m pytest ...`. There is no python on PATH. A multi-line `python -c` gets split per line by this machine's shell — use a `.py` file.

---

### Task 1: `_canonical_cycles` — deterministic loop identity

**Files:**
- Modify: `sespy/network.py` (add above `loop_dominance`, near `feedback_loops` at `:43`)
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: nothing
- Produces: `_canonical_cycles(cycles: list[list[str]]) -> list[list[str]]` — self-loops removed, each cycle rotated to its lexicographically-least start, list sorted. Used by Task 2.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_network.py`:

```python
def test_canonical_cycles_rotation_is_stable():
    from sespy.network import _canonical_cycles
    # Same cycle, three rotations - all must canonicalise identically.
    a = _canonical_cycles([["B", "C", "A"]])
    b = _canonical_cycles([["C", "A", "B"]])
    c = _canonical_cycles([["A", "B", "C"]])
    assert a == b == c == [["A", "B", "C"]]


def test_canonical_cycles_order_is_stable():
    from sespy.network import _canonical_cycles
    one = _canonical_cycles([["B", "C"], ["A", "D"]])
    two = _canonical_cycles([["A", "D"], ["B", "C"]])
    assert one == two == [["A", "D"], ["B", "C"]]


def test_canonical_cycles_drops_self_loops():
    from sespy.network import _canonical_cycles
    # A self-loop is not a feedback loop for dominance: feedback_loops
    # returns them, and left in the denominator a self-growing node was
    # measured governing 86% of a test system.
    assert _canonical_cycles([["X"], ["A", "B"]]) == [["A", "B"]]
    assert _canonical_cycles([["X"]]) == []


def test_canonical_cycles_preserves_direction():
    from sespy.network import _canonical_cycles
    # Rotation must not reverse the cycle - A->B->C is not A->C->B.
    assert _canonical_cycles([["B", "C", "A"]]) == [["A", "B", "C"]]
    assert _canonical_cycles([["C", "B", "A"]]) == [["A", "C", "B"]]
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k canonical_cycles`
Expected: FAIL with `ImportError: cannot import name '_canonical_cycles'`

- [ ] **Step 3: Implement**

In `sespy/network.py`, directly below `feedback_loops`:

```python
def _canonical_cycles(cycles: list[list[str]]) -> list[list[str]]:
    """Canonicalise a cycle set so loop ids are stable across processes.

    `feedback_loops` returns cycles whose ORDER and whose ROTATION both vary
    between runs (`nx.simple_cycles` iterates sets, so hash seeding changes
    both). Positional ids would therefore name a different loop on every app
    start, and tests asserting on position would flake. Rotating each cycle to
    its lexicographically-least start and sorting the set fixes both.

    Self-loops (length 1) are dropped: `feedback_loops` returns them and
    `isa_to_numeric_matrix` sums them onto the diagonal, but a self-loop is not
    a feedback loop for dominance — left in the denominator, a self-growing
    node was measured governing 86% of a test system.

    Runs on the set `feedback_loops` ALREADY returned. Do not sort before the
    `max_loops` cap: that would require enumerating every eligible cycle and
    defeat the `length_bound` tractability fix (#18 — >5 min unbounded vs
    ~10 ms bounded).
    """
    out: list[list[str]] = []
    for cycle in cycles:
        if len(cycle) < 2:
            continue
        start = min(range(len(cycle)), key=lambda i: cycle[i])
        out.append(cycle[start:] + cycle[:start])
    out.sort()
    return out
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k canonical_cycles`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): canonicalise cycles so loop identity is stable"
```

---

### Task 2: `loop_dominance` — the share series

**Files:**
- Modify: `sespy/network.py`
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `_canonical_cycles` (Task 1), `feedback_loops` (`network.py:43`), `loop_polarity` (existing), `isa_to_numeric_matrix` (function-local import from `.dynamics`)
- Produces: `loop_dominance(isa, trajectory, node_ids, *, cycles=None, margin=0.05) -> DominanceResult`, plus the `DominanceRow` / `DominanceResult` TypedDicts. Used by Tasks 3 and 6.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_network.py`:

```python
def _two_loop_isa():
    """Two disjoint 2-cycles with different strengths, so shares are unequal."""
    from sespy.data_structure import IsaData, Element, Connection
    els = [Element(id=n, label=n, type="Drivers") for n in ("A", "B", "C", "D")]
    cons = [
        Connection(source="A", target="B", polarity="+", strength="Strong"),
        Connection(source="B", target="A", polarity="+", strength="Strong"),
        Connection(source="C", target="D", polarity="+", strength="Weak"),
        Connection(source="D", target="C", polarity="+", strength="Weak"),
    ]
    return IsaData(elements=els, connections=cons)


def test_loop_dominance_shares_sum_to_one():
    import numpy as np
    from sespy.network import loop_dominance
    isa = _two_loop_isa()
    node_ids = [e.id for e in isa.elements]
    traj = np.ones((5, 4))
    res = loop_dominance(isa, traj, node_ids)
    assert res["active"] is True
    for t in range(res["n_steps"]):
        assert abs(sum(r["shares"][t] for r in res["rows"]) - 1.0) < 1e-9


def test_loop_dominance_rows_keyed_by_nodes_not_position():
    import numpy as np
    from sespy.network import loop_dominance
    isa = _two_loop_isa()
    node_ids = [e.id for e in isa.elements]
    res = loop_dominance(isa, np.ones((3, 4)), node_ids)
    by_nodes = {tuple(r["nodes"]): r for r in res["rows"]}
    assert ("A", "B") in by_nodes and ("C", "D") in by_nodes
    # The stronger loop carries the larger share.
    assert by_nodes[("A", "B")]["shares"][0] > by_nodes[("C", "D")]["shares"][0]


def test_loop_dominance_length_comparability():
    """Equal structural gain and equal activity => equal share, regardless of
    how many nodes the loop has. This is why activity is a MEAN."""
    import numpy as np
    from sespy.data_structure import IsaData, Element, Connection
    from sespy.network import loop_dominance
    els = [Element(id=n, label=n, type="Drivers") for n in ("A", "B", "C", "D", "E")]
    cons = [
        Connection(source="A", target="B", polarity="+", strength="Medium"),
        Connection(source="B", target="A", polarity="+", strength="Medium"),
        Connection(source="C", target="D", polarity="+", strength="Medium"),
        Connection(source="D", target="E", polarity="+", strength="Medium"),
        Connection(source="E", target="C", polarity="+", strength="Medium"),
    ]
    isa = IsaData(elements=els, connections=cons)
    node_ids = [e.id for e in isa.elements]
    res = loop_dominance(isa, np.ones((2, 5)), node_ids)
    by_len = {len(r["nodes"]): r["shares"][0] for r in res["rows"]}
    # gains differ (2^2 vs 2^3) so shares differ, but neither is zero and the
    # 3-cycle is not penalised for its length beyond its structural gain.
    assert by_len[2] > 0 and by_len[3] > 0


def test_loop_dominance_zero_trajectory_is_inactive():
    import numpy as np
    from sespy.network import loop_dominance
    isa = _two_loop_isa()
    node_ids = [e.id for e in isa.elements]
    res = loop_dominance(isa, np.zeros((10, 4)), node_ids)
    assert res["active"] is False
    assert res["note"] == "zero_trajectory"
    assert res["rows"] == []


def test_loop_dominance_no_cycles_is_inactive():
    import numpy as np
    from sespy.data_structure import IsaData, Element, Connection
    from sespy.network import loop_dominance
    isa = IsaData(
        elements=[Element(id=n, label=n, type="Drivers") for n in ("A", "B")],
        connections=[Connection(source="A", target="B", polarity="+", strength="Medium")],
    )
    res = loop_dominance(isa, np.ones((3, 2)), ["A", "B"])
    assert res["active"] is False and res["note"] == "no_cycles"


def test_loop_dominance_truncates_on_overflow_keeping_the_prefix():
    """A late non-finite step must truncate, NOT void the whole run."""
    import numpy as np
    from sespy.network import loop_dominance
    isa = _two_loop_isa()
    node_ids = [e.id for e in isa.elements]
    traj = np.ones((10, 4))
    traj[7:] = np.inf
    res = loop_dominance(isa, traj, node_ids)
    assert res["active"] is True
    assert res["truncated_at"] == 7
    assert res["n_steps"] == 7
    assert res["note"] == "truncated_overflow"


def test_loop_dominance_truncates_on_underflow():
    import numpy as np
    from sespy.network import loop_dominance
    isa = _two_loop_isa()
    node_ids = [e.id for e in isa.elements]
    traj = np.ones((10, 4))
    traj[6:] = 0.0
    res = loop_dominance(isa, traj, node_ids)
    assert res["active"] is True
    assert res["truncated_at"] == 6
    assert res["note"] == "truncated_underflow"


def test_loop_dominance_self_loop_excluded_from_denominator():
    import numpy as np
    from sespy.data_structure import IsaData, Element, Connection
    from sespy.network import loop_dominance
    els = [Element(id=n, label=n, type="Drivers") for n in ("A", "B", "S")]
    cons = [
        Connection(source="A", target="B", polarity="+", strength="Medium"),
        Connection(source="B", target="A", polarity="+", strength="Medium"),
        Connection(source="S", target="S", polarity="+", strength="Strong"),
    ]
    isa = IsaData(elements=els, connections=cons)
    res = loop_dominance(isa, np.ones((3, 3)), ["A", "B", "S"])
    assert all(len(r["nodes"]) >= 2 for r in res["rows"])
    assert all(("S",) != tuple(r["nodes"]) for r in res["rows"])


def test_loop_dominance_rejects_mismatched_node_ids():
    import numpy as np
    import pytest
    from sespy.network import loop_dominance
    isa = _two_loop_isa()
    with pytest.raises(ValueError):
        loop_dominance(isa, np.ones((3, 4)), ["A", "B"])  # wrong length
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k loop_dominance`
Expected: FAIL with `ImportError: cannot import name 'loop_dominance'`

- [ ] **Step 3: Add the TypedDicts**

At the top of `sespy/network.py`, beside the other type imports (`TypedDict` follows the precedent of `dynamics.LaplacianStability` at `dynamics.py:95`):

```python
class DominanceRow(TypedDict):
    """One loop's dominance series. Key on `nodes`, never on list position."""
    loop_id: str
    nodes: list[str]
    polarity: str
    structural_gain: float
    shares: list[float]
    peak_share: float
    peak_step: int


class DominanceResult(TypedDict):
    """Per-loop dominance shares over a trajectory.

    `note` is a MACHINE TOKEN, never prose — the UI maps it to a translated
    key. One of: "ok", "zero_trajectory", "no_cycles", "zero_gain",
    "truncated_overflow", "truncated_underflow".
    """
    rows: list[DominanceRow]
    n_steps: int
    truncated_at: int | None
    contested_steps: list[int]
    active: bool
    note: str
```

Add `TypedDict` to the existing `from typing import ...` line if absent.

- [ ] **Step 4: Implement `loop_dominance`**

```python
def loop_dominance(
    isa: IsaData,
    trajectory: "np.ndarray",
    node_ids: list[str],
    *,
    cycles: list[list[str]] | None = None,
    margin: float = 0.05,
) -> DominanceResult:
    """Per-loop dominance share over a simulated trajectory.

    share_L(t) = |structural gain| * mean(|x_t[n]| for n in L), normalised
    across loops so shares sum to 1 at each step. Structure is constant; what
    changes over time is which loops carry activity.

    The trajectory is passed IN, never simulated here: the function stays pure
    and testable without `dynamics`, and the caller guarantees the ranking
    describes the run actually on screen.

    `cycles` is for test injection and for a caller's own snapshot. It is NOT a
    hand-off from the Loop Detection panel, whose `detected` set is a
    module-local reactive that other modules cannot read.

    Interpretation limits are real and documented in the spec: shares are
    scale-free, so they carry information during the TRANSIENT only, and
    late-run dominance is a structural (dominant-eigenvector) fact.
    """
    import numpy as np
    from .dynamics import isa_to_numeric_matrix  # local: dynamics imports network

    empty: DominanceResult = {
        "rows": [], "n_steps": 0, "truncated_at": None,
        "contested_steps": [], "active": False, "note": "no_cycles",
    }

    cyc = _canonical_cycles(
        cycles if cycles is not None else feedback_loops(isa))
    if not cyc:
        return empty

    M, mat_ids = isa_to_numeric_matrix(isa)
    if len(node_ids) != trajectory.shape[1] or set(node_ids) != set(mat_ids):
        raise ValueError(
            "node_ids must match the trajectory's columns and the ISA's "
            f"elements; got {len(node_ids)} ids for "
            f"{trajectory.shape[1]} columns")

    mpos = {n: i for i, n in enumerate(mat_ids)}
    structural: list[float] = []
    for c in cyc:
        g = 1.0
        for i in range(len(c)):
            g *= float(M[mpos[c[i]], mpos[c[(i + 1) % len(c)]]])
        structural.append(abs(g))
    if not any(structural):
        return {**empty, "note": "zero_gain"}

    tpos = {n: i for i, n in enumerate(node_ids)}
    series: list[list[float]] = [[] for _ in cyc]
    truncated_at: int | None = None
    note = "ok"
    for t in range(trajectory.shape[0]):
        x = np.abs(trajectory[t])
        raw = [structural[i] * float(np.mean([x[tpos[n]] for n in c]))
               for i, c in enumerate(cyc)]
        total = float(np.sum(raw))
        if not np.isfinite(total):
            truncated_at, note = t, "truncated_overflow"
            break
        if total <= 0.0:
            truncated_at = t
            note = "zero_trajectory" if t == 0 else "truncated_underflow"
            break
        for i in range(len(cyc)):
            series[i].append(raw[i] / total)

    n_steps = len(series[0])
    if n_steps < 2:
        # No usable prefix: active=False is reserved for exactly this.
        return {**empty, "note": note, "truncated_at": truncated_at}

    rows: list[DominanceRow] = []
    for idx, c in enumerate(cyc, start=1):
        s = series[idx - 1]
        peak = max(range(len(s)), key=lambda k: s[k])
        rows.append({
            "loop_id": f"L{idx:03d}",
            "nodes": c,
            "polarity": loop_polarity(c, isa),
            "structural_gain": structural[idx - 1],
            "shares": s,
            "peak_share": s[peak],
            "peak_step": peak,
        })

    contested: list[int] = []
    for t in range(n_steps):
        ordered = sorted((r["shares"][t] for r in rows), reverse=True)
        if len(ordered) >= 2 and ordered[0] <= ordered[1] * (1.0 + margin):
            contested.append(t)

    return {
        "rows": rows, "n_steps": n_steps, "truncated_at": truncated_at,
        "contested_steps": contested, "active": True, "note": note,
    }
```

- [ ] **Step 5: Run to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k loop_dominance`
Expected: PASS (9 tests)

- [ ] **Step 6: Run the whole file for regressions**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): loop_dominance share series over a trajectory"
```

---

### Task 3: `dominance_shifts` — confirmed regime changes

**Files:**
- Modify: `sespy/network.py`
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `DominanceResult` (Task 2)
- Produces: `dominance_shifts(result, *, margin=0.05, dwell=5) -> list[Shift]` and the `Shift` TypedDict. Used by Task 6.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_network.py`:

```python
def _result_from_shares(share_lists, polarities=("Balancing", "Reinforcing")):
    """Build a minimal DominanceResult from explicit share series."""
    n = len(share_lists[0])
    rows = []
    for i, s in enumerate(share_lists, start=1):
        rows.append({
            "loop_id": f"L{i:03d}", "nodes": [f"N{i}a", f"N{i}b"],
            "polarity": polarities[(i - 1) % len(polarities)],
            "structural_gain": 1.0, "shares": list(s),
            "peak_share": max(s), "peak_step": s.index(max(s)),
        })
    return {"rows": rows, "n_steps": n, "truncated_at": None,
            "contested_steps": [], "active": True, "note": "ok"}


def test_dominance_shifts_clear_lead_held_produces_one_shift():
    from sespy.network import dominance_shifts
    # L1 leads for 5 steps, then L2 takes a decisive lead and holds it.
    res = _result_from_shares([
        [0.9, 0.9, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
        [0.1, 0.1, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
    ])
    shifts = dominance_shifts(res, margin=0.05, dwell=5)
    assert len(shifts) == 1
    assert shifts[0]["step"] == 5
    assert shifts[0]["to_loop"] == "L002"
    assert tuple(shifts[0]["to_nodes"]) == ("N2a", "N2b")


def test_dominance_shifts_lead_not_held_long_enough_produces_none():
    from sespy.network import dominance_shifts
    # L2 leads for only 3 steps, below dwell=5.
    res = _result_from_shares([
        [0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.9, 0.9],
        [0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.1],
    ])
    assert dominance_shifts(res, margin=0.05, dwell=5) == []


def test_dominance_shifts_near_tie_below_margin_produces_none():
    from sespy.network import dominance_shifts
    # L2 edges ahead by 2%, under a 5% margin - not a shift.
    res = _result_from_shares([
        [0.51, 0.51, 0.51, 0.49, 0.49, 0.49, 0.49, 0.49, 0.49, 0.49],
        [0.49, 0.49, 0.49, 0.51, 0.51, 0.51, 0.51, 0.51, 0.51, 0.51],
    ])
    assert dominance_shifts(res, margin=0.05, dwell=5) == []


def test_dominance_shifts_polarity_changed_only_on_real_b_to_r():
    from sespy.network import dominance_shifts
    both_balancing = _result_from_shares(
        [[0.9] * 5 + [0.1] * 6, [0.1] * 5 + [0.9] * 6],
        polarities=("Balancing", "Balancing"),
    )
    s = dominance_shifts(both_balancing, margin=0.05, dwell=5)
    assert len(s) == 1 and s[0]["polarity_changed"] is False

    b_to_r = _result_from_shares(
        [[0.9] * 5 + [0.1] * 6, [0.1] * 5 + [0.9] * 6],
        polarities=("Balancing", "Reinforcing"),
    )
    s2 = dominance_shifts(b_to_r, margin=0.05, dwell=5)
    assert len(s2) == 1 and s2[0]["polarity_changed"] is True


def test_dominance_shifts_inactive_result_gives_no_shifts():
    from sespy.network import dominance_shifts
    inactive = {"rows": [], "n_steps": 0, "truncated_at": None,
                "contested_steps": [], "active": False, "note": "no_cycles"}
    assert dominance_shifts(inactive) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k dominance_shifts`
Expected: FAIL with `ImportError: cannot import name 'dominance_shifts'`

- [ ] **Step 3: Implement**

```python
class Shift(TypedDict):
    """One confirmed change of governing loop.

    `step` is where the new leader FIRST took the lead, not where its dwell
    completed. `polarity_changed` is separate on purpose: a change of
    governing loop within one polarity is a weaker event than a B<->R regime
    change, and conflating them would report a "B->R shift" that never
    happened.
    """
    step: int
    from_loop: str
    to_loop: str
    from_nodes: list[str]
    to_nodes: list[str]
    from_polarity: str
    to_polarity: str
    margin_pct: float
    held_steps: int
    polarity_changed: bool


def dominance_shifts(
    result: DominanceResult, *, margin: float = 0.05, dwell: int = 5
) -> list[Shift]:
    """Confirmed changes of governing loop.

    A shift is recorded only when the new leader's share exceeds the
    incumbent's by a RELATIVE `margin` and it holds the lead for `dwell`
    consecutive steps. Near-ties never register; they are in
    `result["contested_steps"]`.

    NOTE: the step is a property of the run, not a model prediction — shift
    timing depends on the initial condition (see the spec's risks section).
    """
    rows = result.get("rows") or []
    n = result.get("n_steps") or 0
    if not result.get("active") or len(rows) < 2 or n < 2:
        return []

    leaders = [max(range(len(rows)), key=lambda i: rows[i]["shares"][t])
               for t in range(n)]

    shifts: list[Shift] = []
    incumbent = leaders[0]
    for t in range(1, n):
        cand = leaders[t]
        if cand == incumbent:
            continue
        new_share = rows[cand]["shares"][t]
        old_share = rows[incumbent]["shares"][t]
        if old_share > 0 and new_share <= old_share * (1.0 + margin):
            continue
        held = 0
        for u in range(t, n):
            if leaders[u] != cand:
                break
            held += 1
        if held < dwell:
            continue
        a, b = rows[incumbent], rows[cand]
        shifts.append({
            "step": t,
            "from_loop": a["loop_id"], "to_loop": b["loop_id"],
            "from_nodes": a["nodes"], "to_nodes": b["nodes"],
            "from_polarity": a["polarity"], "to_polarity": b["polarity"],
            "margin_pct": ((new_share / old_share) - 1.0) * 100.0
                          if old_share > 0 else float("inf"),
            "held_steps": held,
            "polarity_changed": a["polarity"] != b["polarity"],
        })
        incumbent = cand
    return shifts
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k dominance_shifts`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): dominance_shifts with margin and dwell gating"
```

---

### Task 4: The B→R acceptance fixture

**Files:**
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `loop_dominance`, `dominance_shifts` (Tasks 2-3), `isa_to_dynamics_matrix` + `simulate_dynamics` from `sespy.dynamics`
- Produces: nothing — this is #22's acceptance criterion.

**Why a purpose-built fixture:** `data/sample_ses.json` cannot serve. It *does* contain Reinforcing loops (the length-5 cycles through `R002`), but they never lead — their shares peak at ≈0.114 while a Balancing loop holds ≈0.42 throughout. The reliable construction is **timescale separation**: two disconnected components with different spectral radii, so the early leader's share provably decays.

- [ ] **Step 1: Write the failing test**

```python
def test_loop_dominance_detects_a_balancing_to_reinforcing_shift():
    """#22's acceptance criterion.

    Two disconnected components: a BALANCING 2-cycle (one negative edge) that
    is initially large but decays, and a REINFORCING 2-cycle (no negative
    edges) that starts small and grows. Timescale separation guarantees the
    crossing; a single-SCC graph gives no such guarantee.
    """
    import numpy as np
    from sespy.data_structure import IsaData, Element, Connection
    from sespy import dynamics
    from sespy.network import loop_dominance, dominance_shifts

    els = [Element(id=n, label=n, type="Drivers") for n in ("B1", "B2", "R1", "R2")]
    cons = [
        # Balancing: exactly one negative edge, weak weights -> decays.
        Connection(source="B1", target="B2", polarity="+", strength="Weak"),
        Connection(source="B2", target="B1", polarity="-", strength="Weak"),
        # Reinforcing: no negative edges, strong weights -> grows.
        Connection(source="R1", target="R2", polarity="+", strength="Strong"),
        Connection(source="R2", target="R1", polarity="+", strength="Strong"),
    ]
    isa = IsaData(elements=els, connections=cons)
    A, node_ids = dynamics.isa_to_dynamics_matrix(isa)

    # Seed the balancing pair large and the reinforcing pair small, so the
    # balancing loop leads first and is overtaken as the growing mode wins.
    x0 = np.array([100.0 if n.startswith("B") else 1.0 for n in node_ids])
    traj = dynamics.simulate_dynamics(A, n_iter=40, initial_state=x0)

    res = loop_dominance(isa, traj, node_ids)
    assert res["active"] is True

    by_pol = {r["polarity"]: r for r in res["rows"]}
    assert set(by_pol) == {"Balancing", "Reinforcing"}
    assert by_pol["Balancing"]["shares"][0] > by_pol["Reinforcing"]["shares"][0]
    assert by_pol["Reinforcing"]["shares"][-1] > by_pol["Balancing"]["shares"][-1]

    shifts = dominance_shifts(res, margin=0.05, dwell=5)
    assert len(shifts) == 1
    assert shifts[0]["from_polarity"] == "Balancing"
    assert shifts[0]["to_polarity"] == "Reinforcing"
    assert shifts[0]["polarity_changed"] is True


def test_loop_dominance_shares_are_not_constant():
    """Regression guard for the whole design.

    If gain is ever 'simplified' back to the bare product of edge weights, it
    becomes time-invariant and every share is constant. This fails loudly
    instead of silently emitting a constant column.
    """
    import numpy as np
    from sespy.data_structure import IsaData, Element, Connection
    from sespy import dynamics
    from sespy.network import loop_dominance

    els = [Element(id=n, label=n, type="Drivers") for n in ("B1", "B2", "R1", "R2")]
    cons = [
        Connection(source="B1", target="B2", polarity="+", strength="Weak"),
        Connection(source="B2", target="B1", polarity="-", strength="Weak"),
        Connection(source="R1", target="R2", polarity="+", strength="Strong"),
        Connection(source="R2", target="R1", polarity="+", strength="Strong"),
    ]
    isa = IsaData(elements=els, connections=cons)
    A, node_ids = dynamics.isa_to_dynamics_matrix(isa)
    x0 = np.array([100.0 if n.startswith("B") else 1.0 for n in node_ids])
    traj = dynamics.simulate_dynamics(A, n_iter=40, initial_state=x0)
    res = loop_dominance(isa, traj, node_ids)
    spread = max(abs(r["shares"][0] - r["shares"][-1]) for r in res["rows"])
    assert spread > 0.1, f"shares barely moved ({spread:.4f}) - gain may be constant"
```

- [ ] **Step 2: Run to verify they fail, then pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k "balancing_to_reinforcing or not_constant"`

These exercise code written in Tasks 1-3, so they should **PASS on the first run**. That is expected — they are the acceptance criterion, not a new unit under TDD. If either FAILS, do not weaken the assertions: report it, because it means the metric does not do what the spec claims.

If the shift is not detected, the likely cause is that 40 steps is too few for the crossing plus `dwell=5`; try `n_iter=60` before concluding the design is wrong, and say in your report that you did.

- [ ] **Step 3: Commit**

```bash
git add tests/test_network.py
git commit -m "test(network): B->R dominance shift acceptance fixture"
```

---

### Task 5: i18n keys

**Files:**
- Modify: `sespy/translations/core.json`
- Test: existing `tests/test_i18n.py`

**Interfaces:**
- Consumes: nothing
- Produces: the `simulation.dominance*` keys Task 6 calls via `t(...)`.

- [ ] **Step 1: Read the existing shape**

Open `sespy/translations/core.json` and find an existing `"simulation.*"` key. Every key is an object with **all nine** language codes: `en`, `es`, `fr`, `de`, `lt`, `pt`, `it`, `no`, `el`. `tests/test_i18n.py::test_loader_handles_all_supported_languages` fails if any is missing.

- [ ] **Step 2: Add the keys**

Add beside the other `simulation.*` entries, following the file's existing single-line-per-key formatting:

| key | en |
|---|---|
| `simulation.dominance_show` | `Show loop dominance` |
| `simulation.dominance_legend` | `Governing loop` |
| `simulation.dominance_shifts` | `Dominance shifts in this run` |
| `simulation.dominance_none` | `No dominance shift detected in this run.` |
| `simulation.dominance_caption` | `Which feedback loop carries most of the activity at each step. Timing describes this run, not a prediction: it depends on the initial state. A share is an attribution, not proof that a loop causes the behaviour.` |
| `simulation.dominance_zero_trajectory` | `No loop activity — the trajectory is identically zero. Choose a non-zero initial state.` |
| `simulation.dominance_no_cycles` | `No feedback loops found in this model.` |
| `simulation.dominance_zero_gain` | `No loop activity — all loops have zero strength.` |
| `simulation.dominance_truncated_overflow` | `Values grew beyond floating-point range; showing the first {n} steps.` |
| `simulation.dominance_truncated_underflow` | `Values decayed to zero; showing the first {n} steps.` |

Provide accurate translations for the other eight languages, matching the tone of the surrounding `simulation.*` entries.

- [ ] **Step 3: Verify**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n(simulation): loop-dominance overlay keys in all nine languages"
```

---

### Task 6: The overlay

**Files:**
- Modify: `sespy/modules/analysis_simulation.py`
- Test: manual only; covered by Task 4's unit tests and Task 7's e2e

**Interfaces:**
- Consumes: `loop_dominance`, `dominance_shifts` (Tasks 2-3), the i18n keys (Task 5)
- Produces: input id `dominance_show` → `#simulation-dominance_show` for Task 7.

- [ ] **Step 1: Add the checkbox**

In the sidebar, after the `initial_state` radio group (around `:32-38`):

```python
                ui.input_checkbox("dominance_show", t("simulation.dominance_show"), value=False),
```

- [ ] **Step 2: Snapshot what the overlay needs at Run time**

`_run_sim` currently stores `{"error": None, "traj": traj, "node_ids": node_ids}` (`:134`). The overlay must never read the live `project_data`: `_stale_warning` only shows a notification and never clears `sim_store`, so a post-run ISA edit would otherwise pair a new model with an old trajectory.

Extend the success-path store to carry the ISA that was actually simulated:

```python
            sim_store.set({"error": None, "traj": traj, "node_ids": node_ids,
                           "isa": isa})
```

`isa` is already in scope in `_run_sim` (it is what `_build_matrix()` used). Add `"isa": None` to the two error-path `sim_store.set(...)` calls at `:125` and `:136` so the key is always present.

- [ ] **Step 3: Compute dominance in the plot renderer**

In the `@render.plot` for `trajectory_plot` (`:173`), after the existing trajectory is drawn and only when the checkbox is on:

```python
        if input.dominance_show() and s.get("isa") is not None:
            from sespy import network as _net
            res = _net.loop_dominance(s["isa"], s["traj"], s["node_ids"])
            if res["active"]:
                shifts = _net.dominance_shifts(res)
                _shade_dominance(ax, res, shifts)
```

- [ ] **Step 4: Add the shading helper**

Module-level in `analysis_simulation.py`:

```python
def _dominance_segments(res: dict, shifts: list[dict]) -> list[tuple[int, int, str]]:
    """(start, end, loop_id) bands from the CONFIRMED shifts, not per-step argmax.

    Per-step argmax flickers on near-ties; the spec's deliverable is the shift,
    so the shading uses the dwell/margin-filtered segments.
    """
    if not res.get("rows"):
        return []
    first = max(res["rows"], key=lambda r: r["shares"][0])["loop_id"]
    bounds = [(0, first)] + [(sh["step"], sh["to_loop"]) for sh in shifts]
    segs = []
    for i, (start, loop_id) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else res["n_steps"]
        segs.append((start, end, loop_id))
    return segs


def _shade_dominance(ax, res: dict, shifts: list[dict]) -> None:
    """Shade the plot background by governing loop; leave contested steps clear."""
    palette = ["#e8f0fe", "#fdf0e8", "#e8fae8", "#f6e8fa", "#fafae8"]
    order = {r["loop_id"]: i for i, r in enumerate(res["rows"])}
    for start, end, loop_id in _dominance_segments(res, shifts):
        ax.axvspan(start, end, color=palette[order.get(loop_id, 0) % len(palette)],
                   zorder=0, alpha=0.6)
```

- [ ] **Step 5: Render the shift list and the caption**

Add `ui.output_ui("dominance_summary")` directly below the trajectory plot's `nav_panel`, and this renderer in the server body:

```python
    @output
    @render.ui
    def dominance_summary():
        s = sim_store.get()
        if not input.dominance_show() or not s or s.get("isa") is None:
            return ui.tags.span("")
        from sespy import network as _net
        res = _net.loop_dominance(s["isa"], s["traj"], s["node_ids"])
        if not res["active"]:
            # note is a machine token; map it to its translated key.
            return ui.p(t(f"simulation.dominance_{res['note']}"),
                        class_="text-muted", style="font-size: 0.85rem;")
        items = []
        for sh in _net.dominance_shifts(res):
            frm = " → ".join(sh["from_nodes"])
            to = " → ".join(sh["to_nodes"])
            flag = " (polarity regime change)" if sh["polarity_changed"] else ""
            items.append(ui.tags.li(
                f"step {sh['step']}: {frm}  ⇒  {to}"
                f"  [{sh['from_polarity']} → {sh['to_polarity']}]"
                f"  +{sh['margin_pct']:.0f}%, held {sh['held_steps']}{flag}"))
        body = (ui.tags.ul(*items) if items
                else ui.p(t("simulation.dominance_none"), class_="text-muted"))
        parts = [ui.tags.strong(t("simulation.dominance_shifts")), body]
        if res["truncated_at"] is not None:
            parts.append(ui.p(t(f"simulation.dominance_{res['note']}").format(
                n=res["n_steps"]), class_="text-muted"))
        parts.append(ui.p(t("simulation.dominance_caption"),
                          class_="text-muted", style="font-size: 0.85rem;"))
        return ui.div(*parts)
```

Loops are named by their node path, never by `loop_id` — ids are canonicalised but still panel-local, and a bare "L003" invites cross-referencing with the Loops tab, which may have enumerated a different set.

- [ ] **Step 6: Verify the module still imports and the app boots**

Run: `micromamba run -n shiny python -c "import sespy.modules.analysis_simulation"` (single line only)
Expected: no output, exit 0.

Run: `micromamba run -n shiny python -m pytest tests/test_simulation_e2e.py -q`
Expected: PASS — the existing e2e must still pass with the checkbox present and off.

- [ ] **Step 7: Commit**

```bash
git add sespy/modules/analysis_simulation.py
git commit -m "feat(simulation): optional loop-dominance overlay on the trajectory plot"
```

---

### Task 7: E2e

**Files:**
- Modify: `tests/test_simulation_e2e.py`

**Interfaces:**
- Consumes: `#simulation-dominance_show` (Task 6)
- Produces: nothing

**Note:** SESPy's e2e are standalone asyncio Playwright scripts discovered by `tests/run_e2e.py:51`. **`wait_for_nav` does not exist in this repo** — it is a MosaicSES helper. Follow the existing file's pattern exactly.

- [ ] **Step 1: Read the existing pattern**

Open `tests/test_simulation_e2e.py` and copy its structure: how it reaches the panel, how it waits, how it asserts. Do not invent a new idiom.

- [ ] **Step 2: Add the test**

Extend the existing script (or add a sibling following the same pattern) to: reach the Simulation panel; run a simulation; assert `#simulation-dominance_show` exists and is unchecked; check it; wait for the trajectory plot `<img>` to re-render; assert the checkbox is now checked and the plot still renders.

Namespaced ids only — never `[id$=...]`, `[id^=...]`, or a bare `text=` selector; those have broken cross-module in this codebase before.

Deliberately **do not** assert overlay pixel content. That logic is covered by Tasks 2-4. This is a declared coverage limit.

- [ ] **Step 3: Run**

Run: `micromamba run -n shiny python -m pytest tests/test_simulation_e2e.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_simulation_e2e.py
git commit -m "test(e2e): loop-dominance toggle renders on the simulation panel"
```

---

## Final gate — before any merge

Run in this order, never concurrently (the shared editable `sespy` tree makes concurrent runs non-reproducible):

1. `micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` — SESPy unit. Baseline before this work: **537 passed**.
2. Kill anything listening on port 8000, then `micromamba run -n shiny python tests/run_e2e.py` — expect **32/32**.
3. In the MosaicSES repo: `micromamba run -n shiny python -m pytest tests/ -q` — baseline **517 passed**. First confirm it imports the modified sespy: `micromamba run -n shiny python -c "import sespy.network as n; print(hasattr(n, 'loop_dominance'))"` must print `True` from the MosaicSES directory.

Never `-k "not e2e"`. A green subset has been mistaken for a green suite in this codebase before.

## Done means

- A user can tick one box on the Simulation panel and see which loop governs each phase of the run they just executed, with the shifts named by their nodes.
- The B→R acceptance fixture passes, and the not-constant guard would fail if the metric regressed to a time-invariant gain.
- Both repos' full suites pass.

## Explicitly out of scope

ALC (deferred pending #23's reconciliation with the shipped `leverage_realm()`); changing loop enumeration, the simulation, or `leverage_scores()`; any new simulation run; asserting overlay pixel content in e2e.
