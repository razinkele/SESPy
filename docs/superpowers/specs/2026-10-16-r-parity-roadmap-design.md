# R → SESPy parity roadmap — design

Date: 2026-10-16 (revised after review loops 1–3)
Baseline: MarineSABRES_SES_Shiny **v1.28.0** (`e3c3b77`, 2026-10-16; live on
laguna since 16:29) → SESPy **v1.12.1** + `[Unreleased]` fixes to `0543ed0`

## 1. Intent

SESPy is the Python port of the R Shiny MarineSABRES app, and the R app is
the source of truth. SESPy's ports were taken against R ≈ v1.11–1.16
(April–May 2026). Since then R has shipped v1.17 → v1.28.0. Those releases
add the Responses/Measures arm, the Response register, Decision Lens, the
reviewed curated templates, the WP5 suite and a deep-review hardening pass.
This roadmap brings SESPy to feature parity with R v1.28.0. R keeps moving
(two releases on 2026-10-15/16 alone), so §3 defines how drift is tracked
after the baseline.

**Parity runs one way (R → SESPy).** SESPy-only features (QSEM import and
multi-rater, Vester quadrant, governance gap, cascade vulnerability, causal
paths, token diffusion, Bayesian options, …) are kept unchanged. Nothing is
removed to match R.

### Decisions taken (2026-10-16)

| Question | Decision |
|---|---|
| WP5 scope | **Full WP5**: data layer, Response register, valuation, impact assessment + report, intervention designer (incl. 1.28 mode C / Apply) |
| Templates | **Add beside** SESPy's own 4; converted from R JSON, origin-labelled |
| Other R modules | **All in scope**: Scenario Builder, Response Measures page, Graphical SES creator, Guidebook/tutorial, plus the 8 older modules in §5 (P11–P14) |
| R project files | **Import only** (R → SESPy); SESPy keeps its own save format |
| Sequencing | **Foundation-first**, with Decision Lens as an early parallel track |
| Shared KB on laguna | **Vendored copies are the baseline.** An optional, guarded runtime override can point at R's live `data/` (see §3) |

### Verified facts the design rests on

- **Formats differ.** SESPy's `Project` is an elements/connections list. R
  templates are `dapsiwrm_framework.{driver…measure}` lists plus a
  `connections` list (`from_id, to_id, from_type, to_type, polarity,
  strength, confidence, description`), using the legacy type names
  `state`=MPF, `impact`=ES, `welfare`=GB, `measure`→Response. R projects are
  `{project_id, …, min_app_version, data: {metadata, pims, response_measures,
  isa_data, cld, analysis}}`, where `isa_data` holds category frames,
  `adjacency_matrices`, `matrix_dimnames` (the 1.20.0 sidecar) and
  `user_edited_matrices`.
- **SESPy's loader is closed-world.** `Project.from_dict`/`to_dict`
  (`sespy/data_structure.py:258-307`) handle five fixed blocks.
  `ProjectMetadata` drops unknown keys. `_isa_from_dict` builds `Element(**e)`
  *without* key filtering (`:142`), so a file whose elements carry new keys
  raises `TypeError` in older builds. `read_autosave` catches only
  `ValueError`/`OSError` (`sespy/autosave.py:70`).
- **SESPy validation already exists** and is strict:
  `validate_project_payload` rejects connections with unknown endpoints and
  rejects **self-loops** (`sespy/persistent_storage.py:82-102`).
- **SESPy has no transition-rule table.** `_CONN_TYPES` (10 pairs) only feeds
  the AI wizard scorer and the Claude backend. ISA entry accepts any pair and
  defaults polarity to `+`.
- **The quadrant is NOT at parity.** R MICMAC (`functions/network_analysis.R:274-335`)
  counts *unweighted* direct + 2-step reach, puts the high side strictly
  above the mean (`>`), and labels quadrants Relay / Influential / Dependent /
  Autonomous / Undifferentiated. SESPy (`network.py:1203`) is a weighted
  Vester sum with `>=` and its own labels (`undetermined` exists).
