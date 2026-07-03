# Network Loading Spinner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a centered spinner over every pyvis network output while it builds, auto-hidden the moment the graph is drawn — in both the SESPy and MosaicSES apps.

**Architecture:** A pure-CSS spinner rendered as `::before`/`::after` pseudo-elements on the `.pyvis-network-output` element, toggled by an `is-loading` class. A short shell script (`sespy/dashboard.py`) adds the class on Shiny's `shiny:recalculating` event and removes it on the fork's always-sent `<id>_ready` input (with an 8 s fallback). Pseudo-elements + a class are used (not an injected `<div>`) because the fork runs `el.innerHTML = ''` on every render, which would destroy an injected child. The CSS is mirrored into both apps' separate `www/sespy-skin.css` copies.

**Tech Stack:** Python Shiny, the razinka `pyvis.shiny` 4.2 fork (vis-network 10.0.2), vanilla JS + jQuery (`$` present), CSS. Tests: standalone Playwright e2e scripts run via `tests/run_e2e.py`.

## Global Constraints

- Python env: run everything through the existing micromamba env — `micromamba run -n shiny …`. Do NOT create venvs or `pip install`.
- Spinner CSS goes in BOTH `SESPy/www/sespy-skin.css` and `MosaicSES/www/sespy-skin.css` (the apps serve separate copies; the SESPy JS reaches MosaicSES via the editable `sespy` install, but the CSS does not).
- Hide signal is the fork's `<id>_ready` input (always sent, every render, physics-independent — `bindings.js:836`), NOT `_stabilized` (which never fires for the physics-off CLD view).
- Do NOT inject a child node into `.pyvis-network-output`; the fork's `innerHTML=''` (`bindings.js:90`) would wipe it. Use pseudo-elements + the `is-loading` class (both survive `innerHTML=''`).
- Spinner pseudo-element z-index MUST be below `1000` (the fork's `.pyvis-modal-overlay`) so node/edge modals stay on top. Use 5 (veil) / 6 (ring).
- Pseudo-elements MUST be `pointer-events: none` so they never block the canvas.
- e2e asserts the END state only (sticky show-marker present + not stuck loading); never race to catch the transient visible spinner (condition-based-waiting lesson from the leverage/simulation de-flake).
- ruff is blocking in CI; `tests/**` already ignores E402/E501. Keep `ruff check` clean.
- Overlay label text is exactly `Rendering network…` (real ellipsis, U+2026 — in CSS written as the escape `\2026`). Fallback timeout is exactly `8000` ms.

---

## File Structure

- `sespy/dashboard.py` — add `network_spinner_js = ui.tags.script(...)` next to `theme_js`, include it in the existing `ui.head_content(...)`. Class-toggle behavior only. Ships to both apps via the editable `sespy` install.
- `tests/test_cld_e2e.py` — extend the existing CLD e2e with sticky-marker + not-stuck assertions. CI-gated. Depends only on the JS (Task 1), not the CSS.
- `www/sespy-skin.css` (SESPy) and `../MosaicSES/www/sespy-skin.css` — `position: relative` on `.pyvis-network-output` + the `.is-loading::before`/`::after` spinner styles. Identical block in both. Visual; smoke-verified.
- `docs/2026-07-02-network-spinner-smoke-checklist.md` — cross-app manual smoke.

---

## Task 1: Shell `is-loading` toggle + CLD e2e (TDD, behavioral core)

The e2e checks the class/attribute contract only (not pixels), so it depends on the JS, not the CSS — hence test-first here, CSS in Task 2.

**Files:**
- Modify: `sespy/dashboard.py` (add `network_spinner_js`, include in `head_content`)
- Test: `tests/test_cld_e2e.py` (extend the existing script)

**Interfaces:**
- Consumes (from the environment): the pyvis fork sends `Shiny.setInputValue(outputId + '_ready', …)` on every render (`bindings.js:836`); Shiny fires `shiny:recalculating` on the `.pyvis-network-output` output element.
- Produces (consumed by Task 2 CSS + smoke): on show, the `.pyvis-network-output` element gets class `is-loading` AND attribute `data-sespy-net-shown="1"` (sticky, never removed); on `<id>_ready`, `is-loading` is removed.

- [ ] **Step 1: Write the failing test** — in `tests/test_cld_e2e.py`, insert after the existing delay-edge assertions (after the `assert not all(flags), …` line, currently line 35) and before `await page.screenshot(...)` (currently line 37):

```python
        # --- network loading spinner (shared shell) ---
        # End-state only (do NOT race the transient visible spinner):
        #  (1) the sticky marker proves the show path ran (is-loading was added);
        #  (2) is-loading must clear once the graph is up (via <id>_ready or the
        #      8s fallback).
        shown = await page.evaluate(
            "() => document.getElementById('cld-network')"
            "  && document.getElementById('cld-network').getAttribute('data-sespy-net-shown') === '1'"
        )
        assert shown, "#cld-network never entered loading state (spinner show path dead)"
        not_loading = False
        for _ in range(24):  # up to ~12s: covers <id>_ready and the 8s fallback
            not_loading = await page.evaluate(
                "() => { const el = document.getElementById('cld-network');"
                " return !!el && !el.classList.contains('is-loading'); }"
            )
            if not_loading:
                break
            await page.wait_for_timeout(500)
        assert not_loading, "#cld-network stuck in .is-loading after the graph rendered"
        print("network spinner show->hide: OK")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd "/c/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy"
micromamba run -n shiny shiny run --port 8000 app.py &   # wait until :8000 serves
PYTHONPATH="$PWD" micromamba run -n shiny python tests/test_cld_e2e.py
```

Expected: FAIL at `assert shown` — nothing sets `data-sespy-net-shown` yet.

- [ ] **Step 3: Add the script block** — in `sespy/dashboard.py`, immediately after the `theme_js = ui.tags.script(""" … """)` block, add:

```python
    network_spinner_js = ui.tags.script("""
      (function () {
        var FALLBACK_MS = 8000;
        var timers = {};

        // Bound at parse time (jQuery only; no Shiny object needed), so the
        // handlers exist before the first output renders — no first-load race.
        $(document).on('shiny:recalculating', function (e) {
          var el = e.target;
          if (!el || !el.classList || !el.classList.contains('pyvis-network-output')) return;
          el.classList.add('is-loading');
          el.setAttribute('data-sespy-net-shown', '1');   // sticky proof the spinner showed
          if (el.id) {
            clearTimeout(timers[el.id]);
            timers[el.id] = setTimeout(function () { el.classList.remove('is-loading'); }, FALLBACK_MS);
          }
        });

        // The fork sends <id>_ready when the network is created/drawn — every
        // render, physics or not. Hide on that (NOT _stabilized, which never
        // fires for physics-off graphs like the hierarchical CLD).
        $(document).on('shiny:inputchanged', function (e) {
          if (!e.name || e.name.slice(-6) !== '_ready') return;
          var id = e.name.slice(0, -6);
          var el = document.getElementById(id);
          if (el && el.classList.contains('pyvis-network-output')) {
            el.classList.remove('is-loading');
            clearTimeout(timers[id]);
          }
        });
      })();
    """)
```

- [ ] **Step 4: Include it in the head** — in the same file's `ui.head_content( … )` call, add `network_spinner_js` immediately after `theme_js,`:

```python
            burger_js,
            bookmark_js,
            theme_js,
            network_spinner_js,
        ),
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
# restart shiny run so the new dashboard.py is served, wait for :8000, then:
PYTHONPATH="$PWD" micromamba run -n shiny python tests/test_cld_e2e.py
```

Expected: PASS — prints `network spinner show->hide: OK` and `cld e2e assertions pass`.

- [ ] **Step 6: Flake guard — run the CLD e2e 5 times**

```bash
for i in 1 2 3 4 5; do PYTHONPATH="$PWD" micromamba run -n shiny python tests/test_cld_e2e.py >/dev/null 2>&1; echo "run $i EXIT=$?"; done
```

Expected: all `EXIT=0`.

- [ ] **Step 7: Lint**

```bash
micromamba run -n shiny ruff check sespy tests app.py
```

Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add sespy/dashboard.py tests/test_cld_e2e.py
git commit -m "feat(shell): network spinner is-loading toggle + CLD e2e

Adds is-loading (+ sticky data-sespy-net-shown) on shiny:recalculating and
removes it on the fork's always-sent <id>_ready input, with an 8s fallback.
CLD e2e asserts the show->hide cycle (sticky marker + not stuck), non-racy."
```

---

## Task 2: Spinner CSS (pseudo-elements) in both skins

**Files:**
- Modify: `www/sespy-skin.css:122-145`
- Modify: `../MosaicSES/www/sespy-skin.css` (its `.pyvis-network-output` rule — find by search; divergent copy, different line numbers)

**Interfaces:**
- Consumes: the `is-loading` class contract from Task 1.
- Produces: the visible spinner (veil + ring) via pseudo-elements.

- [ ] **Step 1: Add the CSS to the SESPy skin** — in `www/sespy-skin.css`, change the rule at lines 122-124 from:

```css
.pyvis-network-output {
  display: block !important;
}
```

to:

```css
.pyvis-network-output {
  display: block !important;
  position: relative;   /* positioning context for the loading pseudo-elements */
}
```

Then, immediately after the `.pyvis-network-output .pyvis-network-canvas { border: none !important; }` rule (currently ending line 145) and before the `TITLE BAR` comment block, append:

```css
/* (4) Network loading spinner (shared shell). Rendered as pseudo-elements so it
       survives the pyvis fork's `el.innerHTML=''` on every render (bindings.js:90);
       toggled by the `is-loading` class from network_spinner_js. ::before is the
       veil + label, ::after is the ring. z-index stays below the fork's
       .pyvis-modal-overlay (1000) so node/edge modals sit on top. */
.pyvis-network-output.is-loading::before {
  content: "Rendering network\2026";   /* \2026 = U+2026 ellipsis */
  position: absolute;
  inset: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 3.2rem;                 /* leave room for the ring above the text */
  background: color-mix(in srgb, var(--bs-body-bg, #ffffff) 68%, transparent);
  color: var(--bs-secondary-color, #555);
  font-size: 0.9rem;
  pointer-events: none;
}
.pyvis-network-output.is-loading::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 6;
  width: 2.25rem;
  height: 2.25rem;
  margin: -2.4rem 0 0 -1.125rem;       /* center horizontally, sit above the label */
  border: 3px solid color-mix(in srgb, var(--bs-secondary-color, #555) 25%, transparent);
  border-top-color: var(--bs-secondary-color, #555);
  border-radius: 50%;
  animation: sespy-net-spin 0.8s linear infinite;
  pointer-events: none;
}
@keyframes sespy-net-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .pyvis-network-output.is-loading::after { animation: none; }
}
```

- [ ] **Step 2: Add the identical CSS to the MosaicSES skin** — open `../MosaicSES/www/sespy-skin.css`, find its `.pyvis-network-output {` rule, add `position: relative;` to it the same way, and append the **exact same** `/* (4) Network loading spinner … */` block from Step 1.

- [ ] **Step 3: Verify visually in both apps** — boot each app and confirm the spinner shows on a network load and clears; confirm no unstyled text blob:

```bash
# SESPy
micromamba run -n shiny shiny run --port 8000 app.py &        # open http://127.0.0.1:8000, watch CLD load
# MosaicSES
( cd "../MosaicSES" && micromamba run -n shiny shiny run --port 8001 app.py & )   # open http://127.0.0.1:8001, watch Topology
```

Expected: a centered spinner + "Rendering network…" veil during load in BOTH apps, clearing when the graph draws.

- [ ] **Step 4: Commit (two repos)**

```bash
git add www/sespy-skin.css
git commit -m "style(shell): pyvis network loading spinner pseudo-elements (SESPy skin)"
( cd "../MosaicSES" && git add www/sespy-skin.css && git commit -m "style: mirror pyvis network loading spinner CSS from SESPy skin" )
```

Expected: one commit in each repo.

---

## Task 3: Cross-app manual smoke checklist

**Files:**
- Create: `docs/2026-07-02-network-spinner-smoke-checklist.md`

**Interfaces:**
- Consumes: the `is-loading` / pseudo-element contract from Tasks 1-2.

- [ ] **Step 1: Write the checklist**

```markdown
# Network spinner — manual smoke (2026-07-02)

Run each app: `micromamba run -n shiny shiny run --launch-browser app.py`.

## SESPy (app.py)
- [ ] CLD Visualization: spinner shows over the graph on first load and clears
      when it draws (physics-off view — proves the _ready hide, not _stabilized).
- [ ] Leverage Points (physics-on) and back: spinner re-shows on each network
      (re)render, then clears.
- [ ] Node/edge modal opens ABOVE where the spinner was (z-index ok); toolbar
      buttons clickable after load.

## MosaicSES (../MosaicSES/app.py)  — separate skin copy; MUST be checked here
- [ ] Topology: spinner shows over the 6-node graph, clears when drawn. Confirms
      MosaicSES/www/sespy-skin.css got the CSS (else you'll see an UNSTYLED veil
      or nothing).
- [ ] Drill into a compartment (larger CLD): spinner visibly useful, then clears.

## Themes / a11y
- [ ] Switch to a dark theme: veil + text still legible over the canvas.
- [ ] OS "reduce motion" on: veil + text + static ring, no rotation.
```

- [ ] **Step 2: Commit**

```bash
git add docs/2026-07-02-network-spinner-smoke-checklist.md
git commit -m "docs: cross-app manual smoke checklist for the network spinner"
```

---

## Notes for the implementer

- **Do not reintroduce an injected overlay `<div>`.** The fork's `el.innerHTML=''`
  (`bindings.js:90`) destroys child nodes on every render; pseudo-elements +
  the `is-loading` class survive it. This is the whole reason for the approach.
- **First-load SHOW** is covered because the handlers bind at parse time (jQuery
  event delegation, no `Shiny` object needed), before the first output renders.
  The e2e's sticky-marker assertion depends on this; if it ever flakes on
  `assert shown`, check that the script is bound before first render.
- `<id>_ready` suffix is 6 chars (`_ready`); `slice(-6)`/`slice(0,-6)` are correct
  and do not collide with `_stabilized`, `_stabilizationProgress`, etc.
- If `#cld-network` is not the CLD output id in the running app, discover it via
  `Object.keys(window.pyvisNetworks)` in the console and update the test. As of
  this plan it is `cld-network`.
- In CSS the ellipsis is the escape `\2026` (a single backslash), NOT the JS
  `…`. Confirm it renders in the veil during smoke.
- MosaicSES is a SEPARATE git repo; its skin edit is committed in that repo, and
  verifying it requires running/smoking the MosaicSES app (SESPy CI won't).
