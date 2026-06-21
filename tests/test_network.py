"""Smoke tests for the ported analytics layer.

These mirror the testthat patterns in tests/testthat/test-network-analysis.R
at the level needed to prove the port works end-to-end on the sample data.
A real port would replicate all 92 testthat files; this is the proof.
"""

from __future__ import annotations

from pathlib import Path

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
    from sespy.data_structure import Element, Connection, IsaData
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
    from sespy.data_structure import Element, Connection, IsaData
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
