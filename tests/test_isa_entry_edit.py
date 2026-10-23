"""P1b Task 9 — ISA entry edit panels (spec §6.2), in memory with shiny.testserver.

Global Constraints of the plan: selecting row i needs both
`<id>_cell_selection` and `<id>_data_view_rows`; a button with
`ignore_init=True` needs 0 then 1 (then 2, 3, ...); toasts are recorded by
monkeypatching shiny.ui.notification_show; the editors are asserted on their
output_ui HTML. A dynamically rendered input has no value in test_server
until the test sets it, so every test sets the inputs the save reads.
"""
from __future__ import annotations

import dataclasses
import json
from contextlib import contextmanager
from pathlib import Path

import shiny
from shiny import reactive
from shiny.testserver import test_server

from sespy import i18n
from sespy.data_structure import IsaData, Project, ResponseRegister
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.modules.isa_data_entry import isa_data_entry_server
from sespy.response_register import add_measure

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
N_ELEMENTS = 17          # data/sample_ses.json
MPF1, P001, R001 = 8, 5, 15
D001_A001 = 0            # connection row


def _sample() -> Project:
    raw = json.loads((ROOT / "data" / "sample_ses.json").read_text(encoding="utf-8"))
    return Project.from_dict(raw)


def _with_element(project: Project, idx: int, **changes) -> Project:
    els = list(project.isa_data.elements)
    els[idx] = dataclasses.replace(els[idx], **changes)
    return project.replace(isa_data=IsaData(elements=els, connections=project.isa_data.connections))


class _Ui:
    """One test_server session of the entry module with recorded toasts."""

    def __init__(self, ts, holder, toasts, inject):
        self.ts, self.holder, self.toasts, self._inject = ts, holder, toasts, inject
        self.scope = ts.make_scope("entry")
        self._clicks: dict[str, int] = {}
        self._writes = 0

    def write_project(self, project: Project) -> None:
        """project_data.set() inside the session (as another module would):
        calling .set() from the test thread works on 3.13 only with
        `DeprecationWarning: There is no current event loop`."""
        self._inject.append(project)
        self._writes += 1
        self.ts.set_inputs(inject_project=self._writes)

    def click(self, button: str) -> None:
        n = self._clicks.get(button)
        if n is None:                       # the init value ignore_init=True skips
            self.scope.set_inputs(**{button: 0})
            n = 0
        self._clicks[button] = n + 1
        self.scope.set_inputs(**{button: n + 1})

    def select(self, table: str, row: int, n: int) -> None:
        self.scope.set_inputs(**{f"{table}_cell_selection": {"type": "row", "rows": [row]},
                                 f"{table}_data_view_rows": list(range(n))})

    def html(self, output: str) -> str | None:
        out = self.scope.get_output(output)
        return out.value["html"] if out.status == "ok" and out.value else None

    def project(self) -> Project:
        with reactive.isolate():
            return self.holder[0].get()


@contextmanager
def _entry(monkeypatch, project: Project | None = None):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    toasts: list[str] = []
    monkeypatch.setattr(shiny.ui, "notification_show",
                        lambda msg, **kw: toasts.append(str(msg)))
    holder: list[reactive.Value[Project]] = []
    inject: list[Project] = []
    start = project or _sample()

    def server(input, output, session):
        pd = reactive.value(start)
        holder.append(pd)

        @reactive.effect
        @reactive.event(input.inject_project)
        def _inject():
            pd.set(inject.pop(0))

        isa_data_entry_server("entry", project_data=pd, event_bus=create_event_bus(),
                              translator=TR)

    with test_server(server) as ts:
        yield _Ui(ts, holder, toasts, inject)


def _el(project: Project, eid: str):
    return next(e for e in project.isa_data.elements if e.id == eid)


def test_edit_element_saves_indicator_fields(monkeypatch):
    start = _with_element(_sample(), MPF1, r_extra={"baseline": "1990 cover"},
                          registry_id="WP5-IND-07", registry_version="3")
    with _entry(monkeypatch, start) as ui:
        ui.select("elements_table", MPF1, N_ELEMENTS)
        ui.click("edit_element")
        html = ui.html("element_editor")
        assert html and 'id="entry-el_indicator"' in html
        assert TR.t("entry.registry", id="WP5-IND-07", version="3") in html
        ui.scope.set_inputs(el_label="Posidonia beds", el_description="Seagrass",
                            el_indicator="Shoot density", el_indicator_unit="shoots/m2",
                            el_data_source="Survey", el_policy_target="kmgbf_30x30")
        ui.click("save_element")
        el = _el(ui.project(), "MPF1")
        assert (el.label, el.description, el.indicator, el.indicator_unit, el.data_source,
                el.policy_target) == ("Posidonia beds", "Seagrass", "Shoot density",
                                      "shoots/m2", "Survey", "kmgbf_30x30")
        assert el.r_extra == {"baseline": "1990 cover"}
        assert (el.registry_id, el.registry_version) == ("WP5-IND-07", "3")
        assert ui.html("element_editor") is None            # editing reset to None


