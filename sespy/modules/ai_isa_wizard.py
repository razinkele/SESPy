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
import dataclasses
import logging
import os
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, assert_never

from shiny import Inputs, Outputs, Session, module, reactive, render, ui
from shiny.module import resolve_id
from shiny.testmode import export_test_values
from shiny.types import SilentException

from .. import r_kb
from ..claude_backend import (  # NOTE: lazy import for runtime use lives in
    _REASON_TO_I18N,  #       claude_backend imports nothing from Shiny,
    ClaudeBackendError,  #       the @reactive.extended_task body (Task 13).
    ValidationOutcome,  #       These top-level imports are types only —
)  #       and these are pure dataclasses, safe to import.
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
from ..kb_suggestions import (
    countries_for_sea,
    country_names_for,
    get_context_suggestions,
)
from ..ui_i18n import Translator, t
from ..utils import next_id
from ..wizard import (
    ELEMENT_TYPE_MAP,
    REGIONAL_SEAS,
    WIZARD_STEPS,
    suggest_connections,
)

if TYPE_CHECKING:
    from ..r_kb import Snapshot

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


def _country_choices(gov: dict | None, sea: str | None) -> dict[str, dict[str, str]]:
    """Step-2 choices from R's governance data (K1): R `get_countries_for_sea`
    split as R's country step does (module :1360-1432) into EU member states
    and non-EU countries, each in `countries_by_sea` order. Values are ISO
    codes, labels `name_en %||% code`. An empty group is left out, as R
    leaves out its heading. Selectize optgroups replace R's headings."""
    eu: dict[str, str] = {}
    non_eu: dict[str, str] = {}
    for c in countries_for_sea(gov, sea):
        (eu if c["eu_member"] else non_eu)[c["code"]] = c["name_en"] or c["code"]
    choices: dict[str, dict[str, str]] = {}
    if eu:
        choices[t("modules.isa.ai_assistant.eu_member_states")] = eu
    if non_eu:
        choices[t("modules.isa.ai_assistant.non_eu_countries")] = non_eu
    return choices


def _render_choice_many(step: dict, answers: dict, *, gov: dict | None = None) -> ui.Tag:
    """Render a multi-select step (steps 2, 3). `gov` is the session's
    governance data; None means the vendored copy."""
    target = step["target"]
    selected = list(answers.get(target, []))
    regional_sea = answers.get("regional_sea", "")
    options: dict[str, Any] = {"plugins": ["remove_button"]}
    if target == "countries":
        if gov is None:
            gov = r_kb.VENDORED.governance()
        choices: Any = _country_choices(gov, regional_sea)
        label = t("wizard.countries_label")
        # selectize rebuilds its items from <option selected> in DOM order,
        # and optgroups pin that order; `items` restores the click order
        # after Back (user settings override the element's).
        options["items"] = selected
    elif target == "main_issue":
        issues = REGIONAL_SEAS.get(regional_sea, {}).get("common_issues", [])
        choices = {c: c for c in issues}
        label = t("wizard.main_issue_label")
    else:
        choices = {}
        label = ""
    return ui.input_selectize(
        f"answer_{target}", label,
        choices=choices,
        selected=selected,
        multiple=True,
        options=options,
    )


def _row_id(gen: int, target: str, i: int) -> str:
    """Freeform row input id (K1). `gen` is the target's visit generation:
    Shiny keeps an input's last value after its element leaves the DOM, so
    a row id from an earlier visit or wizard run must never be reused."""
    return f"entry_{gen}_{target}_{i}"


def _live_row(input, gen: int, target: str, i: int) -> tuple[bool, str]:
    """(exists, value) of a row input of generation `gen`. It exists once
    the client has registered it; an unregistered input raises
    SilentException on read."""
    try:
        v = input[_row_id(gen, target, i)]()
    except SilentException:
        return False, ""
    return True, (v if v is not None else "")


def _row_count(target: str, answers: dict, counts: dict, pending: dict) -> int:
    """max(freeform_counts, len(saved), max(pending index) + 1, 1) (§4.3)."""
    pd = pending.get(target, {})
    return max(counts.get(target, 1), len(answers.get(target, [])),
               (max(pd) + 1) if pd else 0, 1)


def _effective_rows(
    input, gen: int, target: str, answers: dict, counts: dict, pending: dict,
) -> list[tuple[bool, str]]:
    """Per row (exists, value): the pending server write if there is one
    (including ""), else the live input if it exists in this generation
    (even ""), else the saved answer, else ""."""
    saved = answers.get(target, [])
    pd = pending.get(target, {})
    rows: list[tuple[bool, str]] = []
    for i in range(_row_count(target, answers, counts, pending)):
        exists, live = _live_row(input, gen, target, i)
        if i in pd:
            rows.append((exists, pd[i]))
        elif exists:
            rows.append((exists, live))
        else:
            rows.append((exists, saved[i] if i < len(saved) else ""))
    return rows


#: R shows at most 12 suggestions (module :1522).
N_CHIPS = 12

#: R's source badges (module :1532-1559): label and tooltip key per source.
_CHIP_BADGES = {
    "knowledge_db": ("KB", "modules.isa.ai_assistant.from_knowledge_database"),
    "governance": ("GOV", "modules.isa.ai_assistant.governance_suggestion_tooltip"),
    "socioeconomic": ("SE", "modules.isa.ai_assistant.socioeconomic_suggestion_tooltip"),
}


