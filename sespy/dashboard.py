"""Dashboard shell — visual port of the R app's bs4Dash layout.

Provides `dashboard_page` (UI) and `dashboard_server` (server-side nav state).
Both are designed to be **call-site composable**: the shell exposes slots for
`brand`, `quick_actions`, `header_actions`, `pre_panel_slot`, and `footer`,
all defaulting to None. Deferred features (workflow stepper, project save/
load, language switcher) drop into these slots without changing the shell
signature.

Why action-button nav + `navset_hidden` instead of `navset_pill_list`:
the latter is a self-contained nav+content layout that doesn't fit inside
`page_sidebar`'s sidebar slot alongside a brand block and quick-actions
footer. We need a sidebar that owns its layout; the trade-off is that we
manage active-panel state ourselves via a `reactive.value`. The nav itself
is `@render.ui`-driven so it re-renders on every active-panel change *and*
on every language change once i18n lands — the same path covers both.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from htmltools import Tag
from shiny import Inputs, Outputs, Session, reactive, render, ui
from shiny.module import resolve_id

from .i18n import Translator

LANGUAGE_INPUT_ID = "__sespy_language__"

NAV_INPUT_PREFIX = "sespy_nav_"
NAV_OUTPUT_ID = "sespy_nav_render"
STEPPER_OUTPUT_ID = "sespy_stepper_render"
STEP_INPUT_PREFIX = "sespy_step_"


@dataclass(frozen=True)
class NavItem:
    """One entry in the left sidebar nav menu.

    `label` is a hardcoded English fallback. `label_key` (optional) is a
    translation key (e.g. "nav.cld") that, when set, is resolved through
    the translator at render time so the label changes with the language.
    """
    id: str
    icon: str
    label: str
    label_key: str | None = None

    @property
    def input_id(self) -> str:
        return f"{NAV_INPUT_PREFIX}{self.id}"


@dataclass(frozen=True)
class StepperItem:
    """One step in the DAPSI workflow stepper bar."""
    id: str
    label: str
    label_key: str | None = None


def workflow_stepper_slot() -> Tag:
    """Placeholder for the workflow stepper. Populated by `dashboard_server`
    when `stepper_steps` is supplied. Pass this as `pre_panel_slot` to
    `dashboard_page`.
    """
    return ui.output_ui(STEPPER_OUTPUT_ID)


def _render_stepper(
    items: list[StepperItem],
    *,
    current: str | None,
    translator: Translator | None = None,
) -> Tag:
    """Build the stepper UI. `current` matches a StepperItem.id; items before
    it render as completed, items after as future.
    """
    current_idx = next(
        (i for i, it in enumerate(items) if it.id == current),
        -1,
    )

    children: list[Tag] = []
    for idx, it in enumerate(items):
        if current_idx >= 0 and idx < current_idx:
            state = "completed"
        elif idx == current_idx:
            state = "active"
        else:
            state = "future"
        label = (
            translator.t(it.label_key) if (translator and it.label_key) else it.label
        )
        children.append(
            ui.tags.button(
                ui.tags.span(str(idx + 1), class_="num"),
                ui.tags.span(label),
                id=f"{STEP_INPUT_PREFIX}{it.id}",
                type="button",
                class_=f"sespy-stepper-item action-button {state}",
                **{"data-step": it.id},
            )
        )
        if idx < len(items) - 1:
            children.append(
                ui.tags.span(
                    ui.tags.i(class_="fa fa-chevron-right"),
                    class_="sespy-stepper-arrow",
                )
            )
    return ui.tags.div(*children, class_="sespy-stepper")


def _brand_block(title: str, image: str | None) -> Tag:
    """Sidebar brand: optional image + title. Mirrors `dashboardBrand` in R."""
    parts = []
    if image:
        parts.append(ui.tags.img(src=image, alt=title))
    parts.append(ui.tags.span(title, class_="sespy-brand-title"))
    return ui.tags.div(*parts, class_="sespy-brand")


def _nav_button(item: NavItem, *, active: bool, translator: Translator | None) -> Tag:
    """A single nav-menu button. Active state is encoded in the className so
    the CSS can apply the bs4Dash-style left-edge accent.
    """
    classes = ["sespy-nav-btn", "action-button"]
    if active:
        classes.append("active")
    label = (
        translator.t(item.label_key) if (translator and item.label_key) else item.label
    )
    return ui.tags.button(
        ui.tags.i(class_=f"fa fa-{item.icon} sespy-nav-icon"),
        ui.tags.span(label),
        id=item.input_id,
        type="button",
        class_=" ".join(classes),
    )


def language_switcher(translator: Translator) -> Tag:
    """A small dropdown for switching languages, suitable for `header_actions`.
    Reads/writes `translator.language` via the `__sespy_language__` input id.
    """
    labels = {
        "en": "English", "es": "Español", "fr": "Français",
        "de": "Deutsch", "lt": "Lietuvių", "pt": "Português",
        "it": "Italiano", "no": "Norsk", "el": "Ελληνικά",
    }
    choices = {code: labels.get(code, code) for code in translator.languages}
    return ui.tags.div(
        ui.input_select(
            LANGUAGE_INPUT_ID,
            None,
            choices=choices,
            selected=translator._lang,
            width="160px",
        ),
        class_="sespy-language-switcher",
    )


def dashboard_page(
    *panels: Tag,
    nav_items: list[NavItem],
    initial: str = "",
    title: str = "MarineSABRES SES Toolbox",
    brand_title: str = "SES Tool",
    brand_image: str | None = None,
    quick_actions: Tag | None = None,
    header_actions: Tag | None = None,
    pre_panel_slot: Tag | None = None,
    footer: Tag | None = None,
) -> Tag:
    """Build the top-level page UI.

    All Tag-typed parameters default to None and are simply omitted from the
    output if not supplied. That keeps the shell forward-compatible with the
    deferred features without baking anything in.
    """
    if not initial:
        initial = nav_items[0].id if nav_items else ""

    sidebar_children: list[Tag] = [
        _brand_block(brand_title, brand_image),
        # Nav re-renders on active-panel change via dashboard_server below.
        ui.output_ui(NAV_OUTPUT_ID),
    ]
    if quick_actions is not None:
        sidebar_children.append(quick_actions)

    main_children: list[Tag] = []
    if header_actions is not None:
        main_children.append(ui.tags.div(header_actions, class_="sespy-topbar"))
    if pre_panel_slot is not None:
        main_children.append(pre_panel_slot)
    main_children.append(ui.navset_hidden(*panels, id="main_nav", selected=initial))
    main_children.append(
        footer
        or ui.tags.footer(
            "© 2026 ",
            ui.tags.a("Marine-SABRES", href="https://marinesabres.eu", target="_blank"),
            " — Horizon Europe Project",
            class_="sespy-footer",
        )
    )

    # Mini-mode for the OUTER nav sidebar only. We bind ONE capture-phase
    # listener on the nav LAYOUT (resolved once at init via the dedicated
    # `sespy-nav-shell` marker on its sidebar). Capture on the layout — an
    # ancestor of the toggle — pre-empts bslib's own target-phase collapse
    # handler, so the nav toggle drives mini-mode instead of bslib's full
    # collapse. Every OTHER collapse-toggle (per-page layout_sidebars,
    # .sespy-card module sidebars, any future sidebar) is untouched and falls
    # through to bslib's native collapse.
    #
    # Why an identity check (`=== layout`): the nav layout contains all
    # per-page layouts (page_sidebar wraps the whole page), so a click on a
    # nested per-page toggle still bubbles through this listener — we act ONLY
    # when the clicked toggle's NEAREST sidebar-layout IS the nav layout.
    # `sespy-nav-shell` is LOAD-BEARING FOR BEHAVIOR — do not rename/remove it
    # without updating this script and the marker on the nav sidebar below.
    burger_js = ui.tags.script("""
        (function () {
          function wire() {
            var sidebar = document.querySelector('.sidebar.sespy-nav-shell');
            if (!sidebar) return false;
            var layout = sidebar.closest('.bslib-sidebar-layout');
            if (!layout) return false;
            layout.addEventListener('click', function (e) {
              var btn = e.target.closest('.collapse-toggle');
              if (!btn) return;
              if (btn.closest('.bslib-sidebar-layout') !== layout) return;
              e.preventDefault();
              e.stopImmediatePropagation();
              document.body.classList.toggle('sespy-sidebar-mini');
            }, true);  // capture on the layout — pre-empts bslib's handler
            return true;
          }
          if (!wire()) document.addEventListener('DOMContentLoaded', wire);
        })();
    """)

    # URL bookmarking: when the server sends the active view, reflect it in the
    # address bar (replaceState, so navigation doesn't bloat history). Register
    # on shiny:connected — the handler depends on `Shiny`, which (unlike the
    # burger script) is not defined when this inline script first parses.
    bookmark_js = ui.tags.script("""
        $(document).on('shiny:connected', function() {
          Shiny.addCustomMessageHandler('sespy_view_url', function(m) {
            var u = new URL(window.location);
            u.searchParams.set('view', m.view);
            window.history.replaceState({}, '', u);
          });
        });
    """)

    theme_js = ui.tags.script("""
      $(document).on('shiny:connected', function () {
        Shiny.addCustomMessageHandler('set_theme', function (t) {
          document.documentElement.setAttribute('data-theme', t);
        });
      });
    """)

    return ui.tags.div(
        # Inject the shell stylesheet at the page level. The skin contains the
        # design tokens, layout, AND the critical guards (display:block on
        # pyvis-network-output, transform:none on canvas cards) — landing it
        # via the shell guarantees those guards are present whenever the shell
        # is used.
        ui.head_content(
            ui.tags.link(rel="stylesheet", href="sespy-skin.css"),
            ui.tags.link(rel="stylesheet", href="cld.css"),
            ui.tags.link(rel="stylesheet", href="themes.css"),
            # Font Awesome — needed for the icons in NavItem entries
            ui.tags.link(
                rel="stylesheet",
                href=("https://cdnjs.cloudflare.com/ajax/libs/font-awesome/"
                      "6.5.0/css/all.min.css"),
            ),
            burger_js,
            bookmark_js,
            theme_js,
        ),
        ui.page_sidebar(
            ui.sidebar(*sidebar_children, width=280, class_="sespy-sidebar sespy-nav-shell"),
            *main_children,
            title=title,
            fillable=True,
        ),
    )


def dashboard_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    nav_items: list[NavItem],
    initial: str = "",
    stepper_steps: list[StepperItem] | None = None,
    nav_to_step: dict[str, str] | None = None,
    translator: Translator | None = None,
) -> reactive.Value[str]:
    """Wire the sidebar nav. Returns the `active_panel` reactive so the caller
    can observe it (e.g. for breadcrumbs or telemetry).

    If `stepper_steps` is supplied, also renders the workflow stepper into
    the slot returned by `workflow_stepper_slot()`. `nav_to_step` maps a
    nav item id to a stepper item id (e.g. "cld" -> "visualize"); navs
    not in the map leave the stepper without a current step.
    """
    if not initial:
        initial = nav_items[0].id if nav_items else ""

    active_panel: reactive.Value[str] = reactive.value(initial)

    @render.ui
    def sespy_nav_render():
        cur = active_panel.get()
        return ui.tags.nav(
            *[
                _nav_button(item, active=(item.id == cur), translator=translator)
                for item in nav_items
            ],
            class_="sespy-nav",
        )

    # One observer per nav button. All call the same factory, no copy-paste
    # repetition. When submenus arrive, this is where the tree walk goes.
    for item in nav_items:
        _wire_nav_button(input, session, item, active_panel)

    if translator is not None:
        @reactive.effect
        @reactive.event(input[LANGUAGE_INPUT_ID])
        def _switch_language():
            new_lang = input[LANGUAGE_INPUT_ID]()
            if new_lang and new_lang in translator.languages:
                translator.set_language(new_lang)

    if stepper_steps:
        @render.ui
        def sespy_stepper_render():
            cur_step = (nav_to_step or {}).get(active_panel.get())
            return _render_stepper(stepper_steps, current=cur_step, translator=translator)

        # Reverse map: stepper_id → first nav that maps to it. Built once
        # from `nav_to_step`. Click on stepper step navigates to that nav.
        step_to_nav: dict[str, str] = {}
        for nav_id, step_id in (nav_to_step or {}).items():
            step_to_nav.setdefault(step_id, nav_id)

        for step in stepper_steps:
            target_nav = step_to_nav.get(step.id)
            if target_nav is None:
                continue  # no panel claims this step — leave it non-navigable
            _wire_step_button(input, session, step.id, target_nav, active_panel)

    # --- URL bookmarking (view-only): restore ?view on load, sync on change ---
    from .bookmark import parse_view

    _did_restore = [False]  # per-session closure-local — NOT a module global
    _valid_views = {item.id for item in nav_items}

    @reactive.effect
    def _restore_view_from_url():
        search = session.clientdata.url_search()   # register the dependency
        with reactive.isolate():
            if _did_restore[0]:
                return
            _did_restore[0] = True
        view = parse_view(search, _valid_views)
        if view:
            _goto(active_panel, session, view)

    @reactive.effect
    async def _sync_view_to_url():
        view = active_panel.get()
        await session.send_custom_message("sespy_view_url", {"view": view})

    return active_panel


def _goto(
    active_panel: reactive.Value[str],
    session: Session,
    view: str,
) -> None:
    """Switch the active module: move the sidebar highlight AND switch the
    `navset_hidden(id="main_nav")` panel content. `active_panel.set` alone
    only moves the highlight — both calls are required (this mirrors the
    existing nav/stepper handlers)."""
    active_panel.set(view)
    ui.update_navs("main_nav", selected=view, session=session)


def _wire_nav_button(
    input: Inputs,
    session: Session,
    item: NavItem,
    active_panel: reactive.Value[str],
) -> None:
    @reactive.effect
    @reactive.event(input[item.input_id], ignore_init=True)
    def _switch():
        _goto(active_panel, session, item.id)


def _wire_step_button(
    input: Inputs,
    session: Session,
    step_id: str,
    target_nav: str,
    active_panel: reactive.Value[str],
) -> None:
    """Click on a stepper step → navigate to the first nav that maps to it."""
    @reactive.effect
    @reactive.event(input[f"{STEP_INPUT_PREFIX}{step_id}"], ignore_init=True)
    def _switch():
        _goto(active_panel, session, target_nav)
