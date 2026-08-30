"""Network analysis — minimal port of functions/network_analysis.R.

The R version uses igraph throughout. networkx is used here for the POC to
avoid a package install; swap to python-igraph in production for bit-for-bit
parity with R (both bind the same C `libigraph`).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import logging
from typing import TypedDict

import networkx as nx

from .data_structure import Connection, IsaData

logger = logging.getLogger(__name__)


def to_digraph(isa: IsaData) -> nx.DiGraph:
    g = nx.DiGraph()
    for el in isa.elements:
        g.add_node(el.id, label=el.label, type=el.type)
    for c in isa.connections:
        g.add_edge(c.source, c.target, polarity=c.polarity, strength=c.strength)
    return g


def basic_metrics(isa: IsaData) -> dict[str, int | float]:
    g = to_digraph(isa)
    n = g.number_of_nodes()
    m = g.number_of_edges()
    density = nx.density(g) if n > 1 else 0.0
    return {
        "nodes": n,
        "edges": m,
        "density": round(density, 4),
        "weakly_connected_components": nx.number_weakly_connected_components(g),
    }


def feedback_loops(
    isa: IsaData, *, max_length: int = 6, max_loops: int = 50
) -> list[list[str]]:
    """Return up to `max_loops` simple cycles, capped at `max_length` nodes.

    Mirrors the adaptive-limit logic in functions/network_analysis.R, which
    limits length+count for large graphs to keep loop enumeration tractable.

    `length_bound` (networkx >= 3.1) makes the ENUMERATION itself respect
    max_length: the previous filter-after-generate skipped long cycles but
    still generated them, which is exponential on dense graphs (issue #18 —
    a 40-node p=0.25 digraph ran >5 min unbounded vs ~10 ms bounded).
    Verified identical loop sets AND order on every shipped fixture. Caveat:
    the bounded path uses a different enumeration algorithm (Gupta-Suzumura
    vs Johnson) with no documented ordering guarantee, so on a graph with
    MORE than max_loops eligible cycles the truncated subset could in
    principle differ from the pre-3.1 behavior (none observed in fuzzing).
    """
    g = to_digraph(isa)
    cycles: list[list[str]] = []
    for cycle in nx.simple_cycles(g, length_bound=max_length):
        cycles.append(cycle)
        if len(cycles) >= max_loops:
            break
    return cycles


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


def _edge_polarity_lookup(isa: IsaData) -> dict[tuple[str, str], str]:
    return {(c.source, c.target): c.polarity for c in isa.connections}


def _edge_delay_lookup(isa: IsaData) -> dict[tuple[str, str], str]:
    from .constants import normalize_delay
    return {(c.source, c.target): normalize_delay(c.delay) for c in isa.connections}


def loop_has_delay(cycle: list[str], isa: IsaData) -> bool:
    """True if any edge traversed by `cycle` is delayed
    (normalize_delay(delay) != 'immediate'). Walks (cycle[i], cycle[(i+1)%n])
    like loop_polarity; last-wins on parallel (source,target) edges (the UI
    blocks duplicate edges; only Excel / hand-edited JSON can create them)."""
    lookup = _edge_delay_lookup(isa)
    n = len(cycle)
    return any(
        lookup.get((cycle[i], cycle[(i + 1) % n]), "immediate") != "immediate"
        for i in range(n)
    )


def loop_polarity(cycle: list[str], isa: IsaData) -> str:
    """Classify a cycle as 'Reinforcing' or 'Balancing'.

    Faithful port of classify_loop_type() in functions/network_analysis.R:842 —
    even number of negative edges → Reinforcing, odd → Balancing.
    """
    lookup = _edge_polarity_lookup(isa)
    n = len(cycle)
    n_negative = sum(
        1
        for i in range(n)
        if lookup.get((cycle[i], cycle[(i + 1) % n])) == "-"
    )
    return "Reinforcing" if n_negative % 2 == 0 else "Balancing"


def loop_polarity_contested(cycle: list[str], isa: IsaData) -> bool:
    """True if any directed edge of the cycle is rater-polarity-contested.

    Mirrors loop_polarity's edge iteration (consecutive pairs, wrap-around), so
    the flagged edges are exactly those that determine the loop classification.
    Pure; False for loops whose edges have <2 ratings."""
    conn_by_pair = {(c.source, c.target): c for c in isa.connections}
    n = len(cycle)
    for i in range(n):
        c = conn_by_pair.get((cycle[i], cycle[(i + 1) % n]))
        if c is not None and connection_disagreement(c)["polarity_contested"]:
            return True
    return False


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

    A shift is recorded only when a maximal run of the raw (per-step argmax)
    leader is at least `dwell` steps long AND, measured at the END of that
    dwell window, the candidate's share exceeds the incumbent's by a RELATIVE
    `margin`. `step` is the FIRST step of the run — the crossing — not the
    step the dwell window closed or the margin cleared; on smooth data those
    can differ from the crossing, and conflating them would misreport when a
    user actually saw the new loop take the lead. `held_steps` is the full
    run length. Near-ties never register; they are in
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

    # Maximal runs of a constant raw leader: (leader_id, run_start, run_length).
    runs: list[tuple[int, int, int]] = []
    t0 = 0
    for t in range(1, n + 1):
        if t == n or leaders[t] != leaders[t0]:
            runs.append((leaders[t0], t0, t - t0))
            t0 = t

    shifts: list[Shift] = []
    incumbent = leaders[0]
    for cand, t0, length in runs:
        if cand == incumbent:
            continue
        if length < dwell:
            continue
        check_idx = t0 + dwell - 1
        new_share = rows[cand]["shares"][check_idx]
        old_share = rows[incumbent]["shares"][check_idx]
        if old_share > 0 and new_share <= old_share * (1.0 + margin):
            continue
        a, b = rows[incumbent], rows[cand]
        shifts.append({
            "step": t0,
            "from_loop": a["loop_id"], "to_loop": b["loop_id"],
            "from_nodes": a["nodes"], "to_nodes": b["nodes"],
            "from_polarity": a["polarity"], "to_polarity": b["polarity"],
            "margin_pct": ((new_share / old_share) - 1.0) * 100.0
                          if old_share > 0 else float("inf"),
            "held_steps": length,
            "polarity_changed": a["polarity"] != b["polarity"],
        })
        incumbent = cand
    return shifts


# ---------------------------------------------------------------------------
# Centrality metrics — port of functions/network_analysis.R::calculate_metrics
# (seven per-node centrality measures used in modules/analysis_metrics.R).
# Each returns a {node_id: float} dict for one metric.
# ---------------------------------------------------------------------------

CENTRALITY_METRICS: tuple[str, ...] = (
    "degree", "indegree", "outdegree",
    "betweenness", "closeness", "eigenvector", "pagerank",
)


def _safe_floats(d: dict[str, float]) -> dict[str, float]:
    """Replace inf/nan with 0.0 — closeness on disconnected graphs returns
    inf for unreachable nodes, eigenvector can return nan on degenerate
    structures. Mirrors the R guards at network_analysis.R:57-61, 73-76."""
    import math

    return {
        k: (0.0 if v is None or math.isnan(v) or math.isinf(v) else float(v))
        for k, v in d.items()
    }


def centrality_metrics(isa: IsaData) -> dict[str, dict[str, float]]:
    """Compute all seven centrality metrics for every node in `isa`.

    Returns a dict keyed by metric name; each value is a `{node_id: float}`
    map. Empty graphs and isolated-node cases return zeros, never raise.
    """
    g = to_digraph(isa)
    if g.number_of_nodes() == 0:
        return {m: {} for m in CENTRALITY_METRICS}

    degrees: dict[str, dict[str, float]] = {
        "degree":    {n: float(g.degree(n))    for n in g.nodes()},
        "indegree":  {n: float(g.in_degree(n)) for n in g.nodes()},
        "outdegree": {n: float(g.out_degree(n)) for n in g.nodes()},
    }

    try:
        betweenness = nx.betweenness_centrality(g, normalized=True)
    except Exception as e:
        logger.warning("network.centrality metric=betweenness status=fallback reason=%s", type(e).__name__)
        betweenness = {n: 0.0 for n in g.nodes()}

    try:
        closeness = nx.closeness_centrality(g)
    except Exception as e:
        logger.warning("network.centrality metric=closeness status=fallback reason=%s", type(e).__name__)
        closeness = {n: 0.0 for n in g.nodes()}

    try:
        eigenvector = nx.eigenvector_centrality_numpy(g, max_iter=200)
    except Exception as e:
        logger.warning("network.centrality metric=eigenvector_numpy status=fallback reason=%s", type(e).__name__)
        # Fallback for graphs where the numpy solver is unhappy
        try:
            eigenvector = nx.eigenvector_centrality(g, max_iter=500)
        except Exception as e2:
            logger.warning("network.centrality metric=eigenvector status=fallback_zero reason=%s", type(e2).__name__)
            eigenvector = {n: 0.0 for n in g.nodes()}

    try:
        pagerank = nx.pagerank(g, alpha=0.85)
    except Exception as e:
        logger.warning("network.centrality metric=pagerank status=fallback reason=%s", type(e).__name__)
        pagerank = {n: 0.0 for n in g.nodes()}

    return {
        **degrees,
        "betweenness": _safe_floats(betweenness),
        "closeness":   _safe_floats(closeness),
        "eigenvector": _safe_floats(eigenvector),
        "pagerank":    _safe_floats(pagerank),
    }


def _zscore(values: dict[str, float]) -> dict[str, float]:
    """Standardise to mean 0, std 1. Returns zeros if std is 0 or negligibly
    small relative to the mean (guards against floating-point noise in
    near-uniform centrality vectors amplifying to spuriously large z-scores)."""
    if not values:
        return {}
    vs = list(values.values())
    mean = sum(vs) / len(vs)
    var = sum((v - mean) ** 2 for v in vs) / len(vs)
    std = var ** 0.5
    scale = abs(mean) if mean != 0 else 1.0
    if std == 0 or std / scale < 1e-10:
        return {k: 0.0 for k in values}
    return {k: (v - mean) / std for k, v in values.items()}


def leverage_scores(isa: IsaData) -> dict[str, float]:
    """Composite leverage score per node — z-score(betweenness) +
    z-score(eigenvector) + z-score(pagerank). Higher = more leverage.

    Mirrors functions/network_analysis.R:1390-1392.

    governance_actor_influence() re-derives this same composite per governance
    actor — if this formula changes, change it there too (a golden test pins
    their equality on the sample data).
    """
    m = centrality_metrics(isa)
    bz = _zscore(m["betweenness"])
    ez = _zscore(m["eigenvector"])
    pz = _zscore(m["pagerank"])
    return {nid: bz.get(nid, 0.0) + ez.get(nid, 0.0) + pz.get(nid, 0.0)
            for nid in m["betweenness"]}


def governance_actor_influence(isa: IsaData) -> list[dict]:
    """Per-governance-actor influence within the WHOLE network — the
    power-asymmetry diagnostic of Maritime Studies 2026
    (doi:10.1007/s40152-026-00501-z): dominant vs. peripheral governance
    actors in co-management.

    One row per element whose type is in _GOVERNANCE ("Measures" is
    forward-looking — unreachable through today's ingresses). Rows carry the
    RAW betweenness/eigenvector/pagerank centralities (readable values) plus
    `influence`, the whole-network z-score composite — equal by construction
    to leverage_scores() for the same node: one definition, two views.
    Centralities are computed on the full graph so cross-boundary influence
    counts; z-scores are standardised over ALL nodes so an actor's score
    reads "influence relative to the whole system" and is stable under
    changes to the governance subset. Sorted by influence descending, ties
    in isa.elements order (list.sort is stable). Degenerate inputs return
    []; values are finite (inherited _safe_floats/_zscore guards). Pure.
    """
    governance = [el for el in isa.elements if el.type in _GOVERNANCE]
    if not governance:
        return []
    m = centrality_metrics(isa)
    bz = _zscore(m["betweenness"])
    ez = _zscore(m["eigenvector"])
    pz = _zscore(m["pagerank"])
    rows = [
        {
            "id": el.id,
            "label": el.label,
            "type": el.type,
            "betweenness": m["betweenness"].get(el.id, 0.0),
            "eigenvector": m["eigenvector"].get(el.id, 0.0),
            "pagerank": m["pagerank"].get(el.id, 0.0),
            "influence": (bz.get(el.id, 0.0) + ez.get(el.id, 0.0)
                          + pz.get(el.id, 0.0)),
        }
        for el in governance
    ]
    rows.sort(key=lambda r: -r["influence"])
    return rows


def cascade_vulnerability(
    isa: IsaData, *, max_steps: int = 20, max_length: int = 6, max_loops: int = 50
) -> dict:
    """Sequential-removal cascade diagnostic — ERL 2026
    (doi:10.1088/1748-9326/ae83cb): remove nodes in descending
    leverage_scores() order and track, after each removal, the largest
    weakly-connected-component fraction (lccf; denominator = ORIGINAL
    node count) and the surviving feedback-loop count. The cascade
    threshold node is the removal causing the largest single-step lccf
    drop (earliest step wins ties) — a nonlinearity that per-node
    centrality cannot reveal.

    Loop counts reuse feedback_loops() unmodified (same max_length /
    max_loops caps), which takes IsaData — hence each step builds a
    reduced IsaData (surviving elements, connections whose both
    endpoints survive) instead of mutating a graph. The step cap is
    never silent: n_ranked and max_steps are returned and steps holds
    exactly min(n_ranked, max_steps) rows. Fewer than 3 elements
    returns the trivial shape with cascade_threshold_node None (never
    raises). Pure; deterministic (leverage ties break in isa.elements
    order); no NaN.
    """
    if len(isa.elements) < 3:
        return {"baseline": {"lccf": 0.0, "loop_count": 0}, "steps": [],
                "cascade_threshold_node": None, "n_ranked": 0,
                "max_steps": max_steps}

    n_original = len(isa.elements)

    def _lccf(model: IsaData) -> float:
        if not model.elements:
            return 0.0
        g = to_digraph(model)
        return max(len(c) for c in nx.weakly_connected_components(g)) / n_original

    lev = leverage_scores(isa)
    order = {el.id: i for i, el in enumerate(isa.elements)}
    ranked = sorted(isa.elements, key=lambda el: (-lev[el.id], order[el.id]))

    baseline = {
        "lccf": _lccf(isa),
        "loop_count": len(feedback_loops(
            isa, max_length=max_length, max_loops=max_loops)),
    }

    steps: list[dict] = []
    survivors = list(isa.elements)
    prev = baseline["lccf"]
    for step, victim in enumerate(ranked[:max_steps], start=1):
        survivors = [el for el in survivors if el.id != victim.id]
        ids = {el.id for el in survivors}
        reduced = IsaData(
            elements=survivors,
            connections=[c for c in isa.connections
                         if c.source in ids and c.target in ids],
        )
        cur = _lccf(reduced)
        steps.append({
            "step": step,
            "removed_id": victim.id,
            "removed_label": victim.label,
            "lccf": cur,
            "loop_count": len(feedback_loops(
                reduced, max_length=max_length, max_loops=max_loops)),
            "delta_lccf": prev - cur,
        })
        prev = cur

    threshold = max(steps, key=lambda r: r["delta_lccf"])["removed_id"]
    return {"baseline": baseline, "steps": steps,
            "cascade_threshold_node": threshold,
            "n_ranked": n_original, "max_steps": max_steps}


def causal_paths(
    isa: IsaData, source: str, target: str,
    *, max_length: int = 8, max_paths: int = 100,
) -> dict:
    """Directed causal-chain enumeration with compound-polarity sign
    arithmetic — the static explainability layer of Applied Soft Computing
    2026 (doi:10.1016/j.asoc.2026.115925): "how does A influence B?".

    Enumerates simple directed paths source→target (nx.all_simple_paths;
    cutoff counts EDGES, so max_length bounds path length and prevents
    combinatorial explosion on dense CLDs). Each row carries the node-id
    path, its edge count, and the compound polarity: "-" for an odd number
    of "-" hops, "+" otherwise, and "0" when any hop's polarity is neither
    "+" nor "-" (forward-looking — every current ingress emits only +/-).
    Parallel (source, target) edges deduplicate last-wins, matching
    _axis_sums; self-loops and dangling refs are skipped. Collection stops
    at max_paths with an honest truncated flag (never a silent cap). Rows
    sort (length, path) — deterministic. Unknown endpoints, source ==
    target, or no route return the empty shape; never raises. Pure.
    """
    empty = {"paths": [], "counts": {"+": 0, "-": 0, "0": 0},
             "truncated": False}
    ids = {el.id for el in isa.elements}
    if source not in ids or target not in ids or source == target:
        return empty

    pol: dict[tuple[str, str], str] = {}
    for c in isa.connections:
        if c.source == c.target or c.source not in ids or c.target not in ids:
            continue
        pol[(c.source, c.target)] = c.polarity
    g = nx.DiGraph()
    g.add_nodes_from(ids)
    g.add_edges_from(pol)

    # Prune to nodes that can lie on a source->target path: every simple
    # path uses only descendants(source) ∩ ancestors(target). Two BFS,
    # O(V+E) — makes the no-route case instant and collapses dead-end
    # exploration on dense models (the #18 hang class). Results identical.
    relevant = (nx.descendants(g, source) & nx.ancestors(g, target)) | {source, target}
    if target not in nx.descendants(g, source) | {source}:
        return empty
    g = g.subgraph(relevant)

    rows: list[dict] = []
    truncated = False
    for p in nx.all_simple_paths(g, source, target, cutoff=max_length):
        if len(rows) >= max_paths:
            truncated = True
            break
        negatives = 0
        ambiguous = False
        for a, b in zip(p, p[1:]):
            sign = pol[(a, b)]
            if sign == "-":
                negatives += 1
            elif sign != "+":
                ambiguous = True
        rows.append({
            "path": list(p),
            "length": len(p) - 1,
            "polarity": "0" if ambiguous else ("-" if negatives % 2 else "+"),
        })
    rows.sort(key=lambda r: (r["length"], r["path"]))

    counts = {"+": 0, "-": 0, "0": 0}
    for r in rows:
        counts[r["polarity"]] += 1
    return {"paths": rows, "counts": counts, "truncated": truncated}


_DAPSIWRM_REALM: dict[str, str] = {
    "Pressures": "parameters",
    "Ecosystem Services": "parameters",
    "Goods & Benefits": "parameters",
    "Marine Processes & Functioning": "feedbacks",
    "Activities": "design",
    "Responses": "design",
    "Drivers": "intent",
}


def leverage_realm(element_type: str) -> str:
    """Meadows-realm token for a DAPSIWRM element type — one of
    'parameters' | 'feedbacks' | 'design' | 'intent', or '' for an unknown type
    (incl. 'Measures', an accepted gap). Pure; translation-free."""
    return _DAPSIWRM_REALM.get(element_type, "")


_SUBSYSTEM: dict[str, str] = {
    "Drivers": "social",
    "Activities": "social",
    "Responses": "social",
    "Goods & Benefits": "social",
    "Pressures": "ecological",
    "Marine Processes & Functioning": "ecological",
    "Ecosystem Services": "ecological",
}


def subsystem(element_type: str) -> str:
    """'social' | 'ecological' | '' (unknown type, e.g. 'Measures'). Pure."""
    return _SUBSYSTEM.get(element_type, "")


def social_ecological_fit(isa) -> dict:
    """Graph-level social↔ecological coupling. fit = cross / total edges.

    Each element classified via subsystem(); over connections (self-loops and
    dangling refs skipped, edges touching an unclassified node excluded), count
    edges within-social, within-ecological, and crossing the boundary. Pure.
    Duplicate (source,target) edges are forbidden by the data-entry layer, so
    each valid connection is counted once. n_other distinguishes a pure-
    unclassified graph (total 0, but has connections) from a genuinely empty one.
    """
    sub_by_id: dict[str, str] = {}
    n_social = n_ecological = n_other = 0
    for el in isa.elements:
        s = subsystem(el.type)
        sub_by_id[el.id] = s
        if s == "social":
            n_social += 1
        elif s == "ecological":
            n_ecological += 1
        else:
            n_other += 1

    within_social = within_ecological = cross = 0
    for c in isa.connections:
        if c.source == c.target or c.source not in sub_by_id or c.target not in sub_by_id:
            continue
        a, b = sub_by_id[c.source], sub_by_id[c.target]
        if a == "" or b == "":
            continue
        if a != b:
            cross += 1
        elif a == "social":
            within_social += 1
        else:
            within_ecological += 1

    total = within_social + within_ecological + cross
    return {
        "n_social": n_social,
        "n_ecological": n_ecological,
        "n_other": n_other,
        "within_social_edges": within_social,
        "within_ecological_edges": within_ecological,
        "cross_edges": cross,
        "total_edges": total,
        "fit": (cross / total) if total else 0.0,
    }


_GOVERNANCE: frozenset[str] = frozenset({"Responses", "Measures"})


def governance_gap(isa: IsaData) -> dict:
    """SENA governance-gap diagnostic — directed coverage of the ecological
    subsystem by governance elements.

    Coverage is DIRECTED: an ecological node counts as covered when at least
    one governance node has an out-edge to it. The headline
    ``pressure_gap_fraction`` uses Pressures alone as denominator — the only
    ecological layer the DAPSI(W)R(M) topology (``_CONN_TYPES``) routes a
    Response into; Marine Processes & Functioning and Ecosystem Services are
    unreachable at distance 1 by construction, so their coverage is reported
    per-type in ``gaps_by_type`` rather than pooled into the headline. A
    governance *orphan* is a governance node with no directed PATH to any
    ecological node, so a Response acting through Drivers/Activities (the
    highest-leverage "intent" realm per ``leverage_realm``) is not an orphan.

    Degenerate denominators return 0.0, never NaN; callers discriminate via
    the ``n_*`` counts (same contract as ``social_ecological_fit`` and
    ``total_edges``). ``n_edges_considered`` counts unique directed
    (source, target) pairs after dropping self-loops and dangling refs —
    edges touching untyped nodes included. "Measures" in the governance set
    is forward-looking: ``persistent_storage`` rejects it and no UI offers
    it today. Duplicate element ids (possible only via the validation-free
    ``load_sample``) can overcount — parity with ``social_ecological_fit``.

    Concept: Fraga et al. 2026, Marine Policy 191:107169
    (doi:10.1016/j.marpol.2026.107169) diagnose MPA governance gaps
    interpretively from modularity, participation roles and out-degree
    centrality on a one-mode network held in both undirected and directed
    forms; this function operationalises that concept as an explicit
    directed coverage test over the DAPSI(W)R(M) cascade. Pure.
    """
    ids = {el.id for el in isa.elements}
    out: dict[str, set[str]] = {el.id: set() for el in isa.elements}
    pairs: set[tuple[str, str]] = set()
    for c in isa.connections:
        if c.source == c.target or c.source not in ids or c.target not in ids:
            continue
        pairs.add((c.source, c.target))
        out[c.source].add(c.target)

    governance = [el for el in isa.elements if el.type in _GOVERNANCE]
    ecological = [el for el in isa.elements if subsystem(el.type) == "ecological"]
    n_unclassified = sum(
        1 for el in isa.elements
        if subsystem(el.type) == "" and el.type not in _GOVERNANCE
    )

    covered: set[str] = set()
    for g in governance:
        covered |= out[g.id]

    gaps_by_type: dict[str, dict] = {}
    for el in ecological:
        entry = gaps_by_type.setdefault(el.type, {"n": 0, "uncovered": []})
        entry["n"] += 1
        if el.id not in covered:
            entry["uncovered"].append(el.id)

    eco_ids = {el.id for el in ecological}
    orphans: list[str] = []
    for g in governance:
        seen: set[str] = set()
        stack = [g.id]
        found = False
        while stack and not found:
            for nxt in out[stack.pop()]:
                if nxt in eco_ids:
                    found = True
                    break
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if not found:
            orphans.append(g.id)

    press = gaps_by_type.get("Pressures", {"n": 0, "uncovered": []})
    n_eco = len(ecological)
    n_uncovered = sum(len(v["uncovered"]) for v in gaps_by_type.values())
    return {
        "gaps_by_type": gaps_by_type,
        "pressure_gap_fraction":
            (len(press["uncovered"]) / press["n"]) if press["n"] else 0.0,
        "ecological_gap_fraction": (n_uncovered / n_eco) if n_eco else 0.0,
        "governance_orphans": orphans,
        "n_ecological": n_eco,
        "n_governance": len(governance),
        "n_unclassified": n_unclassified,
        "n_edges_considered": len(pairs),
    }


def _axis_sums(isa: IsaData) -> tuple[dict[str, float], dict[str, float], dict[tuple[str, str], float]]:
    """Per-node Σ edge weights: (influence, dependence, weight_by_pair).
    Parallel (source,target) edges deduplicated (last-wins); self-loops and
    dangling refs skipped. Shared by influence_dependence and influence_skew."""
    influence = {el.id: 0.0 for el in isa.elements}
    dependence = {el.id: 0.0 for el in isa.elements}
    ids = set(influence)
    weight_by_pair: dict[tuple[str, str], float] = {}
    for c in isa.connections:
        if c.source == c.target or c.source not in ids or c.target not in ids:
            continue
        weight_by_pair[(c.source, c.target)] = _edge_weight(c)
    for (src, tgt), w in weight_by_pair.items():
        influence[src] += w
        dependence[tgt] += w
    return influence, dependence, weight_by_pair


def axis_threshold(values: list[float], split: str) -> float:
    """Cross-hair statistic for one quadrant axis. 'median' -> median (robust to
    a hub); anything else -> arithmetic mean. Used by BOTH influence_dependence
    (classification) and the quadrant plot (cross-hair lines) so they agree.
    Assumes a non-empty list (callers guard the empty-graph case first)."""
    import statistics
    return statistics.median(values) if split == "median" else statistics.mean(values)


def influence_dependence(isa: IsaData, *, split: str = "mean") -> dict[str, dict]:
    """Vester influence × dependence per node — weighted, sign-agnostic.

    influence  = Σ _edge_weight over a node's outgoing edges (to OTHERS)
    dependence = Σ _edge_weight over a node's incoming edges (from OTHERS)
    quadrant   = active | critical | reactive | buffering, split at the mean
                 (default) or median of each axis (>= threshold = high side);
                 or 'undetermined' when the system has no structural
                 differentiation. `split` ('mean'|'median') only changes the
                 classification cross-hair, never the degeneracy guard.

    Parallel (source, target) edges are deduplicated (last-wins); self-loops are
    skipped. Returns {} for an empty graph; never raises.
    """
    elements = isa.elements
    if not elements:
        return {}

    influence, dependence, weight_by_pair = _axis_sums(isa)
    n = len(elements)

    # Degeneracy guard: ALWAYS about the mean (split-independent by design).
    mean_inf = sum(influence.values()) / n
    mean_dep = sum(dependence.values()) / n

    def _variance(values: dict[str, float], mean: float) -> float:
        return sum((v - mean) ** 2 for v in values.values()) / n

    if not weight_by_pair or (
        _variance(influence, mean_inf) < 1e-12
        and _variance(dependence, mean_dep) < 1e-12
    ):
        return {
            el.id: {"influence": influence[el.id], "dependence": dependence[el.id],
                    "quadrant": "undetermined"}
            for el in elements
        }

    # Classification cross-hair follows the chosen split.
    thr_inf = axis_threshold(list(influence.values()), split)
    thr_dep = axis_threshold(list(dependence.values()), split)

    out: dict[str, dict] = {}
    for el in elements:
        i, d = influence[el.id], dependence[el.id]
        hi_i, hi_d = i >= thr_inf, d >= thr_dep
        if hi_i and not hi_d:
            quadrant = "active"
        elif hi_i and hi_d:
            quadrant = "critical"
        elif hi_d:
            quadrant = "reactive"
        else:
            quadrant = "buffering"
        out[el.id] = {"influence": i, "dependence": d, "quadrant": quadrant}
    return out


def influence_skew(isa: IsaData, *, k: float = 3.0) -> bool:
    """True when the influence distribution is hub-skewed: max(v) > k * median(v)
    over the non-zero influence values. False when <2 non-zero values. Pure."""
    import statistics
    influence, _, _ = _axis_sums(isa)
    nz = [v for v in influence.values() if v > 0]
    if len(nz) < 2:
        return False
    return max(nz) > k * statistics.median(nz)


def top_n_by_metric(
    isa: IsaData,
    metric: str,
    *,
    n: int = 10,
) -> list[dict]:
    """Return the top-N nodes by `metric`, annotated with element label/type.
    Each row: {rank, id, label, type, value}.
    """
    if metric not in CENTRALITY_METRICS:
        raise ValueError(f"unknown metric {metric!r}; expected one of {CENTRALITY_METRICS}")

    scores = centrality_metrics(isa)[metric]
    by_id = {el.id: el for el in isa.elements}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:n]
    out: list[dict] = []
    for rank, (nid, value) in enumerate(ranked, start=1):
        el = by_id.get(nid)
        out.append({
            "rank": rank,
            "id": nid,
            "label": el.label if el else nid,
            "type":  el.type  if el else "",
            "value": round(float(value), 4),
        })
    return out


# ---------------------------------------------------------------------------
# Network simplification — port of functions/network_analysis.R helpers used
# by modules/analysis_simplify.R. Two reduction modes:
#   - by minimum strength label (drop weak edges below a category)
#   - by top-N edge weight (rank by strength × confidence, keep top-N)
# Both also drop now-isolated nodes by default so the simplified graph is
# the connected core, not a sea of orphans.
# ---------------------------------------------------------------------------

_STRENGTH_RANK: dict[str, int] = {"weak": 1, "medium": 2, "strong": 3}
_RANK_TO_STRENGTH: dict[int, str] = {1: "weak", 2: "medium", 3: "strong"}


def recompute_consensus(connection):
    """Return a copy of `connection` with scalar strength/confidence/polarity/
    delay rewritten as the consensus of its `ratings`. No-op (equivalent copy)
    when there are no ratings. The SOLE writer of the consensus scalars.

    confidence = mean rounded, clamped [1,5]; strength = confidence-weighted
    mean of ranks (plain mean if total weight 0); polarity = majority, tie -> '+';
    delay = mode (ties by first occurrence)."""
    ratings = connection.ratings
    if not ratings:
        return replace(connection)

    confs = [max(1, min(5, int(r.confidence))) for r in ratings]
    confidence = max(1, min(5, round(sum(confs) / len(confs))))

    ranks = [_STRENGTH_RANK.get(r.strength, 2) for r in ratings]
    wsum = sum(confs)
    avg = (sum(rk * c for rk, c in zip(ranks, confs)) / wsum) if wsum > 0 \
        else (sum(ranks) / len(ranks))
    strength = _RANK_TO_STRENGTH[max(1, min(3, round(avg)))]

    n_plus = sum(1 for r in ratings if r.polarity == "+")
    polarity = "+" if n_plus >= (len(ratings) - n_plus) else "-"

    counts = Counter(r.delay for r in ratings)
    top = max(counts.values())
    delay = next(r.delay for r in ratings if counts[r.delay] == top)

    return replace(connection, strength=strength, confidence=confidence,
                   polarity=polarity, delay=delay)


def connection_disagreement(connection) -> dict:
    """Per-connection rater divergence (pure; computed on demand, not stored).

    polarity_contested: ratings not unanimous in sign (False for <2 ratings).
    strength_spread / confidence_spread: max-min over rating ranks / confidences
    (0.0 for <2 ratings)."""
    ratings = connection.ratings
    if len(ratings) < 2:
        return {"polarity_contested": False, "strength_spread": 0.0,
                "confidence_spread": 0.0}
    ranks = [_STRENGTH_RANK.get(r.strength, 2) for r in ratings]
    confs = [max(1, min(5, int(r.confidence))) for r in ratings]
    return {
        "polarity_contested": len({r.polarity for r in ratings}) > 1,
        "strength_spread": float(max(ranks) - min(ranks)),
        "confidence_spread": float(max(confs) - min(confs)),
    }


def disagreement_cell(d: dict, *, contested_label: str) -> str:
    """Column cell text for a connection's disagreement, from a
    connection_disagreement() result + a pre-translated contested label. Pure
    (no t() inside) so every branch — including the spread numbers — is
    unit-testable directly."""
    if d["polarity_contested"]:
        return f"⚠ {contested_label}"
    if d["strength_spread"] > 0 or d["confidence_spread"] > 0:
        return f"~ {d['strength_spread']:.0f}/{d['confidence_spread']:.0f}"
    return "—"


def displayed_pairs(connections, *, contested_only: bool):
    """Pure core of the C3 index contract: (true_idx, connection) pairs — all
    connections when not contested_only, else only polarity-contested ones.
    true_idx is always the position in `connections`, so a contested row keeps
    its true full-list index after filtering (the lookup the UI persists by)."""
    pairs = list(enumerate(connections))
    if not contested_only:
        return pairs
    return [(i, c) for i, c in pairs
            if connection_disagreement(c)["polarity_contested"]]


def upsert_rating(connection, rating):
    """Return a copy of `connection` with `rating` replacing any existing entry
    by the same rater_id (else appended), consensus recomputed. Pure."""
    kept = [r for r in connection.ratings if r.rater_id != rating.rater_id]
    return recompute_consensus(replace(connection, ratings=[*kept, rating]))


def remove_rating(connection, rater_id: str):
    """Return a copy of `connection` with `rater_id`'s rating dropped, consensus
    recomputed (no-op when no ratings remain). Pure."""
    kept = [r for r in connection.ratings if r.rater_id != rater_id]
    return recompute_consensus(replace(connection, ratings=kept))


def _perturb_prob(confidence: int, base: float) -> float:
    """Per-draw drop/flip probability for one edge: base*(5-conf)/4.

    confidence 5 -> 0 (certain edge never perturbed); confidence 1 -> base.
    Confidence is clamped to [1, 5]."""
    c = max(1, min(5, int(confidence)))
    return base * (5 - c) / 4.0


def _perturbed_connections(isa: IsaData, base: float, rng) -> list[Connection]:
    """One Monte Carlo draw of structural uncertainty.

    Each connection independently: drops out with _perturb_prob (omitted from
    the result), or — if kept — flips polarity with the same probability.
    Pure: `isa` is never mutated; returns a fresh connection list."""
    out: list[Connection] = []
    for c in isa.connections:
        p = _perturb_prob(c.confidence, base)
        if rng.random() < p:
            continue  # dropped
        if rng.random() < p:
            flipped = "-" if c.polarity == "+" else "+"
            out.append(replace(c, polarity=flipped))
        else:
            out.append(c)
    return out


def _edge_weight(c) -> float:
    """Composite weight = strength rank × confidence. R uses the same
    multiplicative model in functions/network_analysis.R::edge_weight."""
    s = _STRENGTH_RANK.get(c.strength, 2)
    conf = max(1, min(5, int(c.confidence)))
    return float(s * conf)


def simplify_by_strength(
    isa: IsaData,
    *,
    min_strength: str = "medium",
    drop_isolated: bool = True,
) -> IsaData:
    """Drop edges weaker than `min_strength`. With `drop_isolated=True`,
    nodes with no surviving edges are also dropped — the result is the
    connected core, not a clutter of orphans.
    """
    threshold = _STRENGTH_RANK.get(min_strength, 2)
    kept = [
        c for c in isa.connections
        if _STRENGTH_RANK.get(c.strength, 2) >= threshold
    ]
    if not drop_isolated:
        return IsaData(elements=isa.elements, connections=kept)
    referenced = {c.source for c in kept} | {c.target for c in kept}
    return IsaData(
        elements=[el for el in isa.elements if el.id in referenced],
        connections=kept,
    )


def simplify_top_n_edges(
    isa: IsaData,
    *,
    keep_top_n: int,
    drop_isolated: bool = True,
) -> IsaData:
    """Keep only the top-N edges by composite weight (strength × confidence).
    Mirrors R analysis_simplify's "keep strongest N" reduction."""
    ranked = sorted(isa.connections, key=_edge_weight, reverse=True)[:keep_top_n]
    if not drop_isolated:
        return IsaData(elements=isa.elements, connections=ranked)
    referenced = {c.source for c in ranked} | {c.target for c in ranked}
    return IsaData(
        elements=[el for el in isa.elements if el.id in referenced],
        connections=ranked,
    )


def remove_nodes(isa: IsaData, node_ids: list[str]) -> IsaData:
    """Return a new IsaData with the given node ids and any incident
    connections dropped. Same hygiene as the data-entry cascade-delete:
    no dangling references survive.
    """
    drop = set(node_ids)
    return IsaData(
        elements=[el for el in isa.elements if el.id not in drop],
        connections=[c for c in isa.connections
                     if c.source not in drop and c.target not in drop],
    )


def intervention_impact(
    isa: IsaData,
    node_ids: list[str],
    *,
    metric: str = "pagerank",
) -> dict[str, dict[str, float]]:
    """Compute the "before" and "after" centrality of every remaining
    node when `node_ids` are removed. Mirrors the R analysis_intervention
    module's "node ablation" scenario.

    Returns a dict shaped like:
        {node_id: {"before": x, "after": y, "delta": y - x}}

    Removed nodes themselves don't appear in the result. Nodes whose
    connections didn't go through any removed node typically have small
    deltas; nodes downstream of an ablated node show the biggest swings.
    """
    if metric not in CENTRALITY_METRICS:
        raise ValueError(f"unknown metric {metric!r}")
    before = centrality_metrics(isa)[metric]
    reduced = remove_nodes(isa, node_ids)
    after = centrality_metrics(reduced)[metric]
    out: dict[str, dict[str, float]] = {}
    for nid, before_v in before.items():
        if nid in node_ids:
            continue
        after_v = after.get(nid, 0.0)
        out[nid] = {
            "before": float(before_v),
            "after": float(after_v),
            "delta": float(after_v - before_v),
        }
    return out


def delay_edge_kwargs(c) -> dict:
    """vis.js edge kwargs encoding a connection's delay as a dashed line + a
    delay tooltip. Spread into add_edge(...) at every full-graph edge builder
    (CLD, Leverage, Metrics, Simplify, Intervention) so the delay cue is one
    definition, identical across views. `dashes` is an orthogonal channel — it
    composes with the width/opacity cues some of those views overload."""
    from .constants import normalize_delay
    delay = normalize_delay(c.delay)
    return {"title": f"{c.polarity} · {delay}", "dashes": delay != "immediate"}


def uncertainty_scores(
    isa: IsaData,
    *,
    cycles: list[list[str]] | None = None,
    n_samples: int = 500,
    seed: int | None = None,
    base: float = 0.5,
    max_length: int = 6,
    max_loops: int = 50,
    contested_band: tuple[float, float] = (0.2, 0.8),
) -> dict:
    """Monte-Carlo leverage & loop uncertainty under edge drop + sign-flip.

    Each of `n_samples` draws perturbs the graph via `_perturbed_connections`
    (drop and/or flip per edge, probability decreasing in confidence), then
    recomputes leverage and checks each baseline loop's survival + polarity.

    Returns per-node leverage {mean, ci_low, ci_high, std} (95% percentile CI)
    and per-baseline-loop existence/polarity probabilities with a `contested`
    flag (polarity probability inside `contested_band`). With every edge at
    confidence 5 (or base=0) the result collapses to the point estimate.
    """
    import numpy as np

    node_ids = [el.id for el in isa.elements]
    if not node_ids:
        return {"n_samples": n_samples, "leverage": {}, "loops": []}

    if cycles is None:
        cycles = feedback_loops(isa, max_length=max_length, max_loops=max_loops)

    rng = np.random.default_rng(seed)
    lev_samples: dict[str, list[float]] = {nid: [] for nid in node_ids}
    survived = [0] * len(cycles)
    reinforcing = [0] * len(cycles)

    for _ in range(n_samples):
        pert = IsaData(
            elements=isa.elements,
            connections=_perturbed_connections(isa, base, rng),
        )
        lev = leverage_scores(pert)
        for nid in node_ids:
            lev_samples[nid].append(lev.get(nid, 0.0))
        present = {(c.source, c.target) for c in pert.connections}
        for i, cyc in enumerate(cycles):
            n = len(cyc)
            if all((cyc[k], cyc[(k + 1) % n]) in present for k in range(n)):
                survived[i] += 1
                if loop_polarity(cyc, pert) == "Reinforcing":
                    reinforcing[i] += 1

    leverage_out: dict[str, dict] = {}
    for nid in node_ids:
        arr = np.asarray(lev_samples[nid], dtype=float)
        leverage_out[nid] = {
            "mean": float(arr.mean()),
            "ci_low": float(np.percentile(arr, 2.5)),
            "ci_high": float(np.percentile(arr, 97.5)),
            "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
        }

    label_by_id = {el.id: el.label for el in isa.elements}
    lo, hi = contested_band
    loops_out: list[dict] = []
    for i, cyc in enumerate(cycles):
        exist_p = survived[i] / n_samples
        if survived[i] > 0:
            rein_p = reinforcing[i] / survived[i]
            bal_p = 1.0 - rein_p
            contested = lo <= rein_p <= hi
        else:
            rein_p = bal_p = 0.0
            contested = False
        loops_out.append({
            "id": f"L{i + 1:03d}",
            "nodes": cyc,
            "path": " → ".join(label_by_id.get(x, x) for x in cyc)
            + f" → {label_by_id.get(cyc[0], cyc[0])}",
            "existence_prob": exist_p,
            "reinforcing_prob": rein_p,
            "balancing_prob": bal_p,
            "contested": contested,
        })

    return {"n_samples": n_samples, "leverage": leverage_out, "loops": loops_out}


def classify_loops(cycles: list[list[str]], isa: IsaData) -> list[dict]:
    """Annotate each cycle with id, length, type, delayed, behavior, and a
    human-readable path."""
    label_by_id = {el.id: el.label for el in isa.elements}
    out: list[dict] = []
    for idx, cycle in enumerate(cycles, start=1):
        loop_type = loop_polarity(cycle, isa)
        delayed = loop_has_delay(cycle, isa)
        if loop_type == "Balancing" and delayed:
            behavior = "oscillating"
        elif loop_type == "Balancing":
            behavior = "balancing"
        else:                       # Reinforcing (and any unexpected value)
            behavior = "reinforcing"
        out.append({
            "id": f"L{idx:03d}",
            "length": len(cycle),
            "type": loop_type,
            "delayed": delayed,
            "behavior": behavior,
            "nodes": cycle,
            "path": " → ".join(label_by_id.get(n, n) for n in cycle)
            + f" → {label_by_id.get(cycle[0], cycle[0])}",
        })
    return out
