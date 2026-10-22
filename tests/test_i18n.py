"""Unit tests for the i18n loader + Translator."""
from __future__ import annotations

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


def test_governance_gap_keys_present(translations):
    for key in (
        "metrics.gov_gap", "metrics.gov_gap_caption", "metrics.gov_gap_orphans",
        "metrics.gov_gap_none", "metrics.gov_gap_untyped",
        "metrics.gov_gap_no_gov", "metrics.gov_gap_no_eco",
        "metrics.gov_gap_no_press",
    ):
        assert key in translations


def test_actor_influence_keys_present(translations):
    assert "metrics.actor_influence" in translations
    assert "metrics.actor_influence_caption" in translations


def test_governance_concentration_keys_present(translations):
    for key in ("metrics.gov_concentration_distributed",
                "metrics.gov_concentration_concentrated"):
        assert key in translations
        assert "{entropy}" in translations[key]["en"]


def test_governance_concentration_placeholders_match_across_languages(translations):
    import re
    expected = {
        "metrics.gov_concentration_distributed": {"n", "entropy"},
        "metrics.gov_concentration_concentrated": {"actor", "share", "n", "entropy"},
    }
    for key, names in expected.items():
        for lang, text in translations[key].items():
            assert set(re.findall(r"\{(\w+)\}", text)) == names, (key, lang, text)


def test_cascade_early_warning_keys_present(translations):
    import re
    expected = {
        "metrics.cascade_early_warning": {"id", "step", "kl", "thr_step"},
        "metrics.cascade_early_warning_none": set(),
    }
    for key, names in expected.items():
        assert key in translations
        for lang, text in translations[key].items():
            assert set(re.findall(r"\{(\w+)\}", text)) == names, (key, lang, text)


def test_about_manual_keys_present(translations):
    for key in ("about.manual", "help.manual_hint"):
        assert key in translations
        for lang in ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el"):
            assert translations[key].get(lang), (key, lang)


def test_help_offcanvas_keys_present(translations):
    for key in ("help.this_panel", "help.full_manual"):
        assert key in translations
        for lang in ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el"):
            assert translations[key].get(lang), (key, lang)


def test_cascade_keys_present(translations):
    for key in ("metrics.cascade", "metrics.cascade_run", "metrics.cascade_hint",
                "metrics.cascade_threshold", "metrics.cascade_caption"):
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


def test_help_keys_present(translations):
    for k in ("help.title", "help.body"):
        assert k in translations, k


def test_link_rules_keys_present(translations):
    for key in ("entry.off_rule_link",):
        assert key in translations, key
        for lang in SUPPORTED_LANGUAGES:
            text = translations[key][lang]
            for ph in ("{source}", "{target}", "{source_type}", "{target_type}"):
                assert ph in text, (key, lang, ph)


def test_entry_choose_element_key_present(translations):
    assert "entry.choose_element" in translations
    assert translations["entry.choose_element"]["en"] == "— choose —"


def test_causal_paths_keys_present(translations):
    for key in ("metrics.paths", "metrics.paths_trace", "metrics.paths_source",
                "metrics.paths_target", "metrics.paths_summary",
                "metrics.paths_none", "metrics.paths_truncated"):
        assert key in translations


def test_token_diffusion_keys_present(translations):
    for key in ("diffusion.title", "diffusion.source", "diffusion.steps",
                "diffusion.tokens", "diffusion.run", "diffusion.hint",
                "diffusion.none", "diffusion.summary", "diffusion.caption"):
        assert key in translations


def test_bayesian_keys_present(translations):
    for key in ("rate.bayesian", "rate.p_plus", "rate.strength_post",
                "rate.bayesian_legend", "uncertainty.flip_posterior"):
        assert key in translations


def test_bbn_keys_present(translations):
    for key in ("bbn.title", "bbn.source", "bbn.target", "bbn.direction", "bbn.forward",
                "bbn.diagnostic", "bbn.run", "bbn.hint", "bbn.computing", "bbn.no_path",
                "bbn.unavailable", "bbn.summary", "bbn.truncated", "bbn.cut",
                "bbn.target_line", "bbn.about_text",
                "bbn.also_high", "bbn.also_low", "bbn.evidence", "bbn.ignored",
                "bbn.conflict", "bbn.paths_title", "bbn.paths_legend", "bbn.high", "bbn.low",
                "bbn.posterior_links", "bbn.posterior_line"):
        assert key in translations


