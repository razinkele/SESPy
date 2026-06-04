# URL Bookmarking (active-view) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a `?view=<nav_id>` URL reopen the app at a specific module, and keep that param in sync as the user navigates — so the address bar is a shareable link to the active view.

**Architecture:** A pure `parse_view` validator (`sespy/bookmark.py`); a shared `_goto` helper in `sespy/dashboard.py` that both existing nav/stepper handlers and a new restore effect call (`active_panel.set` + `ui.update_navs("main_nav", …)`); a one-shot read-on-load effect (per-session guard) that restores `?view` via `session.clientdata.url_search()`; an async write effect that pushes the active view to the client via `session.send_custom_message`; and an inline `shiny:connected` handler in `dashboard_page`'s `head_content` that does `history.replaceState`. View-only — `?lang` is out of scope (see spec §1.2/§1.4).

**Tech Stack:** Python 3.11+, Shiny for Python 1.6.x, pytest (+ pytest-playwright for e2e), the project's standalone Playwright e2e runner (`tests/run_e2e.py`).

**Spec:** `docs/superpowers/specs/2026-06-04-url-bookmarking-design.md` (rev. 4 — converged after 3 multi-agent reviews + Context7 Shiny-API validation).

---

## Pre-flight

Work on a feature branch (matches the SP1–SP4 pattern); commit per task; fast-forward to `main` at the end.

```bash
git checkout -b feat/url-bookmarking
git status   # confirm clean tree (on main, at HEAD)
```

All Python/pytest commands use the micromamba `shiny` env (per CLAUDE.md): `micromamba run -n shiny …`. Never bare `python`/`pytest`.

**Key facts (verified against the live code):**
- `dashboard_server(input, output, session, *, nav_items, initial="", stepper_steps, nav_to_step, translator)` lives at `sespy/dashboard.py:258`, builds `active_panel: reactive.value(initial)` (line 280), wires nav/stepper, and `return active_panel` (line 324). The restore + write effects go **inside** this function (it has `session`, `nav_items`, `active_panel` in scope).
- `_wire_nav_button` (`dashboard.py:327`) and `_wire_step_button` (`:340`) both already do `active_panel.set(x)` + `ui.update_navs("main_nav", selected=x, session=session)` — `_goto` factors exactly this pair.
- `dashboard_page` builds `head_content(...)` at `dashboard.py:238-248`, where `burger_js` (defined at `:217`) is passed. The new handler script goes here.
- `app.py:150` `server(...)` calls `dashboard_server(... initial="cld" ...)`; `app.py:138` `app_ui = dashboard_page(... initial="cld" ...)`. **No `app.py` change is needed.**
- jQuery `$` is globally available before `head_content`; `shiny:connected` fires before the client `init`, so the handler is registered before any `sespy_view_url` message (verified, spec §1.3).

---

## Task 1: `sespy/bookmark.py` — pure `parse_view` validator

**Files:**
- Create: `sespy/bookmark.py`
- Test: `tests/test_bookmark.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_bookmark.py`:

```python
"""Tests for sespy.bookmark.parse_view (URL bookmarking)."""
from sespy.bookmark import parse_view

VIEWS = {"cld", "metrics", "loops"}


def test_parse_view_valid():
    assert parse_view("?view=metrics", VIEWS) == "metrics"


def test_parse_view_no_leading_question_mark():
    assert parse_view("view=cld", VIEWS) == "cld"


def test_parse_view_not_in_valid_set_is_none():
    assert parse_view("?view=does_not_exist", VIEWS) is None


def test_parse_view_missing_key_is_none():
    assert parse_view("?lang=es", VIEWS) is None


def test_parse_view_empty_and_none_are_none():
    assert parse_view("", VIEWS) is None
    assert parse_view(None, VIEWS) is None


def test_parse_view_empty_value_is_none():
    assert parse_view("?view=", VIEWS) is None


def test_parse_view_repeated_first_valid_wins():
    assert parse_view("?view=metrics&view=cld", VIEWS) == "metrics"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny pytest tests/test_bookmark.py -v`
