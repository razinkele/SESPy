"""Unit tests for the recent-projects registry (scoped per browser token)."""
from __future__ import annotations

import pytest

from sespy import recent_projects as rp

TOKEN_A = "0f8c2a4e-1b7d-4c3e-9a55-6d2e8f1a0b3c"
TOKEN_B = "7e1d9c3b-5a2f-4e8d-b6c4-2f9a1e7d3c5b"


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
    assert rp.list_recent(token=TOKEN_A) == []


def test_add_and_list(isolated_home):
    f = _make_file(isolated_home)
    rp.add_recent(path=f, name="MyProj", element_count=4, connection_count=3, token=TOKEN_A)
    rows = rp.list_recent(token=TOKEN_A)
    assert len(rows) == 1
    assert rows[0].name == "MyProj"
    assert rows[0].element_count == 4
    assert rows[0].connection_count == 3


def test_other_token_sees_nothing(isolated_home):
    f = _make_file(isolated_home)
    rp.add_recent(path=f, name="Private", token=TOKEN_A)
    assert rp.list_recent(token=TOKEN_B) == []


def test_no_token_is_a_noop(isolated_home):
    """Without a browser token there is no private place to store the
    entry, so nothing is written and nothing is listed."""
    f = _make_file(isolated_home)
    rp.add_recent(path=f, name="Nowhere", token=None)
    assert rp.list_recent(token=None) == []
    assert not (isolated_home / ".sespy" / "recent").exists()


def test_add_same_path_twice_dedups_to_top(isolated_home):
    a = _make_file(isolated_home, "a.json")
    b = _make_file(isolated_home, "b.json")
    rp.add_recent(path=a, name="A", token=TOKEN_A)
    rp.add_recent(path=b, name="B", token=TOKEN_A)
    rp.add_recent(path=a, name="A-updated", token=TOKEN_A)
    rows = rp.list_recent(token=TOKEN_A)
    assert len(rows) == 2
    assert rows[0].name == "A-updated"
    assert rows[1].name == "B"


def test_max_recent_caps_list(isolated_home):
    files = [_make_file(isolated_home, f"f{i}.json") for i in range(rp.MAX_RECENT + 5)]
    for i, f in enumerate(files):
        rp.add_recent(path=f, name=f"f{i}", token=TOKEN_A)
    assert len(rp.list_recent(token=TOKEN_A)) == rp.MAX_RECENT


def test_remove_drops_entry(isolated_home):
    a = _make_file(isolated_home, "a.json")
    rp.add_recent(path=a, name="A", token=TOKEN_A)
    rp.remove_recent(a, token=TOKEN_A)
    assert rp.list_recent(token=TOKEN_A) == []


def test_missing_files_filtered(isolated_home):
    f = _make_file(isolated_home, "ghost.json")
    rp.add_recent(path=f, name="Ghost", token=TOKEN_A)
    f.unlink()
    assert rp.list_recent(token=TOKEN_A) == []


def test_corrupt_registry_returns_empty(isolated_home):
    path = rp._registry_path(TOKEN_A)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid {{{")
    assert rp.list_recent(token=TOKEN_A) == []
