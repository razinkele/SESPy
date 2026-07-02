# Network loading spinner — design

**Date:** 2026-07-02
**Status:** approved (brainstorming)
**Scope:** SESPy shared shell — affects every pyvis network view in both SESPy and MosaicSES.

## Problem

The pyvis network views (Topology, CLD Visualization, Leverage, Network Metrics,
Intervention, Loop Analysis, Simplify) render with a visible delay. There is no
feedback during that delay, so the panel looks blank/broken until the graph
appears. Users perceive the app as slow or stuck.

The delay has two phases:
1. **Server build** — the reactive `render_pyvis_network` output recomputes and
   ships the network data/HTML.
2. **Client layout** — vis-network instantiates and runs physics stabilization
   (nodes animate into place). For larger graphs (compartment CLDs ~20+ nodes)
   this is the dominant, visible wait, and it happens *after* Shiny already
   considers the output "recalculated".

A good indicator must cover **both** phases.

## Goal

Show a centered spinner overlay ("Rendering network…") over each pyvis output
while it is building and laying out, and auto-hide it the moment the graph is
ready. One implementation in the shared shell, covering all network views in
both apps. No changes to the pyvis fork.

Non-goals (YAGNI): percentage progress bar, per-view configuration, persistence,
covering non-pyvis outputs.

## Approach

Add a small CSS overlay + a short client script to the SESPy shell
(`sespy/dashboard.py`), driven entirely by **documented Shiny client events**
plus a signal the pyvis fork **already emits** — so it stays decoupled from the
fork's internals.

Key facts this relies on (verified in the installed `pyvis.shiny` fork, 4.2):
- The output element carries the Shiny output binding class
  `.pyvis-network-output`, and its DOM `id` equals the Shiny output id.
- The fork already calls `Shiny.setInputValue(outputId + '_stabilized', …)` when
  vis-network fires `stabilizationIterationsDone` (event binding defaults to all
  events, which SESPy does not override). This surfaces to arbitrary JS as a
  `shiny:inputchanged` event with `name === outputId + '_stabilized'`.

### Show / hide triggers

| Phase | Signal | Action |
|---|---|---|
| Server build | `shiny:recalculating` on a `.pyvis-network-output` element | show overlay for that element |
| Client layout done | `shiny:inputchanged` with `name` ending `_stabilized` → map to `#<outputId>` | hide that element's overlay |
| Safety net | physics disabled / instant / event missed | hide after an **8 s** timeout, per overlay |

Showing on `recalculating` and hiding only on `_stabilized` (not on
`recalculated`) is what makes the overlay span the client-layout phase.

### Components

1. **CSS** (`www/sespy-skin.css`, next to the existing `.pyvis-network-output`
   guards): `.sespy-net-overlay` — absolutely positioned, covers the output,
   centered spinner + label; `.is-loading` toggles visibility; `pointer-events`
   only active while loading; z-index **below** the fork's `.pyvis-modal-overlay`
   so node/edge modals stay on top. Respects `prefers-reduced-motion` (no spin).

2. **JS** (`network_spinner_js` in `dashboard.py`, injected in `head_content`
   alongside `bookmark_js`/`theme_js`, registered on `shiny:connected`):
   - A `MutationObserver` (plus an initial sweep) ensures every
     `.pyvis-network-output` has a child overlay node injected exactly once —
     works for initial load, tab switches, and re-renders.
   - `$(document).on('shiny:recalculating', …)` → if the target is a
     `.pyvis-network-output`, add `.is-loading` and arm the 8 s fallback timer.
   - `$(document).on('shiny:inputchanged', …)` → if `name` ends with
     `_stabilized`, strip the suffix to get the output id, find
     `#<id>.pyvis-network-output`, remove `.is-loading`, clear its timer.
   - Idempotent: re-showing reuses the same overlay node.

### Why not alternatives

- **Shiny `busy_indicators`**: trivial to enable but only covers the server
  recalculating phase — it hides once the HTML is delivered, *before* physics
  stabilization, i.e. it misses the dominant wait. Rejected.
- **Modify the pyvis fork's `bindings.js`**: the fork owns the network and could
  show its own overlay on `stabilizationIterationsDone` precisely, but the fork
  is a separate repo installed from a conda channel (not the SESPy tree), so it
  can't be committed/shipped from here. Rejected in favor of the shell.

## Error handling / robustness

- Missing/never-firing `_stabilized` → 8 s per-overlay timeout hides it anyway.
- Overlay must never block interaction after hide: `pointer-events: none` when
  not `.is-loading`.
- Must not disturb the fork's toolbar, status bar, or modal overlays (z-index
  and scoping keep them independent).
- Shared-shell blast radius is intended (all network views, both apps); the
  change only *adds* an overlay layer and touches no nav/collapse behavior.

## Testing

- **e2e** (SESPy's own harness, so it is gated by SESPy CI): drive a SESPy
  network view that already has an e2e (CLD visualization or Leverage), and for
  its output id `<id>` assert:
  1. an overlay element exists inside `#<id>.pyvis-network-output`, and
  2. once `window.pyvisNetworks['<id>'].nodes.length > 0`, the output no longer
     carries `.is-loading` (overlay hidden).
  Deliberately assert the **end state**, not a race to catch the transient
  visible overlay — matching the condition-based-waiting lesson from the
  leverage/simulation e2e de-flake. Prefer extending an existing
  `tests/test_cld_e2e.py` / `tests/test_leverage_e2e.py` over a new script.
- **Manual smoke**: load MosaicSES Topology and a larger compartment CLD; the
  spinner shows during load and disappears when the graph settles; the pyvis
  toolbar and node/edge modals still work.

## Files touched

- `sespy/dashboard.py` — add `network_spinner_js`, inject in `head_content`.
- `www/sespy-skin.css` — add `.sespy-net-overlay` styles.
- `tests/test_cld_e2e.py` or `tests/test_leverage_e2e.py` (SESPy) — one
  end-state assertion (extend, don't add a new script).
