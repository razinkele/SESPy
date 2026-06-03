"""Reactive event bus — port of functions/event_bus_setup.R.

The R event bus uses 11 reactiveVal counters as triggers, with emit_*()
functions that increment a counter and on_*() readers that subscribe to it.
This is a deliberately faithful port of that pattern using Shiny for Python's
reactive.value primitive.

The point of this POC is to prove the pattern translates 1:1 — including the
isolate-on-emit discipline that prevented the language-switch infinite loop
documented in app.R:830-835.
"""

from __future__ import annotations

from dataclasses import dataclass

from shiny import reactive


@dataclass
class EventBus:
    """A bag of reactive counters, one per logical event channel.

    The R version stores these inside a reactiveValues list; here each is a
    standalone reactive.value because Shiny for Python does not expose a
    multi-key reactiveValues equivalent at the top level — the difference is
    cosmetic.
    """

    isa_change: reactive.Value[int]
    cld_update: reactive.Value[int]
    analysis_request: reactive.Value[int]
    template_loaded: reactive.Value[int]
    project_loaded: reactive.Value[int]
    project_saved: reactive.Value[int]
    navigation_request: reactive.Value[int]
    language_changed: reactive.Value[int]

    def emit_isa_change(self) -> None:
        with reactive.isolate():
            self.isa_change.set(self.isa_change.get() + 1)

    def emit_cld_update(self) -> None:
        with reactive.isolate():
            self.cld_update.set(self.cld_update.get() + 1)

    def emit_analysis_request(self) -> None:
        with reactive.isolate():
            self.analysis_request.set(self.analysis_request.get() + 1)

    def emit_template_loaded(self) -> None:
        with reactive.isolate():
            self.template_loaded.set(self.template_loaded.get() + 1)

    def emit_project_loaded(self) -> None:
        with reactive.isolate():
            self.project_loaded.set(self.project_loaded.get() + 1)

    def emit_project_saved(self) -> None:
        with reactive.isolate():
            self.project_saved.set(self.project_saved.get() + 1)

    def emit_navigation_request(self) -> None:
        with reactive.isolate():
            self.navigation_request.set(self.navigation_request.get() + 1)

    def emit_language_changed(self) -> None:
        with reactive.isolate():
            self.language_changed.set(self.language_changed.get() + 1)


def create_event_bus() -> EventBus:
    return EventBus(
        isa_change=reactive.value(0),
        cld_update=reactive.value(0),
        analysis_request=reactive.value(0),
        template_loaded=reactive.value(0),
        project_loaded=reactive.value(0),
        project_saved=reactive.value(0),
        navigation_request=reactive.value(0),
        language_changed=reactive.value(0),
    )