def test_indicator_inputs_hidden_for_responses(monkeypatch):
    start = _with_element(_sample(), R001, indicator="TAC")
    with _entry(monkeypatch, start) as ui:
        ui.select("elements_table", R001, N_ELEMENTS)
        ui.click("edit_element")
        html = ui.html("element_editor")
        assert html and 'id="entry-el_label"' in html
        assert 'id="entry-el_indicator' not in html          # none of the four
        ui.scope.set_inputs(el_label="MPA patrols", el_description="d")
        ui.click("save_element")
        el = _el(ui.project(), "R001")
        assert (el.label, el.description, el.indicator) == ("MPA patrols", "d", "TAC")


def test_free_text_policy_target_kept(monkeypatch):
    start = _with_element(_sample(), MPF1, policy_target="My national 25% target",
                          indicator="Cover")
    with _entry(monkeypatch, start) as ui:
        ui.select("elements_table", MPF1, N_ELEMENTS)
        ui.click("edit_element")
        html = ui.html("element_editor")
        assert '<option value="My national 25% target" selected' in html
        ui.scope.set_inputs(el_label="Posidonia meadows", el_description="",
                            el_indicator="Cover", el_indicator_unit="", el_data_source="",
                            el_policy_target="My national 25% target")
        ui.click("save_element")
        assert _el(ui.project(), "MPF1").policy_target == "My national 25% target"


def test_empty_label_is_refused(monkeypatch):
    with _entry(monkeypatch) as ui:
        ui.select("elements_table", MPF1, N_ELEMENTS)
        ui.click("edit_element")
        ui.scope.set_inputs(el_label="   ", el_description="x", el_indicator="I",
                            el_indicator_unit="", el_data_source="", el_policy_target="")
        ui.click("save_element")
        assert ui.toasts and _el(ui.project(), "MPF1").label == "Posidonia meadows"
        assert ui.html("element_editor")                     # still editing
        ui.scope.set_inputs(el_label="Fixed")                 # positive control
        ui.click("save_element")
        assert _el(ui.project(), "MPF1").label == "Fixed"


def test_edit_connection_description(monkeypatch):
    start = _sample()
    with _entry(monkeypatch, start) as ui:
        ui.select("connections_table", D001_A001, 20)
        ui.click("edit_connection")
        html = ui.html("connection_editor")
        assert html and 'id="entry-conn_description"' in html
        ui.scope.set_inputs(conn_description="Visitors bring boats")
        ui.click("save_connection")
        c = ui.project().isa_data.connections[0]
        assert (c.source, c.target, c.description) == ("D001", "A001", "Visitors bring boats")
        assert c == dataclasses.replace(start.isa_data.connections[0],
                                        description="Visitors bring boats")
        assert ui.html("connection_editor") is None


def test_editor_not_clobbered_by_project_writes(monkeypatch):
    start = _with_element(_sample(), MPF1, indicator="A")
    with _entry(monkeypatch, start) as ui:
        ui.select("elements_table", MPF1, N_ELEMENTS)
        ui.click("edit_element")
        before = ui.html("element_editor")
        assert 'value="A"' in before
        ui.write_project(_with_element(start, MPF1, indicator="B"))
        assert _el(ui.project(), "MPF1").indicator == "B"   # the write happened
        assert ui.html("element_editor") == before          # not re-rendered
        ui.click("cancel_element")                           # positive control
        assert ui.html("element_editor") is None
        ui.click("edit_element")
        assert 'value="B"' in ui.html("element_editor")


def test_reclick_edit_shows_the_new_snapshot(monkeypatch):
    # A re-click on the open element takes a new snapshot, so the editor must
    # show that record, or Save writes stale values over it (Task R review).
    start = _with_element(_sample(), MPF1, indicator="A")
    with _entry(monkeypatch, start) as ui:
        ui.select("elements_table", MPF1, N_ELEMENTS)
        ui.click("edit_element")
        assert 'value="A"' in ui.html("element_editor")
        ui.write_project(_with_element(start, MPF1, indicator="B"))    # keeps the id object
        ui.click("edit_element")                                        # no Cancel first
        assert 'value="B"' in ui.html("element_editor")
        ui.scope.set_inputs(el_label="Posidonia meadows", el_description="", el_indicator="B2",
                            el_indicator_unit="", el_data_source="", el_policy_target="")
        ui.click("save_element")
        assert _el(ui.project(), "MPF1").indicator == "B2"


