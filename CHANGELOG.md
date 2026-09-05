# Changelog

All notable changes to SESPy.

## [1.8.1] — 2026-09-05

- Shiny for Python 1.7.0: every `@render.download` renderer (report HTML/PDF/
  DOCX, Save Project, the three stakeholder exports, the BOT CSV) is now
  `@render.download_button`, which 1.7.0 introduced and pairs 1:1 with
  `ui.download_button()`. No user-visible change; the deprecation warning that
  1.7.0 printed on every session start is gone. Floor pin raised to
  `shiny>=1.7`.
- New guard test, `tests/test_no_deprecations.py`, with two checks: a static
  source scan fails the suite if any file still calls the deprecated
  `render.download(...)` (trailing paren, so it does not match
  `render.download_button(...)`), and a fresh-interpreter import check fails
  if importing any `sespy` module raises a module-level
  `ShinyDeprecationWarning`. The scan is what actually catches this
  migration's four sites, because the app's download renderers are defined
  inside `@module.server` functions, which only run per-session — a plain
  import never instantiates them, so the import-time check alone cannot see
  a deprecation nested inside a server function. Together the two checks
  catch a reappearance of this exact deprecated call anywhere, and any
  future *module-level* Shiny deprecation at upgrade time; a future
  deprecation that only fires per-session inside a server function would
  need a further check (e.g. a mock-session harness), which is not yet in
  place.

## [1.8.0] — 2026-09-05

- New **user manual**, `docs/MANUAL.md`, rendered as the *Manual* tab of the
  About dialog and readable on GitHub: getting started, every one of the 19
  panels (purpose, controls, outputs, how to read the result, caveats), the
  scientific background of each analysis with the places SESPy departs from
  the published method, a verified bibliography (method foundations plus the
  2026 literature-alert papers by feature and release), and an appendix with
  file formats, URL parameters, a glossary and known limitations. English
  only; the About tab labels are translated in all nine languages.
- About dialog rebuilt: a curated *Overview* replaces the verbatim README
  dump, *Manual* is new, *Changelog* stays. `docs/screenshots/` is now served
  as a static route so the manual's relative image paths work in-app; the
  old README screenshots inside About were broken images.
- Screenshots regenerated for v1.8.0 by a new `tests/make_docs_screenshots.py`
  (Playwright, 1280×900, sample project, gated blocks run first): one capture
  per panel plus cascade, Monte Carlo and About states. The June 2026 set is
  replaced; `qsem_import.png` and `rate_connections.png` are gone.
- Help dialog points to About → Manual. `deploy.sh` ships the manual and its
  screenshots.
- The manual was fact-checked by a 65-agent review workflow (five lenses, two
  refuters per finding); 34 corrections landed before release, several of
  them to statements about the sample project and the tier/realm mappings.
- Tests: `tests/test_manual.py` keeps the manual honest (every referenced
  image exists, every nav panel has a section, every docstring DOI is in the
  references, the version line tracks the package, the static mount is
  pinned); the topbar e2e opens the Manual tab and asserts an image loads.

## [1.7.0] — 2026-09-05

- New **KL-divergence early warning** on the cascade vulnerability block
  (#25, after Kraehling 2026, doi:10.21203/rs.3.rs-9204974/v3): each removal
  step now reports the smoothed KL divergence of the surviving graph's degree
  distribution from the previous step's, as a `KL` column, and a bold line
  names the early-warning node — the first step whose KL exceeds twice the
  running median of all earlier steps (two earlier steps required). The line
  always prints both the early-warning step and the cascade-threshold step.
- Limitation, stated plainly: the rule cannot fire before step 3, and removal
  runs in descending leverage order, so on hub-shaped models the lccf
  collapse is step 1 and the KL departure can only follow it. On the sample
  project: threshold at step 1 (MPF1), departure at step 7 (D002) — a
  post-threshold departure, not a precursor. The signal earns its name when
  the connectivity collapse comes late in the removal order.
- Purely additive in the library: `lccf`, `loop_count`, `delta_lccf` and
  `cascade_threshold_node` are byte-identical to 1.6.x; the baseline row
  carries no KL (the first step is measured against it); the trivial shape
  gains `early_warning_node: None`. Nine-language strings for the two new
  lines; the caption defines KL.

## [1.6.2] — 2026-09-04

- Post-release review of #26 (workflow: four lenses, two refuters per
  finding) confirmed two defects, both fixed:
  - The distributed/concentrated verdict split on the raw entropy while the
    sentence printed it to 2 dp, so 0.497 read "concentrated … 0.50" and
    0.500 read "distributed … 0.50". The split is now taken on the rounded
    value, through a pure `governance_concentration_verdict()` helper that is
    unit-tested on both branches and at the boundary.
  - The metrics e2e's actor rank-order check was still vacuous after 1.6.1:
    it sliced the block text at the first "influence", which sits in the
    heading, so the sentence's "R002" satisfied it. It now reads the table
    element's own text.