- **Already at parity:** eigenvector-centrality fallback. Boolean cap 12
  (R: 20); the server does not clamp `input.max_nodes()`
  (`analysis_boolean.py:102`), which is the R N16 bug.
- **No SESPy Connection field for link `description`.** All 320 R template
  links carry one. SESPy delay levels are immediate/short/long; R has
  immediate/short-term/medium-term/long-term plus a legacy numeric lag.
- **Shared KB on laguna.** `/srv/shiny-server/marinesabres/data` holds R's
  KB files (razinka:shiny, dir 775). SESPy (`/srv/shiny-server/SESPy`, worker
  user `shiny`) uses none of them today. MosaicSES reaches SESPy's package
  through the symlink `MosaicSES/sespy → SESPy/sespy`. R deploys extract
  with `tar` directly into the live directory (no atomic rename;
  subdirectories not owned by the deploy user are moved to `*.bak` first,
  `deployment/deploy-remote.ps1:358-370`). Stray files persist in `data/`
  (`*.backup-part-b`, `Caribbean_SES_Template_backup.json`, a user `PROJ_*.json`).
  Server files are **CRLF**: a raw byte hash differs from the local copy, a
  hash with CRs stripped matches it. The general KB's `"version": "1.0"` is not
  bumped on content change. The WP5 files carry `schema` (mechanisms),
  `schema_version`/`registry_version` (indicators, impact reference) or only
  `version` (intervention ops, rm synonyms; the general KB and
  `country_governance_db.json` also carry `"version": "1.0"`).

## 2. Sub-projects

Each sub-project gets its own brainstorm → spec → plan → subagent-TDD →
full e2e gate → release cycle.

```
P0 → P1a ─┬→ P2   (soft: K1)
          ├→ K1 ─┬→ P4 (also P1b) → P5 → P6a (also P1c) → P6b → P6c
          │      └→ P9
          ├→ P1b → P1c → P8 → P7a (also P3) → P7b
          └→ P3 (Python side)
P3's R-fixture capture can start at P0; its Python side needs P1a's
template mapper and link types. P10, then P11–P14 (§5); P12 may be
pulled earlier.
```
The per-section "Depends on" lines below match this graph.

### P0 — Forward-compatibility patch (ship first, as a patch release)
- `_isa_from_dict` filters element keys the way it already filters connection
  keys. `read_autosave` also catches `TypeError`/`KeyError`, so a
  newer-schema autosave never breaks startup.
- **Data protection, not just tolerance:** read the **raw payload's**
  `metadata.min_sespy_version` and `metadata.schema_version` *before*
  `Project.from_dict` runs. `from_dict` overwrites `schema_version` with the
  running build's (`data_structure.py:300`), so the loaded object cannot be used. If either is
  newer than the running build, warn in the UI and **block overwrite saves and
  autosave** for that project (offer "save as" only). Otherwise a newer file
  would load with `response_measures` / `r_passthrough` silently dropped and
  then be overwritten.
- New dataclass fields from here on are keyword-only with defaults.
- Shipped in two patch releases (amended 2026-10-17). **v1.12.2** went out
  first as the shared-autosave security hotfix (per-browser token) together
  with the `[Unreleased]` fixes and the `read_autosave` tolerance.
  **v1.12.3** ("P0b") adds the element-key filtering and the read-ahead
  protection. Mapping onto SESPy's I/O: Save is a browser download, so it is
  always "save as"; for a newer-build project it is allowed but warns and
  names the copy `…-older-format.json`. Autosave refuses the project, and a
  persistent toast with translated details appears on every load of one.
  The flag is a runtime field (`Project.newer_build`, never serialised,
  carried by `.replace()`). Either way, every deployed build from v1.12.3
  on tolerates the schema-v7 files that P1a onward will write.

### P1a — Link rules, template mapper (unblocks P2)
R source: 1.17.1, 1.18.0, 1.22.0 (N26/N61/N62), 1.22.3.
- New `constants.DAPSIWRM_ADJACENCY_RULES`, mirroring R's: pairs + default
  polarity + rule id + `extension_targets` (R→R, MPF→MPF, P→P, A→A, the D→P
  exception) + R→MPF (Rule 12, `+`). ISA entry takes its default polarity
  from it (P→MPF = `−`; R→MPF/R→R = `+`). `_CONN_TYPES` is derived from it.