def test_bbn_evidence_placeholders_match_across_languages(translations):
    import re
    expected = {"bbn.evidence": {"items"}, "bbn.ignored": {"ids"}, "bbn.conflict": {"ids"},
                "bbn.posterior_line": {"rated", "total"}}
    for key, names in expected.items():
        for lang, text in translations[key].items():
            assert set(re.findall(r"\{(\w+)\}", text)) == names, (key, lang, text)
    assert translations["bbn.evidence"]["en"].startswith("Evidence:")
    assert translations["bbn.conflict"]["en"].startswith("Conflicting evidence")
    assert translations["bbn.posterior_line"]["en"].startswith("Links from rater posteriors:")


def test_templates_gallery_keys_present(translations):
    # P2 §6.3: SESPy-only keys (R shows these values untranslated).
    keys = ["templates.group_marinesabres", "templates.group_sespy", "templates.about",
            "templates.complexity_simple", "templates.complexity_complex"]
    keys += [f"templates.category_{s}" for s in (
        "multi_stressor", "extraction", "recreation", "production",
        "pollution", "climate", "energy", "general")]
    for key in keys:
        assert key in translations, key
        for lang in SUPPORTED_LANGUAGES:
            assert translations[key].get(lang, "").strip(), (key, lang)
    assert translations["templates.group_marinesabres"]["en"] == "MarineSABRES templates"
    assert translations["templates.group_sespy"]["en"] == "SESPy examples"
    assert translations["templates.about"]["en"] == "About this template"


def test_every_category_and_complexity_the_port_emits_has_a_key(translations):
    from sespy import r_template_catalogue as C
    categories = {C.CATEGORY_NULL, C.CATEGORY_MULTI, C.CATEGORY_FALLBACK,
                  *(cat for _, cat in C.CATEGORY_RULES)}
    for value in categories:
        slug = value.lower().replace("-", "_")
        assert f"templates.category_{slug}" in translations, value
        assert translations[f"templates.category_{slug}"]["en"] == value
    for value in (C.DEFAULT_COMPLEXITY, "complex"):
        assert f"templates.complexity_{value}" in translations, value


def test_module_scopes_share_the_root_session_translator(translations, monkeypatch):
    # Inside a module server get_current_session() is a SessionProxy. The
    # session translator app.py sets from ?lang= lives on the root session, so
    # get_default() must resolve to it from every scope, nested ones included,
    # not build a fresh clone at the process default per namespace.
    from shiny import module
    from shiny.testserver import test_server

    from sespy import i18n

    monkeypatch.setattr(i18n, "_default_translator", Translator(translations=translations))
    seen = {}

    @module.server
    def inner(input, output, session):
        seen["inner"] = i18n.get_default()

    @module.server
    def outer(input, output, session):
        seen["outer"] = i18n.get_default()
        seen["outer_text"] = i18n.t("templates.load")
        inner("child")

    def server(input, output, session):
        root = i18n.get_default()
        root.set_language("de")
        seen["root"] = root
        outer("parent")

    with test_server(server):
        pass

    assert seen["outer"] is seen["root"]
    assert seen["inner"] is seen["root"]
    assert seen["outer_text"] == translations["templates.load"]["de"]
    assert i18n._default_translator._lang == "en"  # the process default is untouched


# ---- P1b (Task 8): SESPy-only keys in core.json; R keys used directly --------

