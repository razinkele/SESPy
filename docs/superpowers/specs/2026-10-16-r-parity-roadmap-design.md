# R → SESPy parity roadmap — design

Date: 2026-10-16
Baseline: MarineSABRES_SES_Shiny **v1.27.0** (`87999d1`, 2026-10-15) → SESPy **v1.12.1** (+ unreleased work to `0543ed0`)

## 1. Intent

SESPy is the Python port of the R Shiny MarineSABRES app, and the R app is
the source of truth. SESPy's ports were taken against R ≈ v1.11–1.16
(April–May 2026). Since then R has shipped v1.17 → v1.27.0. Those releases
add the Responses/Measures arm, Decision Lens, the reviewed curated
templates, the WP5 suite and a deep-review hardening pass. This roadmap brings SESPy to
feature parity with R v1.27.0.

**Parity runs one way (R → SESPy).** SESPy-only features (QSEM import and
multi-rater, governance gap, cascade vulnerability, causal paths, token
diffusion, Bayesian options, …) are kept unchanged. Nothing is removed to
match R.

### Decisions taken (2026-10-16)

| Question | Decision |
|---|---|
| WP5 scope | **Full WP5**: data layer, Response register, valuation calculator, impact assessment + report, intervention designer |
| Templates | **Add beside** SESPy's own 4; converted from R JSON, origin-labelled |
| Other R modules | **All in scope**: Scenario Builder, Response Measures page, Graphical SES creator, Guidebook/tutorial |
| R project files | **Import only** (R → SESPy); SESPy keeps its own save format |
| Sequencing | **Foundation-first**, with Decision Lens as an early parallel track |

### Verified facts the design rests on

- SESPy's `Project` is an elements/connections list. R stores
  `dapsiwrm_framework` + adjacency matrices. Loading R's
  `Fisheries_SES_Template.json` through `Project.from_dict` fails
  (`Connection.__init__() missing 'source' and 'target'`), so every R data
  asset needs a **converter**, not a copy.
- `sespy/data_structure.py` silently drops unknown metadata keys
  (logged warning). An R import would therefore lose R-only blocks unless a
  passthrough is added.
