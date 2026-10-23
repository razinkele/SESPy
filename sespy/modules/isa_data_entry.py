"""ISA Data Entry — port of modules/isa_data_entry_module.R (slimmed down).

Lets the user add/remove elements and connections directly through the UI,
without round-tripping through Excel or JSON. Changes write through to the
shared `project_data` reactive, so the CLD canvas, loop detector, metrics,
and leverage modules all see the edit immediately via `event_bus.isa_change`.

Scope vs. R:
- The R module has separate tabs per DAPSIWRM type with type-specific
  fields (indicator for ES, scale for Activities, …). This POC unifies
  them into a single Elements table; the type comes from a dropdown.
- Adjacency-matrix editing — the R "click-and-toggle" matrix view — is
  deferred. Users edit connections one row at a time here.
- Validation reuses the existing JSON validator so the same error
  story as load/import.
"""

from __future__ import annotations

import dataclasses

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..constants import (
    CONNECTION_POLARITY_LABELS,
    DAPSIWRM_ELEMENTS,
    DELAY_LEVELS,
    POLICY_TARGET_CODES,
)
from ..data_structure import Connection, Element, IsaData, Project
from ..event_bus import EventBus
from ..i18n import Translator, t
from ..link_rules import note_for, seed_polarity
from ..response_register import references_to
from ..utils import next_id


def _prefix_for(element_type: str) -> str:
    """Three-letter short code per DAPSIWRM element type."""
    return {
        "Drivers":                          "D",
        "Activities":                       "A",
        "Pressures":                        "P",
        "Marine Processes & Functioning":   "MPF",
        "Ecosystem Services":               "ES",
        "Goods & Benefits":                 "GB",
        "Responses":                        "R",
        "Measures":                         "RM",
    }.get(element_type, "X")


@module.ui
def isa_data_entry_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.entry")),
        ui.div(
            ui.h4(t("entry.elements")),
            ui.layout_columns(
                ui.input_text("new_label", t("entry.label"),
                              placeholder="e.g. Tourism demand"),
                ui.input_select(
                    "new_type", t("entry.type"),
                    {x: x for x in DAPSIWRM_ELEMENTS},
                    selected="Drivers",
                ),
                ui.input_action_button("add_element", t("entry.add_element"),
                                       class_="btn btn-primary",
                                       style="align-self: end;"),
                col_widths=(5, 4, 3),
            ),
            ui.tags.div(
                ui.output_data_frame("elements_table"),
                ui.input_action_button("edit_element", t("entry.edit_selected"),
                                       class_="btn btn-outline-primary",
                                       style="margin-top: 8px; margin-right: 8px;"),
                ui.input_action_button("remove_element", t("entry.remove_element"),
                                       class_="btn btn-outline-danger",
                                       style="margin-top: 8px;"),
                ui.output_ui("element_editor"),
                style="margin-top: 8px;",
            ),

            ui.tags.hr(style="margin: 32px 0;"),

            ui.h4(t("entry.connections")),
            ui.layout_columns(
                ui.output_ui("source_picker"),
                ui.output_ui("target_picker"),
                ui.input_radio_buttons(
                    "new_polarity", t("entry.polarity"),
                    CONNECTION_POLARITY_LABELS,
                    selected="+",
                    inline=True,
                ),
                ui.input_select(
                    "new_delay", t("entry.delay"),
                    {lvl: t(f"delay.{lvl}") for lvl in DELAY_LEVELS},
                    selected="immediate",
                ),
                ui.input_action_button("add_connection", t("entry.add_connection"),
                                       class_="btn btn-primary",
                                       style="align-self: end;"),
                col_widths=(3, 3, 2, 2, 2),
            ),
            # Off-rule warning for the chosen pair (link_rules.note_for);
            # empty for canonical/extension/untyped pairs. The link still saves.
            ui.output_ui("off_rule_note"),
            ui.tags.div(
                ui.output_data_frame("connections_table"),
                ui.input_action_button("edit_connection", t("entry.edit_selected"),
                                       class_="btn btn-outline-primary",
                                       style="margin-top: 8px; margin-right: 8px;"),
                ui.input_action_button("remove_connection", t("entry.remove_connection"),
                                       class_="btn btn-outline-danger",
                                       style="margin-top: 8px;"),
                ui.output_ui("connection_editor"),
                style="margin-top: 8px;",
            ),

            ui.tags.hr(),
            ui.output_ui("status_line"),
            style="padding: 24px;",
        ),
        class_="sespy-card",
        full_screen=False,
    )


