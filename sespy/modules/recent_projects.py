"""Recent Projects panel — list of recently saved/loaded project files
with click-to-load and click-to-remove actions.

R counterpart: `modules/recent_projects_module.R` (~660 LOC). Ours is a
single-pane list of cards: each card shows project name, path, last-used
timestamp, element/connection counts, and Load + Remove buttons.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..data_structure import Project
from ..event_bus import EventBus
from ..i18n import Translator
from ..persistent_storage import load_project
from ..recent_projects import RecentEntry, list_recent, remove_recent


@module.ui
def recent_projects_ui() -> ui.Tag:
    return ui.card(
        ui.card_header("Recent Projects"),
        ui.div(
            ui.p(
                "Files you've saved or loaded recently. Click a project "
                "to load it.",
                class_="text-muted",
            ),
            ui.output_ui("recent_list"),
            style="padding: 24px;",
        ),
        class_="sespy-card",
        full_screen=False,
    )


def _format_when(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return iso_ts
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def _entry_card(idx: int, entry: RecentEntry) -> ui.Tag:
    return ui.tags.div(
        ui.tags.div(
            ui.tags.div(
                ui.tags.h6(entry.name, style="margin: 0 0 4px 0;"),
                ui.tags.div(
                    f"{entry.element_count} elements · "
                    f"{entry.connection_count} connections · "
                    f"{_format_when(entry.last_used)}",
                    class_="text-muted",
                    style="font-size: 0.85rem;",
                ),
                ui.tags.div(
                    entry.path,
                    style=("font-size: 0.75rem; color: var(--salt-gray); "
                           "font-family: var(--font-mono); "
                           "white-space: nowrap; overflow: hidden; "
                           "text-overflow: ellipsis; max-width: 100%;"),
                ),
                style="flex: 1; min-width: 0;",
            ),
            ui.tags.div(
                ui.input_action_button(
                    f"load_recent_{idx}",
                    "Load",
                    class_="btn btn-sm btn-primary",
                ),
                ui.input_action_button(
                    f"remove_recent_{idx}",
                    "Remove",
                    class_="btn btn-sm btn-outline-secondary",
                    style="margin-left: 8px;",
                ),
                style="display: flex; align-items: center;",
            ),
            style=("display: flex; gap: 16px; align-items: center; "
                   "padding: 12px 16px; border: 1px solid var(--mist-light); "
                   "border-radius: 8px; background: white; "
                   "margin-bottom: 8px;"),
        ),
    )


@module.ui
def _placeholder_ui() -> ui.Tag:  # pragma: no cover (unused)
    return ui.tags.div()


@module.server
def recent_projects_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    # Reactive trigger — we don't watch the registry file for changes, so
    # we manually bump this to re-render after save/load/remove.
    refresh: reactive.Value[int] = reactive.value(0)

    @reactive.effect
    def _refresh_on_save():
        # Read the change channels (subscribes to them).
        event_bus.project_loaded.get()
        event_bus.project_saved.get()
        # Bump `refresh` inside `isolate` so the read of `refresh.get()` in
        # this effect's own loop body doesn't create a self-reference cycle.
        # Without this guard, this effect re-fires every time it writes
        # `refresh`, trapping render outputs in `recalculating` forever.
        with reactive.isolate():
            refresh.set(refresh.get() + 1)

    @reactive.calc
    def entries() -> list[RecentEntry]:
        refresh.get()
        return list_recent()

    @output
    @render.ui
    def recent_list():
        rows = entries()
        if not rows:
            return ui.tags.p(
                "No recent projects yet. Save or load one to populate this list.",
                class_="text-muted",
                style="text-align: center; padding: 32px;",
            )
        return ui.tags.div(*[_entry_card(i, e) for i, e in enumerate(rows)])

    # Wire one observer pair per visible row. Since rows change as the
    # registry grows/shrinks, we register up to MAX_RECENT pairs at module
    # init — clicks on later rows are no-ops if there aren't enough rows.
    from ..recent_projects import MAX_RECENT

    for i in range(MAX_RECENT):
        _wire_load(input, i, project_data, event_bus, entries, refresh)
        _wire_remove(input, i, entries, refresh)


def _wire_load(
    input: Inputs,
    idx: int,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    entries_calc,
    refresh: reactive.Value[int],
) -> None:
    @reactive.effect
    @reactive.event(input[f"load_recent_{idx}"], ignore_init=True)
    def _():
        rows = entries_calc()
        if idx >= len(rows):
            return
        entry = rows[idx]
        try:
            proj = load_project(Path(entry.path))
        except (ValueError, OSError) as e:
            ui.notification_show(
                f"Couldn't load {entry.name}: {e}",
                type="warning",
                duration=6,
            )
            return
        project_data.set(proj)
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        event_bus.emit_project_loaded()
        ui.notification_show(
            f"Loaded {entry.name}.",
            type="message",
            duration=3,
        )


def _wire_remove(
    input: Inputs,
    idx: int,
    entries_calc,
    refresh: reactive.Value[int],
) -> None:
    @reactive.effect
    @reactive.event(input[f"remove_recent_{idx}"], ignore_init=True)
    def _():
        rows = entries_calc()
        if idx >= len(rows):
            return
        remove_recent(rows[idx].path)
        with reactive.isolate():
            refresh.set(refresh.get() + 1)
