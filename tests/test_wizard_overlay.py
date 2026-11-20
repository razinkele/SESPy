"""K1 Task 12: the wizard's freeform rows use a pending overlay and per-visit
row-id generations (spec §4.3).

Row ids are ``entry_{gen}_{target}_{i}``; ``gen[target]`` is bumped whenever
the step is entered and on Replace. A row's effective value is the pending
server write, else the live input of this generation, else the saved answer.

Tests read ``pending`` and ``gen`` through the module's test exports and
assert outcomes through exports and state, never through toast wording.
In ``test_server`` there is no client: an input the server renders stays
unset until the test sets it, which plays the client's part.
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
from sespy.data_structure import ELEMENT_TYPE_MAP, IsaData, Project
from sespy.event_bus import create_event_bus
from sespy.modules.ai_isa_wizard import ai_isa_wizard_server
from sespy.ui_i18n import Translator, load_translations

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
FREEFORM = ["drivers", "activities", "pressures", "states", "impacts", "welfare", "responses"]


@pytest.fixture(autouse=True)
def _pin_translator(monkeypatch):
    # The translator is process-wide; pin one so the run order cannot matter.
    monkeypatch.setattr(sespy.i18n, "get_default", lambda: TR)
    monkeypatch.setattr(shiny.ui, "notification_show", lambda *a, **kw: None)
    monkeypatch.setattr(shiny.ui, "modal_show", lambda *a, **kw: None)
    monkeypatch.setattr(shiny.ui, "modal_remove", lambda *a, **kw: None)


class _Wiz:
    def __init__(self, ts, holder):
        self.scope = ts.make_scope("wizard")
        self.holder = holder
        self._clicks: dict[str, int] = {}

    def click(self, button: str) -> None:
        n = self._clicks.get(button)
        if n is None:                       # prime: ignore_init skips the 0
            self.scope.set_inputs(**{button: 0})
            n = 0
        self._clicks[button] = n + 1
        self.scope.set_inputs(**{button: n + 1})

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

    def rows(self, target: str = "drivers") -> list[str]:
        """Rendered row values of the current generation, in order."""
        g = self.gen(target)
        html = self.html()
        found: dict[int, str] = {}
        for tag in re.findall(r"<input\b[^>]*>", html):
            m = re.search(rf'id="wizard-entry_{g}_{target}_(\d+)"', tag)
            if m:
                v = re.search(r'\bvalue="([^"]*)"', tag)
                found[int(m.group(1))] = unescape(v.group(1)) if v else ""
        return [found[i] for i in sorted(found)]

    def elements(self, elem_type: str = ELEMENT_TYPE_MAP["drivers"]) -> list[tuple[str, str]]:
        with reactive.isolate():
            els = self.holder[0].get().isa_data.elements
        return [(e.id, e.label) for e in els if e.type == elem_type]

    def to_drivers(self) -> None:
        self.click("wizard_start")
        self.scope.set_inputs(answer_regional_sea="baltic")
        self.click("wizard_next")
        self.scope.set_inputs(answer_ecosystem_type="Open coast")
        self.click("wizard_next")
        self.scope.set_inputs(answer_countries=["LT"])
        self.click("wizard_next")
        self.scope.set_inputs(answer_main_issue=["Eutrophication"])
        self.click("wizard_next")
        assert self.step == 4


@contextmanager
def _wizard():
    holder: list[reactive.Value[Project]] = []

    def server(input, output, session):
        pd = reactive.value(Project.from_isa(IsaData()))
        holder.append(pd)
        ai_isa_wizard_server("wizard", project_data=pd, event_bus=create_event_bus(),
                             translator=TR)

    with test_server(server) as ts:
        yield _Wiz(ts, holder)


# ---- rendering ---------------------------------------------------------------------

def test_rows_carry_gen_ids_data_row_and_namespaced_container():
    with _wizard() as wiz:
        wiz.to_drivers()
        html = wiz.html()
        g = wiz.gen()
        assert g >= 1                                   # entering the step bumped it
        assert 'id="wizard-freeform_drivers_container"' in html
        tag = re.search(rf'<input\b[^>]*id="wizard-entry_{g}_drivers_0"[^>]*>', html).group(0)
        assert 'data-row="drivers_0"' in tag            # on the <input>, not the wrapper
        assert 'id="wizard-entry_drivers_0"' not in html
        assert wiz.pending() == {}


# ---- the brief's scenarios -----------------------------------------------------------

def test_remove_then_add_no_stale_text():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "Tourism")
        wiz.click("add_drivers")
        wiz.type(1, "Stale text")
        wiz.click("remove_drivers")
        assert wiz.rows() == ["Tourism"]
        # Re-adding index 1: its live input still holds "Stale text" in this
        # generation; the tombstone makes the new row start blank.
        wiz.click("add_drivers")
        assert wiz.pending() == {"drivers": {"1": ""}}
        assert wiz.rows() == ["Tourism", ""]
        # the client echoes the blank; the clearing effect drops the entry
        wiz.type(1, "")
        assert wiz.pending() == {"drivers": {}}
        # typing afterwards wins (pending no longer masks it)
        wiz.type(1, "Fishing")
        wiz.click("wizard_next")
        assert wiz.step == 5
        assert wiz.export("answers")["drivers"] == ["Tourism", "Fishing"]


def test_remove_then_add_without_typing_saves_only_row_0():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "Tourism")
        wiz.click("add_drivers")
        wiz.type(1, "Stale text")
        wiz.click("remove_drivers")
        wiz.click("add_drivers")
        wiz.click("wizard_next")                         # no echo yet: pending wins
        assert wiz.export("answers")["drivers"] == ["Tourism"]


def test_replace_then_reenter_blank():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "Old driver")
        wiz.click("wizard_next")
        assert wiz.step == 5
        old_gen = wiz.gen()
        wiz.click("wizard_start")                        # non-empty project: modal
        wiz.click("wizard_replace")
        assert wiz.step == 0 and wiz.pending() == {}
        with reactive.isolate():
            assert wiz.holder[0].get().isa_data.elements == []
        wiz.to_drivers()
        assert wiz.gen() > old_gen
        assert wiz.rows() == [""]
        assert "Old driver" not in wiz.html()
        # The previous run's input still holds "Old driver" on the server,
        # but under an old id: an untouched Next is empty and refused.
        wiz.click("wizard_next")
        assert wiz.step == 4
        assert "drivers" not in wiz.export("answers")


def test_failed_next_keeps_pending_row():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "")
        wiz.click("add_drivers")
        wiz.type(1, "Typed then removed")
        wiz.click("remove_drivers")
        wiz.click("add_drivers")                         # tombstone over the stale value
        assert wiz.pending() == {"drivers": {"1": ""}}
        wiz.click("wizard_next")                         # every effective row is empty
        assert wiz.step == 4
        assert "drivers" not in wiz.export("answers")
        # a failed Next does not re-render; the pending row survives it
        assert wiz.pending() == {"drivers": {"1": ""}}


def test_back_next_idempotent():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "Tourism")
        wiz.click("add_drivers")
        wiz.type(1, "Fishing")
        wiz.click("wizard_next")
        first = wiz.elements()
        assert [label for _id, label in first] == ["Tourism", "Fishing"]
        gens = [wiz.gen()]
        # Back/Next without echoing the new rows (inputs of the new visit unset)
        wiz.click("wizard_back")
        assert wiz.step == 4
        gens.append(wiz.gen())
        assert wiz.rows() == ["Tourism", "Fishing"]
        wiz.click("wizard_next")
        assert wiz.step == 5 and wiz.elements() == first
        # Back/Next with the client sending the rendered values
        wiz.click("wizard_back")
        gens.append(wiz.gen())
        wiz.type(0, "Tourism")
        wiz.type(1, "Fishing")
        wiz.click("wizard_next")
        assert wiz.step == 5 and wiz.elements() == first
        assert wiz.export("answers")["drivers"] == ["Tourism", "Fishing"]
        assert gens == sorted(set(gens))                 # a new generation per visit
        assert wiz.pending() == {}


def test_unsaved_text_discarded_by_back():
    # Behaviour change (spec §4.3): only Next persists a step's text. Before
    # K1 it survived Back by accident, through sticky input ids.
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "Never saved")
        wiz.click("wizard_back")
        assert wiz.step == 3
        wiz.click("wizard_next")
        assert wiz.step == 4
        assert wiz.rows() == [""]
        wiz.click("wizard_next")
        assert wiz.step == 4                             # nothing to save: refused


def test_saved_text_survives_back_edit_discarded():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "Saved")
        wiz.click("wizard_next")
        wiz.click("wizard_back")
        wiz.type(0, "Edited, not saved")
        wiz.click("wizard_back")
        wiz.click("wizard_next")
        assert wiz.rows() == ["Saved"]


# ---- entry paths and lifetimes ---------------------------------------------------------

def test_skip_into_freeform_step_starts_a_new_visit():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "Never saved")
        g = wiz.gen()
        wiz.click("wizard_back")
        wiz.click("skip_main_issue")                     # step 3 -> 4 via Skip
        assert wiz.step == 4
        assert wiz.gen() == g + 1
        assert wiz.rows() == [""]


def test_back_drops_pending_of_the_left_visit():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "")
        wiz.click("add_drivers")
        wiz.type(1, "x")
        wiz.click("remove_drivers")
        wiz.click("add_drivers")
        assert wiz.pending() == {"drivers": {"1": ""}}
        wiz.click("wizard_back")
        wiz.click("wizard_next")                         # re-entry bumps gen
        assert "drivers" not in wiz.pending()
        # freeform_counts survives the visit (1.15.1 behaviour); the rows are
        # blank: nothing was saved and the old ids are gone
        assert wiz.rows() == ["", ""]


def test_remove_drops_pending_at_or_above_new_count():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "a")
        wiz.click("add_drivers")
        wiz.type(1, "b")
        wiz.click("remove_drivers")
        wiz.click("add_drivers")
        assert wiz.pending() == {"drivers": {"1": ""}}
        wiz.click("remove_drivers")
        assert wiz.pending() == {"drivers": {}}
        assert wiz.rows() == ["a"]


def test_successful_next_clears_pending_and_next_step_is_fresh():
    with _wizard() as wiz:
        wiz.to_drivers()
        wiz.type(0, "a")
        wiz.click("add_drivers")
        wiz.type(1, "b")
        wiz.click("remove_drivers")
        wiz.click("add_drivers")
        wiz.click("wizard_next")
        assert wiz.step == 5
        assert wiz.pending() == {}
        assert wiz.gen("activities") >= 1
        assert wiz.rows("activities") == [""]
