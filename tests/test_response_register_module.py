"""P1b Task 11 — Response Register page, Register tab (spec §6.1), in memory with
shiny.testserver.

Global Constraints of the plan: test_server runs an empty UI, so every input the
save handler reads is set by the test (an unset input stops the handler silently);
selecting rows needs both `<id>_cell_selection` and `<id>_data_view_rows`; ui.update_*
and toasts are recorded by monkeypatching shiny.ui; a project replaced "by another
module" is written inside the session through an injector input. The browser's echo
of Edit's own updates is replayed by setting the inputs to the values Edit sent.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from pathlib import Path

import shiny
from shiny import reactive
from shiny.testserver import test_server

from sespy import i18n
from sespy.data_structure import Project, ResponseRegister, Stakeholder
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.modules.response_register import EchoGuard, response_register_server
from sespy.response_register import TENET_CODES, add_impact, add_measure, add_milestone

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
RM = "modules.response.measures."

FORM = {"rm_name": "", "rm_type": "", "rm_target": "", "rm_status": "proposed",
        "rm_description": "", "rm_mechanism": "", "rm_target_element": [],
        "rm_effectiveness": "", "rm_feasibility": "", "rm_cost": 5, "rm_stakeholders": "",
        "rm_barriers": "", "rm_kind": "", "rm_ebm_code": "", "rm_gov_level": "",
        "rm_competent_authority": "", "rm_legal_basis": "", "rm_impl_stakeholders": [],
        "rm_paired_with": "", "rm_pestle": [], **{f"rm_tenet_{c}": "" for c in TENET_CODES}}


def _sample() -> Project:
    raw = json.loads((ROOT / "data" / "sample_ses.json").read_text(encoding="utf-8"))
    return Project.from_dict(raw)


def _with_register(*rows: dict, project: Project | None = None) -> Project:
    reg = ResponseRegister()
    for fields in rows:
        reg, _ = add_measure(reg, fields, today="2026-10-22")
    return (project or _sample()).replace(response_measures=reg)


def _form_of(row: dict) -> dict:
    """The inputs a browser holds after Edit repopulated the form from `row`."""
    split = lambda s: [p for p in s.split(";") if p]          # noqa: E731
    form = {**FORM, "rm_name": row["Name"], "rm_type": row["Type"], "rm_target": row["Target"],
            "rm_status": row["Status"], "rm_description": row["Description"],
            "rm_mechanism": row["Mechanism"], "rm_target_element": split(row["TargetElement"]),
            "rm_effectiveness": row["Effectiveness"], "rm_feasibility": row["Feasibility"],
            "rm_cost": row["Cost"], "rm_stakeholders": row["Stakeholders"],
            "rm_barriers": row["Barriers"], "rm_kind": row["Kind"], "rm_ebm_code": row["EbmCode"],
            "rm_gov_level": row["GovernanceLevel"],
            "rm_competent_authority": row["CompetentAuthority"],
            "rm_legal_basis": row["LegalBasis"],
            "rm_impl_stakeholders": split(row["ImplementingStakeholders"]),
            "rm_paired_with": row["PairedWith"], "rm_pestle": split(row["PestleTag"])}
    for c in TENET_CODES:
        form[f"rm_tenet_{c}"] = row[f"Tenet_{c}"]
    return form


class _Ui:
    def __init__(self, ts, holder, toasts, updates, inject):
        self.ts, self.holder, self.toasts, self.updates = ts, holder, toasts, updates
        self._inject = inject
        self.scope = ts.make_scope("responses")
        self._clicks: dict[str, int] = {}
        self._writes = 0

    def click(self, button: str) -> None:
        n = self._clicks.get(button)
        if n is None:                       # the init value ignore_init=True skips
            self.scope.set_inputs(**{button: 0})
            n = 0
        self._clicks[button] = n + 1
        self.scope.set_inputs(**{button: n + 1})

    def add(self, **form) -> None:
        self.scope.set_inputs(**{**FORM, **form})
        self.click("save_measure")

    def select(self, rows: list[int], n: int) -> None:
        self.scope.set_inputs(**{"measures_table_cell_selection": {"type": "row", "rows": rows},
                                 "measures_table_data_view_rows": list(range(n))})

    def write_project(self, project: Project) -> None:
        self._inject.append(project)
        self._writes += 1
        self.ts.set_inputs(inject_project=self._writes)

    def project(self) -> Project:
        with reactive.isolate():
            return self.holder[0].get()

    def calls(self, fn: str, input_id: str) -> list[dict]:
        return [kw for f, i, kw in self.updates if f == fn and i == input_id]

    def table(self) -> str:
        return json.dumps(self.scope.get_output("measures_table").value, ensure_ascii=False)


@contextmanager
def _page(monkeypatch, project: Project | None = None):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    toasts: list[str] = []
    updates: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(shiny.ui, "notification_show",
                        lambda msg, **kw: toasts.append(str(msg)))
    for fn in ("update_text", "update_text_area", "update_select", "update_selectize",
               "update_numeric"):
        monkeypatch.setattr(shiny.ui, fn,
                            (lambda name: lambda id, **kw: updates.append((name, id, kw)))(fn))
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

        response_register_server("responses", project_data=pd, event_bus=create_event_bus(),
                                 translator=TR)

    with test_server(server, timeout_secs=30.0) as ts:
        ui = _Ui(ts, holder, toasts, updates, inject)
        # A browser sends every input's initial value on page load; the
        # follow-up effects (ignore_init=True) skip exactly that first value.
        ui.scope.set_inputs(**FORM)
        yield ui


# ---- EchoGuard (pure) -------------------------------------------------------------

def test_echo_guard():
    g = EchoGuard()
    g.expect("rm_kind", "measure", current="instrument")
    assert g.consume("rm_kind", "measure") is True
    assert g.consume("rm_kind", "measure") is False            # forgotten after one echo
    g.expect("rm_kind", "measure", current="measure")          # no change sent: no echo comes
    assert g.consume("rm_kind", "measure") is False
    g.expect("rm_ebm_code", "output", current="1.1")
    assert g.consume("rm_ebm_code", "spatial.seasonal") is False   # the user's own change
    assert g.consume("rm_ebm_code", "output") is False             # the record is gone


# ---- add, validation ----------------------------------------------------------------

def test_add_two_measures_ids(monkeypatch):
    with _page(monkeypatch) as ui:
        ui.add(rm_name="No-take zone", rm_type="regulatory")
        ui.add(rm_name="Mooring buoys", rm_type="technical")
        reg = ui.project().response_measures
        assert [m["ID"] for m in reg.measures] == ["RM001", "RM002"]
        assert reg.measures[0]["DateAdded"] == date.today().isoformat()
        assert reg.measures[0]["Type"] == "regulatory"                  # the code, not a label
        assert ui.toasts == [TR.t(RM + "response_measure_added")] * 2
        assert "RM002" in ui.table() and TR.t(RM + "technical") in ui.table()


def test_add_requires_name_and_type(monkeypatch):
    with _page(monkeypatch) as ui:
        ui.add(rm_name="Valid", rm_type="economic")                      # positive control
        assert len(ui.project().response_measures.measures) == 1
        ui.add(rm_name="   ", rm_type="economic")
        ui.add(rm_name="No type", rm_type="")
        assert len(ui.project().response_measures.measures) == 1
        assert ui.toasts[-2:] == [TR.t("responses.name_type_required")] * 2


# ---- edit ----------------------------------------------------------------------------

def test_edit_repopulates_and_updates_in_place(monkeypatch):
    start = _with_register({"Name": "No-take zone", "Type": "regulatory", "Status": "planned",
                            "Cost": 7, "PestleTag": "legal"},
                           {"Name": "Mooring buoys", "Type": "technical"})
    with _page(monkeypatch, start) as ui:
        ui.select([0], 2)
        ui.click("edit_measure")
        assert ui.calls("update_text", "rm_name")[-1] == {"value": "No-take zone"}
        assert ui.calls("update_select", "rm_status")[-1]["selected"] == "planned"
        assert ui.calls("update_selectize", "rm_pestle")[-1]["selected"] == ["legal"]
        row = ui.project().response_measures.measures[0]
        ui.scope.set_inputs(**{**_form_of(row), "rm_status": "implemented"})
        ui.click("save_measure")
        reg = ui.project().response_measures
        m = reg.measures[0]
        assert (m["ID"], m["DateAdded"], m["Status"]) == ("RM001", "2026-10-22", "implemented")
        assert reg.counter == 2 and len(reg.measures) == 2
        assert TR.t(RM + "response_measure_added") not in ui.toasts       # an update, not an add


def test_edit_keeps_dangling_and_pass_through_values(monkeypatch):
    start = _with_register({"Name": "Odd", "Type": "something else", "Effectiveness": "Very high",
                            "PairedWith": "RM099", "ImplementingStakeholders": "SH404",
                            "TargetElement": "P001;R001"})
    with _page(monkeypatch, start) as ui:
        before = ui.project().response_measures.measures[0]
        ui.select([0], 1)
        ui.click("edit_measure")
        for fn, input_id, raw in (("update_select", "rm_type", "something else"),
                                  ("update_select", "rm_effectiveness", "Very high"),
                                  ("update_select", "rm_paired_with", "RM099")):
            call = ui.calls(fn, input_id)[-1]
            assert raw in call["choices"] and call["selected"] == raw, input_id
        impl = ui.calls("update_selectize", "rm_impl_stakeholders")[-1]
        assert "SH404" in impl["choices"] and impl["selected"] == ["SH404"]
        target = ui.calls("update_selectize", "rm_target_element")[-1]
        assert "R001" in target["choices"] and target["selected"] == ["P001", "R001"]
        ui.scope.set_inputs(**_form_of(before))
        ui.click("save_measure")
        assert ui.project().response_measures.measures[0] == before          # nothing rewritten


def test_edit_with_two_rows_selected_asks_for_one(monkeypatch):
    start = _with_register({"Name": "a", "Type": "regulatory"}, {"Name": "b", "Type": "economic"})
    with _page(monkeypatch, start) as ui:
        ui.select([0, 1], 2)
        ui.click("edit_measure")
        assert ui.toasts == [TR.t("responses.select_one")]
        assert ui.calls("update_text", "rm_name") == []
        ui.select([], 2)
        ui.click("edit_measure")
        assert ui.toasts[-1] == TR.t("responses.select_first")


def test_edit_echo_does_not_reset_ebm_code_or_target(monkeypatch):
    start = _with_register({"Name": "Output quota", "Type": "regulatory", "Kind": "measure",
                            "EbmCode": "output", "Target": "state"})
    with _page(monkeypatch, start) as ui:
        ui.scope.set_inputs(rm_kind="instrument", rm_ebm_code="1.1")       # what the form shows
        ui.select([0], 1)
        ui.click("edit_measure")
        target_calls = len(ui.calls("update_select", "rm_target"))
        ebm_calls = len(ui.calls("update_select", "rm_ebm_code"))
        ui.scope.set_inputs(rm_kind="measure")             # the browser's echo of Edit's update
        ui.scope.set_inputs(rm_ebm_code="output")
        assert len(ui.calls("update_select", "rm_target")) == target_calls   # no suggestion
        assert len(ui.calls("update_select", "rm_ebm_code")) == ebm_calls    # no kind reset
        ui.scope.set_inputs(rm_ebm_code="restoration.habitat")             # the user's own pick
        assert ui.calls("update_select", "rm_target")[-1] == {"selected": "state"}


def test_measure_code_suggests_target(monkeypatch):
    with _page(monkeypatch) as ui:
        ui.scope.set_inputs(rm_kind="measure")
        ui.scope.set_inputs(rm_ebm_code="output")
        assert ui.calls("update_select", "rm_target")[-1] == {"selected": "pressures"}
        ui.scope.set_inputs(rm_kind="instrument")                          # R: kind resets the code
        assert ui.calls("update_select", "rm_ebm_code")[-1]["selected"] == ""


def test_choice_refresh_keeps_current_pick(monkeypatch):
    start = _with_register({"Name": "a", "Type": "regulatory"}, {"Name": "b", "Type": "economic"})
    with _page(monkeypatch, start) as ui:
        ui.scope.set_inputs(rm_paired_with="RM001", rm_impl_stakeholders=[])
        before = len(ui.calls("update_select", "rm_paired_with"))       # the start-up refresh
        reg, _ = add_measure(start.response_measures, {"Name": "c", "Type": "mixed"}, today="d")
        ui.write_project(start.replace(
            response_measures=reg, stakeholders=[Stakeholder(id="SH001", name="Port")]))
        paired = ui.calls("update_select", "rm_paired_with")[before:]
        assert paired and "RM003" in paired[-1]["choices"]                # the refresh happened
        assert all(c["selected"] == "RM001" for c in paired)             # the pick was kept
        assert "SH001" in ui.calls("update_selectize", "rm_impl_stakeholders")[-1]["choices"]


def test_save_after_project_swap_does_not_write(monkeypatch):
    start = _with_register({"Name": "No-take zone", "Type": "regulatory"})
    with _page(monkeypatch, start) as ui:
        ui.select([0], 1)
        ui.click("edit_measure")
        row = ui.project().response_measures.measures[0]
        swapped = replace(start.response_measures,
                          measures=[{**row, "Name": "Somebody else's zone"}])
        ui.write_project(start.replace(response_measures=swapped))          # another project
        ui.scope.set_inputs(**{**_form_of(row), "rm_name": "My edit"})
        ui.click("save_measure")
        assert ui.project().response_measures.measures[0]["Name"] == "Somebody else's zone"
        assert ui.toasts[-1] == TR.t("responses.record_changed")
        ui.click("edit_measure")                                            # positive control
        ui.click("save_measure")
        assert ui.project().response_measures.measures[0]["Name"] == "My edit"


# ---- delete --------------------------------------------------------------------------

def test_delete_reports_references(monkeypatch):
    start = _with_register({"Name": "a", "Type": "regulatory"}, {"Name": "b", "Type": "economic"})
    reg = add_impact(start.response_measures, {"ResponseID": "RM002", "ProblemType": "specific_pressure"})
    reg = add_milestone(reg, {"ResponseID": "RM002", "Milestone": "Consultation"})
    with _page(monkeypatch, start.replace(response_measures=reg)) as ui:
        ui.select([1], 2)
        ui.click("delete_measures")
        got = ui.project().response_measures
        assert [m["ID"] for m in got.measures] == ["RM001"] and got.counter == 2
        assert len(got.impacts) == 1 and len(got.milestones) == 1         # no cascade
        assert ui.toasts[-1] == (TR.t(RM + "deleted_response_measures") + " "
                                 + TR.t("responses.deleted_with_refs", n=2))
        ui.select([0], 1)
        ui.click("delete_measures")
        assert ui.toasts[-1] == TR.t(RM + "deleted_response_measures")    # nothing refers to RM001


# ---- language --------------------------------------------------------------------------

def test_language_switch_relabels_not_rewrites(monkeypatch):
    start = _with_register({"Name": "a", "Type": "educational"})
    stored = start.response_measures.measures[0]
    TR.set_language("de")
    try:
        with _page(monkeypatch, start) as ui:
            assert TR.t(RM + "educational") in ui.table()
            assert TR.t(RM + "educational") != "Educational"
            assert ui.project().response_measures.measures[0] == stored
    finally:
        TR.set_language("en")
