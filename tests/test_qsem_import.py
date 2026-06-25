"""Unit + integration tests for the .qsem JSON importer."""
from __future__ import annotations

import json

from sespy import constants
from sespy.qsem_import import parse_qsem, qsem_to_isa, qsem_delay_to_level


def _node(nid, label, **extra):
    return {"id": nid, "label": label, **extra}


def _link(src, tgt, **extra):
    return {"sourceNodeId": src, "targetNodeId": tgt, **extra}


def test_qsem_delay_to_level_boundaries():
    assert qsem_delay_to_level(-1) == "immediate"
    assert qsem_delay_to_level(0) == "immediate"
    assert qsem_delay_to_level(1) == "short"
    assert qsem_delay_to_level(2) == "long"
    assert qsem_delay_to_level(3) == "long"
    # Guard: documents why a custom fn exists — normalize_delay flattens 2 -> "short".
    assert constants.normalize_delay(2) == "short"


def test_qsem_to_isa_node_and_link_mapping():
    data = {"canvas": {"nodes": [
        _node("n1", "Fish stock", theme="Ecosystem Services"),   # exact -> type
        _node("n2", "OWF installation", theme="OWFs"),           # unmapped -> "" + desc
        _node("n3", "Some factor"),                              # no theme key at all
        _node("n4", "Dup label"),
        _node("n5", "Dup label"),                                # duplicate label
    ], "links": [
        _link("n1", "n2", polarity="positive", impact=3, delay=1),
        _link("n2", "n3", polarity="negative", impact=1, delay=0),
        _link("n3", "n4", polarity="positive", impact=2, delay=2),
        _link("n4", "n4", polarity="positive", impact=2),        # self-loop -> skip
        _link("n5", "ZZZ", polarity="positive", impact=2),       # dangling -> skip
    ]}}
    elements, connections = qsem_to_isa(data)

    assert [e.id for e in elements] == ["N001", "N002", "N003", "N004", "N005"]
    by_id = {e.id: e for e in elements}
    assert by_id["N001"].type == "Ecosystem Services" and by_id["N001"].description == ""
    assert by_id["N002"].type == "" and by_id["N002"].description == "Theme: OWFs"
    assert by_id["N003"].type == "" and by_id["N003"].description == ""
    assert by_id["N004"].label == by_id["N005"].label == "Dup label"

    pairs = {(c.source, c.target): c for c in connections}
    assert set(pairs) == {("N001", "N002"), ("N002", "N003"), ("N003", "N004")}
    assert pairs[("N001", "N002")].polarity == "+"
    assert pairs[("N001", "N002")].strength == "strong"
    assert pairs[("N001", "N002")].delay == "short"
    assert pairs[("N002", "N003")].polarity == "-"
    assert pairs[("N002", "N003")].strength == "weak"
    assert pairs[("N002", "N003")].delay == "immediate"
    assert pairs[("N003", "N004")].strength == "medium"
    assert pairs[("N003", "N004")].delay == "long"


def test_qsem_to_isa_skips_ghosts_and_redirects_links():
    data = {"canvas": {"nodes": [
        _node("real", "Heat emission", theme="OWFs"),
        _node("ghost", "Heat emission", isGhost=True, originalNodeId="real"),
        _node("other", "Seagrass"),
    ], "links": [
        _link("ghost", "other", polarity="positive", impact=2, delay=1),  # from a ghost
    ]}}
    elements, connections = qsem_to_isa(data)
    assert [e.label for e in elements] == ["Heat emission", "Seagrass"]
    assert [e.id for e in elements] == ["N001", "N002"]
    assert len(connections) == 1
    assert connections[0].source == "N001" and connections[0].target == "N002"


def test_qsem_to_isa_ghost_self_loop_is_skipped():
    """A link ghost→originalNodeId resolves to src==tgt and must be dropped."""
    data = {"canvas": {"nodes": [
        _node("real", "Fish stock"),
        _node("ghost", "Fish stock", isGhost=True, originalNodeId="real"),
    ], "links": [
        _link("ghost", "real", polarity="positive", impact=2, delay=0),  # ghost→its origin
    ]}}
    elements, connections = qsem_to_isa(data)
    assert [e.id for e in elements] == ["N001"]   # ghost not imported
    assert connections == []                        # self-loop after redirect → skipped


def test_parse_qsem_integration(tmp_path):
    data = {"canvas": {"nodes": [
        _node("a", "A", theme="Ecosystem Services"),
        _node("b", "B"),
        _node("c", "C"),
    ], "links": [
        _link("a", "b", polarity="negative", impact=3, delay=2),
        _link("b", "c", polarity="positive", impact=1, delay=1),
        _link("c", "ZZ", polarity="positive", impact=2),  # dangling -> skipped
    ]}}
    f = tmp_path / "sample.qsem"
    f.write_text(json.dumps(data), encoding="utf-8")
    result = parse_qsem(f)
    assert result.valid, result.errors
    proj = result.project
    assert proj is not None
    assert proj.isa_data.element_count() == 3
    assert proj.isa_data.connection_count() == 2
    ab = {(c.source, c.target): c for c in proj.isa_data.connections}[("N001", "N002")]
    assert ab.polarity == "-" and ab.strength == "strong" and ab.delay == "long"


def test_parse_qsem_rejects_non_json(tmp_path):
    f = tmp_path / "bad.qsem"
    f.write_text("this is not json {{{", encoding="utf-8")
    result = parse_qsem(f)
    assert not result.valid
    assert any("QSEM/JSON" in e for e in result.errors)


def test_parse_qsem_rejects_missing_canvas_nodes(tmp_path):
    f = tmp_path / "nocanvas.qsem"
    f.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    result = parse_qsem(f)
    assert not result.valid
    assert any("canvas.nodes" in e for e in result.errors)


def test_parse_qsem_rejects_empty_nodes(tmp_path):
    f = tmp_path / "empty.qsem"
    f.write_text(json.dumps({"canvas": {"nodes": [], "links": []}}), encoding="utf-8")
    result = parse_qsem(f)
    assert not result.valid
    assert any("no nodes" in e for e in result.errors)


def test_qsem_to_isa_tolerates_non_dict_members():
    """Non-dict nodes/links (from a hostile .json) are skipped, not crashed on."""
    data = {"canvas": {
        "nodes": [None, "garbage", _node("a", "A"), {"no": "id"}],
        "links": [None, "x", _link("a", "a")],  # the real link is a self-loop -> skipped
    }}
    elements, connections = qsem_to_isa(data)  # must not raise
    assert [e.label for e in elements] == ["A", ""]   # the two dict nodes; "no id" -> label ""
    assert connections == []


def test_parse_upload_dispatches_by_extension(tmp_path):
    # The dispatch keys off the ORIGINAL filename, not the temp datapath.
    from sespy.modules.import_data import parse_upload

    data = {"canvas": {"nodes": [{"id": "a", "label": "A"}], "links": []}}
    f = tmp_path / "model.qsem"
    f.write_text(json.dumps(data), encoding="utf-8")

    # .qsem name -> parse_qsem -> valid (1 node, 0 connections)
    qsem_result = parse_upload("model.qsem", f)
    assert qsem_result.valid, qsem_result.errors
    assert qsem_result.project.isa_data.element_count() == 1
    # project is named after the original upload, not Shiny's temp datapath stem
    assert qsem_result.project.metadata.name == "model"

    # same JSON bytes but a .xlsx name -> parse_excel -> invalid (not a real xlsx)
    xlsx_result = parse_upload("model.xlsx", f)
    assert not xlsx_result.valid
