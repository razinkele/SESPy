"""K1 Task 11: the wizard's country step from R's governance data, and
skippable steps 2-3.

Step 2 offers ``countries_by_sea[sea]`` resolved through ``countries[code]``
(R ``get_countries_for_sea``), grouped as R does into EU member states and
non-EU countries. Option values are ISO codes and labels are ``name_en``.
Steps 2 and 3 accept an empty Next and have a Skip button, as in R.

Every test asserts through ``wizard_answers`` / the assembled
``WizardState`` (module exports) or the rendered step, never through the
freeform row ids, which Task 12 renames.
"""
from __future__ import annotations

import json
import re
from contextlib import contextmanager
from html import unescape
from pathlib import Path

import pytest
import shiny
from shiny import reactive
from shiny.testserver import test_server

import sespy.i18n
from sespy import r_kb
from sespy.claude_backend import _build_user_message
from sespy.data_structure import IsaData, Project, WizardState
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.kb_suggestions import countries_for_sea, country_names_for
from sespy.modules.ai_isa_wizard import _country_choices, ai_isa_wizard_server

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
GOV = r_kb.VENDORED.governance()
EU_LABEL = TR.t("modules.isa.ai_assistant.eu_member_states")
NON_EU_LABEL = TR.t("modules.isa.ai_assistant.non_eu_countries")
SKIP_LABEL = TR.t("modules.isa.ai_assistant.skip_this_question")


@pytest.fixture(autouse=True)
def _pin_translator(monkeypatch):
    # The translator is process-wide: importing app.py elsewhere in the run
    # installs a default. Pin one so text assertions hold in any order.
    monkeypatch.setattr(sespy.i18n, "get_default", lambda: TR)
    monkeypatch.setattr(shiny.ui, "notification_show", lambda *a, **kw: None)


def test_translator_resolves_the_r_keys():
    for label in (EU_LABEL, NON_EU_LABEL, SKIP_LABEL):
        assert not label.startswith("modules."), label


# ---- choices -------------------------------------------------------------------

def _codes(choices: dict) -> list[str]:
    return [code for group in choices.values() for code in group]


def _names(choices: dict) -> dict[str, str]:
    return {code: name for group in choices.values() for code, name in group.items()}


def test_country_choices_from_governance():
    pacific = _codes(_country_choices(GOV, "pacific"))
    assert "FM" in pacific
    assert not {"CN", "JP", "ID", "PH", "CL"} & set(pacific)
    caribbean = _codes(_country_choices(GOV, "caribbean"))
    assert len(caribbean) == 27
    assert "FR" not in caribbean and "NL" not in caribbean
    assert "US" not in _codes(_country_choices(GOV, "atlantic"))
    assert _names(_country_choices(GOV, "arctic"))["DK"] == "Denmark"
    assert _names(_country_choices(GOV, "atlantic"))["FR"] == "France"
    assert _names(_country_choices(GOV, "north_sea"))["NL"] == "Netherlands"
    for sea in ("arctic", "atlantic", "north_sea", "caribbean"):
        for name in _names(_country_choices(GOV, sea)).values():
            assert "(Greenland)" not in name and "(overseas)" not in name


def test_country_choices_group_like_r():
    baltic = _country_choices(GOV, "baltic")
    assert list(baltic) == [EU_LABEL, NON_EU_LABEL]
    assert list(baltic[NON_EU_LABEL]) == ["RU"]
    # within a group, countries_by_sea order (R iterates the list)
    expected_eu = [c["code"] for c in countries_for_sea(GOV, "baltic") if c["eu_member"]]
    assert list(baltic[EU_LABEL]) == expected_eu
    # an empty group is left out, as R leaves out its heading
    assert list(_country_choices(GOV, "pacific")) == [NON_EU_LABEL]
    assert _country_choices(GOV, "other") == {}
    assert _country_choices(GOV, "") == {}


def test_country_names_for():
    assert country_names_for(GOV, ["SE", "LT"]) == ["Sweden", "Lithuania"]
    assert country_names_for(GOV, []) == []
    # a code the data does not know is shown as the code (R: name_en %||% code)
    assert country_names_for(GOV, ["LT", "ZZ"]) == ["Lithuania", "ZZ"]


