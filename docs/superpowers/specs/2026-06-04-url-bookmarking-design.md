# URL Bookmarking (active-view) — Design

Date: 2026-06-04 (rev. 2 — after the 2026-06-04 deep review)
Status: **Draft** — design phase, not yet implemented.

## Revision note
Rev. 1 scoped this as "active module **+ UI language**". The 2026-06-04 multi-agent
review found the language half is architecturally unsound here (see §1.2): the app
has a single module-level `Translator` and a static `app_ui` built once at import, so
per-session/per-link language is not supported, and applying `?lang` via a reactive
effect would yield a half-translated page. Rev. 2 **scopes the feature to the active
module (`?view`) only** and defers language bookmarking with a clear prerequisite.

## 1. Goal & scope

Let users share/bookmark a link that reopens the app at a specific **module view**
(e.g. Network Metrics). The browser address bar always reflects the current module,
so the URL itself is the shareable artifact — no "share" button needed.

### 1.1 In scope
- A query-string contract `?view=<nav_id>`.
- **Read on load:** seed the initial active module from `?view` (validated against the
  real nav-id set; invalid/missing → existing default).
- **Write on change:** keep `?view` in sync with the active module via
  `history.replaceState` — covering nav-button clicks, stepper clicks, and the
  read-on-load restore (i.e., it tracks `active_panel`, not just nav clicks).
- A pure, unit-tested parse/validate/build helper.
- Unit tests + one e2e test (auto-runs in the e2e CI job).

### 1.2 Out of scope (and why)
- **UI language (`?lang`) — DEFERRED.** `sespy/i18n.py` exposes a tested
  `detect_initial_language("?lang=es")`, but it is **not wired anywhere** in the app,
  and the i18n architecture blocks per-session language: `T = Translator(...)` is built
  **once at module import** (`app.py:68`) and shared across sessions, and `app_ui =
  dashboard_page(...)` is a **static value built once at import** (not a per-request
  function). Consequences flagged by the review:
  (a) applying `?lang` via a reactive `set_language()` only re-renders `@render.ui`
      content — static panel bodies/labels stay in the construction-time language →
      a **half-translated** page;
  (b) the module-level singleton `T` means a shared `?lang` link would flip language
      for **all concurrent sessions**.
  Proper `?lang` support is a **prerequisite feature**: a per-session translator + a
  per-request `app_ui(request)` (dynamic UI), at which point wiring
  `detect_initial_language` at construction becomes correct. Tracked as a follow-up;
  out of scope here.
- **Full project state in the URL** — covered by Save/Load (JSON) + Recent Projects.
- **A "Copy link" button** — the auto-synced address bar suffices for v1.
- **Sub-module state** (which tab/selection inside a module).

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Mechanism | Custom `?view` query-param sync (not Shiny `bookmark_store`) | `bookmark_store="url"` serializes all inputs → ugly URLs + per-module exclusion upkeep; `active_panel` is a server-side `reactive.Value` derived from action-button counts and doesn't round-trip naturally. One clean param is simpler and isolated to the shell. |
| URL update | `history.replaceState` | Reflects the current view without a history entry per navigation. |
| Write trigger | A server effect on `active_panel` (not a client nav-click listener) | Catches **all** ways the module changes — nav buttons, stepper clicks, and restore — not just direct nav clicks. |
| Client transport | `session.send_custom_message` + an **inline** `ui.tags.script` handler in `head_content` | Matches the existing inline-script pattern (the burger toggle); the app has **no** `www/*.js` files and no prior `addCustomMessageHandler`, so this is a new (but standard Shiny) handler, added inline — not a `www` asset. |
| Scope | View only | The language half is deferred (§1.2); `view` is the sound, high-value core. |

## 2. URL contract
```
<path>/?view=<nav_id>
```
- `view` = the active nav item id, exactly what `active_panel: reactive.Value[str]`
  holds (e.g. `cld`, `loops`, `metrics`, `leverage`, `import`). Canonical set =
  `{item.id for item in nav_items}`.
