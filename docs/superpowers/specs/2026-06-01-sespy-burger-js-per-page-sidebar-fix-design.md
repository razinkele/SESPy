# SESPy burger_js per-page sidebar fix — Design

**Date:** 2026-06-01
**Status:** Design — awaiting user review
**Scope class:** Focused bug fix in the shared shell + test + repo hygiene
**Repo:** `Marine-SABRES/SESPy` (the shared dashboard shell used by MosaicSES and other Marine-SABRES apps)

## 1. Problem

MosaicSES chunk-4c-ui added native bslib collapsible sidebars to per-page panels
(Topology, Cross-view). They render correctly but **do not collapse** when the
user clicks the chevron. Diagnosed live in the browser (2026-06-01):

- Clicking a per-page sidebar chevron toggles `body.sespy-sidebar-mini` (the
  OUTER nav's mini-mode) and leaves the per-page pane's `grid-template-columns`
  and the toggle's `aria-expanded` **unchanged** — the pane never collapses.
- Proven the reflow itself works: when the sidebar grid column is forced to
  collapse (`300px 397.6px` → `0px 1fr`), the main content cell goes
  `398px → 698px` (+300, the sidebar width). So the layout is sound; only the
  click is being stolen.

### Root cause

`sespy/dashboard.py` builds a `burger_js` script (lines ~217-230) that attaches
a **capture-phase** click listener on `document` matching **every**
`.collapse-toggle`, calls `stopImmediatePropagation()`, and toggles
`body.sespy-sidebar-mini`. Its guard is a **denylist**:

```js
var layout = btn.closest('.bslib-sidebar-layout');
if (!layout || layout.closest('.sespy-card')) return;   // skip toggles inside a .sespy-card
```

This was written when the OUTER nav `page_sidebar` was the *only*
`.bslib-sidebar-layout` not inside a `.sespy-card`. chunk-4c added per-page
`layout_sidebar`s that live in `main > tab-content > tab-pane` — also not inside
a `.sespy-card` — so the guard fails to exclude them. The denylist **fails
open**: any new sidebar anywhere gets hijacked unless it happens to be in a
`.sespy-card`.

### Confirmed facts (browser-verified, Chromium 145, rendered markup)

- The OUTER nav sidebar `<aside>` renders `class="sidebar sespy-sidebar"` (set at `dashboard.py:250` via `ui.sidebar(..., class_="sespy-sidebar")`). It does NOT carry `bslib-sidebar-input` (that token appears only on sidebars given an explicit `id=`). Both `sidebar` and `sespy-sidebar` are on the SAME element, and that `<aside>` is a DIRECT child of the `.bslib-sidebar-layout` — so `:scope > .sidebar.sespy-sidebar` matches it.
- Per-page sidebars render `class="sidebar bslib-sidebar-input"` (with an `id=`), do NOT carry `sespy-sidebar`, and their layout has no `.sespy-sidebar` child — so the allowlist guard returns null for them (verified).
- bslib's own collapse handler is bound on the toggle `<button>` in BUBBLE phase (`shiny/www/shared/bslib/.../components.min.js`). burger_js is bound on `document` in CAPTURE phase. So for a per-page toggle, burger_js's early `return` (before any `preventDefault`/`stopImmediatePropagation`) lets the event reach the button, where bslib's handler runs the native collapse. The "fall through" mechanism is therefore sound.
- Sidebar inventory across both repos (classification verified): OUTER nav → owns `.sespy-sidebar` → stays mini-mode; the 16 SESPy module sidebars → all wrapped in `.sespy-card` → already bslib-collapse, unchanged; the 4 MosaicSES per-page sidebars (topology list+inspector, cross-view filters) → not in a card, don't own `.sespy-sidebar` → currently hijacked (the bug), will bslib-collapse after fix. NO other sidebar's behavior changes.
- `tests/test_burger.py` exists but only exercises the OUTER toggle (it finds "the FIRST `.collapse-toggle` not in a `.sespy-card`"), so it passed throughout — the per-page half was never tested. NOTE: this selector becomes ambiguous once the demo per-page panel is added (see §5).

## 2. Goal & non-goals

**Goal:** A per-page sidebar's collapse chevron triggers bslib's native collapse
(graph reclaims width); the OUTER nav chevron still drives mini-mode. Guard the
behavior with a test so it can't silently regress again.

**Non-goals:**
- No change to the mini-mode behavior or appearance of the outer nav.
- No change to MosaicSES (the chunk-4c code is already correct; it's blocked only by this shell bug).
- No broader refactor of `dashboard.py`.
- No CSS/skin changes.

## 3. Approach

### 3.1 Invert the guard: denylist → allowlist

Change the guard so burger_js hijacks **only** the layout that owns the outer
nav sidebar (the unique `.sespy-sidebar` marker), and lets every other
`.collapse-toggle` fall through to bslib's native handler.

Current (`dashboard.py:224-225`):
```js
var layout = btn.closest('.bslib-sidebar-layout');
if (!layout || layout.closest('.sespy-card')) return;
```

Fixed:
```js
var layout = btn.closest('.bslib-sidebar-layout');
// Only the OUTER nav layout owns the .sespy-sidebar aside. Every other
// collapse-toggle (per-page layout_sidebars, cards, future sidebars) falls
// through to bslib's native collapse. Allowlist > denylist: fails closed.
if (!layout || !layout.querySelector(':scope > .sidebar.sespy-sidebar')) return;
```

**Why `:scope > .sidebar.sespy-sidebar`:** matches the outer layout's *direct*
sidebar child carrying `sespy-sidebar`, not any nested descendant — so a future
nested sidebar can't accidentally re-trigger mini-mode. The outer
`page_sidebar` renders its `<aside class="sidebar ... sespy-sidebar">` as a
direct child of the layout, so `:scope >` holds (verified in Chromium 145 — the
`<aside class="sidebar sespy-sidebar">` is a direct child).

**END-TO-END VERIFIED (round-2 review, real Chromium against `dashboard_page`):**
This exact allowlist makes a per-page toggle collapse correctly (grid
`300px 652px` → `0px 952px`, `aria-expanded` true→false, `body` NOT mini), while
the outer toggle still mini-modes (grid → `64px ...`) on desktop AND mobile, and
the 16 `.sespy-card` module sidebars still collapse natively. Critically,
**bslib initializes collapsible sidebars even inside hidden `navset_hidden`
tab-panes at page load** (`initCollapsibleAll()` runs on `DOMContentLoaded` with
no visibility filter), so removing the hijack is *sufficient* — there is no
second "dead toggle" blocker. This was the spec's biggest unstated risk; it is
now closed.

**Known design smell (accepted):** this reuses `.sespy-sidebar`, a *styling*
class, as a *behavioral* discriminator — if someone restyles and drops/renames
it, mini-mode silently breaks. A structural alternative exists and is arguably
sturdier: `if (!layout.matches('.bslib-page-sidebar > .bslib-sidebar-layout')) return;`
keys on bslib's own page-sidebar contract (and `test_burger.py` already uses that
exact `.bslib-page-sidebar > .bslib-sidebar-layout > .collapse-toggle` anchor for
the outer toggle). **Decision (per user: "decide at impl"):** the implementer
chooses at implementation time, with this guidance — PREFER the structural anchor
`layout.matches('.bslib-page-sidebar > .bslib-sidebar-layout')` (sturdier: keys
on bslib's own contract, not a SESPy style class, and is consistent with the
selector `test_burger.py` already uses). Fall back to the `.sespy-sidebar`
allowlist only if a runtime check shows the structural form does not match the
outer layout in this bslib version. The implementer's FIRST step is a 2-minute
runtime probe: boot the app and confirm which of the two selectors uniquely
matches the outer nav layout (and ONLY it), then commit to that one for both the
guard AND the test re-scope (§5) so they stay consistent. Whichever is chosen,
add the load-bearing-discriminator code comment from §3.1.

This is **one logic line plus two comment rewrites** (not "one line" — the
comments are load-bearing and MUST be corrected or they'll contradict the code).
Both stale comment regions describe the DENYLIST and become FALSE after the
inversion. Replace them VERBATIM:

**Outer block — replace current `dashboard.py:212-216`:**
```python
    # Hijack bslib's OUTER nav sidebar collapse-toggle: instead of bslib's
    # default full-hide animation, flip `body.sespy-sidebar-mini` so the sidebar
    # narrows to an icon-only strip (bs4Dash sidebar-mini behaviour). ONLY the
    # outer nav layout (identified by its `.sespy-sidebar` aside) is hijacked;
    # every other collapse-toggle (per-page layout_sidebars, .sespy-card module
    # sidebars, any future sidebar) falls through to bslib's native collapse.
```
**Inner comment — replace current `dashboard.py:221-223` (the two lines starting
`// Only the OUTER sidebar's toggle...`):**
```javascript
          // Allowlist: hijack ONLY the layout that owns the outer nav's
          // .sespy-sidebar aside. .sespy-sidebar is now LOAD-BEARING FOR
          // BEHAVIOR (not just styling) — do not drop/rename it without
          // updating this guard. All other toggles fall through to bslib.
```
(If the structural-anchor alternative is chosen, adjust both comments and the
guard line accordingly — same intent, different discriminator.)

### 3.2 Make the demo app exercise a per-page sidebar

SESPy's demo `app.py` uses `nav_panel`s but has **no** per-page
`layout_sidebar`, so there is nothing to test the fix against. Add one small
demo panel whose purpose is to exercise the shell feature:

```python
ui.nav_panel(
    "Sidebar Demo",
    ui.layout_sidebar(
        ui.sidebar(
            ui.markdown("Demo per-page sidebar — collapse me; the content "
                        "area should widen and stay interactive."),
            id="demo_page_sb",
            title="Demo Filters",
            position="left",
            open="desktop",
            width=300,
        ),
        ui.div(
            "Per-page sidebar demo content.",
            id="demo_page_content",
        ),
    ),
    value="sidebar_demo",
),
```

This requires **three coordinated edits** in `app.py` (not just the panel):
1. Add the `ui.nav_panel(..., value="sidebar_demo")` above to the `PANELS` tuple.
2. Add a matching `NavItem(id="sidebar_demo", icon=..., label="Sidebar Demo")` to
   the `NAV` list — `NavItem.id` MUST equal the panel's `value` so the nav button
   `#sespy_nav_sidebar_demo` drives `ui.update_navs("main_nav", selected="sidebar_demo")`.
3. `NAV_TO_STEP` — DELIBERATELY omit `sidebar_demo` (an unmapped nav id is
   tolerated: `_render_stepper` handles `current_idx = -1`). State this so the
   omission isn't mistaken for an oversight.

`NavItem` requires `id`, `icon`, `label` (and optional `label_key`). Use a
concrete icon and NO `label_key` (English-only — consistent with the inert-demo
intent and §2 non-goals; do NOT add translation keys):
```python
NavItem(id="sidebar_demo", icon="square-poll-horizontal", label="Sidebar Demo")
```
Place the demo panel LAST in BOTH `PANELS` and `NAV` so it doesn't interrupt the
workflow ordering (it lands after the terminal "Report" step — harmless,
NAV_TO_STEP-unmapped).
This panel is inert (no server logic) — its only job is to give `test_burger.py`
a real per-page sidebar + stable `#demo_page_sb` / `#demo_page_content` to assert
against. (`open="desktop"` so it starts open at the test's 1280px viewport,
making the "collapse then re-expand" assertions meaningful.)

### 3.3 Version-control SESPy first (prerequisite)

SESPy is currently **not a git repository** (`git rev-parse` → not a work tree),
yet it is the shared shell under every Marine-SABRES app. Before editing the
shared shell, initialize git so this and all future changes are revertible and
reviewable:

1. `git init` in the SESPy root. (Verified safe: no parent/ancestor dir is a git
   repo, so this creates no nested/embedded repo. MosaicSES is a sibling repo,
   not a parent.)
2. The repo has a good `.gitignore` (covers `__pycache__`, `.pytest_cache`,
   `.mypy_cache`, `tests/screenshots/`, the stray `0]` / `e.id)')` /
   `_verify_*.py` artifacts, `*.egg-info/`, and `.claude/local/`) — BUT it does
   NOT cover `.tmp/`, which holds ~20 developer scratch files (logs, render
   probes). **Add `.tmp/` to `.gitignore` before `git init`.** (Verified: no
   secrets/API keys in `data/` or config — `data/` is only `sample_ses.json`;
   the gap is scratch clutter, not secrets.)
3. **Show `git status` and get user confirmation BEFORE the first commit** — do
   not commit blind. Confirm no large data files, secrets, or junk are staged.
4. Initial commit = the current state (pre-fix baseline), so the fix lands as a
   clean, revertible diff on top.

## 4. Components / files touched

- `sespy/dashboard.py` — `burger_js` guard: 1 logic line + 2 comment rewrites (§3.1). The only behavioral change.
- `app.py` — add one "Sidebar Demo" panel via 3 coordinated edits (PANELS + NAV + NAV_TO_STEP-omission). Demo-only, inert.
- `tests/test_burger.py` — RE-SCOPE the outer-toggle selector at ALL THREE call sites (click ~lines 35-40, toggle-back ~77-82, grid-check `.find()` ~60-62) AND add Half B (§5). Also add the `if __name__ == "__main__":` guard.
- `.gitignore` — add `.tmp/`.
- New: `.git/` (via `git init`) + initial baseline commit.
- New: `docs/superpowers/specs/2026-06-01-sespy-burger-js-per-page-sidebar-fix-design.md` (this file) + the plan.

## 5. Testing

`test_burger.py` is a standalone Playwright script (`asyncio.run(main())`) that
drives a manually-booted app on `http://127.0.0.1:8000`. Extend it to assert the
**two-part contract**.

**CRITICAL test-interaction (must fix, or adding the demo panel breaks the
existing test):** Half A currently selects the outer toggle as "the FIRST
`.collapse-toggle` whose layout is NOT inside a `.sespy-card`." Once the demo
per-page panel is added, the demo's toggle ALSO satisfies that predicate (it's
not in a `.sespy-card`), so Half A could click the wrong toggle (DOM-order
dependent) and its `"64" in grid_cols` assertion could fail on the demo layout
(grid `300px 1fr`, never 64px). Therefore Half A's selector MUST be re-scoped to
the `.sespy-sidebar`-owning layout — the same identity the fix uses:
```js
const outerLayout = [...document.querySelectorAll('.bslib-sidebar-layout')]
  .find(el => el.querySelector(':scope > .sidebar.sespy-sidebar'));
const outerToggle = outerLayout.querySelector(':scope > .collapse-toggle');
```
Bonus: this makes Half A also fail loudly if `:scope >` ever stops matching,
self-validating the fix's selector. **Apply this re-scope at ALL THREE existing
call sites** in `test_burger.py` that currently use the `!closest('.sespy-card')`
pattern: the click loop (~lines 35-40), the toggle-back loop (~77-82), and the
grid-check `.find()` (~60-62). Missing any one leaves a fragile assertion.

**Half A — OUTER nav toggle still drives mini-mode (re-scoped, NOT "unchanged"):**
- Select the outer toggle via the `.sespy-sidebar`-owning layout (above).
- Assert `body` gains `sespy-sidebar-mini`, nav grid shrinks to ~64px, labels
  hidden, second click removes the class.

**Half B — per-page toggle is NOT hijacked, bslib collapse runs (NEW):**
- `await page.wait_for_selector("#sespy_nav_sidebar_demo")` (the nav button is
  rendered by a server `@render.ui`, not present at raw page load), then click it.
- `await page.wait_for_selector("#demo_page_content", state="visible")` — all
  panels are in the DOM at load via `navset_hidden`, so the demo sidebar exists
  while HIDDEN; clicking its toggle while the pane is `display:none` yields
  meaningless geometry. Wait for the pane to become visible first.
- Select the demo toggle SCOPED to the demo layout (never a bare
  `querySelector('.collapse-toggle')`, which returns the outer toggle first):
  `document.getElementById('demo_page_content').closest('.bslib-sidebar-layout').querySelector(':scope > .collapse-toggle')`.
- Record `aria-expanded` (expect `"true"`) and the demo layout's
  `grid-template-columns` BEFORE clicking.
- Click the demo toggle, then `wait_for_function` until the toggle's
  `aria-expanded === "false"` (animation-tolerant — do NOT use a fixed sleep).
- **Authoritative assertions** (these two are the reliable collapse signals):
  - `body` does **NOT** contain `sespy-sidebar-mini` (proves burger_js did not
    steal the click — this is the assertion that FAILS on the buggy code and
    passes on the fix);
  - the toggle's `aria-expanded === "false"` AND the demo layout's
    `grid-template-columns` first track parses to `< 5px`. (The demo uses a LEFT
    sidebar so the FIRST track collapses to ~0. A RIGHT sidebar — e.g.
    MosaicSES's topology Inspector — shrinks the LAST track instead; do not
    reuse "first track < 5px" for right sidebars. Demo is left → correct here.)
  - (Content-cell width MAY be logged as informational, but is NOT an assertion —
    width is flaky mid-transition. Also: pyvis's resize handler calls
    `setSize`+`redraw` but NOT `fit()`, so a real graph's canvas widens without
    auto-re-zoom — expected; see §5 manual smoke.)
- Click again → `wait_for_function` `aria-expanded === "true"`; assert the column
  returns. Confirms bidirectional.

**Why Half B catches the bug:** on the buggy denylist code, clicking the demo
toggle DOES toggle `body.sespy-sidebar-mini` (the guard doesn't exclude it), so
"body NOT mini" fails — true red. On the fixed allowlist code, burger_js ignores
it and bslib collapses the pane — green.

**Run procedure + automation caveat:** this file ends in a bare module-level
`asyncio.run(main())` with NO `test_`-prefixed function, so `pytest` would run it
at COLLECTION and error unless an app is already live on :8000. It is therefore a
**manual ship-gate, not an automated CI guard.** Minimum: guard the entry as
`if __name__ == "__main__": asyncio.run(main())` so it doesn't break suite
collection. The plan MUST document the run procedure explicitly (boot
`micromamba run -n shiny shiny run app.py`, then `python tests/test_burger.py`)
and list it as a required manual step — otherwise the regression can silently
return because nothing automated catches it. (Converting to a pytest
subprocess-fixture test is the proper fix but is out of scope per §7.)

### Manual smoke (ship gate, per `[[feedback_runtime_verify_before_shared_state]]`)

The SESPy Half-B test proves ONLY "click no longer hijacked + bslib grid
collapses" on a flat, pyvis-free demo sidebar. It does NOT prove the user-facing
property (pyvis canvas re-fits and stays non-zero), nor the MosaicSES-specific
cases (nested topology sidebars, full_screen card, ResizeObserver reflow). Those
are verified ONLY by the MosaicSES smoke — by design.

**MosaicSES picks up this fix automatically:** `sespy` is installed editable
(`pip show sespy` → "Editable project location" = the SESPy tree;
`python -c "import sespy; print(sespy.__file__)"` points into SESPy source). The
`dashboard.py` edit is live in MosaicSES with NO reinstall. Confirm that
`sespy.__file__` resolves into the SESPy source tree once before smoking.

Run the existing **`MosaicSES/docs/2026-05-30-chunk4c-ui-smoke-checklist.md`**
end-to-end (do not eyeball ad-hoc — it already has the right gates):
- Topology Compartments/Inspector chevrons collapse; **canvas `offsetWidth` AND
  `offsetHeight` both non-zero** after collapse-both and after
  full-screen-while-collapsed (checklist line 9 — the C2 height hazard).
- Cross-view Filters chevron collapses; composite canvas non-zero + widens.
- Outer MosaicSES nav burger still mini-modes.
- Expect: canvas WIDENS but the graph does not auto-re-zoom (pyvis `setSize`
  without `fit()`) — that is expected, not a regression.
This is the cross-app confirmation that the shared-shell fix unblocks chunk-4c.

## 6. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `:scope >` doesn't match the aside | Very low | VERIFIED matching in Chromium 145 (aside is a direct child with both classes); equivalent descendant fallback documented in §3.1; re-scoped Half A fails loudly if it ever breaks |
| Editing shared shell breaks another app's mini-mode | Low | Verified sidebar inventory: only the 4 MosaicSES per-page sidebars change behavior; 16 SESPy module sidebars (in `.sespy-card`) and the outer nav are unaffected. Half A guards the outer-toggle contract |
| Adding the demo panel breaks the EXISTING Half A test | **Med (certain if unaddressed)** | §5 re-scopes Half A's selector to the `.sespy-sidebar`-owning layout — this is a REQUIRED edit, not optional |
| Regression silently returns because the test isn't automated | Med | §5 documents it as a manual ship-gate + `if __name__=="__main__"` guard; plan lists the run procedure as a required step. (Full pytest-fixture conversion deferred, §7) |
| `git init` captures unwanted files | Low | `.gitignore` is good but MISSING `.tmp/` — §3.3 adds it first; mandatory `git status` review before first commit; verified no secrets in `data/`/config |
| Demo panel adds noise to the demo app | Very low | Inert, labeled "Sidebar Demo", placed last in NAV so it doesn't interrupt workflow ordering |

## 7. Ship handoff (concrete sequence to actually unblock chunk-4c)

"Spec done" ≠ "chunk-4c shipped." After implementation, execute in order:

1. **SESPy:** `git init` + `.gitignore` `.tmp/` add + `git status` review (user
   confirm) + baseline commit, THEN the fix commit (guard + comments + demo
   panel + test).
2. **SESPy ship-gate:** boot `micromamba run -n shiny shiny run app.py`, run
   `python tests/test_burger.py` — both Half A and Half B pass.
3. **Confirm linkage:** `python -c "import sespy; print(sespy.__file__)"` resolves
   into the SESPy source tree (editable install → fix is live in MosaicSES).
4. **MosaicSES cross-app smoke:** run `MosaicSES/docs/2026-05-30-chunk4c-ui-smoke-checklist.md`
   end-to-end against the patched shell — the canvas-non-zero + collapse-widens
   gates are the real user-facing proof.
5. **Decide** what to do with MosaicSES's pre-existing uncommitted `.gitignore`
   edit (user-managed — leave untouched per chunk-4b/4c precedent).
6. **MosaicSES:** `git push origin main` (the 7 held chunk-4c commits) — ONLY
   after step 4 is green.

## 8. Out of scope / follow-ups

- Converting SESPy's standalone Playwright scripts to pytest fixtures (broader
  test-infra change) — not now; the §5 `if __name__=="__main__"` guard is the
  minimum to keep them from breaking pytest collection.
- Pyvis `fit()`-on-resize (auto-re-zoom the graph to reclaimed width) — a UX
  nicety, not required for chunk-4c; out of scope.
- The structural-anchor alternative for the guard (§3.1) if the user prefers it
  over the `.sespy-sidebar` discriminator — a one-line swap, decide at impl time.
