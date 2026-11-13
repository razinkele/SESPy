"""Live feedback #17 (2026-11-11): "It would be good if in AI-assisted SES
creation it would be possible to change the polarity, since there are some
logical problems. And also in some cases the word 'enables' is not always
suitable ... (What does Rating in the feedback give?)"

Ported from the R app's connection review (connection_review_tabbed.R): each
suggested connection has a +/- polarity switch and a reverse-direction
control; a changed row reads with R's neutral wording (drives/increases,
affects/reduces) instead of the type verb. The Feedback dialog says what the
rating is for.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from html import escape
from pathlib import Path

import pytest
import shiny
from shiny import reactive
from shiny.testserver import test_server

from sespy import i18n
from sespy.data_structure import ConnectionSuggestion, IsaData, Project
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.modules.ai_isa_wizard import (
    _ClaudeIdle, _render_connection_review, ai_isa_wizard_server, ai_isa_wizard_ui,
)
from sespy.modules.topbar_actions import _feedback_modal

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
LANGS = ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el")
FREEFORM = ["drivers", "activities", "pressures", "states", "impacts", "welfare", "responses"]
SUGG = [ConnectionSuggestion(source="R001", target="D001", polarity="+",
                             confidence=0.3, rationale="MPA enables Tourism")]
LABELS = {"R001": "MPA", "D001": "Tourism"}


def test_each_row_has_a_polarity_switch_and_a_reverse_control(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    html = str(_render_connection_review(SUGG, _ClaudeIdle(), False, LABELS))
    assert 'id="pol_sp3_0"' in html and 'id="swap_sp3_0"' in html
    row = re.search(r'<tr[^>]*class="wiz-sugg"[^>]*>', html).group(0)
    for attr, value in (("data-from-label", "MPA"), ("data-to-label", "Tourism"),
                        ("data-pol", "+"),
                        ("data-vpos", TR.t("wizard.verb_positive")),
                        ("data-vneg", TR.t("wizard.verb_negative"))):
        assert f'{attr}="{escape(value)}"' in row, attr
    assert re.search(r'id="pol_sp3_0"[^>]*checked', html)          # "+" starts on


def test_the_page_carries_the_row_updater_script(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    html = str(ai_isa_wizard_ui("wizard"))
    assert "wiz-sugg" in html and "<script" in html


# ---- what Finish saves -------------------------------------------------------

@contextmanager
def _wizard(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    monkeypatch.setattr(shiny.ui, "notification_show", lambda *a, **kw: None)
    holder: list[reactive.Value[Project]] = []

    def server(input, output, session):
        pd = reactive.value(Project.from_isa(IsaData()))
        holder.append(pd)
        ai_isa_wizard_server("wizard", project_data=pd, event_bus=create_event_bus(),
                             translator=TR)

    with test_server(server) as ts:
        yield ts.make_scope("wizard"), holder


def _drive_to_review(scope):
    clicks = {"n": 0}

    def click(btn):
        scope.set_inputs(**{btn: 0}) if btn not in clicks else None
        clicks.setdefault(btn, 0)
        clicks[btn] += 1
        scope.set_inputs(**{btn: clicks[btn]})

    click("wizard_start")
    answers = {0: ("answer_regional_sea", "baltic"), 1: ("answer_ecosystem_type", "Open coast"),
               2: ("answer_countries", ["Lithuania"]), 3: ("answer_main_issue", ["Eutrophication"])}
    for step in range(11):
        if step in answers:
            scope.set_inputs(**{answers[step][0]: answers[step][1]})
        else:
            scope.set_inputs(**{f"entry_{FREEFORM[step - 4]}_0": f"Item {step}"})
        click("wizard_next")
    html = scope.get_output("wizard_step_render").value["html"]
    n = len(set(re.findall(r'id="wizard-accept_sp3_(\d+)"', html)))
    assert n >= 1
    scope.set_inputs(**{f"accept_sp3_{i}": False for i in range(n)})
    return html, click


def _first_suggestion(html):
    row = re.search(r'<tr[^>]*class="wiz-sugg"[^>]*data-from-id="([^"]+)"[^>]*data-to-id="([^"]+)"'
                    r'[^>]*data-pol="([+-])"', html)
    return row.group(1), row.group(2), row.group(3)


def test_finish_saves_a_flipped_and_reversed_connection(monkeypatch):
    with _wizard(monkeypatch) as (scope, holder):
        html, click = _drive_to_review(scope)
        src, tgt, pol = _first_suggestion(html)
        scope.set_inputs(accept_sp3_0=True, pol_sp3_0=(pol != "+"), swap_sp3_0=True)
        click("wizard_finish")
        with reactive.isolate():
            conns = holder[0].get().isa_data.connections
        flipped = "-" if pol == "+" else "+"
        assert [(c.source, c.target, c.polarity) for c in conns] == [(tgt, src, flipped)]


def test_finish_keeps_an_unchanged_row_as_suggested(monkeypatch):
    with _wizard(monkeypatch) as (scope, holder):
        html, click = _drive_to_review(scope)
        src, tgt, pol = _first_suggestion(html)
        scope.set_inputs(accept_sp3_0=True)                 # switch/reverse never touched
        click("wizard_finish")
        with reactive.isolate():
            conns = holder[0].get().isa_data.connections
        assert [(c.source, c.target, c.polarity) for c in conns] == [(src, tgt, pol)]


# ---- rating hint ---------------------------------------------------------------

def test_feedback_dialog_says_what_the_rating_is_for():
    html = str(_feedback_modal(TR))
    assert escape(TR.t("feedback.rating_help"), quote=False) in html


@pytest.mark.parametrize("key", ["wizard.verb_positive", "wizard.verb_negative",
                                 "wizard.reverse", "feedback.rating_help"])
def test_new_keys_cover_all_languages(key):
    tr = load_translations(ROOT / "sespy" / "translations")
    for lang in LANGS:
        assert tr[key].get(lang, "").strip(), (key, lang)
    assert sum(tr[key][lang] != tr[key]["en"] for lang in LANGS[1:]) >= 7, key
