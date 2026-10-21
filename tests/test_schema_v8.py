"""P1b — schema v8: version 1.15.0, the v8 min-reader floor (spec §4.1)."""
from __future__ import annotations

from sespy import data_structure
from sespy.data_structure import (
    PROJECT_SCHEMA_VERSION,
    SCHEMA_MIN_READER,
    IsaData,
    Project,
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