def _chips_caption(sea: str | None, ecosystem: str | None) -> str:
    """R's context caption (module :1574-1582): " (tailored for <sea>",
    then " - <ecosystem>" only if one is set, then ")". "" without a sea.
    The sea name is the English REGIONAL_SEAS name: SESPy has no per-sea
    i18n keys (R's `name_i18n`), a known difference."""
    if not sea:
        return ""
    name = REGIONAL_SEAS.get(sea, {}).get("name", "")
    eco = f" - {ecosystem}" if ecosystem else ""
    return f" ({t('modules.isa.ai_assistant.tailored_for')} {name}{eco})"


def _render_chips(
    target: str, suggestions: list[tuple[str, str]], selected: set[str], caption: str,
) -> ui.Tag:
    """The chip box of a freeform step: up to N_CHIPS buttons
    `chip_{target}_{i}`, each the suggestion name plus R's source badge;
    `chip-on` when an effective row equals the name (stripped, exact)."""
    chips = []
    for i, (name, source) in enumerate(suggestions[:N_CHIPS]):
        badge = None
        if source in _CHIP_BADGES:
            label, key = _CHIP_BADGES[source]
            badge = ui.tags.span(label, class_=f"kb-badge kb-badge-{label}", title=t(key))
        on = name.strip() in selected
        chips.append(ui.input_action_button(
            f"chip_{target}_{i}", ui.TagList(name, badge),
            class_="btn-sm kb-chip " + ("btn-primary chip-on" if on
                                        else "btn-outline-secondary chip-off"),
        ))
    return ui.div(
        ui.tags.p(caption, class_="kb-caption text-muted") if caption else None,
        ui.div(*chips, class_="kb-chips"),
        class_="kb-chipbox",
    )


def _render_freeform_multiple(
    step: dict, answers: dict, counts: dict, input, *,
    gen: int, pending: reactive.Value[dict[str, dict[int, str]]],
) -> ui.Tag:
    """Render a list of input_text rows + Add/Remove buttons.

    Rows are `entry_{gen}_{target}_{i}`; each row's value is its effective
    value (`_effective_rows`). The caller reads `answers`, `counts` and
    `gen` reactively; `pending` and the live inputs are read here under
    `reactive.isolate()`, so typing (or a pending entry being cleared) does
    not re-render the step, while an Add/Remove re-render keeps what the
    user typed. A new visit (new `gen`) has no live inputs and renders from
    the saved answers.
    """
    target = step["target"]
    with reactive.isolate():
        values = [v for _e, v in _effective_rows(
            input, gen, target, answers, counts, pending.get())]
    placeholder = t(f"wizard.placeholder_{target}")
    # Suggestion chips (K1): their own output, so a chip re-render never
    # re-renders the rows (spec §4.3 chip rule 2).
    rows: list[ui.Tag] = [ui.output_ui(f"chips_{target}")]
    for i, value in enumerate(values):
        text = ui.input_text(
            _row_id(gen, target, i), "",
            value=value,
            placeholder=placeholder,
            width="100%",
        )
        # Stable test hook on the <input> itself (ui.input_text takes no
        # attrs; on the wrapper div Playwright's fill() would fail).
        [c for c in text.children
         if getattr(c, "name", None) == "input"][0].attrs["data-row"] = f"{target}_{i}"
        rows.append(ui.div(text, style="margin-bottom: 4px;"))
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
    # Ids inside a module's @render.ui are not namespaced automatically.
    return ui.div(*rows, id=resolve_id(f"freeform_{target}_container"))


ROW_JS = r"""
// Feedback #17: keep a suggestion row's text in step with its polarity
// switch and reverse control. Delegated, so it survives re-renders of the
// step (a <script> inside the rendered step would not run).
document.addEventListener('change', function (e) {
  var row = e.target && e.target.closest ? e.target.closest('tr.wiz-sugg') : null;
  if (!row) return;
  var pos = row.querySelector('.wiz-pol input').checked;
  var sw = row.querySelector('.wiz-swap input').checked;
  var d = row.dataset;
  row.querySelector('.wiz-pol-label').textContent = pos ? '+' : '−';
  row.querySelector('.wiz-src').textContent = sw ? d.toId : d.fromId;
  row.querySelector('.wiz-tgt').textContent = sw ? d.fromId : d.toId;
  var changed = sw || (pos !== (d.pol === '+'));
  var from = sw ? d.toLabel : d.fromLabel, to = sw ? d.fromLabel : d.toLabel;
  row.querySelector('.wiz-rat').textContent =
    changed ? from + ' ' + (pos ? d.vpos : d.vneg) + ' ' + to : d.rat;
});
"""