- Already at parity, no port needed: quadrant splits on the **mean** with
  `>=` (R's 1.22 N35 fix); Boolean attractor cap 12 (R: 20); eigenvector
  centrality has a fallback (R 1.25 fix). The R 1.19.1–1.21 jsonlite,
  observer, callr, deploy and i18n-tooling fixes are R-specific.
- SESPy has GB→R and R→D/A/P link types. It has **no** R→MPF or R→R types, no
  response register fields, no indicator fields, no archetypes, and nothing
  from WP5.

## 2. Sub-projects

Each sub-project gets its own spec → plan → subagent-TDD → full e2e gate →
minor release cycle. They run in this order (P3 may run in parallel with P1/P2).

### P1 — Schema extension + R importer (foundation)
R source: 1.17.1, 1.18.0, 1.22.0, 1.23.0, 1.24.0.
- Link types **R→MPF** (default `+`, Rule 12) and **R→R** (default `+`, Rule 14).
- **P→MPF default polarity `−`.** Transition table extended with
  R→R, MPF→MPF, P→P, A→A and the D→P exception, matching R's
  `DAPSIWRM_ADJACENCY_RULES` `extension_targets`.
- Response fields: EBM classification (instrument/measure + WP5 EBM type),
  governance level, competent authority, legal basis, implementing
  stakeholders (FK to PIMS stakeholders), strategy pairing, and appraisal against the 11 tenets. All of these are stored as
  **language-independent codes**.
- Element fields `indicator`, `unit` and `data_source`, plus WP5 indicator
  provenance (registry id and revision).
- `metadata.min_app_version` stamp (never lowered). On load, warn when a
  project needs a newer SESPy.
- **R importer, two entry points.** The file shapes were probed on 2026-10-16.
  - *Templates* (`dapsiwrm_framework.{drivers…measures}` lists +
    a `connections` list of `{from_id, to_id, from_type, to_type, polarity,
    strength, confidence, description}`): mostly renaming keys. Check R's
    `template_loader.R` for the mapping before writing it. Measures merge into
    Responses (R 1.22.3 loader fix).
  - *Projects* (`{project_id, …, data: {metadata, pims, isa_data, cld,
    responses, analysis}}`, where `isa_data` holds category lists +
    `connections` + `adjacency_matrices`): matrices become connections,
    including the 1.20.0 dimnames sidecar and the `+medium:5` cell format.
  - R blocks that SESPy does not support yet (e.g.
    `analysis.impact_assessment`, `analysis.scenarios`) are kept in a
    `Project.r_passthrough` field and written back on save.
- **Prerequisite fixture:** save an R v1.27.0 project that contains Responses with the
  1.23 register fields, R→MPF and R→R links, element indicator fields, an impact
  assessment and scenarios. The only R project in R `data/` dates from April.
- **Hardening (R N16 equivalent):** the Boolean module reads
  `input.max_nodes()` without clamping it to the slider's 12. Clamp it on the server side
  and enforce the cap in `dynamics.boolean_attractors` itself.
- Load-time **matrix/element alignment check**, adapted to SESPy's model:
  warn about connections whose endpoints are not elements.
- **Done when:** an R v1.27 project and all 7 R templates import, and they survive a
  SESPy save → load round trip with the same edge set (source, target, sign, strength,
  confidence).

### P2 — Curated templates
R source: 1.21.1, 1.22.1, 1.22.3 (sign-reviewed, 305 links).
- Depends only on P1's *template* entry point (not the matrix importer).
  It can ship as soon as the R→MPF and R→R link types and that mapper exist.
- Convert the 7 R templates (Aquaculture, Caribbean, ClimateChange,
  Fisheries, OffshoreWind, Pollution, Tourism) with the P1 template mapper. Ship
  them in `sespy/templates/` beside SESPy's 4. Each card shows its origin and the R template
  version.
- `scripts/sync_r_templates.py` re-converts the templates from a configured R checkout.
- **Done when:** the cards render and each converted template's link count and signs equal
  the R JSON (checked by a test).

### P3 — Decision Lens (parallel track)
R source: 1.19.0, 1.22.0 (N35/N37/N52), 1.21.0 (N17).
- **First task:** run R v1.27.0's `detect_archetypes()` and
  `calculate_micmac_safe()` on all 7 templates and commit the output as a
  test fixture.
- Archetype detection: **Tragedy of the Commons** (a shared MPF or ES
  stock drawn on by ≥2 Activities; reported once per commons) and **Limits to
  Growth** (the GB→D reinforcing engine checked by a Response-mediated balancing loop
  that passes through an MPF or ES node; one record per leverage Response).
- **Undifferentiated** quadrant state when every node has the same
  influence and dependence, or when there are no links.
- Deterministic, i18n-templated "why this matters" narrative (quadrant
  role × loop participation × archetype leverage). Never generated by a model.
- Builds on the existing `analysis_quadrant` module (no second MICMAC).
- **Done when:** archetype results match R's `detect_archetypes()` output
  on all 7 templates, using a fixture generated from R v1.27.0. The counts have changed
  across R 1.22.0–1.22.3, so take them from R and don't copy them from the changelog.
  Fisheries must show no Limits to Growth.

### P4 — Response Measures page + WP5 data layer
R source: 1.19.0, 1.23.0, 1.24.0. Depends on P1.
- Response register page (create, edit and list Responses with the P1 fields).
- WP5 data assets copied **verbatim** from R `data/`:
  `ses_knowledge_db_wp5_mechanisms.json` (31 mechanisms, D5.2 v5),
  `wp5_indicators.json`, `wp5_intervention_ops.json`,
  `wp5_rm_synonyms.json`, and the vocabulary from R
  `translations/modules/wp5_vocabulary.json`. Python loaders mirror
  `wp5_kb_loader.R` / `wp5_vocabulary.R`.
- "Linked WP5 mechanisms" pane, filtered by demonstration area (single resolver
  mirroring `wp5_da_for_project()`).
- WP5 indicator picker in ISA entry: it copies a snapshot of the values and
  records the revision. On load, warn when the registry entry has changed since the copy.
- Model-check warnings (`wp5_typing_lint.R`): Drivers, Activities or Ecosystem Services named like
  policy instruments (whole-word, 9 languages, excluding the ES sense of
  "regulation"), and Responses that receive no link from MPF, ES or GB.
- **Done when:** a test checks the loaded asset counts and ids against R's JSON, and
  the pane, picker and warnings work in e2e.

### P5 — Valuation calculator
R source: 1.24.0 (`valuation_calculator_module.R`). Depends on P4.
- Posidonia benefit-transfer values from D5.2 Table 19: annual range and undiscounted total
  over a chosen horizon. Toolbox extensions badged as in R: midpoint;
  discounting at 0/3/5/7% plus a custom rate; restoration cost versus €100k–500k/ha;
  survival-adjusted cost (38–60%); break-even horizon. Excel export with provenance.
- **Done when:** 1 ha over 20 years gives €88,800 to €516,800.

### P6 — Impact assessment (three releases, mirroring R WS-6a/6b/6c)
R source: 1.25.0, 1.26.0. Depends on P4, P5.
- **6a data model:** criterion × scenario ordinal cells (direction,
  magnitude, timing, confidence, evidence, uncertainty driver, rationale,
  EQ/PI notes, linked indicators and mechanisms). Up to 5 scenarios + baseline. Rule: low
  confidence needs an uncertainty driver. Displacement check. Copy from the reference
  data (`wp5_impact_reference.json`), recording its version. Stored at
  `analysis.impact_assessment`, which replaces the P1 passthrough for this block.
- **6b wizard:** the seven D5.2 §1.4 steps, each gated by the model's problem
  checks. Read-only Macaronesia Table 21 and Arctic Tables 2–8 panels. Empty
  state for Tuscany. Heat map (arrow = direction, fill = magnitude (badged),
  hatching = low confidence).
- **6c report:** deterministic trade-off narrative (step 6) and a Word/Excel
  report with Appendix A (mechanisms) and Appendix B (provenance).
- **Done when:** an R-saved assessment imports, edits and saves back unchanged; the
  report generates; the narrative matches R for the same matrix.

### P7 — Intervention designer (D5.3)
R source: 1.27.0. Depends on P1, P3.
- Mode A (new intervention node) and mode B (new edges, including the self-loop
  helper). Exhaustive ordinal grid (−1…1), or a seeded sample of 65,536 above that
  size. D5.3 objective, also-sustain and stability ranking. Boolean
  pre-check, skipped above **SESPy's cap of 12 nodes** (R uses 20). The P7
  spec decides whether to raise SESPy's cap for the pre-check only, now that it
  runs in a worker process. Top-20 comparison.
- Runs as a Shiny **ExtendedTask** in a worker process (the pgmpy pattern) with Cancel.
  Single-threaded BLAS. Designs above 4.5 × 10^15 combinations are refused.
- **Done when:** results reproduce R's D5.3 Tuscany fixture (50,176 combinations,
  same top-ranked combinations).

