"""One "data changed — re-run" notice per change, not one per analysis tab.

The Boolean and Dynamic Simulation tabs each posted their own toast on the
same ISA change, so a compartment switch in MosaicSES showed it twice
(MosaicSES tester reports, 22 and 23 Oct 2026). They now share one
notification id, which Shiny replaces instead of stacking."""
from pathlib import Path

import shiny

import sespy
from sespy.modules import _notify


def test_notice_uses_one_shared_id(monkeypatch):
    calls = []
    monkeypatch.setattr(shiny.ui, "notification_show", lambda *a, **k: calls.append(k))
    _notify.notify_data_changed()
    _notify.notify_data_changed()
    assert [c.get("id") for c in calls] == [_notify.DATA_CHANGED_ID] * 2


def test_no_tab_posts_its_own_data_changed_toast():
    root = Path(sespy.__file__).parent / "modules"
    direct = [p.name for p in root.glob("*.py")
              if p.name != "_notify.py"
              and "data_changed_rerun" in p.read_text(encoding="utf-8")]
    assert not direct, direct