- `Connection.description` (optional).
- **Template mapper**: legacy type names → SESPy types; Measures merge into
  Responses (measure→response links become R→R); per-element R extras
  (Caribbean `category`, `intensity`, `related_issues`, `indicator`,
  `baseline`, …) are kept in `Element.r_extra: dict`.
- `ProjectMetadata` gains declared fields `origin`, `r_template_version` and
  `min_sespy_version` (stamped, never lowered).
- **`PROJECT_SCHEMA_VERSION` → 7 here**, because P1a is the first release to
  write new fields. P1b and P1c add fields within v7 or bump again, and say so.
- Boolean hardening: clamp `input.max_nodes()` on the server side; keep
  `dynamics.boolean_attractors`' existing default (`max_nodes=12`) and add a
  module-level hard ceiling that P7 may override explicitly.
- `excel_import.py` column mapping extended for the new fields and link types.
- **Done when:** all 7 R templates convert, and SESPy save → load keeps their
  edge set **including** polarity, strength, confidence and description. The
  R fields not carried over are listed in the spec.

### P1b — Response register + indicator fields
R source: 1.19.0, 1.23.0 (WS-3a), 1.24.0 (WS-4). Depends on P1a.
- The **Response register is a separate block**, as in R:
  `Project.response_measures = {measures, impacts, milestones, counter}`.
  Measures use R's column names: `ID, Name, Type, Target, Description,
  Mechanism, TargetElement, Effectiveness, Feasibility, Cost, Status,
  Stakeholders, Barriers, DateAdded, Kind, EbmCode, GovernanceLevel,
  CompetentAuthority, LegalBasis, ImplementingStakeholders, PairedWith,
  Tenet_<11 codes>`.
- Code lists ported from R (`RM_TYPE_CODES`, `RM_TARGET_CODES`,
  `RM_STATUS_CODES`, `GOVERNANCE_LEVELS` (7), `TENET_LEVELS`; "intermediate"
  only for `ecol_effective`). The label → code reverse map covers all 9
  languages (`rm_reverse_label_map`).
- Element indicator fields with R's names: `Indicator, Indicator_Unit,
  Data_Source, Registry_Id, Registry_Version`, on **all elements except
  Responses**.
- Two version stamps, kept separate: SESPy's own `metadata.min_sespy_version`
  (introduced in P1a, honoured by P0), and `metadata.r_min_app_version`
  (copied from an R import's top-level `min_app_version`, used only for import
  diagnostics, never compared with SESPy's version).
- Explicit `to_dict`/`from_dict` code for every new block. Bump the schema version if a
  v7 reader would drop the block.

### P1c — R project importer + passthrough
R source: 1.19.0, 1.20.0 (N4/N5), 1.21.0 (N24/N25/N27/N50), 1.22.0.
Depends on P1a/P1b.
- Matrix → connection converter:
  - Cell grammar `±strength[:conf[:delay[:delay_years]]]`
    (`functions/utils.R:47-89`; a bare `+strong` takes the default
    confidence), including the legacy numeric lag.
  - Element columns are matched case-insensitively (R's JSON loader
    lowercases them, `data_structure.R:929`). The canonical indicator names are
    R's `ISA_INDICATOR_COLUMNS`.
  - The delay mapping is explicit: R medium-term goes into a new SESPy level
    or is documented as mapped to `short`; decide in the P1c spec.
  - Placement uses the `matrix_dimnames` sidecar, falling back to element-ID
    order for old files.
  - Legacy keys `p_mp`/`mp_es`, plus `r_mpf`/`r_r`.
  - Mismatches are reported *before* `validate_project_payload`. Diagonal
    (self-loop) cells are reported and kept out of the ISA.
- `Project.r_passthrough: dict` (default `{}`) with explicit
  `to_dict`/`from_dict` code. It holds R blocks SESPy does not support yet
  (`analysis.impact_assessment`, `analysis.scenarios`, `cld`, …). Legacy
  `data$scenarios` moves to `analysis.scenarios` (R `migrate_legacy_scenarios`).
- **Prerequisite fixture:** save an R v1.28.0 project that contains register
  measures with the WS-3a fields, R→MPF/R→R links, indicator fields, an
  impact assessment and a Designer-applied scenario with `links_modified`.
- **Done when:** importing the fixture, editing through each module's
  `.replace` path, autosaving and reloading keeps `r_passthrough`
  byte-equal and keeps the edge set (incl. delay and description).

### K1 — General knowledge-base parity
R source: `functions/ses_knowledge_db_loader.R`, `modules/ai_isa_knowledge_base.R`,
`functions/country_governance_loader.R`, `functions/kb_report_helpers.R`,
`functions/report_generation.R:140-174,481-499`,
`data/ses_connection_knowledge_base.R`. Depends on P1a.
- The KB loader implements the §3 "Reference data" rules (vendored + optional
  override). The same loader is used by P4.
- **`ses_knowledge_db.json`**: 33 sea × habitat contexts, each with D/A/P/S/I/W/R
  lists, connections, `generic_fallback` and 20 `cross_ecosystem_links`.
  These give offline element suggestions in SESPy's AI ISA wizard, next to
  `regional_seas.json`.
- **`country_governance_db.json`**: 97 countries, 11 seas and 8 conventions,
  giving governance context.
- **Regional Context** section in SESPy reports.
- **`SES_CONNECTION_DB`/`SES_SYNONYM_DB`** are live R code, so they get a
  one-off R → JSON export, vendored and hash-checked. Python cannot read
  `.R` at runtime, so the override does not apply to these.
- **Done when:** for 3 contexts, SESPy's suggestions equal R's
  `get_context_elements(min_relevance = 0.5)`.

### P2 — Curated templates
R source: 1.21.1, 1.22.1, 1.22.3. Depends on P1a; soft dependency on K1
(R templates say they were rebuilt from KB contexts).
- Convert the 7 R templates (Aquaculture, Caribbean v1.1, ClimateChange,
  Fisheries, OffshoreWind, Pollution, Tourism; versions 2.1–2.3), **320
  links** in total. Exclude `Caribbean_SES_Template_backup.json`. They need
  the P→P (8), MPF→MPF (13) and R→R (11) transitions; no template has R→MPF.
- Ship them in `sespy/templates/` beside SESPy's 4. Names get an origin
  suffix (R's "Offshore Wind Energy" sits beside SESPy's "Offshore Wind Farm
  SES"). e2e selectors are scoped: `test_templates_e2e.py:33` currently
  matches the substring "Offshore Wind".
- `scripts/sync_r_templates.py` re-converts the templates from a configured R checkout.
- **Done when:** each converted template's link count and signs equal the R JSON.

### P3 — Decision Lens (parallel track)
R source: 1.19.0, 1.20.0 (N17), 1.21.0 (N35/N36), 1.22.0 (N37/N52).
- **First task:** run R v1.28.0's `calculate_micmac_safe()` and
  `detect_archetypes()` on all 7 templates and commit the output as a test
  fixture.
- **R-exact MICMAC**, *beside* SESPy's Vester quadrant (which stays):
  influence = `rowSums(adj != 0) + rowSums(adj %*% adj != 0)`, dependence the
  column equivalent. High side strictly above the mean. Labels Relay /
  Influential / Dependent / Autonomous. **Undifferentiated** when all
  influence values are equal *and* all dependence values are equal, or there are no edges.
- Loops: `find_all_cycles(max_length = 8, max_cycles = 500)`, dropping cycles of
  ≤ 2 nodes.
- **Tragedy of the Commons**: an MPF/ES node in ≥ 2 loops whose union holds
  ≥ 2 distinct Activities (any loop type). MPF candidates come first, deduplicated
  by identical loop set. An ES candidate is dropped if its loops overlap an
  accepted MPF commons. Leverage = the shared node.
- **Limits to Growth**: any Reinforcing loop containing a D or A node that
  shares ≥ 1 node with a Balancing loop containing an R node *and* an MPF or ES
  node. Leverage = the first R node in the balancing loop's order. One record per
  leverage R.
- Deterministic, i18n-templated "why this matters" narrative, using the
  **per-session** translator (never `T._lang`).
- **Done when:** MICMAC and archetype output equal the R fixture on all 7 templates.

### P4 — Response Measures page + WP5 data layer
R source: 1.19.0, 1.22.0 (N48), 1.23.0, 1.24.0. Depends on P1b; loader from K1.
- Response register page (R `response_module.R`) on the P1b block.
- WP5 assets loaded through the §3 reference-data loader:
  `ses_knowledge_db_wp5_mechanisms.json` (`schema: 2`, 31 mechanisms),
  `wp5_indicators.json` (its `registry_version` is the value stamped into
  `Registry_Version`; its `schema_version` is the key used for the §3
  major-version check), `wp5_intervention_ops.json`,
  `wp5_rm_synonyms.json`. `translations/modules/wp5_vocabulary.json` lives
  outside `data/`, so it is **always vendored** (never overridden).
- "Linked WP5 mechanisms" pane, filtered by demonstration area (single resolver
  mirroring `wp5_da_for_project()`).
- WP5 indicator picker (snapshot + `Registry_Version`). On load, warn when the
  registry entry has changed since the copy.
- Model-check warnings (`wp5_typing_lint.R`).
- **Done when:** loaded asset counts and ids equal the vendored copy, and, when
  the override is set, the live copy too (integration test, skipped in CI).
  The pane, picker and warnings work in e2e.

### P5 — Valuation calculator
R source: 1.24.0. Depends on P4.
- As in R: D5.2 Table 19 range, the badged toolbox extensions, Excel export
  whose provenance is read from `metadata.reference_data` (see §3).
- **Done when:** 1 ha over 20 years gives €88,800 to €516,800.

### P6 — Impact assessment (three releases: 6a / 6b / 6c)
R source: 1.25.0, 1.26.0. Depends on P4, P5, P1c.
- **6a reference data:** `wp5_impact_reference.json` (Macaronesia Table 21,
  Arctic Tables 2–8, political feasibility), loaded as in R
  `functions/impact_reference.R` through the §3 loader.
- **6a data model:** as R `impact_assessment_model.R`, stored at
  `analysis.impact_assessment`, which replaces the P1c passthrough for this block.
  An assessment that fails to normalise is dropped on load with a warning, as R does
  (`data_structure.R:990`).
- **6b wizard**, **6c narrative + Word/Excel report**: Appendix B provenance is
  read from `metadata.reference_data`.
- **Analysis-preservation rule** (R 1.25.0): an ISA change clears only loops
  and metrics, never the scenarios or the impact assessment.
- **Done when:** an R-saved assessment imports, edits and saves back unchanged;
  the report generates; the narrative matches R for the same matrix.

### P8 — Scenario Builder (moved before P7)
R source: `scenario_builder_module.R` at v1.28.0 (1,381 lines), 1.21.0 N33,
1.28.0 fixes. Depends on P1c.
- R's schema:
  - A scenario is `{id, name, description, created, modified, results,
    modifications}`, plus `source` and `ops[]` **only on Designer-written
    scenarios** (`intervention_designer.R:498`). Builder scenarios
    (`scenario_builder_module.R:286-301`) have neither field, and their
    `links_added` have no `strength`.
  - `modifications` holds `nodes_added[{id,label,dapsi,description}]`,
    `nodes_removed`, `nodes_modified`, `links_added[{id,from,to,polarity,strength}]`,
    `links_removed` (edge ids) and `links_modified[{from,to,polarity,strength,previous_strength}]`.
    `links_modified` is matched by **endpoints**.
  - `ops[]` entries are `{op, from, to, weight, intervention_type, ebm_code}`,
    where `from`/`to` are node **labels**, not ids.
- R anchors scenarios to **CLD node and edge ids**. The P8 spec defines the
  mapping from R CLD ids to SESPy element ids and connection keys for both
  import and native use.
- Baseline and scenario loop counts use the shared cycle finder.
  `predict_impacts()` handles removed links (the 1.28.0 crash fix).
- **Done when:** loop counts and predicted impacts match R on a fixture, and the
  P1c fixture's applied scenario round-trips.

### P7a — Intervention designer, modes A/B
R source: 1.27.0. Depends on P1a, P3, P8.
- Mode A (new node) and mode B (new edges; the self-loop helper needs an
  explicit exemption from `validate_project_payload` or must stay out of
  the saved ISA, decided in the spec).
- Grid levels {−1, −0.5, −0.25, 0, 0.25, 0.5, 1}. Exhaustive, or a seeded
  sample (seed 20261014) of 65,536 above that size. Designs above 4.5 × 10^15
  combinations are refused.
- 1,000 steps, judged on the last 100. Also-sustain defaults to all GB nodes.
- Stability = all Laplacian eigenvalues real, checked first on rows passing
  (a) + (b), and stopped at 70% of the 600 s job budget with a partial notice.
- Top 20. Boolean pre-check up to 20 nodes, using P1a's explicit ceiling override.
- **Evidence priors:** `INTERVENTION_EVIDENCE_PRIORS` (e.g. behavioural
  0.25, regulatory 0.5) cap |level| per intervention type through
  `ses_evidence_prior_range()` (`constants.R:925`,
  `intervention_designer.R:110`). Badged as a toolbox extension, as in R.
- **Reproducibility:** R draws the initial state with `runif()` under seed
  20261014 (`intervention_designer.R:384`), and NumPy cannot reproduce R's
  stream. Either port R's Mersenne-Twister/`runif`, or load the fixture's x0
  into the test (decided in the P7a spec).
- **Execution:** SESPy's **first worker-process pattern**
  (`ProcessPoolExecutor`/`multiprocessing`, spawn-safe on Windows, Cancel =
  terminate the process, single-threaded BLAS). This is *not* the pgmpy
  `asyncio.to_thread` pattern, which cannot cancel and shares the GIL and BLAS.
- **Done when:** given the same x0, results reproduce R's D5.3 Tuscany
  fixture (50,176 combinations, the same top-20 set and ranking).

### P7b — Designer mode C, sensitivity, Compare, Apply
R source: 1.28.0. Depends on P7a, P8.
- Mode C: re-weight a link with its sign fixed, levels sign × {0.25, 0.5, 1}.
  Link ranking by dominant-eigenvalue sensitivity (`ses_link_sensitivity`).
  "What success depends on" table from 30 successes up.
- "Compare structure" (loops, leverage top 10, attractors) in the worker.
- "Apply to project" writes a P8 scenario with `ops` and `links_modified`.
- **Done when:** the Tuscany fixture's mode C results and the applied scenario
  match R.

### P9 — Graphical SES creator
R source: 1.20.0 N6 and the creator/network-builder modules. Depends on P1a, K1.
- Canvas builder; "Export to ISA" produces canonical SESPy ISA data.
- Type suggestions come from K1's KB and synonyms, not torch.
- **Done when:** a canvas model exports to ISA and renders in the CLD.

### P10 — Guidebook / tutorial
R source: `guidebook/guidebook_{9 langs}.Rmd`, `modules/tutorial_system.R`
(show-once tutorials per feature).
- The guidebook content goes into SESPy's Manual (About → Manual). Show-once
  tutorials go into the contextual Help offcanvas. No parallel help system.
- **Done when:** the guided tour runs across the main pages in all 9 languages.

## 3. Rules that apply to every sub-project

### Reference data (shared KB)
- **Vendored copies are the baseline.** R's data files are copied from an R
  git **tag** into `sespy/data/r_kb/`, using an explicit **allow-list** of file
  names (never a glob over `*.json`).
- **Optional runtime override:** `SESPY_R_DATA_DIR`, an absolute path (on
  laguna `/srv/shiny-server/marinesabres/data`).
  - **How it reaches the server process:** `deploy/config.env` stays on the
    developer machine and never ships (`deploy.sh` excludes `deploy/`). The
    value lives in a server-side settings file, `APP_DIR/server_settings.env`,
    owned by the server. `app.py` reads it at startup, and an environment
    variable of the same name takes precedence.
  - `deploy.sh` creates the file only if it is absent and otherwise
    **preserves** it, the same pattern as `feedback.db` (it is never clobbered).
  - MosaicSES runs as its own process, with its own `APP_DIR/server_settings.env`
    and the same key. Its deploy script preserves the file the same way.

  The loader:
  1. reads and parses the file;
  2. validates it:
     - the required top-level keys must be present;
     - entry counts must be ≥ the per-file minimum stated in the allow-list
       (never "equal to the vendored count");
     - the file's version key must have the same major as the vendored copy.
       The allow-list names that key per file: `schema` (mechanisms),
       `schema_version` (indicators, impact reference), `version`
       (`wp5_intervention_ops.json`, `wp5_rm_synonyms.json`,
       `ses_knowledge_db.json`, `country_governance_db.json`);
  3. publishes a new immutable snapshot atomically;
  4. re-stats size and mtime when a session starts and reloads on change.
     **Each session pins the snapshot current at its start**, so other live
     sessions never see data change underneath them, and that session's
     provenance comes from its pinned snapshot;
  5. on any failure, including a missing directory (R's deploy moves
     `data/` to `data.bak` if it ever becomes shiny-owned,
     `deploy-remote.ps1:360-362`), keeps the last good copy, else the vendored
     one, and logs one warning.

  It is strictly **read-only**: it never writes into R's directory (the
  directory is group-writable).
- **Allow-list (initial):** `ses_knowledge_db.json`,
  `country_governance_db.json`, `ses_knowledge_db_wp5_mechanisms.json`,
  `wp5_indicators.json`, `wp5_impact_reference.json`,
  `wp5_intervention_ops.json`, `wp5_rm_synonyms.json`, the 7
  `*_SES_Template.json` files (P2 only; converted, never read at runtime), plus the
  vendored-only `SES_CONNECTION_DB`/`SES_SYNONYM_DB` export (K1) and
  `wp5_vocabulary.json` (P4).
- **Provenance in projects:** on save, SESPy writes
  `metadata.reference_data = {file: {source: vendored|shared, sha256_norm,
  version, vendored_r_tag}}`. On load, SESPy warns when that differs from
  the session's pinned snapshot. When the recorded hash matches neither the
  vendored copy nor the live copy, it says "reference data unavailable;
  results may differ". P5/P6 provenance appendices read it. R records nothing for the
  general KB, so SESPy adds this.
- **Hashing:** `sha256_norm` = sha256 of the parsed JSON re-serialised with
  sorted keys, UTF-8 and LF. Never raw bytes: the server files are CRLF, and the R
  working tree mixes line endings.
- **Drift check:** `tests/parity/` asserts the vendored files match the hashes
  recorded in `docs/parity/R_SYNC.md`. `tests/parity/check_live.py`
  (read-only over SSH) compares the live laguna copies. `deploy/deploy.sh`
  runs it as a pre-flight step (SESPy has no `release.sh`, unlike MosaicSES),
  and it can also be run by hand after an R deploy.
  It is never run in CI or picked up by pytest collection. A mismatch blocks the next SESPy release until the files are
  re-vendored or the change is explicitly accepted in R_SYNC.md.
- **CI and tests** use vendored data only. The full e2e gate uses vendored data.

### Sync tracking
`docs/parity/R_SYNC.md` records, for each ported feature, the R version and commit it
matches (baseline v1.28.0 @ `e3c3b77`), plus each vendored file's
`sha256_norm`. R releases after the baseline are triaged into it.

### R stays the source of truth for data
Data is never re-typed. R's "toolbox extension" badges, "pre-final draft" badges
and partner-pending flags carry over exactly as R shows them.

### i18n
SESPy has 9 languages in one flat `sespy/translations/core.json`. R keys
(`modules.wp5_vocabulary.criteria.EE`) never match SESPy keys literally.
New WP5 and port strings **adopt R's `modules.*` namespace** in separate
`sespy/translations/*.json` files (so a sync script can copy them), and
older strings are mapped explicitly. e2e selectors stay scoped and namespaced.

### MosaicSES
MosaicSES builds `Project`/`Element`/`Connection` directly, reuses
`isa_data_entry_server` and `analysis_boolean_server` inside compartments,
and embeds SESPy Projects in `.multises.json`. Every **schema- or
ISA-entry-touching** sub-project (P0, P1a–c, P4, P8) runs MosaicSES's unit
tests and full e2e against the SESPy branch **before merge**, and checks the
live MosaicSES after deploy.

### Testing and releases
- Unit tests reproduce R's published numbers.
- Every sub-project passes the **full** e2e gate, with no heavy jobs running
  concurrently on the 16 GB machine.
- P0 = v1.12.2 (hotfix) + v1.12.3 (P0b). Then one minor release per sub-project, with **versions
  assigned in merge order** (P3 or K1 may ship out of sequence; P6 takes three).
  The CHANGELOG names the sub-project and the R version it matches. Bump the MANUAL
  version line and re-run the screenshots.

## 4. Out of scope

- Writing R-format JSON from SESPy (import is one-way).
- R-only infrastructure fixes: jsonlite round trips, observer leaks, callr,
  deploy scripts, i18n tooling, Shiny Server single-process hazards. The
  1.26.0 event-bus navigation fix applies only if a ported page links across tabs.
- The torch-based ML models. `ses_knowledge_db_offshore_wind.json` and
  `element_classifier_training.json` are offline training inputs in R, not
  runtime data.
- Changing or removing SESPy-only features.

## 5. Older R modules — all in scope (decided 2026-10-16)

These R modules are older than v1.17 (they first appear in R's git history
on 2026-05-18) and have no SESPy equivalent. The user brought all of them in
as four further sub-projects. Each gets its own brainstorm → spec cycle, and
its R source is pinned to the baseline at that time.

| Sub-project | R modules | Nearest SESPy feature | Depends on |
|---|---|---|---|
| **P11** Guided entry | `entry_point_module` (guided pathway), `workflow_stepper_module` | AI ISA wizard | P1a; after P10 so the tour and stepper are designed together |
| **P12** Experience levels | `get_level_config` / level config (menus, AI element caps; per-session store, R 1.20.0 N20) | — | P0. Can be pulled earlier, because it gates menus that later pages register into; decide at P1a review |
| **P13** Model library + connection review | `ses_models_module` (SES model library, server-mode path containment R 1.18.2/1.19.1), `connection_review_tabbed` (observer-leak fix R 1.21.0 N30) | templates; review inside the AI wizard | P1c (library files are R models), K1 |
| **P14** Report prep, feedback admin, pilot study | `prepare_report_module`, `feedback_admin_module` (admin-only actions, escaped user text, R 1.19.1), `pilot_study_module` | `report_export`; topbar feedback form (`feedback.db`) | K1 (Regional Context section), P6c (shared report pipeline) |

Already equivalent: `local_storage` ≈ autosave/persistent_storage;
`export_reports` ≈ `report_export`; event bus ≈ `event_bus.py`.

## 6. Risks

- **R keeps moving.** The baseline was overtaken within hours (v1.27 → v1.28).
  R_SYNC.md and `check_live.py` make that drift visible.
- **WP5 content is still moving.** The mechanism catalogue was released before
  partner sign-off (R 1.23 Q1); the EBM-code mapping in
  `wp5_intervention_ops.json` is provisional; the Arctic revenue tables
  conflict with D5.2's assumptions (partner question 2); the per-component
  participation ratio is an open item (R 1.28 notes). SESPy mirrors R's flags
  and never resolves them on its own.
- **Live override hazards:** a partially extracted file during an R deploy, or
  unreviewed edits in `data/`. These are mitigated by validate-then-swap and the
  last-good fallback; the override is off by default.
- **P7 compute cost** on laguna (shared host): a worker process, a hard
  size refusal and single-threaded BLAS.
