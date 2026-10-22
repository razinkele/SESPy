"""P1b — schema v8: version 1.15.0, the v8 min-reader floor (spec §4.1),
Element indicator fields (§4.3)."""
from __future__ import annotations

import json
import logging

import pytest

from sespy import data_structure
from sespy.constants import POLICY_TARGET_CODES
from sespy.data_structure import (
    INDICATOR_FIELDS,
    PROJECT_SCHEMA_VERSION,
    SCHEMA_MIN_READER,
    Element,
    IsaData,
    Project,
    ProjectMetadata,
    Stakeholder,
    _isa_from_dict,
    newer_build_info,
)

# ---- Task 1: version and schema bump ----------------------------------------


def test_schema_8_and_floor():
    assert PROJECT_SCHEMA_VERSION == 8
    assert SCHEMA_MIN_READER == {7: "1.13.0", 8: "1.15.0"}


def test_every_save_is_stamped_1_15_0():
    d = Project.from_isa(IsaData()).to_dict()
    assert d["metadata"]["schema_version"] == 8
    assert d["metadata"]["min_sespy_version"] == "1.15.0"


def test_v8_file_is_newer_build_for_a_1_14_reader(monkeypatch):
    raw = Project.from_isa(IsaData()).to_dict()
    monkeypatch.setattr(data_structure, "_running_version", lambda: "1.14.2")
    assert newer_build_info(raw) == {"min_version": "1.15.0", "running": "1.14.2"}


# ---- Task 2: Element indicator fields (spec §4.3) ----------------------------


def test_indicator_constants_match_r():
    # R ISA_INDICATOR_COLUMNS (constants.R:855), lowercased as R's JSON loader
    # does (data_structure.R:947-949); WP5_POLICY_TARGETS (constants.R:940).
    assert INDICATOR_FIELDS == ("indicator", "indicator_unit", "data_source",
                                "registry_id", "registry_version", "policy_target")
    assert POLICY_TARGET_CODES == ("kmgbf_30x30", "eu_nrr", "msfd_ges_d1",
                                   "msfd_ges_d6", "national_mpa_pct")


def test_indicator_fields_round_trip_and_omit_when_empty():
    a = Element(id="MPF1", label="x", type="Marine Processes & Functioning",
                indicator="Coral cover", indicator_unit="%", policy_target="kmgbf_30x30")
    b = Element(id="D1", label="y", type="Drivers")
    d = Project.from_isa(IsaData(elements=[a, b])).to_dict()
    e0, e1 = d["isa_data"]["elements"]
    assert e0["indicator"] == "Coral cover" and e0["policy_target"] == "kmgbf_30x30"
    assert "data_source" not in e0                       # empty -> omitted
    assert not set(INDICATOR_FIELDS) & set(e1)           # v7 element shape
    # after confidence, before r_extra, in INDICATOR_FIELDS order
    assert list(e0) == ["id", "label", "type", "description", "confidence",
                        "indicator", "indicator_unit", "policy_target"]
    back = Project.from_dict(json.loads(json.dumps(d))).isa_data.elements
    assert back[0] == a and back[1] == b


@pytest.mark.parametrize("given,want,logged", [
    (12, "12", True), (1.5, "1.5", True), (None, "", False), ("ok", "ok", False)])
def test_indicator_field_non_str_is_coerced(caplog, given, want, logged):
    raw = {"elements": [{"id": "S1", "label": "s", "type": "Marine Processes & Functioning",
                         "registry_version": given}], "connections": []}
    with caplog.at_level(logging.WARNING, logger="sespy.data_structure"):
        el = _isa_from_dict(raw).elements[0]
    assert el.registry_version == want
    msgs = [r.getMessage() for r in caplog.records]
    assert any("S1" in m and "registry_version" in m for m in msgs) is logged


def test_indicator_field_coercion(caplog):        # the plan's literal test (Task 2)
    d = Project.from_isa(IsaData(elements=[Element(id="D1", label="x", type="Drivers")])).to_dict()
    d["isa_data"]["elements"][0].update(indicator=12, indicator_unit=None)
    with caplog.at_level(logging.WARNING):
        el = Project.from_dict(d).isa_data.elements[0]
    assert (el.indicator, el.indicator_unit) == ("12", "")
    assert sum("indicator" in r.getMessage() for r in caplog.records) == 1   # the int warns, None is silent


def test_saved_r_extra_indicator_is_hoisted_on_load():
    raw = {"metadata": {"name": "P", "schema_version": 7}, "isa_data": {"elements": [
        {"id": "S1", "label": "Sargassum", "type": "Marine Processes & Functioning",
         "r_extra": {"indicator": "Volume (t/yr)", "baseline": "Minimal pre-2011"}},
        {"id": "S2", "label": "Reef", "type": "Marine Processes & Functioning",
         "indicator": "kept", "r_extra": {"indicator": "left alone"}}], "connections": []}}
    s1, s2 = Project.from_dict(raw).isa_data.elements
    assert s1.indicator == "Volume (t/yr)" and s1.r_extra == {"baseline": "Minimal pre-2011"}
    assert s2.indicator == "kept" and s2.r_extra == {"indicator": "left alone"}


