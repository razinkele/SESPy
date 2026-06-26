"""Unit tests for the i18n loader + Translator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sespy.i18n import (
    SUPPORTED_LANGUAGES,
    Translator,
    detect_initial_language,
    load_translations,
)

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "sespy" / "translations"


@pytest.fixture(scope="module")
def translations() -> dict:
    return load_translations(TRANSLATIONS)


def test_loader_finds_keys(translations):
    assert "nav.cld" in translations
    assert "stepper.start" in translations
    assert translations["nav.cld"]["en"] == "CLD Visualization"


def test_loader_handles_all_supported_languages(translations):
    # Every key should have entries for every supported language. (Drift
    # check — catches missing translations early.)
    for key, entry in translations.items():
        missing = [lang for lang in SUPPORTED_LANGUAGES if lang not in entry]
        assert not missing, f"key {key!r} missing translations: {missing}"


def test_translator_basic_lookup(translations):
    t = Translator(translations=translations)
    assert t.t("nav.cld") == "CLD Visualization"


def test_translator_language_switch(translations):
    t = Translator(translations=translations)
    t.set_language("es")
    assert t.t("nav.cld") == "Visualización CLD"
    t.set_language("fr")
    assert t.t("nav.cld") == "Visualisation CLD"
    t.set_language("lt")
    assert t.t("nav.cld") == "CLD Vizualizacija"


def test_translator_falls_back_to_english_on_missing_lang(translations):
    """If a language is supported but a specific key has no entry for it,
    fall back to English rather than returning the raw key.
    """
    sparse_translations = {
        "x.only_english": {"en": "english text"},
    }
    t = Translator(translations=sparse_translations)
    t.set_language("lt")
    assert t.t("x.only_english") == "english text"


def test_translator_returns_key_when_missing(translations):
    t = Translator(translations=translations)
    assert t.t("does.not.exist") == "does.not.exist"


def test_translator_format_interpolation(translations):
    sample = {"loops.found": {"en": "Found {n} loops", "es": "Encontré {n} bucles"}}
    t = Translator(translations=sample)
    assert t.t("loops.found", n=7) == "Found 7 loops"
    t.set_language("es")
    assert t.t("loops.found", n=7) == "Encontré 7 bucles"


def test_detect_initial_language_from_query():
    assert detect_initial_language("?lang=es") == "es"
    assert detect_initial_language("?language=fr") == "fr"
    assert detect_initial_language("?lang=zz") == "en"  # unsupported → fallback
    assert detect_initial_language("") == "en"
    assert detect_initial_language(None) == "en"


def test_leverage_realm_keys_present(translations):
    for token in ("parameters", "feedbacks", "design", "intent"):
        assert f"leverage.realm.{token}" in translations


def test_metrics_fit_keys_present(translations):
    for key in ("metrics.fit", "metrics.fit_caption", "metrics.fit_none"):
        assert key in translations


def test_uncertainty_computing_key_present(translations):
    assert "uncertainty.computing" in translations


def test_blind_rating_keys_present(translations):
    assert "rate.blind_mode" in translations
    assert "rate.blind_hidden" in translations


def test_cld_contested_keys_present(translations):
    assert "cld.contested_legend" in translations
    assert "cld.contested_sign" in translations


def test_disagreement_legend_key_present(translations):
    assert "loops.disagreement_legend" in translations


def test_topbar_and_feedback_keys_present(translations):
    for k in ("topbar.feedback", "topbar.about", "topbar.options", "topbar.help",
              "feedback.title", "feedback.message", "feedback.rating", "feedback.category",
              "feedback.submit", "feedback.sent", "feedback.empty",
              "feedback.cat_bug", "feedback.cat_suggestion", "feedback.cat_question",
              "feedback.cat_other"):
        assert k in translations, k


def test_about_keys_present(translations):
    for k in ("about.overview", "about.changelog"):
        assert k in translations, k


def test_options_keys_present(translations):
    for k in ("options.title", "options.appearance", "options.theme", "options.language",
              "options.autosave", "options.autosave_enable", "options.autosave_clear",
              "options.autosave_status"):
        assert k in translations, k