P1B_CORE_KEYS = [
    # text copied from R translations/common/labels.json at v1.33.0
    "responses.name", "responses.type", "responses.status", "responses.description",
    "responses.target_date", "responses.milestone_status",
    # SESPy text
    "nav.responses", "responses.edit_selected", "responses.cancel", "responses.save",
    "responses.select_first", "responses.select_one", "responses.name_type_required",
    "responses.deleted_with_refs", "responses.tenet_source", "responses.target_element_hint",
    "responses.element_still_referenced",
    "entry.edit_selected", "entry.save_changes", "entry.cancel_edit", "entry.description",
    "entry.registry", "entry.connection_description",
    # plan review round 2: stale-edit refusal and the ISA editors' own toasts
    "responses.record_changed", "entry.record_changed", "entry.label_required",
    "entry.select_first",
]
_RM = "modules.response.measures."
_GOV = "modules.response.governance."
P1B_R_KEYS = [
    *(_RM + k for k in (
        # tabs, buttons, toasts
        "response_register", "impact_assessment", "prioritization", "implementation_plan",
        "delete_selected", "download_response_data_excel",
        "deleted_response_measures", "impact_linkage_added", "milestone_added",
        # plot
        "add_effectiveness_and_feasibility_ratings", "response_measure_prioritization_matrix",
        "feasibility", "effectiveness", "low", "medium", "high",
        "high_priorityneffective_feasible", "effective_butndifficult", "easy_butnlimited_impact",
        "low_priority",
        # the register, impact and milestone labels R uses at response_module.R:28-190,
        # 196-232, 318-345 (v1.33.0; extracted by regex, 51 keys)
        "management_measures_and_policy_interventions", "add_response_measure",
        "eg_fishing_quota_reduction", "targets", "what_does_this_measure_do",
        "mechanism_of_action", "how_will_this_intervention_work", "target_element_id",
        "placeholder_element_ids", "expected_effectiveness", "unknown",
        "estimated_cost_relative", "responsible_stakeholders", "who_implements_this_measure",
        "implementation_barriers", "what_obstacles_exist", "response_measures_register",
        "create_impact_linkage", "select_response", "addresses_problem", "specific_pressure",
        "specific_activity", "specific_driver", "system_wide_issue", "problem_element_id",
        "impact_strength", "strong", "moderate", "weak", "timeframe", "immediate",
        "short_term_1_3y", "medium_term_3_10y", "long_term_10y", "add_impact_link",
        "add_implementation_milestone", "response_measure", "milestone", "eg_legislation_passed",
        "notesactions_required", "pending", "in_progress", "completed", "delayed",
        "add_milestone")),
    *(_GOV + k for k in (
        "section_title", "kind", "ebm_code", "level", "competent_authority", "legal_basis",
        "paired_with", "implementing_stakeholders", "pestle", "tenets_title", "ebm_code_hint",
        "pestle_hint", "no_stakeholders_hint", "tenet_level.not_assessed")),
    *(f"modules.indicator_registry.{k}" for k in (
        "field_indicator", "field_unit", "field_data_source", "field_policy_target",
        "policy_target_help", "policy_target.kmgbf_30x30", "policy_target.eu_nrr",
        "policy_target.msfd_ges_d1", "policy_target.msfd_ges_d6", "policy_target.national_mpa_pct")),
    "modules.wp5_governance.ne_roles", "modules.wp5_governance.ne_roles_hint",
    *(f"modules.wp5_governance.role.{r.lower()}" for r in (
        "Inputters", "Extractors", "Regulators", "Affectees", "Beneficiaries", "Influencers")),
]


def test_p1b_keys_present(translations):
    for key in P1B_CORE_KEYS + P1B_R_KEYS:
        assert key in translations, key
        for lang in SUPPORTED_LANGUAGES:
            assert (translations[key].get(lang) or "").strip(), (key, lang)


def test_p1b_sespy_keys_live_in_core_json():
    import json
    core = json.loads((TRANSLATIONS / "core.json").read_text(encoding="utf-8"))["translation"]
    assert set(P1B_CORE_KEYS) <= set(core)
    assert not {k for k in P1B_R_KEYS if k in core}        # R keys stay vendored


def test_p1b_common_labels_are_r_text(translations):
    # R translations/common/labels.json at v1.33.0 (not vendored; spec §7).
    assert translations["responses.name"]["en"] == "Response Name:"
    assert translations["responses.type"]["lt"] == "Atsako Tipas:"
    assert translations["responses.status"]["de"] == "Umsetzungsstatus:"
    assert translations["responses.description"]["el"] == "Περιγραφή"
    assert translations["responses.target_date"]["fr"] == "Date Cible:"
    assert translations["responses.milestone_status"]["no"] == "Status"


def test_p1b_placeholders_match_across_languages(translations):
    import re
    expected = {"responses.deleted_with_refs": {"n"},
                "responses.element_still_referenced": {"id", "measures"},
                "entry.registry": {"id", "version"}}
    for key, names in expected.items():
        for lang, text in translations[key].items():
            assert set(re.findall(r"\{(\w+)\}", text)) == names, (key, lang, text)
    assert translations["entry.registry"]["en"] == "WP5 registry: {id} (revision {version})"
