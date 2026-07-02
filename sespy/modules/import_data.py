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

import json
from pathlib import Path

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..constants import DAPSIWRM_ELEMENTS
from ..data_structure import Project
from ..event_bus import EventBus
from ..excel_import import parse_excel
from ..i18n import Translator
from ..persistent_storage import ValidationResult
from ..qsem_import import parse_qsem, qsem_themes, suggest_dapsiwrm_map


def parse_upload(name: str, datapath: Path | str) -> ValidationResult:
    """Dispatch an uploaded file to the right parser by its ORIGINAL filename
    extension — Shiny's temp `datapath` may not preserve the suffix."""
    suffix = Path(name).suffix.lower()
    if suffix in (".qsem", ".json"):
        result = parse_qsem(datapath)
    else:
        result = parse_excel(datapath)
    # Name the project after the original upload, not Shiny's temp datapath
    # (whose stem is an opaque index like "0").
    if result.valid and result.project is not None:
        result.project.metadata.name = Path(name).stem
    return result


@module.ui
def import_data_ui() -> ui.Tag:
    return ui.card(
        ui.card_header("Import Data"),
        ui.div(
            ui.h5("Upload Excel workbook or QSEM model"),
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
                " You can also upload a ",
                ui.tags.b(".qsem"),
                " model file exported from the QSEM app.",
                class_="text-muted",
            ),
            ui.input_file(
                "xlsx",
                "",
                accept=[".xlsx", ".xls", ".qsem", ".json"],
                multiple=False,
                button_label="Choose a file…",
                placeholder="No file selected",
            ),
            ui.input_checkbox(
                "assign_dapsiwrm",
                "Assign DAPSIWRM types (QSEM only)",
                value=False,
            ),
            ui.tags.small(
                "Map each QSEM theme to a DAPSIWRM category so the diagram is "
                "coloured and levelled. Unmapped themes stay untyped.",
                class_="text-muted",
            ),
            ui.output_ui("dapsiwrm_map"),
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
    raw_qsem: reactive.Value[dict | None] = reactive.value(None)
    themes: reactive.Value[list[str]] = reactive.value([])
    seq: reactive.Value[int] = reactive.value(0)

    def _t(key: str, fallback: str) -> str:
        return translator.t(key) if translator else fallback

    @reactive.effect
    @reactive.event(input.xlsx, ignore_init=True)
    def _on_upload():
        files = input.xlsx()
        if not files:
            parsed.set(None)
            return
        info = files[0]
        result = parse_upload(info["name"], info["datapath"])
        parsed.set(result)
        suffix = Path(info["name"]).suffix.lower()
        if suffix in (".qsem", ".json") and result.valid:
            try:
                data = json.loads(Path(info["datapath"]).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = None
            raw_qsem.set(data)
            themes.set([t for t, _ in qsem_themes(data)] if data else [])
            seq.set(seq.get() + 1)
        else:
            raw_qsem.set(None)
            themes.set([])
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

    @output
    @render.ui
    def dapsiwrm_map():
        if raw_qsem.get() is None or not input.assign_dapsiwrm():
            return None
        th = themes.get()
        suggested = suggest_dapsiwrm_map(th)
        choices = {"": _t("import.leave_untyped", "Leave untyped")}
        choices.update({d: d for d in DAPSIWRM_ELEMENTS})
        s = seq.get()
        counts = dict(qsem_themes(raw_qsem.get()))
        rows = [
            ui.tags.tr(
                ui.tags.td(t or _t("import.leave_untyped", "(untyped)")),
                ui.tags.td(str(counts.get(t, 0)), class_="text-nowrap"),
                ui.tags.td(ui.input_select(
                    f"map_{s}_{i}", None, choices=choices, selected=suggested.get(t, ""),
                    width="240px",
                )),
            )
            for i, t in enumerate(th)
        ]
        head = ui.tags.thead(ui.tags.tr(
            ui.tags.th(_t("import.map_theme", "QSEM theme")),
            ui.tags.th(_t("import.map_count", "Nodes")),
            ui.tags.th(_t("import.map_type", "DAPSIWRM type")),
        ))
        return ui.tags.table(head, ui.tags.tbody(*rows),
                             class_="table table-sm sespy-feedback-table mb-0")

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