def test_claude_prompt_uses_names():
    state = WizardState(regional_sea="arctic", countries=["DK", "NO"],
                        country_names=["Denmark", "Norway"])
    msg = _build_user_message(state)
    assert "Countries: Denmark, Norway" in msg
    assert "DK" not in msg.split("Countries:")[1].splitlines()[0]


# ---- the wizard server -----------------------------------------------------------

class _Wiz:
    def __init__(self, ts, reads):
        self.scope = ts.make_scope("wizard")
        self.reads = reads
        self._clicks: dict[str, int] = {}

    def click(self, button: str) -> None:
        n = self._clicks.get(button)
        if n is None:
            self.scope.set_inputs(**{button: 0})
            n = 0
        self._clicks[button] = n + 1
        self.scope.set_inputs(**{button: n + 1})

    def html(self) -> str:
        out = self.scope.get_output("wizard_step_render")
        assert out.status == "ok", (out.status, out.error)
        return out.value["html"]

    def export(self, name: str):
        return self.scope.get_export(name).value

    @property
    def step(self) -> int:
        return self.export("step")

    def answers(self) -> dict:
        return self.export("answers")

    def state(self) -> dict:
        return self.export("wizard_state")

    def to_countries(self, sea: str = "baltic", eco: str = "Open coast") -> None:
        self.click("wizard_start")
        self.scope.set_inputs(answer_regional_sea=sea)
        self.click("wizard_next")
        self.scope.set_inputs(answer_ecosystem_type=eco)
        self.click("wizard_next")
        assert self.step == 2


@contextmanager
def _wizard(*, with_snapshot: bool = True):
    reads_holder: list[reactive.Value[frozenset[str]]] = []

    def server(input, output, session):
        pd = reactive.value(Project.from_isa(IsaData()))
        kwargs = {}
        if with_snapshot:
            rr = reactive.value(frozenset())
            reads_holder.append(rr)
            kwargs = {"snapshot": r_kb.VENDORED, "reference_reads": rr}
        ai_isa_wizard_server("wizard", project_data=pd, event_bus=create_event_bus(),
                             translator=TR, **kwargs)

    with test_server(server) as ts:
        yield _Wiz(ts, reads_holder)


def _reads(wiz: _Wiz) -> frozenset[str]:
    with reactive.isolate():
        return wiz.reads[0].get()


def test_country_optgroups():
    with _wizard() as wiz:
        wiz.to_countries()
        html = wiz.html()
        groups = re.findall(r'<optgroup label="([^"]*)"', html)
        assert [unescape(g) for g in groups] == [EU_LABEL, NON_EU_LABEL]
        assert re.search(r'<option value="LT"[^>]*>Lithuania</option>', html)
        assert re.search(r'<option value="RU"[^>]*>Russia</option>', html)


def test_values_are_codes_and_names_resolved():
    with _wizard() as wiz:
        wiz.to_countries()
        wiz.scope.set_inputs(answer_countries=["LT", "RU"])
        wiz.click("wizard_next")
        assert wiz.step == 3
        assert wiz.answers()["countries"] == ["LT", "RU"]
        state = wiz.state()
        assert state["countries"] == ["LT", "RU"]
        assert state["country_names"] == ["Lithuania", "Russia"]


def test_country_order_kept():
    with _wizard() as wiz:
        wiz.to_countries()
        # reverse of option order: selectize's getValue() returns click order
        wiz.scope.set_inputs(answer_countries=["RU", "SE", "LT"])
        wiz.click("wizard_next")
        state = wiz.state()
        assert state["countries"] == ["RU", "SE", "LT"]
        assert state["country_names"] == ["Russia", "Sweden", "Lithuania"]


def test_back_preserves_country_order():
    with _wizard() as wiz:
        wiz.to_countries()
        wiz.scope.set_inputs(answer_countries=["RU", "LT"])
        wiz.click("wizard_next")
        wiz.click("wizard_back")
        assert wiz.step == 2
        html = wiz.html()
        m = re.search(r'<script type="application/json" data-for="wizard-answer_countries"[^>]*>'
                      r'(.*?)</script>', html, re.S)
        assert m, "selectize options payload missing"
        options = json.loads(unescape(m.group(1)))
        # selectize would rebuild items from <option selected> in DOM order;
        # the items setting restores the click order
        assert options["items"] == ["RU", "LT"]
        assert options["plugins"] == ["remove_button"]