### P8 — Scenario Builder
R source: `scenario_builder_module.R` (1,451 lines; 1.21 N33 fix). Depends on P1.
- What-if CLD edits (add, remove or re-sign links and nodes) compared with the baseline
  loops through the shared cycle finder. Stored at `analysis.scenarios`
  (round-trips with R imports through P1).
- **Done when:** baseline and scenario loop counts match R on a fixture.

### P9 — Graphical SES creator
R source: `graphical_ses_creator_module.R`, `graphical_ses_network_builder.R`
(+ AI classifier and ML enhancer), 1.20.0 N6.
- Canvas builder whose "Export to ISA" produces canonical SESPy ISA data.
- Element-type suggestions only through a non-torch path (rule- or
  knowledge-base-driven, as in `ai_isa_knowledge_base`). The torch ML enhancer is out
  unless a lightweight equivalent exists.
- **Done when:** a canvas model exports to ISA and renders in the CLD.

### P10 — Guidebook / tutorial
R source: `guidebook_module.R`, `tutorial_system.R`.
- Guided tour and guidebook content merged into SESPy's existing Manual (About →
  Manual) and contextual Help offcanvas. No parallel help system.
- **Done when:** the guided tour runs across the main pages in all 9 languages.

## 3. Rules that apply to every sub-project

- **Sync tracking.** `docs/parity/R_SYNC.md` records, for each ported feature, the
  R version and commit it matches (baseline v1.27.0 @ `87999d1`).
  `tests/parity/` holds hash checks for each R data asset SESPy depends on,
  so a change in R shows up as a failing, reviewable item, not silent
  drift.
- **R stays the source of truth for data.** R JSON assets are copied verbatim with
  their provenance fields and never re-typed. R's "toolbox extension" badges,
  "pre-final draft" badges and partner-pending flags carry over exactly as R shows them.
- **i18n.** Every new string is translated into all 9 languages, taking R's translations where
  the keys match. e2e selectors stay scoped and namespaced (no bare `text=`
  on strings another module also renders).
- **Testing.** Unit tests reproduce R's published numbers. Each
  sub-project passes the **full** e2e gate (never `-k "not e2e"`), with no
  heavy jobs running concurrently on the 16 GB machine.
- **Releases.** One minor SESPy release per sub-project (v1.13.0 onward; P6
  may take three). The CHANGELOG names the R version it matches. Bump the MANUAL
  version line and re-run `tests/make_docs_screenshots.py`. After each SESPy
  deploy, re-check MosaicSES (it symlinks SESPy's package).

## 4. Out of scope

- Writing R-format JSON from SESPy (import is one-way).
- R-only infrastructure fixes: jsonlite round trips, observer leaks, callr,
  deploy scripts, i18n tooling, Shiny Server single-process hazards.
- The torch-based ML connection and classification models.
- Changing or removing SESPy-only features.

## 5. Risks

- **WP5 content is still moving.** The mechanism catalogue was released before partner sign-off
  (R 1.23 Q1), the EBM-code mapping in `wp5_intervention_ops.json` is provisional, and the Arctic revenue
  tables conflict with D5.2's stated assumptions (partner question 2). The hash checks
  will flag R updates. SESPy mirrors R's flags and never resolves them on its own.
- **Schema churn in R.** If R adds project fields, the P1 passthrough keeps them
  intact on import. Proper support is a new parity item.
- **P7 compute cost** on laguna (shared host): an ExtendedTask with a worker process and
  a hard size refusal, as in R.
