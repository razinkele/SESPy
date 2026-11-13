"""Live feedback #18 (2026-11-11): "After answering all the questions of the
Wizard and pressing continue, the progress was deleted."

Reproduced: Finish kept the elements but put the wizard back on its idle
screen (text + "Start Wizard"), identical to a fresh start. Its only button
opened a "Replace existing SES?" modal whose primary button read "Continue,
replace it" — which clears isa_data. The fix (ported from the R app's AI
assistant): after Finish the wizard shows a completion panel with the counts
and links to CLD Visualization / Edit Data, and the destructive modal is a
clearly worded "Start over?" with a red "Yes, start over".
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path

import pytest
import shiny
from shiny import reactive
from shiny.testserver import test_server

from sespy import i18n
from sespy.data_structure import IsaData, Project
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.modules.ai_isa_wizard import ai_isa_wizard_server

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
LANGS = ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el")
FREEFORM = ["drivers", "activities", "pressures", "states", "impacts", "welfare", "responses"]


class _Wiz:
    def __init__(self, ts, holder, modals):
        self.ts, self.holder, self.modals = ts, holder, modals
        self.scope = ts.make_scope("wizard")
        self._clicks: dict[str, int] = {}

    def click(self, button: str) -> None:
        n = self._clicks.get(button)
        if n is None:                       # the init value ignore_init=True skips
            self.scope.set_inputs(**{button: 0})
            n = 0
        self._clicks[button] = n + 1
        self.scope.set_inputs(**{button: n + 1})

    def html(self, output: str = "wizard_step_render") -> str:
        out = self.scope.get_output(output)
        assert out.status == "ok", (out.status, out.error)
        return out.value["html"]

    def project(self) -> Project:
        with reactive.isolate():
            return self.holder[0].get()

    def run_to_finish(self) -> None:
        self.click("wizard_start")
        answers = {0: ("answer_regional_sea", "baltic"),
                   1: ("answer_ecosystem_type", "Open coast"),
                   2: ("answer_countries", ["Lithuania"]),
                   3: ("answer_main_issue", ["Eutrophication"])}
        for step in range(11):
            if step in answers:
                name, value = answers[step]
                self.scope.set_inputs(**{name: value})
            else:
                self.scope.set_inputs(**{f"entry_{FREEFORM[step - 4]}_0": f"Item {step}"})
            self.click("wizard_next")
        n_sugg = len(set(re.findall(r'id="wizard-accept_sp3_(\d+)"', self.html())))
        self.scope.set_inputs(**{f"accept_sp3_{i}": False for i in range(n_sugg)})
        self.click("wizard_finish")


@contextmanager
def _wizard(monkeypatch, project: Project | None = None):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    monkeypatch.setattr(shiny.ui, "notification_show", lambda *a, **kw: None)
    modals: list[str] = []
    monkeypatch.setattr(shiny.ui, "modal_show", lambda m, **kw: modals.append(str(m)))
    monkeypatch.setattr(shiny.ui, "modal_remove", lambda **kw: None)
    holder: list[reactive.Value[Project]] = []
    start = project or Project.from_isa(IsaData())

    def server(input, output, session):
        pd = reactive.value(start)
        holder.append(pd)
        ai_isa_wizard_server("wizard", project_data=pd, event_bus=create_event_bus(),
                             translator=TR)

    with test_server(server) as ts:
        yield _Wiz(ts, holder, modals)


def test_finish_shows_a_completion_panel_not_a_fresh_start(monkeypatch):
    with _wizard(monkeypatch) as wiz:
        wiz.run_to_finish()
        assert len(wiz.project().isa_data.elements) == 7
        html = wiz.html()
        assert TR.t("wizard.complete_title") in html
        assert TR.t("wizard.complete_body", elements=7, connections=0) in html
        # links to the pages that show the SES, via the sidebar nav buttons
        assert "sespy_nav_cld" in html and "sespy_nav_entry" in html
        # starting again is offered as "Start over", not as the fresh-start button
        assert 'id="wizard-wizard_start"' in html
        assert TR.t("wizard.start_over") in html
        assert "Click Start Wizard to begin" not in html


def test_start_over_asks_with_an_unmistakable_destructive_button(monkeypatch):
    with _wizard(monkeypatch) as wiz:
        wiz.run_to_finish()
        wiz.click("wizard_start")
        assert len(wiz.modals) == 1
        modal = wiz.modals[0]
        assert TR.t("wizard.modal_title") in modal
        assert TR.t("wizard.replace") in modal
        assert re.search(r'id="wizard-wizard_replace"[^>]*class="[^"]*btn-danger'
                         r'|class="[^"]*btn-danger[^"]*"[^>]*id="wizard-wizard_replace"', modal)
        # Cancel keeps the SES
        wiz.click("wizard_cancel_modal")
        assert len(wiz.project().isa_data.elements) == 7


def test_confirming_start_over_clears_and_restarts_the_wizard(monkeypatch):
    with _wizard(monkeypatch) as wiz:
        wiz.run_to_finish()
        wiz.click("wizard_start")
        wiz.click("wizard_replace")
        assert wiz.project().isa_data.elements == []
        html = wiz.html()
        assert TR.t("wizard.step_0_title") in html          # wizard active again at step 0
        assert TR.t("wizard.complete_title") not in html


def test_a_fresh_session_still_shows_the_start_screen(monkeypatch):
    with _wizard(monkeypatch) as wiz:
        html = wiz.html()
        assert TR.t("wizard.start") in html
        assert TR.t("wizard.complete_title") not in html


def test_the_destructive_label_no_longer_says_continue():
    tr = load_translations(ROOT / "sespy" / "translations")
    for lang in LANGS:
        assert "continue" not in tr["wizard.replace"][lang].lower()


@pytest.mark.parametrize("key", ["wizard.complete_title", "wizard.complete_body",
                                 "wizard.start_over", "wizard.replace",
                                 "wizard.modal_title", "wizard.modal_body"])
def test_completion_and_start_over_keys_cover_all_languages(key):
    tr = load_translations(ROOT / "sespy" / "translations")
    assert key in tr
    assert set(LANGS) <= set(tr[key])
    english = tr[key]["en"]
    for lang in LANGS[1:]:
        assert tr[key][lang].strip(), (key, lang)
        assert tr[key][lang] != english, f"{key} [{lang}] is untranslated English"
    if key == "wizard.complete_body":
        for lang in LANGS:
            assert "{elements}" in tr[key][lang] and "{connections}" in tr[key][lang], lang
