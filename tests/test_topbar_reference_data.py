"""About modal: Reference data section (K1 Task 15)."""
import dataclasses

import pytest

import sespy.i18n
from sespy import r_kb
from sespy.modules.topbar_actions import _about_modal


@pytest.fixture(autouse=True)
def _pin_translator(monkeypatch):
    monkeypatch.setattr(sespy.i18n, "get_default", lambda: None)


def _html(snapshot=None) -> str:
    return str(_about_modal(None, snapshot=snapshot))


def test_about_lists_both_files_vendored():
    html = _html(r_kb.VENDORED)
    assert 'id="about-reference-data"' in html
    for row in r_kb.ALLOW_LIST:
        assert row.name in html
        assert r_kb.VENDORED.files[row.name].sha256_norm[:8] in html
    assert "vendored" in html
    assert f"R {r_kb.VENDORED.manifest['r_tag']}" in html
    assert "R v1.35.6" in html


def test_about_shared_differs_label():
    name = r_kb.KB_NAME
    entry = dataclasses.replace(r_kb.VENDORED.files[name], source="shared",
                                sha256_norm="deadbeef" + "0" * 56)
    snap = dataclasses.replace(r_kb.VENDORED,
                               files={**r_kb.VENDORED.files, name: entry},
                               live_r_version="1.99.0")
    html = _html(snap)
    assert "shared, differs from R v1.35.6" in html
    assert "deadbeef" in html
    assert "live R 1.99.0" in html


def test_about_without_snapshot_omits_section():
    assert "about-reference-data" not in _html(None)
    assert "about-reference-data" not in str(_about_modal(None))
