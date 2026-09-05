"""Contextual help (v1.9.0): the Help offcanvas shows the manual section for the
active panel. The extractor is pure text slicing over docs/MANUAL.md."""
from pathlib import Path

import pytest

from sespy.modules.topbar_actions import manual_section

ROOT = Path(__file__).resolve().parents[1]
MANUAL = (ROOT / "docs" / "MANUAL.md").read_text(encoding="utf-8")


def _nav_labels():
    from app import NAV
    return [item.label for item in NAV]


@pytest.mark.parametrize("label", _nav_labels())
def test_every_nav_panel_has_a_manual_section(label):
    section = manual_section(label, MANUAL)
    assert section, label
    assert section.splitlines()[0].endswith(f". {label}"), section.splitlines()[0]


def test_section_stops_before_the_next_heading():
    section = manual_section("Templates", MANUAL)
    assert "## 8. SES Wizard" not in section
    assert "Shipped templates" in section


def test_unknown_label_returns_none():
    assert manual_section("No Such Panel", MANUAL) is None


def test_section_heading_is_demoted_for_the_side_panel():
    # The offcanvas already carries a title, so the section's own "## N." line
    # is dropped and the body starts at the screenshot/purpose text.
    body = manual_section("Loop Analysis", MANUAL, strip_heading=True)
    assert not body.startswith("## ")
    assert "**Purpose.**" in body
