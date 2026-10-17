"""P1a — ISA entry: empty first picker choice, polarity prefill and the
off-rule note, in memory with shiny.testserver (spec §3.4, §10).

update_radio_buttons only sends a client message that test_server does not
reflect back into inputs, so the tests record the calls instead.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import shiny
from shiny import reactive
from shiny.testserver import test_server

from sespy import i18n
from sespy.data_structure import Project
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.modules.isa_data_entry import isa_data_entry_server

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))


def _sample() -> Project:
    raw = json.loads((ROOT / "data" / "sample_ses.json").read_text(encoding="utf-8"))
    return Project.from_dict(raw)


@pytest.fixture
def entry(monkeypatch):
    # The module labels its pickers with the module-level t(); give it the
    # real translations for this test only (restored by monkeypatch).
    monkeypatch.setattr(i18n, "_default_translator", TR)
    radio: list[dict] = []
    toasts: list[str] = []
    monkeypatch.setattr(shiny.ui, "update_radio_buttons",
                        lambda id, **kw: radio.append({"id": id, **kw}))
    monkeypatch.setattr(shiny.ui, "notification_show",
                        lambda msg, **kw: toasts.append(str(msg)))
    holder: list[reactive.Value[Project]] = []

    def server(input, output, session):
        pd = reactive.value(_sample())
        holder.append(pd)
        isa_data_entry_server("entry", project_data=pd, event_bus=create_event_bus(),
                              translator=TR)

    with test_server(server) as ts:
        yield ts, ts.make_scope("entry"), radio, toasts, holder


def _note(scope):
    out = scope.get_output("off_rule_note")
    return None if out.status != "ok" or not out.value else out.value["html"]


@pytest.mark.parametrize("picker", ["source_picker", "target_picker"])
def test_pickers_start_with_an_empty_selected_choice(entry, picker):
    _, scope, *_ = entry
    html = scope.get_output(picker).value["html"]
    assert '<option value="" selected' in html
    assert TR.t("entry.choose_element") in html
    assert html.index('value=""') < html.index('value="D001"')


def test_empty_project_keeps_the_no_elements_choice(monkeypatch):
    from sespy.data_structure import IsaData, ProjectMetadata

    def server(input, output, session):
        isa_data_entry_server("entry", project_data=reactive.value(
            Project(ProjectMetadata(), IsaData())), event_bus=create_event_bus())

    with test_server(server) as ts:
        html = ts.make_scope("entry").get_output("source_picker").value["html"]
    assert "(no elements yet)" in html and "choose" not in html


def test_pressure_to_mpf_seeds_minus(entry):
    _, scope, radio, *_ = entry
    scope.set_inputs(new_source="P001", new_target="MPF2")
    assert radio and radio[-1] == {"id": "new_polarity", "selected": "-"}


def test_off_rule_pair_seeds_plus_and_shows_the_note(entry):
    _, scope, radio, *_ = entry
    scope.set_inputs(new_source="D001", new_target="GB01")
    assert radio[-1] == {"id": "new_polarity", "selected": "+"}
    html = _note(scope)
    assert html and "sespy-off-rule-note" in html and "alert-warning" in html
    assert "Drivers" in html and "Goods &amp; Benefits" in html


def test_changing_an_endpoint_reseeds(entry):
    _, scope, radio, *_ = entry
    scope.set_inputs(new_source="P001", new_target="MPF2")
    scope.set_inputs(new_source="R001")            # R -> MPF is "+"
    assert [c["selected"] for c in radio[-2:]] == ["-", "+"]


def test_only_a_source_seeds_nothing_and_shows_no_note(entry):
    _, scope, radio, *_ = entry
    # new_target set explicitly to "": unset, the effect would never run and
    # the test would pass vacuously.
    scope.set_inputs(new_source="P001", new_target="")
    assert radio == []
    assert _note(scope) is None


def test_default_state_has_no_note(entry):
    _, scope, radio, *_ = entry
    scope.set_inputs(new_source="", new_target="")
    assert _note(scope) is None and radio == []


def test_canonical_pair_has_no_note(entry):
    _, scope, *_ = entry
    scope.set_inputs(new_source="P001", new_target="MPF2")
    assert _note(scope) is None


def test_add_connection_refuses_an_empty_endpoint(entry):
    """Characterisation: _add_connection already refuses an empty endpoint."""
    _, scope, _, toasts, holder = entry
    scope.set_inputs(new_source="", new_target="D001", new_polarity="+",
                     new_delay="immediate", add_connection=0)
    scope.set_inputs(add_connection=1)
    assert toasts and "Pick source and target" in toasts[-1]
    with reactive.isolate():
        assert holder[0].get().isa_data.connection_count() == 20


def test_off_rule_link_still_saves(entry):
    _, scope, _, toasts, holder = entry
    scope.set_inputs(new_source="D001", new_target="GB01", new_polarity="+",
                     new_delay="immediate", add_connection=0)
    scope.set_inputs(add_connection=1)
    with reactive.isolate():
        conns = holder[0].get().isa_data.connections
    assert ("D001", "GB01") in {(c.source, c.target) for c in conns}
    assert len(conns) == 21
