"""Smoke tests for the ported analytics layer.

These mirror the testthat patterns in tests/testthat/test-network-analysis.R
at the level needed to prove the port works end-to-end on the sample data.
A real port would replicate all 92 testthat files; this is the proof.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sespy import network
from sespy.data_structure import (
    Connection,
    Element,
    IsaData,
    filter_elements,
    load_sample,
    to_visnetwork,
)

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_ses.json"


def test_feedback_loops_enumeration_is_bounded():
    """Tripwire for issue #18: on a dense digraph, unbounded
    nx.simple_cycles enumeration ran >5 minutes here (cycles longer than
    max_length are generated before being filtered); with
    length_bound the same call returns capped results in milliseconds.
    A regression to unbounded enumeration hangs this test."""
    import random
    rng = random.Random(7)
    els = [Element(id=f"N{i}", label=f"n{i}", type="Drivers") for i in range(40)]
    conns = [Connection(source=f"N{i}", target=f"N{j}")
             for i in range(40) for j in range(40)
             if i != j and rng.random() < 0.25]
    loops = network.feedback_loops(IsaData(elements=els, connections=conns))
    assert len(loops) == 50  # max_loops cap reached
    assert all(2 <= len(lp) <= 6 for lp in loops)  # max_length honored


@pytest.fixture(scope="module")
def isa():
    return load_sample(SAMPLE)


def test_sample_loads(isa):
    assert isa.element_count() == 17
    assert isa.connection_count() == 20


def test_basic_metrics(isa):
    m = network.basic_metrics(isa)
    assert m["nodes"] == 17
    assert m["edges"] == 20
    assert 0 < m["density"] < 1


def test_feedback_loops_detected(isa):
    cycles = network.feedback_loops(isa)
    # The sample SES has at least the demand→activity→pressure→state→service→
    # benefit→demand reinforcing loop and the response→pressure damping loop.
    assert len(cycles) >= 1
    for cycle in cycles:
        assert len(cycle) <= 6


def test_filter_drops_dangling_connections(isa):
    only_drivers = filter_elements(isa, ["Drivers"])
    assert all(e.type == "Drivers" for e in only_drivers.elements)
    assert only_drivers.connection_count() == 0  # no edges connect Driver→Driver in sample


def test_to_visnetwork_shape(isa):
    payload = to_visnetwork(isa)
    assert set(payload) == {"nodes", "edges"}
    assert {"id", "label", "group", "color", "shape", "level"} <= set(payload["nodes"][0])
    assert {"from", "to", "color", "arrows"} <= set(payload["edges"][0])


def test_dapsiwrm_levels_ordered_correctly(isa):
    """Hierarchical level assignments encode the DAPSIWRM causal flow.

    With vis.js direction="DU", smaller levels are at the bottom. So the
    framework reads top→bottom as Drivers > Activities > Pressures >
    Responses > MPF > ES > G&B. Responses get their own row directly
    below Pressures (deviates from R's same-row-with-x-offset, which
    vis.js silently ignores in hierarchical mode).
    """
    payload = to_visnetwork(isa)
    by_type: dict[str, set[int]] = {}
    for node in payload["nodes"]:
        by_type.setdefault(node["group"], set()).add(node["level"])

    expected_order = [
        "Goods & Benefits",
        "Ecosystem Services",
        "Marine Processes & Functioning",
        "Responses",
        "Pressures",
        "Activities",
        "Drivers",
    ]
    levels_in_order = [next(iter(by_type[t])) for t in expected_order if t in by_type]
    assert levels_in_order == sorted(levels_in_order), (
        f"DAPSIWRM levels are out of order: {levels_in_order}"
    )

    # Responses must be on their own row — distinct from every other type
    if "Responses" in by_type:
        responses_level = next(iter(by_type["Responses"]))
        other_levels = {
            lvl for t, lvls in by_type.items() if t != "Responses" for lvl in lvls
        }
        assert responses_level not in other_levels, (
            "Responses should have a dedicated row, not share with another DAPSIWRM type"
        )


def test_loop_polarity_rule(isa):
    """Even-negatives ⇒ Reinforcing, odd-negatives ⇒ Balancing.

    Mirrors functions/network_analysis.R::classify_loop_type (line 842).
    """
    cycles = network.feedback_loops(isa)
    annotated = network.classify_loops(cycles, isa)

    # Sample SES has at least one of each by design (demand→activity→pressure
    # →state→service→benefit→demand has no negatives → Reinforcing; the
    # response-mediated one threads through "-" pressure→state edges).
    types = {row["type"] for row in annotated}
    assert types <= {"Reinforcing", "Balancing"}
    assert all(row["length"] == len(row["nodes"]) for row in annotated)
    assert all(row["id"].startswith("L") for row in annotated)


def test_centrality_metrics_seven_keys(isa):
    """All seven centrality measures should be present and cover every node."""
    m = network.centrality_metrics(isa)
    assert set(m) == set(network.CENTRALITY_METRICS)
    n_nodes = isa.element_count()
    for metric, scores in m.items():
        assert len(scores) == n_nodes, (
            f"{metric} returned {len(scores)} scores, expected {n_nodes}"
        )


def test_centrality_finite_no_inf_no_nan(isa):
    """The R guard at network_analysis.R:57-61 sanitises closeness inf/nan;
    our `_safe_floats` should do the same."""
    import math
    m = network.centrality_metrics(isa)
    for metric, scores in m.items():
        for nid, v in scores.items():
            assert math.isfinite(v), f"{metric}[{nid}] = {v!r} is not finite"


def test_centrality_degree_matches_directed_in_plus_out(isa):
    """Sanity: total degree == in-degree + out-degree for directed graphs."""
    m = network.centrality_metrics(isa)
    for nid in m["degree"]:
        assert m["degree"][nid] == m["indegree"][nid] + m["outdegree"][nid], nid


def test_top_n_by_metric_orders_descending(isa):
    rows = network.top_n_by_metric(isa, "degree", n=5)
    assert len(rows) == 5
    values = [r["value"] for r in rows]
    assert values == sorted(values, reverse=True)
    # rank should be 1..N
    assert [r["rank"] for r in rows] == [1, 2, 3, 4, 5]
    # each row carries label and type for display
    for r in rows:
        assert r["label"]
        assert r["type"]


def test_leverage_scores_returns_per_node_floats(isa):
    """Composite score = z(betweenness) + z(eigenvector) + z(pagerank).
    Mirrors functions/network_analysis.R:1390. Result is a finite per-node
    score, mean ≈ 0 (sum of three z-scores summed across all nodes is 0)."""
    import math

    s = network.leverage_scores(isa)
    assert len(s) == isa.element_count()
    for v in s.values():
        assert math.isfinite(v)
    # Sum of z-scores across nodes is 0 by construction; sum of three of
    # those is also 0 (within float-precision tolerance).
    assert abs(sum(s.values())) < 1e-6


def test_leverage_top_node_has_highest_score(isa):
    """The element with the most cross-cutting role (highest betweenness +
    eigenvector + pagerank) should top the leverage rank."""
    s = network.leverage_scores(isa)
    top_id = max(s, key=s.get)
    # Sanity check: the top node should be one that actually has
    # connections (a degree > 0). Isolated nodes can't have leverage.
    g = network.to_digraph(isa)
    assert g.degree(top_id) > 0


def test_simplify_by_strength_drops_weak(isa):
    """Keeping ≥medium drops every weak edge (and any node it isolated)."""
    weak_count = sum(1 for c in isa.connections if c.strength == "weak")
    if weak_count == 0:
        # Sample doesn't have any weak edges by default; build a synthetic
        # case so the assertion remains meaningful.
        from sespy.data_structure import Connection
        isa = type(isa)(
            elements=isa.elements,
            connections=isa.connections + [
                Connection(source=isa.elements[0].id,
                           target=isa.elements[1].id,
                           polarity="+", strength="weak"),
            ],
        )
        weak_count = 1

    result = network.simplify_by_strength(
        isa, min_strength="medium", drop_isolated=False,
    )
    assert all(c.strength != "weak" for c in result.connections)
    assert len(result.connections) == len(isa.connections) - weak_count


def test_simplify_top_n_keeps_strongest(isa):
    """Top-N reduction keeps the highest strength × confidence edges."""
    n = 5
    result = network.simplify_top_n_edges(isa, keep_top_n=n, drop_isolated=False)
    assert result.connection_count() == min(n, isa.connection_count())
    # Every kept edge should weigh ≥ every dropped edge
    kept_weights = {network._edge_weight(c) for c in result.connections}
    kept_set = {(c.source, c.target) for c in result.connections}
    dropped = [c for c in isa.connections
               if (c.source, c.target) not in kept_set]
    if dropped:
        max_dropped = max(network._edge_weight(c) for c in dropped)
        assert min(kept_weights) >= max_dropped


def test_simplify_drop_isolated_removes_orphan_nodes(isa):
    """When `drop_isolated=True`, nodes with zero surviving edges go away
    too — the result is the connected core."""
    result = network.simplify_by_strength(
        isa, min_strength="strong", drop_isolated=True,
    )
    referenced = {c.source for c in result.connections} | \
                 {c.target for c in result.connections}
    assert {el.id for el in result.elements} == referenced


def test_remove_nodes_drops_node_and_incident_edges(isa):
    sample_id = isa.elements[0].id
    reduced = network.remove_nodes(isa, [sample_id])
    assert all(el.id != sample_id for el in reduced.elements)
    assert all(c.source != sample_id and c.target != sample_id
               for c in reduced.connections)
    # Element count drops by exactly 1; connections drop by however
    # many were incident
    assert reduced.element_count() == isa.element_count() - 1


def test_intervention_impact_excludes_removed(isa):
    target = isa.elements[0].id
    impact = network.intervention_impact(isa, [target], metric="degree")
    assert target not in impact
    # Every surviving node has all three keys
    for nid, info in impact.items():
        assert {"before", "after", "delta"} <= set(info)
        # `delta` must equal `after - before`
        assert abs((info["after"] - info["before"]) - info["delta"]) < 1e-9


def test_intervention_impact_neighbours_change_more(isa):
    """Removing a high-degree node should affect its direct neighbours
    more than distant nodes (their `after` degree drops)."""
    # Pick the node with the most connections
    g = network.to_digraph(isa)
    top = max(g.nodes(), key=lambda n: g.degree(n))
    direct_neighbours = set(g.successors(top)) | set(g.predecessors(top))

    impact = network.intervention_impact(isa, [top], metric="degree")
    for n in direct_neighbours:
        if n in impact:
            # Neighbours of the removed node should have a non-zero delta
            # (they lost at least one edge)
            assert impact[n]["delta"] != 0


def test_centrality_4_node_loop_golden():
    """Hand-checked tiny graph: 4-node directed cycle. Degree-1 in/out for
    every node; betweenness = 0 (no node lies on any path other than the
    cycle itself); pagerank uniform at 0.25."""
    from sespy.data_structure import Connection, Element, IsaData

    nodes = [Element(id=c, label=c, type="Drivers") for c in "ABCD"]
    edges = [
        Connection(source="A", target="B", polarity="+"),
        Connection(source="B", target="C", polarity="+"),
        Connection(source="C", target="D", polarity="+"),
        Connection(source="D", target="A", polarity="+"),
    ]
    m = network.centrality_metrics(IsaData(elements=nodes, connections=edges))
    for n in "ABCD":
        assert m["indegree"][n] == 1
        assert m["outdegree"][n] == 1
        assert m["degree"][n] == 2
        assert abs(m["pagerank"][n] - 0.25) < 1e-6, m["pagerank"][n]


def test_pyvis_loop_payload_shape():
    """pyvis 4.2 used as a JSON builder: build_loop_payload should hand back
    the same {nodes, edges} dict shape the vis-network bridge expects, with
    DAPSIWRM colors/shapes already mapped per element type.
    """
    # analysis_loops imports `pyvis.shiny`, which only exists in the pyvis
    # fork (not upstream PyPI pyvis). Skip where the fork isn't installed
    # rather than fail a fork-independent environment (e.g. CI on PyPI deps).
    pytest.importorskip("pyvis.shiny")
    from sespy.constants import EDGE_COLORS, ELEMENT_COLORS, ELEMENT_SHAPES
    from sespy.modules.analysis_loops import build_loop_payload

    isa = load_sample(SAMPLE)
    cycles = network.feedback_loops(isa)
    assert cycles, "sample SES should contain at least one cycle"

    payload = build_loop_payload(cycles[0], isa)
    assert set(payload) == {"nodes", "edges"}

    type_by_id = {e.id: e.type for e in isa.elements}
    for node in payload["nodes"]:
        nid = node["id"]
        assert "label" in node
        # Color/shape come from the DAPSIWRM constants via pyvis
        assert node["color"] == ELEMENT_COLORS[type_by_id[nid]]
        assert node["shape"] == ELEMENT_SHAPES[type_by_id[nid]]

    # Edges are colored by polarity (reinforcing/opposing) — same rule as the
    # CLD canvas, applied loop-wide so the cycle classification is visible.
    valid_edge_colors = set(EDGE_COLORS.values())
    for edge in payload["edges"]:
        assert edge["from"] in {n["id"] for n in payload["nodes"]}
        assert edge["to"] in {n["id"] for n in payload["nodes"]}
        assert edge["color"] in valid_edge_colors
        assert edge["label"] in {"+", "-"}


# ---------------------------------------------------------------------------
# Vester influence × dependence — Task 1
# ---------------------------------------------------------------------------

def _quadrant_fixture():
    # Four nodes hitting all four quadrants; confidence=1 so weight == strength rank.
    els = [
        Element(id="D", label="Driver", type="Driver"),
        Element(id="H", label="Hub", type="Pressure"),
        Element(id="S", label="Sink", type="State"),
        Element(id="I", label="Inert", type="Welfare"),
    ]
    conns = [
        Connection(source="D", target="H", strength="strong", confidence=1),  # w=3
        Connection(source="D", target="S", strength="strong", confidence=1),  # w=3
        Connection(source="H", target="S", strength="strong", confidence=1),  # w=3
        Connection(source="H", target="I", strength="weak",   confidence=1),  # w=1
        Connection(source="S", target="H", strength="weak",   confidence=1),  # w=1
    ]
    return IsaData(elements=els, connections=conns)


def test_influence_dependence_sums_and_quadrants():
    res = network.influence_dependence(_quadrant_fixture())
    # influence (out): D=6, H=4, S=1, I=0 ; dependence (in): D=0, H=4, S=6, I=1
    assert res["D"]["influence"] == 6.0 and res["D"]["dependence"] == 0.0
    assert res["H"]["influence"] == 4.0 and res["H"]["dependence"] == 4.0
    assert res["S"]["influence"] == 1.0 and res["S"]["dependence"] == 6.0
    assert res["I"]["influence"] == 0.0 and res["I"]["dependence"] == 1.0
    # means are 2.75 / 2.75
    assert res["D"]["quadrant"] == "active"
    assert res["H"]["quadrant"] == "critical"
    assert res["S"]["quadrant"] == "reactive"
    assert res["I"]["quadrant"] == "buffering"


def test_influence_dependence_empty_graph():
    assert network.influence_dependence(IsaData()) == {}


def test_influence_dependence_all_isolated_is_undetermined():
    els = [Element(id="A", label="A", type="Driver"),
           Element(id="B", label="B", type="State")]
    res = network.influence_dependence(IsaData(elements=els, connections=[]))
    assert {r["quadrant"] for r in res.values()} == {"undetermined"}
    assert res["A"]["influence"] == 0.0 and res["A"]["dependence"] == 0.0


def test_influence_dependence_uniform_ring_is_undetermined():
    els = [Element(id=n, label=n, type="Driver") for n in ("A", "B", "C")]
    conns = [Connection(source="A", target="B", strength="medium", confidence=3),
             Connection(source="B", target="C", strength="medium", confidence=3),
             Connection(source="C", target="A", strength="medium", confidence=3)]
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert {r["quadrant"] for r in res.values()} == {"undetermined"}


def test_influence_dependence_skips_self_loops():
    els = [Element(id="A", label="A", type="Driver"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="A", strength="strong", confidence=1),  # ignored
             Connection(source="A", target="B", strength="medium", confidence=1)]  # w=2
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert res["A"]["influence"] == 2.0      # self-loop not added
    assert res["A"]["dependence"] == 0.0     # self-loop not added to dependence either


def test_influence_dependence_dedups_parallel_edges():
    els = [Element(id="A", label="A", type="Driver"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="B", strength="medium", confidence=1),  # w=2
             Connection(source="A", target="B", strength="strong", confidence=1)]  # w=3 (last wins)
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert res["A"]["influence"] == 3.0      # counted once, last-wins weight, not 5.0


def test_influence_dependence_is_sign_agnostic():
    els = [Element(id="A", label="A", type="Driver"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="B", polarity="-", strength="strong", confidence=1)]
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert res["A"]["influence"] == 3.0      # negative polarity still positive magnitude


def test_influence_dependence_tie_boundary_and_nonuniform_cycle():
    # Non-uniform cycle: influence {A:1, B:2, C:3} mean 2 ; dependence {A:3, B:1, C:2} mean 2.
    # Both axes VARY (var=0.667) so the AND-both-axes degeneracy guard must NOT fire —
    # this pins AND-not-OR semantics. B sits EXACTLY at mean influence (2.0), so the
    # `>= mean` tie rule must place it on the HIGH influence side: a `>` implementation
    # would misclassify B as buffering and fail this test.
    els = [Element(id=n, label=n, type="Driver") for n in ("A", "B", "C")]
    conns = [Connection(source="A", target="B", strength="weak",   confidence=1),  # w=1
             Connection(source="B", target="C", strength="medium", confidence=1),  # w=2
             Connection(source="C", target="A", strength="strong", confidence=1)]  # w=3
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert res["B"]["influence"] == 2.0          # exactly mean_inf
    assert res["B"]["quadrant"] == "active"      # tie -> high side (fails under '>')
    assert res["A"]["quadrant"] == "reactive"
    assert res["C"]["quadrant"] == "critical"
    # Differentiated graph -> distinct quadrants, NOT all 'undetermined'.
    assert len({r["quadrant"] for r in res.values()}) == 3


def test_normalize_delay_table():
    from sespy.constants import normalize_delay
    cases = {
        "immediate": "immediate", "short": "short", "long": "long",
        "SHORT": "short", "Long": "long", "  short  ": "short",
        "": "immediate", "no": "immediate", "none": "immediate",
        "false": "immediate", "0": "immediate", "0.0": "immediate", "-": "immediate",
        "3": "short", "5y": "short", "lag": "short", "delayed": "short",
    }
    for raw, exp in cases.items():
        assert normalize_delay(raw) == exp, (raw, normalize_delay(raw))
    assert normalize_delay(None) == "immediate"


# ---------------------------------------------------------------------------
# Task 2: loop_has_delay + classify_loops behavior/delayed
# ---------------------------------------------------------------------------

def _delay_fixture(ab_polarity, ab_delay, ba_polarity="+", ba_delay="immediate"):
    from sespy.data_structure import Connection, Element, IsaData
    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="B", polarity=ab_polarity, delay=ab_delay),
             Connection(source="B", target="A", polarity=ba_polarity, delay=ba_delay)]
    return IsaData(elements=els, connections=conns)


def test_classify_loops_oscillating_when_balancing_and_delayed():
    isa = _delay_fixture(ab_polarity="-", ab_delay="short")  # 1 negative -> Balancing
    rows = network.classify_loops(network.feedback_loops(isa), isa)
    assert rows, "expected >=1 loop"
    r = rows[0]
    assert r["type"] == "Balancing"
    assert r["delayed"] is True
    assert r["behavior"] == "oscillating"


def test_classify_loops_delayed_reinforcing_stays_reinforcing():
    isa = _delay_fixture(ab_polarity="+", ab_delay="short")  # 0 negatives -> Reinforcing
    r = network.classify_loops(network.feedback_loops(isa), isa)[0]
    assert r["type"] == "Reinforcing"
    assert r["delayed"] is True
    assert r["behavior"] == "reinforcing"


def test_classify_loops_immediate_balancing_not_oscillating():
    isa = _delay_fixture(ab_polarity="-", ab_delay="immediate")
    r = network.classify_loops(network.feedback_loops(isa), isa)[0]
    assert r["type"] == "Balancing"
    assert r["delayed"] is False
    assert r["behavior"] == "balancing"


def test_classify_loops_behavior_buckets_sum_to_total(isa):
    rows = network.classify_loops(network.feedback_loops(isa), isa)
    counts = {b: sum(1 for r in rows if r["behavior"] == b)
              for b in ("reinforcing", "balancing", "oscillating")}
    assert sum(counts.values()) == len(rows)


def test_loop_has_delay_parallel_edges_last_wins():
    from sespy.data_structure import Connection, Element, IsaData
    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="State")]
    # Two A->B edges; last one wins the (source,target) lookup.
    isa_delayed = IsaData(elements=els, connections=[
        Connection(source="A", target="B", delay="immediate"),
        Connection(source="A", target="B", delay="short"),     # last -> delayed
        Connection(source="B", target="A", delay="immediate"),
    ])
    assert network.loop_has_delay(["A", "B"], isa_delayed) is True
    isa_immediate = IsaData(elements=els, connections=[
        Connection(source="A", target="B", delay="short"),
        Connection(source="A", target="B", delay="immediate"),  # last -> immediate
        Connection(source="B", target="A", delay="immediate"),
    ])
    assert network.loop_has_delay(["A", "B"], isa_immediate) is False


# ---------------------------------------------------------------------------
# Task 3: done-criterion — sample seed must yield ≥1 oscillating loop
# ---------------------------------------------------------------------------

def test_sample_has_oscillating_loop(isa):
    rows = network.classify_loops(network.feedback_loops(isa), isa)
    osc = [r for r in rows if r["behavior"] == "oscillating"]
    assert len(osc) >= 1, "sample seed missing — expected >=1 oscillating loop"


# ---------------------------------------------------------------------------
# Task 1 (B2): delay_edge_kwargs shared helper + sample guard
# ---------------------------------------------------------------------------

def test_delay_edge_kwargs():
    from sespy.data_structure import Connection
    from sespy.network import delay_edge_kwargs
    short = delay_edge_kwargs(Connection(source="A", target="B", polarity="+", delay="short"))
    assert short["dashes"] is True
    assert short["title"] == "+ · short"
    imm = delay_edge_kwargs(Connection(source="A", target="B", polarity="+", delay="immediate"))
    assert imm["dashes"] is False
    assert imm["title"] == "+ · immediate"
    neg = delay_edge_kwargs(Connection(source="A", target="B", polarity="-", delay="long"))
    assert neg["dashes"] is True
    assert neg["title"] == "- · long"


def test_sample_has_a_delayed_connection(isa):
    from sespy.constants import normalize_delay
    delayed = sum(1 for c in isa.connections if normalize_delay(c.delay) != "immediate")
    assert delayed >= 1, "sample lost its seeded delayed edge"


# ---------------------------------------------------------------------------
# Task 1 (quadrant): axis_threshold, influence_dependence(split=), influence_skew
# ---------------------------------------------------------------------------

def test_axis_threshold():
    assert network.axis_threshold([1, 2, 3, 4], "mean") == 2.5
    assert network.axis_threshold([1, 2, 3, 4], "median") == 2.5
    assert network.axis_threshold([1, 2, 3, 100], "mean") == 26.5
    assert network.axis_threshold([1, 2, 3, 100], "median") == 2.5  # robust to outlier


def test_influence_dependence_default_is_mean(isa):
    assert network.influence_dependence(isa) == network.influence_dependence(isa, split="mean")


def test_influence_dependence_median_reclassifies_sample(isa):
    mean_q = network.influence_dependence(isa, split="mean")
    med_q = network.influence_dependence(isa, split="median")
    # Empirically verified on data/sample_ses.json (mean_inf 12.18, median_inf 12.0).
    # D001 influence == 12.0 == median_inf — the >= tie-rule boundary node; if the
    # sample changes so this no longer holds, re-derive a new pinned node (do NOT
    # delete this assertion).
    assert mean_q["D001"]["quadrant"] == "buffering"
    assert med_q["D001"]["quadrant"] == "active"
    assert any(mean_q[k]["quadrant"] != med_q[k]["quadrant"] for k in mean_q)


def _skew_fixture():
    """isa where node 'A' has 4 strong out-edges (influence 12) and each of
    B,C,D,E has 1 weak out-edge (influence 1) → nz=[12,1,1,1,1], max 12 > 3·1."""
    from sespy.data_structure import Connection, Element, IsaData
    els = [Element(id=i, label=i, type="Drivers") for i in ("A", "B", "C", "D", "E")]
    conns = [Connection(source="A", target=t, strength="strong", confidence=1)
             for t in ("B", "C", "D", "E")]
    conns += [Connection(source=s, target="A", strength="weak", confidence=1)
              for s in ("B", "C", "D", "E")]
    return IsaData(elements=els, connections=conns)


def test_influence_skew_true_on_hub():
    assert network.influence_skew(_skew_fixture()) is True


def test_influence_skew_false_balanced():
    from sespy.data_structure import Connection, Element, IsaData
    els = [Element(id=i, label=i, type="Drivers") for i in ("A", "B", "C")]
    conns = [Connection(source="A", target="B", strength="medium", confidence=1),
             Connection(source="B", target="C", strength="medium", confidence=1),
             Connection(source="C", target="A", strength="medium", confidence=1)]
    assert network.influence_skew(IsaData(elements=els, connections=conns)) is False


def test_influence_skew_false_boundary():
    # nz = [6, 2, 2, 2]: max 6 == 3*median 2 -> strict '>' is False.
    from sespy.data_structure import Connection, Element, IsaData
    els = [Element(id=i, label=i, type="Drivers") for i in ("H", "B", "C", "D", "S")]
    conns = [
        Connection(source="H", target="S", strength="strong", confidence=2),  # H influence 6
        Connection(source="B", target="S", strength="medium", confidence=1),  # B influence 2
        Connection(source="C", target="S", strength="medium", confidence=1),  # C influence 2
        Connection(source="D", target="S", strength="medium", confidence=1),  # D influence 2
    ]
    assert network.influence_skew(IsaData(elements=els, connections=conns)) is False


def test_influence_skew_false_empty():
    from sespy.data_structure import IsaData
    assert network.influence_skew(IsaData()) is False


def test_influence_skew_false_on_default_sample(isa):
    # The shipped sample is NOT skew-flagged: max influence 23 ≯ 3·median 12.
    # This pins the e2e's premise that the skew caption does NOT show on the
    # default view (so the e2e correctly does not assert the caption).
    assert network.influence_skew(isa) is False


# ---------------------------------------------------------------------------
# Task 1 (D2D MC): perturbation primitives
# ---------------------------------------------------------------------------

def _isa(conns):
    """Build an IsaData whose elements are exactly the ids referenced by conns."""
    ids = sorted({c.source for c in conns} | {c.target for c in conns})
    els = [Element(id=i, label=i, type="pressure") for i in ids]
    return IsaData(elements=els, connections=conns)


def test_perturb_prob_endpoints():
    assert network._perturb_prob(5, 0.5) == 0.0
    assert network._perturb_prob(1, 0.5) == 0.5
    assert network._perturb_prob(3, 0.5) == 0.25
    # confidence clamps to [1, 5]
    assert network._perturb_prob(9, 0.5) == 0.0
    assert network._perturb_prob(0, 0.5) == 0.5


def test_perturbed_connections_certain_graph_never_changes():
    conns = [Connection("A", "B", polarity="+", confidence=5),
             Connection("B", "A", polarity="-", confidence=5)]
    isa = _isa(conns)
    rng = np.random.default_rng(0)
    for _ in range(200):
        out = network._perturbed_connections(isa, 0.5, rng)
        assert {(c.source, c.target, c.polarity) for c in out} == {
            ("A", "B", "+"), ("B", "A", "-")}


def test_perturbed_connections_low_confidence_drops_and_flips():
    conns = [Connection("A", "B", polarity="+", confidence=1),
             Connection("B", "A", polarity="+", confidence=1)]
    isa = _isa(conns)
    rng = np.random.default_rng(0)
    saw_drop = saw_flip = False
    for _ in range(500):
        out = network._perturbed_connections(isa, 0.5, rng)
        if len(out) < 2:
            saw_drop = True
        if any(c.polarity == "-" for c in out):
            saw_flip = True
    assert saw_drop and saw_flip


# ---------------------------------------------------------------------------
# Task 2 (D2D MC): uncertainty_scores aggregation
# ---------------------------------------------------------------------------

def test_uncertainty_regression_anchor_certain_graph():
    # All confidence-5 -> p=0 -> every draw equals the point estimate.
    conns = [Connection("A", "B", polarity="+", confidence=5),
             Connection("B", "C", polarity="-", confidence=5),
             Connection("C", "A", polarity="+", confidence=5)]
    isa = _isa(conns)
    point = network.leverage_scores(isa)
    res = network.uncertainty_scores(isa, n_samples=50, seed=1)
    for nid, lev in res["leverage"].items():
        assert lev["std"] == 0.0
        assert lev["mean"] == point[nid]
        assert lev["ci_low"] == lev["ci_high"] == point[nid]
    assert len(res["loops"]) == 1
    loop = res["loops"][0]
    assert loop["existence_prob"] == 1.0
    # A->B(+), B->C(-), C->A(+): one negative edge -> Balancing.
    assert loop["balancing_prob"] == 1.0
    assert loop["reinforcing_prob"] == 0.0
    assert loop["contested"] is False


def test_uncertainty_empty_graph():
    res = network.uncertainty_scores(IsaData(), n_samples=10, seed=0)
    assert res == {"n_samples": 10, "leverage": {}, "loops": []}


def test_uncertainty_no_cycles():
    conns = [Connection("A", "B", polarity="+", confidence=3)]
    res = network.uncertainty_scores(_isa(conns), n_samples=20, seed=0)
    assert res["loops"] == []
    assert set(res["leverage"]) == {"A", "B"}


def test_uncertainty_deterministic_seed():
    conns = [Connection("A", "B", polarity="+", confidence=1),
             Connection("B", "A", polarity="+", confidence=1)]
    isa = _isa(conns)
    a = network.uncertainty_scores(isa, n_samples=100, seed=7)
    b = network.uncertainty_scores(isa, n_samples=100, seed=7)
    c = network.uncertainty_scores(isa, n_samples=100, seed=8)
    assert a == b
    assert a != c


def test_uncertainty_low_confidence_widens_and_lowers_existence():
    conns = [Connection("A", "B", polarity="+", confidence=1),
             Connection("B", "C", polarity="+", confidence=1),
             Connection("C", "A", polarity="+", confidence=1)]
    res = network.uncertainty_scores(_isa(conns), n_samples=500, seed=0)
    assert any(lev["std"] > 0 for lev in res["leverage"].values())
    assert res["loops"][0]["existence_prob"] < 1.0


def test_uncertainty_contested_loop():
    # A->B certain (+); B->A uncertain (+, conf 1). When the uncertain edge
    # survives it flips ~50% -> loop polarity ~50/50 -> contested.
    conns = [Connection("A", "B", polarity="+", confidence=5),
             Connection("B", "A", polarity="+", confidence=1)]
    res = network.uncertainty_scores(_isa(conns), n_samples=3000, seed=1)
    assert len(res["loops"]) == 1
    lp = res["loops"][0]
    assert lp["contested"] is True
    assert 0.2 <= lp["reinforcing_prob"] <= 0.8


def test_uncertainty_respects_supplied_cycles():
    conns = [Connection("A", "B", polarity="+", confidence=5),
             Connection("B", "A", polarity="+", confidence=5)]
    isa = _isa(conns)
    res = network.uncertainty_scores(isa, cycles=[["A", "B"]], n_samples=10, seed=0)
    assert [lp["nodes"] for lp in res["loops"]] == [["A", "B"]]
    assert res["loops"][0]["id"] == "L001"


# ---------------------------------------------------------------------------
# recompute_consensus
# ---------------------------------------------------------------------------

def test_recompute_consensus_empty_is_noop():
    from sespy.data_structure import Connection
    c = Connection(source="A", target="B", polarity="-", strength="strong", confidence=5, delay="long")
    out = network.recompute_consensus(c)
    assert (out.polarity, out.strength, out.confidence, out.delay) == ("-", "strong", 5, "long")
    assert out is not c  # returns a copy


def test_recompute_consensus_confidence_weighted_strength():
    from sespy.data_structure import Connection, Rating
    c = Connection(source="A", target="B", ratings=[
        Rating(rater_id="s1", strength="weak", confidence=5, polarity="+"),
        Rating(rater_id="s2", strength="strong", confidence=1, polarity="+"),
    ])
    out = network.recompute_consensus(c)
    # weighted rank = (1*5 + 3*1)/6 = 1.33 -> rank 1 -> "weak"; conf = round((5+1)/2)=3
    assert out.strength == "weak"
    assert out.confidence == 3
    assert out.polarity == "+"


def test_recompute_consensus_majority_and_tie_polarity():
    from sespy.data_structure import Connection, Rating
    maj = network.recompute_consensus(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", polarity="+"), Rating(rater_id="b", polarity="+"),
        Rating(rater_id="c", polarity="-"),
    ]))
    assert maj.polarity == "+"
    tie = network.recompute_consensus(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", polarity="+"), Rating(rater_id="b", polarity="-"),
    ]))
    assert tie.polarity == "+"  # exact tie -> "+"


def test_recompute_consensus_delay_mode():
    from sespy.data_structure import Connection, Rating
    out = network.recompute_consensus(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", delay="short"), Rating(rater_id="b", delay="short"),
        Rating(rater_id="c", delay="immediate"),
    ]))
    assert out.delay == "short"


# ---------------------------------------------------------------------------
# Task 1 (D2D C2): upsert_rating + remove_rating (rating mutation helpers)
# ---------------------------------------------------------------------------

def test_upsert_rating_adds_and_recomputes():
    from sespy.data_structure import Connection, Rating
    c = Connection(source="A", target="B")  # ratings=[]
    out = network.upsert_rating(c, Rating(rater_id="s1", strength="strong", confidence=5, polarity="+", delay="short"))
    assert len(out.ratings) == 1
    assert out.strength == "strong" and out.confidence == 5 and out.delay == "short"
    assert c.ratings == []  # input unmutated (pure)


def test_upsert_rating_replaces_same_rater():
    from sespy.data_structure import Connection, Rating
    c = network.upsert_rating(Connection(source="A", target="B"),
                              Rating(rater_id="s1", strength="weak", confidence=2, polarity="+"))
    out = network.upsert_rating(c, Rating(rater_id="s1", strength="strong", confidence=5, polarity="+"))
    assert len(out.ratings) == 1            # replaced, not duplicated
    assert out.ratings[0].strength == "strong"
    assert out.strength == "strong" and out.confidence == 5


def test_remove_rating_drops_and_recomputes():
    from sespy.data_structure import Connection, Rating
    c = Connection(source="A", target="B", ratings=[
        Rating(rater_id="s1", strength="weak", confidence=1, polarity="-"),
        Rating(rater_id="s2", strength="strong", confidence=5, polarity="+"),
    ])
    c = network.recompute_consensus(c)
    out = network.remove_rating(c, "s1")
    assert [r.rater_id for r in out.ratings] == ["s2"]
    assert out.strength == "strong" and out.polarity == "+"
    assert len(c.ratings) == 2  # input unmutated


def test_remove_last_rating_freezes_consensus():
    from sespy.data_structure import Connection, Rating
    c = network.upsert_rating(Connection(source="A", target="B"),
                              Rating(rater_id="s1", strength="strong", confidence=5, polarity="-", delay="long"))
    out = network.remove_rating(c, "s1")
    assert out.ratings == []
    # no-op recompute on empty ratings: scalars stay at last consensus
    assert (out.strength, out.confidence, out.polarity, out.delay) == ("strong", 5, "-", "long")


# connection_disagreement

def test_disagreement_polarity_split_is_contested():
    from sespy.data_structure import Connection, Rating
    d = network.connection_disagreement(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", strength="weak", confidence=2, polarity="+"),
        Rating(rater_id="b", strength="strong", confidence=5, polarity="-"),
    ]))
    assert d["polarity_contested"] is True
    assert d["strength_spread"] == 2.0   # rank 3 - rank 1
    assert d["confidence_spread"] == 3.0  # 5 - 2


def test_disagreement_unanimous_not_contested():
    from sespy.data_structure import Connection, Rating
    d = network.connection_disagreement(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", polarity="+"), Rating(rater_id="b", polarity="+"),
    ]))
    assert d["polarity_contested"] is False


def test_disagreement_under_two_ratings_is_zero():
    from sespy.data_structure import Connection, Rating
    one = network.connection_disagreement(Connection(source="A", target="B",
        ratings=[Rating(rater_id="a", polarity="-")]))
    assert one == {"polarity_contested": False, "strength_spread": 0.0, "confidence_spread": 0.0}
    none = network.connection_disagreement(Connection(source="A", target="B"))
    assert none == {"polarity_contested": False, "strength_spread": 0.0, "confidence_spread": 0.0}


# ---------------------------------------------------------------------------
# Task 1 (C3): disagreement_cell + displayed_pairs
# ---------------------------------------------------------------------------


def test_disagreement_cell_contested():
    d = {"polarity_contested": True, "strength_spread": 2.0, "confidence_spread": 3.0}
    assert network.disagreement_cell(d, contested_label="Contested") == "⚠ Contested"


def test_disagreement_cell_spread():
    d = {"polarity_contested": False, "strength_spread": 2.0, "confidence_spread": 3.0}
    assert network.disagreement_cell(d, contested_label="Contested") == "~ 2/3"


def test_disagreement_cell_spread_confidence_only():
    d = {"polarity_contested": False, "strength_spread": 0.0, "confidence_spread": 4.0}
    assert network.disagreement_cell(d, contested_label="X") == "~ 0/4"


def test_disagreement_cell_none():
    d = {"polarity_contested": False, "strength_spread": 0.0, "confidence_spread": 0.0}
    assert network.disagreement_cell(d, contested_label="Contested") == "—"


def test_disagreement_cell_from_real_connection_disagreement():
    from sespy.data_structure import Connection, Rating
    # +/- split → contested
    c = Connection(source="A", target="B", ratings=[
        Rating(rater_id="s1", polarity="+"), Rating(rater_id="s2", polarity="-")])
    assert network.disagreement_cell(network.connection_disagreement(c),
                                     contested_label="Contested") == "⚠ Contested"
    # same sign, weak vs strong → spread (strength rank 1 vs 3 → 2; confidence 3/3 → 0)
    c2 = Connection(source="A", target="B", ratings=[
        Rating(rater_id="s1", polarity="+", strength="weak", confidence=3),
        Rating(rater_id="s2", polarity="+", strength="strong", confidence=3)])
    assert network.disagreement_cell(network.connection_disagreement(c2),
                                     contested_label="X") == "~ 2/0"
    # single rating → none
    c3 = Connection(source="A", target="B", ratings=[Rating(rater_id="s1")])
    assert network.disagreement_cell(network.connection_disagreement(c3),
                                     contested_label="X") == "—"


def test_displayed_pairs_full_and_filtered_preserve_true_index():
    from sespy.data_structure import Connection, Rating
    # connections[0] is NOT contested; connections[1] IS (+/- split).
    c0 = Connection(source="A", target="B")  # no ratings → not contested
    c1 = Connection(source="B", target="C", ratings=[
        Rating(rater_id="s1", polarity="+"), Rating(rater_id="s2", polarity="-")])
    conns = [c0, c1]
    # Filter off: full list, indices intact.
    assert network.displayed_pairs(conns, contested_only=False) == [(0, c0), (1, c1)]
    # Filter on: only the contested row, and it KEEPS true index 1 (NOT 0).
    pairs = network.displayed_pairs(conns, contested_only=True)
    assert pairs == [(1, c1)]
    assert pairs[0][0] == 1  # the index-contract guarantee: displayed-row-0 → true idx 1


# ---------------------------------------------------------------------------
# Task 1 (leverage-typology): leverage_realm
# ---------------------------------------------------------------------------


def test_leverage_realm_all_dapsiwrm_types():
    expected = {
        "Drivers": "intent",
        "Activities": "design",
        "Responses": "design",
        "Marine Processes & Functioning": "feedbacks",
        "Pressures": "parameters",
        "Ecosystem Services": "parameters",
        "Goods & Benefits": "parameters",
    }
    for etype, token in expected.items():
        assert network.leverage_realm(etype) == token


def test_leverage_realm_unknown_returns_empty():
    assert network.leverage_realm("Measures") == ""
    assert network.leverage_realm("") == ""
    assert network.leverage_realm("Bogus") == ""


# ---------------------------------------------------------------------------
# Task 1 (social-ecological fit)
# ---------------------------------------------------------------------------


def test_subsystem_classifies_all_types():
    assert network.subsystem("Drivers") == "social"
    assert network.subsystem("Activities") == "social"
    assert network.subsystem("Responses") == "social"
    assert network.subsystem("Goods & Benefits") == "social"
    assert network.subsystem("Pressures") == "ecological"
    assert network.subsystem("Marine Processes & Functioning") == "ecological"
    assert network.subsystem("Ecosystem Services") == "ecological"
    assert network.subsystem("Measures") == ""
    assert network.subsystem("Bogus") == ""


def test_fit_fully_crossed():
    isa = IsaData(
        elements=[Element(id="D", label="d", type="Drivers"),
                  Element(id="P", label="p", type="Pressures")],
        connections=[Connection(source="D", target="P")],
    )
    r = network.social_ecological_fit(isa)
    assert r["cross_edges"] == 1 and r["total_edges"] == 1 and r["fit"] == 1.0
    assert r["n_social"] == 1 and r["n_ecological"] == 1 and r["n_other"] == 0


def test_fit_siloed_both_subsystems():
    isa = IsaData(
        elements=[Element(id="D", label="d", type="Drivers"),
                  Element(id="A", label="a", type="Activities"),
                  Element(id="P", label="p", type="Pressures"),
                  Element(id="ES", label="e", type="Ecosystem Services")],
        connections=[Connection(source="D", target="A"),
                     Connection(source="P", target="ES")],
    )
    r = network.social_ecological_fit(isa)
    assert r == {"n_social": 2, "n_ecological": 2, "n_other": 0,
                 "within_social_edges": 1, "within_ecological_edges": 1,
                 "cross_edges": 0, "total_edges": 2, "fit": 0.0}


def test_fit_empty_graph():
    r = network.social_ecological_fit(IsaData())
    assert r["total_edges"] == 0 and r["fit"] == 0.0


def test_fit_excludes_measures_self_loop_and_dangling():
    isa = IsaData(
        elements=[Element(id="D", label="d", type="Drivers"),
                  Element(id="M", label="m", type="Measures")],
        connections=[Connection(source="D", target="M"),   # touches unclassified → excluded
                     Connection(source="D", target="D"),   # self-loop → skipped
                     Connection(source="D", target="X")],  # dangling → skipped
    )
    r = network.social_ecological_fit(isa)
    assert r["n_other"] == 1
    assert r["total_edges"] == 0 and r["fit"] == 0.0


def test_fit_sample_golden():
    root = Path(__file__).resolve().parents[1]
    r = network.social_ecological_fit(load_sample(root / "data" / "sample_ses.json"))
    assert r["cross_edges"] == 8
    assert r["within_social_edges"] == 6
    assert r["within_ecological_edges"] == 6
    assert r["total_edges"] == 20
    assert r["n_other"] == 0
    assert round(r["fit"], 2) == 0.40


# ---------------------------------------------------------------------------
# Task 1 (loops): disagreement_aware_loop_flagging
# ---------------------------------------------------------------------------

def test_loop_polarity_contested():
    from sespy.data_structure import Connection, Element, IsaData, Rating

    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="Pressures")]

    def rating(pol):
        return Rating(rater_id=f"r{pol}", strength="medium", confidence=3,
                      polarity=pol, delay="immediate")

    # A→B carries two sign-disagreeing ratings → the loop A→B→A is contested.
    contested = IsaData(elements=els, connections=[
        Connection(source="A", target="B", polarity="+", ratings=[rating("+"), rating("-")]),
        Connection(source="B", target="A", polarity="+", ratings=[]),
    ])
    assert network.loop_polarity_contested(["A", "B"], contested) is True

    # Unanimous ratings → not contested.
    unanimous = IsaData(elements=els, connections=[
        Connection(source="A", target="B", polarity="+", ratings=[rating("+"), rating("+")]),
        Connection(source="B", target="A", polarity="+", ratings=[]),
    ])
    assert network.loop_polarity_contested(["A", "B"], unanimous) is False

    # <2 ratings → not contested.
    one = IsaData(elements=els, connections=[
        Connection(source="A", target="B", polarity="+", ratings=[rating("+")]),
        Connection(source="B", target="A", polarity="+", ratings=[]),
    ])
    assert network.loop_polarity_contested(["A", "B"], one) is False

    # A contested edge that is NOT on the loop path → not contested.
    els3 = els + [Element(id="C", label="C", type="Pressures")]
    offpath = IsaData(elements=els3, connections=[
        Connection(source="A", target="B", polarity="+", ratings=[]),
        Connection(source="B", target="A", polarity="+", ratings=[]),
        Connection(source="A", target="C", polarity="+", ratings=[rating("+"), rating("-")]),
    ])
    assert network.loop_polarity_contested(["A", "B"], offpath) is False


# ---------------------------------------------------------------------------
# governance_gap (issue #13, amended per the 2026-08-12 design review)
# ---------------------------------------------------------------------------


def _gg(elements, connections=()):
    return network.governance_gap(
        IsaData(elements=list(elements), connections=list(connections)))


def test_governance_gap_sample_golden():
    root = Path(__file__).resolve().parents[1]
    r = network.governance_gap(load_sample(root / "data" / "sample_ses.json"))
    assert r["gaps_by_type"]["Pressures"] == {"n": 3, "uncovered": ["P003"]}
    assert round(r["pressure_gap_fraction"], 3) == 0.333
    assert r["governance_orphans"] == []
    assert r["n_ecological"] == 8 and r["n_governance"] == 2
    assert r["n_unclassified"] == 0
    assert r["n_edges_considered"] == 20


def test_governance_gap_coverage_is_directed():
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="P1", label="p", type="Pressures")]
    # An ecological -> governance edge alone does NOT cover the pressure...
    r = _gg(els, [Connection(source="P1", target="R1")])
    assert r["gaps_by_type"]["Pressures"]["uncovered"] == ["P1"]
    assert r["pressure_gap_fraction"] == 1.0
    # ...adding the antiparallel governance -> ecological edge does, and the
    # pair stays two distinct directed edges (no undirected collapse).
    r = _gg(els, [Connection(source="P1", target="R1"),
                  Connection(source="R1", target="P1")])
    assert r["gaps_by_type"]["Pressures"]["uncovered"] == []
    assert r["pressure_gap_fraction"] == 0.0
    assert r["n_edges_considered"] == 2


def test_governance_gap_intent_chain_is_not_orphan():
    # R -> Drivers -> Activities -> Pressures reaches ecology only through
    # the "intent" realm; the Response must NOT be an orphan (consistency
    # with leverage_realm), while P1 stays uncovered (no DIRECT edge).
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="D1", label="d", type="Drivers"),
           Element(id="A1", label="a", type="Activities"),
           Element(id="P1", label="p", type="Pressures")]
    conns = [Connection(source="R1", target="D1"),
             Connection(source="D1", target="A1"),
             Connection(source="A1", target="P1")]
    r = _gg(els, conns)
    assert r["governance_orphans"] == []
    assert r["gaps_by_type"]["Pressures"]["uncovered"] == ["P1"]


def test_governance_gap_dead_end_response_is_orphan():
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="D1", label="d", type="Drivers"),
           Element(id="P1", label="p", type="Pressures")]
    r = _gg(els, [Connection(source="R1", target="D1")])
    assert r["governance_orphans"] == ["R1"]


def test_governance_gap_no_governance_shape():
    els = [Element(id="P1", label="p", type="Pressures")]
    r = _gg(els, [Connection(source="P1", target="P1")])  # self-loop only
    assert r["n_governance"] == 0
    assert r["n_edges_considered"] == 0
    assert r["pressure_gap_fraction"] == 1.0  # UI guards on n_governance
    assert r["governance_orphans"] == []


def test_governance_gap_no_ecological_still_reports_orphans():
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="D1", label="d", type="Drivers")]
    r = _gg(els, [Connection(source="R1", target="D1")])
    assert r["n_ecological"] == 0
    assert r["ecological_gap_fraction"] == 0.0  # never NaN
    assert r["pressure_gap_fraction"] == 0.0
    assert r["governance_orphans"] == ["R1"]


def test_governance_gap_empty_graph():
    r = network.governance_gap(IsaData())
    assert r == {
        "gaps_by_type": {},
        "pressure_gap_fraction": 0.0,
        "ecological_gap_fraction": 0.0,
        "governance_orphans": [],
        "n_ecological": 0,
        "n_governance": 0,
        "n_unclassified": 0,
        "n_edges_considered": 0,
    }


def test_governance_gap_edges_considered_definition():
    # n_edges_considered = unique directed (source, target) pairs after
    # dropping self-loops and dangling refs. Edges touching an UNTYPED node
    # still count (they are structure) — deliberately unlike
    # social_ecological_fit's total_edges, which classifies them away.
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="U1", label="u", type=""),
           Element(id="P1", label="p", type="Pressures")]
    conns = [Connection(source="R1", target="U1"),   # touches untyped: counts
             Connection(source="R1", target="U1"),   # duplicate: deduplicated
             Connection(source="U1", target="U1"),   # self-loop: skipped
             Connection(source="R1", target="X9"),   # dangling: skipped
             Connection(source="R1", target="P1")]   # counts
    r = _gg(els, conns)
    assert r["n_edges_considered"] == 2
    assert r["n_unclassified"] == 1


def test_governance_gap_measures_is_governance_forward_compat():
    # "Measures" is unreachable through every production ingress today
    # (persistent_storage.py:25 rejects it; no UI offers it). Synthetic-
    # IsaData precedent: test_fit_excludes_measures_self_loop_and_dangling.
    # Forward-compat: when the vocabulary widens, Measures must count as
    # governance, never as unclassified.
    els = [Element(id="M1", label="m", type="Measures"),
           Element(id="P1", label="p", type="Pressures")]
    r = _gg(els, [Connection(source="M1", target="P1")])
    assert r["n_governance"] == 1
    assert r["n_unclassified"] == 0
    assert r["gaps_by_type"]["Pressures"]["uncovered"] == []


# ---------------------------------------------------------------------------
# governance_actor_influence (issue #14)
# ---------------------------------------------------------------------------


def test_actor_influence_sample_golden():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    rows = network.governance_actor_influence(isa)
    # R002 dominates; R001 is peripheral (zero betweenness/eigenvector) —
    # the power-asymmetry pattern the source paper diagnoses.
    assert [r["id"] for r in rows] == ["R002", "R001"]
    assert rows[0]["label"] == "Mooring buoy program"
    assert set(rows[0]) == {"id", "label", "type", "betweenness",
                            "eigenvector", "pagerank", "influence"}
    lv = network.leverage_scores(isa)
    for r in rows:
        assert r["influence"] == lv[r["id"]]  # equal by construction
        assert r["type"] == "Responses"
    assert round(rows[0]["betweenness"], 4) == 0.0833
    assert round(rows[0]["eigenvector"], 4) == 0.3393
    assert round(rows[0]["pagerank"], 4) == 0.0592
    assert round(rows[1]["influence"], 4) == -4.0938


def test_actor_influence_no_governance_returns_empty():
    isa = IsaData(
        elements=[Element(id="P1", label="p", type="Pressures"),
                  Element(id="D1", label="d", type="Drivers")],
        connections=[Connection(source="D1", target="P1")],
    )
    assert network.governance_actor_influence(isa) == []


def test_actor_influence_empty_graph():
    assert network.governance_actor_influence(IsaData()) == []


def test_actor_influence_measures_forward_compat():
    # Synthetic-IsaData precedent for the unreachable "Measures" type
    # (see test_governance_gap_measures_is_governance_forward_compat).
    isa = IsaData(
        elements=[Element(id="M1", label="m", type="Measures"),
                  Element(id="P1", label="p", type="Pressures")],
        connections=[Connection(source="M1", target="P1")],
    )
    rows = network.governance_actor_influence(isa)
    assert [r["id"] for r in rows] == ["M1"]
    assert rows[0]["type"] == "Measures"


def test_actor_influence_tie_order_deterministic():
    # Two structurally identical Responses: equal influence, so the sort
    # must fall back to isa.elements order (R2 listed first wins).
    els = [Element(id="R2", label="b", type="Responses"),
           Element(id="R1", label="a", type="Responses"),
           Element(id="P1", label="p", type="Pressures")]
    conns = [Connection(source="R2", target="P1"),
             Connection(source="R1", target="P1")]
    rows = network.governance_actor_influence(
        IsaData(elements=els, connections=conns))
    assert [r["id"] for r in rows] == ["R2", "R1"]


def test_actor_influence_disconnected_graph_is_finite():
    import math
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="P1", label="p", type="Pressures"),
           Element(id="D1", label="d", type="Drivers")]
    rows = network.governance_actor_influence(
        IsaData(elements=els,
                connections=[Connection(source="D1", target="P1")]))
    assert len(rows) == 1
    assert all(math.isfinite(v) for v in rows[0].values()
               if isinstance(v, float))


# ---------------------------------------------------------------------------
# cascade_vulnerability (issue #15)
# ---------------------------------------------------------------------------


def _bridge_isa():
    """Two 2-cycles joined by a directed bridge: H1<->H2 -> BR -> H3<->H4."""
    els = [Element(id="H1", label="h1", type="Drivers"),
           Element(id="H2", label="h2", type="Activities"),
           Element(id="BR", label="bridge", type="Pressures"),
           Element(id="H3", label="h3", type="Marine Processes & Functioning"),
           Element(id="H4", label="h4", type="Ecosystem Services")]
    conns = [Connection(source="H1", target="H2"),
             Connection(source="H2", target="H1"),
             Connection(source="H2", target="BR"),
             Connection(source="BR", target="H3"),
             Connection(source="H3", target="H4"),
             Connection(source="H4", target="H3")]
    return IsaData(elements=els, connections=conns)


def test_cascade_sample_golden():
    root = Path(__file__).resolve().parents[1]
    r = network.cascade_vulnerability(load_sample(root / "data" / "sample_ses.json"))
    assert r["baseline"] == {"lccf": 1.0, "loop_count": 5}
    assert r["n_ranked"] == 17 and r["max_steps"] == 20
    assert len(r["steps"]) == 17
    assert r["cascade_threshold_node"] == "MPF1"
    first = r["steps"][0]
    assert first["removed_id"] == "MPF1"
    assert first["removed_label"] == "Posidonia meadows"
    assert round(first["lccf"], 4) == 0.5294
    assert first["loop_count"] == 1
    assert round(first["delta_lccf"], 4) == 0.4706
    # Steps 2-6 remove nodes outside the surviving LCC: no further drop.
    assert all(s["delta_lccf"] == 0.0 for s in r["steps"][1:6])


def test_cascade_bridge_collapse():
    r = network.cascade_vulnerability(_bridge_isa())
    assert r["baseline"] == {"lccf": 1.0, "loop_count": 2}
    assert [s["removed_id"] for s in r["steps"]] == ["H3", "BR", "H4", "H2", "H1"]
    assert r["cascade_threshold_node"] == "H3"
    assert round(r["steps"][0]["delta_lccf"], 4) == 0.4   # 1.0 -> 0.6
    assert round(r["steps"][1]["lccf"], 4) == 0.4          # BR removal
    assert r["steps"][-1]["lccf"] == 0.0                   # everything gone
    assert r["steps"][-1]["loop_count"] == 0


def test_cascade_step_cap_is_honest():
    r = network.cascade_vulnerability(_bridge_isa(), max_steps=2)
    assert len(r["steps"]) == 2
    assert r["n_ranked"] == 5 and r["max_steps"] == 2
    assert r["cascade_threshold_node"] == "H3"


def test_cascade_under_three_elements_trivial():
    for isa in (IsaData(),
                IsaData(elements=[Element(id="A", label="a", type="Drivers"),
                                  Element(id="B", label="b", type="Pressures")],
                        connections=[Connection(source="A", target="B")])):
        r = network.cascade_vulnerability(isa)
        assert r == {"baseline": {"lccf": 0.0, "loop_count": 0}, "steps": [],
                     "cascade_threshold_node": None, "n_ranked": 0,
                     "max_steps": 20}


def test_cascade_is_deterministic():
    a = network.cascade_vulnerability(_bridge_isa())
    b = network.cascade_vulnerability(_bridge_isa())
    assert a == b


def test_cascade_removal_follows_leverage_ranking():
    isa = _bridge_isa()
    lev = network.leverage_scores(isa)
    order = {el.id: i for i, el in enumerate(isa.elements)}
    expected = [el.id for el in sorted(isa.elements,
                                       key=lambda el: (-lev[el.id], order[el.id]))]
    r = network.cascade_vulnerability(isa)
    assert [s["removed_id"] for s in r["steps"]] == expected


# ---------------------------------------------------------------------------
# causal_paths (issue #16)
# ---------------------------------------------------------------------------

_EMPTY_PATHS = {"paths": [], "counts": {"+": 0, "-": 0, "0": 0}, "truncated": False}


def test_causal_paths_sample_single_positive():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    r = network.causal_paths(isa, "D001", "P001")
    assert r["paths"] == [{"path": ["D001", "A001", "P001"],
                           "length": 2, "polarity": "+"}]
    assert r["counts"] == {"+": 1, "-": 0, "0": 0}
    assert r["truncated"] is False


def test_causal_paths_sample_two_negative_sorted():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    r = network.causal_paths(isa, "ES02", "D001")
    assert [p["path"] for p in r["paths"]] == [
        ["ES02", "GB02", "D002", "A003", "P003", "MPF1", "ES01", "GB01", "D001"],
        ["ES02", "GB02", "D002", "A003", "P003", "MPF1", "ES03", "GB01", "D001"],
    ]
    assert all(p["polarity"] == "-" and p["length"] == 8 for p in r["paths"])
    assert r["counts"] == {"+": 0, "-": 2, "0": 0}


def test_causal_paths_sample_no_route():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    assert network.causal_paths(isa, "D001", "ES02") == _EMPTY_PATHS


def test_causal_paths_truncation_is_honest():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    r = network.causal_paths(isa, "ES02", "D001", max_paths=1)
    assert len(r["paths"]) == 1
    assert r["truncated"] is True


def test_causal_paths_diamond_polarity():
    # A->B->D (one negative hop) and A->C->D (all positive): the compound
    # sign differs per route, and counts reflect both.
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABCD"]
    conns = [Connection(source="A", target="B", polarity="-"),
             Connection(source="B", target="D", polarity="+"),
             Connection(source="A", target="C", polarity="+"),
             Connection(source="C", target="D", polarity="+")]
    r = network.causal_paths(IsaData(elements=els, connections=conns), "A", "D")
    by_route = {tuple(p["path"]): p["polarity"] for p in r["paths"]}
    assert by_route == {("A", "B", "D"): "-", ("A", "C", "D"): "+"}
    assert r["counts"] == {"+": 1, "-": 1, "0": 0}


def test_causal_paths_even_negatives_are_positive():
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABC"]
    conns = [Connection(source="A", target="B", polarity="-"),
             Connection(source="B", target="C", polarity="-")]
    r = network.causal_paths(IsaData(elements=els, connections=conns), "A", "C")
    assert r["paths"][0]["polarity"] == "+"  # two negatives multiply out


def test_causal_paths_unsigned_hop_is_ambiguous():
    # Forward-looking: no current ingress emits a polarity outside {+,-},
    # but the sign arithmetic must not silently misread one.
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABC"]
    conns = [Connection(source="A", target="B", polarity=""),
             Connection(source="B", target="C", polarity="-")]
    r = network.causal_paths(IsaData(elements=els, connections=conns), "A", "C")
    assert r["paths"][0]["polarity"] == "0"
    assert r["counts"] == {"+": 0, "-": 0, "0": 1}


def test_causal_paths_degenerate_inputs():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    assert network.causal_paths(isa, "NOPE", "D001") == _EMPTY_PATHS
    assert network.causal_paths(isa, "D001", "NOPE") == _EMPTY_PATHS
    assert network.causal_paths(isa, "D001", "D001") == _EMPTY_PATHS
    assert network.causal_paths(IsaData(), "A", "B") == _EMPTY_PATHS


def test_causal_paths_cycles_yield_simple_paths_only():
    # A->B->A cycle plus B->C: only the simple path A->B->C may appear.
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABC"]
    conns = [Connection(source="A", target="B"),
             Connection(source="B", target="A"),
             Connection(source="B", target="C")]
    r = network.causal_paths(IsaData(elements=els, connections=conns), "A", "C")
    assert [p["path"] for p in r["paths"]] == [["A", "B", "C"]]


def test_causal_paths_deterministic():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    assert network.causal_paths(isa, "ES02", "D001") == \
        network.causal_paths(isa, "ES02", "D001")


def test_causal_paths_unreachable_on_dense_graph_is_fast():
    # No-route pair on a dense digraph: without reachability pruning,
    # all_simple_paths explores ~degree^max_length dead-end prefixes.
    # With pruning this returns the empty shape in milliseconds; a
    # regression makes this test hang rather than fail.
    import random
    rng = random.Random(11)
    els = [Element(id=f"N{i}", label=f"n{i}", type="Drivers") for i in range(60)]
    els.append(Element(id="ISOLATED", label="iso", type="Pressures"))
    conns = [Connection(source=f"N{i}", target=f"N{j}")
             for i in range(60) for j in range(60)
             if i != j and rng.random() < 0.3]
    r = network.causal_paths(IsaData(elements=els, connections=conns),
                             "N0", "ISOLATED")
    assert r == _EMPTY_PATHS


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
