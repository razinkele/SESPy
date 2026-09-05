"""Topbar utility cluster — Feedback / About / Options / Help buttons that open
modals. Plain functions wired at root (NOT a Shiny module), so input ids are
global. Mimics the BowTie app's feedback (SQLite) + About/Options/Help."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from shiny import reactive, render, ui

from .. import __version__ as _sespy_version
from .. import feedback_store
from ..autosave import autosave_age_seconds, clear_autosave
from ..dashboard import language_switcher
from ..i18n import Translator

_THEME_CHOICES = {"light-marine": "Light Marine", "deep-ocean": "Deep Ocean (Dark)"}

_REPO_ROOT = Path(__file__).resolve().parents[2]   # sespy/modules/ -> repo root


def read_project_doc(name: str) -> str:
    """Best-effort read of a repo-root doc; short fallback if missing."""
    try:
        return (_REPO_ROOT / name).read_text(encoding="utf-8")
    except OSError:
        return f"_{name} not available._"


_SECTION_HEADING = re.compile(r"^## (\d+)\. (.+?)\s*$", re.M)


def manual_section(label: str, text: str | None = None, *,
                   strip_heading: bool = False) -> str | None:
    """The docs/MANUAL.md section whose `## N. <label>` heading matches a
    navigation label (Part II is keyed by nav labels). Returns the text from
    that heading up to (not including) the next `## ` or `# ` heading, or
    None when no heading matches. strip_heading drops the section's own
    heading line so the caller can supply its own title. Pure."""
    if text is None:
        text = read_project_doc("docs/MANUAL.md")
    for m in _SECTION_HEADING.finditer(text):
        if m.group(2).strip() != label:
            continue
        start = m.start()
        nxt = re.compile(r"^#{1,2} ", re.M).search(text, m.end())
        section = text[start:nxt.start() if nxt else len(text)].rstrip()
        if strip_heading:
            section = section.split("\n", 1)[1].lstrip("\n") if "\n" in section else ""
        return section
    return None


def _app_version() -> str:
    # The shipped source's __version__ is authoritative: the app runs from the
    # app_dir without an installed sespy distribution, so importlib.metadata
    # would report a stale install (or nothing) rather than the deployed code.
    return _sespy_version

_CATEGORY_KEYS = ("bug", "suggestion", "question", "other")


def _t(translator: Translator | None, key: str, fallback: str) -> str:
    return translator.t(key) if translator else fallback


def topbar_actions_ui(translator: Translator | None = None) -> ui.Tag:
    """The left-of-topbar button group (Feedback / About / Options / Help)."""
    def btn(bid: str, icon: str, key: str, default: str) -> ui.Tag:
        return ui.input_action_button(
            bid, ui.tags.span(ui.tags.i(class_=f"fa fa-{icon}"), " ",
                              _t(translator, key, default)),
            class_="btn btn-sm sespy-topbar-btn",
        )
    return ui.div(
        btn("tb_feedback", "comment", "topbar.feedback", "Feedback"),
        btn("tb_about", "circle-info", "topbar.about", "About"),
        btn("tb_options", "gear", "topbar.options", "Options"),
        btn("tb_help", "circle-question", "topbar.help", "Help"),
        class_="sespy-topbar-actions",
    )


def help_panel_ui(translator: Translator | None = None) -> ui.Tag:
    """The contextual-help offcanvas (v1.9.0). Mount it in the page BODY (app.py
    passes it through dashboard_page's pre_panel_slot), NOT inside the title bar:
    Bootstrap offcanvas is position:fixed and the title bar's layout context
    mis-positions it and collapses the rendered output. Body: the workflow
    paragraph, the manual pointer, then the manual section for the ACTIVE
    panel, rendered server-side into tb_help_section (topbar_actions_server)."""
    return ui.offcanvas(
        ui.markdown(_t(translator, "help.body", "See the README.")),
        ui.p(_t(translator, "help.manual_hint",
                "The full manual is in About → Manual."),
             class_="text-muted small"),
        ui.tags.hr(),
        ui.h5(_t(translator, "help.this_panel", "About this panel")),
        ui.output_ui("tb_help_section"),
        ui.p(ui.input_action_link("tb_help_open_manual",
                                  _t(translator, "help.full_manual",
                                     "Open the full manual (About → Manual)"),
                                  class_="small"),
             class_="mt-3"),
        # Bootstrap's shown/hidden events → input.tb_help_shown, so the manual
        # section is rendered ONLY while the panel is open. A closed panel is
        # still in the DOM; rendering into it would leave manual text (panel
        # labels such as "Boolean attractors") hidden on the page, where bare
        # `text=` selectors and screen readers can find it.
        ui.tags.script(
            "$(document).on('shown.bs.offcanvas', '#tb_help_panel', function () {"
            " Shiny.setInputValue('tb_help_shown', true); });"
            "$(document).on('hidden.bs.offcanvas', '#tb_help_panel', function () {"
            " Shiny.setInputValue('tb_help_shown', false); });"
        ),
        title=_t(translator, "help.title", "Help"),
        id="tb_help_panel", placement="right", width="540px",
        backdrop=False, scroll=True,
        class_="sespy-help-panel",
    )


def _fmt_ts(created_at: str) -> str:
    """ISO-8601 UTC timestamp → compact 'YYYY-MM-DD HH:MM'. Best-effort: returns
    the raw string on a parse failure, or an em dash for empty input."""
    if not created_at:
        return "—"
    try:
        return datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return created_at


def _truncate(text: str, n: int = 60) -> str:
    """Trim to <= n chars, appending an ellipsis when shortened. Full text is
    kept in the cell's title= attribute (see _feedback_table) for hover."""
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


_RATING_MAX = 5


def _feedback_table(entries: list[dict], translator: Translator | None = None) -> ui.Tag:
    """Read-only 'recent feedback' listing for the Feedback modal.

    Pure function of `entries` (dicts as returned by feedback_store.list_entries,
    newest first) so it is unit-testable without a database. Renders an empty-
    state note when there are no entries, otherwise a compact Bootstrap table.
    """
    heading = ui.h6(_t(translator, "feedback.recent_title", "Recent feedback"),
                    class_="mt-3")
    if not entries:
        return ui.TagList(
            heading,
            ui.p(_t(translator, "feedback.none", "No feedback yet."),
                 class_="text-muted small"),
        )

    header = ui.tags.thead(ui.tags.tr(
        ui.tags.th(_t(translator, "feedback.col_date", "Date")),
        ui.tags.th(_t(translator, "feedback.category", "Category")),
        ui.tags.th(_t(translator, "feedback.rating", "Rating")),
        ui.tags.th(_t(translator, "feedback.col_message", "Message")),
    ))
    rows = []
    for e in entries:
        cat = e.get("category") or "other"
        cat_label = _t(translator, f"feedback.cat_{cat}", str(cat).title())
        rating = e.get("rating")
        rating_txt = f"{int(rating)}★" if rating is not None else "—"
        msg = (e.get("message") or "").strip()
        rows.append(ui.tags.tr(
            ui.tags.td(_fmt_ts(e.get("created_at", "")), class_="text-nowrap"),
            ui.tags.td(cat_label),
            ui.tags.td(rating_txt, class_="text-nowrap"),
            ui.tags.td(_truncate(msg), title=msg),
        ))
    table = ui.tags.table(
        header, ui.tags.tbody(*rows),
        class_="table table-sm table-striped sespy-feedback-table mb-0",
    )
    return ui.TagList(heading, ui.div(table, class_="sespy-feedback-table-wrap"))


def _safe_recent_entries(limit: int = 10) -> list[dict]:
    """Best-effort recent-feedback read for the modal. NEVER raises: a store
    problem (e.g. a read-only DB when the deployed app user cannot write the
    WAL/journal) must not crash the whole Feedback dialog — the form still
    opens, the table just shows its empty state. The submit path has its own
    guard, so writing is unaffected by this."""
    try:
        return feedback_store.list_entries(limit=limit)
    except Exception:
        logging.getLogger(__name__).exception("feedback list_entries failed; showing empty table")
        return []


def _feedback_modal(translator: Translator | None) -> ui.Tag:
    cats = {c: _t(translator, f"feedback.cat_{c}", c.title()) for c in _CATEGORY_KEYS}
    return ui.modal(
        ui.input_text_area("fb_message", _t(translator, "feedback.message", "Your feedback"),
                           rows=4, width="100%"),
        ui.input_slider("fb_rating", _t(translator, "feedback.rating", "Rating"),
                        min=1, max=5, value=3, step=1),
        ui.input_select("fb_category", _t(translator, "feedback.category", "Category"),
                        choices=cats),
        ui.tags.hr(),
        # Recent-feedback listing. Built at modal-open time, so it reflects the
        # store as of when Feedback was opened (a freshly submitted entry shows
        # on the next open). Capped at 10 rows to keep the dialog compact. The
        # read is guarded so a DB error degrades to an empty table, not a crash.
        _feedback_table(_safe_recent_entries(10), translator),
        title=_t(translator, "feedback.title", "Send feedback"),
        footer=ui.TagList(
            ui.input_action_button("fb_submit", _t(translator, "feedback.submit", "Submit"),
                                   class_="btn-primary"),
            ui.modal_button("Close"),
        ),
        easy_close=True,
    )


_ABOUT_OVERVIEW = """
SESPy is the Python port of the MarineSABRES Social-Ecological Systems (SES)
Toolbox. A facilitator and a stakeholder group build a causal loop diagram of a
marine social-ecological system, typed with the DAPSI(W)R(M) framework, and
then interrogate it: which feedback loops it contains, which elements carry
leverage, where governance does not reach the pressures it should, how robust
the structure is, and what an intervention might propagate into.

**Workflow.** Setup → Get Started → Create SES → Visualize → Analyze → Report.
The stepper across the top is a guide, not a gate; every panel is reachable
from the navigation at any time.

| Stage | Panels |
|---|---|
| Setup | Project Setup, Stakeholders |
| Get Started | Recent Projects |
| Create SES | Templates, SES Wizard, Edit Data, Rate Connections, Import Data |
| Visualize | CLD Visualization |
| Analyze | Loop Analysis, Network Metrics, Leverage Points, Factor Quadrant, Boolean & Laplacian, Dynamic Simulation, Behaviour Over Time, Intervention, Simplify Network |
| Report | Export Report |

**Where to look next.** The *Manual* tab of this dialog walks through every
panel, explains the science behind each analysis and lists the literature
that shaped the app. The *Changelog* tab records what changed in each release.
"""


def _about_modal(translator) -> ui.Tag:
    header = ui.markdown(
        f"### MarineSABRES SES Toolbox — Python\n\n"
        f"**Version {_app_version()}** — developed within the "
        f"[MarineSABRES](https://marinesabres.eu) Horizon Europe project. "
        f"[Source](https://github.com/razinkele/SESPy). MIT licensed."
    )
    return ui.modal(
        ui.navset_tab(
            ui.nav_panel(_t(translator, "about.overview", "Overview"),
                         ui.div(header, class_="mb-3"),
                         ui.markdown(_ABOUT_OVERVIEW)),
            ui.nav_panel(_t(translator, "about.manual", "Manual"),
                         ui.div(ui.markdown(read_project_doc("docs/MANUAL.md")),
                                class_="sespy-manual")),
            ui.nav_panel(_t(translator, "about.changelog", "Changelog"),
                         ui.markdown(read_project_doc("CHANGELOG.md"))),
        ),
        title="About",
        footer=ui.modal_button("Close"),
        size="xl", easy_close=True,
    )


def _options_modal(translator, current_theme, autosave_enabled) -> ui.Tag:
    age = autosave_age_seconds()
    status = (f"{int(age)}s ago" if age is not None else "—")
    return ui.modal(
        ui.h5(_t(translator, "options.appearance", "Appearance")),
        ui.input_radio_buttons("theme_select", _t(translator, "options.theme", "Theme"),
                               choices=_THEME_CHOICES, selected=current_theme.get()),
        ui.h5(_t(translator, "options.language", "Language")),
        language_switcher(translator),   # the relocated language selector (label is None;
                                         # the h5 above gives it a translated heading)
        ui.tags.hr(),
        ui.h5(_t(translator, "options.autosave", "Autosave")),
        ui.input_switch("autosave_enabled", _t(translator, "options.autosave_enable",
                        "Enable autosave"), value=autosave_enabled.get()),
        ui.p(f"{_t(translator, 'options.autosave_status', 'Last autosave')}: {status}",
             class_="text-muted"),
        ui.input_action_button("autosave_clear",
                               _t(translator, "options.autosave_clear", "Clear autosaved data"),
                               class_="btn-outline-danger btn-sm"),
        title=_t(translator, "options.title", "Options"),
        footer=ui.modal_button("Close"), easy_close=True,
    )


def _help_modal(translator) -> ui.Tag:
    return ui.modal(
        ui.markdown(_t(translator, "help.body", "See the README.")),
        ui.p(_t(translator, "help.manual_hint",
                "The full manual is in About → Manual."),
             class_="text-muted"),
        title=_t(translator, "help.title", "Help"),
        footer=ui.modal_button("Close"), size="l", easy_close=True,
    )


def topbar_actions_server(input, output, session, *, translator=None,
                          current_theme=None, autosave_enabled=None,
                          active_panel=None, nav_items=None) -> None:
    """Wires the four topbar buttons. Feedback / About / Options open modals;
    Help toggles the offcanvas built in topbar_actions_ui. current_theme /
    autosave_enabled are the shared reactive.Values (used by the Options
    modal). active_panel (reactive.Value[str], the nav id from
    dashboard_server) + nav_items (the NAV list, id → label) drive the
    contextual "About this panel" section; either missing → the section
    just shows the manual pointer."""
    labels = {item.id: item.label for item in (nav_items or [])}

    @reactive.effect
    @reactive.event(input.tb_feedback)
    def _open_feedback():
        ui.modal_show(_feedback_modal(translator))

    @reactive.effect
    @reactive.event(input.tb_about)
    def _open_about():
        ui.modal_show(_about_modal(translator))

    @reactive.effect
    @reactive.event(input.tb_options)
    def _open_options():
        ui.modal_show(_options_modal(translator, current_theme, autosave_enabled))

    @reactive.effect
    @reactive.event(input.tb_help)
    def _open_help():
        ui.toggle_offcanvas("tb_help_panel")

    @output
    @render.ui
    def tb_help_section():
        # Only while the panel is shown (see the script in help_panel_ui);
        # `input.tb_help_shown` is unset until the first open → render nothing.
        if not input.tb_help_shown():
            return None
        label = labels.get(active_panel.get()) if active_panel is not None else None
        section = manual_section(label, strip_heading=True) if label else None
        if not section:
            return ui.p(_t(translator, "help.manual_hint",
                           "The full manual is in About → Manual."),
                        class_="text-muted")
        return ui.div(ui.h6(label), ui.markdown(section),
                      class_="sespy-help-section")

    @reactive.effect
    @reactive.event(input.tb_help_open_manual)
    def _help_to_manual():
        ui.toggle_offcanvas("tb_help_panel", show=False)
        ui.modal_show(_about_modal(translator))

    @reactive.effect
    @reactive.event(input.theme_select)
    async def _apply_theme():
        theme = input.theme_select()
        if theme in _THEME_CHOICES:
            current_theme.set(theme)
            await session.send_custom_message("set_theme", theme)

    @reactive.effect
    @reactive.event(input.autosave_enabled)
    def _apply_autosave_pref():
        if autosave_enabled is not None:
            autosave_enabled.set(bool(input.autosave_enabled()))

    @reactive.effect
    @reactive.event(input.autosave_clear)
    def _clear_autosave():
        # clear_autosave() re-raises OSError (it used to swallow it), and an
        # exception escaping a reactive effect surfaces as a session error.
        try:
            clear_autosave()
        except OSError as e:
            logging.getLogger(__name__).warning(
                "topbar.clear_autosave status=error reason=%s", type(e).__name__)
            ui.notification_show(
                _t(translator, "ui.quickactions.clear_autosave_failed",
                   "Could not clear autosaved data."),
                type="warning", duration=4,
            )
            return
        ui.notification_show(
            _t(translator, "options.autosave_cleared", "Autosaved data cleared."),
            type="message", duration=3,
        )

    @reactive.effect
    @reactive.event(input.fb_submit)
    def _submit_feedback():
        msg = (input.fb_message() or "").strip()
        if not msg:
            ui.notification_show(_t(translator, "feedback.empty", "Please enter a message."),
                                 type="warning", duration=3)
            return
        try:
            feedback_store.add(msg, int(input.fb_rating() or 3), input.fb_category() or "other")
        except Exception:
            ui.notification_show(
                _t(translator, "feedback.save_failed", "Could not record feedback."),
                type="error", duration=4,
            )
            return
        ui.modal_remove()
        ui.notification_show(_t(translator, "feedback.sent",
                                "Thanks — your feedback was recorded."),
                             type="message", duration=4)
