"""AI-Assisted SES Creation Wizard module.

12-step guided wizard for building a DAPSI(W)R(M) framework. Writes
elements to project_data.isa_data per step (live writes), with a
confirmation modal protecting existing SES data.

Pattern: matches `analysis_intervention.py` for static form-style UI
plus a state machine driven by reactive values.

Pure-data flow definition lives in `sespy/wizard.py` so SP2/SP3/SP4
can swap in their own backends without touching this module.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, replace
from typing import Any, assert_never

from shiny import Inputs, Outputs, Session, module, reactive, render, ui
from shiny.types import SilentException

from ..claude_backend import (    # NOTE: lazy import for runtime use lives in
    ClaudeBackendError,           #       the @reactive.extended_task body (Task 13).
    ClaudeErrorReason,            #       These top-level imports are types only —
    ValidationOutcome,            #       claude_backend itself imports nothing from
    _REASON_TO_I18N,              #       Shiny, and these classes are pure dataclasses
)                                 #       so they're safe to import unconditionally.
from ..constants import ELEMENT_ID_PREFIX
from ..data_structure import (
    Connection,
    ConnectionSuggestion,
    Element,
    IsaData,
    Project,
    WizardState,
)
from ..event_bus import EventBus
from ..i18n import Translator, t
from ..utils import next_id
from ..wizard import (
    ELEMENT_TYPE_MAP,
    REGIONAL_SEAS,
    WIZARD_STEPS,
    suggest_connections,
)


# ---------------------------------------------------------------------------
# SP4 sum-typed status — distinguishes never-called, in-flight, returned-N,
# and failed states that an empty-list reactive would conflate.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _ClaudeIdle:
    pass


@dataclass(frozen=True)
class _ClaudeLoading:
    pass


@dataclass(frozen=True)
class _ClaudeReturned:
    outcome: ValidationOutcome


@dataclass(frozen=True)
class _ClaudeFailed:
    error: ClaudeBackendError


ClaudeBackendStatus = (
    _ClaudeIdle | _ClaudeLoading | _ClaudeReturned | _ClaudeFailed
)


_logger = logging.getLogger(__name__)


def _render_choice_one(step: dict, answers: dict) -> ui.Tag:
    """Render a single-choice step (steps 0, 1)."""
    target = step["target"]
    selected = answers.get(target, "")
    if target == "regional_sea":
        choices = {"": "—"} | {
            slug: data["name"] for slug, data in REGIONAL_SEAS.items()
        }
        return ui.input_radio_buttons(
            f"answer_{target}", t("wizard.regional_sea_label"),
            choices=choices, selected=selected,
        )
    if target == "ecosystem_type":
        # Filter ecosystem types by previously-chosen regional sea.
        regional_sea = answers.get("regional_sea", "")
        eco_list = REGIONAL_SEAS.get(regional_sea, {}).get(
            "ecosystem_types", []
        )
        choices = {"": "—"} | {e: e for e in eco_list}
        return ui.input_radio_buttons(
            f"answer_{target}", t("wizard.ecosystem_type_label"),
            choices=choices, selected=selected,
        )
    return ui.tags.div(f"choice_one renderer doesn't know target {target!r}")


def _render_choice_many(step: dict, answers: dict) -> ui.Tag:
    """Render a multi-select step (steps 2, 3)."""
    target = step["target"]
    selected = answers.get(target, [])
    regional_sea = answers.get("regional_sea", "")
    sea_data = REGIONAL_SEAS.get(regional_sea, {})
    if target == "countries":
        choices = sea_data.get("countries", [])
        label = t("wizard.countries_label")
    elif target == "main_issue":
        choices = sea_data.get("common_issues", [])
        label = t("wizard.main_issue_label")
    else:
        choices = []
        label = ""
    return ui.input_selectize(
        f"answer_{target}", label,
        choices={c: c for c in choices},
        selected=selected,
        multiple=True,
        options={"plugins": ["remove_button"]},
    )


def _render_freeform_multiple(
    step: dict, answers: dict, counts: dict, input,
) -> ui.Tag:
    """Render a list of input_text rows + Add/Remove buttons.

    `counts[target]` is the number of rows currently visible. Pre-populates
    from `answers[target]` (a list[str]) when re-entering a step via Back —
    in that case we ALSO bump counts[target] up to match the saved length.

    `input` is passed in (rather than closure-captured) because this is a
    module-top-scope helper. We use it to snapshot live typing-in-progress
    so that clicking Add/Remove doesn't wipe what the user just typed.
    Without this snapshot, the renderer would re-emit `value=""` for any
    row that hasn't been saved yet, and Shiny would push that empty value
    back to the client, overwriting the typed text — exactly the spec §9
    risk. Reads are wrapped in `reactive.isolate()` so we don't subscribe
    to every entry input (which would cause the renderer to fire on every
    keystroke).
    """
    target = step["target"]
    saved = answers.get(target, [])
    n_rows = max(counts.get(target, 1), len(saved), 1)
    placeholder = t(f"wizard.placeholder_{target}")
    # Snapshot live input values so typing survives Add/Remove re-renders.
    current_values: list[str] = []
    with reactive.isolate():
        for i in range(n_rows):
            try:
                v = input[f"entry_{target}_{i}"]()
                current_values.append(v if v is not None else "")
            except Exception:
                # Input doesn't exist yet (first render) — empty default.
                current_values.append("")
    rows = []
    for i in range(n_rows):
        row_id = f"entry_{target}_{i}"
        # Priority: live typing > saved value > empty.
        value = current_values[i] or (saved[i] if i < len(saved) else "")
        rows.append(
            ui.div(
                ui.input_text(
                    row_id, "",
                    value=value,
                    placeholder=placeholder,
                    width="100%",
                ),
                style="margin-bottom: 4px;",
            )
        )
    rows.append(
        ui.div(
            ui.input_action_button(
                f"add_{target}", t("wizard.add_another"),
                class_="btn btn-sm btn-secondary",
            ),
            ui.input_action_button(
                f"remove_{target}", t("wizard.remove"),
                class_="btn btn-sm btn-secondary",
                style="margin-left: 8px;",
            ),
            style="margin-top: 8px;",
        )
    )
    return ui.div(*rows, id=f"freeform_{target}_container")


def _render_connection_review(suggestions: list) -> ui.Tag:
    """Render the connection-review step (step 11)."""
    if not suggestions:
        return ui.tags.div(
            ui.tags.p(t("wizard.no_suggestions"), class_="text-muted"),
            ui.tags.p(
                "Click Finish to complete the wizard. You can add "
                "connections manually via the Edit Data module.",
                class_="text-muted",
            ),
        )
    # Suggestions present — render an accept/reject table (SP3+ path).
    # Column 1 is the row number ("#"); the table label
    # `wizard.connection_suggestions_table` is rendered as a <caption>
    # above the rows, NOT as the first column header (which would
    # mis-label the row-number column).
    rows = [
        ui.tags.tr(
            ui.tags.th("#"),
            ui.tags.th("Source"),
            ui.tags.th("Target"),
            ui.tags.th(t("wizard.confidence")),
            ui.tags.th(t("wizard.rationale")),
            ui.tags.th(t("wizard.accept")),
        ),
    ]
    for i, s in enumerate(suggestions):
        rows.append(
            ui.tags.tr(
                ui.tags.td(f"{i+1}"),
                ui.tags.td(s.source),
                ui.tags.td(s.target),
                ui.tags.td(f"{s.confidence:.2f}"),
                ui.tags.td(s.rationale),
                ui.tags.td(
                    ui.input_checkbox(f"accept_sp3_{i}", "", value=False),
                ),
            )
        )
    return ui.tags.table(
        ui.tags.caption(t("wizard.connection_suggestions_table")),
        *rows,
        class_="table table-sm",
    )


def _replace_metadata(meta, **overrides):
    """Build a new ProjectMetadata copying meta and overriding listed fields.
    `replace` is imported at module top alongside other stdlib imports."""
    return replace(meta, **overrides)


@module.ui
def ai_isa_wizard_ui() -> ui.Tag:
    """Static UI: card with breadcrumb output + step-render output. The
    nav buttons (Start / Back / Next / Finish) are rendered CONDITIONALLY
    inside `wizard_step_render` so we don't need inline JS to toggle
    visibility (which would require <script>-tags in @render.ui output —
    browsers don't execute innerHTML-inserted <script> tags reliably,
    and Shiny for Python's update pipeline doesn't work around that).

    Each conditionally-rendered button keeps the SAME input id across
    renders (`wizard_start`, `wizard_back`, etc.) so the @reactive.event
    handlers registered at server-init time fire whenever the button
    exists and gets clicked.
    """
    return ui.card(
        ui.card_header(t("wizard.title")),
        ui.div(
            ui.output_ui("wizard_breadcrumb"),    # step pills
            ui.output_ui("wizard_step_render"),   # Start OR step widget + nav buttons
            style="padding: 16px;",
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def ai_isa_wizard_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    # Wizard state — three module-local reactives.
    wizard_step: reactive.Value[int] = reactive.value(0)
    wizard_answers: reactive.Value[dict[str, Any]] = reactive.value({})
    wizard_active: reactive.Value[bool] = reactive.value(False)
    wizard_suggestions_sp3: reactive.Value[list[ConnectionSuggestion]] = reactive.value([])
    # SP4 sum-typed status reactive (alongside wizard_suggestions_sp3 above).
    wizard_claude_status: reactive.Value[ClaudeBackendStatus] = (
        reactive.Value(_ClaudeIdle())
    )
    # One-time per-session consent flag; reset on new session.
    wizard_claude_consent_given: reactive.Value[bool] = reactive.Value(False)
    # Generation counter — incremented on Back-from-11. The extended task
    # captures the generation at start; the observer compares before
    # writing wizard_claude_status. Stale results are silently discarded.
    wizard_claude_generation: reactive.Value[int] = reactive.Value(0)
    # Per-target counts for the freeform_multiple archetype's dynamic UI.
    freeform_counts: reactive.Value[dict[str, int]] = reactive.value({})

    # ---- Placeholders — Tasks 8-14 fill these in ----------------------------

    @reactive.effect
    @reactive.event(input.wizard_start, ignore_init=True)
    def _on_start() -> None:
        if len(project_data.get().isa_data.elements) == 0:
            # Empty project — start directly without modal.
            wizard_answers.set({})
            wizard_step.set(0)
            wizard_active.set(True)
            return
        # Non-empty — open confirmation modal.
        ui.modal_show(
            ui.modal(
                ui.tags.p(t("wizard.modal_body")),
                ui.div(
                    ui.input_action_button(
                        "wizard_replace", t("wizard.replace"),
                        class_="btn btn-warning",
                    ),
                    ui.input_action_button(
                        "wizard_cancel_modal", t("wizard.cancel"),
                        class_="btn btn-secondary",
                    ),
                    style="display: flex; gap: 8px; margin-top: 12px;",
                ),
                title=t("wizard.modal_title"),
                easy_close=False,
                footer=None,
            )
        )

    @reactive.effect
    @reactive.event(input.wizard_replace, ignore_init=True)
    def _on_modal_replace() -> None:
        # Pinned write order — same shape as the live writes in `_on_next`:
        #   build new project → project_data.set → emit signals →
        #   wizard_answers.set / freeform_counts.set → wizard_active /
        #   wizard_step (LAST so wizard_step_render fires once with all
        #   downstream state already settled).
        # Why this order matters: `wizard_active.set(True)` triggers
        # `wizard_step_render`, which depends on `wizard_answers` and
        # `freeform_counts`. Putting wizard_active before the clears
        # would render step 0 against stale answers from the previous
        # session. Putting wizard_active before the emits would let the
        # wizard breadcrumb appear before CLD/autosave see the cleared
        # isa_data, producing a single-frame inconsistent UI.
        current = project_data.get()
        project_data.set(Project(
            metadata=current.metadata,
            isa_data=IsaData(),
        ))
        # Emit BOTH so autosave + CLD see the clearance immediately.
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        wizard_answers.set({})
        freeform_counts.set({})
        wizard_active.set(True)
        wizard_step.set(0)
        ui.modal_remove()

    @reactive.effect
    @reactive.event(input.wizard_cancel_modal, ignore_init=True)
    def _on_modal_cancel() -> None:
        # wizard_active is False by construction (modal only opens when False).
        ui.modal_remove()

    # Add/Remove handlers — one pair per freeform_multiple target.
    _freeform_targets = ["drivers", "activities", "pressures", "states",
                         "impacts", "welfare", "responses"]

    def _make_add_handler(target: str):
        @reactive.effect
        @reactive.event(input[f"add_{target}"], ignore_init=True)
        def _():
            counts = dict(freeform_counts.get())
            counts[target] = counts.get(target, 1) + 1
            freeform_counts.set(counts)
        return _

    def _make_remove_handler(target: str):
        @reactive.effect
        @reactive.event(input[f"remove_{target}"], ignore_init=True)
        def _():
            counts = dict(freeform_counts.get())
            counts[target] = max(counts.get(target, 1) - 1, 1)
            freeform_counts.set(counts)
        return _

    _freeform_handlers = [
        (_make_add_handler(t_), _make_remove_handler(t_))
        for t_ in _freeform_targets
    ]

    @reactive.effect
    @reactive.event(input.wizard_next, ignore_init=True)
    def _on_next() -> None:
        # Guard: on step 11 only Finish is rendered (no Next button), but a
        # stale click event could still arrive — bail before mutating state.
        if wizard_step.get() >= 11:
            return
        step_idx = wizard_step.get()
        step = WIZARD_STEPS[step_idx]
        target = step["target"]
        archetype = step["archetype"]

        # Read answer from inputs (defensive: input may be None).
        if archetype == "choice_one":
            value = (input[f"answer_{target}"]() or "").strip()
            if not value:
                ui.notification_show(
                    t("wizard.validation_error"), type="warning", duration=3,
                )
                return
            answer: Any = value
        elif archetype == "choice_many":
            raw = input[f"answer_{target}"]()
            value_list = list(raw) if raw else []
            if not value_list:
                ui.notification_show(
                    t("wizard.validation_error"), type="warning", duration=3,
                )
                return
            answer = value_list
        elif archetype == "freeform_multiple":
            # Read row count from BOTH freeform_counts (display state)
            # AND len(saved answers) — the renderer expands rows for
            # saved answers without writing back to freeform_counts, so
            # using freeform_counts alone misses Back-navigation rows.
            counts = freeform_counts.get()
            saved = wizard_answers.get().get(target, [])
            n = max(counts.get(target, 1), len(saved))
            raw_entries: list[str] = []
            for i in range(n):
                v = (input[f"entry_{target}_{i}"]() or "").strip()
                if v:
                    raw_entries.append(v)
            if not raw_entries:
                ui.notification_show(
                    t("wizard.validation_error"), type="warning", duration=3,
                )
                return
            # Duplicates are a validation failure per spec §4 — toast and bail.
            if len(raw_entries) != len(set(raw_entries)):
                ui.notification_show(
                    t("wizard.duplicate_error"), type="warning", duration=3,
                )
                return
            answer = raw_entries
        else:
            return  # connection_review reached via _on_finish, not _on_next

        # Write phase — pinned order.
        # Steps 0-1: write to metadata; steps 2-3: ephemeral (no project_data write);
        # steps 4-10: write Element objects to isa_data.
        current = project_data.get()
        if step_idx == 0:
            # regional_sea — metadata write
            new_meta = _replace_metadata(current.metadata, regional_sea=answer)
            new_proj = Project(metadata=new_meta, isa_data=current.isa_data)
            project_data.set(new_proj)
            event_bus.emit_isa_change()
            event_bus.emit_cld_update()
        elif step_idx == 1:
            new_meta = _replace_metadata(current.metadata, ecosystem_type=answer)
            new_proj = Project(metadata=new_meta, isa_data=current.isa_data)
            project_data.set(new_proj)
            event_bus.emit_isa_change()
            event_bus.emit_cld_update()
        elif step_idx in (2, 3):
            pass  # ephemeral; only wizard_answers gets updated below
        elif step_idx in (4, 5, 6, 7, 8, 9, 10):
            elem_type = ELEMENT_TYPE_MAP[target]
            prefix = ELEMENT_ID_PREFIX[target]

            # Idempotent re-write semantics. The R-style "Back doesn't undo
            # writes" rule (spec §4) means that on first Next from this
            # step, we wrote N Elements to isa_data. If the user goes Back
            # and clicks Next AGAIN — without this idempotency block —
            # _on_next would APPEND a fresh batch alongside the previous
            # one, leaving the project with duplicated labels (D001 and
            # D002 both = "Tourism"). To prevent that, before appending
            # we REMOVE this step's previous batch by matching
            # (type == elem_type AND label in prev_answer). Connections
            # referencing those removed ids are also pruned (no
            # dangling endpoints).
            prev_answer = wizard_answers.get().get(target, [])
            if prev_answer == answer:
                # No-change re-Next (user clicked Back, then Next without
                # edits). The existing elements already match what the
                # user wants — skip the rebuild entirely. Rewriting would
                # re-allocate element ids (gap-filling typically yields
                # the SAME id, but the rewrite still emits an
                # intermediate IsaData with the old elements removed) and
                # would prune any external connections (e.g. from PIMS
                # or Edit Data) that reference those ids. Forward-compat
                # for SP3/SP4: once `suggest_connections` returns real
                # suggestions and the user accepts some via Finish, those
                # connections live in `project_data.connections`. A user
                # re-running the wizard later (Replace flow) would clear
                # everything anyway, but a Back+Next mid-wizard with no
                # edits should be a true no-op.
                pass
            else:
                if prev_answer:
                    # Re-Next WITH changes: replace previous batch with
                    # current answer; prune connections to removed ids.
                    elements_to_keep = [
                        e for e in current.isa_data.elements
                        if not (e.type == elem_type and e.label in prev_answer)
                    ]
                    removed_ids = {
                        e.id for e in current.isa_data.elements
                    } - {e.id for e in elements_to_keep}
                    connections_to_keep = [
                        c for c in current.isa_data.connections
                        if c.source not in removed_ids and c.target not in removed_ids
                    ]
                else:
                    # First Next from this step: nothing to remove.
                    elements_to_keep = list(current.isa_data.elements)
                    connections_to_keep = list(current.isa_data.connections)

                existing_ids = [e.id for e in elements_to_keep]
                new_elements = list(elements_to_keep)
                for entry_label in answer:
                    new_id = next_id(existing_ids, prefix)
                    new_elements.append(Element(id=new_id, label=entry_label, type=elem_type))
                    existing_ids.append(new_id)
                new_isa = IsaData(
                    elements=new_elements,
                    connections=connections_to_keep,
                )
                new_proj = Project(metadata=current.metadata, isa_data=new_isa)
                project_data.set(new_proj)
                event_bus.emit_isa_change()
                event_bus.emit_cld_update()

        # Always: update answers, populate suggestions if next step is 11,
        # then advance the step LAST. Pinned order so wizard_step_render
        # fires once with all dependent reactives already at their new
        # values — otherwise setting wizard_step to 11 would re-render
        # _render_connection_review before wizard_suggestions_sp3 has been
        # updated, showing the empty placeholder for one flush before
        # the real suggestions arrive.
        ans = dict(wizard_answers.get())
        ans[target] = answer
        wizard_answers.set(ans)

        if step_idx + 1 == 11:
            wizard_suggestions_sp3.set(suggest_connections(_assemble_wizard_state()))

        wizard_step.set(step_idx + 1)

    def _assemble_wizard_state() -> WizardState:
        """Build a WizardState snapshot from current reactive state."""
        ans = wizard_answers.get()
        isa = project_data.get().isa_data
        return WizardState(
            regional_sea=ans.get("regional_sea", ""),
            ecosystem_type=ans.get("ecosystem_type", ""),
            countries=ans.get("countries", []),
            main_issue=ans.get("main_issue", []),
            elements=list(isa.elements),
        )

    @reactive.extended_task
    async def _claude_task(
        state: WizardState, generation: int,
    ) -> tuple[int, ValidationOutcome]:
        """Capture generation alongside outcome so the observer can discard
        stale results (Back-while-loading race)."""
        # Lazy import inside the task body — runs only when the task is
        # invoked (not at module load).
        from ..claude_backend import suggest_connections as _claude_impl
        outcome = await asyncio.to_thread(_claude_impl, state)
        return (generation, outcome)

    def _trigger_claude_call() -> None:
        """Snapshot state + generation, mark Loading, invoke the task.
        Step assertion guards against stale events (e.g., Back-without-
        dismiss + queued Confirm)."""
        if wizard_step.get() != 11:
            return
        state = _assemble_wizard_state()
        generation = wizard_claude_generation.get()
        wizard_claude_status.set(_ClaudeLoading())
        _claude_task(state, generation)

    @reactive.effect
    def _observe_claude_result() -> None:
        """Maps task outcome into wizard_claude_status. NB: no
        @reactive.event — the dependency on _claude_task.status is
        registered by the unconditional .result() read. Adding
        @reactive.event would break the dependency. The initial-run
        SilentException is expected."""
        try:
            result = _claude_task.result()
        except SilentException:
            # .result() registers the status dependency before raising;
            # re-raise so the effect re-fires on success/error.
            raise
        except (ImportError, ModuleNotFoundError):
            _logger.exception("claude_backend SDK missing")
            ui.notification_show(
                t("wizard.claude_error_sdk_missing"),
                type="warning", duration=8,
            )
            wizard_claude_status.set(_ClaudeIdle())
            return
        except ClaudeBackendError as e:
            _logger.exception("claude backend failed: %s", e.reason)
            i18n_key = _REASON_TO_I18N[e.reason]
            msg = t(i18n_key)
            if e.reason == "status" and e.status_code:
                msg = f"{msg} (HTTP {e.status_code})"
            ui.notification_show(msg, type="warning", duration=6)
            wizard_claude_status.set(_ClaudeFailed(error=e))
            return
        except Exception as e:                            # noqa: BLE001
            # Catch-all: AttributeError if response is None; RuntimeError
            # from asyncio thread oddities; future SDK exceptions outside
            # the documented set. Without this, an unforeseen exception
            # leaves the spinner stuck in Loading forever.
            _logger.exception("unexpected error in claude observer")
            ui.notification_show(
                t("wizard.claude_error_other"),
                type="warning", duration=6,
            )
            wizard_claude_status.set(_ClaudeFailed(error=ClaudeBackendError(
                reason="status",
                text_content=f"unexpected: {type(e).__name__}: {e}",
            )))
            return

        captured_generation, outcome = result
        if captured_generation != wizard_claude_generation.get():
            # Stale result — user clicked Back-from-11 and started fresh.
            # Log so operators can detect Back-during-loading frequency
            # (cost-ceiling honesty: the call was paid, result discarded).
            _logger.info(
                "claude observer: discarded stale result "
                "(captured_generation=%d, current=%d)",
                captured_generation, wizard_claude_generation.get(),
            )
            return
        wizard_claude_status.set(_ClaudeReturned(outcome=outcome))

    @reactive.effect
    @reactive.event(input.wizard_back, ignore_init=True)
    def _on_back() -> None:
        if wizard_step.get() <= 0:
            return  # can't go before step 0
        new_step_idx = wizard_step.get() - 1
        # If returning to a freeform_multiple step, pre-seed
        # freeform_counts[target] = max(current, len(saved)) so that
        # subsequent Add/Remove clicks operate on the correct visible
        # row count. Without this, _render_freeform_multiple still shows
        # the right number of rows (via max(counts, len(saved), 1)),
        # but Add/Remove handlers mutate the stale `counts` value — a
        # 3-entry re-entry would show 3 rows but Remove would clamp
        # `counts[target]` from 1 to 1, leaving the visible 3 rows
        # unchanged from the user's perspective.
        new_step = WIZARD_STEPS[new_step_idx]
        if new_step["archetype"] == "freeform_multiple":
            target = new_step["target"]
            saved = wizard_answers.get().get(target, [])
            counts = dict(freeform_counts.get())
            counts[target] = max(counts.get(target, 1), len(saved), 1)
            freeform_counts.set(counts)
        wizard_step.set(new_step_idx)

    @reactive.effect
    @reactive.event(input.wizard_finish, ignore_init=True)
    def _on_finish() -> None:
        # Hard guard — Finish is only rendered on step 11, but a stale click
        # event could still arrive — bail before mutating state.
        if wizard_step.get() != 11:
            return
        # Collect accepted suggestions (if any). SP1 stub returns [], so the
        # accept_sp3_<i> inputs may not exist; defensive read.
        accepted: list[ConnectionSuggestion] = []
        for i, s in enumerate(wizard_suggestions_sp3.get()):
            try:
                if input[f"accept_sp3_{i}"]():
                    accepted.append(s)
            except Exception:
                pass
        if accepted:
            current = project_data.get()
            new_conns = list(current.isa_data.connections)
            for s in accepted:
                new_conns.append(Connection(
                    source=s.source, target=s.target, polarity=s.polarity,
                ))
            new_isa = IsaData(
                elements=list(current.isa_data.elements),
                connections=new_conns,
            )
            new_proj = Project(metadata=current.metadata, isa_data=new_isa)
            project_data.set(new_proj)
            event_bus.emit_isa_change()
            event_bus.emit_cld_update()
        # Deactivate.
        wizard_active.set(False)
        ui.notification_show(
            "Wizard complete — your SES is ready.",
            type="message", duration=4,
        )

    @output
    @render.ui
    def wizard_breadcrumb() -> ui.Tag:
        """Pill row showing all 12 steps. Inactive state returns empty;
        active state highlights the current step + marks completed."""
        if not wizard_active.get():
            return ui.tags.div()
        current = wizard_step.get()
        pills = []
        for s in WIZARD_STEPS:
            idx = s["step"]
            label = t(f"wizard.step_{idx}_title")
            if idx < current:
                cls = "badge bg-success"  # completed
            elif idx == current:
                cls = "badge bg-primary"  # active
            else:
                cls = "badge bg-secondary"  # future
            pills.append(
                ui.tags.span(
                    f"{idx + 1}. {label}",
                    class_=cls,
                    style="margin: 2px; padding: 4px 8px;",
                )
            )
        return ui.tags.div(
            *pills,
            class_="wizard-breadcrumb",
            style="margin-bottom: 16px; display: flex; flex-wrap: wrap;",
        )

    @output
    @render.ui
    def wizard_step_render() -> ui.Tag:
        """Conditionally render: inactive state shows the Start button;
        active state shows the step widget + Back/Next or Back/Finish.
        Buttons are rendered (not hidden via CSS) so we don't depend on
        innerHTML-inserted <script> execution."""
        active = wizard_active.get()
        if not active:
            return ui.tags.div(
                ui.tags.p(
                    "Click Start Wizard to begin a guided 12-step "
                    "DAPSI(W)R(M) framework setup.",
                    class_="text-muted",
                    style="margin-bottom: 16px;",
                ),
                ui.input_action_button(
                    "wizard_start", t("wizard.start"),
                    class_="btn btn-primary",
                ),
            )
        # Active state — render the current step.
        step_idx = wizard_step.get()
        step = WIZARD_STEPS[step_idx]
        archetype = step["archetype"]
        widget: ui.Tag
        if archetype == "choice_one":
            widget = _render_choice_one(step, wizard_answers.get())
        elif archetype == "choice_many":
            widget = _render_choice_many(step, wizard_answers.get())
        elif archetype == "freeform_multiple":
            widget = _render_freeform_multiple(
                step, wizard_answers.get(), freeform_counts.get(), input,
            )
        elif archetype == "connection_review":
            widget = _render_connection_review(wizard_suggestions_sp3.get())
        else:
            widget = ui.tags.div(f"Unknown archetype: {archetype}")

        # Build nav buttons inline based on which step we're on.
        nav_buttons: list[ui.Tag] = []
        if step_idx > 0:
            nav_buttons.append(ui.input_action_button(
                "wizard_back", t("wizard.back"), class_="btn btn-secondary",
            ))
        if step_idx < 11:
            nav_buttons.append(ui.input_action_button(
                "wizard_next", t("wizard.next"), class_="btn btn-primary",
            ))
        else:  # step_idx == 11
            nav_buttons.append(ui.input_action_button(
                "wizard_finish", t("wizard.finish"), class_="btn btn-success",
            ))

        return ui.tags.div(
            ui.tags.h4(t(f"wizard.step_{step_idx}_title")),
            ui.tags.p(t(f"wizard.step_{step_idx}_question"), class_="text-muted"),
            widget,
            ui.div(
                *nav_buttons,
                style="margin-top: 16px; display: flex; gap: 8px;",
            ),
        )
