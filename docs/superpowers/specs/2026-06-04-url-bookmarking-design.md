# URL Bookmarking (view-only) — Design

Date: 2026-06-04
Status: **Draft** — design phase, not yet implemented.

## 1. Goal & scope

Let users share a link (or browser-bookmark a URL) that reopens the app at a
specific **view**: the active module plus the UI language. The browser address
bar always reflects the current view, so the URL itself is the shareable
artifact — no explicit "share" button needed.

### 1.1 In scope
- A query-string contract `?view=<nav_id>&lang=<code>`.
- **Read on load:** seed the initial active module + language from the query
  string (validated).
- **Write on change:** keep the URL in sync as the user navigates modules and
  switches language, via `history.replaceState` (no browser-history spam).
- A pure, unit-tested parse/validate/build helper.
- Unit tests + one e2e test (auto-runs in CI).

### 1.2 Out of scope (YAGNI)
- **Full project state in the URL.** SESPy already has Save/Load (JSON) and
  Recent Projects for persisting/sharing the elements/connections/metadata.
  Putting that in a URL would duplicate existing functionality, require Shiny's
  server-side bookmark store, and produce links that don't carry data across
  machines. A bookmarked link restores the *view*, not the user's project.
- A dedicated "Copy link" button — the auto-synced address bar suffices for v1
  (can be added later).
- Sub-module state (e.g. which tab inside an analysis module, scroll position,
  selected rows) or wizard step.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Mechanism | Custom query-param sync (not Shiny `bookmark_store`) | `bookmark_store="url"` serializes *all* inputs → ugly URLs + per-module exclusion upkeep; `active_panel` is a server-side `reactive.Value` derived from action-button counts and doesn't round-trip naturally. A 2-field custom contract yields clean, stable, human-readable links and stays isolated to the shell. |
| URL update | `history.replaceState` | Reflects the current view without adding a history entry per navigation. |
| Params | `view`, `lang` | The two pieces of "view" state. Both optional; invalid/missing → defaults. |
| Validation | Against the real nav-id set + `translator.languages` | Never trust the URL; unknown values silently fall back to defaults. |

## 2. URL contract

```
<path>/?view=<nav_id>&lang=<code>
```

- `view` — the active nav item id, exactly the value held by
  `active_panel: reactive.Value[str]` (e.g. `cld`, `loops`, `metrics`,
  `leverage`, `import`). The canonical id set is `{item.id for item in nav_items}`.
- `lang` — a code in `translator.languages` (e.g. `en`, `es`, `fr`, …).
- Both optional. Missing or unrecognized → existing defaults
  (`active_panel` default = `nav_items[0].id`; current translator language).

## 3. Architecture

Three small, isolated pieces:

```
 page load ──▶ session.clientdata.url_search()  ──┐
                                                   ▼
                                   sespy/bookmark.parse_bookmark()
                                   (validate vs nav ids + langs)
                                                   │ (view?, lang?)
                                                   ▼
            dashboard_server: one-shot @reactive.effect seeds
              active_panel.set(view) + translator.set_language(lang)

 nav/lang change ──▶ dashboard_server: @reactive.effect
        depends on active_panel.get() + translator.language.get()
                       │  build_bookmark(view, lang) -> "?view=…&lang=…"
                       ▼  session.send_custom_message("sespy_bookmark_url", {search})
                www/sespy-bookmark.js handler ──▶ history.replaceState({}, "", search)
```

### 3.1 `sespy/bookmark.py` (new — pure, no Shiny imports)

```python
def parse_bookmark(
    search: str, *, valid_views: set[str], valid_langs: set[str]
) -> tuple[str | None, str | None]:
    """Parse a URL query string into (view, lang), returning only values that
    are present AND valid. Unknown/missing -> None (caller keeps its default)."""

def build_bookmark(view: str, lang: str) -> str:
    """Build the query string '?view=<view>&lang=<lang>' for replaceState."""
```

- Uses `urllib.parse` (`parse_qs`, `urlencode`). Pure functions → fast,
  browser-free unit tests.
- `parse_bookmark` tolerates a leading `?`, missing keys, repeated keys
  (first wins), and empty values.

### 3.2 `sespy/dashboard.py` (edit — ~15 LOC, in `dashboard_server`)

`active_panel`, the nav wiring, and the language input already live here, so
this is the natural and only home for the wiring.

- **Read on load (one-shot):** a `@reactive.effect` reads
  `session.clientdata.url_search()`, calls `parse_bookmark` against the live
  nav-id set and `translator.languages`, and for each valid value calls
  `active_panel.set(view)` / `translator.set_language(lang)`. A module-scoped
  boolean flag (set inside `reactive.isolate()`) ensures it runs once per
  session and does not re-fire when the URL it later writes changes.
- **Write on change:** a `@reactive.effect` that reads `active_panel.get()` and
  `translator.language.get()`, builds the query string via `build_bookmark`,
  and `session.send_custom_message("sespy_bookmark_url", {"search": ...})`.

Self-trigger guard: the read-effect must not depend on the write path, and the
write-effect only reads `active_panel`/`language` (not `url_search`), so there
is no read↔write loop. The "restored once" flag is read/written inside
`reactive.isolate()` so it does not register as a dependency.

### 3.3 `www/sespy-bookmark.js` (new — tiny)

```js
Shiny.addCustomMessageHandler("sespy_bookmark_url", (payload) => {
  history.replaceState({}, "", payload.search);
});
```

Registered the same way as the existing custom JS (burger toggle, pyvis
bridge) — referenced from the dashboard page head/`www`.

## 4. Edge cases

- **Unknown `view`/`lang`** → ignored; defaults retained (validated against the
  real id set + `translator.languages`).
- **No query string** → unchanged default behavior.
- **Repeated/garbage params** → `parse_bookmark` takes first valid, ignores the
  rest; never raises.
- **History:** `replaceState` (not `pushState`) so module navigation doesn't
  bloat the back button.
- **Collision:** Shiny does not use `?view`/`?lang`; we own them.
- **clientdata timing:** `url_search()` is read inside a reactive effect (after
  the session connects), not at module-construction time.

## 5. Testing

- **Unit — `tests/test_bookmark.py`:** `parse_bookmark` (valid, invalid view,
  invalid lang, missing keys, leading `?`, empty values) and `build_bookmark`
  (formatting + round-trip with `parse_bookmark`). Pure; runs in the pip unit
  CI job.
- **E2e — `tests/test_bookmark_e2e.py`:** (1) load `?view=metrics&lang=es` →
  Network Metrics module active and Spanish nav labels; (2) click a different
  nav button → URL `view` param updates; (3) switch language → URL `lang`
  param updates. Auto-discovered by `tests/run_e2e.py` → runs in the e2e CI
  job. Uses `wait_for_selector`/`wait_for_function` per the project's e2e
  convention (never fixed sleeps against reactive renders).

## 6. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/bookmark.py` | new (~30 LOC) | pure parse/validate/build helpers |
| `sespy/dashboard.py` | edit (~+15 LOC) | read-on-load + write-on-change effects in `dashboard_server` |
| `www/sespy-bookmark.js` | new (~3 LOC) | `replaceState` custom-message handler |
| `app.py` / dashboard head | edit (~1 LOC) | include the new JS asset |
| `tests/test_bookmark.py` | new | unit tests for the helpers |
| `tests/test_bookmark_e2e.py` | new | e2e: restore-from-URL + URL-sync-on-change |

No changes to module servers, the project schema, or the App construction
(`bookmark_store` stays unset).
