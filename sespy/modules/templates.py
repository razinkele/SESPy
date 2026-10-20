"""Templates panel — pick a domain-specific starting project.

Two groups (P2): "MarineSABRES templates" (R's 7 curated templates,
pre-converted, listed from `templates/marinesabres/catalogue.json`) and
"SESPy examples" (SESPy's own 4). Each card shows the template's name,
badges (MarineSABRES only: category, complexity, version, regional sea),
element/connection counts, the description, an "About this template"
section (source, usage notes) and a Load button. Loading replaces
`project_data` and fires `isa_change` so the analysis modules recompute
against the new SES.

R counterpart: `modules/template_ses_module.R` (~1200 LOC). Slimmed to
the picker + load action; R's complexity filter (P12) and its preview /
"edit before loading" flow (P13) are deferred.
"""

from __future__ import annotations

from collections.abc import Callable

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..data_structure import Project
from ..event_bus import EventBus
from ..i18n import Translator, t
from ..templates import TemplateInfo, list_catalogue, list_templates, load_template

GROUPS = ("marinesabres", "sespy")      # display order of the two groups


def _tr_value(tr: Callable[..., str], kind: str, value: str) -> str:
    """Translated category / complexity label. `tr` returns the key itself on
    a miss, so an R value SESPy has no key for (e.g. a future complexity
    "moderate") is shown raw, never as a key string. `tr` is the session
    translator's `.t` (the global `t()` resolves to a process-default clone
    inside a module render)."""
    key = f"templates.{kind}_{value.lower().replace('-', '_')}"
    text = tr(key)
    return value if text == key else text


def _badges(info: TemplateInfo, tr: Callable[..., str]) -> ui.Tag:
    labels = [_tr_value(tr, "category", info.category) if info.category else "",
              _tr_value(tr, "complexity", info.complexity) if info.complexity else "",
              f"v{info.version}" if info.version else "",
              info.regional_sea_label]
    return ui.tags.div(
        *[ui.tags.span(x, class_="badge bg-secondary me-1") for x in labels if x],
        class_="sespy-template-badges",
        style="margin: 0 0 4px 0;",
    )


def _about(info: TemplateInfo, tr: Callable[..., str]) -> ui.Tag | None:
    if not (info.source or info.usage_notes):
        return None
    return ui.tags.details(
        ui.tags.summary(tr("templates.about")),
        *[ui.tags.p(x, style="margin: 4px 0 0 0;")
          for x in (info.source, info.usage_notes) if x],
        style="margin: 8px 0 0 0; font-size: 0.85rem;",
    )


def _template_card(idx: int, info: TemplateInfo, tr: Callable[..., str]) -> ui.Tag:
    marinesabres = info.group == "marinesabres"
    return ui.tags.div(
        ui.tags.div(
            ui.tags.h5(info.name, style="margin: 0 0 4px 0;"),
            _badges(info, tr) if marinesabres else None,
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
            _about(info, tr) if marinesabres else None,
            style="flex: 1;",
        ),
        ui.tags.div(
            ui.input_action_button(
                f"load_template_{idx}",
                tr("templates.load"),
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
    tr: Callable[..., str],
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
            tr("templates.loaded") + f" ({info.name})",
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

    # The session translator app.py passes in; `.t` reads its reactive
    # `language`, so the render below refreshes on a language switch.
    tr = translator.t if translator is not None else t

    @reactive.calc
    def templates() -> list[TemplateInfo]:
        # One combined index drives the pre-wired load_template_<i> buttons.
        return list_catalogue() + list_templates()

    @output
    @render.ui
    def templates_list():
        rows = templates()
        if not rows:
            return ui.tags.p(
                "No templates installed.",
                class_="text-muted",
            )
        children: list[ui.Tag] = []
        for group in GROUPS:
            cards = [_template_card(i, r, tr) for i, r in enumerate(rows) if r.group == group]
            if not cards:
                continue                    # an empty group renders no header
            # A plain id= inside render.ui is not namespaced: use session.ns.
            children.append(ui.tags.h4(tr(f"templates.group_{group}"),
                                       id=session.ns(f"group_{group}"),
                                       style="margin: 8px 0 12px 0;"))
            children += cards
        return ui.tags.div(*children)

    for i in range(MAX_TEMPLATES):
        _wire_load(input, i, project_data, event_bus, templates, tr)
