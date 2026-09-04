"""The user manual (docs/MANUAL.md) must stay in step with the app.

These checks keep the manual honest without an e2e run: every image it
references exists, every navigation panel has a Part II section, every DOI
a library docstring cites is in Part IV, and the version line tracks the
package. They also pin the About modal's static-asset mount so the
manual's relative image paths resolve in-app.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "docs" / "MANUAL.md"


@pytest.fixture(scope="module")
def manual() -> str:
    return MANUAL.read_text(encoding="utf-8")


def test_manual_exists_and_is_substantial(manual):
    assert len(manual.split()) > 5000


def test_manual_version_line_matches_package(manual):
    from sespy import __version__
    assert f"**Version {__version__}" in manual


def test_every_manual_image_exists(manual):
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", manual)
    assert refs, "manual has no images"
    missing = [r for r in refs if not (ROOT / r).is_file()]
    assert not missing, missing


def test_every_readme_image_exists():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
    refs = [r for r in refs if not r.startswith("http")]
    missing = [r for r in refs if not (ROOT / r).is_file()]
    assert not missing, missing


def test_every_nav_panel_has_a_part_two_section(manual):
    from app import NAV
    headings = set(re.findall(r"^## \d+\. (.+)$", manual, flags=re.M))
    missing = [item.label for item in NAV if item.label not in headings]
    assert not missing, missing


def test_every_docstring_doi_is_in_the_references(manual):
    dois = set()
    for name in ("network.py", "dynamics.py"):
        src = (ROOT / "sespy" / name).read_text(encoding="utf-8")
        dois.update(re.findall(r"doi:\s*([0-9.]+/[^\s)\]]+)", src))
    assert dois, "no DOIs found in docstrings"
    refs = manual.split("# Part IV")[1]
    missing = sorted(d for d in dois if d not in refs)
    assert not missing, missing


def test_about_static_mount_serves_manual_screenshots():
    from app import app  # noqa: F401  (import builds the App)
    import app as app_module
    mounts = app_module.STATIC_ASSETS
    assert Path(mounts["/docs/screenshots"]) == ROOT / "docs" / "screenshots"
    assert Path(mounts["/"]) == ROOT / "www"