def _render_suggestions_table(
    items: list[ConnectionSuggestion],
    *,
    prefix: str,
    title: str,
    note: str | None = None,
    labels: dict[str, str] | None = None,
    rule_based: bool = False,
) -> ui.Tag:
    """Render a suggestions table with accept-checkboxes.

    `rule_based` (K1b) adds R's Strength and Confidence (1-5) columns; the
    Claude table keeps its single 0..1 column, labelled Score.

    `note` (feedback #16) is shown under the title: what the Confidence
    column is based on, which differs between the rule-based and Claude
    tables.

    `prefix` is the input-id prefix ('accept_sp3_' or 'accept_sp4_').
    Extracted from the existing inline rendering in
    _render_connection_review (SP1) to support the SP4 two-table flow.
    Column order: # | Source | Target | Polarity | Reverse | Strength |
    Confidence | Rationale | Accept for the rule-based table; the Claude
    table has a single Score column in place of Strength and Confidence.
    """
    rows = []
    rows.append(ui.tags.tr(
        ui.tags.th("#"),
        ui.tags.th(t("wizard.source")),
        ui.tags.th(t("wizard.target")),
        ui.tags.th(t("wizard.polarity")),
        ui.tags.th(t("wizard.reverse")),
        *([ui.tags.th(t("wizard.col_strength")),
           ui.tags.th(t("wizard.col_confidence"))] if rule_based
          else [ui.tags.th(t("wizard.col_score"))]),
        ui.tags.th(t("wizard.rationale")),
        ui.tags.th(t("wizard.accept")),
    ))
    # Per-row polarity switch and reverse control (feedback #17, ported from
    # R's connection review). Ids: pol_sp3_0, swap_sp3_0 next to accept_sp3_0.
    tag = prefix.removeprefix("accept_")
    labels = labels or {}
    for i, s in enumerate(items):
        rows.append(ui.tags.tr(
            ui.tags.td(str(i + 1)),
            ui.tags.td(s.source, class_="wiz-src"),
            ui.tags.td(s.target, class_="wiz-tgt"),
            ui.tags.td(
                ui.tags.span(s.polarity if s.polarity == "+" else "\u2212",
                             class_="wiz-pol-label"),
                ui.input_switch(f"pol_{tag}{i}", None, value=s.polarity == "+"),
                class_="wiz-pol",
            ),
            ui.tags.td(ui.input_checkbox(f"swap_{tag}{i}", "\u21c4", value=False),
                       class_="wiz-swap"),
            *([ui.tags.td(t(f"strength.{s.strength}"), class_="wiz-str"),
               ui.tags.td(str(s.confidence), class_="wiz-conf")] if rule_based
              else [ui.tags.td(f"{s.relevance:.2f}")]),
            ui.tags.td(s.rationale, class_="wiz-rat"),
            ui.tags.td(ui.input_checkbox(f"{prefix}{i}", "", value=False)),
            class_="wiz-sugg",
            **{
                "data-from-id": s.source, "data-to-id": s.target,
                "data-from-label": labels.get(s.source, s.source),
                "data-to-label": labels.get(s.target, s.target),
                "data-pol": s.polarity, "data-rat": s.rationale,
                "data-vpos": t("wizard.verb_positive"),
                "data-vneg": t("wizard.verb_negative"),
            },
        ))
    return ui.tags.div(
        ui.tags.h6(title),
        ui.tags.p(note, class_="text-muted", style="font-size: 0.85rem;") if note else None,
        ui.tags.table(*rows, class_="table table-sm"),
    )


def _render_connection_review(
    sp3: list[ConnectionSuggestion],
    sp4_status: ClaudeBackendStatus,
    claude_available: bool,
    labels: dict[str, str] | None = None,
) -> ui.Tag:
    """Render the connection-review step (step 11).

    Shows SP3 rule-based table always (when suggestions or Claude path
    exists); SP4 Claude table below the Generate button after success.
    Empty-state branch preserves the SP1 'no_suggestions' message when
    SP3 is empty AND no Claude path.
    """
    parts: list[ui.Tag] = []

    # Empty-state branch: preserve the friendly SP1 message when there's
    # nothing to show AND no Claude path.
    if not sp3 and not claude_available:
        parts.append(ui.tags.div(
            ui.tags.p(t("wizard.no_suggestions"), class_="text-muted"),
            ui.tags.p(
                "Click Finish to complete the wizard. You can add "
                "connections manually via the Edit Data module.",
                class_="text-muted",
            ),
        ))
        return ui.tags.div(*parts)

    # SP3 table — always shown (even if empty, for side-by-side layout).
    parts.append(_render_suggestions_table(
        sp3, prefix="accept_sp3_",
        title=t("wizard.suggestions_rule_based_n").format(n=len(sp3)),
        note=t("wizard.confidence_help_rules") if sp3 else None,
        labels=labels, rule_based=True,
    ))

    # Generate-with-Claude button — only when env key set + not disabled.
    if claude_available:
        match sp4_status:
            case _ClaudeLoading():
                parts.append(ui.tags.div(
                    ui.tags.span(class_="spinner-border spinner-border-sm me-2"),
                    t("wizard.claude_generating"),
                    class_="my-3 text-muted",
                ))
            case _ClaudeFailed(
                error=ClaudeBackendError(reason="rate_limit", retry_after=ra)
            ) if ra is not None and ra > 0:
                # Positive Retry-After only — zero/absent means "retry now".
                parts.append(ui.input_action_button(
                    "wizard_claude_generate",
                    t("wizard.claude_retry_after").format(s=int(ra)),
                    class_="btn btn-outline-primary my-3 disabled",
                ))
            case _ClaudeIdle() | _ClaudeReturned() | _ClaudeFailed():
                parts.append(ui.input_action_button(
                    "wizard_claude_generate",
                    t("wizard.claude_generate_button"),
                    class_="btn btn-outline-primary my-3",
                ))
            case _ as unreachable:
                assert_never(unreachable)

    # SP4 table — render based on status.
    match sp4_status:
        case _ClaudeReturned(outcome=outcome):
            if outcome.suggestions:
                if outcome.raw_count > len(outcome.suggestions):
                    parts.append(ui.tags.div(
                        t("wizard.claude_drops_badge").format(
                            kept=len(outcome.suggestions),
                            raw=outcome.raw_count,
                            dropped=outcome.raw_count - len(outcome.suggestions),
                        ),
                        class_="alert alert-info py-1",
                    ))
                parts.append(_render_suggestions_table(
                    outcome.suggestions, prefix="accept_sp4_",
                    title=t("wizard.suggestions_claude_n").format(
                        n=len(outcome.suggestions)
                    ),
                    note=t("wizard.confidence_help_claude"),
                    labels=labels,
                ))
            else:
                parts.append(ui.tags.div(
                    t("wizard.claude_returned_zero"),
                    class_="text-muted my-3",
                ))
        case _ClaudeIdle() | _ClaudeLoading() | _ClaudeFailed():
            pass
        case _ as unreachable:
            assert_never(unreachable)

    return ui.tags.div(*parts)


