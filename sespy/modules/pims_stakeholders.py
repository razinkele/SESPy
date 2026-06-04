"""PIMS Stakeholders — register UI + CRUD server. Port of pims_stakeholder_module.R.

A self-contained Shiny module: an add/edit form on the left, a render.data_frame
table on the right with selection-based Edit/Remove. All envelope writes go
through Project.replace() and emit isa_change so autosave fires.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from sespy.data_structure import Project, Stakeholder
from sespy.event_bus import EventBus
from sespy.i18n import Translator, t as _t
from sespy.stakeholders import add_stakeholder, remove_stakeholder, update_stakeholder

# code -> i18n label-key suffix maps (codes are stored; labels are rendered)
_TYPE_CODES = ["resource_users", "industry", "government", "ngo", "academic",
               "local_community", "indigenous", "other"]
_SECTOR_CODES = ["fisheries", "aquaculture", "tourism", "shipping", "energy",
                 "conservation", "research", "policy", "multiple", "other"]
_LEVEL_CODES = ["HIGH", "MEDIUM", "LOW"]
_ATTITUDE_CODES = ["supportive", "neutral", "resistant", "unknown"]
_ENGAGE_CODES = ["inform", "consult", "involve", "collaborate", "empower"]


def _choices(codes: list[str], group: str, translate) -> dict[str, str]:
    # "" front option so a field can be left blank; label via i18n key.
    out = {"": "—"}
    for c in codes:
        out[c] = translate(f"stakeholders.{group}.{c}")
    return out


@module.ui
def pims_stakeholders_ui() -> ui.Tag:
    # Static labels resolved via the module-level default translator (`_t`),
    # matching pims_project_ui's pattern.
    return ui.div(
        ui.h3(_t("stakeholders.title")),
        ui.layout_columns(
            ui.card(
                ui.card_header(_t("stakeholders.add_heading")),
                ui.input_text("sh_name", _t("stakeholders.name")),
                ui.input_select("sh_type", _t("stakeholders.type"),
                                _choices(_TYPE_CODES, "type", _t)),
                ui.input_select("sh_sector", _t("stakeholders.sector"),
                                _choices(_SECTOR_CODES, "sector", _t)),
                ui.input_text("sh_contact", _t("stakeholders.contact")),
                ui.input_text_area("sh_interests", _t("stakeholders.interests")),
                ui.input_text_area("sh_role", _t("stakeholders.role")),
                ui.input_select("sh_power", _t("stakeholders.power"),
                                _choices(_LEVEL_CODES, "power", _t)),
                ui.input_select("sh_interest", _t("stakeholders.interest"),
                                _choices(_LEVEL_CODES, "interest", _t)),
                ui.input_select("sh_attitude", _t("stakeholders.attitude"),
                                _choices(_ATTITUDE_CODES, "attitude", _t)),
                ui.input_select("sh_engagement_level", _t("stakeholders.engagement_level"),
                                _choices(_ENGAGE_CODES, "engagement", _t)),
                ui.input_action_button("save_stakeholder", _t("stakeholders.save"),
                                       class_="btn-primary"),
                ui.input_action_button("cancel_edit", _t("stakeholders.cancel")),
            ),
            ui.card(
                ui.card_header(_t("stakeholders.title")),
                ui.output_data_frame("stakeholder_table"),
                ui.div(
                    ui.input_action_button("edit_selected", _t("stakeholders.edit_selected")),
                    ui.input_action_button(
                        "remove_selected", _t("stakeholders.remove_selected")),
                ),
            ),
            col_widths=[5, 7],
        ),
        class_="sespy-card",
    )


@module.server
def pims_stakeholders_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    T = translator
    tr = (lambda k: T.t(k)) if T is not None else _t

    editing_id: reactive.Value[str | None] = reactive.value(None)

    def _items() -> list[Stakeholder]:
        return project_data.get().stakeholders

    @output
    @render.data_frame
    def stakeholder_table():
        rows = [
            {"name": s.name, "type": s.stakeholder_type, "sector": s.sector,
             "power": s.power, "interest": s.interest,
             "attitude": s.attitude, "engagement": s.engagement_level}
            for s in _items()
        ]
        stub = [{"name": tr("stakeholders.empty"), "type": "", "sector": "",
                 "power": "", "interest": "", "attitude": "", "engagement": ""}]
        return render.DataGrid(pd.DataFrame(rows or stub),
                               selection_mode="row", height="320px")

    def _form_fields() -> dict:
        return {
            "name": input.sh_name().strip(),
            "stakeholder_type": input.sh_type(),
            "sector": input.sh_sector(),
            "contact": input.sh_contact().strip(),
            "interests": input.sh_interests().strip(),
            "role": input.sh_role().strip(),
            "power": input.sh_power(),
            "interest": input.sh_interest(),
            "attitude": input.sh_attitude(),
            "engagement_level": input.sh_engagement_level(),
        }

    def _clear_form() -> None:
        ui.update_text("sh_name", value="")
        ui.update_select("sh_type", selected="")
        ui.update_select("sh_sector", selected="")
        ui.update_text("sh_contact", value="")
        ui.update_text_area("sh_interests", value="")
        ui.update_text_area("sh_role", value="")
        ui.update_select("sh_power", selected="")
        ui.update_select("sh_interest", selected="")
        ui.update_select("sh_attitude", selected="")
        ui.update_select("sh_engagement_level", selected="")

    @reactive.effect
    @reactive.event(input.save_stakeholder, ignore_init=True)
    def _save():
        f = _form_fields()
        if not f["name"] or not f["stakeholder_type"]:
            ui.notification_show(tr("stakeholders.name_type_required"),
                                 type="warning", duration=3)
            return
        eid = editing_id.get()
        if eid is None:
            new_list = add_stakeholder(_items(), f, today=date.today().isoformat())
        else:
            new_list = update_stakeholder(_items(), eid, f)
        # Reset editing_id BEFORE project_data.set so the _repopulate effect
        # (it subscribes to project_data via _items()) re-runs with editing_id
        # == None and exits early, rather than re-filling the cleared form.
        editing_id.set(None)
        project_data.set(project_data.get().replace(stakeholders=new_list))
        event_bus.emit_isa_change()
        _clear_form()

    @reactive.effect
    @reactive.event(input.edit_selected, ignore_init=True)
    def _edit():
        sel = stakeholder_table.cell_selection()
        items = _items()
        if not sel or not sel.get("rows") or not items:
            ui.notification_show(tr("stakeholders.select_first"),
                                 type="warning", duration=3)
            return
        editing_id.set(items[sel["rows"][0]].id)

    # Repopulate the form ONLY when editing_id changes — never subscribe to the
    # sh_* inputs here (that would clobber typing). Mirrors pims_project.py:195.
    @reactive.effect
    def _repopulate():
        eid = editing_id.get()
        if eid is None:
            return
        match = next((s for s in _items() if s.id == eid), None)
        if match is None:
            return
        ui.update_text("sh_name", value=match.name)
        ui.update_select("sh_type", selected=match.stakeholder_type)
        ui.update_select("sh_sector", selected=match.sector)
        ui.update_text("sh_contact", value=match.contact)
        ui.update_text_area("sh_interests", value=match.interests)
        ui.update_text_area("sh_role", value=match.role)
        ui.update_select("sh_power", selected=match.power)
        ui.update_select("sh_interest", selected=match.interest)
        ui.update_select("sh_attitude", selected=match.attitude)
        ui.update_select("sh_engagement_level", selected=match.engagement_level)

    @reactive.effect
    @reactive.event(input.cancel_edit, ignore_init=True)
    def _cancel():
        editing_id.set(None)
        _clear_form()

    @reactive.effect
    @reactive.event(input.remove_selected, ignore_init=True)
    def _remove():
        sel = stakeholder_table.cell_selection()
        items = _items()
        if not sel or not sel.get("rows") or not items:
            ui.notification_show(tr("stakeholders.select_first"),
                                 type="warning", duration=3)
            return
        sid = items[sel["rows"][0]].id
        project_data.set(project_data.get().replace(
            stakeholders=remove_stakeholder(items, sid)))
        event_bus.emit_isa_change()
        if editing_id.get() == sid:
            editing_id.set(None)
            _clear_form()