def test_empty_next_allowed_on_steps_2_3():
    with _wizard() as wiz:
        wiz.to_countries()
        # nothing ever selected: the input is unset (SilentException)
        wiz.click("wizard_next")
        assert wiz.step == 3
        assert wiz.answers()["countries"] == []
        wiz.scope.set_inputs(answer_main_issue=[])
        wiz.click("wizard_next")
        assert wiz.step == 4
        assert wiz.answers()["main_issue"] == []
        state = wiz.state()
        assert state["countries"] == [] and state["country_names"] == []


def test_empty_next_still_refused_on_choice_one():
    with _wizard() as wiz:
        wiz.click("wizard_start")
        wiz.scope.set_inputs(answer_regional_sea="")
        wiz.click("wizard_next")
        assert wiz.step == 0


def test_skip_button_records_empty():
    with _wizard() as wiz:
        wiz.to_countries()
        html = wiz.html()
        assert 'id="wizard-skip_countries"' in html and SKIP_LABEL in html
        wiz.scope.set_inputs(answer_countries=["LT"])
        wiz.click("skip_countries")
        assert wiz.step == 3
        assert wiz.answers()["countries"] == []
        assert 'id="wizard-skip_main_issue"' in wiz.html()
        wiz.scope.set_inputs(answer_main_issue=["Eutrophication"])
        wiz.click("skip_main_issue")
        assert wiz.step == 4
        assert wiz.answers()["main_issue"] == []
        assert "skip_" not in wiz.html()


def test_skip_acts_only_on_its_current_step():
    with _wizard() as wiz:
        # inactive wizard: a stale Skip does nothing
        wiz.click("skip_countries")
        assert wiz.step == 0 and wiz.answers() == {}
        wiz.to_countries()
        # Skip for step 3 while on step 2: ignored
        wiz.click("skip_main_issue")
        assert wiz.step == 2 and "main_issue" not in wiz.answers()
        wiz.scope.set_inputs(answer_countries=["LT"])
        wiz.click("wizard_next")
        assert wiz.step == 3
        # Skip for step 2 while on step 3: ignored, countries kept
        wiz.click("skip_countries")
        assert wiz.step == 3 and wiz.answers()["countries"] == ["LT"]


def test_sea_change_filters_codes():
    with _wizard() as wiz:
        wiz.to_countries("baltic")
        picked = ["LT", "RU", "SE", "DK"]
        wiz.scope.set_inputs(answer_countries=picked)
        wiz.click("wizard_next")
        for _ in range(3):
            wiz.click("wizard_back")
        assert wiz.step == 0
        wiz.scope.set_inputs(answer_regional_sea="north_sea")
        wiz.click("wizard_next")
        north = {c["code"] for c in countries_for_sea(GOV, "north_sea")}
        expected = [c for c in picked if c in north]
        assert expected and expected != picked
        assert wiz.answers()["countries"] == expected
        # same sea again: nothing is dropped
        wiz.click("wizard_back")
        wiz.click("wizard_next")
        assert wiz.answers()["countries"] == expected


def test_countries_record_reads():
    with _wizard() as wiz:
        wiz.click("wizard_start")
        wiz.html()
        assert _reads(wiz) == frozenset()
        wiz.scope.set_inputs(answer_regional_sea="baltic")
        wiz.click("wizard_next")
        wiz.scope.set_inputs(answer_ecosystem_type="Open coast")
        wiz.click("wizard_next")
        wiz.html()
        assert _reads(wiz) == frozenset({r_kb.KB_NAME, r_kb.GOVERNANCE_NAME})


def test_wizard_without_snapshot_uses_vendored():
    with _wizard(with_snapshot=False) as wiz:
        wiz.to_countries()
        assert re.search(r'<option value="LT"[^>]*>Lithuania</option>', wiz.html())


def test_other_sea_excluded():
    with _wizard() as wiz:
        wiz.click("wizard_start")
        html = wiz.html()
        assert 'value="baltic"' in html
        assert 'value="other"' not in html
