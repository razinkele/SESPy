"""App tests: _dedup_accepted from sespy.modules.ai_isa_wizard."""
from __future__ import annotations

# ===========================================================================
# SP4 dedup logic tests — pure-data layer (no Shiny reactive context required).
# These test the dedup helper only; the full _on_finish flow is exercised
# via e2e in tests/test_wizard_e2e.py.
# ===========================================================================
from sespy.data_structure import ConnectionSuggestion

# Import the production helper directly — NOT a copy. Tests below
# exercise the exact same algorithm _on_finish uses.
from sespy.modules.ai_isa_wizard import _dedup_accepted as _dedup


def _make_sug(source, target, polarity, confidence, rationale="r"):
    return ConnectionSuggestion(
        source=source, target=target, polarity=polarity,
        relevance=confidence, rationale=rationale,
    )


def test_dedup_keeps_both_polarities_for_same_pair():
    """(D001, A001, +) and (D001, A001, -) co-exist — different polarity
    is NOT a duplicate."""
    pos = _make_sug("D001", "A001", "+", 0.9)
    neg = _make_sug("D001", "A001", "-", 0.7)
    final, discarded, overwritten = _dedup([pos, neg])
    assert len(final) == 2
    assert {(s.source, s.target, s.polarity) for s in final} == {
        ("D001", "A001", "+"), ("D001", "A001", "-"),
    }
    assert discarded == 0 and overwritten == 0


def test_dedup_drops_lower_confidence_same_polarity():
    sp3 = _make_sug("D001", "A001", "+", 0.5, rationale="sp3 r")
    sp4 = _make_sug("D001", "A001", "+", 0.9, rationale="sp4 r")
    # SP3 first, then SP4 (real iteration order in _on_finish).
    final, discarded, overwritten = _dedup([sp3, sp4])
    assert len(final) == 1
    # Higher confidence wins.
    assert final[0].relevance == 0.9
    assert final[0].rationale == "sp4 r"
    assert overwritten == 1
    assert discarded == 0


def test_dedup_tie_break_favors_sp3_via_iteration_order():
    """Equal confidence — first-iterated entry wins (the SP3 entry,
    since SP3 is read before SP4 in _on_finish)."""
    sp3 = _make_sug("D001", "A001", "+", 0.7, rationale="sp3 r")
    sp4 = _make_sug("D001", "A001", "+", 0.7, rationale="sp4 r")
    final, discarded, overwritten = _dedup([sp3, sp4])
    assert len(final) == 1
    assert final[0].rationale == "sp3 r"
    assert discarded == 1
    assert overwritten == 0


def test_dedup_on_relevance_tie_keeps_rule_row():
    rule = ConnectionSuggestion("a", "b", "+", 0.7, "r", "strong", 4)
    claude = ConnectionSuggestion("a", "b", "+", 0.7, "c")
    kept, discarded, overwritten = _dedup([rule, claude])
    assert kept == [rule] and (discarded, overwritten) == (1, 0)