Expected: collection/ImportError — `sespy.bookmark` does not exist.

- [ ] **Step 3: Create `sespy/bookmark.py`**

```python
"""URL-bookmarking helpers (view-only). Pure — no Shiny imports."""
from __future__ import annotations

from urllib.parse import parse_qs


def parse_view(search: str | None, valid_views: set[str]) -> str | None:
    """Return the ?view value iff present AND in valid_views; else None.

    Tolerates a leading '?', None/empty input, missing/empty/repeated keys
    (first value wins). The client encodes when it sets the param, so there
    is no build_view counterpart — the server sends the raw view id.
    """
    if not search:
        return None
    values = parse_qs(search.lstrip("?")).get("view") or []
    view = values[0] if values else None
    return view if view in valid_views else None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny pytest tests/test_bookmark.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add sespy/bookmark.py tests/test_bookmark.py
git commit -m "feat(bookmark): add parse_view validator for ?view URL bookmarking"
```

---

## Task 2: `_goto` helper + route the two existing handlers through it

**Files:**
- Modify: `sespy/dashboard.py` (add `_goto`; refactor `_wire_nav_button:327` and `_wire_step_button:340`)

**Why:** A single switch-the-view helper, reused by nav clicks, stepper clicks, and (Task 3) URL restore. Pure refactor — no behaviour change; covered by the existing stepper/shell/full-app e2e.

- [ ] **Step 1: Add the `_goto` helper** to `sespy/dashboard.py`, immediately **above** `def _wire_nav_button(` (line 327):

```python
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
```

- [ ] **Step 2: Refactor `_wire_nav_button`** — replace its `_switch` body (lines 335-337):

```python
    @reactive.effect
    @reactive.event(input[item.input_id], ignore_init=True)
    def _switch():
        _goto(active_panel, session, item.id)
```

- [ ] **Step 3: Refactor `_wire_step_button`** — replace its `_switch` body (lines 350-352):

```python
    @reactive.effect
    @reactive.event(input[f"{STEP_INPUT_PREFIX}{step_id}"], ignore_init=True)
    def _switch():
        _goto(active_panel, session, target_nav)
```

- [ ] **Step 4: Verify the module imports and existing nav/stepper e2e still pass**

```
micromamba run -n shiny python -c "import sespy.dashboard, app; print('import OK')"
```
Expected: `import OK`.

Then confirm the refactor preserved behaviour by running the stepper + shell e2e against a live server:
```
# terminal 1: micromamba run -n shiny shiny run --port 8000 app.py
micromamba run -n shiny python tests/test_stepper.py
micromamba run -n shiny python tests/test_stepper_click.py
micromamba run -n shiny python tests/test_shell_e2e.py
```
Expected: each prints its "...assertions pass" line and exits 0.

- [ ] **Step 5: Commit**

```bash
git add sespy/dashboard.py
git commit -m "refactor(dashboard): factor nav/stepper view-switch into _goto helper"
```

---

## Task 3: Restore-on-load + write-on-change effects (inside `dashboard_server`)

**Files:**
- Modify: `sespy/dashboard.py` (`dashboard_server`, just before `return active_panel` at line 324)

- [ ] **Step 1: Add the restore + sync effects** — in `dashboard_server`, insert immediately **before** `return active_panel`:

```python
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
```

Notes for the implementer (do not paste as code):
- The restore effect reads **only** `url_search()` as a dependency (never `active_panel`, which would couple it to the write path). The guard is defensive — `replaceState` does not re-report `url_search`, so it cannot self-retrigger.
- The write effect is `async` because `session.send_custom_message` is a coroutine. It fires once on the initial flush (stamping `?view=<default>`, e.g. `?view=cld` — intended) and on every change. The transient default→target double-write on a `?view=metrics` load is harmless under `replaceState`.

