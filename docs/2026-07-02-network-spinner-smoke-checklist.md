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
