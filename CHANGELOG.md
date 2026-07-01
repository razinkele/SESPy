# Changelog

All notable changes to SESPy.

## [Unreleased]
- Title-bar utility cluster: Feedback, About, Options, and Help buttons in the right corner of the app title bar.
- Feedback modal now lists recent feedback below the form (date, category, rating,
  message; newest first, 10 rows, scroll-capped).
- Deploy: the server-owned feedback database (`sespy/logs/feedback.db`) is preserved
  across deploys instead of being overwritten by the local copy.
- Feedback modal writing to a local SQLite store (message, rating, category).
- About modal with Overview and Changelog tabs (rendered from README + this file).
- Options modal: colour theme (Light Marine / Deep Ocean), the language selector
  (relocated here), and autosave controls (enable, clear, last-saved status).
- Help modal summarising the create → edit → analyze → export workflow.

## [1.2.0] — 2026-06-26
- Disagreement-aware loops: a loop whose classification hinges on a rater-contested edge shows ⚠.
- Contested-edge styling on the CLD graph (heavier width + ⚠ marker).
- Blind rating mode in Rate Connections (hide peers' ratings until you submit).
- Off-thread uncertainty Monte Carlo (no UI freeze; "computing…" indicator).

## [1.1.0] — 2026-06-25
- Direct `.qsem` import (QSEM web-app JSON node/link graph).

## [1.0.0] — 2026-06-25
- First stable release: 17-module create→edit→analyze→export workflow, QSEM multi-rater
  elicitation, D2D Monte-Carlo uncertainty, social-ecological fit, FCM import, factor
  quadrant, delay-aware loops, Meadows leverage typology.
