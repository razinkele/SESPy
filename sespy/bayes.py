"""Path-set Bayesian belief network (Option B of the 2026-09-08 Bayesian
options design).

A causal loop diagram has feedback loops; a belief network must be a DAG.
Rather than cut the whole diagram, this module answers one question at a
time: for a chosen source and target it takes the simple causal paths
between them (network.causal_paths), unions them into a small graph, makes
that graph acyclic by greedily removing the weakest link on each cycle found
(always reported, never silent), derives every
conditional probability table by noisy-OR from the existing strength ×
confidence × polarity scores, and runs exact inference with pgmpy.

pgmpy is optional (`pip install "sespy[bayes]"` / `micromamba install -n
shiny pgmpy`) and is imported lazily inside the two functions that need it;
importing this module never requires it.
"""
from __future__ import annotations

import itertools

import networkx as nx

from .data_structure import IsaData
from .network import causal_paths

#: P(child high | no active parent) — the noisy-OR leak.
LEAK: float = 0.05
#: Base link strength per strength rank before confidence scaling.
STRENGTH_LINK: dict[str, float] = {"weak": 0.30, "medium": 0.55, "strong": 0.80}

_INSTALL_HINT = ('Bayesian inference needs the optional pgmpy package: '
                 'pip install "sespy[bayes]"  or  micromamba install -n shiny pgmpy')


class BayesUnavailable(ImportError):
    """pgmpy is not installed. str(exc) carries the install hint."""


def link_probability(connection) -> float:
    """Noisy-OR link strength q for one edge: STRENGTH_LINK[strength] scaled
    by confidence, q = s·(0.5 + 0.5·(conf − 1)/4); confidence 5 gives s,
    confidence 1 gives s/2. Unknown strength counts as medium; confidence is
    clamped to [1, 5]; q is clamped to [0.01, 0.99]. Pure."""
    s = STRENGTH_LINK.get(connection.strength, STRENGTH_LINK["medium"])
    conf = max(1, min(5, int(connection.confidence)))
    q = s * (0.5 + 0.5 * (conf - 1) / 4.0)
    return min(0.99, max(0.01, q))


def _empty_dag() -> dict:
    return {"nodes": [], "edges": [], "cut_edges": [], "paths": [], "truncated": False}


def path_set_dag(isa: IsaData, source: str, target: str, *,
                 max_length: int = 8, max_paths: int = 100) -> dict:
    """Union of the simple source→target paths, made acyclic.

    Returns {"nodes": [ids in lexicographic topological order],
             "edges": [(u, v, Connection)], "cut_edges": [(u, v)],
             "paths": the causal_paths rows still intact after cuts,
             "truncated": bool}; the empty shape when there is no path. The
    union of simple paths is NOT always a DAG (s→a→b→t and s→b→a→t contain
    a⇄b): while a cycle remains, the edge on it with the lowest
    link_probability (ties: lexicographic (u, v)) is removed greedily and
    recorded in cut_edges — never silently (greedy, not minimal: a shared
    edge on two cycles may be spared in favour of two weaker ones). A node
    whose in-edges were all cut becomes a parentless 0.5-prior root. Parallel
    (source, target) connections deduplicate last-wins, matching
    causal_paths. Pure."""
    cp = causal_paths(isa, source, target, max_length=max_length, max_paths=max_paths)
    if not cp["paths"]:
        return _empty_dag()
    conn_by: dict[tuple[str, str], object] = {}
    for c in isa.connections:
        conn_by[(c.source, c.target)] = c
    g = nx.DiGraph()
    for row in cp["paths"]:
        p = row["path"]
        for u, v in zip(p, p[1:]):
            g.add_edge(u, v)
    cut: list[tuple[str, str]] = []
    while True:
        try:
            cycle = nx.find_cycle(g)
        except nx.NetworkXNoCycle:
            break
        u, v = min(((e[0], e[1]) for e in cycle),
                   key=lambda uv: (link_probability(conn_by[uv]), uv))
        g.remove_edge(u, v)
        cut.append((u, v))
    nodes = list(nx.lexicographical_topological_sort(g))
    edges = [(u, v, conn_by[(u, v)]) for u, v in sorted(g.edges())]
    # Only paths whose every hop survived the cuts are still IN the model;
    # n_paths in the UI must count those, not the pre-cut enumeration.
    paths = [r for r in cp["paths"]
             if all(g.has_edge(a, b) for a, b in zip(r["path"], r["path"][1:]))]
    return {"nodes": nodes, "edges": edges, "cut_edges": cut,
            "paths": paths, "truncated": cp["truncated"]}


