"""Unit tests for the project save/load layer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sespy import data_structure as ds
from sespy.persistent_storage import (
    load_project,
    project_to_bytes,
    save_project_atomic,
    validate_project_payload,
)

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_ses.json"


def test_save_load_roundtrip_preserves_isa(tmp_path):
    """Save the sample → load it back → original IsaData survives."""
    isa_before = ds.load_sample(SAMPLE)
    project = ds.Project.from_isa(isa_before, name="roundtrip-test")

    target = tmp_path / "out.json"
    save_project_atomic(project, target)
    assert target.exists()

    loaded = load_project(target)
    isa_after = loaded.isa_data

    assert isa_before.element_count() == isa_after.element_count()
    assert isa_before.connection_count() == isa_after.connection_count()
    # Spot-check the first element + first connection survived intact
    assert isa_before.elements[0].id == isa_after.elements[0].id
    assert isa_before.elements[0].label == isa_after.elements[0].label
    assert isa_before.elements[0].type == isa_after.elements[0].type
    assert isa_before.connections[0].source == isa_after.connections[0].source
    assert isa_before.connections[0].target == isa_after.connections[0].target
    assert isa_before.connections[0].polarity == isa_after.connections[0].polarity


def test_load_rejects_payload_missing_elements(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"isa_data": {"connections": []}}))
    with pytest.raises(ValueError) as exc:
        load_project(bad)
    assert "elements" in str(exc.value)


def test_load_rejects_dangling_connection(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "metadata": {"name": "x"},
        "isa_data": {
            "elements": [{"id": "A", "label": "Alpha", "type": "Drivers"}],
            "connections": [{"source": "A", "target": "GHOST", "polarity": "+"}],
        },
    }))
    with pytest.raises(ValueError) as exc:
        load_project(bad)
    assert "GHOST" in str(exc.value)


def test_load_rejects_duplicate_element_ids(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "isa_data": {
            "elements": [
                {"id": "A", "label": "One", "type": "Drivers"},
                {"id": "A", "label": "Two", "type": "Drivers"},
            ],
            "connections": [],
        },
    }))
    with pytest.raises(ValueError) as exc:
        load_project(bad)
    assert "duplicate" in str(exc.value).lower()


def test_validate_accepts_flat_isa_shape():
    """Tolerate the older "flat" {elements, connections} shape that the
    sample file uses, in addition to the {metadata, isa_data} envelope."""
    flat = json.loads(SAMPLE.read_text(encoding="utf-8"))
    result = validate_project_payload(flat)
    assert result.valid
    assert result.project is not None
    assert result.project.isa_data.element_count() == 17


def test_atomic_write_does_not_leak_temp_files(tmp_path):
    project = ds.Project.from_isa(ds.load_sample(SAMPLE))
    target = tmp_path / "out.json"
    save_project_atomic(project, target)
    leftovers = list(tmp_path.glob("*.tmp.json"))
    assert leftovers == [], f"temp files leaked: {leftovers}"


def test_project_to_bytes_is_valid_json():
    isa = ds.load_sample(SAMPLE)
    project = ds.Project.from_isa(isa)
    payload = project_to_bytes(project)
    assert isinstance(payload, bytes)
    parsed = json.loads(payload.decode())
    assert "metadata" in parsed
    assert "isa_data" in parsed
    assert parsed["isa_data"]["elements"][0]["id"] == isa.elements[0].id