- Optional. Missing/unrecognized → existing default (`active_panel` default =
  `nav_items[0].id`).
- Any other query params (incl. a future `?lang`) are left untouched.

## 3. Architecture

```
 page load ─▶ session.clientdata.url_search()
                     │  bookmark.parse_view(search, valid_views)  (validate vs nav ids)
                     ▼  view? 
   dashboard_server: one-shot @reactive.effect → active_panel.set(view)   [guarded once]

 module change (nav click / stepper click / restore) ─▶ dashboard_server:
   async @reactive.effect, depends on active_panel.get()
                     │  bookmark.build_view(view) -> "view=<id>"
                     ▼  await session.send_custom_message("sespy_view_url", {view})
   inline head_content script: addCustomMessageHandler → URL.searchParams.set('view', …)
                                                          history.replaceState(...)
```

### 3.1 `sespy/bookmark.py` (new — pure, no Shiny imports)
```python
def parse_view(search: str, valid_views: set[str]) -> str | None:
    """Return the ?view value iff present AND in valid_views; else None."""

def build_view(view: str) -> str:
    """Return 'view=<view>' (urlencoded) for the client to set on the URL."""
```
Uses `urllib.parse` (`parse_qs`, `urlencode`). Pure → fast unit tests. Tolerates a
leading `?`, missing/empty/repeated keys (first valid wins).

### 3.2 `sespy/dashboard.py` (edit — ~12 LOC, in `dashboard_server`)
- **Read on load (one-shot):** a `@reactive.effect` reads
  `session.clientdata.url_search()`, calls `parse_view(search, {ids})`, and if valid
  `active_panel.set(view)`. A module-scoped flag (read/written inside
  `reactive.isolate()`) makes it run once and not re-fire when the URL it later writes
  changes. Empty/first-connect search → no-op (keep default).
- **Write on change (async):** an `async @reactive.effect` that reads
  `active_panel.get()` and `await session.send_custom_message("sespy_view_url",
  {"view": build_view(active_panel.get())})`. (`send_custom_message` is a coroutine —
  the effect must be async.)

### 3.3 Inline handler (in `dashboard_page` `head_content`)
```python
ui.tags.script(
    "Shiny.addCustomMessageHandler('sespy_view_url', function(m){"
    "  var u = new URL(window.location);"
    "  u.searchParams.set('view', m.view);"
    "  window.history.replaceState({}, '', u);"
    "});"
)
```
Added alongside the existing inline burger script — **not** a `www/*.js` file.

## 4. Edge cases
- Unknown/missing `?view` → default module retained (validated against the live id set).
- `replaceState` (not `pushState`) so module switching doesn't bloat history.
- We touch only the `view` param; other params (future `?lang`) are preserved.
- `url_search()` is read inside a reactive effect (post-connect), not at construction.

## 5. Testing
- **Unit — `tests/test_bookmark.py`:** `parse_view` (valid, invalid, missing, leading
  `?`, empty, repeated) and `build_view` (format + round-trip). Pure; runs in the pip
  unit job.
- **E2e — `tests/test_bookmark_e2e.py`:** (1) load `?view=metrics` → Network Metrics
  module active; (2) click a different nav button → URL `view` updates; (3) click a
  stepper step that changes module → URL `view` updates (proves it tracks
  `active_panel`, not just nav clicks). Auto-discovered by `tests/run_e2e.py`; uses
  `wait_for_selector`/`wait_for_function` (never fixed sleeps), per the project's e2e
  convention.

## 6. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/bookmark.py` | new (~20 LOC) | pure `parse_view`/`build_view` |
| `sespy/dashboard.py` | edit (~+12 LOC) | read-on-load + async write-on-change effects in `dashboard_server`; inline `addCustomMessageHandler` script in `dashboard_page` head |
| `tests/test_bookmark.py` | new | unit tests |
| `tests/test_bookmark_e2e.py` | new | e2e: restore-from-URL + URL-sync (nav + stepper) |

No `www` assets, no module-server/schema/`App()` changes. Language (`?lang`) is a
separate, prerequisite-gated follow-up (§1.2).