def test_hoist_logs_once_per_project_with_the_count(caplog):
    raw = {"metadata": {"name": "P"}, "isa_data": {"elements": [
        {"id": f"S{i}", "label": "x", "type": "Marine Processes & Functioning",
         "r_extra": {"indicator": f"ind {i}"}} for i in (1, 2, 3)] + [
        {"id": "S4", "label": "x", "type": "Drivers", "r_extra": {"indicator": 7}},     # not a str: stays
        {"id": "S5", "label": "x", "type": "Drivers", "r_extra": {"indicator": ""}}],   # empty: stays
        "connections": []}}
    with caplog.at_level(logging.INFO, logger="sespy.data_structure"):
        els = Project.from_dict(raw).isa_data.elements
    assert [e.indicator for e in els] == ["ind 1", "ind 2", "ind 3", "", ""]
    assert els[3].r_extra == {"indicator": 7} and els[4].r_extra == {"indicator": ""}
    hoist = [r.getMessage() for r in caplog.records if "r_extra" in r.getMessage()]
    assert len(hoist) == 1 and "3" in hoist[0]


def test_indicator_fields_on_responses_survive_round_trip():
    r = Element(id="R1", label="Quota", type="Responses", indicator="TAC")
    assert Project.from_dict(Project.from_isa(IsaData(elements=[r])).to_dict()
                             ).isa_data.elements[0].indicator == "TAC"


def test_new_element_fields_are_keyword_only():
    e = Element("D1", "x", "Drivers", "d", 3)
    assert all(getattr(e, f) == "" for f in INDICATOR_FIELDS)
    with pytest.raises(TypeError):
        Element("D1", "x", "Drivers", "d", 3, "positional indicator")


# ---- Task 3: stakeholder roles (spec §4.4) ------------------------------------


def test_stakeholder_roles_round_trip():
    s = Stakeholder(id="SH001", name="Port", ne_roles="Inputters;Regulators",
                    source_id="d54:tus_07")
    blank = Stakeholder(id="SH002", name="NGO")
    d = Project(ProjectMetadata(), IsaData(), stakeholders=[s, blank]).to_dict()
    for row in d["stakeholders"]:                    # asdict: both keys always written
        assert {"ne_roles", "source_id"} <= set(row)
    assert d["stakeholders"][1]["ne_roles"] == d["stakeholders"][1]["source_id"] == ""
    back = Project.from_dict(json.loads(json.dumps(d))).stakeholders
    assert back == [s, blank]


def test_loaded_roles_are_normalised():
    raw = {"metadata": {"name": "T"}, "isa_data": {"elements": [], "connections": []},
           "stakeholders": [{"id": "SH001", "name": "X",
                             "ne_roles": "Regulators;Bogus;Inputters;Inputters"},
                            {"id": "SH002", "name": "Y", "ne_roles": ["Affectees"]},
                            {"id": "SH003", "name": "Z", "ne_roles": None}]}
    got = [s.ne_roles for s in Project.from_dict(raw).stakeholders]
    assert got == ["Inputters;Regulators", "Affectees", ""]


def test_loaded_source_id_is_coerced(caplog):
    # Task 3 Interfaces: source_id None -> "" silently, non-str -> str() with a warning.
    raw = {"metadata": {"name": "T"}, "isa_data": {"elements": [], "connections": []},
           "stakeholders": [{"id": "SH001", "name": "X", "source_id": None},
                            {"id": "SH002", "name": "Y", "source_id": 54},
                            {"id": "SH003", "name": "Z", "source_id": "d54:x"}]}
    with caplog.at_level(logging.WARNING, logger="sespy.data_structure"):
        got = [s.source_id for s in Project.from_dict(raw).stakeholders]
    assert got == ["", "54", "d54:x"]
    assert sum("source_id" in r.getMessage() for r in caplog.records) == 1


def test_stakeholder_counter_round_trip(caplog):
    p = Project(ProjectMetadata(), IsaData(), stakeholder_counter=4)
    d = p.to_dict()
    assert d["stakeholder_counter"] == 4
    assert Project.from_dict(json.loads(json.dumps(d))).stakeholder_counter == 4
    assert p.replace(stakeholders=[]).stakeholder_counter == 4            # replace() carries it
    assert "stakeholder_counter" not in Project(ProjectMetadata(), IsaData()).to_dict()   # 0 -> absent
    d.pop("stakeholder_counter")
    with caplog.at_level(logging.WARNING, logger="sespy.data_structure"):
        assert Project.from_dict(d).stakeholder_counter == 0             # v7 file: silent default
    assert not caplog.records
    d["stakeholder_counter"] = "4"
    assert Project.from_dict(d).stakeholder_counter == 4
    d["stakeholder_counter"] = "x"
    with caplog.at_level(logging.WARNING, logger="sespy.data_structure"):
        assert Project.from_dict(d).stakeholder_counter == 0
    assert sum("stakeholder_counter" in r.getMessage() for r in caplog.records) == 1


@pytest.mark.parametrize("given,want,warns", [
    (3, 3, False), (3.0, 3, False), ("3", 3, False), (" 2.9 ", 2, False),
    (True, 0, True), (None, 0, True), ("x", 0, True), (float("inf"), 0, True),
    ("nan", 0, True), ([4], 0, True)])
def test_coerce_counter(caplog, given, want, warns):
    with caplog.at_level(logging.WARNING, logger="sespy.data_structure"):
        assert data_structure._coerce_counter(given, "test") == want
    assert bool(caplog.records) is warns


def test_new_stakeholder_fields_are_keyword_only():
    s = Stakeholder("SH001", "X", "t", "s", "c", "i", "r", "HIGH", "LOW", "a", "e", "2026")
    assert (s.ne_roles, s.source_id) == ("", "")
    with pytest.raises(TypeError):
        Stakeholder("SH001", "X", "t", "s", "c", "i", "r", "HIGH", "LOW", "a", "e", "2026",
                    "Inputters")
