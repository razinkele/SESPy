"""Every full-graph edge builder applies the shared delay cue (dashes)."""
from sespy.data_structure import Element, Connection, IsaData, Rating
from sespy.modules.cld_visualization import _build_pyvis_network
from sespy.modules.analysis_leverage import _build_leverage_network
from sespy.modules.analysis_metrics import _build_metrics_network
from sespy.modules.analysis_simplify import _build_simplified_network
from sespy.modules.analysis_intervention import _build_intervention_network


def _fixture():
    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="B", polarity="+", delay="short"),      # delayed
             Connection(source="B", target="A", polarity="-", delay="immediate")]  # not
    return IsaData(elements=els, connections=conns)


def _dashes_by_edge(net):
    nodes, edges, *_ = net.get_network_data()
    return {(e["from"], e["to"]): e.get("dashes") for e in edges}


def test_every_builder_dashes_the_delayed_edge():
    isa = _fixture()
    builders = [
        _build_pyvis_network(isa, layout_kind="physics", direction="UD",
                             level_sep=150, node_sp=120, size_scale=1.0, font_scale=1.0),
        _build_leverage_network(isa, {"A": 1.0, "B": 0.5}),
        _build_metrics_network(isa, "degree", {"A": 2.0, "B": 1.0}),
        _build_simplified_network(isa),
        # intervention reads info['before']/['after']/['delta'] per surviving
        # node, so pass a complete impact dict (removed_ids empty = nothing ablated).
        _build_intervention_network(
            isa,
            {"A": {"before": 0.0, "after": 0.0, "delta": 0.0},
             "B": {"before": 0.0, "after": 0.0, "delta": 0.0}},
            [],
        ),
    ]
    for net in builders:
        d = _dashes_by_edge(net)
        assert d[("A", "B")] is True, f"delayed edge not dashed in {net}"
        assert d[("B", "A")] is False, f"immediate edge wrongly dashed in {net}"


def test_contested_edge_is_styled():
    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="State")]
    contested = Connection(
        source="A", target="B", polarity="+", delay="immediate",
        ratings=[Rating(rater_id="r1", strength="medium", confidence=3, polarity="+", delay="immediate"),
                 Rating(rater_id="r2", strength="medium", confidence=3, polarity="-", delay="immediate")],
    )
    plain = Connection(source="B", target="A", polarity="-", delay="immediate")  # <2 ratings
    isa = IsaData(elements=els, connections=[contested, plain])
    net = _build_pyvis_network(isa, layout_kind="physics", direction="UD",
                               level_sep=150, node_sp=120, size_scale=1.0, font_scale=1.0)
    _, edges, *_ = net.get_network_data()
    by = {(e["from"], e["to"]): e for e in edges}
    ce = by[("A", "B")]
    assert ce["width"] > 2 and "⚠" in ce["label"], f"contested edge not styled: {ce}"
    pe = by[("B", "A")]
    assert pe["width"] == 2 and "⚠" not in pe["label"], f"plain edge wrongly styled: {pe}"
