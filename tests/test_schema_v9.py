"""K1 — schema v9: ProjectMetadata.reference_data (spec §4.1)."""
from __future__ import annotations

import logging
from dataclasses import fields as _real_fields

from sespy import data_structure
from sespy.data_structure import (
    PROJECT_SCHEMA_VERSION,
    SCHEMA_MIN_READER,
    IsaData,
    Project,
    ProjectMetadata,
)

REF = {"ses_knowledge_db": {"version": "1.2", "sha256": "abc"}}


def _raw(**meta):
    return {"metadata": {"name": "P", **meta}, "isa_data": {"elements": [], "connections": []}}


def test_schema_9_and_floor():
    assert PROJECT_SCHEMA_VERSION == 9
    assert SCHEMA_MIN_READER[9] == "1.16.0"
    assert SCHEMA_MIN_READER[8] == "1.15.0"


def test_roundtrip_reference_data():
    p = Project.from_isa(IsaData())
    p.metadata.reference_data = REF
    d = p.to_dict()
    assert d["metadata"]["reference_data"] == REF
    assert Project.from_dict(d).metadata.reference_data == REF


def test_malformed_reference_data_dropped_with_warning(caplog):
    for bad in (["x"], {"a": "not-a-dict"}):
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=data_structure.__name__):
            p = Project.from_dict(_raw(reference_data=bad))
        assert p.metadata.reference_data == {}
        assert any("reference_data" in r.getMessage() for r in caplog.records)


def test_save_stamps_1_16_0_even_when_empty():
    d = Project.from_isa(IsaData()).to_dict()
    assert d["metadata"]["schema_version"] == 9
    assert d["metadata"]["min_sespy_version"] == "1.16.0"
    assert d["metadata"]["reference_data"] == {}


def test_v8_reader_drops_field(monkeypatch):
    def pre_k1_fields(cls):
        fs = _real_fields(cls)
        if cls is ProjectMetadata:
            fs = tuple(f for f in fs if f.name != "reference_data")
        return fs

    monkeypatch.setattr(data_structure, "fields", pre_k1_fields)
    d = Project.from_isa(IsaData()).to_dict()
    d["metadata"]["reference_data"] = REF
    p = Project.from_dict(d)
    assert p.metadata.name == "Untitled Project"
    assert p.metadata.reference_data == {}
