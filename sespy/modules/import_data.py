"""Import Data module — port of modules/import_data_module.R (slimmed down).

Workflow:
  1. User uploads an .xlsx (drag-drop or pick) with `Elements` + `Connections` sheets
  2. Module parses + validates, shows a summary preview
  3. User clicks "Load into project" — replaces project_data, fires isa_change
     so all three downstream modules (CLD, Loops, Metrics) refresh

Validation reuses the same machinery as JSON load (`validate_project_payload`),
so the user gets a consistent error story whether the source is JSON or Excel.

Why this matters for the port: with JSON load + Excel import both available,
domain experts can use whichever workflow they prefer (the R user base splits
roughly 60/40 toward Excel for the same reason — most ecologists curate data
in spreadsheets). Plus this exercises a fourth module subscribing to the
shared event_bus, lifting the architecture's coupling-count to four.
"""

from __future__ import annotations

from pathlib import Path

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..data_structure import IsaData, Project
from ..event_bus import EventBus
from ..excel_import import parse_excel
from ..i18n import Translator
from ..persistent_storage import ValidationResult


@module.ui
def import_data_ui() -> ui.Tag:
    return ui.card(
        ui.card_header("Import Data"),
        ui.div(
            ui.h5("Upload Excel workbook"),
            ui.p(
                "The workbook must contain an ",
                ui.tags.b("Elements"),
                " sheet and a ",
                ui.tags.b("Connections"),
                " sheet. Sheet and column names are matched case-insensitively. ",
                "Required columns: Elements need ",
                ui.tags.code("id, label, type"),
                "; Connections need ",
                ui.tags.code("source, target"),
                ".",
                class_="text-muted",
            ),
            ui.input_file(
                "xlsx",
                "",
                accept=[".xlsx", ".xls"],
                multiple=False,
                button_label="Choose Excel file…",
                placeholder="No file selected",
            ),
            ui.tags.hr(),
            ui.output_ui("preview"),
            ui.tags.div(
                ui.input_action_button(
                    "commit",
                    "Load into project",
                    class_="btn btn-primary",
                    disabled=True,
                ),
                style="margin-top: 16px;",
            ),
            style="padding: 24px;",
        ),
        class_="sespy-card",
        full_screen=False,
    )


@module.server
def import_data_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    parsed: reactive.Value[ValidationResult | None] = reactive.value(None)

    @reactive.effect
    @reactive.event(input.xlsx, ignore_init=True)
    def _on_upload():
        files = input.xlsx()
        if not files:
            parsed.set(None)
            return
        path = Path(files[0]["datapath"])
        result = parse_excel(path)
        parsed.set(result)
        # Enable/disable the commit button via JS — `update_action_button`
        # doesn't accept disabled= directly, so we toggle it client-side.
        if result.valid:
            session.send_input_message(
                "commit",
                {"label": "Load into project"},
            )
            ui.update_action_button("commit", disabled=False)
        else:
            ui.update_action_button("commit", disabled=True)

    @output
    @render.ui
    def preview():
        result = parsed.get()
        if result is None:
            return ui.tags.p(
                "No file uploaded yet.",
                class_="text-muted",
            )
        if not result.valid:
            return ui.div(
                ui.tags.h6("Errors", class_="text-danger"),
                ui.tags.ul(*[ui.tags.li(e) for e in result.errors]),
                class_="alert alert-warning",
                style="padding: 12px;",
            )
        proj = result.project
        assert proj is not None
        types_seen = {el.type for el in proj.isa_data.elements}
        return ui.div(
            ui.tags.h6("Preview", class_="text-success"),
            ui.tags.ul(
                ui.tags.li(f"Workbook: {proj.metadata.name}"),
                ui.tags.li(f"Elements: {proj.isa_data.element_count()}"),
                ui.tags.li(f"Connections: {proj.isa_data.connection_count()}"),
                ui.tags.li(f"Element types: {', '.join(sorted(types_seen)) or '—'}"),
            ),
            class_="alert alert-success",
            style="padding: 12px;",
        )

    @reactive.effect
    @reactive.event(input.commit, ignore_init=True)
    def _on_commit():
        result = parsed.get()
        if result is None or not result.valid or result.project is None:
            return
        project_data.set(result.project)
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        event_bus.emit_project_loaded()
        ui.notification_show(
            f"Imported {result.project.isa_data.element_count()} elements "
            f"and {result.project.isa_data.connection_count()} connections.",
            type="message",
            duration=4,
        )
        # Reset the form so the same file can be re-uploaded later.
        parsed.set(None)
        ui.update_action_button("commit", disabled=True)
