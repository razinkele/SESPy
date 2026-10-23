"""P1a — schema v7: Connection.description, Element.r_extra, the three new
ProjectMetadata fields, and the min_sespy_version stamp (spec §4)."""
from __future__ import annotations

import copy
import json
import logging

import pytest

from sespy.data_structure import (
    PROJECT_SCHEMA_VERSION,
    SCHEMA_MIN_READER,
    Connection,
    Element,
    IsaData,
    Project,
    ProjectMetadata,
    _isa_from_dict,
)
from sespy.persistent_storage import project_to_bytes, validate_project_payload

FLOOR = SCHEMA_MIN_READER[PROJECT_SCHEMA_VERSION]


def _isa() -> IsaData:
    return IsaData(
        elements=[
            Element("P1", "Nutrients", "Pressures",
                    r_extra={"r_type": "pressure", "category": ["a", 1]}),
            Element("M1", "Oxygen", "Marine Processes & Functioning"),
        ],
        connections=[Connection("P1", "M1", polarity="-",
                                description="Nutrients deplete oxygen")],
    )


def _payload(**meta) -> dict:
    return {
        "metadata": {"name": "P", **meta},
        "isa_data": {
            "elements": [
                {"id": "P1", "label": "p", "type": "Pressures"},
                {"id": "M1", "label": "m", "type": "Marine Processes & Functioning"},
            ],
            "connections": [{"source": "P1", "target": "M1", "polarity": "-"}],
        },
    }


# ---- constants -----------------------------------------------------------


def test_schema_min_reader_has_entry_for_current_schema():
    # A future bump without a table entry would make to_dict() raise KeyError.
    assert PROJECT_SCHEMA_VERSION in SCHEMA_MIN_READER
    assert SCHEMA_MIN_READER[7] == "1.13.0"


def test_min_reader_floor_not_newer_than_running_build():
    """A schema bump before the version bump would stamp a floor newer than
    this build, so it would flag its own saved files as newer."""
    import sespy
    from packaging.version import Version

    assert Version(FLOOR) <= Version(sespy.__version__)


def test_new_fields_are_keyword_only_with_defaults():
    # MosaicSES constructs these positionally; the new fields must not shift.
    assert Element("A", "a", "Drivers", "d", 4).r_extra == {}
    c = Connection("A", "B", "-", "weak", 2, "short", [])
    assert c.description == ""
    m = ProjectMetadata("n")
    assert (m.origin, m.r_template_version, m.min_sespy_version) == ("", "", "")
    with pytest.raises(TypeError):
        Connection("A", "B", "-", "weak", 2, "short", [], "positional desc")


# ---- round trip ----------------------------------------------------------

def test_round_trip_keeps_description_and_r_extra():
    p = Project(ProjectMetadata(name="R", origin="r_template",
                                r_template_version="2.3"), _isa())
    back = Project.from_dict(json.loads(p.to_json()))
    assert back.isa_data == p.isa_data
    assert back.isa_data.connections[0].description == "Nutrients deplete oxygen"
    assert back.isa_data.elements[0].r_extra == {"r_type": "pressure",
                                                 "category": ["a", 1]}
    assert back.metadata.origin == "r_template"
    assert back.metadata.r_template_version == "2.3"
    assert back.metadata.min_sespy_version == FLOOR


def test_round_trip_through_the_real_upload_path():
    p = Project(ProjectMetadata(name="R"), _isa())
    res = validate_project_payload(json.loads(project_to_bytes(p)))
    assert res.valid, res.errors
    assert not res.project.newer_build     # needs the commit-1 bump to 1.13.0
    assert res.project.isa_data == p.isa_data


def test_empty_description_and_r_extra_are_omitted():
    isa = IsaData([Element("A", "a", "Drivers"), Element("B", "b", "Activities")],
                  [Connection("A", "B")])
    d = Project(ProjectMetadata(), isa).to_dict()
    for el in d["isa_data"]["elements"]:
        assert "r_extra" not in el
        assert list(el) == ["id", "label", "type", "description", "confidence"]
    conn = d["isa_data"]["connections"][0]
    assert "description" not in conn
    assert list(conn) == ["source", "target", "polarity", "strength",
                          "confidence", "delay", "ratings"]


def test_new_metadata_fields_always_serialised():
    meta = Project(ProjectMetadata(), IsaData()).to_dict()["metadata"]
    assert meta["origin"] == "" and meta["r_template_version"] == ""
    assert meta["schema_version"] == PROJECT_SCHEMA_VERSION


def test_v6_file_loads():
    raw = _payload(schema_version=6)
    p = Project.from_dict(raw)
    assert p.newer_build == {}
    assert p.metadata.schema_version == PROJECT_SCHEMA_VERSION
    assert p.isa_data.connections[0].description == ""
    assert p.isa_data.elements[0].r_extra == {}
    assert validate_project_payload(raw).valid


def test_replace_keeps_description_and_r_extra():
    p = Project(ProjectMetadata(), _isa())
    q = p.replace(stakeholders=[]).with_modified_now()
    assert q.isa_data.connections[0].description == "Nutrients deplete oxygen"
    assert q.isa_data.elements[0].r_extra["r_type"] == "pressure"


def test_with_modified_now_keeps_new_metadata_fields():
    p = Project(ProjectMetadata(origin="r_template", r_template_version="2.1",
                                min_sespy_version="1.13.0"), IsaData())
    m = p.with_modified_now().metadata
    assert (m.origin, m.r_template_version, m.min_sespy_version) == \
        ("r_template", "2.1", "1.13.0")


# ---- load tolerance (_isa_from_dict) ------------------------------------

