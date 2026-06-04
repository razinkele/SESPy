"""PIMS Project Setup module.

Mirrors `modules/pims_module.R` lines 7-152 (PROJECT SETUP MODULE).
Captures project-level context (name, DA site, focal issue, definition
statement, temporal/spatial scale, system in focus) in a two-column form
view that updates the parallel `project_metadata` reactive on Save.

Pattern matches `analysis_intervention.py` for static form-style UI.
"""
from __future__ import annotations

from datetime import datetime, timezone

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..constants import DA_SITES, SPATIAL_SCALES, TEMPORAL_SCALES
from ..data_structure import Project, ProjectMetadata
from ..event_bus import EventBus
from ..i18n import Translator, t


_TEMPORAL_LABEL_KEYS = {
    "Daily": "pims.temporal_daily",
    "Monthly": "pims.temporal_monthly",
    "Yearly": "pims.temporal_yearly",
    "Decadal": "pims.temporal_decadal",
}

_SPATIAL_LABEL_KEYS = {
    "Local": "pims.spatial_local",
    "Regional": "pims.spatial_regional",
    "National": "pims.spatial_national",
    "International": "pims.spatial_international",
}


def _temporal_choices() -> dict[str, str]:
    """Map raw values to localized labels for the temporal-scale select.

    Iterating TEMPORAL_SCALES guarantees the form stays in lock-step with
    the canonical constants — adding a new scale to the constants list
    forces a missing-label-key KeyError here, fast-failing rather than
    silently producing an incomplete dropdown.
    """
    return {"": "—", **{v: t(_TEMPORAL_LABEL_KEYS[v]) for v in TEMPORAL_SCALES}}


def _spatial_choices() -> dict[str, str]:
    return {"": "—", **{v: t(_SPATIAL_LABEL_KEYS[v]) for v in SPATIAL_SCALES}}


def _da_site_choices() -> dict[str, str]:
    return {"": "—", **{s: s for s in DA_SITES}}


@module.ui
def pims_project_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("pims.title")),
        ui.div(
            ui.tags.p(t("pims.subtitle"), class_="text-muted"),
            ui.layout_columns(
                # Left column: project information.
                ui.div(
                    ui.h4(t("pims.project_information")),
                    ui.input_text(
                        "project_name",
                        t("pims.project_name"),
                        placeholder=t("pims.project_name_placeholder"),
                    ),
                    ui.input_select(
                        "da_site",
                        t("pims.demonstration_area"),
                        choices=_da_site_choices(),
                        selected="",
                    ),
                    ui.input_text_area(
                        "focal_issue",
                        t("pims.focal_issue"),
                        placeholder=t("pims.focal_issue_placeholder"),
                        rows=4,
                        width="100%",
                    ),
                    ui.input_text_area(
                        "definition_statement",
                        t("pims.definition_statement"),
                        placeholder=t("pims.definition_statement_placeholder"),
                        rows=6,
                        width="100%",
                    ),
                    ui.input_action_button(
                        "save_project_info",
                        t("pims.save"),
                        class_="btn btn-primary",
                        style="margin-top: 8px;",
                    ),
                ),
                # Right column: system scope + status.
                ui.div(
                    ui.h4(t("pims.system_scope")),
                    ui.input_select(
                        "temporal_scale",
                        t("pims.temporal_scale"),
                        choices=_temporal_choices(),
                        selected="",
                    ),
                    ui.input_select(
                        "spatial_scale",
                        t("pims.spatial_scale"),
                        choices=_spatial_choices(),
                        selected="",
                    ),
                    ui.input_text_area(
                        "system_in_focus",
                        t("pims.system_in_focus"),
                        placeholder=t("pims.system_in_focus_placeholder"),
                        rows=4,
                        width="100%",
                    ),
                    ui.tags.hr(),
                    ui.output_ui("current_status"),
                ),
                col_widths=(6, 6),
            ),
            style="padding: 16px;",
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def pims_project_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    # Session-only indicator: HH:MM:SS string set on the most recent Save
    # click in this session. None until first save.
    pims_save_status: reactive.Value[str | None] = reactive.value(None)

    # Full save handler: read form inputs, apply empty-name fallback,
    # build fresh ProjectMetadata, call project_metadata.set, emit
    # project_change, and show confirmation toast.
    @reactive.effect
    @reactive.event(input.save_project_info, ignore_init=True)
    def _handle_save() -> None:
        # Empty-name fallback: never persist a literally-empty project name.
        name = (input.project_name() or "").strip() or "Untitled Project"
        current_project = project_data.get()
        current = current_project.metadata
        new_meta = ProjectMetadata(
            name=name,
            description=current.description,
            da_site=(input.da_site() or "").strip(),
            regional_sea=current.regional_sea,
            ecosystem_type=current.ecosystem_type,
            focal_issue=(input.focal_issue() or "").strip(),
            definition_statement=(input.definition_statement() or "").strip(),
            temporal_scale=(input.temporal_scale() or "").strip(),
            spatial_scale=(input.spatial_scale() or "").strip(),
            system_in_focus=(input.system_in_focus() or "").strip(),
            created_at=current.created_at,
            modified_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            schema_version=current.schema_version,
        )
        project_data.set(current_project.replace(metadata=new_meta))
        pims_save_status.set(datetime.now().strftime("%H:%M:%S"))
        event_bus.emit_isa_change()
        ui.notification_show(
            f"{t('pims.save')} ✓",
            duration=3,
            type="message",
        )

    @output
    @render.ui
    def current_status():
        meta = project_data.get().metadata
        saved_text = pims_save_status.get() or t("pims.no_save_yet")
        return ui.tags.dl(
            ui.tags.dt(t("pims.saved_at")),
            ui.tags.dd(saved_text),
            ui.tags.dt(t("pims.modified_at")),
            ui.tags.dd(meta.modified_at or "—"),
            ui.tags.dt(t("pims.schema_version")),
            ui.tags.dd(str(meta.schema_version)),
        )

    @reactive.effect
    def _load_form_values() -> None:
        # Track project_data changes only. Do NOT subscribe to inputs
        # here — that would cause this effect to re-fire on every keystroke
        # and undo the user's typing.
        meta = project_data.get().metadata
        ui.update_text("project_name", value=meta.name or "")
        ui.update_select("da_site", selected=meta.da_site or "")
        ui.update_text_area("focal_issue", value=meta.focal_issue or "")
        ui.update_text_area("definition_statement", value=meta.definition_statement or "")
        ui.update_select("temporal_scale", selected=meta.temporal_scale or "")
        ui.update_select("spatial_scale", selected=meta.spatial_scale or "")
        ui.update_text_area("system_in_focus", value=meta.system_in_focus or "")