- Placeholder parity of the two verdict strings is asserted across all nine
  languages.

## [1.6.1] — 2026-09-04

- New one-line **governance concentration** verdict above the "Governance
  actor influence" table on the Network Metrics card (#26, after Heredia et
  al. 2026, doi:10.21203/rs.3.rs-10195628/v1): whether governance power is
  distributed across the actors or concentrated in one, with the dominant
  actor's share and the normalised Shannon entropy of the influence shares.
  "Distributed" is worded at normalised entropy ≥ 0.5. On the sample project:
  concentrated in R002 (share 0.99 of 2 actors, entropy 0.10).
- Shares come from a softmax over the actor-influence composite rather than
  the issue's min-shift normalisation: the latter pins the weakest actor's
  share to zero by construction, so every two-actor model would read as fully
  concentrated. Library: `governance_concentration()` returns n_actors,
  shannon_entropy, normalised_entropy, gini, dominant_actor, dominant_share
  (None-filled below two actors); `governance_actor_influence()` is called
  unchanged.
- Test hygiene (intended, but not achieved until 1.6.2): the metrics e2e
  was meant to check actor rank order on the table alone, since the new
  sentence names the dominant actor above it.

## [1.6.0] — 2026-09-04

- New button-gated **"SES subsystem modules"** block on the Network Metrics
  card (#24, after Pinheiro et al. 2026's HyperMod,
  doi:10.1098/rspb.2026.1348): detects cohesive multi-tier subsystems —
  hypermodules — by module congruence across the three bipartite tier
  projections (ecological / social / governance), listing each with its tier
  composition and member labels plus a hypermodularity score. On the sample
  project: two hypermodules covering 9 of 17 typed elements.
- The congruence procedure deliberately deviates from the issue as filed,
  and both deviations were measured rather than argued: the issue's literal
  "same module in ≥2 of 3 projections" is vacuous on pairs (a cross-tier
  pair co-occurs in exactly one projection), so congruence works through
  hinge-tier nodes; and a flat two-shared-hinges threshold returns zero
  hypermodules on the shipped sample and structurally cannot fire on
  chain-shaped models, so the threshold is size-aware (two, or one when
  either module only has one hinge-tier node). The whole procedure is a
  documented reconstruction — the paper was unreachable — flagged in the
  spec, the docstring and the UI caption.
- Deterministic end to end: greedy modularity (no RNG, no seed), sorted
  construction everywhere networkx looks, membership merged to a partition.
  Established empirically at review: six hash seeds bit-identical, thirty
  construction-order shuffles identical, all merge orders over two hundred
  random candidate collections collapse to one partition.
- Every degenerate route has its own translated explanation (no cross-tier
  coupling / only one tier pair connected / tiers connected but nothing
  co-clusters), so a zero result is never a bare empty table. Library:
  `hypermodules()` and the `_TIER` partition, whose governance tier matches
  `governance_gap()`'s layer exactly; `_SUBSYSTEM` is untouched.

## [1.5.0] — 2026-09-04

- New on the Leverage Points panel (#23): the Meadows realm column is now
  **loop-aware** — an Activity that participates in a detected feedback loop
  reports Feedbacks rather than Design, since a variable inside a feedback
  loop acts at the feedback level. Every other type, and an Activity in no
  loop, is classified exactly as before. Deliberately NOT the issue as filed:
  #23's proposed `leverage_depth` column duplicated the shipped realm ladder
  and contradicted it on two of seven element types, so there is one
  classification, made structural, rather than two that disagree.
- New **ALC column** (Adjusted Loop Centrality) beside the leverage composite:
  per node, the sum of the signed structural gains of every detected loop it
  sits in. Positive means amplifying structure, negative damping, zero no
  loop. Not comparable with the leverage score beside it (the caption says
  so). ALC is suppressed, with a note, when a model exceeds the loop-detection
  cap: above it the detected loop subset varies between processes, so the
  sign — ALC's whole meaning — is not reproducible (measured −300/−169/+46
  for one node across three runs). Both source papers were unreachable, so
  the depth semantics and the ALC formula are documented reconstructions;
  ALC's "initiates vs reinforces" half is a recorded gap.
- Library: `loop_gain()` (the signed product `loop_dominance` previously
  computed inline and stripped via `abs()`), `adjusted_loop_centrality()`,
  `leverage_realms()`, `alc_is_truncated()` and a `LOOP_ENUMERATION_CAP`
  constant now wired as the `max_loops` default of `feedback_loops`,
  `cascade_vulnerability` and `uncertainty_scores`, with a source-scan test
  so a hardcoded cap cannot drift back in. `leverage_scores()` and
  `leverage_realm()` are unchanged.
- The eigenvector-centrality numpy fallback no longer logs a WARNING on every
  model. `nx.eigenvector_centrality_numpy` raises AmbiguousSolution for any
  digraph that is not strongly connected — which a causal SES diagram
  essentially never is — so the warning fired five times per report render on
  clean sample data and drowned out the one eigenvector message that matters,
  the all-zeros fallback (still WARNING). Scores were always computed by the
  iterative solver and are unchanged.
