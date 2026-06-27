"""Templates panel — pick a domain-specific starting project.

Each card shows the template's name, description, demonstration area,
and element/connection counts, plus a Load button. Loading replaces
`project_data` and fires `isa_change` so the four analysis modules
recompute against the new SES.

R counterpart: `modules/template_ses_module.R` (~1200 LOC). Slimmed to
the picker + load action; R's "edit before loading" wizard is deferred.
"""

from __future__ import annotations

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..data_structure import Project
from ..event_bus import EventBus
from ..i18n import Translator, t
from ..templates import TemplateInfo, list_templates, load_template


def _template_card(idx: int, info: TemplateInfo) -> ui.Tag:
    return ui.tags.div(
        ui.tags.div(
            ui.tags.h5(info.name, style="margin: 0 0 4px 0;"),
            ui.tags.div(
                f"{info.element_count} elements · {info.connection_count} connections"
                + (f" · {info.da_site}" if info.da_site else ""),
                class_="text-muted",
                style="font-size: 0.85rem;",
            ),
            ui.tags.p(
                info.description,
                style="margin: 8px 0 0 0; font-size: 0.9rem;",
            ),
            style="flex: 1;",
        ),
        ui.tags.div(
            ui.input_action_button(
                f"load_template_{idx}",
                t("templates.load"),
                class_="btn btn-primary",
            ),
            style="display: flex; align-items: center;",
        ),
        style=("display: flex; gap: 16px; align-items: center; "
               "padding: 16px 20px; border: 1px solid var(--mist-light); "
               "border-radius: 8px; background: white; "
               "margin-bottom: 12px;"),
    )


@module.ui
def templates_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.templates")),
        ui.div(
            ui.p(
                t("templates.intro"),
                class_="text-muted",
            ),
            ui.output_ui("templates_list"),
            style="padding: 24px;",
        ),
        class_="sespy-card",
        full_screen=False,
    )


# --- Helper to wire each Load button at module init time -------------------

MAX_TEMPLATES = 16


def _wire_load(
    input: Inputs,
    idx: int,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    templates_calc,
) -> None:
    @reactive.effect
    @reactive.event(input[f"load_template_{idx}"], ignore_init=True)
    def _():
        rows = templates_calc()
        if idx >= len(rows):
            return
        info = rows[idx]
        try:
            project = load_template(info.file)
        except (ValueError, OSError) as e:
            ui.notification_show(
                f"Couldn't load template: {e}",
                type="warning",
                duration=6,
            )
            return
        project_data.set(project)
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        event_bus.emit_template_loaded()
        ui.notification_show(
            t("templates.loaded") + f" ({info.name})",
            type="message",
            duration=4,
        )


@module.server
def templates_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @reactive.calc
    def templates() -> list[TemplateInfo]:
        return list_templates()

    @output
    @render.ui
    def templates_list():
        rows = templates()
        if not rows:
            return ui.tags.p(
                "No templates installed.",
                class_="text-muted",
            )
        return ui.tags.div(*[_template_card(i, t_) for i, t_ in enumerate(rows)])

    for i in range(MAX_TEMPLATES):
        _wire_load(input, i, project_data, event_bus, templates)
