"""K1 Task 13: knowledge-base suggestion chips on wizard steps 4-10 (spec §4.3,
rules for chips 1-7).

Chips write through Task 12's pending overlay; they never write
``wizard_answers``. In ``test_server`` there is no client, so
``ui.update_text`` is never echoed: the tests spy on it and simulate the echo
with a following ``set_inputs(entry_...=value)``. "Same flush" means one
``set_inputs`` call carrying both buttons; effects then run in keyword order.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from html import unescape
from pathlib import Path

import pytest
import shiny
from shiny import reactive
from shiny.testserver import test_server

import sespy.i18n
import sespy.modules.ai_isa_wizard as wiz_mod
from sespy import r_kb
from sespy.data_structure import IsaData, Project
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.kb_suggestions import get_context_suggestions
from sespy.modules.ai_isa_wizard import _chips_caption, ai_isa_wizard_server

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
FREEFORM = ["drivers", "activities", "pressures", "states", "impacts", "welfare", "responses"]
SEA, ECO, CODES = "baltic", "Coastal lagoon", ["LT", "PL"]
KB, GOV = r_kb.VENDORED.kb(), r_kb.VENDORED.governance()


def sugg(target: str = "drivers") -> list[tuple[str, str]]:
    """Task 6's output for the scenario every test drives."""
    return get_context_suggestions(KB, GOV, target, SEA, ECO, ["Eutrophication"], CODES)


def T(i: int, target: str = "drivers") -> str:
    return sugg(target)[i][0]


@pytest.fixture(autouse=True)
def _pin_translator(monkeypatch):
    # The translator is process-wide; pin one so the run order cannot matter.
    monkeypatch.setattr(sespy.i18n, "get_default", lambda: TR)
    monkeypatch.setattr(shiny.ui, "notification_show", lambda *a, **kw: None)
    monkeypatch.setattr(shiny.ui, "modal_show", lambda *a, **kw: None)
    monkeypatch.setattr(shiny.ui, "modal_remove", lambda *a, **kw: None)


