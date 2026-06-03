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

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..constants import (
    CONNECTION_POLARITY_LABELS,
    DAPSIWRM_ELEMENTS,
)
from ..data_structure import Connection, Element, IsaData, Project
from ..event_bus import EventBus
from ..i18n import Translator, t
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
                ui.input_action_button("remove_element", t("entry.remove_element"),
                                       class_="btn btn-outline-danger",
                                       style="margin-top: 8px;"),
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
                ui.input_action_button("add_connection", t("entry.add_connection"),
                                       class_="btn btn-primary",
                                       style="align-self: end;"),
                col_widths=(3, 3, 3, 3),
            ),
            ui.tags.div(
                ui.output_data_frame("connections_table"),
                ui.input_action_button("remove_connection", t("entry.remove_connection"),
                                       class_="btn btn-outline-danger",
                                       style="margin-top: 8px;"),
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

    # ---- Element-type-aware label pickers for connections ---------------
    @output
    @render.ui
    def source_picker():
        event_bus.isa_change.get()
        choices = {el.id: f"{el.id} · {el.label}" for el in project_data.get().isa_data.elements}
        return ui.input_select("new_source", t("entry.source"),
                               choices or {"": "(no elements yet)"})

    @output
    @render.ui
    def target_picker():
        event_bus.isa_change.get()
        choices = {el.id: f"{el.id} · {el.label}" for el in project_data.get().isa_data.elements}
        return ui.input_select("new_target", t("entry.target"),
                               choices or {"": "(no elements yet)"})

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
            }
            for c in project_data.get().isa_data.connections
        ]
        return render.DataGrid(
            pd.DataFrame(rows or [{"source": "", "target": "", "polarity": "", "strength": ""}]),
            selection_mode="row",
            height="240px",
        )

    # ---- Mutators -------------------------------------------------------
    def _replace(isa: IsaData) -> None:
        current = project_data.get()
        project_data.set(Project(metadata=current.metadata, isa_data=isa))
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
                         polarity=input.new_polarity() or "+")
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
