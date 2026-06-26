"""Topbar utility cluster — Feedback / About / Options / Help buttons that open
modals. Plain functions wired at root (NOT a Shiny module), so input ids are
global. Mimics the BowTie app's feedback (SQLite) + About/Options/Help."""
from __future__ import annotations

from importlib.metadata import version as _pkg_version
from pathlib import Path

from shiny import reactive, ui

from ..i18n import Translator
from .. import feedback_store
from ..dashboard import language_switcher
from ..autosave import clear_autosave, autosave_age_seconds

_THEME_CHOICES = {"light-marine": "Light Marine", "deep-ocean": "Deep Ocean (Dark)"}

_REPO_ROOT = Path(__file__).resolve().parents[2]   # sespy/modules/ -> repo root


def read_project_doc(name: str) -> str:
    """Best-effort read of a repo-root doc; short fallback if missing."""
    try:
        return (_REPO_ROOT / name).read_text(encoding="utf-8")
    except OSError:
        return f"_{name} not available._"


def _app_version() -> str:
    try:
        return _pkg_version("sespy")
    except Exception:
        return "1.2.0"

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


def _feedback_modal(translator: Translator | None) -> ui.Tag:
    cats = {c: _t(translator, f"feedback.cat_{c}", c.title()) for c in _CATEGORY_KEYS}
    return ui.modal(
        ui.input_text_area("fb_message", _t(translator, "feedback.message", "Your feedback"),
                           rows=4, width="100%"),
        ui.input_slider("fb_rating", _t(translator, "feedback.rating", "Rating"),
                        min=1, max=5, value=3, step=1),
        ui.input_select("fb_category", _t(translator, "feedback.category", "Category"),
                        choices=cats),
        title=_t(translator, "feedback.title", "Send feedback"),
        footer=ui.TagList(
            ui.input_action_button("fb_submit", _t(translator, "feedback.submit", "Submit"),
                                   class_="btn-primary"),
            ui.modal_button("Close"),
        ),
        easy_close=True,
    )


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
                         ui.markdown(read_project_doc("README.md"))),
            ui.nav_panel(_t(translator, "about.changelog", "Changelog"),
                         ui.markdown(read_project_doc("CHANGELOG.md"))),
        ),
        title="About",
        footer=ui.modal_button("Close"),
        size="l", easy_close=True,
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
        title=_t(translator, "help.title", "Help"),
        footer=ui.modal_button("Close"), size="l", easy_close=True,
    )


def topbar_actions_server(input, output, session, *, project_data, translator=None,
                          current_theme=None, autosave_enabled=None) -> None:
    """Wires the four topbar buttons to their modals. current_theme /
    autosave_enabled are the shared reactive.Values (used by the Options modal)."""

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
        ui.modal_show(_help_modal(translator))

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
        clear_autosave()
        ui.notification_show("Autosaved data cleared.", type="message", duration=3)

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
            ui.notification_show("Could not record feedback.", type="error", duration=4)
            return
        ui.modal_remove()
        ui.notification_show(_t(translator, "feedback.sent",
                                "Thanks — your feedback was recorded."),
                             type="message", duration=4)
