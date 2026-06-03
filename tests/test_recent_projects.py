"""Unit tests for the recent-projects registry."""
from __future__ import annotations

import pytest

from sespy import recent_projects as rp


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    yield tmp_path


def _make_file(tmp_path, name="proj.json", content="{}"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_empty_registry_returns_empty(isolated_home):
    assert rp.list_recent() == []


def test_add_and_list(isolated_home):
    f = _make_file(isolated_home)
    rp.add_recent(path=f, name="MyProj", element_count=4, connection_count=3)
    rows = rp.list_recent()
    assert len(rows) == 1
    assert rows[0].name == "MyProj"
    assert rows[0].element_count == 4
    assert rows[0].connection_count == 3


def test_add_same_path_twice_dedups_to_top(isolated_home):
    a = _make_file(isolated_home, "a.json")
    b = _make_file(isolated_home, "b.json")
    rp.add_recent(path=a, name="A")
    rp.add_recent(path=b, name="B")
    rp.add_recent(path=a, name="A-updated")  # touch a again
    rows = rp.list_recent()
    assert len(rows) == 2
    # a should be at the top now (last_used is fresher)
    assert rows[0].name == "A-updated"
    assert rows[1].name == "B"


def test_max_recent_caps_list(isolated_home):
    files = [_make_file(isolated_home, f"f{i}.json") for i in range(rp.MAX_RECENT + 5)]
    for i, f in enumerate(files):
        rp.add_recent(path=f, name=f"f{i}")
    rows = rp.list_recent()
    assert len(rows) == rp.MAX_RECENT


def test_remove_drops_entry(isolated_home):
    a = _make_file(isolated_home, "a.json")
    rp.add_recent(path=a, name="A")
    rp.remove_recent(a)
    assert rp.list_recent() == []


def test_missing_files_filtered(isolated_home):
    """Entries pointing to deleted files shouldn't appear in the list —
    a stale registry entry is just confusing."""
    f = _make_file(isolated_home, "ghost.json")
    rp.add_recent(path=f, name="Ghost")
    f.unlink()  # file gone
    assert rp.list_recent() == []


def test_corrupt_registry_returns_empty(isolated_home):
    """A bad JSON registry shouldn't crash the app — just return []."""
    rp._registry_path().write_text("not valid {{{")
    assert rp.list_recent() == []
