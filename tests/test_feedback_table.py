"""Unit tests for the recent-feedback table in the Feedback modal.

The renderer is a pure function of a list of entry dicts (as returned by
feedback_store.list_entries), so no database is needed here.
"""
import sqlite3

from sespy.modules import topbar_actions
from sespy.modules.topbar_actions import _feedback_table, _fmt_ts, _safe_recent_entries, _truncate


def test_fmt_ts_iso_to_minute():
    assert _fmt_ts("2026-06-30T17:55:37.990094+00:00") == "2026-06-30 17:55"


def test_fmt_ts_bad_input_returns_placeholder():
    assert _fmt_ts("not-a-date") == "not-a-date"
    assert _fmt_ts("") == "—"


def test_truncate_short_is_unchanged():
    assert _truncate("short message") == "short message"


def test_truncate_long_is_ellipsised():
    out = _truncate("x" * 200, 60)
    assert out.endswith("…") and len(out) <= 60


def test_feedback_table_empty_shows_placeholder_not_table():
    html = str(_feedback_table([]))
    assert "No feedback yet" in html
    assert "<table" not in html


def test_feedback_table_renders_rows():
    entries = [
        {"created_at": "2026-06-30T10:00:00+00:00", "category": "bug",
         "rating": 2, "message": "It froze on export"},
        {"created_at": "2026-06-29T09:00:00+00:00", "category": "suggestion",
         "rating": 5, "message": "Nice tool"},
    ]
    html = str(_feedback_table(entries))
    assert "<table" in html
    assert "It froze on export" in html and "Nice tool" in html
    assert "2★" in html and "5★" in html          # rating rendering
    assert "Bug" in html                           # category label (English fallback)
    assert "2026-06-30 10:00" in html              # formatted timestamp


def test_safe_recent_entries_swallows_readonly_db_error(monkeypatch):
    """Reproduces the server crash: the app user cannot write the WAL, so the
    store read raises. The modal helper must degrade to [] rather than crash
    the Feedback dialog (and thus the whole session)."""
    def boom(*a, **k):
        raise sqlite3.OperationalError("attempt to write a readonly database")

    monkeypatch.setattr(topbar_actions.feedback_store, "list_entries", boom)
    assert _safe_recent_entries(10) == []


def test_safe_recent_entries_returns_rows_on_success(monkeypatch):
    monkeypatch.setattr(
        topbar_actions.feedback_store, "list_entries",
        lambda *a, **k: [{"created_at": "2026-06-30T10:00:00+00:00",
                          "category": "bug", "rating": 2, "message": "x"}],
    )
    rows = _safe_recent_entries(10)
    assert len(rows) == 1 and rows[0]["message"] == "x"


def test_feedback_table_truncates_long_message_with_full_title():
    long = "y" * 200
    html = str(_feedback_table([
        {"created_at": "2026-06-30T10:00:00+00:00", "category": "other",
         "rating": 3, "message": long},
    ]))
    assert "…" in html          # cell text is ellipsised
    assert long in html         # full text preserved in the title= tooltip
