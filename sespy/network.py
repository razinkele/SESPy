"""Network analysis — minimal port of functions/network_analysis.R.

The R version uses igraph throughout. networkx is used here for the POC to
avoid a package install; swap to python-igraph in production for bit-for-bit
parity with R (both bind the same C `libigraph`).
"""

from __future__ import annotations

import networkx as nx

from .data_structure import IsaData


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
    """
    g = to_digraph(isa)
    cycles: list[list[str]] = []
    for cycle in nx.simple_cycles(g):
        if len(cycle) > max_length:
            continue
        cycles.append(cycle)
        if len(cycles) >= max_loops:
            break
    return cycles


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
    except Exception:
        betweenness = {n: 0.0 for n in g.nodes()}

    try:
        closeness = nx.closeness_centrality(g)
    except Exception:
        closeness = {n: 0.0 for n in g.nodes()}

    try:
        eigenvector = nx.eigenvector_centrality_numpy(g, max_iter=200)
    except Exception:
        # Fallback for graphs where the numpy solver is unhappy
        try:
            eigenvector = nx.eigenvector_centrality(g, max_iter=500)
        except Exception:
            eigenvector = {n: 0.0 for n in g.nodes()}

    try:
        pagerank = nx.pagerank(g, alpha=0.85)
    except Exception:
        pagerank = {n: 0.0 for n in g.nodes()}

    return {
        **degrees,
        "betweenness": _safe_floats(betweenness),
        "closeness":   _safe_floats(closeness),
        "eigenvector": _safe_floats(eigenvector),
        "pagerank":    _safe_floats(pagerank),
    }


def _zscore(values: dict[str, float]) -> dict[str, float]:
    """Standardise to mean 0, std 1. Returns zeros if std is 0."""
    if not values:
        return {}
    vs = list(values.values())
    mean = sum(vs) / len(vs)
    var = sum((v - mean) ** 2 for v in vs) / len(vs)
    std = var ** 0.5
    if std == 0:
        return {k: 0.0 for k in values}
    return {k: (v - mean) / std for k, v in values.items()}


def leverage_scores(isa: IsaData) -> dict[str, float]:
    """Composite leverage score per node — z-score(betweenness) +
    z-score(eigenvector) + z-score(pagerank). Higher = more leverage.

    Mirrors functions/network_analysis.R:1390-1392.
    """
    m = centrality_metrics(isa)
    bz = _zscore(m["betweenness"])
    ez = _zscore(m["eigenvector"])
    pz = _zscore(m["pagerank"])
    return {nid: bz.get(nid, 0.0) + ez.get(nid, 0.0) + pz.get(nid, 0.0)
            for nid in m["betweenness"]}


def influence_dependence(isa: IsaData) -> dict[str, dict]:
    """Vester influence × dependence per node — weighted, sign-agnostic.

    influence  = Σ _edge_weight over a node's outgoing edges (to OTHERS)
    dependence = Σ _edge_weight over a node's incoming edges (from OTHERS)
    quadrant   = active | critical | reactive | buffering, split at the mean
                 of each axis (>= mean = high side); or 'undetermined' when the
                 system has no structural differentiation.

    Parallel (source, target) edges are deduplicated (last-wins), matching
    to_digraph; self-loops are skipped. Returns {} for an empty graph; never
    raises. Mirrors the zeros-never-raise posture of the other metrics here.
    """
    elements = isa.elements
    if not elements:
        return {}

    influence = {el.id: 0.0 for el in elements}
    dependence = {el.id: 0.0 for el in elements}
    ids = set(influence)

    # Deduplicate parallel edges (last-wins) and drop self-loops / dangling refs.
    weight_by_pair: dict[tuple[str, str], float] = {}
    for c in isa.connections:
        if c.source == c.target:
            continue
        if c.source not in ids or c.target not in ids:
            continue
        weight_by_pair[(c.source, c.target)] = _edge_weight(c)

    for (src, tgt), w in weight_by_pair.items():
        influence[src] += w
        dependence[tgt] += w

    n = len(elements)
    mean_inf = sum(influence.values()) / n
    mean_dep = sum(dependence.values()) / n

    def _variance(values: dict[str, float], mean: float) -> float:
        return sum((v - mean) ** 2 for v in values.values()) / n

    # Degeneracy guard: no edges, or zero variance on both axes (uniform graph).
    if not weight_by_pair or (
        _variance(influence, mean_inf) < 1e-12
        and _variance(dependence, mean_dep) < 1e-12
    ):
        return {
            el.id: {
                "influence": influence[el.id],
                "dependence": dependence[el.id],
                "quadrant": "undetermined",
            }
            for el in elements
        }

    out: dict[str, dict] = {}
    for el in elements:
        i, d = influence[el.id], dependence[el.id]
        hi_i, hi_d = i >= mean_inf, d >= mean_dep
        if hi_i and not hi_d:
            quadrant = "active"
        elif hi_i and hi_d:
            quadrant = "critical"
        elif hi_d:  # not hi_i and hi_d
            quadrant = "reactive"
        else:
            quadrant = "buffering"
        out[el.id] = {"influence": i, "dependence": d, "quadrant": quadrant}
    return out


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
