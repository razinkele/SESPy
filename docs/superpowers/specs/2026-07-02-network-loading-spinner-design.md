# Network loading spinner — design

**Date:** 2026-07-02 (revised 2026-07-03 after multi-agent plan review)
**Status:** approved (brainstorming), revised post-review
**Scope:** SESPy shared shell + both apps' skin copies — affects every pyvis network view in SESPy and MosaicSES.

## Problem

The pyvis network views (Topology, CLD Visualization, Leverage, Network Metrics,
Intervention, Loop Analysis, Simplify) render with a visible delay and show no
feedback during it, so the panel looks blank/broken until the graph appears.

The genuinely *blank* window is: the server recomputes the `render_pyvis_network`
output, then the client rebuilds the DOM and instantiates vis-network. Physics
stabilization (nodes animating into place) happens *after* the graph is already
drawn and visible — it is not a blank wait, and the common CLD view runs with
physics **disabled** anyway (`sespy/modules/cld_visualization.py:187`,
hierarchical layout). So the indicator must cover the blank build/instantiate
window and clear the moment the graph is first drawn — uniformly, regardless of
whether physics runs.

## Goal

Show a centered spinner over each pyvis output while it builds, auto-hidden the
moment the graph is drawn. One implementation in the shared shell (plus the CSS
mirrored into both apps' skin copies). No changes to the pyvis fork.

Non-goals (YAGNI): percentage progress bar, per-view config, persistence,
covering non-pyvis outputs, de-duplicating the two skin copies (pre-existing
divergence, tracked separately).

## Approach

A pure-CSS spinner rendered as **`::before`/`::after` pseudo-elements on the
`.pyvis-network-output` element itself**, toggled by an `is-loading` class that a
short shell script adds/removes based on documented Shiny client events.

### Why pseudo-elements (the load-bearing decision)

The pyvis fork's binding runs `el.innerHTML = ''` at the top of every
`renderValue` (`pyvis/shiny/bindings.js:90`, where `el` is the
`.pyvis-network-output` element). Any child node injected into `el` (an overlay
`<div>`) is therefore **destroyed on every render** — precisely when the graph is
building. Pseudo-elements are generated content on the element, not child nodes,
so `innerHTML = ''` cannot remove them; and the `is-loading` **class** is an
attribute, which also survives `innerHTML = ''`. This eliminates the injected
node, a MutationObserver, and the entire wipe/re-inject problem. (An earlier
draft used an injected overlay div + observer; multi-agent review found the fork
wipes it — hence this approach.)

### Show / hide triggers

| Phase | Signal | Action |
|---|---|---|
| Server build + client instantiate | `shiny:recalculating` on a `.pyvis-network-output` element | add `is-loading`; set a sticky `data-sespy-net-shown="1"` marker; arm an 8 s fallback |
| Graph drawn | `shiny:inputchanged` with `name` ending `_ready` (the fork sends `<id>_ready` **"always … sent"**, `bindings.js:836-841`, unconditional, every render, physics-independent) → map to `#<id>` | remove `is-loading`; clear the timer |
| Safety net | `_ready` missed for any reason | 8 s per-output timeout removes `is-loading` |

`_ready` (not `_stabilized`) is the hide signal: `_stabilized` only fires when
physics runs, so the physics-off CLD view would never receive it. `_ready` fires
for all renders when the network is created/about to draw — the correct, uniform
"graph is up" moment.

### Components

1. **CSS** — appended to **both** `SESPy/www/sespy-skin.css` and
   `MosaicSES/www/sespy-skin.css` (the apps serve separate copies). Adds
   `position: relative` to `.pyvis-network-output`, then:
   - `.pyvis-network-output.is-loading::before` — a full veil (`inset:0`,
     translucent bg) carrying the centered label "Rendering network…".
   - `.pyvis-network-output.is-loading::after` — a centered rotating spinner ring
     (border + `@keyframes`), positioned just above the label.
   - `z-index` 5/6 — below the fork's `.pyvis-modal-overlay` (z-index 1000,
     `pyvis/shiny/styles.css:168-179`), so node/edge modals stay on top.
   - `@media (prefers-reduced-motion: reduce)` — no rotation.
   - Pseudo-elements are `pointer-events: none` so they never block the canvas
     (only visible while `.is-loading`; the graph is interactive as soon as the
     class is removed).

