# URL Bookmarking (active-view) — Design

Date: 2026-06-04 (rev. 3 — after two multi-agent reviews + Shiny-API validation)
Status: **Draft** — design phase, not yet implemented.

## Revision history
- **rev. 1** — scoped "module + UI language".
- **rev. 2** — review found the language half architecturally unsound (static `app_ui`
  + module-level singleton `Translator`); dropped `?lang`, kept `?view`.
- **rev. 3** — second review + Context7 Shiny-API validation. Fixes two implementation-
  breaking defects (panel content not switched on restore; inline handler running before
  `Shiny` is defined), corrects the documented default, resolves first-load/ordering
  behavior, and simplifies (drop `build_view`; add a shared `_goto` helper). All
  mechanisms below are verified against shiny 1.6.1 and the live code.

## 1. Goal & scope

Share/bookmark a link that reopens the app at a specific **module view** (e.g. Network
Metrics). The address bar always reflects the current module, so the URL itself is the
shareable artifact — no "share" button.

### 1.1 In scope
- A query-string contract `?view=<nav_id>`.
- **Read on load:** restore the active module from `?view` (validated), switching **both**
  the sidebar highlight and the visible panel.
- **Write on change:** keep `?view` in sync with `active_panel` (covers nav clicks,
  stepper clicks, and restore) via `history.replaceState`.
- A pure, unit-tested `parse_view` validator; unit + e2e tests.

### 1.2 Out of scope (and why)
- **UI language (`?lang`) — DEFERRED.** `detect_initial_language` exists in `sespy/i18n.py`
  but is **unwired**; `T` is a module-level singleton and `app_ui` is a static value built
  once at import, so per-session/per-link language is unsupported and restoring it via
  `set_language` in an effect half-translates the page. Prerequisite: per-session translator
  + a per-request `app_ui(request)` (the same change Shiny's native bookmarking would also
  require — see §1.4). Tracked as a follow-up.
- **Full project state in the URL** — covered by Save/Load + Recent Projects.
- **A "Copy link" button** / sub-module state (tab, selection).

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Mechanism | Custom `?view` query-param sync (not Shiny `bookmark_store`) | See §1.4 — the native path needs an `app_ui`-as-function refactor + input-exclusion upkeep; the custom path is isolated to the shell and yields a clean one-param URL. Review verified the custom path is sound. |
| URL update | `history.replaceState`, mutating only the `view` param via `new URL(...).searchParams.set('view', …)` | Preserves any other/ future param (e.g. `?lang`); no per-navigation history entry. |
| Write trigger | A server `async @reactive.effect` on `active_panel` | Catches all module changes (nav, stepper, restore), not just nav clicks. `session.send_custom_message` is an async coroutine → the effect is `async` and `await`s it. |
| Client transport | `session.send_custom_message` + `Shiny.addCustomMessageHandler`, registered **inside a `shiny:connected` handler** in an inline `head_content` script | The handler must not reference `Shiny` at parse time (the script parses before `shiny.js` loads). New (standard) handler; the app has no `www/*.js` and no prior `addCustomMessageHandler`. |
| URL always reflects view | On a clean cold load the write effect stamps `?view=<default>` (e.g. `?view=cld`) | Deliberate: "the URL always reflects the current view." Accepted as an edge case (§4); avoids a special-case suppression guard. |
| Scope | View only | Language deferred (§1.2). |

### 1.4 Considered alternative — Shiny native bookmarking (rejected for v1)
Shiny for Python offers `App(..., bookmark_store="url")` + `@session.bookmark.on_bookmark`/
`on_restore`/`on_bookmarked` + `session.bookmark.update_query_string(url)`. It would handle
restore + URL-write natively, **but** requires `app_ui` to become a `def app_ui(request)`
function and pulls in input-serialization (every input must be excluded to keep a clean URL).
For view-only that is more invasive than the custom path. **Note for the future:** the
`app_ui`-as-function refactor it requires is the *same* unlock needed for per-session `?lang`;
if `?lang` is ever pursued, migrating to native bookmarking at that point is the natural move.

## 2. URL contract
```
<path>/?view=<nav_id>
```
- `view` = the active nav item id (what `active_panel: reactive.Value[str]` holds).
  Valid set = `{item.id for item in nav_items}` — the **full 16-panel nav set** (cld, loops,
  metrics, leverage, intervention, simplify, boolean, simulation, bot, wizard, entry,
  templates, import, recent, report, pims — i.e. every panel is bookmarkable).
- Optional. Missing/unrecognized → the app's current default, which is the **`initial`
  argument** passed in `app.py` (currently `"cld"`). `nav_items[0].id` is only the
  fallback when `initial` is falsy — it is **not** the live default.

## 3. Architecture

```
 page load ─▶ session.clientdata.url_search()  ("?view=metrics" | "" )
                  │  bookmark.parse_view(search, valid_views)  → view | None
                  ▼
   dashboard_server one-shot @reactive.effect → _goto(view)   [if view valid]

 module change (nav / stepper / restore) ─▶ async @reactive.effect on active_panel.get()
                  │  await session.send_custom_message("sespy_view_url", {"view": active_panel.get()})
                  ▼
   inline head_content script (registered on shiny:connected):
     addCustomMessageHandler("sespy_view_url", m =>
       { const u=new URL(location); u.searchParams.set('view', m.view); history.replaceState({},'',u); })
```

