"""Live feedback #16 (2026-11-11): "How is confidence score set in the
AI-assisted SES Creation? Maybe there could be explained how the score was
calculated or what is it based on."

Since K1b the rule-based table shows R's Strength and Confidence from the
connection knowledge base (exact match 4, synonym or keyword match 3), not the
old 0.3/0.6/0.9 keyword steps. Claude's scores are the model's own estimate.
The review step says so under each table.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import get_args

import pytest

from sespy import i18n
from sespy.claude_backend import DropReason, ValidationOutcome
from sespy.data_structure import ConnectionSuggestion
from sespy.modules.ai_isa_wizard import _ClaudeIdle, _ClaudeReturned, _render_connection_review
from sespy.ui_i18n import Translator, load_translations

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
LANGS = ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el")
SUGG = [ConnectionSuggestion(source="D001", target="A001", polarity="+",
                             relevance=0.6, rationale="Tourism drives boating")]


def test_rule_based_table_explains_its_confidence(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    html = str(_render_connection_review(SUGG, _ClaudeIdle(), False))
    assert escape(TR.t("wizard.confidence_help_rules"), quote=False) in html


def test_claude_table_explains_its_confidence(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    outcome = ValidationOutcome(suggestions=SUGG, raw_count=1,
                                drops_by_reason=dict.fromkeys(get_args(DropReason), 0))
    html = str(_render_connection_review(SUGG, _ClaudeReturned(outcome=outcome), True))
    assert escape(TR.t("wizard.confidence_help_claude"), quote=False) in html


def test_no_explanation_without_suggestions(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    html = str(_render_connection_review([], _ClaudeIdle(), False))
    assert escape(TR.t("wizard.confidence_help_rules"), quote=False) not in html


@pytest.mark.parametrize("key", ["wizard.confidence_help_rules", "wizard.confidence_help_claude"])
def test_explanations_cover_all_languages(key):
    tr = load_translations(ROOT / "sespy" / "translations")
    for lang in LANGS:
        assert tr[key].get(lang, "").strip(), (key, lang)
    for lang in LANGS[1:]:
        assert tr[key][lang] != tr[key]["en"], (key, lang)


def test_rule_help_text_describes_r_kb_confidence_and_strength():
    """K1b Task 7: confidence comes from R's connection KB (exact match 4,
    synonym or keyword match 3), strength from the KB, else medium. The scorer
    must actually behave as the help text says."""
    assert "exact match gives confidence 4" in TR.t("wizard.confidence_help_rules")
    assert "synonym or keyword match gives 3" in TR.t("wizard.confidence_help_rules")
    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import Element, WizardState
    sugg = suggest_connections(WizardState(elements=[
        Element("D1", "Food security", "Drivers"),
        Element("A1", "Commercial fishing", "Activities")]))
    assert sugg
    assert all(s.confidence in (3, 4) for s in sugg)
    assert all(s.strength in ("weak", "medium", "strong") for s in sugg)
    assert any(s.confidence == 4 for s in sugg)
