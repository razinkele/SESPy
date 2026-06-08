# SESPy burger_js per-page sidebar fix — Implementation Plan

**Status:** ✅ **Completed** (2026-06-08 · all 4 tasks done, 1 commit shipped: `9977aba`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make per-page bslib collapsible sidebars actually collapse, by replacing SESPy's `burger_js` (a fragile document-level capture filter that hijacks *every* `.collapse-toggle`) with an init-time listener bound to ONLY the outer nav layout, identified by a dedicated behavioral marker — so per-page sidebar toggles fall through to bslib's native collapse while the outer nav still mini-modes.

**Architecture:** The current `burger_js` listens at document/capture on every click, walks the DOM, and uses a denylist (`skip if in .sespy-card`) that *fails open* — per-page `layout_sidebar`s (in `main > tab-pane`, not in a card) get hijacked too. The fix: at page load, resolve the outer nav layout once via a dedicated marker class `sespy-nav-shell` (added to the nav `ui.sidebar`), attach a capture-phase click listener **on that layout** (an ancestor of its toggle, so it still pre-empts bslib's target-phase handler), and act ONLY when the clicked toggle's *nearest* `.bslib-sidebar-layout` IS the nav layout. This removes the styling-class-as-behavior coupling (`.sespy-sidebar`) and the global every-click filtering. **Per the user's decisions: (a) trim hard — no demo panel, no Playwright test rewrite, no probe task; rely on the existing `test_burger.py` for the outer-nav mini-mode contract and the MosaicSES smoke checklist for per-page collapse; (b) do the sturdier bind-at-init fix, not the one-line denylist swap.**

**Tech Stack:** Python, Shiny for Python 1.6.1 (bslib `page_sidebar`/`layout_sidebar`), vanilla JS (the `burger_js` string), Playwright (existing standalone script only), git.

**Spec:** `SESPy/docs/superpowers/specs/2026-06-01-sespy-burger-js-per-page-sidebar-fix-design.md` (note: spec describes the one-line allowlist; this plan implements the sturdier bind-at-init variant the user chose at impl time — same behavior, better architecture).

**Repo:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy` — already a git repo (versioned 2026-01 onward). Shared shell; `MosaicSES` consumes it via an editable install (`pip show sespy` → Editable project location = this tree), so edits are live in MosaicSES with no reinstall.

**Environment:** all commands run via the **Bash tool** (POSIX-style; `grep`/`rm`/`curl`/`netstat` work there, not in PowerShell). Python in the `shiny` micromamba env: prefix with `micromamba run -n shiny`.

**The fix is BROWSER-VERIFIED.** This exact architecture was spiked against the live MosaicSES app (which has both the outer nav and real per-page sidebars) and confirmed: outer-nav toggle → `body.sespy-sidebar-mini` set (our capture wins the race against bslib); Topology per-page toggle → `aria-expanded` true→false, grid first track 300px→0px (native collapse), `body` mini-class untouched. The spike was reverted; this plan re-applies it cleanly.

**Running the app (Task 2 verification + Task 4 smoke) — single-channel/subagent procedure.**
`shiny run` is FOREGROUND/blocking — never run it as a foreground tool call (it hangs the channel). Use this triad:
1. Sweep stale server first (Bash): `netstat -ano 2>/dev/null | grep -E ':8000\s.*LISTENING' | awk '{print $5}' | sort -u | xargs -r -I{} taskkill //PID {} //F 2>/dev/null; echo swept`
2. Start in BACKGROUND (Bash tool, `run_in_background: true`): `micromamba run -n shiny shiny run app.py --host 127.0.0.1 --port 8000` — note the shell id.
3. Poll until ready (Bash): `for i in $(seq 1 30); do curl -s -o /dev/null http://127.0.0.1:8000 && { echo ready; break; }; sleep 1; done`
4. Run the script / drive the browser.
5. Sweep again (step 1) to kill the server.

---

## Task 0: Version-control SESPy (prerequisite)

SESPy is the shared shell and unversioned. Initialize git so the fix is a clean, revertible diff and the spec+plan land in a baseline. Verified safe: no parent dir is a git repo (no nested-repo risk); `data/` holds only `sample_ses.json` (no secrets).

**Files:** `.gitignore` (add `.tmp/`); new `.git/` + baseline commit.

- [ ] **Step 1: Add `.tmp/` to `.gitignore`**

The existing `.gitignore` covers caches, `tests/screenshots/`, stray artifacts, `*.egg-info/` — but NOT `.tmp/` (dev scratch). Append:
```gitignore

# Developer scratch (probes, logs, render dumps)
.tmp/
```

- [ ] **Step 2: Initialize**
```bash
git init
git add -A
```

- [ ] **Step 3: Review staged set BEFORE committing (mandatory gate)**

Automated check (Bash tool — deny-list must have ZERO staged matches):
```bash
git status --short | grep -E '(^|/)(\.tmp/|__pycache__/|\.pytest_cache/|\.mypy_cache/|.*\.egg-info/|tests/screenshots/|0\]|e\.id)' && echo "DENYLIST HIT — STOP" || echo "staged set clean"
```
Expected: `staged set clean`. If `DENYLIST HIT`, fix `.gitignore`, `git rm --cached <path>`, re-run until clean.

**Human gate:** this is the first-ever commit to a shared shell. ALSO surface the full `git status --short` to the user and get explicit go-ahead before Step 4. A subagent MUST pause and report the staged set, not auto-commit.

- [ ] **Step 4: Baseline commit**
```bash
git commit -m "chore: initial commit — SESPy shared shell (pre burger_js fix baseline)"
```
Run `git log --oneline -1` — expect the baseline as HEAD.

---

## Task 1: Add the `sespy-nav-shell` marker + the bind-at-init `burger_js`

Replace the document-level denylist filter with an init-time listener bound to the outer nav layout, and tag the nav sidebar with a dedicated behavioral marker. Both edits are in `sespy/dashboard.py`; they go together (the JS depends on the marker).

**Files:**
- Modify: `sespy/dashboard.py` — the nav `ui.sidebar` class (line ~250) AND the `burger_js` block (lines ~212-230)

- [ ] **Step 1: Add the marker class to the outer nav sidebar**

In `sespy/dashboard.py`, the `page_sidebar` call (line ~250) currently reads:
```python
            ui.sidebar(*sidebar_children, width=280, class_="sespy-sidebar"),
```
Change the class to add the marker:
```python
            ui.sidebar(*sidebar_children, width=280, class_="sespy-sidebar sespy-nav-shell"),
```
(`sespy-sidebar` stays for styling; `sespy-nav-shell` is the NEW behavioral marker the JS keys on — keeping styling and behavior decoupled.)

- [ ] **Step 2: Replace the `burger_js` block**

The current block (lines ~212-230) is:
```python
    # Hijack bslib's OUTER sidebar collapse-toggle: instead of bslib's default
    # full-hide animation, flip `body.sespy-sidebar-mini` so the sidebar
    # narrows to an icon-only strip (bs4Dash sidebar-mini behaviour). The
    # inner sidebar toggle (inside .sespy-card) is left alone — bslib's
    # default fully-collapse is what we want there.
    burger_js = ui.tags.script("""
        document.addEventListener('click', function(e) {
          var btn = e.target.closest('.collapse-toggle');
          if (!btn) return;
          // Only the OUTER sidebar's toggle drives mini mode. The toggle is
          // a child of .bslib-sidebar-layout; the outer one is at page
          // level (not nested inside a .sespy-card).
          var layout = btn.closest('.bslib-sidebar-layout');
          if (!layout || layout.closest('.sespy-card')) return;
          e.preventDefault();
          e.stopImmediatePropagation();
          document.body.classList.toggle('sespy-sidebar-mini');
        }, true);  // capture phase, before bslib's own handler
    """)
```
Replace it ENTIRELY with (browser-verified form):
```python
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
```

- [ ] **Step 3: Sanity-check the shell still imports**

Run: `micromamba run -n shiny python -c "import sespy.dashboard; print('dashboard import OK')"`
Expected: `dashboard import OK`, no exception.

- [ ] **Step 4: Commit**
```bash
git add sespy/dashboard.py
git commit -m "fix(sespy): bind mini-mode to nav layout only; per-page sidebars collapse natively"
```

---

## Task 2: Verify both halves in the real app (browser)

No new automated test (per the trim decision). Verify the behavior directly in MosaicSES (the real consumer with both an outer nav and per-page sidebars) using a short throwaway probe, then delete it. This re-confirms the spike result on the committed code.

**Files:** new (scratch, deleted at end): `.tmp/verify_fix.py`

- [ ] **Step 1: Write the verification probe**

Create `.tmp/verify_fix.py`:
```python
"""Verify burger fix against MosaicSES (boot it first per the 'Running the app' triad)."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1400, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Half A: outer nav toggle → mini-mode (our capture wins the race)
        await page.evaluate("""() => {
          const lay = document.querySelector('.sidebar.sespy-nav-shell').closest('.bslib-sidebar-layout');
          lay.querySelector(':scope > .collapse-toggle').id = 'v-outer';
        }""")
        await page.click('#v-outer')
        await page.wait_for_timeout(800)
        mini_a = await page.evaluate("() => document.body.classList.contains('sespy-sidebar-mini')")
        assert mini_a is True, "Half A FAILED: outer toggle did not set mini-mode"
        print("Half A pass — outer nav mini-mode")

        # Half B: per-page Topology toggle → bslib collapse, NOT hijacked
        await page.click('#sespy_nav_topology')
        await page.wait_for_selector('#topology-topology_list_sb', timeout=10000)
        await page.evaluate("""() => {
          const lay = document.getElementById('topology-topology_list_sb').closest('.bslib-sidebar-layout');
          lay.querySelector(':scope > .collapse-toggle').id = 'v-perpage';
        }""")
        before_mini = await page.evaluate("() => document.body.classList.contains('sespy-sidebar-mini')")
        await page.click('#v-perpage')
        await page.wait_for_timeout(1500)
        res = await page.evaluate("""() => {
          const lay = document.getElementById('topology-topology_list_sb').closest('.bslib-sidebar-layout');
          const tog = lay.querySelector(':scope > .collapse-toggle');
          return {
            aria: tog.getAttribute('aria-expanded'),
            firstTrack: parseFloat(getComputedStyle(lay).gridTemplateColumns.split(' ')[0]),
            mini: document.body.classList.contains('sespy-sidebar-mini'),
          };
        }""")
        print("Half B result:", res)
        assert res["aria"] == "false", "Half B FAILED: per-page sidebar did not collapse (aria)"
        assert res["firstTrack"] < 5, f"Half B FAILED: column did not collapse, got {res['firstTrack']}px"
        assert res["mini"] == before_mini, "Half B FAILED: per-page click changed nav mini-mode (hijack regression)"
        print("Half B pass — per-page native collapse, no hijack")

        print("\nALL VERIFIED")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Boot MosaicSES + run the probe**

Boot MosaicSES per the "Running the app" triad (sweep → background `cd .../MosaicSES && shiny run app.py` → poll ready). Then:
`micromamba run -n shiny python .tmp/verify_fix.py`
Expected: `Half A pass`, `Half B pass`, `ALL VERIFIED`, exit 0. If Half B fails, the fix didn't take (check `sespy.__file__` points into the SESPy source tree — editable install). Sweep the server after.

- [ ] **Step 3: Clean up**

`rm .tmp/verify_fix.py`. (Scratch only — no commit. `.tmp/` is gitignored from Task 0.)

---

## Task 3: Confirm the existing `test_burger.py` still passes (outer-nav contract intact)

The existing `tests/test_burger.py` exercises the OUTER nav mini-mode. The fix changes how that listener is wired, so confirm it still passes — this is the retained regression guard for mini-mode. Note: its toggle selector (`.bslib-sidebar-layout > .collapse-toggle` filtered by `!closest('.sespy-card')`) still uniquely finds the outer toggle because we did NOT add any per-page sidebar to the demo app (trim decision) — the demo app's only `.bslib-sidebar-layout` is still the outer nav.

**Files:** none (run-only); update `tests/test_burger.py` ONLY if it fails for a selector reason (see Step 2).

- [ ] **Step 1: Run the existing test**

Boot the SESPy demo app per the triad (`cd .../SESPy && shiny run app.py`), then:
`micromamba run -n shiny python tests/test_burger.py`
Expected: `all burger assertions pass`, exit 0.

- [ ] **Step 2: If (and only if) it fails**

If it fails because the outer-toggle selector no longer resolves (it shouldn't — the demo app is unchanged), re-scope its outer-toggle lookup to the marker: replace the `!t.closest('.sespy-card')` filter with selecting the toggle whose layout owns `:scope > .sidebar.sespy-nav-shell`. Commit any such change:
```bash
git add tests/test_burger.py
git commit -m "test(sespy): point burger test at sespy-nav-shell marker"
```
If it passes unchanged (expected), no commit needed.

---

## Task 4: Cross-app smoke (MosaicSES) + ship handoff

The fix is browser-verified (Task 2) and the mini-mode contract is guarded (Task 3). Now the user runs the full MosaicSES chunk-4c smoke (covers pyvis reflow, nested sidebars, full-screen — things the SESPy-level checks don't), then ships the held chunk-4c commits.

**Files:** none (verification + git only).

- [ ] **Step 1: Confirm editable linkage**

`micromamba run -n shiny python -c "import sespy; print(sespy.__file__)"`
Expected: a path INTO the SESPy source tree. If it points into `site-packages/`, STOP — the fix won't reach MosaicSES; escalate.

- [ ] **Step 2: User runs the MosaicSES chunk-4c smoke**

Boot MosaicSES (triad). Walk `MosaicSES/docs/2026-05-30-chunk4c-ui-smoke-checklist.md`. Load-bearing items:
- Topology: collapse Compartments chevron → canvas widens; collapse Inspector → widens; **DevTools: `document.querySelector('#topology-network canvas')` has non-zero `offsetWidth` AND `offsetHeight`** after collapse-both and full-screen.
- Cross-view: collapse Filters → composite widens.
- Outer MosaicSES nav burger still mini-modes.
- Expected (NOT a regression): canvas widens but graph doesn't auto-re-zoom (pyvis `setSize` without `fit()`).

Manual gate (per `[[feedback_runtime_verify_before_shared_state]]`) — the user runs it. If a pane doesn't collapse or a canvas reads 0-height, STOP and report.

- [ ] **Step 3: Ship chunk-4c (only after Step 2 green, user go-ahead)**

The 7 chunk-4c commits sit on MosaicSES local `main` (HEAD `1dcdc42`, 7 ahead of origin); the pre-existing uncommitted `.gitignore` edit is intentional — leave it. With smoke green:
```bash
# in MosaicSES
git push origin main
```
Optionally tag `chunk-4c-ui-shipped`. User's shared-state action — do not push without explicit go-ahead.

---

## Definition of done

- [ ] SESPy is a git repo; `.tmp/` ignored; baseline + fix commits present.
- [ ] `sespy/dashboard.py`: nav sidebar carries `sespy-nav-shell`; `burger_js` binds at init to the nav layout with the identity check; no `.sespy-card` denylist remains.
- [ ] Task 2 probe printed `ALL VERIFIED` (Half A mini-mode + Half B per-page native collapse, no hijack).
- [ ] Existing `tests/test_burger.py` passes (outer-nav mini-mode guard intact).
- [ ] MosaicSES smoke green (per-page collapse works, canvas non-zero, outer mini-mode intact).
- [ ] chunk-4c's 7 commits pushed to origin (user go-ahead).

## Spec-coverage / decision self-check

- Spec §3 guard fix → Task 1 (implemented as the sturdier bind-at-init variant per user's "do the sturdier fix now" decision, not the spec's one-line allowlist).
- Spec §3.2 demo panel → DROPPED per user's "trim hard" decision; verification uses MosaicSES's real per-page sidebars (Task 2) instead of a SESPy demo panel.
- Spec §5 test → reduced to: keep existing `test_burger.py` (Task 3) + a throwaway verification probe (Task 2) + MosaicSES smoke (Task 4). No permanent SESPy Playwright rewrite.
- Spec §3.3 git init + `.tmp/` + status gate → Task 0.
- Spec §7 ship handoff → Task 4.

## Consistency self-check

- Marker `sespy-nav-shell` is added to the nav sidebar (Task 1 Step 1) AND keyed by the JS (Task 1 Step 2) AND used in the verification probe (Task 2) — same string everywhere.
- The fix is the exact JS spiked + browser-verified (outer mini-mode wins race; per-page collapses via `=== layout` identity check; mini-class untouched on per-page click).
- No demo panel, no `app.py` edit, no NAV/PANELS/NAV_TO_STEP change (trim decision) — so the existing `test_burger.py` selector stays valid (Task 3).
