"""P2 — the Templates panel in memory with shiny.testserver (spec §6.2, §6.3, §8):
two namespaced group headers, MarineSABRES badges and "About this template",
loading by the combined index, and raw R values without a translation key.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import shiny
from shiny import reactive
from shiny.testserver import test_server

import sespy.modules.templates as mod
from sespy import i18n
from sespy.data_structure import IsaData, Project, ProjectMetadata
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.templates import TemplateInfo, list_catalogue

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
CARIBBEAN = "Caribbean Island - Comprehensive SES Template (MarineSABRES)"


@pytest.fixture
def panel(monkeypatch):
    # The module labels with the module-level t(); give it the real
    # translations for this test only (restored by monkeypatch).
    monkeypatch.setattr(i18n, "_default_translator", TR)
    toasts: list[str] = []
    monkeypatch.setattr(shiny.ui, "notification_show",
                        lambda msg, **kw: toasts.append(str(msg)))
    holder: list[reactive.Value[Project]] = []

    def server(input, output, session):
        pd = reactive.value(Project(ProjectMetadata(name="before"), IsaData()))
        holder.append(pd)
        mod.templates_server("templates", project_data=pd,
                             event_bus=create_event_bus(), translator=TR)

    # A factory, so a test can monkeypatch list_catalogue before the server starts.
    yield (lambda: test_server(server)), toasts, holder


def _html(ts) -> str:
    return ts.make_scope("templates").get_output("templates_list").value["html"]


def test_two_namespaced_group_headers_in_order(panel):
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    assert re.search(r'<h4 id="templates-group_marinesabres"[^>]*>MarineSABRES templates</h4>', html)
    assert re.search(r'<h4 id="templates-group_sespy"[^>]*>SESPy examples</h4>', html)
    assert html.index("templates-group_marinesabres") < html.index("sespy-template-badges") \
        < html.index("templates-group_sespy")


def test_h5_are_exactly_the_card_names(panel):
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    names = re.findall(r"<h5[^>]*>(.*?)</h5>", html)
    assert len(names) == 11
    assert names[0] == CARIBBEAN
    assert names[7:] == [r.name for r in mod.list_templates()]


def test_first_card_shows_its_badges_and_about(panel):
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    first = html[html.index(CARIBBEAN): html.index("templates-load_template_0")]
    badges = re.findall(r'<span class="badge[^"]*">(.*?)</span>', first)
    assert badges == ["Multi-Stressor", "Complex", "v1.1", "Caribbean Sea"]
    assert "78 elements · 140 connections" in first
    assert "<summary>About this template</summary>" in first
    assert html.count("sespy-template-badges") == 7      # MarineSABRES cards only
    assert html.count("<details") == 7                    # all 7 have a source


def test_loading_index_0_loads_the_caribbean_template(panel):
    run, toasts, holder = panel
    with run() as ts:
        scope = ts.make_scope("templates")
        scope.set_inputs(load_template_0=0)
        scope.set_inputs(load_template_0=1)
        with reactive.isolate():
            project = holder[0]()
    assert project.metadata.name == CARIBBEAN
    assert project.isa_data.element_count() == 78
    assert toasts == [f"Template loaded. ({CARIBBEAN})"]


def test_index_7_is_the_first_sespy_example(panel):
    run, toasts, holder = panel
    first_sespy = mod.list_templates()[0].name
    with run() as ts:
        scope = ts.make_scope("templates")
        scope.set_inputs(load_template_7=0)
        scope.set_inputs(load_template_7=1)
        with reactive.isolate():
            assert holder[0]().metadata.name == first_sespy


def test_untranslated_category_and_complexity_show_the_raw_value(panel, monkeypatch):
    real = list_catalogue()[0]
    odd = TemplateInfo(**{**real.__dict__, "category": "Kelp Forests",
                          "complexity": "moderate", "regional_sea_label": ""})
    monkeypatch.setattr(mod, "list_catalogue", lambda: [odd])
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    badges = re.findall(r'<span class="badge[^"]*">(.*?)</span>', html)
    assert badges == ["Kelp Forests", "moderate", "v1.1"]
    assert "templates.category_" not in html and "templates.complexity_" not in html


def test_empty_catalogue_renders_no_marinesabres_header(panel, monkeypatch):
    monkeypatch.setattr(mod, "list_catalogue", lambda: [])
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    assert "templates-group_marinesabres" not in html
    assert 'id="templates-group_sespy"' in html


def _core(key: str, lang: str) -> str:
    # core.json nests its entries under a wrapper object.
    data = json.loads((ROOT / "sespy" / "translations" / "core.json")
                      .read_text(encoding="utf-8"))
    flat = next(v for v in data.values() if isinstance(v, dict) and key in v)
    return flat[key][lang]


def test_labels_follow_the_session_translator_not_the_process_default(monkeypatch):
    """F1: inside a module render the global t() resolves to a proxy-local
    clone at the process default ("en"); the gallery must use the translator
    app.py hands in, and re-render when its language changes."""
    monkeypatch.setattr(i18n, "_default_translator", TR)       # process default: en
    session_tr = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
    session_tr.set_language("de")
    monkeypatch.setattr(shiny.ui, "notification_show", lambda *a, **k: None)

    def server(input, output, session):
        pd = reactive.value(Project(ProjectMetadata(name="before"), IsaData()))
        mod.templates_server("templates", project_data=pd,
                             event_bus=create_event_bus(), translator=session_tr)

        # Like app.py's Options switcher: the language changes inside an effect.
        @reactive.effect
        @reactive.event(input.switch_lang, ignore_init=True)
        def _():
            session_tr.set_language(input.switch_lang())

    with test_server(server) as ts:
        html = _html(ts)
        assert _core("templates.group_marinesabres", "de") in html
        assert _core("templates.category_energy", "de") in html
        assert _core("templates.load", "de") in html
        assert "MarineSABRES templates" not in html
        ts.set_inputs(switch_lang="de")     # first value is swallowed by ignore_init
        ts.set_inputs(switch_lang="lt")
        html = _html(ts)
        assert _core("templates.group_marinesabres", "lt") in html
        assert _core("templates.category_energy", "lt") in html
        assert _core("templates.group_marinesabres", "de") not in html


def test_tr_value_on_a_key_miss_returns_the_value(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    assert i18n.t("templates.complexity_moderate") == "templates.complexity_moderate"
    assert mod._tr_value(i18n.t, "complexity", "moderate") == "moderate"
    assert mod._tr_value(i18n.t, "category", "Multi-Stressor") == "Multi-Stressor"
    assert mod._tr_value(i18n.t, "complexity", "complex") == "Complex"
    TR.set_language("de")
    try:
        assert mod._tr_value(i18n.t, "category", "Energy") == "Energie"
    finally:
        TR.set_language("en")
