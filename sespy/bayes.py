"""Path-set Bayesian belief network (Option B of the 2026-09-08 Bayesian
options design).

A causal loop diagram has feedback loops; a belief network must be a DAG.
Rather than cut the whole diagram, this module answers one question at a
time: for a chosen source and target it takes the simple causal paths
between them (network.causal_paths), unions them into a small graph, makes
that graph acyclic by greedily removing the weakest link on each cycle found
(always reported, never silent), derives every
conditional probability table by noisy-OR from the stored strength ×
confidence × polarity scores, or optionally (link_mode="posterior") from the
rater posteriors with the sign marginalised, and runs exact inference with
pgmpy.

pgmpy is optional (`pip install "sespy[bayes]"` / `micromamba install -n
shiny pgmpy`) and is imported lazily inside the two functions that need it;
importing this module never requires it.
"""
from __future__ import annotations

import itertools
from typing import Literal

import networkx as nx

from .data_structure import IsaData
from .network import causal_paths, polarity_posterior, strength_posterior

LinkMode = Literal["stored", "posterior"]

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
                 max_length: int = 8, max_paths: int = 100,
                 link_mode: LinkMode = "stored") -> dict:
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
    causal_paths. link_mode selects the link strength used to rank edges in
    the cycle cut (link_params(conn, link_mode)[0]); "posterior" can cut a
    different edge than "stored" when raters disagree, and the node set is
    the same in both modes (only the topological order can differ). Pure."""
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
                   key=lambda uv: (link_params(conn_by[uv], link_mode)[0], uv))
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


def link_params(connection, link_mode: LinkMode = "stored") -> tuple[float, float]:
    """(q, p_plus) for one edge: the noisy-OR link strength and the
    probability that the link is positive.

    "stored": q = link_probability(connection); p_plus = 1.0 for polarity
    '+', 0.0 for '-'. Any other polarity returns (0.0, 0.0) — q of exactly 0,
    bypassing link_probability's [0.01, 0.99] clamp — so the edge is inactive
    in both parent states, as the v1.10.0 noisy-OR treated it.
    "posterior", when connection.ratings is non-empty: p_plus is the Beta
    posterior mean of network.polarity_posterior and q the expected strength
    under the Dirichlet posterior of network.strength_posterior,
    s_bar = Σ_k mean[k]·STRENGTH_LINK[k], clamped to [0.01, 0.99]. Rater
    confidence enters once, as the pseudo-count weight inside both
    posteriors; no second confidence factor is applied (Decision 5 of the
    2026-09-12 design). "posterior" with no ratings is identical to
    "stored". Pure; ~3 ms for a rated edge (two scipy beta.ppf calls)."""
    if link_mode == "posterior" and connection.ratings:
        p_plus = polarity_posterior(connection)["p_plus"]
        mean = strength_posterior(connection)["mean"]
        s_bar = sum(mean[k] * STRENGTH_LINK[k] for k in STRENGTH_LINK)
        return min(0.99, max(0.01, s_bar)), float(p_plus)
    if connection.polarity == "+":
        return link_probability(connection), 1.0
    if connection.polarity == "-":
        return link_probability(connection), 0.0
    return 0.0, 0.0


def _noisy_or(states: tuple[int, ...], params: list[tuple[float, float]]) -> float:
    """P(child high | parent states) from resolved (q, p_plus) pairs.

    The sign of each link is a latent Bernoulli(p_plus) marginalised out:
    a_i = p_plus_i when the parent is high, 1 − p_plus_i when it is low, and
    P(high) = 1 − (1 − LEAK)·Π_i (1 − q_i·a_i). With p_plus ∈ {0, 1} this is
    the v1.10.0 formula exactly (an inactive parent multiplies by 1.0). At
    p_plus = 0.5 both parent states give the same activation, so the child
    is independent of that parent. Pure."""
    prod = 1.0 - LEAK
    for state, (q, p_plus) in zip(states, params):
        a = p_plus if state == 1 else 1.0 - p_plus
        prod *= 1.0 - q * a
    return 1.0 - prod


def noisy_or_p_high(states: tuple[int, ...], parents: list, *,
                    link_mode: LinkMode = "stored") -> float:
    """P(child high | parent states) for (parent_id, Connection) pairs —
    _noisy_or over link_params resolved per call. Pure."""
    return _noisy_or(states, [link_params(conn, link_mode) for _, conn in parents])


def merge_evidence(preset: dict[str, int], high, low, nodes: list[str]) -> dict:
    """Merge the preset evidence with the user's extra picks. `high`/`low`
    are any iterable of node ids or None (a multi-select with nothing chosen
    is None in Shiny). Returns {"evidence": {id: 0|1}, "ignored": [ids],
    "conflicts": [ids]}. Rules, per id: (1) not in `nodes` → ignored (outside
    the path set: not part of the question), checked first so an unknown id
    is never a conflict; (2) in both pickers → conflict; (3) in a picker with
    the opposite state to the preset → conflict (agreeing is fine); (4)
    otherwise merged, preset first. Lists are sorted and deduplicated. Any
    conflict means the caller must not run inference. Pure."""
    known = set(nodes)
    hi = sorted({str(x) for x in (high or ())})
    lo = sorted({str(x) for x in (low or ())})
    ignored = sorted({x for x in hi + lo if x not in known})
    hi = [x for x in hi if x in known]
    lo = [x for x in lo if x in known]
    conflicts = set(hi) & set(lo)
    conflicts |= {x for x in hi if preset.get(x) == 0}
    conflicts |= {x for x in lo if preset.get(x) == 1}
    evidence = dict(preset)
    for x in hi:
        evidence.setdefault(x, 1)
    for x in lo:
        evidence.setdefault(x, 0)
    return {"evidence": evidence, "ignored": ignored, "conflicts": sorted(conflicts)}


def focus_node(source: str, target: str, evidence: dict[str, int]) -> str | None:
    """The node whose posterior the summary and the attribution are about:
    the target unless it is in evidence, then the source; None when both
    are in evidence (no focus line, no attribution). Pure."""
    if target not in evidence:
        return target
    if source not in evidence:
        return source
    return None


def model_from_dag(info: dict, *, link_mode: LinkMode = "stored"):
    """pgmpy DiscreteBayesianNetwork over a path_set_dag result (or any dict
    with the same "nodes"/"edges" shape); None when info has no nodes.
    Every node is binary (0 low, 1 high). Parentless nodes (the source, and
    any node whose in-edges were all cut) get P(high) = 0.5; every other
    CPT is noisy-OR over its in-edges via noisy_or_p_high. This is the single
    place the CPT derivation lives: build_path_bbn and attribute_paths both
    call it. link_mode: "stored" (v1.10.0 CPTs, bit-identical) or "posterior"
    (rated edges take (q, p_plus) from the rater posteriors; the sign is
    marginalised inside the noisy-OR). Parameters are resolved once per
    in-edge, not per CPT cell. Raises BayesUnavailable when pgmpy is missing
    (checked before the empty check, so the caller learns about a missing
    engine even with no path)."""
    try:
        from pgmpy.factors.discrete import TabularCPD
        from pgmpy.models import DiscreteBayesianNetwork
    except ImportError as exc:
        raise BayesUnavailable(_INSTALL_HINT) from exc

    if not info["nodes"]:
        return None
    model = DiscreteBayesianNetwork([(u, v) for u, v, _ in info["edges"]])
    model.add_nodes_from(info["nodes"])
    parents: dict[str, list] = {n: [] for n in info["nodes"]}
    for u, v, c in info["edges"]:
        parents[v].append((u, link_params(c, link_mode)))
    for node in info["nodes"]:
        ps = parents[node]
        if not ps:
            model.add_cpds(TabularCPD(node, 2, [[0.5], [0.5]]))
            continue
        # pgmpy column order: itertools.product over the evidence list, last
        # variable fastest — exactly what product([0, 1], repeat=k) yields.
        params = [prm for _, prm in ps]
        highs = [_noisy_or(states, params)
                 for states in itertools.product((0, 1), repeat=len(ps))]
        model.add_cpds(TabularCPD(
            node, 2, [[1.0 - p for p in highs], highs],
            evidence=[u for u, _ in ps], evidence_card=[2] * len(ps),
        ))
    model.check_model()
    return model


def build_path_bbn(isa: IsaData, source: str, target: str, *,
                   max_length: int = 8, max_paths: int = 100,
                   link_mode: LinkMode = "stored"):
    """(pgmpy DiscreteBayesianNetwork, dag_info) over path_set_dag; (None,
    empty dag_info) when there is no path. Equivalent to
    (model_from_dag(info), info) with info = path_set_dag(...). Raises
    BayesUnavailable when pgmpy is missing."""
    info = path_set_dag(isa, source, target, max_length=max_length, max_paths=max_paths,
                        link_mode=link_mode)
    return model_from_dag(info, link_mode=link_mode), info


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


def attribute_paths(info: dict, evidence: dict[str, int], focus: str, *,
                    link_mode: LinkMode = "stored") -> list[dict]:
    """Solo-path effect: for each route still intact in info["paths"], build
    a chain model over that route's edges only (model_from_dag), apply the
    evidence restricted to the route's nodes, and read the focus node.
    Rows {"path": [ids], "length", "polarity", "baseline", "p_high",
    "delta"} sorted by (-round(|delta|, 9), path); the explicit rounding
    makes the lexicographic tiebreak deterministic when routes tie (the
    sample's two D001→GB01 routes both give −0.0301). `baseline` is the
    chain's own no-evidence marginal and differs from the joint baseline.
    The values are computed on the chain ALONE and do NOT sum to the joint
    delta of query_path_bbn (noisy-OR is sub-additive; routes share edges).
    Chain models are built in `link_mode`, the same mode as the joint model.
    Precondition: focus ∉ evidence (focus_node guarantees it) — ValueError
    otherwise. [] when there are no routes. Raises BayesUnavailable when
    pgmpy is missing. Deterministic."""
    if focus in evidence:
        raise ValueError("attribute_paths: the focus node must not be in evidence")
    conn_by = {(u, v): c for u, v, c in info["edges"]}
    rows: list[dict] = []
    for r in info["paths"]:
        p = list(r["path"])
        on_route = set(p)
        sub = {"nodes": p,
               "edges": [(u, v, conn_by[(u, v)]) for u, v in zip(p, p[1:])],
               "cut_edges": [], "paths": [r], "truncated": False}
        model = model_from_dag(sub, link_mode=link_mode)
        q = query_path_bbn(model, sub, {k: v for k, v in evidence.items() if k in on_route})
        row = next(x for x in q["rows"] if x["id"] == focus)
        rows.append({"path": p, "length": r["length"], "polarity": r["polarity"],
                     "baseline": row["baseline"], "p_high": row["p_high"], "delta": row["delta"]})
    rows.sort(key=lambda x: (-round(abs(x["delta"]), 9), x["path"]))
    return rows