@pytest.mark.parametrize("bad", ["x", 3, ["a"], True])
def test_non_object_r_extra_dropped_with_warning(bad, caplog):
    raw = _payload()["isa_data"]
    raw["elements"][0]["r_extra"] = bad
    with caplog.at_level(logging.WARNING, logger="sespy.data_structure"):
        isa = _isa_from_dict(raw)
    assert isa.elements[0].r_extra == {}
    assert any("r_extra" in r.getMessage() for r in caplog.records)


def test_null_or_absent_r_extra_is_silent(caplog):
    raw = _payload()["isa_data"]
    raw["elements"][0]["r_extra"] = None
    with caplog.at_level(logging.WARNING, logger="sespy.data_structure"):
        isa = _isa_from_dict(raw)
    assert [e.r_extra for e in isa.elements] == [{}, {}]
    assert not [r for r in caplog.records if "r_extra" in r.getMessage()]


@pytest.mark.parametrize("given,want", [(None, ""), (7, "7"), (1.5, "1.5"),
                                        ("ok", "ok")])
def test_connection_description_coerced_on_load(given, want):
    raw = _payload()["isa_data"]
    raw["connections"][0]["description"] = given
    assert _isa_from_dict(raw).connections[0].description == want


def test_element_description_none_is_untouched():
    # P1a does not touch Element.description: None still loads as None.
    raw = _payload()["isa_data"]
    raw["elements"][0]["description"] = None
    assert _isa_from_dict(raw).elements[0].description is None


# ---- validation (SESPy upload path) -------------------------------------

@pytest.mark.parametrize("bad", [7, ["x"], {"a": 1}, True])
def test_validation_rejects_non_string_connection_description(bad):
    raw = _payload()
    raw["isa_data"]["connections"][0]["description"] = bad
    res = validate_project_payload(raw)
    assert not res.valid
    assert any("description" in e for e in res.errors)


def test_validation_skips_null_description_and_loads_it_as_empty():
    raw = _payload()
    raw["isa_data"]["connections"][0]["description"] = None
    res = validate_project_payload(raw)
    assert res.valid, res.errors
    assert res.project.isa_data.connections[0].description == ""


def test_validation_does_not_check_element_description():
    raw = _payload()
    raw["isa_data"]["elements"][0]["description"] = 42
    assert validate_project_payload(raw).valid


def test_validation_drops_bad_r_extra_but_loads():
    raw = _payload()
    raw["isa_data"]["elements"][0]["r_extra"] = "oops"
    res = validate_project_payload(raw)
    assert res.valid
    assert res.project.isa_data.elements[0].r_extra == {}


# ---- stamping --------------------------------------------------------------

def test_fresh_project_is_stamped_with_floor():
    d = Project.from_isa(IsaData()).to_dict()
    assert d["metadata"]["min_sespy_version"] == FLOOR


def test_stamp_never_lowered_for_in_memory_project():
    # Built in memory: a LOADED stamp above the running version would set
    # newer_build and take the reset branch instead.
    p = Project(ProjectMetadata(min_sespy_version="99.0.0"), IsaData())
    assert not p.newer_build
    assert p.to_dict()["metadata"]["min_sespy_version"] == "99.0.0"


def test_stamp_equal_to_floor_is_kept():
    p = Project(ProjectMetadata(min_sespy_version=FLOOR), IsaData())
    assert p.to_dict()["metadata"]["min_sespy_version"] == FLOOR


def test_older_stamp_is_raised_to_floor():
    p = Project(ProjectMetadata(min_sespy_version="1.0.0"), IsaData())
    assert p.to_dict()["metadata"]["min_sespy_version"] == FLOOR


@pytest.mark.parametrize("bad", [13, 13.0, None, True, "", "not-a-version"])
def test_unparsable_or_non_string_stamp_is_replaced(bad):
    p = Project.from_dict(_payload(min_sespy_version=bad))
    assert not p.newer_build
    assert p.to_dict()["metadata"]["min_sespy_version"] == FLOOR


def test_int_stamp_reaches_metadata_and_is_replaced():
    # Version(13) raises TypeError, not InvalidVersion: the isinstance guard
    # must run first.
    p = Project.from_dict(_payload(min_sespy_version=13))
    assert p.metadata.min_sespy_version == 13
    assert p.to_dict()["metadata"]["min_sespy_version"] == FLOOR


def test_newer_build_stamp_is_reset_on_save():
    p = Project.from_dict(_payload(schema_version=PROJECT_SCHEMA_VERSION + 1,
                                   min_sespy_version="99.0.0"))
    assert p.newer_build
    assert p.to_dict()["metadata"]["min_sespy_version"] == FLOOR
    assert p.metadata.min_sespy_version == "99.0.0"   # raw stamp kept


def test_older_format_copy_reloads_unflagged():
    flagged = Project.from_dict(_payload(min_sespy_version="99.0.0"))
    assert flagged.newer_build
    res = validate_project_payload(json.loads(project_to_bytes(flagged)))
    assert res.valid
    assert res.project.newer_build == {}


def test_to_dict_does_not_mutate_metadata():
    p = Project(ProjectMetadata(min_sespy_version=""), IsaData())
    before = copy.deepcopy(p.metadata)
    p.to_dict()
    assert p.metadata == before


def test_p0b_still_flags_a_newer_file():
    p = Project.from_dict(_payload(schema_version=PROJECT_SCHEMA_VERSION + 1))
    assert p.newer_build == {"schema": PROJECT_SCHEMA_VERSION + 1,
                             "schema_max": PROJECT_SCHEMA_VERSION}
