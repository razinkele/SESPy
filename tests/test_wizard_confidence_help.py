"""Live feedback #16 (2026-11-11): "How is confidence score set in the
AI-assisted SES Creation? Maybe there could be explained how the score was
calculated or what is it based on."

The rule-based score (ported from R's .calculate_basic_relevance) counts
keyword matches in the two element names: none 0.3, one 0.6, two or more
0.9, and a flat 0.5 for link types with no keyword list. Claude's scores are
the model's own estimate. The review step now says so under each table.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import get_args

import pytest

from sespy import i18n
from sespy.claude_backend import DropReason, ValidationOutcome
from sespy.data_structure import ConnectionSuggestion
from sespy.i18n import Translator, load_translations
from sespy.modules.ai_isa_wizard import _ClaudeIdle, _ClaudeReturned, _render_connection_review

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
LANGS = ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el")
SUGG = [ConnectionSuggestion(source="D001", target="A001", polarity="+",
                             confidence=0.6, rationale="Tourism drives boating")]


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


def test_rule_explanation_matches_the_scorer():
    """The numbers in the text are the scorer's actual levels."""
    from sespy.connection_scorer import calculate_relevance
    tr = load_translations(ROOT / "sespy" / "translations")
    text = tr["wizard.confidence_help_rules"]["en"]
    for level in ("0.3", "0.6", "0.9", "0.5"):
        assert level in text
    assert calculate_relevance("zzz", "qqq", "drivers", "activities") == 0.3
    assert calculate_relevance("zzz", "qqq", "responses", "states") == 0.5
