"""P0b — forward compatibility with project files from a newer SESPy.

`Project.from_dict` overwrites `metadata.schema_version` with the running
build's, so whether a file came from a newer build must be read from the
raw payload before that happens. A flagged project must never be
autosaved: autosave would silently replace it with a copy that has lost
the fields this build does not understand.
"""
from __future__ import annotations

import pytest

import sespy
from sespy import autosave
from sespy import data_structure as ds
from sespy.data_structure import PROJECT_SCHEMA_VERSION, Project

TOKEN_A = "0f8c2a4e-1b7d-4c3e-9a55-6d2e8f1a0b3c"


def _payload(**meta):
    return {
        "metadata": {"name": "P", **meta},
        "isa_data": {
            "elements": [
                {"id": "A", "label": "A", "type": "Drivers"},
                {"id": "B", "label": "B", "type": "Activities"},
            ],
            "connections": [{"source": "A", "target": "B"}],
        },
    }


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    yield tmp_path


# ---- tolerance -----------------------------------------------------------

def test_unknown_element_keys_are_dropped_not_fatal():
    raw = _payload()
    raw["isa_data"]["elements"][0]["indicator"] = "SST"
    raw["isa_data"]["elements"][0]["r_extra"] = {"category": "x"}
    proj = Project.from_dict(raw)
    assert proj.isa_data.elements[0].id == "A"
    assert not hasattr(proj.isa_data.elements[0], "indicator")


# ---- detection -----------------------------------------------------------

def test_current_file_has_no_note():
    assert Project.from_dict(_payload(schema_version=PROJECT_SCHEMA_VERSION)).newer_build_note == ""


def test_missing_stamps_have_no_note():
    assert Project.from_dict(_payload()).newer_build_note == ""


def test_newer_schema_version_sets_note():
    proj = Project.from_dict(_payload(schema_version=PROJECT_SCHEMA_VERSION + 1))
    assert proj.newer_build_note
    assert str(PROJECT_SCHEMA_VERSION + 1) in proj.newer_build_note
    # from_dict still upgrades the object's own stamp to the running build.
    assert proj.metadata.schema_version == PROJECT_SCHEMA_VERSION


def test_newer_min_sespy_version_sets_note(monkeypatch):
    monkeypatch.setattr(sespy, "__version__", "1.12.3")
    proj = Project.from_dict(_payload(min_sespy_version="1.13.0"))
    assert "1.13.0" in proj.newer_build_note


def test_equal_or_older_min_sespy_version_has_no_note(monkeypatch):
    monkeypatch.setattr(sespy, "__version__", "1.12.3")
    assert Project.from_dict(_payload(min_sespy_version="1.12.3")).newer_build_note == ""
    assert Project.from_dict(_payload(min_sespy_version="1.9.0")).newer_build_note == ""


@pytest.mark.parametrize("bad", [
    {"schema_version": "seven"},
    {"schema_version": None},
    {"schema_version": 7.5},
    {"schema_version": True},
    {"min_sespy_version": "not-a-version"},
    {"min_sespy_version": 13},
    {"min_sespy_version": ""},
])
def test_malformed_stamps_never_block_a_load(bad):
    proj = Project.from_dict(_payload(**bad))
    assert proj.newer_build_note == ""
    assert proj.isa_data.element_count() == 2


def test_non_dict_metadata_does_not_crash():
    raw = _payload()
    raw["metadata"] = None
    assert Project.from_dict(raw).newer_build_note == ""


# ---- the note travels with the project, but never to disk ----------------

def test_note_survives_edits():
    proj = Project.from_dict(_payload(schema_version=PROJECT_SCHEMA_VERSION + 1))
    assert proj.replace(stakeholders=[]).newer_build_note == proj.newer_build_note
    assert proj.with_modified_now().newer_build_note == proj.newer_build_note


def test_note_is_not_serialised():
    proj = Project.from_dict(_payload(schema_version=PROJECT_SCHEMA_VERSION + 1))
    d = proj.to_dict()
    assert "newer_build_note" not in d
    assert "newer_build_note" not in d["metadata"]


def test_note_field_is_keyword_only_with_default():
    """MosaicSES builds Project(metadata, isa_data) positionally."""
    proj = Project(ds.ProjectMetadata(), ds.IsaData())
    assert proj.newer_build_note == ""


# ---- protection ----------------------------------------------------------

def test_write_autosave_refuses_flagged_project(isolated_home):
    proj = Project.from_dict(_payload(schema_version=PROJECT_SCHEMA_VERSION + 1))
    assert autosave.write_autosave(proj, token=TOKEN_A) is None
    assert not autosave.autosave_path(TOKEN_A).exists()


def test_write_autosave_refusal_keeps_existing_autosave(isolated_home):
    autosave.write_autosave(Project.from_dict(_payload()), token=TOKEN_A)
    before = autosave.autosave_path(TOKEN_A).read_bytes()
    flagged = Project.from_dict(_payload(schema_version=PROJECT_SCHEMA_VERSION + 1))
    autosave.write_autosave(flagged, token=TOKEN_A)
    assert autosave.autosave_path(TOKEN_A).read_bytes() == before
