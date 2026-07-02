"""Unit tests for optional DAPSIWRM assignment on QSEM import."""
from sespy.qsem_import import build_project, qsem_to_isa


def _canvas(nodes, links=None):
    return {"canvas": {"nodes": nodes, "links": links or []}}


def test_theme_map_none_is_unchanged():
    data = _canvas([{"id": "a", "label": "A", "theme": "Ecosystem Services"},
                    {"id": "b", "label": "B", "theme": "OWFs"}])
    els, _ = qsem_to_isa(data)  # no map
    by_label = {e.label: e for e in els}
    assert by_label["A"].type == "Ecosystem Services"   # exact DAPSIWRM match
    assert by_label["B"].type == ""                     # non-DAPSIWRM -> untyped
    assert by_label["B"].description == "Theme: OWFs"    # annotation retained


def test_theme_map_applies_and_description_keys_off_resolved_type():
    data = _canvas([{"id": "b", "label": "B", "theme": "OWFs"}])
    els, _ = qsem_to_isa(data, {"OWFs": "Activities"})
    assert els[0].type == "Activities"
    assert els[0].description == ""     # typed via map -> NO "Theme: OWFs"


def test_theme_map_untyped_value_and_coercion():
    data = _canvas([{"id": "b", "label": "B", "theme": "OWFs"},
                    {"id": "c", "label": "C", "theme": "LWB"}])
    els, _ = qsem_to_isa(data, {"OWFs": "", "LWB": "NotAType"})
    by_label = {e.label: e for e in els}
    assert by_label["B"].type == ""                    # "" -> untyped
    assert by_label["B"].description == "Theme: OWFs"   # untyped -> annotated
    assert by_label["C"].type == ""                    # bogus value coerced to ""


def test_build_project_names_and_validates():
    data = _canvas([{"id": "a", "label": "A", "theme": "OWFs"}])
    res = build_project(data, "MyModel", {"OWFs": "Activities"})
    assert res.valid and res.project is not None
    assert res.project.metadata.name == "MyModel"
    assert res.project.isa_data.elements[0].type == "Activities"
