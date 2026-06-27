"""Unit tests for the autosave layer."""
from __future__ import annotations

from pathlib import Path

import pytest

from sespy import autosave
from sespy import data_structure as ds

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_ses.json"


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect ~/.sespy/ into a temp dir for isolation."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    yield tmp_path


def test_write_then_read_roundtrips(isolated_home):
    isa_before = ds.load_sample(SAMPLE)
    written = autosave.write_autosave(isa_before)
    assert written.exists()
    assert written.parent.name == ".sespy"

    project_after = autosave.read_autosave()
    assert project_after is not None
    assert project_after.isa_data.element_count() == 17
    assert project_after.isa_data.connection_count() == 20


def test_read_returns_none_when_no_autosave(isolated_home):
    assert autosave.read_autosave() is None


def test_age_seconds_returns_value_after_write(isolated_home):
    autosave.write_autosave(ds.load_sample(SAMPLE))
    age = autosave.autosave_age_seconds()
    assert age is not None
    assert age >= 0  # just-written file
    assert age < 5    # but not stale


def test_clear_removes_file(isolated_home):
    autosave.write_autosave(ds.load_sample(SAMPLE))
    assert autosave.autosave_path().exists()
    autosave.clear_autosave()
    assert not autosave.autosave_path().exists()
    # Idempotent — calling again on a missing file shouldn't raise
    autosave.clear_autosave()


def test_corrupt_autosave_returns_none_not_raises(isolated_home):
    autosave.autosave_path().write_text("not valid json {{{")
    assert autosave.read_autosave() is None  # no exception


def test_write_with_isa_wraps_in_project(isolated_home):
    """write_autosave accepts either Project or IsaData."""
    isa = ds.load_sample(SAMPLE)
    autosave.write_autosave(isa)
    project = autosave.read_autosave()
    assert project is not None
    assert project.metadata.name == "Autosave"


def test_write_preserves_existing_project_metadata(isolated_home):
    """When the user passes a full Project (with metadata), metadata
    survives the round-trip."""
    project = ds.Project.from_isa(ds.load_sample(SAMPLE), name="Custom Name")
    autosave.write_autosave(project)
    loaded = autosave.read_autosave()
    assert loaded is not None
    assert loaded.metadata.name == "Custom Name"