def _dedup_accepted(
    accepted: list[ConnectionSuggestion],
) -> tuple[list[ConnectionSuggestion], int, int]:
    """Pure-data dedup helper extracted from _on_finish.

    Dedups by (source, target, polarity) — different polarity for the
    same edge is NOT a duplicate. On relevance tie, the FIRST entry
    wins (iteration order; in _on_finish, SP3 is iterated first so SP3
    wins ties).

    Returns (deduped_list, discarded_count, overwritten_count).
    Extracted so tests/test_wizard.py can exercise the exact same
    algorithm production code uses — NOT a copy.
    """
    seen: dict[tuple[str, str, str], ConnectionSuggestion] = {}
    discarded = 0
    overwritten = 0
    for s in accepted:
        key = (s.source, s.target, s.polarity)
        prev = seen.get(key)
        if prev is None:
            seen[key] = s
        elif s.relevance > prev.relevance:
            seen[key] = s
            overwritten += 1
        else:
            discarded += 1
    return list(seen.values()), discarded, overwritten


def _replace_metadata(meta, **overrides):
    """Build a new ProjectMetadata copying meta and overriding listed fields.
    `replace` is imported at module top alongside other stdlib imports."""
    return replace(meta, **overrides)


def _nav_button(nav_id: str, label: str, cls: str) -> ui.Tag:
    """A button that opens another page by clicking its sidebar nav button,
    so the sidebar highlight and the page switch stay in one place."""
    return ui.tags.button(
        label, type="button", class_=f"btn {cls}",
        onclick=f"document.getElementById('sespy_nav_{nav_id}').click()",
    )


