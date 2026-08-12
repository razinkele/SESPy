# Changelog

All notable changes to SESPy.

## [Unreleased]
- New "Governance gap" block on the Network Metrics card (#13): directed
  coverage of pressure nodes by governance elements (headline fraction),
  per-layer gap data in the analysis API, and detection of governance elements with no path
  into the ecological subsystem. Operationalises the SENA governance-gap
  concept of Fraga et al. 2026 (Marine Policy, doi:10.1016/j.marpol.2026.107169).
- Language is now per session. The translator was a process-wide singleton, so one
  user switching language changed it for everyone connected to the same server;
  each session now gets its own translator. The initial language is read from the
  `?lang=` (or `?language=`) URL query on connect.
- Autosave, project-save and feedback failures now tell you they failed. These paths
  previously swallowed every exception, so a locked file or an unwritable database
  looked identical to success; they now show a notification and log the cause.
- About box reports the running version instead of a stale installed one (it showed
  1.2.0 through the 1.3.0 release).
- PDF export gives an actionable message when WeasyPrint's native libraries
  (Cairo, Pango) are missing, rather than an unhandled error.
- Fix: element confidence and moving-average window no longer silently rewrite a
  legitimate `0` into the default `3`. In Behaviour Over Time this halved the
  simulated noise on the least certain elements.
- Fix: clearing autosaved data from the Options modal could raise instead of warning
  when the file was locked.
- Two remaining hardcoded English notifications ("Autosaved data cleared.", "Could
  not record feedback.") are now translated in all nine languages.
- Internal: network centrality now logs when a metric degrades to zeros, so silent
  analysis-quality loss is visible.
- Internal: the QSEM sample models are vendored into `data/`, so the QSEM tests run
  everywhere instead of skipping off the author's machine.
- Internal: the e2e suite writes feedback to a throwaway database instead of the
  real (deploy-preserved) store.
- Docs: the `pdf` extra records a conda-forge pitfall — conda-forge's
  "tinycss2 1.5.1" ships 1.4.0 code without the `color5` module that WeasyPrint 67+
  imports, so PDF export dies at import in conda environments. Use `weasyprint=66`
  there. pip installs are unaffected.

## [1.3.0] — 2026-07-06
- Network graph loading spinner: every pyvis network view (CLD, Topology, Leverage,
  Network Metrics, Intervention, Loop Analysis, Simplify) shows a centered
  "Rendering network…" spinner while the graph builds, clearing the moment it draws.
- Import: optional "Assign DAPSIWRM types" for QSEM models — an editable,
  heuristic-pre-filled per-theme mapping table (opt-in, default off) so imported
  models render as a coloured, levelled CLD.
- Fix: imported QSEM / food-web models now render in the CLD. Their nodes use
  non-DAPSIWRM themes (or none), and the DAPSIWRM-only type filter was silently
  dropping every untyped element, so the diagram came up empty. Untyped / custom
  themes the filter doesn't offer are now always shown.
- Title-bar utility cluster: Feedback, About, Options, and Help buttons in the right corner of the app title bar.
- Feedback modal now lists recent feedback below the form (date, category, rating,
  message; newest first, 10 rows, scroll-capped). The listing read is guarded so a
  read-only / unwritable store degrades to an empty table instead of crashing the
  dialog (fixes a server crash when the deployed app user could not write the DB).
- Deploy: the server-owned feedback database (`sespy/logs/feedback.db`) is preserved
  across deploys instead of being overwritten by the local copy.
- Feedback modal writing to a local SQLite store (message, rating, category).
- About modal with Overview and Changelog tabs (rendered from README + this file).
- Options modal: colour theme (Light Marine / Deep Ocean), the language selector
  (relocated here), and autosave controls (enable, clear, last-saved status).
- Help modal summarising the create → edit → analyze → export workflow.
- Internal: the shell stylesheets (skin, cld, themes) are now shipped as `sespy`
  package data and served via a single `HTMLDependency`, so every app embedding the
  shell gets one source of truth (no per-app CSS copies to drift).

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
