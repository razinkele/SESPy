"""Response Register page (P1b, spec §6.1). Port of R's response_module.R tabs 1–5.

The Register tab holds an add/edit form with R's fields (response_module.R:28-190)
and a table of R's 15 display columns. Edit repopulates the form, Save adds or
updates, and Delete drops measures without cascading into impacts or milestones.
Codes are stored and labels come from R's vendored translation keys. Every write
goes through Project.replace() and emits isa_change, so autosave fires. The
Impacts, Prioritisation and Milestones tabs are filled by Task 12.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from sespy.data_structure import Project, ResponseRegister
from sespy.event_bus import EventBus
from sespy.i18n import Translator
from sespy.i18n import t as _t
from sespy.response_register import (
    EFFECTIVENESS_LEVELS,
    FEASIBILITY_LEVELS,
    GOVERNANCE_LEVELS,
    KIND_CODES,
    PESTLE_CODES,
    RM_DISPLAY_COLUMNS,
    RM_STATUS_CODES,
    RM_TARGET_CODES,
    RM_TYPE_CODES,
    TENET_CODES,
    TENET_LEVELS,
    add_measure,
    delete_measures,
    display_value,
    ebm_code_choices,
    ebm_picker_label,
    split_ids,
    suggest_target,
    update_measure,
)

_RM = "modules.response.measures."
_GOV = "modules.response.governance."
_BLANK = {"": " "}          # R's blank first choice, c(" " = "")


class EchoGuard:
    """Tells the browser's echo of a value the server just sent apart from the
    user's own change (spec §6.1). Edit fills the form with ui.update_*, and each
    changed value comes back as an input change in a later flush. That echo must
    not fire R's follow-up rules: Kind resets the EBM code, and an EBM measure
    code replaces Target (response_module.R:531-538)."""

    def __init__(self) -> None:
        self._pending: dict[str, Any] = {}

    def expect(self, name: str, sent: Any, current: Any) -> None:
        # The browser only sends a value back when it changed.
        if sent != current:
            self._pending[name] = sent
        else:
            self._pending.pop(name, None)

    def consume(self, name: str, incoming: Any) -> bool:
        if name not in self._pending:
            return False
        return self._pending.pop(name) == incoming


# ---- choice lists (codes -> translated labels) -----------------------------------

def _type_choices(tr) -> dict[str, str]:
    return {**_BLANK, **{c: tr(_RM + s) for c, s in RM_TYPE_CODES.items()}}


def _target_choices(tr) -> dict[str, str]:
    return {**_BLANK, **{c: tr(_RM + s) for c, s in RM_TARGET_CODES.items()}}


def _status_choices(tr) -> dict[str, str]:
    # No blank choice: R's select defaults to "proposed" (response_module.R:68-70).
    return {c: tr(_RM + s) for c, s in RM_STATUS_CODES.items()}


def _level_choices(levels: tuple[str, ...], tr) -> dict[str, str]:
    return {"": "", **{lv: tr(_RM + lv.lower()) for lv in levels}}


def _kind_choices(tr) -> dict[str, str]:
    return {**_BLANK, **{k: tr(f"{_GOV}kind.{k}") for k in KIND_CODES}}


def _gov_choices(tr) -> dict[str, str]:
    return {**_BLANK, **{g: tr(f"{_GOV}level.{g}") for g in GOVERNANCE_LEVELS}}


def _pestle_choices(tr) -> dict[str, str]:
    return {c: tr(f"modules.wp5_scenarios.pestle.{c}") for c in PESTLE_CODES}


def _tenet_choices(code: str, tr) -> dict[str, str]:
    # "intermediate" exists only for ecological effectiveness (R :169).
    levels = TENET_LEVELS if code == "ecol_effective" else tuple(
        lv for lv in TENET_LEVELS if lv != "intermediate")
    return {"": tr(f"{_GOV}tenet_level.not_assessed"),
            **{lv: tr(f"{_GOV}tenet_level.{lv}") for lv in levels}}


def _ebm_choices(kind: str, tr) -> dict[str, str]:
    return {**_BLANK, **{c: ebm_picker_label(kind, c, tr) for c in ebm_code_choices(kind)}}


def _with_raw(choices: dict[str, str], *values: str) -> dict[str, str]:
    """Add each stored value that is not among the choices, shown raw, so Edit
    then Save never rewrites it (Shiny drops a selected value that is not a choice)."""
    out = dict(choices)
    for v in values:
        if v and v not in out:
            out[v] = v
    return out


# ---- UI ---------------------------------------------------------------------------

def _register_panel() -> ui.TagList:
    """Plain function, no @module.ui: the enclosing response_register_ui
    namespaces the ids. Static labels use the default translator (`_t`), as
    pims_stakeholders_ui does."""
    return ui.TagList(
        ui.card(
            ui.card_header(_t(_RM + "add_response_measure")),
            ui.layout_columns(
                ui.input_text("rm_name", _t("responses.name")),
                ui.input_select("rm_type", _t("responses.type"), _type_choices(_t)),
                ui.input_select("rm_target", _t(_RM + "targets"), _target_choices(_t)),
                ui.input_select("rm_status", _t("responses.status"), _status_choices(_t),
                                selected="proposed"),
                col_widths=[3, 3, 3, 3],
            ),
            ui.layout_columns(
                ui.input_text_area("rm_description", _t("responses.description"), rows=3),
                ui.input_text_area("rm_mechanism", _t(_RM + "mechanism_of_action"), rows=3),
                col_widths=[6, 6],
            ),
            ui.layout_columns(
                ui.div(
                    ui.input_selectize("rm_target_element", _t(_RM + "target_element_id"),
                                       {}, multiple=True),
                    ui.tags.small(_t("responses.target_element_hint"), class_="text-muted"),
                ),
                ui.input_select("rm_effectiveness", _t(_RM + "expected_effectiveness"),
                                _level_choices(EFFECTIVENESS_LEVELS, _t)),
                ui.input_select("rm_feasibility", _t(_RM + "feasibility"),
                                _level_choices(FEASIBILITY_LEVELS, _t)),
                ui.input_numeric("rm_cost", _t(_RM + "estimated_cost_relative"),
                                 value=5, min=1, max=10),
                col_widths=[3, 3, 3, 3],
            ),
            ui.layout_columns(
                ui.input_text_area("rm_stakeholders", _t(_RM + "responsible_stakeholders"),
                                   rows=2),
                ui.input_text_area("rm_barriers", _t(_RM + "implementation_barriers"), rows=2),
                col_widths=[6, 6],
            ),
            ui.tags.details(
                ui.tags.summary(ui.tags.strong(_t(_GOV + "section_title"))),
                ui.layout_columns(
                    ui.input_select("rm_kind", _t(_GOV + "kind"), _kind_choices(_t)),
                    ui.div(
                        ui.input_select("rm_ebm_code", _t(_GOV + "ebm_code"), dict(_BLANK)),
                        ui.tags.small(_t(_GOV + "ebm_code_hint"), class_="text-muted"),
                    ),
                    ui.input_select("rm_gov_level", _t(_GOV + "level"), _gov_choices(_t)),
                    col_widths=[3, 5, 4],
                ),
                ui.layout_columns(
                    ui.input_text("rm_competent_authority", _t(_GOV + "competent_authority")),
                    ui.input_text("rm_legal_basis", _t(_GOV + "legal_basis")),
                    ui.input_select("rm_paired_with", _t(_GOV + "paired_with"), dict(_BLANK)),
                    col_widths=[4, 4, 4],
                ),
                ui.input_selectize("rm_impl_stakeholders", _t(_GOV + "implementing_stakeholders"),
                                   {}, multiple=True),
                ui.output_ui("impl_stakeholders_hint"),
                ui.input_selectize("rm_pestle", _t(_GOV + "pestle"), _pestle_choices(_t),
                                   multiple=True),
                ui.tags.small(_t(_GOV + "pestle_hint"), class_="text-muted"),
                ui.h6(_t(_GOV + "tenets_title"), class_="mt-2"),
                ui.layout_columns(
                    *[ui.input_select(f"rm_tenet_{c}", _t(f"modules.wp5_vocabulary.tenet.{c}"),
                                      _tenet_choices(c, _t)) for c in TENET_CODES],
                    col_widths=3,
                ),
                ui.output_ui("tenet_source"),
                class_="mt-2 mb-2",
            ),
            ui.div(
                ui.input_action_button("save_measure", _t("responses.save"),
                                       class_="btn btn-success", style="margin-right: 8px;"),
                ui.input_action_button("cancel_measure", _t("responses.cancel")),
            ),
        ),
        ui.card(
            ui.card_header(_t(_RM + "response_measures_register")),
            ui.output_data_frame("measures_table"),
            ui.div(
                ui.input_action_button("edit_measure", _t("responses.edit_selected"),
                                       style="margin-right: 8px;"),
                ui.input_action_button("delete_measures", _t(_RM + "delete_selected"),
                                       class_="btn btn-danger"),
            ),
        ),
    )


@module.ui
def response_register_ui() -> ui.Tag:
    return ui.div(
        ui.h3(_t(_RM + "response_register")),
        ui.navset_tab(
            ui.nav_panel(_t(_RM + "response_register"), _register_panel(), value="register"),
            ui.nav_panel(_t(_RM + "impact_assessment"), ui.div(), value="impacts"),
            ui.nav_panel(_t(_RM + "prioritization"), ui.div(), value="priority"),
            ui.nav_panel(_t(_RM + "implementation_plan"), ui.div(), value="milestones"),
            id="response_tabs",
        ),
        class_="sespy-card",
    )


# ---- server -------------------------------------------------------------------------

_TEXT_INPUTS = ("rm_name", "rm_competent_authority", "rm_legal_basis")
_AREA_INPUTS = ("rm_description", "rm_mechanism", "rm_stakeholders", "rm_barriers")


@module.server
def response_register_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    tr = translator.t if translator is not None else _t
    # The measure being edited, and the row as Edit opened it (spec §6.1 stale
    # check). Plain dicts never become dependencies.
    editing_measure: reactive.Value[str | None] = reactive.value(None)
    edit_state: dict[str, dict[str, Any] | None] = {"snapshot": None}
    guard = EchoGuard()
    last_choices: dict[str, dict[str, str]] = {}

    def _register() -> ResponseRegister:
        return project_data.get().response_measures

    def _write(reg: ResponseRegister) -> None:
        project_data.set(project_data.get().replace(response_measures=reg))
        event_bus.emit_isa_change()

    def _toast(message: str, kind: str = "warning", duration: int = 4) -> None:
        ui.notification_show(message, type=kind, duration=duration)

    # ---- table -------------------------------------------------------------------
    @output
    @render.data_frame
    def measures_table():
        rows = [{c: display_value(c, m.get(c), tr) for c in RM_DISPLAY_COLUMNS}
                for m in _register().measures]
        stub = [{c: "" for c in RM_DISPLAY_COLUMNS}]
        # Built in register order, so a selected row index is a register index.
        return render.DataGrid(pd.DataFrame(rows or stub, columns=list(RM_DISPLAY_COLUMNS)),
                               selection_mode="rows", height="360px")

    def _selected_ids() -> list[str]:
        sel = measures_table.cell_selection()
        measures = _register().measures
        rows = (sel or {}).get("rows") or ()
        return [measures[i].get("ID", "") for i in rows if 0 <= i < len(measures)]

    # ---- project-fed pickers: refreshed without losing the current pick -------------
    def _element_choices(project: Project) -> dict[str, str]:
        return {e.id: f"{e.id} · {e.label}" for e in project.isa_data.elements
                if e.type != "Responses"}

    def _paired_choices(project: Project) -> dict[str, str]:
        editing = editing_measure.get()
        return {**_BLANK, **{m["ID"]: f"{m['ID']} - {m.get('Name', '')}"   # R's hyphen (:554)
                             for m in project.response_measures.measures
                             if m.get("ID") and m["ID"] != editing}}

    def _stakeholder_choices(project: Project) -> dict[str, str]:
        return {s.id: f"{s.name} ({s.id})" for s in project.stakeholders}

    def _stored(column: str) -> list[str]:
        row = edit_state["snapshot"] if editing_measure.get() is not None else None
        return split_ids(row.get(column, "")) if row else []

    def _refresh(input_id: str, choices: dict[str, str], *, multiple: bool) -> None:
        if last_choices.get(input_id) == choices:   # R stakeholder_picker_update skip
            return
        with reactive.isolate():
            value = input[input_id]
            current = value() if value.is_set() else None
        if multiple:
            selected = [v for v in (current or ()) if v in choices]
            ui.update_selectize(input_id, choices=choices, selected=selected)
        else:
            selected = current if current in choices else ""
            ui.update_select(input_id, choices=choices, selected=selected)
        last_choices[input_id] = choices

    @reactive.effect
    def _refresh_target_element():
        choices = _with_raw(_element_choices(project_data.get()), *_stored("TargetElement"))
        _refresh("rm_target_element", choices, multiple=True)

    @reactive.effect
    def _refresh_paired_with():
        choices = _with_raw(_paired_choices(project_data.get()), *_stored("PairedWith"))
        _refresh("rm_paired_with", choices, multiple=False)

    @reactive.effect
    def _refresh_impl_stakeholders():
        choices = _with_raw(_stakeholder_choices(project_data.get()),
                            *_stored("ImplementingStakeholders"))
        _refresh("rm_impl_stakeholders", choices, multiple=True)

    @output
    @render.ui
    def impl_stakeholders_hint():
        if project_data.get().stakeholders:
            return None
        return ui.tags.small(tr(_GOV + "no_stakeholders_hint"), class_="text-muted")

    @output
    @render.ui
    def tenet_source():
        editing_measure.get()
        row = edit_state["snapshot"]
        source = (row or {}).get("TenetSource", "")
        if not source:
            return None
        return ui.p(f"{tr('responses.tenet_source')}: {source}", class_="text-muted")

    # ---- R's follow-up rules, skipped for Edit's own echo ----------------------------
    @reactive.effect
    @reactive.event(input.rm_kind, ignore_init=True)
    def _kind_changed():
        kind = input.rm_kind()
        if guard.consume("rm_kind", kind):
            return
        ui.update_select("rm_ebm_code", choices=_ebm_choices(kind, tr), selected="")   # R :531-533

    @reactive.effect
    @reactive.event(input.rm_ebm_code, ignore_init=True)
    def _ebm_code_changed():
        code = input.rm_ebm_code()
        if guard.consume("rm_ebm_code", code):
            return
        with reactive.isolate():
            kind = input.rm_kind() if input.rm_kind.is_set() else ""
        if kind == "measure":                                                # R :535-538
            target = suggest_target(code)
            if target:
                ui.update_select("rm_target", selected=target)

    # ---- edit ------------------------------------------------------------------------
    @reactive.effect
    @reactive.event(input.edit_measure, ignore_init=True)
    def _edit():
        ids = _selected_ids()
        if not ids:
            _toast(tr("responses.select_first"))
            return
        if len(ids) > 1:
            _toast(tr("responses.select_one"))
            return
        row = next(m for m in _register().measures if m.get("ID") == ids[0])
        edit_state["snapshot"] = dict(row)
        editing_measure.set(row["ID"])

    # Repopulate ONLY when editing_measure changes (the pims_stakeholders._repopulate
    # pattern), so project writes from elsewhere never refill what the user types.
    @reactive.effect
    @reactive.event(editing_measure)
    def _repopulate():
        row = edit_state["snapshot"]
        if editing_measure.get() is None or row is None:
            return
        project = project_data.get()
        for i, col in (("rm_name", "Name"), ("rm_competent_authority", "CompetentAuthority"),
                       ("rm_legal_basis", "LegalBasis")):
            ui.update_text(i, value=row.get(col, ""))
        for i, col in (("rm_description", "Description"), ("rm_mechanism", "Mechanism"),
                       ("rm_stakeholders", "Stakeholders"), ("rm_barriers", "Barriers")):
            ui.update_text_area(i, value=row.get(col, ""))
        cost = row.get("Cost")
        ui.update_numeric("rm_cost", value="" if cost is None else cost)    # "" keeps NA blank
        kind, code = row.get("Kind", ""), row.get("EbmCode", "")
        with reactive.isolate():
            guard.expect("rm_kind", kind, input.rm_kind() if input.rm_kind.is_set() else None)
            guard.expect("rm_ebm_code", code,
                         input.rm_ebm_code() if input.rm_ebm_code.is_set() else None)
        selects = (
            ("rm_type", _type_choices(tr), "Type"),
            ("rm_target", _target_choices(tr), "Target"),
            ("rm_status", _status_choices(tr), "Status"),
            ("rm_effectiveness", _level_choices(EFFECTIVENESS_LEVELS, tr), "Effectiveness"),
            ("rm_feasibility", _level_choices(FEASIBILITY_LEVELS, tr), "Feasibility"),
            ("rm_kind", _kind_choices(tr), "Kind"),
            ("rm_ebm_code", _ebm_choices(kind, tr), "EbmCode"),
            ("rm_gov_level", _gov_choices(tr), "GovernanceLevel"),
            *((f"rm_tenet_{c}", _tenet_choices(c, tr), f"Tenet_{c}") for c in TENET_CODES),
        )
        for input_id, choices, col in selects:
            value = row.get(col, "")
            ui.update_select(input_id, choices=_with_raw(choices, value), selected=value)
        paired = row.get("PairedWith", "")
        choices = _with_raw(_paired_choices(project), paired)
        ui.update_select("rm_paired_with", choices=choices, selected=paired)
        last_choices["rm_paired_with"] = choices
        for input_id, base, col in (
                ("rm_target_element", _element_choices(project), "TargetElement"),
                ("rm_impl_stakeholders", _stakeholder_choices(project),
                 "ImplementingStakeholders")):
            ids = split_ids(row.get(col, ""))
            choices = _with_raw(base, *ids)
            ui.update_selectize(input_id, choices=choices, selected=ids)
            last_choices[input_id] = choices
        pestle = split_ids(row.get("PestleTag", ""))
        ui.update_selectize("rm_pestle", choices=_with_raw(_pestle_choices(tr), *pestle),
                            selected=pestle)

    def _close_edit() -> None:
        editing_measure.set(None)
        edit_state["snapshot"] = None

    def _clear_form() -> None:
        # Exactly what R clears after an add (response_module.R:589-599).
        for i in _TEXT_INPUTS:
            ui.update_text(i, value="")
        for i in _AREA_INPUTS:
            ui.update_text_area(i, value="")
        for i in ("rm_target_element", "rm_impl_stakeholders", "rm_pestle"):
            ui.update_selectize(i, selected=[])
        for c in TENET_CODES:
            ui.update_select(f"rm_tenet_{c}", selected="")

    def _form_fields() -> dict[str, Any]:
        fields: dict[str, Any] = {
            "Name": (input.rm_name() or "").strip(),
            "Type": input.rm_type() or "",
            "Target": input.rm_target() or "",
            "Status": input.rm_status() or "",
            "Description": input.rm_description() or "",
            "Mechanism": input.rm_mechanism() or "",
            "TargetElement": ";".join(input.rm_target_element() or ()),
            "Effectiveness": input.rm_effectiveness() or "",
            "Feasibility": input.rm_feasibility() or "",
            "Cost": input.rm_cost(),
            "Stakeholders": input.rm_stakeholders() or "",
            "Barriers": input.rm_barriers() or "",
            "Kind": input.rm_kind() or "",
            "EbmCode": input.rm_ebm_code() or "",
            "GovernanceLevel": input.rm_gov_level() or "",
            "CompetentAuthority": input.rm_competent_authority() or "",
            "LegalBasis": input.rm_legal_basis() or "",
            "ImplementingStakeholders": ";".join(input.rm_impl_stakeholders() or ()),
            "PairedWith": input.rm_paired_with() or "",
            "PestleTag": ";".join(input.rm_pestle() or ()),
        }
        for c in TENET_CODES:
            fields[f"Tenet_{c}"] = input[f"rm_tenet_{c}"]() or ""
        return fields

    # ---- save / cancel / delete ------------------------------------------------------
    @reactive.effect
    @reactive.event(input.save_measure, ignore_init=True)
    def _save():
        fields = _form_fields()
        if not fields["Name"] or not fields["Type"]:
            _toast(tr("responses.name_type_required"))
            return
        reg = _register()
        mid = editing_measure.get()
        if mid is not None:
            current = next((m for m in reg.measures if m.get("ID") == mid), None)
            if current is None or current != edit_state["snapshot"]:   # stale: write nothing
                _toast(tr("responses.record_changed"), duration=6)
                _close_edit()
                return
            reg, _ = update_measure(reg, mid, fields)
        else:
            reg, _ = add_measure(reg, fields, today=date.today().isoformat())
            _toast(tr(_RM + "response_measure_added"), kind="message", duration=3)
        _write(reg)
        _close_edit()
        _clear_form()

    @reactive.effect
    @reactive.event(input.cancel_measure, ignore_init=True)
    def _cancel():
        _close_edit()
        _clear_form()

    @reactive.effect
    @reactive.event(input.delete_measures, ignore_init=True)
    def _delete():
        ids = _selected_ids()
        if not ids:
            _toast(tr("responses.select_first"))
            return
        reg, refs = delete_measures(_register(), ids)
        _write(reg)
        message = tr(_RM + "deleted_response_measures")
        if refs > 0:                       # no cascade (spec §6.1): say what still refers
            message += " " + tr("responses.deleted_with_refs", n=refs)
        _toast(message, duration=6)
        if editing_measure.get() in ids:
            _close_edit()
            _clear_form()