@module.server
def isa_data_entry_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    tr = translator.t if translator is not None else t
    # P1b edit panels: the element (by id) or connection (by source, target)
    # being edited; None = no editor shown.
    editing_element: reactive.Value[str | None] = reactive.value(None)
    editing_connection: reactive.Value[tuple[str, str] | None] = reactive.value(None)
    # The record each editor opened (spec §6.2 stale check): Save writes only
    # if the current project still holds an equal record. A project load or a
    # MosaicSES compartment switch replaces the project under an open editor,
    # and compartments repeat element IDs. Plain dict: never a dependency.
    snapshot: dict[str, Element | Connection | None] = {"element": None, "connection": None}

    # ---- Element-type-aware label pickers for connections ---------------
    # Both pickers re-render on every isa_change with no selected=, so they
    # fall back to their first choice. That choice is an empty "— choose —"
    # entry, so a half-chosen pair never seeds a polarity or shows a note.
    def _picker_choices() -> dict[str, str]:
        elements = project_data.get().isa_data.elements
        if not elements:
            return {"": "(no elements yet)"}
        return {"": t("entry.choose_element"),
                **{el.id: f"{el.id} · {el.label}" for el in elements}}

    @output
    @render.ui
    def source_picker():
        event_bus.isa_change.get()
        return ui.input_select("new_source", t("entry.source"), _picker_choices())

    @output
    @render.ui
    def target_picker():
        event_bus.isa_change.get()
        return ui.input_select("new_target", t("entry.target"), _picker_choices())

    def _element(eid: str | None) -> Element | None:
        if not eid:
            return None
        return next((el for el in project_data.get().isa_data.elements
                     if el.id == eid), None)

    def _chosen_pair() -> tuple[Element | None, Element | None]:
        """The elements behind the two pickers; takes the picker
        dependencies, looks the elements up without one."""
        src_id, tgt_id = input.new_source(), input.new_target()
        with reactive.isolate():
            return _element(src_id), _element(tgt_id)

    # ---- Polarity prefill from the link rules (R default_polarity_for_matrix)
    @reactive.effect
    def _seed_polarity():
        src, tgt = _chosen_pair()
        polarity = seed_polarity(src, tgt)
        # Changing either endpoint re-seeds, overriding a manual choice (as R).
        if polarity is not None:
            ui.update_radio_buttons("new_polarity", selected=polarity)

    @output
    @render.ui
    def off_rule_note():
        src, tgt = _chosen_pair()
        text = note_for(src, tgt, translator)
        if text is None:
            return None
        return ui.div(text, class_="sespy-off-rule-note alert alert-warning")

    # ---- Tables ---------------------------------------------------------
    @output
    @render.data_frame
    def elements_table():
        import pandas as pd

        event_bus.isa_change.get()
        rows = [
            {"id": el.id, "label": el.label, "type": el.type}
            for el in project_data.get().isa_data.elements
        ]
        return render.DataGrid(
            pd.DataFrame(rows or [{"id": "", "label": "", "type": ""}]),
            selection_mode="row",
            height="240px",
        )

    @output
    @render.data_frame
    def connections_table():
        import pandas as pd

        event_bus.isa_change.get()
        by_id = {el.id: el.label for el in project_data.get().isa_data.elements}
        rows = [
            {
                "source": f"{c.source} · {by_id.get(c.source, '?')}",
                "target": f"{c.target} · {by_id.get(c.target, '?')}",
                "polarity": c.polarity,
                "strength": c.strength,
                "delay": c.delay,
            }
            for c in project_data.get().isa_data.connections
        ]
        return render.DataGrid(
            pd.DataFrame(rows or [{"source": "", "target": "", "polarity": "", "strength": "", "delay": ""}]),
            selection_mode="row",
            height="240px",
        )

    # ---- Mutators -------------------------------------------------------
    def _replace(isa: IsaData) -> None:
        current = project_data.get()
        project_data.set(current.replace(isa_data=isa))
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()

    @reactive.effect
    @reactive.event(input.add_element, ignore_init=True)
    def _add_element():
        label = (input.new_label() or "").strip()
        if not label:
            ui.notification_show("Label is required.", type="warning", duration=3)
            return
        el_type = input.new_type() or "Drivers"
        existing = [e.id for e in project_data.get().isa_data.elements]
        new = Element(
            id=next_id(existing, _prefix_for(el_type)),
            label=label,
            type=el_type,
        )
        isa = project_data.get().isa_data
        _replace(IsaData(
            elements=[*isa.elements, new],
            connections=isa.connections,
        ))
        ui.update_text("new_label", value="")

    @reactive.effect
    @reactive.event(input.remove_element, ignore_init=True)
    def _remove_element():
        sel = elements_table.cell_selection()
        if not sel or not sel.get("rows"):
            ui.notification_show("Select an element first.", type="warning", duration=3)
            return
        idx = sel["rows"][0]
        isa = project_data.get().isa_data
        if idx >= len(isa.elements):
            return
        target_id = isa.elements[idx].id
        # Drop the element AND any connection that references it — leaving
        # dangling refs would fail the project validator on next save.
        _replace(IsaData(
            elements=[e for e in isa.elements if e.id != target_id],
            connections=[c for c in isa.connections
                         if c.source != target_id and c.target != target_id],
        ))
        if editing_element.get() == target_id:
            editing_element.set(None)
        pair = editing_connection.get()
        if pair is not None and target_id in pair:
            editing_connection.set(None)
        # Spec §6.1: deletes do not cascade into the register; element IDs can
        # be reused (next_id), so say which measures still name this element.
        refs = references_to(project_data.get().response_measures, target_id)
        if refs:
            ui.notification_show(
                tr("responses.element_still_referenced", id=target_id,
                   measures=", ".join(refs)),
                type="warning", duration=8)

    # ---- Edit panels (P1b, spec §6.2) -----------------------------------
    # The editors render ONLY when editing_* changes (@reactive.event), never
    # on project_data writes, so autosave or another module cannot clobber
    # what the user is typing (the pims_stakeholders._repopulate pattern).
    @reactive.effect
    @reactive.event(input.edit_element, ignore_init=True)
    def _edit_element():
        sel = elements_table.cell_selection()
        isa = project_data.get().isa_data
        if not sel or not sel.get("rows") or sel["rows"][0] >= len(isa.elements):
            ui.notification_show(tr("entry.select_first"), type="warning", duration=3)
            return
        el = isa.elements[sel["rows"][0]]
        snapshot["element"] = el
        # None first, so a re-click on the open element re-renders it with the new
        # snapshot: reactive.Value ignores a set() of the identical id object.
        editing_element.set(None)
        editing_element.set(el.id)

    @output
    @render.ui
    @reactive.event(editing_element)
    def element_editor():
        el = _element(editing_element.get())
        if el is None:
            return None
        fields = [
            ui.input_text("el_label", tr("entry.label"), value=el.label),
            ui.input_text_area("el_description", tr("entry.description"),
                               value=el.description),
        ]
        if el.type != "Responses":       # R isa_form_builders.R:74-86
            choices = {"": ""}
            choices.update({c: tr(f"modules.indicator_registry.policy_target.{c}")
                            for c in POLICY_TARGET_CODES})
            if el.policy_target and el.policy_target not in choices:
                choices[el.policy_target] = el.policy_target     # free text, shown raw
            fields += [
                ui.input_text("el_indicator", tr("modules.indicator_registry.field_indicator"),
                              value=el.indicator),
                ui.input_text("el_indicator_unit", tr("modules.indicator_registry.field_unit"),
                              value=el.indicator_unit),
                ui.input_text("el_data_source",
                              tr("modules.indicator_registry.field_data_source"),
                              value=el.data_source),
                ui.input_selectize("el_policy_target",
                                   tr("modules.indicator_registry.field_policy_target"),
                                   choices, selected=el.policy_target,
                                   options={"create": True}),
                ui.tags.small(tr("modules.indicator_registry.policy_target_help"),
                              class_="text-muted"),
            ]
            if el.registry_id:
                fields.append(ui.p(tr("entry.registry", id=el.registry_id,
                                      version=el.registry_version),
                                   class_="text-muted sespy-registry-line"))
        return ui.div(
            ui.h5(f"{el.id} · {el.type}"),
            *fields,
            ui.div(
                ui.input_action_button("save_element", tr("entry.save_changes"),
                                       class_="btn btn-primary", style="margin-right: 8px;"),
                ui.input_action_button("cancel_element", tr("entry.cancel_edit")),
                style="margin-top: 8px;",
            ),
            class_="sespy-edit-panel",
            style="margin-top: 16px; padding: 12px; border: 1px solid #dee2e6;",
        )

    @reactive.effect
    @reactive.event(input.save_element, ignore_init=True)
    def _save_element():
        eid = editing_element.get()
        if eid is None:
            return
        el = _element(eid)
        if el is None or el != snapshot["element"]:     # stale: write nothing
            ui.notification_show(tr("entry.record_changed"), type="warning", duration=6)
            editing_element.set(None)
            return
        label = (input.el_label() or "").strip()
        if not label:
            ui.notification_show(tr("entry.label_required"), type="warning", duration=3)
            return
        changes = {"label": label, "description": input.el_description() or ""}
        if el.type != "Responses":        # Responses: label and description only
            changes.update(
                indicator=input.el_indicator() or "",
                indicator_unit=input.el_indicator_unit() or "",
                data_source=input.el_data_source() or "",
                policy_target=input.el_policy_target() or "",
            )
        # dataclasses.replace keeps r_extra, the registry fields and every
        # field the panel does not show.
        new = dataclasses.replace(el, **changes)
        isa = project_data.get().isa_data
        editing_element.set(None)
        _replace(IsaData(elements=[new if e.id == eid else e for e in isa.elements],
                         connections=isa.connections))

    @reactive.effect
    @reactive.event(input.cancel_element, ignore_init=True)
    def _cancel_element():
        editing_element.set(None)

    def _connection(pair: tuple[str, str] | None) -> Connection | None:
        if pair is None:
            return None
        return next((c for c in project_data.get().isa_data.connections
                     if (c.source, c.target) == pair), None)

    @reactive.effect
    @reactive.event(input.edit_connection, ignore_init=True)
    def _edit_connection():
        sel = connections_table.cell_selection()
        conns = project_data.get().isa_data.connections
        if not sel or not sel.get("rows") or sel["rows"][0] >= len(conns):
            ui.notification_show(tr("entry.select_first"), type="warning", duration=3)
            return
        c = conns[sel["rows"][0]]
        snapshot["connection"] = c
        editing_connection.set((c.source, c.target))

    @output
    @render.ui
    @reactive.event(editing_connection)
    def connection_editor():
        c = _connection(editing_connection.get())
        if c is None:
            return None
        return ui.div(
            ui.h5(f"{c.source} → {c.target}"),
            ui.input_text_area("conn_description", tr("entry.connection_description"),
                               value=c.description),
            ui.div(
                ui.input_action_button("save_connection", tr("entry.save_changes"),
                                       class_="btn btn-primary", style="margin-right: 8px;"),
                ui.input_action_button("cancel_connection", tr("entry.cancel_edit")),
                style="margin-top: 8px;",
            ),
            class_="sespy-edit-panel",
            style="margin-top: 16px; padding: 12px; border: 1px solid #dee2e6;",
        )

    @reactive.effect
    @reactive.event(input.save_connection, ignore_init=True)
    def _save_connection():
        pair = editing_connection.get()
        if pair is None:
            return
        c = _connection(pair)
        editing_connection.set(None)
        if c is None or c != snapshot["connection"]:    # stale: write nothing
            ui.notification_show(tr("entry.record_changed"), type="warning", duration=6)
            return
        new = dataclasses.replace(c, description=input.conn_description() or "")
        isa = project_data.get().isa_data
        _replace(IsaData(elements=isa.elements,
                         connections=[new if (x.source, x.target) == pair else x
                                      for x in isa.connections]))

    @reactive.effect
    @reactive.event(input.cancel_connection, ignore_init=True)
    def _cancel_connection():
        editing_connection.set(None)

    @reactive.effect
    @reactive.event(input.add_connection, ignore_init=True)
    def _add_connection():
        try:
            src, tgt = input.new_source(), input.new_target()
        except Exception:
            return
        if not src or not tgt:
            ui.notification_show("Pick source and target elements.",
                                 type="warning", duration=3)
            return
        if src == tgt:
            ui.notification_show("Source and target must differ.",
                                 type="warning", duration=3)
            return
        isa = project_data.get().isa_data
        # Disallow exact duplicates (same source + target). The R app
        # allows them; we don't, because edge-DataSet keys collide in vis.js.
        if any(c.source == src and c.target == tgt for c in isa.connections):
            ui.notification_show("That connection already exists.",
                                 type="warning", duration=3)
            return
        new = Connection(source=src, target=tgt,
                         polarity=input.new_polarity() or "+",
                         delay=input.new_delay() or "immediate")
        _replace(IsaData(
            elements=isa.elements,
            connections=[*isa.connections, new],
        ))

    @reactive.effect
    @reactive.event(input.remove_connection, ignore_init=True)
    def _remove_connection():
        sel = connections_table.cell_selection()
        if not sel or not sel.get("rows"):
            ui.notification_show("Select a connection first.",
                                 type="warning", duration=3)
            return
        idx = sel["rows"][0]
        isa = project_data.get().isa_data
        if idx >= len(isa.connections):
            return
        new_connections = [c for i, c in enumerate(isa.connections) if i != idx]
        _replace(IsaData(elements=isa.elements, connections=new_connections))

    @output
    @render.ui
    def status_line():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        return ui.tags.p(
            f"{isa.element_count()} elements · {isa.connection_count()} connections. "
            "Use Save Project in the sidebar to write to disk.",
            class_="text-muted",
            style="font-size: 0.85rem; margin: 0;",
        )
