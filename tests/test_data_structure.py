"""Unit tests for sespy.data_structure — Project / ProjectMetadata schema."""
from __future__ import annotations

import json

from sespy.data_structure import (
    PROJECT_SCHEMA_VERSION,
    Project,
    ProjectMetadata,
    empty,
)


def test_schema_version_is_2():
    assert PROJECT_SCHEMA_VERSION == 2


def test_metadata_has_pims_fields_with_empty_defaults():
    meta = ProjectMetadata()
    assert meta.focal_issue == ""
    assert meta.definition_statement == ""
    assert meta.temporal_scale == ""
    assert meta.spatial_scale == ""
    assert meta.system_in_focus == ""


def test_round_trip_preserves_pims_fields():
    meta = ProjectMetadata(
        name="Test",
        da_site="Macaronesia",
        focal_issue="Plastic pollution in coastal habitats",
        definition_statement="A 5-year monitoring programme across three islands.",
        temporal_scale="Yearly",
        spatial_scale="Regional",
        system_in_focus="Intertidal zone",
    )
    project = Project(metadata=meta, isa_data=empty())
    payload = json.loads(project.to_json())
    restored = Project.from_dict(payload)
    assert restored.metadata.focal_issue == meta.focal_issue
    assert restored.metadata.definition_statement == meta.definition_statement
    assert restored.metadata.temporal_scale == meta.temporal_scale
    assert restored.metadata.spatial_scale == meta.spatial_scale
    assert restored.metadata.system_in_focus == meta.system_in_focus


def test_from_dict_drops_unknown_metadata_keys(caplog):
    payload = {
        "metadata": {
            "name": "Probe",
            "future_field": "hello",
            "another_unknown": 42,
        },
        "isa_data": {"elements": [], "connections": []},
    }
    import logging
    with caplog.at_level(logging.WARNING):
        project = Project.from_dict(payload)
    assert project.metadata.name == "Probe"
    assert not hasattr(project.metadata, "future_field")
    # Both unknown keys should appear in the warning message.
    assert any("future_field" in record.message and "another_unknown" in record.message
               for record in caplog.records)


def test_from_dict_loads_legacy_v1_files_silently():
    # A pre-v2 file lacks all PIMS fields; defaults must fill in.
    payload = {
        "metadata": {
            "name": "Legacy",
            "schema_version": 1,
        },
        "isa_data": {"elements": [], "connections": []},
    }
    project = Project.from_dict(payload)
    assert project.metadata.name == "Legacy"
    assert project.metadata.focal_issue == ""
    assert project.metadata.spatial_scale == ""


def test_wizard_state_defaults():
    from sespy.data_structure import WizardState
    state = WizardState()
    assert state.regional_sea == ""
    assert state.ecosystem_type == ""
    assert state.countries == []
    assert state.main_issue == []
    assert state.elements == []


def test_wizard_state_construction():
    from sespy.data_structure import WizardState, Element
    elements = [Element(id="D001", label="Tourism", type="Drivers")]
    state = WizardState(
        regional_sea="baltic",
        ecosystem_type="open_coast",
        countries=["Lithuania", "Poland"],
        main_issue=["Eutrophication"],
        elements=elements,
    )
    assert state.regional_sea == "baltic"
    assert len(state.elements) == 1
    assert state.elements[0].id == "D001"


def test_connection_suggestion_construction():
    from sespy.data_structure import ConnectionSuggestion
    s = ConnectionSuggestion(
        source="D001", target="P001", polarity="+",
        confidence=0.7, rationale="Tourism drives anchor damage."
    )
    assert s.source == "D001"
    assert s.target == "P001"
    assert s.polarity == "+"
    assert s.confidence == 0.7
    assert "anchor" in s.rationale.lower()
