"""Project I/O — Save / Load / New buttons in the sidebar's Quick Actions.

Owns the handlers; modules don't see this. Modules read project_data and
emit event_bus signals; this module writes project_data when the user
loads a file or starts fresh.

Three buttons:
  - Save Project   — `@render.download_button` writes the current project as JSON
  - Load Project   — `ui.input_file` accepts an upload, validates, sets
  - New Project    — resets to the seed sample (the default-on-startup data)

Status messages go through `ui.notification_show` (toast) so the user
knows what happened. Validation errors surface as warnings rather than
crashing the app.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import logging

from shiny import Inputs, Outputs, Session, reactive, render, ui

from .. import data_structure as ds
from ..autosave import (
    autosave_age_seconds,
    clear_autosave,
    housekeeping,
    read_autosave,
    write_autosave,
)
from ..browser_token import browser_token_script, read_browser_token
from ..event_bus import EventBus
from ..i18n import Translator
from ..persistent_storage import (
    load_project,
    project_to_bytes,
)
from ..recent_projects import add_recent

logger = logging.getLogger(__name__)

# Notification id of the "saved by a newer SESPy" warning (also used by e2e).
_NEWER_BUILD_TOAST = "newer-build-warning"


def quick_actions_ui(translator: Translator | None = None) -> ui.Tag:
    """Three-button stack styled to match `.sespy-quick-actions`. Caller
    drops this into `dashboard_page(quick_actions=...)`.
    """
    def t(key: str, fallback: str) -> str:
        return translator.t(key) if translator else fallback

    return ui.tags.div(
        # Reports this browser's private token (localStorage) to the server;
        # autosave and recent projects are scoped to it.
        browser_token_script(),
        # Auto-save indicator at the top — silent until first change, then
        # shows a small "Auto-saved at HH:MM" line.
        ui.output_ui("autosave_indicator"),
        ui.h6(t("ui.quickactions.title", "QUICK ACTIONS")),
        # Save: a download_button is a special widget that triggers our
        # @render.download_button function below. The id maps to the function.
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
    def t(key: str, fallback: str, **fmt) -> str:
        if translator:
            return translator.t(key, **fmt)
        return fallback.format(**fmt) if fmt else fallback

    # Tracks the moment of the last successful autosave write — drives
    # the "Auto-saved at HH:MM" indicator.
    autosave_time: reactive.Value[str] = reactive.value("")

    # This browser's private token (None until the browser script reports
    # it). Autosave and recent projects are scoped to it; without it nothing
    # is written or offered — there is no shared fallback.
    @reactive.calc
    def browser_token() -> str | None:
        return read_browser_token(input)

    # Set once this browser's recovery check has run. No autosave is written
    # before then, so a fresh session can never overwrite the work it is
    # about to be offered.
    recovery_checked = reactive.value(False)

    # ---- AUTO-SAVE ------------------------------------------------------
    @reactive.effect
    def _autosave_on_change():
        # Subscribe to ISA changes so editor activity and metadata edits are autosaved.
        event_bus.isa_change.get()
        if autosave_enabled is not None and not autosave_enabled.get():
            return
        with reactive.isolate():
            token = browser_token()
            checked = recovery_checked.get()
        if token is None or not checked:
            return
        proj = project_data.get()
        if proj.newer_build:
            # Written by a newer SESPy; write_autosave would refuse anyway.
            # Clear the indicator too: an earlier project's "Auto-saved"
            # time must not suggest this one is being saved.
            autosave_time.set("")
            return
        try:
            write_autosave(proj, token=token)
            from datetime import datetime as _dt
            autosave_time.set(_dt.now().strftime("%H:%M:%S"))
        except Exception as e:
            logger.warning("quick_actions.autosave status=error reason=%s", type(e).__name__)
            ui.notification_show(
                t("ui.quickactions.autosave_failed", "Autosave failed."),
                type="warning",
                duration=4,
            )

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
        # Runs when this browser's token arrives (the calc invalidates);
        # once per session.
        token = browser_token()
        if token is None:
            return
        with reactive.isolate():
            if recovery_checked.get():
                return
        try:
            housekeeping()
        except OSError as e:
            logger.warning("quick_actions.housekeeping status=error reason=%s", type(e).__name__)
        try:
            age = autosave_age_seconds(token=token)
            if age is None or age > 24 * 3600:
                return
            if read_autosave(token=token) is None:
                return
        finally:
            recovery_checked.set(True)
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

    # ---- NEWER-BUILD WARNING --------------------------------------------
    # A project from a newer SESPy loads with the data this build does not
    # understand dropped (Project.newer_build). Warn on every load of such a
    # project, whichever path loaded it (upload, recent projects), and clear
    # the warning when a normal project replaces it. Edits keep the same
    # `newer_build` and do not emit project_loaded, so they do not re-raise
    # a toast the user has closed.
    # A language switch changes the text (t() subscribes to the language),
    # so an open warning is re-shown in the new language.
    last_warned: dict = {"info": {}, "loads": None, "text": None}

    @reactive.effect
    def _newer_build_warning():
        info = project_data.get().newer_build
        loads = event_bus.project_loaded.get()
        if not info:
            if last_warned["info"]:
                ui.notification_remove(_NEWER_BUILD_TOAST)
            last_warned.update(info={}, loads=loads, text=None)
            return
        title = t("ui.quickactions.newer_build_title",
                  "This project was saved by a newer SESPy.")
        body = t("ui.quickactions.newer_build_body",
                 "Details: {note}. Data this version does not "
                 "understand was left out, and autosave is off for "
                 "this project. Keep your original file: Save Project "
                 "writes a separate copy in the older format.",
                 note=_newer_build_details(info))
        text = (title, body)
        if (info == last_warned["info"] and loads == last_warned["loads"]
                and text == last_warned["text"]):
            return
        last_warned.update(info=info, loads=loads, text=text)
        ui.notification_show(
            ui.tags.div(ui.tags.strong(title), ui.tags.div(body)),
            type="warning",
            duration=None,
            id=_NEWER_BUILD_TOAST,
        )

    def _newer_build_details(info: dict) -> str:
        parts = []
        if "schema" in info:
            parts.append(t("ui.quickactions.newer_build_schema",
                           "file format {schema}, this version reads up to {schema_max}",
                           schema=info["schema"], schema_max=info["schema_max"]))
        if "min_version" in info:
            parts.append(t("ui.quickactions.newer_build_version",
                           "requires SESPy {min_version} or newer, this is {running}",
                           min_version=info["min_version"], running=info["running"]))
        return "; ".join(parts)

    # ---- SAVE -----------------------------------------------------------
    def _save_filename() -> str:
        stem = f"sespy-project-{datetime.now():%Y%m%d-%H%M%S}"
        # Download handlers run isolated, so this read takes no dependency.
        if project_data.get().newer_build:
            stem += "-older-format"
        return f"{stem}.json"

    @render.download_button(filename=_save_filename)
    def save_project():
        # project_to_bytes calls .with_modified_now() internally; don't double-stamp.
        proj = project_data.get()
        if proj.newer_build:
            ui.notification_show(
                t("ui.quickactions.saved_older_format",
                  "Saved in this version's format. Data from the newer "
                  "SESPy is not in this copy; keep the original file."),
                type="warning",
                duration=8,
            )
        try:
            # A newer-build project is never autosaved, so the autosave on
            # disk belongs to an earlier project; this lossy copy does not
            # make it obsolete.
            if not proj.newer_build:
                clear_autosave(token=browser_token())
        except OSError as e:
            logger.warning("quick_actions.clear_autosave status=error reason=%s", type(e).__name__)
            ui.notification_show(
                t("ui.quickactions.clear_autosave_failed", "Could not clear autosaved data."),
                type="warning",
                duration=4,
            )
        # Emit before yield so the generator's continuation isn't required.
        event_bus.emit_project_saved()
        yield project_to_bytes(proj)

    # ---- RECOVERY ACTION (from the toast button) -----------------------
    @reactive.effect
    @reactive.event(input["__sespy_restore_autosave__"], ignore_init=True)
    def _do_restore():
        recovered = read_autosave(token=browser_token())
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
                token=browser_token(),
            )
        except Exception as e:
            logger.warning("quick_actions.add_recent status=error reason=%s", type(e).__name__)
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