@pytest.fixture
def updates(monkeypatch):
    """Every ui.update_text call as (id, value)."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(shiny.ui, "update_text",
                        lambda id, *a, value=None, **kw: calls.append((id, value)))
    return calls


class _Wiz:
    def __init__(self, ts, holder):
        self.scope = ts.make_scope("wizard")
        self.holder = holder
        self._clicks: dict[str, int] = {}

    def press(self, *buttons: str) -> None:
        """Click `buttons` in ONE flush (in this order); unprimed buttons are
        primed with 0 in an earlier flush first."""
        unprimed = {b: 0 for b in buttons if b not in self._clicks}
        if unprimed:
            self.scope.set_inputs(**unprimed)
            self._clicks.update(unprimed)
        nxt = {}
        for b in buttons:
            self._clicks[b] += 1
            nxt[b] = self._clicks[b]
        self.scope.set_inputs(**nxt)

    def click(self, button: str) -> None:
        self.press(button)

    def chip(self, i: int, target: str = "drivers") -> None:
        self.press(f"chip_{target}_{i}")

    def export(self, name: str):
        return self.scope.get_export(name).value

    @property
    def step(self) -> int:
        return self.export("step")

    def gen(self, target: str = "drivers") -> int:
        return self.export("gen")[target]

    def pending(self) -> dict:
        return self.export("pending")

    def rid(self, i: int, target: str = "drivers") -> str:
        return f"entry_{self.gen(target)}_{target}_{i}"

    def type(self, i: int, value: str, target: str = "drivers") -> None:
        self.scope.set_inputs(**{self.rid(i, target): value})

    def html(self) -> str:
        out = self.scope.get_output("wizard_step_render")
        assert out.status == "ok", (out.status, out.error)
        return out.value["html"]

    def chips_html(self, target: str = "drivers") -> str:
        out = self.scope.get_output(f"chips_{target}")
        assert out.status == "ok", (out.status, out.error)
        return out.value["html"] if out.value else ""

    def chips(self, target: str = "drivers") -> list[tuple[str, str, str | None]]:
        """(name, on|off, badge) per rendered chip, in index order."""
        found = {}
        for m in re.finditer(r'<button\b([^>]*)>(.*?)</button>', self.chips_html(target), re.S):
            attrs, inner = m.groups()
            idm = re.search(rf'id="wizard-chip_{target}_(\d+)"', attrs)
            if not idm:
                continue
            state = "on" if "chip-on" in attrs else "off" if "chip-off" in attrs else "?"
            badge = re.search(r'kb-badge-(KB|GOV|SE)"[^>]*>([^<]*)<', inner)
            name = re.sub(r"<span[^>]*kb-badge.*?</span>", "", inner, flags=re.S)
            name = unescape(re.sub(r"<[^>]+>", "", name)).strip()
            found[int(idm.group(1))] = (name, state, badge.group(1) if badge else None)
        return [found[i] for i in sorted(found)]

    def on(self, target: str = "drivers") -> list[str]:
        return [n for n, s, _b in self.chips(target) if s == "on"]

    def rows(self, target: str = "drivers") -> list[str]:
        """Rendered row values of the current generation, in order."""
        g = self.gen(target)
        found: dict[int, str] = {}
        for tag in re.findall(r"<input\b[^>]*>", self.html()):
            m = re.search(rf'id="wizard-entry_{g}_{target}_(\d+)"', tag)
            if m:
                v = re.search(r'\bvalue="([^"]*)"', tag)
                found[int(m.group(1))] = unescape(v.group(1)) if v else ""
        return [found[i] for i in sorted(found)]

    def to_drivers(self) -> None:
        self.click("wizard_start")
        self.scope.set_inputs(answer_regional_sea=SEA)
        self.click("wizard_next")
        self.scope.set_inputs(answer_ecosystem_type=ECO)
        self.click("wizard_next")
        self.scope.set_inputs(answer_countries=CODES)
        self.click("wizard_next")
        self.scope.set_inputs(answer_main_issue=["Eutrophication"])
        self.click("wizard_next")
        assert self.step == 4

    def next_with(self, text: str, target: str) -> None:
        self.type(0, text, target)
        self.click("wizard_next")


@contextmanager
def _wizard(reads=None):
    holder: list[reactive.Value[Project]] = []

    def server(input, output, session):
        pd = reactive.value(Project.from_isa(IsaData()))
        holder.append(pd)
        kw = {} if reads is None else {"reference_reads": reads}
        ai_isa_wizard_server("wizard", project_data=pd, event_bus=create_event_bus(),
                             translator=TR, **kw)

    with test_server(server) as ts:
        yield _Wiz(ts, holder)


# ---- rendering ---------------------------------------------------------------------

def test_chips_match_r_first_12():
    expected = sugg("drivers")[:12]
    badge = {"knowledge_db": "KB", "governance": "GOV", "socioeconomic": "SE"}
    assert {s for _n, s in expected} >= {"knowledge_db", "governance", "socioeconomic"}
    with _wizard() as wiz:
        wiz.to_drivers()
        assert wiz.chips() == [(n, "off", badge.get(s)) for n, s in expected]
        html = wiz.chips_html()
        # R's tooltip keys on the badges
        assert f'title="{TR.t("modules.isa.ai_assistant.from_knowledge_database")}"' in html
        assert f'title="{TR.t("modules.isa.ai_assistant.governance_suggestion_tooltip")}"' in html
        assert f'title="{TR.t("modules.isa.ai_assistant.socioeconomic_suggestion_tooltip")}"' in html
        # mounted inside the freeform widget
        assert 'id="wizard-chips_drivers"' in wiz.html()


def test_chips_capped_at_12_on_a_long_list():
    full = sugg("responses")
    assert len(full) > 12                                   # the cap is exercised
    with _wizard() as wiz:
        wiz.to_drivers()
        for t_ in FREEFORM[:-1]:
            wiz.next_with(f"x {t_}", t_)
        assert wiz.step == 10
        assert [n for n, _s, _b in wiz.chips("responses")] == [n for n, _s in full[:12]]


def test_caption_without_ecosystem():
    assert _chips_caption("baltic", None) == " (tailored for Baltic Sea)"
    assert _chips_caption("baltic", "") == " (tailored for Baltic Sea)"


def test_caption_with_ecosystem():
    assert _chips_caption("baltic", ECO) == " (tailored for Baltic Sea - Coastal lagoon)"
    with _wizard() as wiz:
        wiz.to_drivers()
        assert "(tailored for Baltic Sea - Coastal lagoon)" in wiz.chips_html()


def test_chips_render_only_current_step(monkeypatch):
    calls: list[str] = []

    def spy(*a, **kw):
        calls.append(a[2])
        return get_context_suggestions(*a, **kw)

    monkeypatch.setattr(wiz_mod, "get_context_suggestions", spy)
    with _wizard() as wiz:
        wiz.to_drivers()
        assert calls == ["drivers"]                         # steps 0-3: none
        for t_ in FREEFORM[1:]:
            assert wiz.chips_html(t_).strip() in ("", "<div></div>")
        wiz.type(0, "typing")                               # typing: no recompute
        wiz.type(0, "")
        wiz.chip(0)                                         # chips: no recompute
        wiz.chip(0)                                         # (select, then deselect)
        wiz.click("add_drivers")
        wiz.click("remove_drivers")
        wiz.click("wizard_next")                            # failed Next: no recompute
        assert wiz.step == 4
        assert calls == ["drivers"]
        wiz.type(0, "D")
        wiz.click("wizard_next")
        assert calls == ["drivers", "activities"]
        assert wiz.chips_html("drivers").strip() in ("", "<div></div>")
        wiz.click("wizard_back")                            # Back into a step: one call
        assert calls == ["drivers", "activities", "drivers"]


def test_typing_and_chip_fill_do_not_rerender_step(monkeypatch, updates):
    # T12-m1: the step render reads pending and live inputs under isolate().
    renders: list[int] = []
    real = wiz_mod._render_freeform_multiple

    def counting(*a, **kw):
        renders.append(1)
        return real(*a, **kw)

    monkeypatch.setattr(wiz_mod, "_render_freeform_multiple", counting)
    with _wizard() as wiz:
        wiz.to_drivers()
        n = len(renders)
        wiz.type(0, "a")
        wiz.type(0, "ab")
        wiz.type(0, "")
        wiz.chip(0)                                         # fill path: pending only
        wiz.type(0, T(0))                                   # echo
        assert len(renders) == n
        assert wiz.on() == [T(0)]


# ---- selecting and deselecting (rules 4 and 5) ----------------------------------------

def test_select_fills_first_empty_then_adds_row(updates):
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "")
        wiz.chip(0)
        assert wiz.pending() == {"drivers": {"0": T(0)}}
        assert updates == [(wiz.rid(0), T(0))]
        wiz.type(0, T(0))                                   # client echo
        assert wiz.pending() == {"drivers": {}}
        assert wiz.on() == [T(0)]
        wiz.chip(1)                                         # no empty row: add one
        assert wiz.pending() == {"drivers": {"1": T(1)}}
        assert len(updates) == 1                            # the new row has no input yet
        assert wiz.rows() == [T(0), T(1)]
        assert wiz.on() == [T(0), T(1)]
        assert "drivers" not in wiz.export("answers")      # chips never write answers
        wiz.click("wizard_next")
        assert wiz.export("answers")["drivers"] == [T(0), T(1)]


def test_deselect_blanks_all_matches_in_place(updates):
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, T(0))
        wiz.click("add_drivers")
        wiz.type(1, "Other")
        wiz.click("add_drivers")
        wiz.type(2, T(0) + " ")
        assert wiz.on() == [T(0)]
        wiz.chip(0)
        assert wiz.pending() == {"drivers": {"0": "", "2": ""}}
        assert sorted(updates) == sorted([(wiz.rid(0), ""), (wiz.rid(2), "")])
        assert wiz.on() == []
        wiz.click("add_drivers")                            # nothing shifted
        assert wiz.rows() == ["", "Other", "", ""]
        wiz.click("wizard_next")
        assert wiz.export("answers")["drivers"] == ["Other"]


def test_hand_typed_text_selects_chip_including_trailing_space(updates):
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, T(3))
        assert wiz.on() == [T(3)]
        wiz.type(0, T(3) + " ")
        assert wiz.on() == [T(3)]
        wiz.chip(3)                                         # deselects the typed row
        assert wiz.pending() == {"drivers": {"0": ""}}
        assert updates == [(wiz.rid(0), "")]
        assert wiz.on() == []


def test_case_variant_is_distinct():
    with _wizard() as wiz:
        wiz.to_drivers()
        variant = T(0).lower()
        assert variant != T(0)
        wiz.type(0, variant)
        assert wiz.on() == []                               # exact, case-sensitive
        wiz.chip(0)                                         # selects: row 0 is taken
        assert wiz.pending() == {"drivers": {"1": T(0)}}
        assert wiz.on() == [T(0)]
        wiz.click("wizard_next")
        assert wiz.export("answers")["drivers"] == [variant, T(0)]


def test_two_different_chips_same_flush_with_empty_row(updates):
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "")
        wiz.press("chip_drivers_0", "chip_drivers_1")
        assert wiz.pending() == {"drivers": {"0": T(0), "1": T(1)}}
        assert wiz.rows() == [T(0), T(1)]
        assert wiz.on() == [T(0), T(1)]


def test_two_different_chips_same_flush_without_empty_row():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "typed A")
        wiz.press("chip_drivers_0", "chip_drivers_1")
        assert wiz.pending() == {"drivers": {"1": T(0), "2": T(1)}}
        assert wiz.rows() == ["typed A", T(0), T(1)]


def test_chip_then_next_same_flush_fill_path():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "")
        wiz.press("chip_drivers_0", "wizard_next")
        assert wiz.step == 5
        assert wiz.export("answers")["drivers"] == [T(0)]
        assert wiz.pending() == {}


def test_chip_then_next_same_flush_added_row_path():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "typed A")
        wiz.press("chip_drivers_1", "wizard_next")
        assert wiz.step == 5
        assert wiz.export("answers")["drivers"] == ["typed A", T(1)]
        assert wiz.pending() == {}


def test_chip_then_next_same_flush_then_back_shows_saved():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "")
        wiz.press("chip_drivers_0", "wizard_next")
        wiz.click("wizard_back")
        assert wiz.step == 4
        assert wiz.rows() == [T(0)]
        assert wiz.on() == [T(0)]


def test_chip_and_back_same_flush_then_reenter_no_leak():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.next_with(T(0), "drivers")
        assert wiz.step == 5
        wiz.type(0, "", "activities")
        wiz.press("chip_activities_4", "wizard_back")
        assert wiz.step == 4
        wiz.click("wizard_next")                            # saved drivers, unchanged
        assert wiz.step == 5
        assert wiz.rows("activities") == [""]
        assert wiz.on("activities") == []
        assert wiz.pending() == {}


def test_add_remove_interleaved_with_chips():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.click("add_drivers")
        wiz.click("add_drivers")
        for i in range(3):
            wiz.type(i, "")
        wiz.chip(0)
        wiz.type(0, T(0))
        wiz.chip(1)
        wiz.type(1, T(1))
        wiz.click("remove_drivers")
        assert wiz.rows() == [T(0), T(1)]
        wiz.chip(4)                                         # no empty row: added row
        assert wiz.rows() == [T(0), T(1), T(4)]
        wiz.click("remove_drivers")
        assert wiz.rows() == [T(0), T(1)]
        assert wiz.pending() == {"drivers": {}}
        assert wiz.on() == [T(0), T(1)]
        wiz.click("wizard_next")
        assert wiz.export("answers")["drivers"] == [T(0), T(1)]


def test_type_row1_remove_then_chip_with_no_empty_row():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "typed A")
        wiz.click("add_drivers")
        wiz.type(1, "removed B")
        wiz.click("remove_drivers")
        wiz.chip(2)
        assert wiz.rows() == ["typed A", T(2)]              # not the stale "removed B"
        wiz.click("add_drivers")
        assert wiz.rows() == ["typed A", T(2), ""]
        wiz.click("wizard_next")
        assert wiz.export("answers")["drivers"] == ["typed A", T(2)]


def test_added_row_chip_and_failing_next_same_flush_keeps_row():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.click("add_drivers")
        wiz.type(0, "X")
        wiz.type(1, "X")
        wiz.press("chip_drivers_0", "wizard_next")          # Next fails: duplicates
        assert wiz.step == 4
        assert wiz.pending() == {"drivers": {"2": T(0)}}
        assert wiz.rows() == ["X", "X", T(0)]


def test_chip_for_other_target_ignored(updates):
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "")
        wiz.chip(0, "activities")
        wiz.chip(0, "impacts")
        assert wiz.pending() == {}
        assert updates == []
        assert wiz.rows() == [""]
        # Next then a chip in the same flush: the chip's step is gone
        wiz.type(0, "typed A")
        wiz.press("wizard_next", "chip_drivers_0")
        assert wiz.step == 5
        assert wiz.export("answers")["drivers"] == ["typed A"]
        assert wiz.pending() == {}


def test_chip_past_end_of_list_does_nothing():
    n = len(sugg("impacts"))
    assert n < 12
    with _wizard() as wiz:
        wiz.to_drivers()
        for t_ in FREEFORM[:4]:
            wiz.next_with(f"x {t_}", t_)
        assert wiz.step == 8
        assert len(wiz.chips("impacts")) == n
        wiz.type(0, "", "impacts")
        wiz.chip(n, "impacts")
        wiz.chip(11, "impacts")
        assert wiz.pending() == {}
        wiz.chip(n - 1, "impacts")
        assert wiz.pending() == {"impacts": {"0": T(n - 1, "impacts")}}


def test_reads_recorded_once():
    reads: reactive.Value[frozenset[str]] = reactive.value(frozenset())
    sets: list[frozenset[str]] = []
    real_set = reads.set

    def counting_set(v):
        sets.append(v)
        return real_set(v)

    reads.set = counting_set                                # type: ignore[method-assign]
    with _wizard(reads) as wiz:
        wiz.click("wizard_start")
        wiz.scope.set_inputs(answer_regional_sea=SEA)
        wiz.click("wizard_next")
        wiz.scope.set_inputs(answer_ecosystem_type=ECO)
        wiz.click("wizard_next")
        wiz.scope.set_inputs(answer_countries=CODES)
        wiz.click("wizard_next")
        # The country step recorded both files already; drop them (as a load
        # does) so the chips' own add_reads is what is under test.
        with reactive.isolate():
            real_set(frozenset())
        sets.clear()
        wiz.scope.set_inputs(answer_main_issue=["Eutrophication"])
        wiz.click("wizard_next")
        assert wiz.step == 4
        expected = frozenset({"ses_knowledge_db.json", "country_governance_db.json"})
        with reactive.isolate():
            assert reads.get() == expected
        wiz.chip(0)
        wiz.next_with("D", "drivers")
        wiz.next_with("A", "activities")
        assert wiz.step == 6
        assert sets == [expected]


def test_back_deselect_add_stays_blank(updates):
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "")
        for i in range(3):
            wiz.chip(i)
        wiz.click("wizard_next")
        assert wiz.export("answers")["drivers"] == [T(0), T(1), T(2)]
        wiz.click("wizard_back")
        assert wiz.rows() == [T(0), T(1), T(2)]
        for i in range(3):                                  # the client registers the rows
            wiz.type(i, T(i))
        updates.clear()
        wiz.chip(1)                                         # deselect a saved item
        assert updates == [(wiz.rid(1), "")]
        assert wiz.pending() == {"drivers": {"1": ""}}
        wiz.click("add_drivers")                            # before the echo
        assert wiz.rows() == [T(0), "", T(2), ""]
        wiz.type(1, "")                                     # echo
        wiz.click("add_drivers")
        assert wiz.rows() == [T(0), "", T(2), "", ""]
        wiz.click("wizard_next")
        assert wiz.export("answers")["drivers"] == [T(0), T(2)]


def test_typing_after_server_fill_wins():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "")
        wiz.chip(0)
        wiz.type(0, T(0))                                   # echo clears pending
        assert wiz.pending() == {"drivers": {}}
        wiz.type(0, "Edited")
        assert wiz.on() == []
        wiz.click("wizard_next")
        assert wiz.export("answers")["drivers"] == ["Edited"]