def _render_completion(n_elements: int, n_connections: int) -> ui.Tag:
    """Shown after Finish instead of the fresh-start screen (feedback #18)."""
    return ui.tags.div(
        ui.tags.h4(t("wizard.complete_title")),
        ui.tags.p(t("wizard.complete_body", elements=n_elements,
                    connections=n_connections)),
        ui.div(
            _nav_button("cld", t("nav.cld"), "btn-primary"),
            _nav_button("entry", t("nav.entry"), "btn-outline-primary"),
            ui.input_action_button(
                "wizard_start", t("wizard.start_over"),
                class_="btn btn-outline-danger",
            ),
            style="margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap;",
        ),
        class_="wizard-complete",
    )


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
        ui.tags.script(ROW_JS),
        # Shiny input wrappers default to a 300px width; inside the review
        # table they must shrink to the control.
        ui.tags.style(
            "tr.wiz-sugg .shiny-input-container, tr.wiz-sugg .form-group"
            " { width: auto !important; margin: 0; }"
            " tr.wiz-sugg td.wiz-pol { white-space: nowrap; }"
            " tr.wiz-sugg td.wiz-pol .shiny-input-container"
            " { display: inline-block; vertical-align: middle; margin-left: 6px; }"
            " tr.wiz-sugg .form-check { margin: 0; min-height: 0; }"
            " .kb-chipbox { margin-bottom: 10px; }"
            " .kb-caption { font-size: 0.85rem; margin-bottom: 4px; }"
            " .kb-chips .kb-chip { margin: 3px; }"
            " .kb-badge { font-size: 0.65em; vertical-align: super; margin-left: 3px;"
            " padding: 1px 4px; border-radius: 3px; cursor: help; color: #fff; }"
            " .kb-badge-KB { background: #0aa2c0; } .kb-badge-GOV { background: #b8860b; }"
            " .kb-badge-SE { background: #198754; }"
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
    snapshot: Snapshot | None = None,
    reference_reads: reactive.Value[frozenset[str]] | None = None,
) -> None:
    # K1: `snapshot` / `reference_reads` are the session's reference data and
    # the files it read (suggestions and countries, Tasks 11-13). Both
    # optional: MosaicSES and the unit tests mount the wizard without them.
    snap = snapshot if snapshot is not None else r_kb.VENDORED

    def _gov() -> dict:
        return snap.governance()

    # Wizard state — three module-local reactives.
    wizard_step: reactive.Value[int] = reactive.value(0)
    wizard_answers: reactive.Value[dict[str, Any]] = reactive.value({})
    wizard_active: reactive.Value[bool] = reactive.value(False)
    # True after Finish until the wizard is started again: the idle screen
    # then shows the completion panel, not the fresh-start screen (live
    # feedback #18 — a finished SES looked like a blank start, and its only
    # button led to the destructive replace modal).
    wizard_completed: reactive.Value[bool] = reactive.value(False)
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
    _freeform_targets = ["drivers", "activities", "pressures", "states",
                         "impacts", "welfare", "responses"]
    # K1 pending overlay (spec §4.3): every server-issued row write (the Add
    # tombstone now; chip fills and deselects in Task 13), per target and
    # row index, until the client echoes it. It wins over the live input.
    pending: reactive.Value[dict[str, dict[int, str]]] = reactive.value({})
    # Per-target visit generation in the row ids, bumped on every entry to
    # the step and on Replace, so stale inputs from an earlier visit or run
    # never resurface.
    gen: reactive.Value[dict[str, int]] = reactive.value(
        {t_: 0 for t_ in _freeform_targets})

    def _gen_of(target: str) -> int:
        return gen.get().get(target, 0)

    def effective_rows(target: str) -> list[tuple[bool, str]]:
        """(exists, value) per row: pending, else live-if-exists, else saved."""
        return _effective_rows(input, _gen_of(target), target, wizard_answers.get(),
                               freeform_counts.get(), pending.get())

    def row_count(target: str) -> int:
        return _row_count(target, wizard_answers.get(), freeform_counts.get(),
                          pending.get())

    def _set_pending(target: str, i: int, value: str) -> None:
        p = dict(pending.get())
        p[target] = dict(p.get(target, {}))
        p[target][i] = value
        pending.set(p)

    def _drop_pending(target: str) -> None:
        p = dict(pending.get())
        if p.pop(target, None) is not None:
            pending.set(p)

    def _bump_gen(targets: list[str]) -> None:
        """New visit for `targets`: fresh row ids, and their pending dropped
        (so a server write from the previous visit never leaks into it)."""
        g = dict(gen.get())
        p = dict(pending.get())
        for t_ in targets:
            g[t_] = g.get(t_, 0) + 1
            p.pop(t_, None)
        gen.set(g)
        pending.set(p)

    def _enter_step(idx: int) -> None:
        """Move to step `idx` (Next, Back, Skip); entering a freeform step
        starts a new visit."""
        new_step = WIZARD_STEPS[idx]
        if new_step["archetype"] == "freeform_multiple":
            _bump_gen([new_step["target"]])
        wizard_step.set(idx)

    # ---- Placeholders — Tasks 8-14 fill these in ----------------------------

    @reactive.effect
    @reactive.event(input.wizard_start, ignore_init=True)
    def _on_start() -> None:
        if len(project_data.get().isa_data.elements) == 0:
            # Empty project — start directly without modal.
            wizard_answers.set({})
            wizard_completed.set(False)
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
                        class_="btn btn-danger",
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
        project_data.set(current.replace(isa_data=IsaData()))
        # Emit BOTH so autosave + CLD see the clearance immediately.
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        wizard_answers.set({})
        freeform_counts.set({})
        pending.set({})
        _bump_gen(_freeform_targets)   # rows of the previous run never resurface
        wizard_completed.set(False)
        wizard_active.set(True)
        wizard_step.set(0)
        ui.modal_remove()

    @reactive.effect
    @reactive.event(input.wizard_cancel_modal, ignore_init=True)
    def _on_modal_cancel() -> None:
        # wizard_active is False by construction (modal only opens when False).
        ui.modal_remove()

    # Add/Remove handlers — one pair per freeform_multiple target. Both work
    # on the effective row count (§4.3).
    def _make_add_handler(target: str):
        @reactive.effect
        @reactive.event(input[f"add_{target}"], ignore_init=True)
        def _():
            n = row_count(target)
            counts = dict(freeform_counts.get())
            counts[target] = n + 1
            # Tombstone: index n may still hold text from before a Remove in
            # this generation; the re-added row starts blank.
            exists, live = _live_row(input, _gen_of(target), target, n)
            if exists and live:
                _set_pending(target, n, "")
            freeform_counts.set(counts)
        return _

    def _make_remove_handler(target: str):
        @reactive.effect
        @reactive.event(input[f"remove_{target}"], ignore_init=True)
        def _():
            new = max(row_count(target) - 1, 1)
            counts = dict(freeform_counts.get())
            counts[target] = new
            p = dict(pending.get())
            if target in p:
                p[target] = {k: v for k, v in p[target].items() if k < new}
                pending.set(p)
            freeform_counts.set(counts)
        return _

    # Clearing: drop a pending entry as soon as the live input of the current
    # generation reports the same value (the client echoed the server write),
    # so pending does not mask what the user types next.
    def _make_clear_effect(target: str):
        @reactive.effect
        def _():
            pd = pending.get().get(target, {})
            if not pd:
                return
            g = _gen_of(target)
            done = [k for k, v in pd.items() if _live_row(input, g, target, k) == (True, v)]
            if done:
                with reactive.isolate():
                    p = dict(pending.get())
                p[target] = {k: v for k, v in p.get(target, {}).items() if k not in done}
                pending.set(p)
        return _

    _freeform_handlers = [
        (_make_add_handler(t_), _make_remove_handler(t_), _make_clear_effect(t_))
        for t_ in _freeform_targets
    ]

    def _is_current_step(target: str) -> bool:
        """True when the wizard is active and on the step whose target is
        `target`. Per-step buttons (Skip; Task 13's chips) act only then, so a
        stale click from an earlier render, or one after Finish, is ignored."""
        return (wizard_active.get()
                and WIZARD_STEPS[wizard_step.get()]["target"] == target)

    # Skip buttons on steps 2-3 (R's "Skip this question"): record [] and
    # advance, like an empty Next.
    def _make_skip_handler(target: str):
        @reactive.effect
        @reactive.event(input[f"skip_{target}"], ignore_init=True)
        def _():
            if not _is_current_step(target):
                return
            ans = dict(wizard_answers.get())
            ans[target] = []
            wizard_answers.set(ans)
            _enter_step(wizard_step.get() + 1)
        return _

    _skip_handlers = [_make_skip_handler(t_) for t_ in ("countries", "main_issue")]

    # ---- K1 suggestion chips (spec §4.3, chip rules 1-7) --------------------

    @reactive.calc
    def _step_suggestions() -> list[tuple[str, str]]:
        """The current freeform step's suggestions, R
        `get_context_suggestions(..., return_sources = TRUE)` over the
        session's reference data; [] off steps 4-10. A calc, so the
        pipeline runs once per step change, not per output or keystroke."""
        if not wizard_active.get():
            return []
        step = WIZARD_STEPS[wizard_step.get()]
        if step["archetype"] != "freeform_multiple":
            return []
        ans = wizard_answers.get()
        r_kb.add_reads(reference_reads, (r_kb.KB_NAME, r_kb.GOVERNANCE_NAME))
        return get_context_suggestions(
            snap.kb(), _gov(), step["target"],
            ans.get("regional_sea") or None, ans.get("ecosystem_type") or None,
            list(ans.get("main_issue") or []), list(ans.get("countries") or []),
        )

    def _make_chips_output(target: str):
        @output(id=f"chips_{target}")
        @render.ui
        def _():
            # Only the current step's chips render (and compute suggestions).
            if not _is_current_step(target):
                return ui.TagList()
            suggestions = _step_suggestions()
            if not suggestions:
                return ui.TagList()          # R shows no block without suggestions
            selected = {v.strip() for _e, v in effective_rows(target) if v.strip()}
            ans = wizard_answers.get()
            caption = _chips_caption(ans.get("regional_sea") or None,
                                     ans.get("ecosystem_type") or None)
            return _render_chips(target, suggestions, selected, caption)
        return _

    def _make_chip_handler(target: str, i: int):
        @reactive.effect
        @reactive.event(input[f"chip_{target}_{i}"], ignore_init=True)
        def _():
            if not _is_current_step(target):
                return
            suggestions = _step_suggestions()[:N_CHIPS]   # the list at click time
            if i >= len(suggestions):
                return
            text = suggestions[i][0].strip()
            g = _gen_of(target)
            rows = effective_rows(target)
            hits = [k for k, (_e, v) in enumerate(rows) if v.strip() == text]
            empty = None if hits else next(
                (k for k, (_e, v) in enumerate(rows) if not v.strip()), None)
            # A click that would write in place into a row the client has not
            # bound yet is ignored: no update_text can reach it, and a pending
            # value the client never shows would mask what it echoes and what
            # the user types next. The usual case is a double click: click 2
            # arrives before the row added by click 1 is bound, so it counts
            # as the same click (final review F2). Adding a new row is not
            # affected; its render carries the pending value.
            in_place = hits or ([] if empty is None else [empty])
            if any(not rows[k][0] for k in in_place):
                return
            if hits:
                # Rule 5: blank every matching row in place (R's Filter).
                for k in hits:
                    _set_pending(target, k, "")
                    ui.update_text(_row_id(g, target, k), value="")
                return
            # Rule 4: the first empty row, else a new row.
            if empty is not None:
                _set_pending(target, empty, text)
                ui.update_text(_row_id(g, target, empty), value=text)
            else:
                n = len(rows)
                _set_pending(target, n, text)
                counts = dict(freeform_counts.get())
                counts[target] = n + 1
                freeform_counts.set(counts)
        return _

    _chip_outputs = [_make_chips_output(t_) for t_ in _freeform_targets]
    _chip_handlers = [_make_chip_handler(t_, i)
                      for t_ in _freeform_targets for i in range(N_CHIPS)]

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
            # Steps 2-3 are skippable (K1, as in R): an empty selection is
            # accepted and records []. The input is unset when nothing was
            # ever selected, and reading it then raises SilentException.
            try:
                raw = input[f"answer_{target}"]()
            except SilentException:
                raw = None
            answer = list(raw) if raw else []
        elif archetype == "freeform_multiple":
            # Effective values over the effective row count (K1 §4.3):
            # pending server writes win, then this visit's live inputs, then
            # the saved answers (rows the client has not echoed yet).
            raw_entries = [v.strip() for _e, v in effective_rows(target) if v.strip()]
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
            new_proj = current.replace(metadata=new_meta)
            project_data.set(new_proj)
            event_bus.emit_isa_change()
            event_bus.emit_cld_update()
        elif step_idx == 1:
            new_meta = _replace_metadata(current.metadata, ecosystem_type=answer)
            new_proj = current.replace(metadata=new_meta)
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
                new_proj = current.replace(isa_data=new_isa)
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
        if step_idx == 0 and ans.get("countries"):
            # Sea change after Back: keep only codes the new sea offers,
            # in their selected order.
            valid = {c["code"] for c in countries_for_sea(_gov(), answer)}
            ans["countries"] = [c for c in ans["countries"] if c in valid]
        wizard_answers.set(ans)
        if archetype == "freeform_multiple":
            # Only after a successful write: a failed Next keeps pending.
            _drop_pending(target)

        if step_idx + 1 == 11:
            # Provenance (D9): the connection DB feeds these suggestions.
            r_kb.add_reads(reference_reads, (r_kb.CONNECTION_DB_NAME,))
            wizard_suggestions_sp3.set(
                suggest_connections(_assemble_wizard_state(), snap))

        _enter_step(step_idx + 1)

    def _assemble_wizard_state() -> WizardState:
        """Build a WizardState snapshot from current reactive state."""
        ans = wizard_answers.get()
        isa = project_data.get().isa_data
        countries = list(ans.get("countries", []))
        return WizardState(
            regional_sea=ans.get("regional_sea", ""),
            ecosystem_type=ans.get("ecosystem_type", ""),
            countries=countries,
            main_issue=ans.get("main_issue", []),
            elements=list(isa.elements),
            country_names=country_names_for(_gov(), countries),
        )

    # Test-mode only (no-op otherwise): tests assert through these, not ids.
    export_test_values(
        step=wizard_step.get,
        answers=wizard_answers.get,
        wizard_state=lambda: dataclasses.asdict(_assemble_wizard_state()),
        # String keys: orjson rejects int keys.
        pending=lambda: {t_: {str(i): v for i, v in d.items()}
                         for t_, d in pending.get().items()},
        gen=lambda: dict(gen.get()),
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
    @reactive.event(input.wizard_claude_generate, ignore_init=True)
    def _on_claude_generate_clicked() -> None:
        """First-stage handler: in-flight guard, then consent or call."""
        # In-flight guard — protects against rapid-clicks during Loading.
        if isinstance(wizard_claude_status.get(), _ClaudeLoading):
            return
        if wizard_claude_consent_given.get():
            # Already consented — go straight to call.
            _trigger_claude_call()
            return
        # First click — show consent modal.
        ui.modal_show(ui.modal(
            ui.tags.p(t("wizard.claude_consent_body")),
            ui.tags.ul(
                ui.tags.li(t("wizard.claude_consent_field_sea")),
                ui.tags.li(t("wizard.claude_consent_field_ecosystem")),
                ui.tags.li(t("wizard.claude_consent_field_countries")),
                ui.tags.li(t("wizard.claude_consent_field_issues")),
                ui.tags.li(t("wizard.claude_consent_field_elements")),
            ),
            ui.tags.p(t("wizard.claude_consent_privacy_note")),
            title=t("wizard.claude_consent_title"),
            footer=ui.tags.div(
                ui.input_action_button(
                    "wizard_claude_consent_cancel",
                    t("wizard.claude_consent_cancel"),
                    class_="btn btn-secondary me-2",
                ),
                ui.input_action_button(
                    "wizard_claude_consent_confirm",
                    t("wizard.claude_consent_confirm"),
                    class_="btn btn-primary",
                ),
            ),
            easy_close=False,
        ))


    @reactive.effect
    @reactive.event(input.wizard_claude_consent_cancel, ignore_init=True)
    def _on_consent_cancel() -> None:
        ui.modal_remove()


    @reactive.effect
    @reactive.event(input.wizard_claude_consent_confirm, ignore_init=True)
    def _on_consent_confirm() -> None:
        # Defensive guard against stale Shiny event replay on reconnect.
        if isinstance(wizard_claude_status.get(), _ClaudeLoading):
            ui.modal_remove()
            return
        wizard_claude_consent_given.set(True)
        ui.modal_remove()
        _trigger_claude_call()

    @reactive.effect
    @reactive.event(input.wizard_back, ignore_init=True)
    def _on_back() -> None:
        if wizard_step.get() == 11:
            # Defensively dismiss any open consent modal.
            ui.modal_remove()
            wizard_claude_status.set(_ClaudeIdle())
            # Bump generation; in-flight task results will fail the staleness check.
            wizard_claude_generation.set(
                wizard_claude_generation.get() + 1
            )
            # wizard_suggestions_sp3 will be repopulated on the next 10->11.
        if wizard_step.get() <= 0:
            return  # can't go before step 0
        new_step_idx = wizard_step.get() - 1
        # If returning to a freeform_multiple step, pre-seed
        # freeform_counts[target] = max(current, len(saved)). Since K1 the
        # renderer and Add/Remove all use the effective row count
        # (`row_count`, which already includes len(saved)), so this only
        # keeps freeform_counts in step with what is shown (1.15.1 shape).
        new_step = WIZARD_STEPS[new_step_idx]
        if new_step["archetype"] == "freeform_multiple":
            target = new_step["target"]
            saved = wizard_answers.get().get(target, [])
            counts = dict(freeform_counts.get())
            counts[target] = max(counts.get(target, 1), len(saved), 1)
            freeform_counts.set(counts)
        # A new visit renders from the saved answers: text typed on the step
        # and never saved by Next is discarded (K1 behaviour change).
        _enter_step(new_step_idx)

    def _apply_row_edits(s: ConnectionSuggestion, tag: str, i: int) -> ConnectionSuggestion:
        """A row's polarity switch and reverse control (feedback #17). An
        input the browser never sent keeps the suggestion as it was."""
        pol_in, swap_in = input[f"pol_{tag}_{i}"], input[f"swap_{tag}_{i}"]
        polarity = s.polarity
        if pol_in.is_set():
            polarity = "+" if pol_in() else "-"
        source, target = s.source, s.target
        if swap_in.is_set() and swap_in():
            source, target = target, source
        if (source, target, polarity) == (s.source, s.target, s.polarity):
            return s
        return dataclasses.replace(s, source=source, target=target, polarity=polarity)

    @reactive.effect
    @reactive.event(input.wizard_finish, ignore_init=True)
    def _on_finish() -> None:
        # Hard guard — Finish is only rendered on step 11, but a stale click
        # event could still arrive — bail before mutating state.
        if wizard_step.get() != 11:
            return

        accepted: list[ConnectionSuggestion] = []
        read_failures = 0

        # Read SP3 acceptances first (so ties favor SP3 in dedup).
        for i, s in enumerate(wizard_suggestions_sp3.get()):
            try:
                if input[f"accept_sp3_{i}"]():
                    accepted.append(_apply_row_edits(s, "sp3", i))
            except SilentException:
                raise   # Shiny session disconnect — propagate, don't swallow.
            except KeyError as e:
                _logger.warning("accept checkbox sp3_%d not found: %s", i, e)
                read_failures += 1

        # Read SP4 acceptances if any.
        sp4_outcome = (
            wizard_claude_status.get().outcome
            if isinstance(wizard_claude_status.get(), _ClaudeReturned)
            else None
        )
        if sp4_outcome:
            for i, s in enumerate(sp4_outcome.suggestions):
                try:
                    if input[f"accept_sp4_{i}"]():
                        accepted.append(_apply_row_edits(s, "sp4", i))
                except SilentException:
                    raise
                except KeyError as e:
                    _logger.warning("accept checkbox sp4_%d not found: %s", i, e)
                    read_failures += 1

        if read_failures:
            # Deliberate abort-and-retry semantics: if ANY checkbox read
            # fails, we surface the toast and require the user to click
            # Finish again. Rationale: a failed read indicates a transient
            # render/session issue; partial commit could lose the user's
            # accept clicks they THINK they made (the failed-to-read
            # checkbox might have been ON). Aborting protects against
            # silent partial-acceptance. The trade-off: if the same
            # transient race recurs on the next Finish click, the user
            # gets stuck — but in practice render races are rare and
            # idempotent retries succeed.
            ui.notification_show(
                t("wizard.read_failures_n").format(n=read_failures),
                type="warning", duration=6,
            )
            return

        # Delegate dedup to the shared helper. This keeps the production
        # code AND the unit tests in tests/test_wizard.py exercising the
        # exact same algorithm — not a copy.
        final, discarded, overwritten = _dedup_accepted(accepted)

        if discarded or overwritten:
            ui.notification_show(
                t("wizard.duplicates_resolved_n").format(
                    discarded=discarded, overwritten=overwritten,
                ),
                type="message", duration=4,
            )

        if final:
            current = project_data.get()
            new_conns = list(current.isa_data.connections)
            for s in final:
                new_conns.append(Connection(
                    source=s.source, target=s.target, polarity=s.polarity,
                    strength=s.strength, confidence=s.confidence,
                ))
            new_isa = IsaData(
                elements=list(current.isa_data.elements),
                connections=new_conns,
            )
            new_proj = current.replace(isa_data=new_isa)
            project_data.set(new_proj)
            event_bus.emit_isa_change()
            event_bus.emit_cld_update()
        # Deactivate; the idle screen now shows the completion panel.
        wizard_completed.set(True)
        wizard_active.set(False)
        ui.notification_show(
            t("wizard.complete_title"),
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
        if not active and wizard_completed.get():
            # Read project_data only in this branch, so edits elsewhere do
            # not re-render (and reset) an active wizard step.
            isa = project_data.get().isa_data
            return _render_completion(len(isa.elements), len(isa.connections))
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
            if step["target"] == "countries":
                # The country list comes from the session's reference data.
                r_kb.add_reads(reference_reads, (r_kb.KB_NAME, r_kb.GOVERNANCE_NAME))
            widget = _render_choice_many(step, wizard_answers.get(), gov=_gov())
        elif archetype == "freeform_multiple":
            widget = _render_freeform_multiple(
                step, wizard_answers.get(), freeform_counts.get(), input,
                gen=_gen_of(step["target"]), pending=pending,
            )
        elif archetype == "connection_review":
            claude_available = bool(
                os.environ.get("ANTHROPIC_API_KEY")
                and not os.environ.get("SESPY_DISABLE_CLAUDE")
            )
            with reactive.isolate():
                labels = {el.id: el.label for el in project_data.get().isa_data.elements}
            widget = _render_connection_review(
                wizard_suggestions_sp3.get(),
                wizard_claude_status.get(),
                claude_available,
                labels,
            )
        else:
            widget = ui.tags.div(f"Unknown archetype: {archetype}")

        # Build nav buttons inline based on which step we're on.
        nav_buttons: list[ui.Tag] = []
        if step_idx > 0:
            nav_buttons.append(ui.input_action_button(
                "wizard_back", t("wizard.back"), class_="btn btn-secondary",
            ))
        if archetype == "choice_many":
            nav_buttons.append(ui.input_action_button(
                f"skip_{step['target']}",
                t("modules.isa.ai_assistant.skip_this_question"),
                class_="btn btn-outline-secondary",
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