2. **JS** (`network_spinner_js` in `sespy/dashboard.py`, injected in
   `head_content` next to `theme_js`; ships to both apps via the editable `sespy`
   install). Registers the two jQuery delegated handlers at parse time (they need
   only jQuery, not the `Shiny` object, so binding before the first render is
   guaranteed — no first-load race):
   - `$(document).on('shiny:recalculating', …)` → if `e.target` has class
     `pyvis-network-output`, add `is-loading`, set `dataset.sespyNetShown = '1'`,
     and arm/re-arm an 8 s `setTimeout` (keyed by `e.target.id`) that removes
     `is-loading`.
   - `$(document).on('shiny:inputchanged', …)` → if `e.name` ends with `_ready`,
     strip the suffix, and on the matching `#<id>.pyvis-network-output` remove
     `is-loading` and clear its timer.
   No MutationObserver, no DOM injection.

### Why not alternatives

- **Injected overlay `<div>` + MutationObserver**: broken by the fork's
  `innerHTML = ''` (see above). Rejected.
- **Shiny `busy_indicators`**: covers only the server-recalculating phase, hides
  before the client build/instantiate finishes. Rejected.
- **Modify the pyvis fork's `bindings.js`**: separate repo installed from a conda
  channel; can't be committed/shipped from the app trees. Rejected.

## Error handling / robustness

- `_ready` missed → 8 s per-output timeout clears `is-loading`.
- Pseudo-elements are `pointer-events: none` and only visible while
  `.is-loading`, so nothing blocks interaction after the graph draws.
- z-index keeps the spinner below the fork's modals/toolbar; the veil sits over
  the whole output (incl. the fork's toolbar/status bar) but only during load.
- `shiny:inputchanged` fires for every app-wide input; the handler does only a
  cheap suffix test + a class removal that no-ops unless the id resolves to a
  `.pyvis-network-output`. Negligible cost, no misfire.
- Shared-shell blast radius (all network views, both apps) is intended; the
  change only toggles a class and adds pseudo-element styling — it touches no
  nav/collapse/burger behavior.

## Testing

- **e2e** (SESPy's own harness, gated by SESPy CI): extend `tests/test_cld_e2e.py`
  for output id `cld-network`. After the network is ready
  (`window.pyvisNetworks['cld-network'].nodes`/edges readable), assert:
  1. `#cld-network` has `data-sespy-net-shown === "1"` — proves the **show** path
     ran (spinner entered loading state); non-racy because the marker is sticky.
  2. poll up to ~12 s until `#cld-network` no longer has class `is-loading` —
     proves the **hide** path ran and nothing is stuck.
  End-state only; never races to catch the transient visible spinner (per the
  condition-based-waiting lesson from the leverage/simulation de-flake). The
  sticky marker closes the "spinner never showed" vacuous-pass gap.
- **Manual smoke** (both apps): SESPy CLD/Leverage + MosaicSES Topology and a
  large compartment CLD — spinner shows during load, clears when drawn; toolbar
  and node/edge modals still work; check a dark theme; check reduced-motion.

## Files touched

- `sespy/dashboard.py` — add `network_spinner_js`, inject in `head_content`.
- `www/sespy-skin.css` (SESPy) — add `.pyvis-network-output` spinner styles.
- `../MosaicSES/www/sespy-skin.css` — add the identical spinner styles.
- `tests/test_cld_e2e.py` (SESPy) — sticky-marker + not-stuck end-state assertions.

## Known follow-ups (out of scope)

- The two `sespy-skin.css` copies are already ~54 lines divergent; de-duplicating
  them into one shared asset is separate tech debt.
- Verifying MosaicSES gets the change requires MosaicSES CI/smoke — SESPy CI does
  not load the MosaicSES app.