def noisy_or_p_high(states: tuple[int, ...], parents: list) -> float:
    """P(child high | parent states) under noisy-OR.

    A parent is *active* when it is high and its edge is '+', or low and its
    edge is '-' (a negative link pushes the child high when the parent is
    low). P(high) = 1 − (1 − LEAK)·Π_active (1 − q_i). Pure."""
    prod = 1.0 - LEAK
    for state, (_, conn) in zip(states, parents):
        active = (state == 1 and conn.polarity == "+") or (state == 0 and conn.polarity == "-")
        if active:
            prod *= 1.0 - link_probability(conn)
    return 1.0 - prod


def build_path_bbn(isa: IsaData, source: str, target: str, *,
                   max_length: int = 8, max_paths: int = 100):
    """(pgmpy DiscreteBayesianNetwork, dag_info) over path_set_dag; (None,
    empty dag_info) when there is no path. Every node is binary (0 low,
    1 high). Parentless nodes (the source, and any node whose in-edges were
    all cut) get P(high) = 0.5; every other
    CPT is noisy-OR over its parents *inside the path set*. Raises
    BayesUnavailable when pgmpy is missing."""
    try:
        from pgmpy.factors.discrete import TabularCPD
        from pgmpy.models import DiscreteBayesianNetwork
    except ImportError as exc:
        raise BayesUnavailable(_INSTALL_HINT) from exc

    info = path_set_dag(isa, source, target, max_length=max_length, max_paths=max_paths)
    if not info["nodes"]:
        return None, info
    model = DiscreteBayesianNetwork([(u, v) for u, v, _ in info["edges"]])
    parents: dict[str, list] = {n: [] for n in info["nodes"]}
    for u, v, c in info["edges"]:
        parents[v].append((u, c))
    for node in info["nodes"]:
        ps = parents[node]
        if not ps:
            model.add_cpds(TabularCPD(node, 2, [[0.5], [0.5]]))
            continue
        # pgmpy column order: itertools.product over the evidence list, last
        # variable fastest — exactly what product([0, 1], repeat=k) yields.
        highs = [noisy_or_p_high(states, ps)
                 for states in itertools.product((0, 1), repeat=len(ps))]
        model.add_cpds(TabularCPD(
            node, 2, [[1.0 - p for p in highs], highs],
            evidence=[u for u, _ in ps], evidence_card=[2] * len(ps),
        ))
    model.check_model()
    return model, info


def query_path_bbn(model, info: dict, evidence: dict[str, int]) -> dict:
    """Exact posterior P(high) for every path-set node given `evidence`
    ({node_id: 0|1}), by variable elimination, against the no-evidence
    baseline. rows sort by |delta| descending then id; evidence nodes report
    p_high equal to their evidence value. Deterministic (no sampling)."""
    from pgmpy.inference import VariableElimination

    ve = VariableElimination(model)
    ev = {k: int(v) for k, v in evidence.items()}
    rows = []
    for n in info["nodes"]:
        base = float(ve.query([n], show_progress=False).values[1])
        if n in ev:
            p = float(ev[n])
        else:
            p = float(ve.query([n], evidence=ev, show_progress=False).values[1])
        rows.append({"id": n, "baseline": base, "p_high": p, "delta": p - base})
    rows.sort(key=lambda r: (-abs(r["delta"]), r["id"]))
    return {"rows": rows, "evidence": ev, "n_paths": len(info["paths"]),
            "truncated": info["truncated"], "cut_edges": list(info["cut_edges"])}
