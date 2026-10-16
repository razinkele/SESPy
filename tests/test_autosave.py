"""Unit tests for the autosave layer.

Autosaves are scoped to a per-browser token (port of R 1.20.1 N7): on a
shared server every session runs as the same OS user, so a single
`~/.sespy/autosave.json` handed one user's project to the next visitor.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from sespy import autosave
from sespy import data_structure as ds

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_ses.json"

TOKEN_A = "0f8c2a4e-1b7d-4c3e-9a55-6d2e8f1a0b3c"
TOKEN_B = "7e1d9c3b-5a2f-4e8d-b6c4-2f9a1e7d3c5b"


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect ~/.sespy/ into a temp dir for isolation."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    yield tmp_path


def test_write_then_read_roundtrips(isolated_home):
    isa_before = ds.load_sample(SAMPLE)
    written = autosave.write_autosave(isa_before, token=TOKEN_A)
    assert written.exists()
    assert written.parent.name == "autosaves"

    project_after = autosave.read_autosave(token=TOKEN_A)
    assert project_after is not None
    assert project_after.isa_data.element_count() == 17
    assert project_after.isa_data.connection_count() == 20


def test_other_token_cannot_read_autosave(isolated_home):
    """The bug being fixed: browser B must never see browser A's work."""
    autosave.write_autosave(ds.load_sample(SAMPLE), token=TOKEN_A)
    assert autosave.read_autosave(token=TOKEN_B) is None
    assert autosave.autosave_age_seconds(token=TOKEN_B) is None


def test_path_does_not_contain_raw_token(isolated_home):
    """The file name is a hash, so a directory listing never leaks a
    token another browser could replay."""
    path = autosave.autosave_path(TOKEN_A)
    assert TOKEN_A not in str(path)
    assert path != autosave.autosave_path(TOKEN_B)


@pytest.mark.parametrize("bad", [
    None, "", "short", "../../etc/passwd", "a" * 65, "abc def ghi jkl mno pqr stu vwx yz",
    "0f8c2a4e/1b7d/4c3e/9a55/6d2e8f1a0b3c",
])
def test_invalid_tokens_rejected(isolated_home, bad):
    assert autosave.valid_token(bad) is False
    with pytest.raises(ValueError):
        autosave.autosave_path(bad)


def test_valid_token_accepts_uuid():
    assert autosave.valid_token(TOKEN_A) is True


def test_read_returns_none_when_no_autosave(isolated_home):
    assert autosave.read_autosave(token=TOKEN_A) is None


def test_read_returns_none_for_invalid_token(isolated_home):
    """Never raises — recovery is best-effort."""
    assert autosave.read_autosave(token="nope") is None


def test_age_seconds_returns_value_after_write(isolated_home):
    autosave.write_autosave(ds.load_sample(SAMPLE), token=TOKEN_A)
    age = autosave.autosave_age_seconds(token=TOKEN_A)
    assert age is not None
    assert 0 <= age < 5


def test_clear_removes_file(isolated_home):
    autosave.write_autosave(ds.load_sample(SAMPLE), token=TOKEN_A)
    assert autosave.autosave_path(TOKEN_A).exists()
    autosave.clear_autosave(token=TOKEN_A)
    assert not autosave.autosave_path(TOKEN_A).exists()
    autosave.clear_autosave(token=TOKEN_A)  # idempotent


def test_corrupt_autosave_returns_none_not_raises(isolated_home):
    path = autosave.autosave_path(TOKEN_A)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid json {{{")
    assert autosave.read_autosave(token=TOKEN_A) is None


def test_newer_schema_autosave_returns_none_not_raises(isolated_home):
    """An element key this build doesn't know raised TypeError, which
    read_autosave did not catch, so a stale autosave could break startup."""
    path = autosave.autosave_path(TOKEN_A)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"metadata": {}, "isa_data": {"elements": ['
        '{"id": "D1", "label": "x", "type": "Drivers", "future_field": 1}],'
        ' "connections": []}}',
        encoding="utf-8",
    )
    # Must not raise; whether it loads or returns None is up to the loader.
    autosave.read_autosave(token=TOKEN_A)


def test_write_with_isa_wraps_in_project(isolated_home):
    autosave.write_autosave(ds.load_sample(SAMPLE), token=TOKEN_A)
    project = autosave.read_autosave(token=TOKEN_A)
    assert project is not None
    assert project.metadata.name == "Autosave"


def test_write_preserves_existing_project_metadata(isolated_home):
    project = ds.Project.from_isa(ds.load_sample(SAMPLE), name="Custom Name")
    autosave.write_autosave(project, token=TOKEN_A)
    loaded = autosave.read_autosave(token=TOKEN_A)
    assert loaded is not None
    assert loaded.metadata.name == "Custom Name"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_autosave_dir_and_file_are_private(isolated_home):
    path = autosave.write_autosave(ds.load_sample(SAMPLE), token=TOKEN_A)
    assert (path.parent.stat().st_mode & 0o777) == 0o700
    assert (path.stat().st_mode & 0o777) == 0o600


def test_prune_removes_only_old_autosaves(isolated_home):
    old = autosave.write_autosave(ds.load_sample(SAMPLE), token=TOKEN_A)
    fresh = autosave.write_autosave(ds.load_sample(SAMPLE), token=TOKEN_B)
    past = time.time() - 73 * 3600
    os.utime(old, (past, past))
    removed = autosave.prune_autosaves(max_age_hours=72)
    assert removed == 1
    assert not old.exists()
    assert fresh.exists()


def test_housekeeping_runs_at_most_once_an_hour(isolated_home, monkeypatch):
    """Every session start calls housekeeping; the directory scan must not
    run for each of them."""
    monkeypatch.setattr(autosave, "_last_housekeeping", None)
    calls = []
    monkeypatch.setattr(autosave, "prune_autosaves", lambda *a, **k: calls.append("prune") or 0)
    monkeypatch.setattr(autosave, "remove_legacy_shared_files", lambda: calls.append("legacy") or 0)
    t0 = 1_000_000.0
    assert autosave.housekeeping(now=t0) is True
    assert autosave.housekeeping(now=t0 + 1800) is False
    assert autosave.housekeeping(now=t0 + 3601) is True
    assert calls == ["legacy", "prune", "legacy", "prune"]


def test_legacy_shared_files_are_removed_and_never_offered(isolated_home):
    """The pre-1.12.2 shared files can't be attributed to anyone."""
    legacy_dir = isolated_home / ".sespy"
    legacy_dir.mkdir()
    (legacy_dir / "autosave.json").write_text("{}", encoding="utf-8")
    (legacy_dir / "recent.json").write_text("[]", encoding="utf-8")
    removed = autosave.remove_legacy_shared_files()
    assert removed == 2
    assert not (legacy_dir / "autosave.json").exists()
    assert not (legacy_dir / "recent.json").exists()
    assert autosave.remove_legacy_shared_files() == 0  # idempotent
