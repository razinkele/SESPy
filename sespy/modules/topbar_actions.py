"""Topbar utility cluster — Feedback / About / Options / Help buttons that open
modals. Plain functions wired at root (NOT a Shiny module), so input ids are
global. Mimics the BowTie app's feedback (SQLite) + About/Options/Help."""
from __future__ import annotations

from importlib.metadata import version as _pkg_version
from pathlib import Path

from shiny import reactive, ui

from ..i18n import Translator
from .. import feedback_store

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
