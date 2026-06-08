# URL Bookmarking (active-view) — Design

Date: 2026-06-04 (rev. 5 — status update after implementation + deep review)
Status: **Implemented** ✓ (2026-06-08 · 317 unit tests + 24/24 e2e tests pass)

## Revision history
- **rev. 1** — scoped "module + UI language".
- **rev. 2** — dropped `?lang` (static `app_ui` + singleton `Translator` make per-session
  language unsound); kept `?view`.
- **rev. 3** — fixed restore (must call `ui.update_navs`, not just `active_panel.set`; added
  `_goto`), handler registration timing, the documented default, first-load stamp.
- **rev. 4** — third review confirmed the JS/transport is correct (jQuery `$` is reliably
  global; `shiny:connected` registers the handler before any message can arrive — verified
  against shiny 1.6.1). Remaining fixes are test-rigor + a per-session-guard precision:
  (a) the stepper e2e was vacuous (identity short-circuit on `cld`→`cld`); (b) the restore
  assertion checked existence, not visibility (`navset_hidden` renders all panels);
  (c) the restore once-guard must be a **per-session closure-local**, not a module global.
- **rev. 5** — implementation complete (2026-06-08). Status updated from Draft to Implemented.
  **Critical note on `?lang` deferral:** v1 is module-level `app_ui` (static) + singleton
  `Translator` (captured at import). Per-session language requires a three-part refactor:
  (a) per-request `app_ui(request)` builder (same refactor Shiny native bookmarking needs);
  (b) per-request translator instance (not singleton); (c) reload or re-render of static UI
  blocks on language change. This is a *deliberate architectural deque* (§1.2), not a bug.
  Phase-2 language bookmark is the natural follow-up after per-session infrastructure lands.

## 1. Goal & scope

Share/bookmark a link that reopens the app at a specific **module view** (e.g. Network
Metrics). The address bar always reflects the current module, so the URL itself is the
shareable artifact — no "share" button.

### 1.1 In scope
- A query-string contract `?view=<nav_id>`.
- **Read on load:** restore the active module from `?view` (validated), switching **both**
  the sidebar highlight **and** the visible panel.
- **Write on change:** keep `?view` in sync with `active_panel` (nav clicks, stepper clicks,
  restore) via `history.replaceState`.
- A pure, unit-tested `parse_view` validator; unit + e2e tests.

### 1.2 Out of scope (and why)
- **UI language (`?lang`) — DEFERRED.** `detect_initial_language` exists but is unwired; `T`
  is a module-level singleton and `app_ui` is static, so per-session language is unsupported
  and an effect-based `set_language` half-translates the page. Prerequisite: per-session
  translator + a per-request `app_ui(request)` (the same change Shiny's native bookmarking
  needs — §1.4).
- **Full project state in the URL** — covered by Save/Load + Recent Projects.
- **A "Copy link" button** / sub-module state.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Mechanism | Custom `?view` query-param sync (not Shiny `bookmark_store`) | §1.4 — native path needs an `app_ui`-as-function refactor + input-exclusion upkeep; the custom path is isolated and yields a clean one-param URL. Reviews verified it sound. |
| URL update | `history.replaceState`, mutating only `view` via `new URL(...).searchParams.set('view', …)` | Preserves other/future params (`?lang`); no per-nav history entry. Verified: `replaceState` fires no event and Shiny doesn't poll `location`, so it cannot re-trigger the read effect. |
| Write trigger | server `async @reactive.effect` on `active_panel` | Catches all module changes. `session.send_custom_message` is an async coroutine → effect is `async` + `await`s it. |
| Client transport | `Shiny.addCustomMessageHandler` registered inside `$(document).on('shiny:connected', …)`, in an inline `head_content` script | **Verified correct (rev.4):** jQuery `$` is globally available (jquery dep injected at head index 0, before the `head_content` script); `shiny:connected` fires before the client sends `init`, and the server only sends after receiving `init`, so the handler is registered before any `sespy_view_url` message — no drop. (Shiny silently drops unmatched custom-message types with no client queue, so this timing is load-bearing — do not move registration out of `shiny:connected`.) |
| URL always reflects view | Clean cold load stamps `?view=<default>` (e.g. `?view=cld`) | Deliberate; accepted edge case (§4). |
| Restore once-guard | **per-session closure-local** flag (`_did_restore = [False]` captured in `dashboard_server`) | Must NOT be a Python module-global — that would disable restore for every later session on the process. |
| Scope | View only | Language deferred (§1.2). |

