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


def test_indicator_fields_on_responses_survive_round_trip():
    r = Element(id="R1", label="Quota", type="Responses", indicator="TAC")
    assert Project.from_dict(Project.from_isa(IsaData(elements=[r])).to_dict()
                             ).isa_data.elements[0].indicator == "TAC"


def test_new_element_fields_are_keyword_only():
    e = Element("D1", "x", "Drivers", "d", 3)
    assert all(getattr(e, f) == "" for f in INDICATOR_FIELDS)
    with pytest.raises(TypeError):
        Element("D1", "x", "Drivers", "d", 3, "positional indicator")
