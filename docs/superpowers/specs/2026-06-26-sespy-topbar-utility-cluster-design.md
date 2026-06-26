# Topbar utility cluster (Feedback / About / Options / Help) — design

**Date:** 2026-06-26
**Status:** approved (brainstorm)
**Mimics:** the BowTie Python Shiny app (`/srv/shiny-server/BowTie/bowtie_app_py` on
laguna) — its `helpers/feedback_store.py` (SQLite), `modules/about_tab.py`,
`modules/theme_module.py`, `modules/feedback_tab.py`, `modules/autosave.py` settings.

## Problem / goal

SESPy's topbar holds only a language switcher. Add a **utility cluster** to the LEFT of
the topbar — **Feedback · About · Options · Help** — each a button opening a `ui.modal`,
mirroring the BowTie app's mechanisms (feedback → SQLite, About → Overview+Changelog
tabs, Options → theme + language + autosave). Relocate the language selector into Options.

## Decisions (from brainstorm)

- **Mimic BowTie**: SQLite feedback store (BowTie schema verbatim), two named themes,
  About with Overview + Changelog tabs.
- **Topbar-button + modal** pattern (SESPy's nav is a left-sidebar stepper, so these
  utility items fit as topbar buttons → `ui.modal`, not nav tabs).
- **Two themes**: Light-marine (the current skin, default) + Deep-ocean (new dark CSS),
  switched via `data-theme` on `<html>` (BowTie's `send_custom_message("set_theme")` JS).
- **Options = genuinely-global, low-plumbing settings only**: theme + relocated language
  + autosave (enable / clear / status). Per-module inputs (uncertainty `n_samples`,
  blind-mode, loop limits, …) are NOT hoisted to global defaults (heavy plumbing, low
  value).
- **Session-scoped** options for v1 (apply now; reset on reload). Cross-session
  persistence (localStorage/cookie) is deferred.
- **Feedback transport = SQLite only** (the GitHub-issue POST is out of scope).

## Architecture (files / components — one plan, ~6 tasks)

### 1. Topbar button group + modal wiring — `sespy/modules/topbar_actions.py` (new)
- `topbar_actions_ui(t)` → a `ui.div(class_="sespy-topbar-actions")` with four
  `ui.input_action_button`s: `tb_feedback`, `tb_about`, `tb_options`, `tb_help`, each with
  a Font-Awesome icon + tooltip/label (`t("topbar.feedback")`, etc.).
- `app.py`: `header_actions=topbar_actions_ui(T)` (replaces `language_switcher(T)` — the
  language switcher moves into the Options modal). `topbar_actions_server(...)` is wired
  in `app.py`'s server alongside the other module servers.
- `topbar_actions_server(input, output, session, *, project_data, translator, …)`: four
  `@reactive.effect @reactive.event(input.tb_*)` handlers, each `ui.modal_show(<modal>)`.
  Holds the Feedback-submit, theme, autosave-clear, and language sub-handlers (below).

### 2. Feedback — `sespy/feedback_store.py` (new, ported from BowTie) + the modal
- **Pure SQLite layer** (no Shiny), BowTie schema verbatim:
  `feedback(id INTEGER PK, created_at TEXT, category TEXT, message TEXT, rating INTEGER,
  status TEXT DEFAULT 'open', resolved_at TEXT, resolved_note TEXT, commit_sha TEXT)`.
  WAL mode + 5 s timeout; idempotent schema on connect.
  - `add(message, rating, category, *, db_path=None) -> int` — INSERT (`created_at`=UTC
    ISO, `status`='open'); returns lastrowid.
  - `list_entries(status=None, limit=500, *, db_path=None) -> list[dict]`.
  - `db_path(db=None) -> Path` — precedence: arg > `SESPY_FEEDBACK_DB` env > default
    `sespy/logs/feedback.db`.
  - `_connect` **must `path.parent.mkdir(parents=True, exist_ok=True)`** (BowTie does) —
    `sespy/logs/` does NOT exist yet. Add `sespy/logs/` to `.gitignore` (it's runtime
    state — neither `logs/` nor `sespy/logs/` is currently ignored).
- **Feedback modal** (mirrors BowTie `feedback_tab`): `ui.input_text_area("fb_message")`,
  `ui.input_slider("fb_rating", 1..5, value=3)`, `ui.input_select("fb_category", choices)`
  with categories `{bug, suggestion, question, other}` (i18n labels), and a `fb_submit`
  button. Submit handler: strip message → if empty `ui.notification_show(warning)` and
  keep modal; else `feedback_store.add(message, rating, category)` →
  `ui.modal_remove()` + success notification.

### 3. About — modal with Overview + Changelog tabs (BowTie `about_tab`)
- New `CHANGELOG.md` at repo root (created from the v1.0.0 / v1.1.0 / v1.2.0 release notes
  — keep-a-changelog style).
- `read_project_doc(name)` helper (in `topbar_actions.py`): reads `<repo>/<name>` and
  returns its text (best-effort; missing file → a short fallback string).
- About modal: `ui.navset_tab(ui.nav_panel(t("about.overview"), ui.markdown(version
  header + README)), ui.nav_panel(t("about.changelog"), ui.markdown(CHANGELOG.md)))`.
  Version from `pyproject`/`__version__` (1.2.0); links to the repo + MarineSABRES.

### 4. Options (Settings) modal — theme + language + autosave

**Shared state (REQUIRED — modals re-render from scratch).** `ui.modal_show` rebuilds the
modal UI every open with NO input-value preservation, so hardcoded `selected=`/`value=`
would revert on every reopen even though the *actual* setting changed. Therefore the
Options modal is **built at show-time from the current state**, held in three
session-scoped `reactive.Value`s created in `app.py` and passed to the relevant servers:
`current_theme = reactive.value("light-marine")`, `autosave_enabled = reactive.value(True)`,
and the existing `translator` (current language). The `tb_options` handler reads these to
set the inputs' initial values, so reopening shows the real current settings.

- **Appearance:** `ui.input_radio_buttons("theme_select", choices=THEME_PRESETS_LABELS,
  selected=current_theme.get())`. A `@reactive.effect @reactive.event(input.theme_select)`
  → `current_theme.set(theme)` + `await session.send_custom_message("set_theme", theme)`.
  - **JS handler — registered after connect, like `bookmark_js`.** `Shiny` is undefined at
    inline-script parse time (confirmed: `dashboard.py` wraps its handlers in
    `$(document).on('shiny:connected', …)`). Add the handler the same way (a `ui.tags.script`
    in the shell head): `$(document).on('shiny:connected', function () {
    Shiny.addCustomMessageHandler('set_theme', function (t) {
    document.documentElement.setAttribute('data-theme', t); }); });`.
  - `www/themes.css` (a NEW file) holds a `[data-theme="deep-ocean"]` block overriding the
    page background / text / card colors to a dark palette. It must be injected in the
    shell **AFTER** `sespy-skin.css` (so the override wins by load order) — add it to the
    `dashboard.py` page-level CSS links (this theme work touches the shell, not just
    `topbar_actions.py`). Light-marine = default (no/`light-marine` `data-theme`).
    `THEME_PRESETS = {"light-marine": {...}, "deep-ocean": {...}}` (key→label). NOTE: pyvis
    graph canvases set a white `bgcolor` in code — under deep-ocean they stay light for v1
    (a themed canvas is out of scope; acceptable, the graphs are framed cards).
- **Language:** the existing `language_switcher(T)` embedded here. On change,
  `dashboard_server._switch_language` calls `translator.set_language()` and the
  `@render.ui` outputs (nav/stepper) re-render — an in-place reactive update, **NOT** a
  full page reload. No special modal-close logic needed.
- **Autosave:** `ui.input_switch("autosave_enabled", value=autosave_enabled.get())`,
  `autosave_clear` button → `autosave.clear_autosave()` + notification, status line from
  `autosave.autosave_age_seconds()` (a snapshot at modal-open time — acceptable).
  - **Cross-module gating (REQUIRED).** The autosave WRITE lives in
    `quick_actions_server` (`project_io.py`, the `_autosave_on_change` effect on
    `event_bus.isa_change`) — NOT in the Options server. To make the toggle work, the
    shared `autosave_enabled` reactive.Value is also passed to `quick_actions_server`,
    and `_autosave_on_change` early-returns when `not autosave_enabled.get()`. The Options
    toggle effect just does `autosave_enabled.set(input.autosave_enabled())`.

### 5. Help — modal
- `ui.modal` with the create→edit→analyze→export workflow guide (brief, i18n) + a link to
  the README / docs. (Mirrors BowTie `help_tab` content, as a modal.)

### 6. i18n + glue
- **~26 new flat keys, each with ALL 9 languages** (en es fr de lt pt it no el).
  `test_loader_handles_all_supported_languages` iterates EVERY key and hard-fails on any
  missing language, so the plan must supply all 9 for each (≈ 26 × 9 ≈ 234 strings).
  Keys: `topbar.{feedback,about,options,help}` (4); `feedback.{title,message,rating,
  category,submit,sent,empty,cat_bug,cat_suggestion,cat_question,cat_other}` (12);
  `about.{overview,changelog}` (2); `options.{title,appearance,theme,language,autosave,
  autosave_enable,autosave_clear,autosave_status}` (8); `help.{title,body}` (2). Add a
  named presence test per group (mirroring `test_cld_contested_keys_present`).

## Data flow

Topbar button → `ui.modal_show`. Feedback submit → `feedback_store.add` (SQLite) →
notify. Theme radio → `send_custom_message("set_theme")` → JS `data-theme`. Language →
existing reload path. Autosave toggle/clear → the autosave module. About/Help → static
markdown/content. Nothing touches `network.py` or the analysis modules.

## Error handling / edge cases

- Empty feedback message → warning notification, modal stays open (no row written).
- `feedback_store` write failure (read-only `logs/`) → caught; the `SESPy_FEEDBACK_DB`
  env lets ops point it at a writable path; surface a failure notification (do not crash
  the session).
- Unknown theme value → ignored (logged), no message sent.
- Missing `CHANGELOG.md`/`README.md` → `read_project_doc` returns a short fallback.
- Autosave disabled → the autosave-on-change effect early-returns (no write); "Clear"
  still works.
- The `data-theme` mechanism is additive: with no JS run / default theme, the app renders
  exactly as today (light-marine).

## Testing

- **Unit** (`tests/test_feedback_store.py`): `add` returns an id and writes a row with
  `status='open'` + the message/rating/category + a `created_at`; `list_entries` returns
  newest-first; the schema is created idempotently; `db_path` honors `SESPY_FEEDBACK_DB`.
  Use a `tmp_path` DB.
- **i18n** named presence tests per key group; the per-language completeness test
  enforces all 9.
- **Update `tests/test_i18n_e2e.py` (REQUIRED — it breaks otherwise).** It currently does
  `document.getElementById('__sespy_language__')` directly; once the switcher is in the
  Options modal that element is absent until the modal opens. Change it to: click
  `#tb_options`, `wait_for_selector('.modal #__sespy_language__')`, then
  `select_option('.modal #__sespy_language__', 'es')`. This is part of THIS work, not a
  pre-existing-unaffected test.
- **New topbar e2e** (`tests/test_topbar_e2e.py`): the four buttons `#tb_feedback`,
  `#tb_about`, `#tb_options`, `#tb_help` are present (root-scoped ids — `topbar_actions`
  is plain functions wired at root, NOT a Shiny module, so NO namespace prefix); clicking
  each opens its modal (`.modal` with the expected title). Feedback: type a message →
  click `#fb_submit` → assert the **success notification** appears (the e2e cannot read
  the server SQLite; the store's write is covered by the unit test — the e2e verifies the
  wired path via the notification). Theme: select Deep-ocean → assert
  `document.documentElement` has `data-theme="deep-ocean"`. About: both `Overview` and
  `Changelog` tabs visible.
- `import app` builds; full e2e stays green **except** the `test_i18n_e2e.py` change above
  (the only shell change is the topbar's `header_actions` + the theme CSS/JS in the shell).

## Out of scope (YAGNI)

- Cross-session persistence of options (localStorage/cookie) — session-scoped for v1.
- The GitHub-issue POST half of BowTie's feedback (SQLite log only).
- Hoisting per-module inputs (uncertainty samples, blind-mode, loop limits) to global
  preferences.
- An in-app feedback admin/triage view (the SQLite DB is consumed by external triage
  tooling, as in BowTie).
- A full design-token refactor — the Deep-ocean theme overrides the key colors, not every
  component, for v1.