def test_save_after_project_swap_does_not_write(monkeypatch):
    # spec §6.2: a Save is refused when the record changed or the project was replaced.
    start = _sample()
    with _entry(monkeypatch, start) as ui:
        ui.select("elements_table", MPF1, N_ELEMENTS)
        ui.click("edit_element")
        ui.write_project(_with_element(start, MPF1, label="Swapped meadows"))   # another project
        ui.scope.set_inputs(el_label="My edit", el_description="", el_indicator="",
                            el_indicator_unit="", el_data_source="", el_policy_target="")
        ui.click("save_element")
        assert _el(ui.project(), "MPF1").label == "Swapped meadows"           # nothing written
        assert ui.toasts == [TR.t("entry.record_changed")]
        assert ui.html("element_editor") is None                              # editor closed
        ui.click("edit_element")                                              # positive control
        ui.scope.set_inputs(el_label="My edit")
        ui.click("save_element")
        assert _el(ui.project(), "MPF1").label == "My edit"


def test_connection_save_after_project_swap_does_not_write(monkeypatch):
    start = _sample()
    swapped_conn = dataclasses.replace(start.isa_data.connections[D001_A001], description="other")
    swapped = start.replace(isa_data=IsaData(
        elements=start.isa_data.elements,
        connections=[swapped_conn, *start.isa_data.connections[1:]]))
    with _entry(monkeypatch, start) as ui:
        ui.select("connections_table", D001_A001, 20)
        ui.click("edit_connection")
        ui.write_project(swapped)
        ui.scope.set_inputs(conn_description="mine")
        ui.click("save_connection")
        assert ui.project().isa_data.connections[0].description == "other"
        assert ui.toasts == [TR.t("entry.record_changed")]
        assert ui.html("connection_editor") is None
        ui.click("edit_connection")                                    # positive control
        ui.click("save_connection")
        assert ui.project().isa_data.connections[0].description == "mine"


def test_editor_toasts_are_translated(monkeypatch):
    TR.set_language("de")                      # TR is shared by this file's tests
    try:
        with _entry(monkeypatch) as ui:
            ui.scope.set_inputs(elements_table_cell_selection={"type": "row", "rows": []},
                                elements_table_data_view_rows=list(range(N_ELEMENTS)))
            ui.click("edit_element")
            assert ui.toasts == [TR.t("entry.select_first")]
            ui.scope.set_inputs(connections_table_cell_selection={"type": "row", "rows": []},
                                connections_table_data_view_rows=list(range(20)))
            ui.click("edit_connection")
            assert ui.toasts == [TR.t("entry.select_first")] * 2
            ui.select("elements_table", MPF1, N_ELEMENTS)
            ui.click("edit_element")
            ui.scope.set_inputs(el_label=" ", el_description="", el_indicator="",
                                el_indicator_unit="", el_data_source="", el_policy_target="")
            ui.click("save_element")
            assert ui.toasts[-1] == TR.t("entry.label_required") != "Label is required."
    finally:
        TR.set_language("en")


def test_delete_referenced_element_warns(monkeypatch):
    reg, mid = add_measure(ResponseRegister(), {"Name": "Anchoring ban", "Type": "regulatory",
                                                "TargetElement": "P001"}, today="2026-10-22")
    start = _sample().replace(response_measures=reg)
    with _entry(monkeypatch, start) as ui:
        ui.select("elements_table", P001, N_ELEMENTS)
        ui.click("remove_element")
        p = ui.project()
        assert "P001" not in {e.id for e in p.isa_data.elements}      # the removal (a write)
        warn = [m for m in ui.toasts if "P001" in m]
        assert len(warn) == 1 and mid in warn[0]
        assert p.response_measures.measures[0]["TargetElement"] == "P001"   # kept


def test_delete_unreferenced_element_does_not_warn(monkeypatch):
    with _entry(monkeypatch) as ui:
        ui.select("elements_table", P001, N_ELEMENTS)
        ui.click("remove_element")
        assert "P001" not in {e.id for e in ui.project().isa_data.elements}
        assert ui.toasts == []


def test_connection_save_touches_only_the_opened_connection(monkeypatch):
    # A loaded file can repeat a (source, target) pair; Save writes only the
    # connection the editor opened (Task 6-10 review).
    start = _sample()
    first = start.isa_data.connections[D001_A001]
    twin = dataclasses.replace(first, polarity="-" if first.polarity == "+" else "+",
                               description="twin")
    start = start.replace(isa_data=IsaData(elements=start.isa_data.elements,
                                           connections=[*start.isa_data.connections, twin]))
    with _entry(monkeypatch, start) as ui:
        ui.select("connections_table", D001_A001, 21)
        ui.click("edit_connection")
        ui.scope.set_inputs(conn_description="mine")
        ui.click("save_connection")
        connections = ui.project().isa_data.connections
        assert connections[D001_A001].description == "mine"
        assert connections[-1] == twin
