# Network Loading Spinner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a centered spinner overlay ("Rendering network…") over every pyvis network output while it builds and lays out, auto-hidden the moment the graph is ready.

**Architecture:** One CSS overlay + one short client script, both injected by the shared SESPy shell (`sespy/dashboard.py` + `www/sespy-skin.css`). The script shows the overlay on Shiny's `shiny:recalculating` event for `.pyvis-network-output` elements (server build) and hides it on the `shiny:inputchanged` event for `<id>_stabilized` (the pyvis fork already emits this when vis-network finishes physics), with an 8 s per-overlay fallback. No changes to the pyvis fork; every network view in SESPy and MosaicSES inherits it.

**Tech Stack:** Python Shiny, the razinka `pyvis.shiny` 4.2 fork (vis-network 10.0.2), vanilla JS + jQuery (`$` is present — Shiny ships it), CSS. Tests: standalone Playwright e2e scripts run via `tests/run_e2e.py`.

## Global Constraints

- Python env: run everything through the existing micromamba env — `micromamba run -n shiny …`. Do NOT create venvs or `pip install`.
- The spinner overlay z-index MUST be below `1000` (the fork's `.pyvis-modal-overlay` z-index) so node/edge modals stay on top.
- Overlay MUST be `pointer-events: none` unless the output is `.is-loading`, so it never blocks interaction after hiding.
- e2e assertions MUST check the **end state** (overlay hidden once the graph is ready), never race to catch the transient visible overlay — per the condition-based-waiting lesson from the leverage/simulation de-flake.
- ruff lint is blocking in CI; `tests/**` already ignores E402/E501. Keep `ruff check` clean.
- Overlay label text is exactly `Rendering network…` (with a real ellipsis `…`, U+2026).
- Fallback timeout is exactly `8000` ms.

---

## File Structure

- `www/sespy-skin.css` — add `position: relative` to the existing `.pyvis-network-output` rule and append the `.sespy-net-overlay` styles. Static styling only.
- `sespy/dashboard.py` — add a `network_spinner_js = ui.tags.script(...)` block next to `theme_js`, and include it in the existing `ui.head_content(...)` call. Owns show/hide behavior.
- `tests/test_cld_e2e.py` — extend the existing CLD network e2e with the overlay end-state assertion (do NOT add a new script). This is the CI-gated test.
- `docs/2026-07-02-network-spinner-smoke-checklist.md` — manual cross-app smoke steps (MosaicSES topology + a large CLD).

---

## Task 1: Network spinner overlay (shell CSS + JS) with CLD e2e

**Files:**
- Modify: `www/sespy-skin.css:122-145` (the pyvis guards section)
- Modify: `sespy/dashboard.py` (add `network_spinner_js`, include in `head_content`)
- Test: `tests/test_cld_e2e.py` (extend the existing script)

**Interfaces:**
- Consumes (from the environment, already present):
  - DOM: the pyvis output element has class `pyvis-network-output` and its `id` equals the Shiny output id (e.g. `cld-network`).
  - Shiny client events: `shiny:recalculating` (fires on the output element), `shiny:inputchanged` (has `.name`, fires for `<id>_stabilized`).
- Produces (relied on by the e2e and manual smoke):
  - CSS class contract: while loading, the `.pyvis-network-output` element carries `is-loading`; it always contains exactly one child `div.sespy-net-overlay`.

- [ ] **Step 1: Write the failing test** — insert the overlay end-state assertion into `tests/test_cld_e2e.py` after the existing delay-edge assertions (after the `assert not all(flags), …` line, currently line 35) and before the `await page.screenshot(...)` line (currently line 37):

```python
        # --- network loading overlay (shared shell) ---
        # The network is ready here (edges readable). The overlay must exist and,
        # after stabilization/fallback, must no longer mark the output as loading.
        # End-state only: do NOT race to catch the transient visible overlay.
        overlay_present = await page.evaluate(
            "() => !!document.querySelector('#cld-network .sespy-net-overlay')"
        )
        assert overlay_present, "no .sespy-net-overlay injected into #cld-network"
        not_loading = False
        for _ in range(24):  # up to ~12s: covers the _stabilized event and the 8s fallback
            not_loading = await page.evaluate(
                "() => { const el = document.getElementById('cld-network');"
                " return !!el && !el.classList.contains('is-loading'); }"
            )
            if not_loading:
                break
            await page.wait_for_timeout(500)
        assert not_loading, "#cld-network stuck in .is-loading after network ready"
        print("network overlay end-state: OK")
```

- [ ] **Step 2: Run the test to verify it fails**

Boot the app, then run the script (the runner boots the server for the full suite, but for a single script boot it manually):

```bash
cd "/c/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy"
micromamba run -n shiny shiny run --port 8000 app.py &   # leave running
# wait until http://127.0.0.1:8000 serves, then:
PYTHONPATH="$PWD" micromamba run -n shiny python tests/test_cld_e2e.py
```

Expected: FAIL at `assert overlay_present` — `AssertionError: no .sespy-net-overlay injected into #cld-network` (the overlay does not exist yet).

- [ ] **Step 3: Add the overlay CSS** — in `www/sespy-skin.css`, change the existing rule at lines 122-124 from:

```css
.pyvis-network-output {
  display: block !important;
}
```

to:

```css
.pyvis-network-output {
  display: block !important;
  position: relative;   /* anchor for the loading overlay */
}
```

Then, immediately after the `.pyvis-network-output .pyvis-network-canvas { border: none !important; }` rule (currently ending line 145) and before the `TITLE BAR` comment block, append:

```css
/* (4) Network loading spinner overlay (shared shell). Shown while the pyvis
       output builds server-side AND while vis-network runs physics; hidden on
       the fork's <id>_stabilized signal (8s JS fallback). Sits below the fork's
       .pyvis-modal-overlay (z-index 1000) so node/edge modals stay on top. */
.sespy-net-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  z-index: 5;
  background: color-mix(in srgb, var(--bs-body-bg, #ffffff) 68%, transparent);
  color: var(--bs-secondary-color, #555);
  font-size: 0.9rem;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}
.pyvis-network-output.is-loading .sespy-net-overlay {
  opacity: 1;
  pointer-events: auto;
}
.sespy-net-overlay__spinner {
  width: 2.25rem;
  height: 2.25rem;
  border: 3px solid color-mix(in srgb, currentColor 25%, transparent);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: sespy-net-spin 0.8s linear infinite;
}
@keyframes sespy-net-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .sespy-net-overlay__spinner { animation: none; }
}
```

- [ ] **Step 4: Add the injected script** — in `sespy/dashboard.py`, immediately after the `theme_js = ui.tags.script(""" … """)` block, add:

```python
    network_spinner_js = ui.tags.script("""
      $(document).on('shiny:connected', function () {
        var LABEL = 'Rendering network\\u2026';
        var FALLBACK_MS = 8000;
        var timers = {};

        function ensureOverlay(el) {
          if (el.querySelector(':scope > .sespy-net-overlay')) return;
          var ov = document.createElement('div');
          ov.className = 'sespy-net-overlay';
          ov.setAttribute('aria-hidden', 'true');
          ov.innerHTML = '<div class="sespy-net-overlay__spinner"></div><div>' + LABEL + '</div>';
          el.appendChild(ov);
        }
        function sweep(root) {
          (root || document).querySelectorAll('.pyvis-network-output').forEach(ensureOverlay);
        }
        function show(el) {
          ensureOverlay(el);
          el.classList.add('is-loading');
          if (el.id) {
            clearTimeout(timers[el.id]);
            timers[el.id] = setTimeout(function () { el.classList.remove('is-loading'); }, FALLBACK_MS);
          }
        }
        function hide(id) {
          var el = document.getElementById(id);
          if (el && el.classList.contains('pyvis-network-output')) {
            el.classList.remove('is-loading');
            clearTimeout(timers[id]);
          }
        }

        sweep(document);
        new MutationObserver(function (muts) {
          muts.forEach(function (m) {
            m.addedNodes.forEach(function (n) {
              if (n.nodeType !== 1) return;
              if (n.classList && n.classList.contains('pyvis-network-output')) ensureOverlay(n);
              if (n.querySelectorAll) sweep(n);
            });
          });
        }).observe(document.body, { childList: true, subtree: true });

        $(document).on('shiny:recalculating', function (e) {
          var el = e.target;
          if (el && el.classList && el.classList.contains('pyvis-network-output')) show(el);
        });
        $(document).on('shiny:inputchanged', function (e) {
          if (e.name && e.name.slice(-11) === '_stabilized') hide(e.name.slice(0, -11));
        });
      });
    """)
```

- [ ] **Step 5: Include the script in the head** — in the same file, in the `ui.head_content( … )` call, add `network_spinner_js` to the list immediately after `theme_js,`:

```python
            burger_js,
            bookmark_js,
            theme_js,
            network_spinner_js,
        ),
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
# app still running from Step 2 — reload happens automatically on file save,
# but to be safe restart: kill the shiny run, relaunch, wait for :8000, then:
PYTHONPATH="$PWD" micromamba run -n shiny python tests/test_cld_e2e.py
```

Expected: PASS — prints `network overlay end-state: OK` and `cld e2e assertions pass`.

- [ ] **Step 7: Guard against flakiness** — run the CLD e2e 3 times; all must exit 0:

```bash
for i in 1 2 3; do PYTHONPATH="$PWD" micromamba run -n shiny python tests/test_cld_e2e.py >/dev/null 2>&1; echo "run $i EXIT=$?"; done
```

Expected: `run 1 EXIT=0`, `run 2 EXIT=0`, `run 3 EXIT=0`.

- [ ] **Step 8: Lint**

```bash
micromamba run -n shiny ruff check sespy tests app.py
```

Expected: `All checks passed!`

- [ ] **Step 9: Commit**

```bash
git add www/sespy-skin.css sespy/dashboard.py tests/test_cld_e2e.py
git commit -m "feat(shell): loading spinner overlay for pyvis networks

Centered spinner shown while a pyvis output builds and while vis-network runs
physics, auto-hidden on the fork's <id>_stabilized signal (8s fallback).
Injected once in the SESPy shell, so every network view in SESPy + MosaicSES
gets it. CLD e2e asserts the overlay exists and clears once the graph is ready."
```

---

## Task 2: Cross-app manual smoke checklist

**Files:**
- Create: `docs/2026-07-02-network-spinner-smoke-checklist.md`

**Interfaces:**
- Consumes: the `is-loading` / `.sespy-net-overlay` contract from Task 1.
- Produces: a checklist doc (no code consumers).

- [ ] **Step 1: Write the checklist** — create `docs/2026-07-02-network-spinner-smoke-checklist.md`:

```markdown
# Network spinner — manual smoke (2026-07-02)

Run each app with `micromamba run -n shiny shiny run --launch-browser app.py`.

## SESPy (app.py)
- [ ] CLD Visualization: on first load the spinner shows over the graph and
      disappears once nodes settle.
- [ ] Switch to Leverage Points and back to CLD: spinner re-shows on each
      network (re)render, then clears.
- [ ] Node/edge modal still opens and sits ABOVE where the overlay was
      (z-index correct); toolbar buttons still clickable after load.

## MosaicSES (../MosaicSES/app.py)
- [ ] Topology: spinner shows over the 6-node compartment graph, clears when
      laid out.
- [ ] Drill into a compartment (larger CLD, ~20+ nodes): spinner is visibly
      useful during the longer stabilization, then clears.

## Reduced motion
- [ ] With OS "reduce motion" on, the overlay still shows but the spinner does
      not rotate (label + static ring only).
```

- [ ] **Step 2: Commit**

```bash
git add docs/2026-07-02-network-spinner-smoke-checklist.md
git commit -m "docs: manual smoke checklist for the network loading spinner"
```

---

## Notes for the implementer

- The overlay's SHOW behavior on the very first render can race the script's
  event registration; that is why the e2e asserts only the **end state**
  (overlay present + not stuck loading). The visible-during-load behavior is
  covered by the manual smoke, not the e2e. Do not add an assertion that races
  to catch the overlay while visible.
- If `#cld-network` is not the CLD output id in the running app, discover it in
  the browser console with `Object.keys(window.pyvisNetworks)` and use that id
  in the e2e (update both the selector and the `pyvisNetworks[...]` key). As of
  this plan it is `cld-network`.
- `':scope > .sespy-net-overlay'` and `color-mix()` are supported by the
  vis-network target (Chromium via Playwright, and modern desktop browsers).
