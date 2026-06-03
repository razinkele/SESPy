"""Report Export — generates an HTML or PDF report of the current project.

Sits at the end of the workflow stepper ("Report" stage). One panel,
two download buttons, an inline preview of what the report contains.
"""

from __future__ import annotations

from datetime import datetime

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..data_structure import IsaData, Project
from ..event_bus import EventBus
from ..i18n import Translator
from ..report import render_docx, render_html, render_pdf


@module.ui
def report_export_ui() -> ui.Tag:
    return ui.card(
        ui.card_header("Export Report"),
        ui.div(
            ui.h4("Generate a project report"),
            ui.p(
                "Bundles the project's ISA data, feedback-loop classification, "
                "centrality rankings, and leverage points into one document. "
                "HTML opens directly in a browser; PDF is print-ready.",
                class_="text-muted",
            ),
            ui.tags.div(
                ui.download_button(
                    "download_html",
                    ui.tags.span(
                        ui.tags.i(class_="fa fa-file-code", style="margin-right: 6px;"),
                        "Download HTML",
                    ),
                    class_="btn btn-primary",
                ),
                ui.download_button(
                    "download_pdf",
                    ui.tags.span(
                        ui.tags.i(class_="fa fa-file-pdf", style="margin-right: 6px;"),
                        "Download PDF",
                    ),
                    class_="btn btn-outline-primary",
                    style="margin-left: 12px;",
                ),
                ui.download_button(
                    "download_docx",
                    ui.tags.span(
                        ui.tags.i(class_="fa fa-file-word", style="margin-right: 6px;"),
                        "Download Word",
                    ),
                    class_="btn btn-outline-primary",
                    style="margin-left: 12px;",
                ),
                style="margin: 16px 0 24px 0;",
            ),
            ui.tags.hr(),
            ui.h5("Preview"),
            ui.output_ui("report_preview"),
            style="padding: 24px;",
        ),
        class_="sespy-card",
        full_screen=False,
    )


@module.server
def report_export_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    def _stamp() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    @render.download(filename=lambda: f"sespy-report-{_stamp()}.html")
    def download_html():
        proj = project_data.get()
        yield render_html(proj).encode("utf-8")

    @render.download(filename=lambda: f"sespy-report-{_stamp()}.pdf")
    def download_pdf():
        proj = project_data.get()
        yield render_pdf(proj)

    @render.download(filename=lambda: f"sespy-report-{_stamp()}.docx")
    def download_docx():
        proj = project_data.get()
        yield render_docx(proj)

    @output
    @render.ui
    def report_preview():
        # Subscribe so the preview re-renders when the user edits the data
        event_bus.isa_change.get()
        proj = project_data.get()
        return ui.div(
            ui.tags.iframe(
                # Inline-rendered HTML, no server round-trip — gives the
                # user a clear preview of exactly what they're about to
                # download.
                srcdoc=render_html(proj),
                style="width: 100%; height: 600px; border: 1px solid #e0e0e0; "
                      "border-radius: 8px; background: white;",
            ),
        )
