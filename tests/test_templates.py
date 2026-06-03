"""Unit tests for the templates registry + JSON validity."""
from __future__ import annotations

from pathlib import Path

import pytest

from sespy import templates as tpl
from sespy.persistent_storage import load_project


def test_templates_directory_has_at_least_two():
    """Sanity check that we ship multiple starting points."""
    rows = tpl.list_templates()
    assert len(rows) >= 2, f"expected ≥2 built-in templates, got {len(rows)}"


def test_each_template_loads_and_validates():
    """Every shipped template should parse + pass schema validation."""
    rows = tpl.list_templates()
    for info in rows:
        project = load_project(info.file)
        assert project.isa_data.element_count() > 0, info.name
        assert project.isa_data.connection_count() > 0, info.name


def test_templates_have_distinct_names():
    rows = tpl.list_templates()
    names = [r.name for r in rows]
    assert len(names) == len(set(names)), f"duplicate names: {names}"


def test_template_metadata_populated():
    """Each template should have a name and a non-empty description —
    they're shown in the picker."""
    for info in tpl.list_templates():
        assert info.name, info.file
        assert info.description, f"{info.name} missing description"


def test_template_load_roundtrip_via_load_template_helper():
    rows = tpl.list_templates()
    if not rows:
        pytest.skip("no templates installed")
    project = tpl.load_template(rows[0].file)
    assert project.isa_data.element_count() == rows[0].element_count
    assert project.isa_data.connection_count() == rows[0].connection_count


def test_offshore_wind_template_has_responses():
    """Spot-check the offshore wind template includes Response elements
    (R001 spatial planning, R002 noise mitigation) that the analyses
    use as a 'what intervention?' example."""
    project = load_project(
        Path(tpl._templates_dir()) / "offshore_wind.json"
    )
    types = {el.type for el in project.isa_data.elements}
    assert "Responses" in types
