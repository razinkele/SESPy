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

## Automated coverage (already green)
- `tests/test_cld_e2e.py` asserts the show→hide cycle via the sticky
  `data-sespy-net-shown` / `data-sespy-net-hidden="ready"` markers (CI-gated,
  5/5 local). It does NOT assert the visible pixels — hence this manual pass.

## Automated smoke results (2026-07-05, Chromium via Playwright)
Several checklist items above were verified programmatically post-merge (forcing
`is-loading` on `#cld-network` and reading computed styles / geometry):

- **Spinner shows + clears (both apps)** — PASS. SESPy CLD + MosaicSES Topology:
  `::before` content `"Rendering network…"`, and geometry `outputCoversCanvas: true`
  (output box == canvas box, 582×650 SESPy / 474×650 MosaicSES) — veil fully
  covers the canvas; pseudo-elements paint above it.
- **MosaicSES separate skin got the CSS** — PASS. `::before` resolves in the
  MosaicSES app (proves its own `www/sespy-skin.css` copy carries the block).
- **Reduced motion** — PASS. Under `prefers-reduced-motion: reduce`, `::after`
  `animation-name: none` (no rotation); veil + label still shown.
- **Modal z-order** — PASS. Spinner `::before`=5 / `::after`=6 vs the fork's
  `.pyvis-modal-overlay`=1000 — modals paint above the spinner.
- **Dark theme (deep-ocean)** — PASS (legible). Body bg `rgb(11,31,51)`; the pyvis
  canvas stays light in every theme, so the white veil (68%) + dark label
  `rgb(29,31,33)` are high-contrast and consistent — no jarring flash.

Still needs a human eye (interaction-dependent, not auto-verified): Leverage
physics-on re-show, MosaicSES compartment drill-in, an actual node/edge modal
click over a just-loaded graph.