### 1.4 Considered alternative — Shiny native bookmarking (rejected for v1)
`App(..., bookmark_store="url")` + `on_bookmark`/`on_restore`/`on_bookmarked` +
`session.bookmark.update_query_string`. Handles restore + URL-write natively, **but** requires
`app_ui` to become `def app_ui(request)` and pulls in input-serialization (exclude every input
for a clean URL). More invasive than the custom path for view-only. **Future note:** that
`app_ui`-as-function refactor is the same unlock per-session `?lang` would need; if `?lang` is
pursued, migrating to native bookmarking then is the natural move.

## 2. URL contract
```
<path>/?view=<nav_id>
```
- `view` = the active nav item id (what `active_panel: reactive.Value[str]` holds). The
  authoritative valid set is computed at runtime as `{item.id for item in nav_items}` — every
  panel is bookmarkable. (Verified: this equals the live NAV ids in `app.py`. The id list is
  intentionally not hardcoded in code to avoid drift; if any doc list is added, back it with a
  unit assertion that it equals the NAV ids.)
- Optional. Missing/unrecognized → the app's current default, which is the **`initial`
  argument** passed in `app.py` (currently `"cld"`). `nav_items[0].id` (=`pims`) is only the
  fallback when `initial` is falsy — **not** the live default.

## 3. Architecture

```
 page load ─▶ session.clientdata.url_search()  ("?view=metrics" | "")
                  │  bookmark.parse_view(search, valid_views)  → view | None
                  ▼
   dashboard_server one-shot @reactive.effect → _goto(view)   [if view valid]

 module change (nav / stepper / restore) ─▶ async @reactive.effect on active_panel.get()
                  │  await session.send_custom_message("sespy_view_url", {"view": active_panel.get()})
                  ▼
   inline head_content script (registers on shiny:connected):
     $(document).on('shiny:connected', () => Shiny.addCustomMessageHandler('sespy_view_url',
       m => { const u=new URL(location); u.searchParams.set('view', m.view); history.replaceState({},'',u); }))
```

### 3.1 `sespy/bookmark.py` (new — pure, no Shiny imports)
```python
def parse_view(search: str, valid_views: set[str]) -> str | None:
    """Return the ?view value iff present AND in valid_views; else None.
    Tolerates a leading '?', missing/empty/repeated keys (first valid wins)."""
```
`urllib.parse.parse_qs`. No `build_view` — the client encodes via `searchParams.set`, so the
server sends the raw view id.

### 3.2 `sespy/dashboard.py` (edit — in `dashboard_server`)
- **`_goto(view)` helper** — `active_panel.set(view)` **and**
  `ui.update_navs("main_nav", selected=view, session=session)`. Mirrors the existing nav
  (dashboard.py:333-337) and stepper (:348-352) handlers, which both call this pair —
  `active_panel.set` alone moves the highlight but does NOT switch the `navset_hidden`
  content. Refactor nav, stepper, and restore to call `_goto`.
- **Read on load (one-shot), exact shape:**
  ```python
  _did_restore = [False]            # per-session closure-local; NOT a module global
  @reactive.effect
  def _restore_view():
      search = session.clientdata.url_search()     # register the dependency
      with reactive.isolate():
          if _did_restore[0]:
              return
          _did_restore[0] = True
      view = parse_view(search, {item.id for item in nav_items})
      if view:
          _goto(view)
  ```
  Reads only `url_search()` as a dependency (never `active_panel`, which would couple it to
  the write path). The guard is defensive — `replaceState` cannot re-report `url_search`, so
  the effect cannot re-fire from its own writes. Empty search on first flush → `parse_view`
  returns None → no-op.