- [ ] **Step 2: Verify the module + app import cleanly**

```
micromamba run -n shiny python -c "import sespy.dashboard, app; print('import OK')"
```
Expected: `import OK` (a `RuntimeError` here usually means an effect was placed at module level by mistake — it must be inside `dashboard_server`).

- [ ] **Step 3: Verify the app still boots and serves**

```
micromamba run -n shiny shiny run --port 8000 app.py   # then in another shell:
micromamba run -n shiny python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000', timeout=10).status)"
```
Expected: `200`. (Functional restore/sync behaviour is verified by the Task 5 e2e.)

- [ ] **Step 4: Commit**

```bash
git add sespy/dashboard.py
git commit -m "feat(dashboard): restore ?view on load + sync active view to URL"
```

---

## Task 4: Inline `shiny:connected` handler in `head_content`

**Files:**
- Modify: `sespy/dashboard.py` (`dashboard_page`: define `bookmark_js` near `burger_js:217`; add it to `head_content` at `:238-248`)

- [ ] **Step 1: Define `bookmark_js`** in `dashboard_page`, immediately **after** the `burger_js = ui.tags.script("""...""")` block (after line 230):

```python
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
```

- [ ] **Step 2: Add `bookmark_js` to `head_content`** — in the `ui.head_content(...)` call (line 238-248), add it after `burger_js,`:

```python
        ui.head_content(
            ui.tags.link(rel="stylesheet", href="sespy-skin.css"),
            ui.tags.link(rel="stylesheet", href="cld.css"),
            ui.tags.link(
                rel="stylesheet",
                href=("https://cdnjs.cloudflare.com/ajax/libs/font-awesome/"
                      "6.5.0/css/all.min.css"),
            ),
            burger_js,
            bookmark_js,
        ),
```

- [ ] **Step 3: Verify import + boot**

```
micromamba run -n shiny python -c "import app; print('import OK')"
```
Expected: `import OK`.

- [ ] **Step 4: Commit**

```bash
git add sespy/dashboard.py
git commit -m "feat(dashboard): inline shiny:connected handler to write ?view to the URL"
```

---

## Task 5: End-to-end test — restore (visibility) + sync (nav + stepper)

**Files:**
- Create: `tests/test_bookmark_e2e.py`

