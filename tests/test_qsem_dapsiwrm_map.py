"""Unit tests for optional DAPSIWRM assignment on QSEM import."""
import json
from pathlib import Path

import pytest

from sespy.qsem_import import build_project, qsem_themes, qsem_to_isa


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


_MODELS_DIR = Path(
    r"C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\NiD4OCEAN"
    r"\DST\social ecological system map\Social ecological systems map"
)


def test_qsem_themes_counts_and_untyped_and_ghosts():
    data = _canvas([
        {"id": "a", "label": "A", "theme": "OWFs"},
        {"id": "b", "label": "B", "theme": "OWFs"},
        {"id": "c", "label": "C"},                       # missing theme -> ""
        {"id": "d", "label": "D", "theme": None},        # None -> ""
        {"id": "g", "label": "G", "theme": "OWFs", "isGhost": True},  # excluded
        "not-a-dict",                                    # excluded
    ])
    themes = dict(qsem_themes(data))
    assert themes["OWFs"] == 2       # ghost + non-dict excluded
    assert themes[""] == 2           # missing + None collapse to ""


@pytest.mark.skipif(not _MODELS_DIR.is_dir(), reason="external models absent")
def test_qsem_themes_keyset_matches_qsem_to_isa():
    for f in _MODELS_DIR.glob("*.qsem"):
        data = json.loads(f.read_text(encoding="utf-8"))
        theme_keys = {t for t, _ in qsem_themes(data)}
        # themes qsem_to_isa actually normalizes from canonical nodes
        canon = [n for n in data["canvas"]["nodes"]
                 if isinstance(n, dict) and not n.get("isGhost")]
        seen = {(n.get("theme") or "") for n in canon}
        assert theme_keys == seen, f.name


def test_suggest_known_themes():
    from sespy.qsem_import import suggest_dapsiwrm_map

    m = suggest_dapsiwrm_map([
        "OWFs", "Environmental pressures", "Ecosystem components",
        "Policy", "Food web", "Ecosystem Services", "LWB", "NiD", "",
    ])
    assert m["OWFs"] == "Activities"
    assert m["Environmental pressures"] == "Pressures"
    assert m["Ecosystem components"] == "Marine Processes & Functioning"
    assert m["Policy"] == "Responses"
    assert m["Food web"] == "Marine Processes & Functioning"
    assert m["Ecosystem Services"] == "Ecosystem Services"  # exact match first
    assert m["NiD"] == "Responses"      # exact abbreviation lookup (user-confirmed)
    assert m["LWB"] == "" and m[""] == ""


def test_suggest_ordering_responses_before_goods():
    from sespy.qsem_import import suggest_dapsiwrm_map

    # "governance" must win over the broad "good"
    assert suggest_dapsiwrm_map(["Good governance"])["Good governance"] == "Responses"


def test_suggest_abbrev_is_exact_not_substring():
    from sespy.qsem_import import suggest_dapsiwrm_map

    # exact 'NiD' -> Responses, but a word merely CONTAINING 'nid' must not match
    m = suggest_dapsiwrm_map(["NiD", "Unidentified stressors"])
    assert m["NiD"] == "Responses"
    assert m["Unidentified stressors"] == ""   # no false substring hit