### 3.1 `sespy/bookmark.py` (new — pure, no Shiny imports)
```python
def parse_view(search: str, valid_views: set[str]) -> str | None:
    """Return the ?view value iff present AND in valid_views; else None.
    Tolerates a leading '?', missing/empty/repeated keys (first valid wins)."""
```
`urllib.parse.parse_qs`. (No `build_view`: the client already encodes via
`searchParams.set`, so the server sends the raw view id.)

### 3.2 `sespy/dashboard.py` (edit — in `dashboard_server`)
- **`_goto(view)` helper** — `active_panel.set(view)` **and**
  `ui.update_navs("main_nav", selected=view, session=session)`. This mirrors the existing
  nav/stepper handlers (dashboard.py:333-337, 349-352), which both call set **+**
  `ui.update_navs` — setting `active_panel` alone moves the highlight but does **not**
  switch the `navset_hidden(id="main_nav")` panel content. Refactor nav, stepper, and the
  restore path to call `_goto`.
- **Read on load (one-shot):** a `@reactive.effect` reads `session.clientdata.url_search()`
  once, calls `parse_view(search, {item.id for item in nav_items})`, and if a valid view
  results calls `_goto(view)`. The effect reads `url_search()` (taking the dependency) then
  short-circuits via a module-scoped flag set inside `reactive.isolate()`. Rationale: this is
  **defensive only** — `history.replaceState` does NOT re-report `.clientdata_url_search` to
  the server, so the read effect cannot re-fire from the write path; the guard simply prevents
  re-running on unrelated `url_search` notifications. Empty search on first flush → no-op.
- **Write on change:** an `async @reactive.effect` that reads `active_panel.get()` and
  `await session.send_custom_message("sespy_view_url", {"view": active_panel.get()})`.
  It fires once on the initial flush (stamping `?view=<default>` — see §1.3/§4) and on every
  subsequent change.

**Ordering / double-write:** the write effect may emit `?view=<default>` before the read
effect restores `?view=metrics`, producing a transient default→target write. This is harmless
under `replaceState` (last write wins); the e2e must assert on the **final settled** URL
(`wait_for_function`), not the first.

### 3.3 Inline handler (added to the existing `ui.head_content(...)` at dashboard.py:238-248,
as another argument alongside `burger_js`)
```python
ui.tags.script(
    "$(document).on('shiny:connected', function(){"
    "  Shiny.addCustomMessageHandler('sespy_view_url', function(m){"
    "    var u = new URL(window.location);"
    "    u.searchParams.set('view', m.view);"
    "    window.history.replaceState({}, '', u);"
    "  });"
    "});"
)
```
Registration is deferred to `shiny:connected` so `Shiny` is defined. (Unlike `burger_js`,
which has no `Shiny` dependency and can run immediately.)

## 4. Edge cases
- **Clean cold load stamps `?view=<default>`** (e.g. `?view=cld`) — intended ("URL always
  reflects current view").
- **Transient double-write** on `?view=metrics` load (default then target) — harmless under
  `replaceState`; e2e asserts the final settled URL.
- Unknown/missing `?view` → default retained (validated against the live 16-id set).
- Only the `view` param is touched (`searchParams.set`); a future `?lang` is preserved.
- `url_search()` may be empty on the first flush before the client reports it — the read
  effect tolerates it (no-op).
- JS is required for the whole Shiny app; no JS-disabled degradation path is needed.

## 5. Testing
- **Unit — `tests/test_bookmark.py`:** `parse_view` (valid, invalid, missing, leading `?`,
  empty, repeated, view-not-in-set). Pure; pip unit job.
- **E2e — `tests/test_bookmark_e2e.py`:** (1) load `?view=metrics` → Network Metrics panel
  **content** visible (not just the highlight) — assert a metrics-only DOM node, and
  `wait_for_function` that the URL settles on `?view=metrics`; (2) click a different nav
  button → URL `view` updates; (3) click the **`visualize`** stepper step (maps to nav
  `cld`) → `wait_for_function` URL becomes `?view=cld` (proves it tracks `active_panel`, not
  just nav clicks). Auto-discovered by `tests/run_e2e.py`; uses `wait_for_selector`/
  `wait_for_function` (never fixed sleeps).

## 6. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/bookmark.py` | new (~12 LOC) | pure `parse_view` validator |
| `sespy/dashboard.py` | edit (~+15 LOC) | `_goto` helper (set + `ui.update_navs`), reused by nav/stepper/restore; one-shot read effect; async write effect; inline `shiny:connected` handler in the existing `head_content` |
| `tests/test_bookmark.py` | new | unit tests |
| `tests/test_bookmark_e2e.py` | new | e2e: restore (panel content) + URL-sync (nav + stepper) |

No `www` assets, no module-server/schema/`App()` changes. `?lang` is a separate,
prerequisite-gated follow-up (§1.2 / §1.4).