This standalone Playwright script (the project's e2e pattern: `asyncio.run(main())`, asserts on the live app at `http://127.0.0.1:8000`) is auto-discovered by `tests/run_e2e.py`.

- [ ] **Step 1: Write the e2e script** — create `tests/test_bookmark_e2e.py`:

```python
"""E2e: ?view restores the active module (panel visible, not just highlighted),
and the URL stays in sync on nav + stepper navigation."""
import asyncio
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8000"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})

        # --- Case 1: restore from ?view switches the PANEL, not just the highlight
        print("\n=== case 1: restore ?view=metrics shows the metrics panel ===")
        await page.goto(f"{BASE}/?view=metrics", wait_until="networkidle")
        # navset_hidden renders every panel into the DOM, so assert the metrics
        # tab-pane is ACTIVE (visible), not merely present.
        await page.wait_for_function(
            "() => { const el = document.querySelector(\"#main_nav .tab-pane[data-value='metrics']\");"
            " return !!el && el.classList.contains('active'); }",
            timeout=20000,
        )
        # URL settles on ?view=metrics (after any transient default->target write)
        await page.wait_for_function(
            "() => new URL(window.location).searchParams.get('view') === 'metrics'",
            timeout=10000,
        )
        print("  ok (metrics panel active + URL settled)")

        # --- Case 2: clicking a nav button updates the URL
        print("\n=== case 2: nav click updates ?view ===")
        await page.click("#sespy_nav_loops")
        await page.wait_for_function(
            "() => new URL(window.location).searchParams.get('view') === 'loops'",
            timeout=10000,
        )
        print("  ok (?view=loops)")

        # --- Case 3: stepper click tracks active_panel (real value change)
        # Navigate to metrics first so visualize->cld is a genuine change
        # (from the default cld, visualize->cld is a no-op the reactive.Value
        # identity check short-circuits).
        print("\n=== case 3: stepper visualize -> cld (real change) ===")
        await page.click("#sespy_nav_metrics")
        await page.wait_for_function(
            "() => new URL(window.location).searchParams.get('view') === 'metrics'",
            timeout=10000,
        )
        await page.click("#sespy_step_visualize")
        await page.wait_for_function(
            "() => new URL(window.location).searchParams.get('view') === 'cld'",
            timeout=10000,
        )
        print("  ok (?view=cld via stepper)")

        print("\nbookmark e2e assertions pass")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Run it against a live server**

```
# terminal 1: micromamba run -n shiny shiny run --port 8000 app.py   (wait for "Application startup complete")
micromamba run -n shiny python tests/test_bookmark_e2e.py
```
Expected: prints the three `ok` lines + "bookmark e2e assertions pass", exits 0.

If case 1 fails on the `active` class, confirm Task 3's restore calls `_goto` (not just `active_panel.set`) and that `#main_nav` panels carry `data-value="<nav_id>"` (inspect the DOM); if the panel selector differs, assert instead that `#metrics-metrics_network` `is_visible()` is True while the `cld` pane is hidden. If case 2/3 URL never updates, confirm the Task 4 handler registered (browser console: no "no handler for sespy_view_url" warning) and that Task 3's async write effect is `async def` + `await`s `send_custom_message`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_bookmark_e2e.py
git commit -m "test(e2e): ?view restore (panel visibility) + URL sync (nav + stepper)"
```

---

## Task 6: Full verification + merge

**Files:** (no modifications — verification only)

- [ ] **Step 1: Unit suite green (includes the new bookmark unit tests)**

```
micromamba run -n shiny pytest tests/ -q \
  --ignore-glob='*e2e*' --ignore=tests/test_burger.py \
  --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py
```
Expected: all pass (prior count + 7 new bookmark tests).

- [ ] **Step 2: Full e2e sweep green (the runner discovers `test_bookmark_e2e.py`)**

```
micromamba run -n shiny python tests/run_e2e.py
```
Expected: `23/23 e2e scripts passed, 0 failed` (22 prior + bookmark), 0 retries.

- [ ] **Step 3: Confirm clean tree + focused history**

```
git status                                   # clean
git log --oneline main..feat/url-bookmarking # ~5 focused commits
```

- [ ] **Step 4: Merge to main (fast-forward) and push**

```bash
git checkout main && git merge --ff-only feat/url-bookmarking
git push origin main          # triggers CI (unit + full-app + e2e)
git branch -d feat/url-bookmarking
```
Expected: CI green on all jobs (the e2e job now runs the bookmark e2e too).

---

## Self-review (author checklist — completed)

- **Spec coverage:** §1 in-scope (`?view` read + write) → Tasks 3-4; `parse_view` → Task 1; `_goto`/`ui.update_navs` → Task 2; unit tests → Task 1; e2e (restore visibility + nav + stepper-real-change) → Task 5; defer `?lang` → not implemented (correct). ✓
- **No placeholders:** every code step shows complete code; no TBD/TODO. ✓
- **Type/name consistency:** `parse_view(search, valid_views)` (Task 1) is called identically in Task 3; `_goto(active_panel, session, view)` defined in Task 2 and reused in Tasks 2-3; custom message type `"sespy_view_url"` matches between the write effect (Task 3) and the JS handler (Task 4); `active_panel`/`session`/`nav_items` are the real `dashboard_server` symbols. ✓
- **Codebase accuracy:** all file:line anchors verified against the live `sespy/dashboard.py` and `app.py`; no `app.py` change required. ✓
