"""P1a — R template mapper (spec §1 done-when, §5, §6)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sespy.constants import DAPSIWRM_ELEMENTS
from sespy.persistent_storage import project_to_bytes, validate_project_payload
from sespy.r_template_mapper import (
    ConversionReport,
    convert_r_template,
    load_r_template,
)

FIXTURES = Path(__file__).resolve().parent / "parity" / "r_templates"
KEYS = ["Aquaculture", "Caribbean", "ClimateChange", "Fisheries",
        "OffshoreWind", "Pollution", "Tourism"]


def _fixture(key: str) -> dict:
    return load_r_template(FIXTURES / f"{key}_SES_Template.json")


def _edge(c) -> tuple:
    return (c.source, c.target, c.polarity, c.strength, c.confidence, c.description)


# ---- done-when (spec §1) -------------------------------------------------

@pytest.mark.parametrize("key", KEYS)
def test_r_template_survives_real_save_load(key):
    raw = _fixture(key)
    project, report = convert_r_template(raw, key=key)

    res = validate_project_payload(json.loads(project_to_bytes(project)))
    assert res.valid, res.errors
    loaded = res.project
    assert not loaded.newer_build

    expected = [(c["from_id"], c["to_id"], c["polarity"], c["strength"],
                 c["confidence"], c["description"]) for c in raw["connections"]]
    got = [_edge(c) for c in loaded.isa_data.connections]
    assert len(got) == len(expected)              # nothing dropped or merged
    assert set(got) == set(expected)
    assert report.link_count == len(expected)

    fw = raw["dapsiwrm_framework"]
    assert len(loaded.isa_data.elements) == sum(len(v) for v in fw.values())
    n_resp = len(fw.get("responses", [])) + len(fw.get("measures", []))
    assert sum(e.type == "Responses" for e in loaded.isa_data.elements) == n_resp
    assert report.counts_by_type.get("Responses", 0) == n_resp

    assert report.off_rule_links == ()
    assert report.type_mismatches == ()
    assert loaded.metadata.origin == "r_template"
    assert loaded.metadata.r_template_version == raw["metadata"]["version"]


def test_fixture_link_total_is_read_from_the_files():
    # The spec quotes 320 at v1.29.0; the done-when test never hard-codes it.
    assert sum(len(_fixture(k)["connections"]) for k in KEYS) == 320


# ---- folding, r_type, extras ----------------------------------------------

def test_measures_fold_into_responses_with_r_kind():
    raw = _fixture("Fisheries")
    project, report = convert_r_template(raw, key="Fisheries")
    measure_ids = [m["id"] for m in raw["dapsiwrm_framework"]["measures"]]
    assert measure_ids and report.folded_measures == tuple(measure_ids)
    by_id = {e.id: e for e in project.isa_data.elements}
    for mid in measure_ids:
        assert by_id[mid].type == "Responses"
        assert by_id[mid].r_extra["r_kind"] == "measure"
    for r in raw["dapsiwrm_framework"]["responses"]:
        assert "r_kind" not in by_id[r["id"]].r_extra
    assert "Measures" not in {e.type for e in project.isa_data.elements}


def test_r_type_kept_only_when_the_element_has_one():
    raw = _fixture("Caribbean")
    project, report = convert_r_template(raw, key="Caribbean")
    by_id = {e.id: e for e in project.isa_data.elements}
    for cat, items in raw["dapsiwrm_framework"].items():
        for item in items:
            el = by_id[item["id"]]
            if "type" in item:
                assert el.r_extra["r_type"] == item["type"]
            else:
                assert "r_type" not in el.r_extra
    assert "type" in report.extra_fields and "r_type" not in report.extra_fields


def test_type_comes_from_the_category_never_the_element():
    raw = _fixture("Caribbean")
    project, _ = convert_r_template(raw, key="Caribbean")
    by_id = {e.id: e for e in project.isa_data.elements}
    for p in raw["dapsiwrm_framework"]["pressures"]:
        assert by_id[p["id"]].type == "Pressures"


def test_every_r_element_field_is_kept():
    raw = _fixture("Caribbean")
    project, report = convert_r_template(raw, key="Caribbean")
    by_id = {e.id: e for e in project.isa_data.elements}
    names = set()
    for items in raw["dapsiwrm_framework"].values():
        for item in items:
            el = by_id[item["id"]]
            assert el.label == item["name"] and el.confidence == 3
            assert el.description == item.get("description", "")
            for f, v in item.items():
                if f not in ("id", "name", "description", "type"):
                    assert el.r_extra[f] == v
                    names.add(f)
    assert set(report.extra_fields) == names | {"type"}
    assert list(report.extra_fields) == sorted(report.extra_fields)


# ---- report and metadata --------------------------------------------------

def test_report_contents_fisheries():
    raw = _fixture("Fisheries")
    _, report = convert_r_template(raw, key="Fisheries")
    assert isinstance(report, ConversionReport)
    assert report.key == "Fisheries"
    assert set(report.counts_by_type) <= set(DAPSIWRM_ELEMENTS)
    assert all(v > 0 for v in report.counts_by_type.values())
    assert sum(report.counts_by_type.values()) == sum(
        len(v) for v in raw["dapsiwrm_framework"].values())
    assert report.extra_fields == ("type",)
    meta = raw["metadata"]
    assert report.template_meta == {
        "complexity": raw["complexity"],
        "version": meta["version"], "created_date": meta["created_date"],
        "source": meta["source"], "applicable_regions": meta["applicable_regions"],
        "regional_context": raw["regional_context"],
    }


def test_metadata_from_the_r_file_and_no_clock():
    raw = _fixture("Fisheries")
    p1, _ = convert_r_template(raw, key="Fisheries")
    p2, _ = convert_r_template(copy.deepcopy(raw), key="Fisheries")
    m = p1.metadata
    assert m.name == raw["template_name"]
    assert m.description == raw["template_description"]
    assert m.regional_sea == raw["regional_context"]["regional_sea"]
    assert m.created_at == m.modified_at == raw["metadata"]["created_date"]
    assert p1.to_dict() == p2.to_dict()          # deterministic


def test_caribbean_has_no_regional_sea_and_keeps_usage_notes():
    raw = _fixture("Caribbean")
    project, report = convert_r_template(raw, key="Caribbean")
    assert project.metadata.regional_sea == ""
    assert report.template_meta["usage_notes"] == raw["usage_notes"]
    assert "regional_sea" not in report.template_meta["regional_context"]


def test_connection_fields_and_delay():
    raw = _fixture("Aquaculture")
    project, _ = convert_r_template(raw, key="Aquaculture")
    assert {c.delay for c in project.isa_data.connections} == {"immediate"}


# ---- synthetic inputs: aliases, defaults, mismatches, failure modes ---------

def _tiny() -> dict:
    return {
        "template_name": "Tiny", "template_description": "d",
        "metadata": {"version": "1.0"},
        "dapsiwrm_framework": {
            "pressures": [{"id": "P1", "name": "p", "description": "", "type": "pressure"}],
            "marine_processes": [{"id": "S1", "name": "s", "description": ""}],
            "responses": [{"id": "R1", "name": "r"}],
            "measures": [{"id": "M1", "name": "m"}],
        },
        "connections": [{
            "from_id": "P1", "to_id": "S1", "from_type": "pressure",
            "to_type": "state", "polarity": "-", "strength": "strong",
            "confidence": 4, "description": "x",
        }],
    }


def test_legacy_category_aliases_are_accepted():
    t = _tiny()
    fw = t["dapsiwrm_framework"]
    fw["states"] = fw.pop("marine_processes")
    fw["impacts"] = [{"id": "E1", "name": "e"}]
    fw["welfare"] = [{"id": "G1", "name": "g"}]
    project, report = convert_r_template(t, key="Tiny")
    types = {e.id: e.type for e in project.isa_data.elements}
    assert types["S1"] == "Marine Processes & Functioning"
    assert types["E1"] == "Ecosystem Services"
    assert types["G1"] == "Goods & Benefits"


def test_canonical_key_wins_over_alias():
    t = _tiny()
    t["dapsiwrm_framework"]["states"] = [{"id": "X9", "name": "ignored"}]
    project, _ = convert_r_template(t, key="Tiny")
    assert "X9" not in {e.id for e in project.isa_data.elements}


@pytest.mark.parametrize("missing", ["polarity", "strength", "confidence", "description"])
@pytest.mark.parametrize("how", ["absent", "null"])
def test_absent_or_null_fields_take_r_defaults(missing, how):
    t = _tiny()
    if how == "absent":
        del t["connections"][0][missing]
    else:
        t["connections"][0][missing] = None
    c = convert_r_template(t, key="Tiny")[0].isa_data.connections[0]
    want = {"polarity": "+", "strength": "medium", "confidence": 3, "description": ""}
    assert getattr(c, missing) == want[missing]


@pytest.mark.parametrize("given,want", [(0, 1), (9, 5), (2, 2)])
def test_confidence_is_clamped(given, want):
    t = _tiny()
    t["connections"][0]["confidence"] = given
    assert convert_r_template(t, key="Tiny")[0].isa_data.connections[0].confidence == want


def test_measure_to_response_link_becomes_extension_not_off_rule():
    t = _tiny()
    t["connections"].append({"from_id": "M1", "to_id": "R1",
                             "from_type": "measure", "to_type": "response"})
    _, report = convert_r_template(t, key="Tiny")
    assert report.off_rule_links == ()
    assert report.type_mismatches == ()        # 'measure' matches the pre-fold category


def test_off_rule_links_are_reported_not_raised():
    t = _tiny()
    t["connections"].append({"from_id": "S1", "to_id": "P1"})   # MPF -> P
    project, report = convert_r_template(t, key="Tiny")
    assert report.off_rule_links == (("S1", "P1"),)
    assert len(project.isa_data.connections) == 2


def test_type_mismatch_is_reported_not_raised():
    t = _tiny()
    t["connections"][0]["to_type"] = "impact"
    _, report = convert_r_template(t, key="Tiny")
    assert report.type_mismatches == (
        "connections[0] P1->S1: to_type 'impact' vs category 'marine_processes'",)


@pytest.mark.parametrize("mutate,match", [
    (lambda t: t["connections"][0].update(to_id="NOPE"), r"Tiny.*NOPE"),
    (lambda t: t["dapsiwrm_framework"]["responses"].append({"id": "P1", "name": "dup"}),
     r"Tiny.*duplicate element id 'P1'"),
    (lambda t: t["connections"].append(dict(t["connections"][0], polarity="+")),
     r"Tiny.*P1->S1.*duplicate link"),
    (lambda t: t["connections"][0].update(to_id="P1"), r"Tiny.*self-loop"),
    (lambda t: t["connections"][0].update(polarity="positive"), r"Tiny.*'positive'"),
    (lambda t: t["connections"][0].update(strength="very strong"), r"Tiny.*'very strong'"),
    (lambda t: t["connections"][0].update(strength="Strong"), r"Tiny.*'Strong'"),
    (lambda t: t["connections"][0].update(confidence="4"), r"Tiny.*confidence"),
    (lambda t: t["connections"][0].update(confidence=4.5), r"Tiny.*confidence"),
    (lambda t: t["connections"][0].update(confidence=True), r"Tiny.*confidence"),
    (lambda t: t["connections"][0].update(description=7), r"Tiny.*description"),
    (lambda t: t["dapsiwrm_framework"].update(drivers={"id": "D1"}), r"Tiny.*'drivers' is not a list"),
    (lambda t: t["dapsiwrm_framework"]["responses"].append({"name": "no id"}), r"Tiny.*no id or name"),
    (lambda t: t["dapsiwrm_framework"]["responses"].append({"id": "R9"}), r"Tiny.*no id or name"),
])
def test_failure_modes_raise_value_error(mutate, match):
    t = _tiny()
    mutate(t)
    with pytest.raises(ValueError, match=match):
        convert_r_template(t, key="Tiny")


def test_legacy_format_is_rejected():
    with pytest.raises(ValueError, match="unsupported legacy R template format"):
        convert_r_template({"template_info": {}, "elements": []}, key="Old")


def test_load_r_template_tolerates_bom_and_crlf(tmp_path):
    p = tmp_path / "t.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(_tiny(), indent=2).replace("\n", "\r\n").encode("utf-8"))
    assert load_r_template(p) == _tiny()


def test_mapper_imports_without_shiny():
    import subprocess
    import sys
    code = ("import sys, sespy.r_template_mapper; "
            "sys.exit(1 if 'shiny' in sys.modules else 0)")
    root = Path(__file__).resolve().parents[1]
    assert subprocess.run([sys.executable, "-c", code], cwd=root).returncode == 0
