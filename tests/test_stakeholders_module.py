"""P1b Task 10 — stakeholder roles field and R's counter-based stakeholder IDs
(spec §4.4, §6.3), in memory with shiny.testserver.

The module UI is static and test_server(server) runs an empty UI, so every
form input `_save` reads is set by the test (an unset input stops the handler
silently). ui.update_* calls are recorded (test_server does not reflect them
into inputs), as tests/test_isa_entry_link_rules.py does.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import shiny
from shiny import reactive
from shiny.testserver import test_server

from sespy import i18n
from sespy.data_structure import IsaData, Project, ProjectMetadata, Stakeholder
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.modules.pims_stakeholders import pims_stakeholders_server

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))

FORM = {"sh_name": "", "sh_type": "", "sh_sector": "", "sh_contact": "", "sh_interests": "",
        "sh_role": "", "sh_power": "", "sh_interest": "", "sh_attitude": "",
        "sh_engagement_level": "", "sh_ne_roles": []}


class _Ui:
    def __init__(self, ts, holder, toasts, updates):
        self.ts, self.holder, self.toasts, self.updates = ts, holder, toasts, updates
        self.scope = ts.make_scope("stakeholders")
        self._clicks: dict[str, int] = {}

    def click(self, button: str) -> None:
        n = self._clicks.get(button)
        if n is None:                       # the init value ignore_init=True skips
            self.scope.set_inputs(**{button: 0})
            n = 0
        self._clicks[button] = n + 1
        self.scope.set_inputs(**{button: n + 1})

    def add(self, name: str, roles=(), **form) -> None:
        self.scope.set_inputs(**{**FORM, "sh_name": name, "sh_type": "ngo",
                                 "sh_ne_roles": list(roles), **form})
        self.click("save_stakeholder")

    def select(self, row: int, n: int) -> None:
        self.scope.set_inputs(**{"stakeholder_table_cell_selection": {"type": "row", "rows": [row]},
                                 "stakeholder_table_data_view_rows": list(range(n))})

    def project(self) -> Project:
        with reactive.isolate():
            return self.holder[0].get()

    def selectize_updates(self, input_id: str) -> list[dict]:
        return [kw for fn, i, kw in self.updates if fn == "update_selectize" and i == input_id]


@contextmanager
def _stakeholders(monkeypatch, project: Project | None = None):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    toasts: list[str] = []
    updates: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(shiny.ui, "notification_show",
                        lambda msg, **kw: toasts.append(str(msg)))
    for fn in ("update_text", "update_text_area", "update_select", "update_selectize"):
        monkeypatch.setattr(shiny.ui, fn,
                            (lambda name: lambda id, **kw: updates.append((name, id, kw)))(fn))
    holder: list[reactive.Value[Project]] = []
    start = project or Project(ProjectMetadata(name="S"), IsaData())

    def server(input, output, session):
        pd = reactive.value(start)
        holder.append(pd)
        pims_stakeholders_server("stakeholders", project_data=pd, event_bus=create_event_bus(),
                                 translator=TR)

    # The page renders four matplotlib plots on the first flush; the 5 s default
    # can trip on a loaded machine.
    with test_server(server, timeout_secs=30.0) as ts:
        yield _Ui(ts, holder, toasts, updates)


def test_add_with_two_roles_stores_canonical_order(monkeypatch):
    with _stakeholders(monkeypatch) as ui:
        ui.add("Port Authority", roles=("Regulators", "Inputters"))
        (s,) = ui.project().stakeholders
        assert s.ne_roles == "Inputters;Regulators"
        table = json.dumps(ui.scope.get_output("stakeholder_table").value, ensure_ascii=False)
        assert "Inputters, Regulators" in table              # translated labels, ", "-joined
        assert {"selected": []} in ui.selectize_updates("sh_ne_roles")   # the form is cleared


def test_add_adds_exactly_one_row(monkeypatch):
    # R 33ddd96: adding a second stakeholder created duplicate rows.
    with _stakeholders(monkeypatch) as ui:
        ui.add("A")
        assert len(ui.project().stakeholders) == 1
        ui.add("B")
        assert [s.id for s in ui.project().stakeholders] == ["SH001", "SH002"]
        assert ui.project().stakeholder_counter == 2


def test_deleted_id_is_not_reused(monkeypatch):
    with _stakeholders(monkeypatch) as ui:
        ui.add("A")
        ui.add("B")
        ui.select(1, 2)
        ui.click("remove_selected")
        assert [s.id for s in ui.project().stakeholders] == ["SH001"]
        assert ui.project().stakeholder_counter == 2         # a delete never lowers it
        ui.add("C")
        p = ui.project()
        assert [s.id for s in p.stakeholders] == ["SH001", "SH003"]
        assert p.stakeholder_counter == 3


def test_deleted_id_is_not_reused_on_a_pre_1_15_project(monkeypatch):
    # spec §4.4: a file saved before v1.15 has no counter (loads as 0); removing
    # its highest ID before any add must not hand that ID out again.
    raw = {"metadata": {"name": "Old", "schema_version": 7}, "isa_data": {"elements": [], "connections": []},
           "stakeholders": [{"id": "SH001", "name": "A"}, {"id": "SH002", "name": "B"}]}
    start = Project.from_dict(raw)
    assert start.stakeholder_counter == 0
    with _stakeholders(monkeypatch, start) as ui:
        ui.select(1, 2)
        ui.click("remove_selected")
        assert [s.id for s in ui.project().stakeholders] == ["SH001"]
        ui.add("C")
        p = ui.project()
        assert [s.id for s in p.stakeholders] == ["SH001", "SH003"]
        assert p.stakeholder_counter == 3


def test_loaded_project_without_counter_continues_after_its_ids(monkeypatch):
    start = Project(ProjectMetadata(name="Old"), IsaData(),
                    stakeholders=[Stakeholder(id="SH007", name="X")])     # counter 0 (v7 file)
    with _stakeholders(monkeypatch, start) as ui:
        ui.add("Y")
        p = ui.project()
        assert p.stakeholders[-1].id == "SH008" and p.stakeholder_counter == 8


def test_edit_repopulates_roles_and_keeps_source_id(monkeypatch):
    start = Project(ProjectMetadata(name="E"), IsaData(), stakeholder_counter=1, stakeholders=[
        Stakeholder(id="SH001", name="Port", stakeholder_type="government",
                    ne_roles="Regulators", source_id="d54:x")])
    with _stakeholders(monkeypatch, start) as ui:
        ui.select(0, 1)
        ui.click("edit_selected")
        assert ui.selectize_updates("sh_ne_roles")[-1] == {"selected": ["Regulators"]}
        ui.scope.set_inputs(**{**FORM, "sh_name": "Port Authority", "sh_type": "government",
                               "sh_ne_roles": ["Regulators", "Influencers"]})
        ui.click("save_stakeholder")
        (s,) = ui.project().stakeholders
        assert (s.id, s.name, s.ne_roles, s.source_id) == (
            "SH001", "Port Authority", "Regulators;Influencers", "d54:x")
        assert ui.project().stakeholder_counter == 1        # the edit branch leaves it alone