- **Write on change:** an `async @reactive.effect` reading `active_panel.get()` and
  `await session.send_custom_message("sespy_view_url", {"view": active_panel.get()})`.

**Ordering / double-write:** the write effect may emit `?view=<default>` before the read
effect restores `?view=metrics` — a transient default→target write, harmless under
`replaceState`. Tests assert the **final settled** URL.

### 3.3 Inline handler (added to the existing `ui.head_content(...)` at dashboard.py:238-248,
alongside `burger_js`)
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
(Unlike `burger_js`, this depends on `Shiny`, so it registers on `shiny:connected` — verified
to fire before any message arrives.)

## 4. Edge cases
- **Clean cold load stamps `?view=<default>`** (`?view=cld`) — intended.
- **Transient default→target double-write** on `?view=metrics` load — harmless under
  `replaceState`; e2e asserts the final settled URL.
- **Restore `update_navs` fires during the initial reactive flush** — a newer timing than the
  existing post-click handlers exercise. Assumption: Shiny queues the `update_navs` message
  and applies it on connect; the §5 **visibility** assertion is the safety net that this
  actually switched the panel.
- Unknown/missing `?view` → default retained (validated against the live 16-id set).
- Only `view` is touched; a future `?lang` is preserved.
- JS is required for the whole Shiny app; no JS-disabled degradation path.

## 5. Testing
- **Unit — `tests/test_bookmark.py`:** `parse_view` (valid, invalid, missing, leading `?`,
  empty, repeated, view-not-in-set). Pure; pip unit job.
- **E2e — `tests/test_bookmark_e2e.py`** (builds its own `http://127.0.0.1:<port>/?view=…`
  URLs — the harness passes no query string; uses `wait_for_selector`/`wait_for_function`,
  never fixed sleeps):
  1. **Restore switches the panel (not just the highlight).** Load `?view=metrics`; assert
     the metrics tab-pane is **active/visible** — e.g. the `.tab-pane[data-value='metrics']`
     has class `active`, or `#metrics-metrics_network` `is_visible()` is True while the `cld`
     pane is hidden. (A bare existence check is insufficient: `navset_hidden` renders all
     panels into the DOM.) Also `wait_for_function` the URL settles on `?view=metrics`.
  2. **Nav click updates the URL.** Click a different nav button; `wait_for_function` the URL
     `view` param updates.
  3. **Stepper click tracks `active_panel` (real value change).** First click
     `#sespy_nav_metrics` and `wait_for_function` URL is `?view=metrics`; THEN click
     `#sespy_step_visualize` (maps to nav `cld`) and `wait_for_function` URL becomes
     `?view=cld`. (Navigating to metrics first is required: starting from the default `cld`,
     `visualize`→`cld` is a no-op `active_panel.set` that the `reactive.Value` identity check
     short-circuits, so the assertion would pass from the cold-load stamp regardless.)

## 6. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/bookmark.py` | new (~12 LOC) | pure `parse_view` validator |
| `sespy/dashboard.py` | edit (~+18 LOC) | `_goto` (set + `ui.update_navs`) reused by nav/stepper/restore; one-shot read effect (per-session guard); async write effect; inline `shiny:connected` handler in the existing `head_content` |
| `tests/test_bookmark.py` | new | unit tests |
| `tests/test_bookmark_e2e.py` | new | e2e: restore (panel **visibility**) + URL-sync (nav + stepper-with-real-change) |

No `www` assets, no module-server/schema/`App()` changes. `?lang` is a separate,
prerequisite-gated follow-up (§1.2 / §1.4).