- `environment.yml` now requires `networkx>=3.1`, matching `pyproject.toml`.
  The conda file still said `>=3.0`, so a server env rebuilt from it could
  satisfy the spec with a networkx lacking `simple_cycles(length_bound=...)`
  and crash Loop Analysis, uncertainty scoring, cascade vulnerability and the
  v1.4.0 loop-dominance overlay.

## [1.4.0] — 2026-08-30

- **Fix — changes shipped output. Dynamic Simulation propagated influence
  backwards.** `isa_to_numeric_matrix` documents `M[i,j]` as the edge i→j
  (row = source, col = target), but the iterator computes `x_{t+1} = M @ x_t`,
  so a node's next state depended on the nodes it points *at* rather than
  those pointing *into* it. On a two-node A→B graph seeded at A, nothing
  propagated at all. A new `isa_to_dynamics_matrix` (the transpose, oriented
  for iteration) fixes Run Simulation and Monte Carlo in one change. Results
  from those two panels will differ from previous versions: anything
  published from them was computed with influence flowing the wrong way.
  The direction had never been tested — every prior test used identity or
  1×1 matrices, which are transpose-invariant — and now is.
- New opt-in "Show loop dominance" overlay on the Dynamic Simulation panel
  (#22): which feedback loop governs the system changes over a run, so the
  trajectory is shaded by its governing loop and each shift is named by its
  nodes. Loop identity is rotation-invariant and direction-preserving; shifts
  are margin- and dwell-gated, and the step reported is the raw-leader
  crossing rather than the later margin-clear. Timing describes the run, not
  a prediction — it depends on the initial state, and a share is an
  attribution rather than proof of causation.
- i18n: reviewed the Norwegian, Greek and Lithuanian loop-dominance strings.
  Greek called the loop's share a ποσοστό (percentage) beside a summary
  rendering a literal `%`, inviting the share to be read as that number; it
  is now μερίδιο. Lithuanian rendered "timing" as `Laikas` (time), now
  `Pokyčių laikas`.
- Intervention-simulation ranks are now decided by a paired test and no
  longer chain ties down the list (#21). A row shares a rank until it
  separates from the group *leader* rather than merely from its
  predecessor — separation is not transitive, so the old rule merged
  elements that were cleanly apart end to end and could collapse a
  gently-decreasing list toward a single rank. Separation is now measured
  on the per-batch difference between the two elements rather than by
  asking whether their two displayed margins overlap: both are fed by the
  same token draws, so competing sinks honestly tie more often and
  elements sharing an upstream path separate more sharply. Ranks on the
  sample model are unchanged.
- The intervention-simulation bar chart now draws the 95% margin as error
  bars (#20), so the chart no longer implies a precision the table already
  disclaims. Deterministic and single-batch runs carry no margin and draw
  no caps.
- Intervention simulation now reports its own sampling error (#19): each
  element carries a 95% margin (`1501 ±32`) and a rank that statistically
  tied elements share, so a near-tie is no longer displayed as a firm
  ranking, and a net sign of `~` now means "within sampling error" rather
  than "inside an arbitrary 5% band" — the old rule mislabelled balanced
  elements in about 12% of runs.
- New "Intervention simulation" block on the Intervention card (#17): seed
  tokens at any element and watch them diffuse along the causal links —
  negative links flip a token's sign — giving a ranked reach, net sign and
  first-arrival step per element, with a colour-coded chart. Lets two
  candidate intervention points be compared directly (Donlan et al. 2026,
  doi:10.21203/rs.3.rs-10397797/v1).
- New button-gated "Causal pathways" block on the Network Metrics card (#16):
  enumerate the directed simple paths between any two elements with compound
  polarity (odd negatives flip the sign), honest truncation, and a
  positive/negative/ambiguous summary (Applied Soft Computing 2026,
  doi:10.1016/j.asoc.2026.115925 — static layer only).
- Fix: feedback-loop enumeration is now bounded during generation (networkx
  length_bound), so dense imported models can no longer hang Loop Analysis,
  uncertainty scoring, or cascade vulnerability (#18); networkx floor is now 3.1.
- New button-gated "Cascade vulnerability" block on the Network Metrics card
  (#15): sequential removal of nodes in leverage order tracking connectivity
  collapse and surviving feedback loops, identifying the cascade threshold
  node whose loss causes the largest single-step drop (ERL 2026,
  doi:10.1088/1748-9326/ae83cb).
- New "Governance actor influence" table on the Network Metrics card (#14):
  whole-network centrality ranking (betweenness, eigenvector, PageRank, and a
  z-score composite equal to the leverage score) restricted to governance
  elements, revealing dominant vs. peripheral actors (Maritime Studies 2026,
  doi:10.1007/s40152-026-00501-z).
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
