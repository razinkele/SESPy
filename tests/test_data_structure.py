"""Unit tests for sespy.data_structure — Project / ProjectMetadata schema."""
from __future__ import annotations

import json

from sespy.data_structure import (
    PROJECT_SCHEMA_VERSION,
    Connection,
    IsaData,
    Project,
    ProjectMetadata,
    Rating,
    empty,
)


def test_schema_version_is_6():
    assert PROJECT_SCHEMA_VERSION == 6


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


# ---------------------------------------------------------------------------
# SP4 shared topology constants: Slug, _CONN_TYPES, _VALID_TYPE_PAIRS
# ---------------------------------------------------------------------------

"""Tests for the shared data-layer constants used by both backends."""
from typing import get_args

import pytest

from sespy.data_structure import (
    ELEMENT_TYPE_MAP,
    Slug,
    _CONN_TYPES,
    _VALID_TYPE_PAIRS,
)


def test_slug_literal_matches_element_type_map_keys():
    """Slug Literal members must equal the keys of ELEMENT_TYPE_MAP."""
    assert set(get_args(Slug)) == set(ELEMENT_TYPE_MAP.keys())
    assert len(get_args(Slug)) == 7


def test_conn_types_is_three_tuple_shape():
    """_CONN_TYPES preserves (from_slug, to_slug, key) 3-tuple shape from
    the original connection_scorer.py definition. Pinning this prevents
    a refactor from silently breaking tests/test_connection_scorer.py:491."""
    assert isinstance(_CONN_TYPES, list)
    assert len(_CONN_TYPES) == 10
    for entry in _CONN_TYPES:
        assert isinstance(entry, tuple)
        assert len(entry) == 3
        from_slug, to_slug, key = entry
        assert isinstance(from_slug, str)
        assert isinstance(to_slug, str)
        assert isinstance(key, str)
        assert key == f"{from_slug}_{to_slug}"


def test_conn_types_exact_entries():
    """The 10 type-pairs are the canonical DAPSI(W)R(M) directed edges."""
    expected = [
        ("drivers", "activities", "drivers_activities"),
        ("activities", "pressures", "activities_pressures"),
        ("pressures", "states", "pressures_states"),
        ("states", "impacts", "states_impacts"),
        ("impacts", "welfare", "impacts_welfare"),
        ("responses", "pressures", "responses_pressures"),
        ("responses", "drivers", "responses_drivers"),
        ("responses", "activities", "responses_activities"),
        ("welfare", "drivers", "welfare_drivers"),
        ("welfare", "responses", "welfare_responses"),
    ]
    assert _CONN_TYPES == expected


def test_valid_type_pairs_derives_from_conn_types():
    """_VALID_TYPE_PAIRS is the 2-tuple projection of _CONN_TYPES.
    Catches drift if either constant is later defined inline."""
    expected = frozenset(
        (from_slug, to_slug) for from_slug, to_slug, _key in _CONN_TYPES
    )
    assert _VALID_TYPE_PAIRS == expected
    assert isinstance(_VALID_TYPE_PAIRS, frozenset)
    assert len(_VALID_TYPE_PAIRS) == 10


def test_connection_ratings_round_trip():
    conn = Connection(
        source="A", target="B", polarity="+", strength="strong", confidence=4,
        ratings=[
            Rating(rater_id="s1", strength="strong", confidence=5, polarity="+"),
            Rating(rater_id="s2", strength="weak", confidence=2, polarity="-"),
        ],
    )
    project = Project(metadata=ProjectMetadata(name="R"), isa_data=IsaData(connections=[conn]))
    restored = Project.from_dict(json.loads(project.to_json()))
    rc = restored.isa_data.connections[0]
    assert len(rc.ratings) == 2
    assert all(isinstance(r, Rating) for r in rc.ratings)
    assert rc.ratings[0].rater_id == "s1"
    assert rc.ratings[1].polarity == "-"


def test_v5_project_loads_without_ratings():
    payload = {
        "metadata": {"name": "Legacy", "schema_version": 5},
        "isa_data": {
            "elements": [],
            "connections": [{"source": "A", "target": "B", "polarity": "-",
                             "strength": "weak", "confidence": 2, "delay": "short"}],
        },
    }
    restored = Project.from_dict(payload)
    c = restored.isa_data.connections[0]
    assert c.ratings == []
    assert (c.polarity, c.strength, c.confidence, c.delay) == ("-", "weak", 2, "short")
    assert restored.metadata.schema_version == 6


def test_connection_unknown_keys_filtered():
    payload = {
        "isa_data": {"elements": [], "connections": [
            {"source": "A", "target": "B", "future_field": 99,
             "ratings": [{"rater_id": "s1", "confidence": 3, "junk": 1}]}
        ]},
    }
    restored = Project.from_dict(payload)
    c = restored.isa_data.connections[0]
    assert c.source == "A" and c.target == "B"
    assert len(c.ratings) == 1 and c.ratings[0].rater_id == "s1"
