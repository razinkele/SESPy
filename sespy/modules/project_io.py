"""Project I/O — Save / Load / New buttons in the sidebar's Quick Actions.

Owns the handlers; modules don't see this. Modules read project_data and
emit event_bus signals; this module writes project_data when the user
loads a file or starts fresh.

Three buttons:
  - Save Project   — `@render.download` writes the current project as JSON
  - Load Project   — `ui.input_file` accepts an upload, validates, sets
  - New Project    — resets to the seed sample (the default-on-startup data)

Status messages go through `ui.notification_show` (toast) so the user
knows what happened. Validation errors surface as warnings rather than
crashing the app.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from shiny import Inputs, Outputs, Session, reactive, render, ui

from .. import data_structure as ds
from ..autosave import (
    autosave_age_seconds,
    autosave_path,
    clear_autosave,
    read_autosave,
    write_autosave,
)
from ..event_bus import EventBus
from ..i18n import Translator
from ..persistent_storage import (
    ValidationResult,
    load_project,
    project_to_bytes,
    validate_project_payload,
)
from ..recent_projects import add_recent


def quick_actions_ui(translator: Translator | None = None) -> ui.Tag:
    """Three-button stack styled to match `.sespy-quick-actions`. Caller
    drops this into `dashboard_page(quick_actions=...)`.
    """
    def t(key: str, fallback: str) -> str:
        return translator.t(key) if translator else fallback

    return ui.tags.div(
        # Auto-save indicator at the top — silent until first change, then
        # shows a small "Auto-saved at HH:MM" line.
        ui.output_ui("autosave_indicator"),
        ui.h6(t("ui.quickactions.title", "QUICK ACTIONS")),
        # Save: a download_button is a special widget that triggers our
        # @render.download function below. The id maps to the function.
        ui.download_button(
            "save_project",
            ui.tags.span(
                ui.tags.i(class_="fa fa-save"),
                ui.tags.span(t("common.buttons.save_project", "Save Project"),
                             class_="btn-text"),
            ),
            class_="btn",
        ),
        # Load: input_file always emits a label + button + filename text
        # input. We pass an empty label (None renders the param name
        # instead, which is worse) and hide the filename display via CSS
        # in the .sespy-quick-actions context. Only `button_label` shows.
        ui.input_file(
            "load_project",
            "",
            accept=[".json"],
            multiple=False,
            button_label=ui.tags.span(
                ui.tags.i(class_="fa fa-folder-open"),
                ui.tags.span(t("common.buttons.load_project", "Load Project"),
                             class_="btn-text"),
            ),
            placeholder="",
        ),
        ui.input_action_button(
            "new_project",
            ui.tags.span(
                ui.tags.i(class_="fa fa-file"),
                ui.tags.span(t("common.buttons.new_project", "New Project"),
                             class_="btn-text"),
            ),
            class_="btn",
        ),
        class_="sespy-quick-actions",
    )


def quick_actions_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[ds.Project],
    event_bus: EventBus,
    sample_path: Path,
    translator: Translator | None = None,
    autosave_enabled=None,
) -> None:
    """Wire the Quick Actions buttons.

    `project_data` is the source of truth for the loaded project. Save reads
    it; Load and New write to it (and emit `isa_change` so analysis modules
    invalidate their caches, mirroring `server/project_io.R`).
    """
    def t(key: str, fallback: str) -> str:
        return translator.t(key) if translator else fallback

    # Tracks the moment of the last successful autosave write — drives
    # the "Auto-saved at HH:MM" indicator.
    autosave_time: reactive.Value[str] = reactive.value("")

    # ---- AUTO-SAVE ------------------------------------------------------
    @reactive.effect
    def _autosave_on_change():
        # Subscribe to ISA changes so editor activity and metadata edits are autosaved.
        event_bus.isa_change.get()
        try:
            write_autosave(project_data.get())
            from datetime import datetime as _dt
            autosave_time.set(_dt.now().strftime("%H:%M:%S"))
        except Exception:
            pass

    @output
    @render.ui
    def autosave_indicator():
        ts = autosave_time.get()
        if not ts:
            return ui.tags.span()  # silent until the first save
        return ui.tags.div(
            ui.tags.i(class_="fa fa-cloud", style="margin-right: 6px;"),
            ui.tags.span(t("ui.quickactions.autosaved", "Auto-saved")),
            ui.tags.span(" · ", style="opacity: 0.5;"),
            ui.tags.span(ts),
            class_="sespy-autosave-indicator",
        )

    # ---- RECOVERY OFFER -------------------------------------------------
    # On session start, check for a stale autosave file and offer to
    # restore it. Skipped if the autosave is older than 24h (probably from
    # a long-abandoned session — recovery prompts then are confusing).
    #
    # The action button uses notification_show's `action=` parameter, NOT
    # a hand-rolled action_button inside `ui=`. Shiny doesn't bind input
    # widgets that appear in notification messages — only the dedicated
    # `action` slot wires the click back to a server input.
    @reactive.effect
    def _offer_recovery():
        if getattr(_offer_recovery, "_fired", False):
            return
        _offer_recovery._fired = True  # type: ignore[attr-defined]

        age = autosave_age_seconds()
        if age is None or age > 24 * 3600:
            return
        if read_autosave() is None:
            return
        ui.notification_show(
            t("ui.quickactions.recovery_available",
              "Recovered work from your last session."),
            action=ui.input_action_button(
                "__sespy_restore_autosave__",
                t("ui.quickactions.restore", "Restore"),
                class_="btn btn-sm btn-primary",
            ),
            type="default",
            duration=None,
            id="autosave-recovery",
        )

    # ---- SAVE -----------------------------------------------------------
    @render.download(
        filename=lambda: f"sespy-project-{datetime.now():%Y%m%d-%H%M%S}.json"
    )
    def save_project():
        # project_to_bytes calls .with_modified_now() internally; don't double-stamp.
        proj = project_data.get()
        try:
            clear_autosave()
        except Exception:
            pass
        # Emit before yield so the generator's continuation isn't required.
        event_bus.emit_project_saved()
        yield project_to_bytes(proj)

    # ---- RECOVERY ACTION (from the toast button) -----------------------
    @reactive.effect
    @reactive.event(input["__sespy_restore_autosave__"], ignore_init=True)
    def _do_restore():
        recovered = read_autosave()
        if recovered is None:
            ui.notification_remove("autosave-recovery")
            return
        project_data.set(recovered)
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        event_bus.emit_project_loaded()
        ui.notification_remove("autosave-recovery")
        ui.notification_show(
            t("ui.quickactions.restored", "Recovered work restored."),
            type="message",
            duration=4,
        )

    # ---- LOAD -----------------------------------------------------------
    @reactive.effect
    @reactive.event(input.load_project, ignore_init=True)
    def _on_upload():
        files = input.load_project()
        if not files:
            return
        upload = files[0]
        try:
            proj = load_project(Path(upload["datapath"]))
        except ValueError as e:
            ui.notification_show(
                str(e),
                type="warning",
                duration=8,
            )
            return
        project_data.set(proj)
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        event_bus.emit_project_loaded()
        # Register in the Recent Projects panel — best-effort.
        try:
            add_recent(
                path=upload["datapath"],
                name=proj.metadata.name,
                element_count=proj.isa_data.element_count(),
                connection_count=proj.isa_data.connection_count(),
            )
        except Exception:
            pass
        ui.notification_show(
            t("ui.quickactions.loaded", "Project loaded.")
            + f"  ({proj.metadata.name})",
            type="message",
            duration=4,
        )

    # ---- NEW ------------------------------------------------------------
    @reactive.effect
    @reactive.event(input.new_project, ignore_init=True)
    def _on_new():
        project_data.set(ds.Project.from_isa(ds.load_sample(sample_path)))
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        ui.notification_show(
            t("ui.quickactions.reset", "Project reset to sample."),
            type="message",
            duration=3,
        )
