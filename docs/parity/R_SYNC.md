# R sync record

SESPy reads a few files from the R MarineSABRES SES Toolbox. The copies under
`tests/parity/` are **test fixtures**: they never ship to the server. Since
SESPy 1.14.0 the 7 R templates also ship, as SESPy projects converted from
those fixtures (`sespy/templates/marinesabres/`). This page is the human
record of which R release they come from. The machine-readable pin is
[`tests/parity/r_sync.json`](../../tests/parity/r_sync.json), which
`tests/parity/test_r_sync.py` checks; it also checks that this page lists
exactly the same hashes. The sync script
(`python -m scripts.sync_r_templates`) updates the pin, the hashes and the
generated block below together; never edit the block by hand.

## Current pin

<!-- r-sync:begin -->
- **R release:** MarineSABRES_SES_Shiny **v1.33.0**, commit `4017feb`.

| File | Hash |
|---|---|
| `tests/parity/r_rules/dapsiwrm_connection_rules.R` | `ca4294f10974af34adf7dad9fe029318955c1c498356224b656a3e69525422a5` |
| `tests/parity/r_source/constants.R` | `27bdf3c7902c5ce602515ae448d6f81912edd5c9836672c1741650d3c0c42bc3` |
| `tests/parity/r_source/response_measures_schema.R` | `ac3de5f9dbfb87d9451ae6cc3c8a0e3e12594c10a7253def09565e55ce34c9b7` |
| `tests/parity/r_source/stakeholder_schema.R` | `489311719ba13863a0ae84934fa4116378736b52c41374d1b957da1354ee1bce` |
| `tests/parity/r_source/template_loader.R` | `3ebe6c83a737ead8e91936f9f11ca5cfa4244d56d52f1644fc7df2af131d02d3` |
| `tests/parity/r_templates/Aquaculture_SES_Template.json` | `d24154498ce843d0f10e2b724340ca63878002e63486132d933ef777d844c946` |
| `tests/parity/r_templates/Caribbean_SES_Template.json` | `7c38efa11232215eea9754c2831e8beaec31eb8d7a90618a16d3834af9bd5961` |
| `tests/parity/r_templates/ClimateChange_SES_Template.json` | `ab8cbaca91842fdc8cf87e46d0b0d20e14d298f38c21379dcaf27c8650f92ae3` |
| `tests/parity/r_templates/Fisheries_SES_Template.json` | `f04c3673afad34f2424e3ebaf3944f9e117dda87efb537960e4c14ef16c04da6` |
| `tests/parity/r_templates/OffshoreWind_SES_Template.json` | `a7657b88a1046d0590e4dcfdea39852cf2a4cdfa7629a2f14564753079c6debf` |
| `tests/parity/r_templates/Pollution_SES_Template.json` | `d3da39cf77605a35c7d3accbdd4b37830753443230f88d22c59e971c60332e56` |
| `tests/parity/r_templates/Tourism_SES_Template.json` | `1c0af86d3737cdb306ccc8eb0107fbe1ac75b41c4fede2dd56dc265c9983662e` |
| `tests/parity/r_translations/indicator_registry.json` | `b8ec68a82ca57afdf160db2c1e7dc479e9b2721d8843555c1ca637efa3bbc4f8` |
| `tests/parity/r_translations/response_governance.json` | `ff962cd5156fcbd14c33c3b17d74fc1073e99270b00f1aef102982fe2d2fc6a6` |
| `tests/parity/r_translations/response_measures.json` | `94103aabca9cb51076fb0ff10d21c0f38b0d53b95114457ca0b64f905e04728b` |
| `tests/parity/r_translations/wp5_governance.json` | `ebeb2c7553879c58f733654525f0c3e570c5fc92889df2b6e2355bd1a3e40276` |
| `tests/parity/r_translations/wp5_scenarios.json` | `5ba25f38cfda9b2bbbcba6b2d0d18594ba8638de34bf38f15caa0998d6af4ef6` |
| `tests/parity/r_translations/wp5_vocabulary.json` | `e4607ea6dadebea817e65aa873e9584d2ae65ec0e119e5d7be7293f48762591a` |

**Accepted sync warnings:** none.
<!-- r-sync:end -->

- **Adopted in:** SESPy 1.15.0 (P1b: response register, indicator fields,
  stakeholder roles). The previous pin, v1.31.0 (`4b53b7d`), was adopted in
  SESPy 1.14.0 (P2); before it, v1.29.0 (`e33faea`) in SESPy 1.13.0 (P1a).
- **Roadmap baseline:** moved from v1.31.0 (`4b53b7d`) to v1.33.0
  (`4017feb`), the release laguna runs. The 9 files pinned since P2 are
  unchanged between the two tags (`git diff --quiet v1.31.0 v1.33.0 -- <the
  9 paths>` exits 0). P1b adds 9 fixtures: `constants.R`,
  `functions/response_measures_schema.R`, `functions/stakeholder_schema.R`
  (the register and stakeholder ports are tested against them) and 6
  `translations/modules/*.json` files, whose key subsets ship as
  `sespy/translations/modules/*.json` (written by the sync).

The JSON templates are hashed with `sespy.r_sync.sha256_norm` (the parsed
JSON, so key order, CRLF and a BOM do not matter). The `.R` files are hashed
with `sespy.r_sync.sha256_text_norm` (text with CRLF normalised to LF).
`Caribbean_SES_Template_backup.json` is not a fixture.

## Laguna verification (2026-10-17)

The R app deployed on laguna (`/srv/shiny-server/marinesabres`) was
v1.29.0 on 2026-10-17. Its 7 templates and its
`functions/dapsiwrm_connection_rules.R` have the same hashes as the local
checkout, so the pin above matches what users run. This check covered the 8
files P1a pinned; `functions/template_loader.R` (pinned since SESPy 1.14.0)
is pinned from git only and was not checked on laguna. The 9 pinned files
are identical at v1.29.0 and v1.31.0, so a laguna R still at v1.29.0 does
not affect them.

**Re-checked 2026-10-20 (SESPy 1.14.0 release):** laguna's R app had moved
to v1.33.0 (`VERSION` and `DESCRIPTION`). All 9 pinned files, now including
`functions/template_loader.R`, hash identically on laguna and at the
v1.31.0 pin. The checked files were the 7 `data/*_SES_Template.json`, the
connection rules and the template loader, hashed with `sha256_norm` /
`sha256_text_norm`. The pin therefore still matches what laguna users run.

## Adopting a new R release

1. From the SESPy repo root run
   `micromamba run -n shiny python -m scripts.sync_r_templates --r-root <R app dir> --rev vX.Y.Z`
   (`<R app dir>` is `.../SESToolbox/MarineSABRES_SES_Shiny`). It reads the
   inputs with `git show` (it never checks out, switches or stashes in the R
   repo), converts the 7 templates, and rewrites the fixtures,
   `tests/parity/r_sync.json`, the shipped `sespy/templates/marinesabres/`
   files and the generated block above in one go. Off-rule links or type
   mismatches make it fail; after reviewing them, rerun with
   `--accept-warnings` and they are listed in the block.
2. Review the diff (`git diff --stat`, and the `hash ...: old -> new` lines
   the script prints), then triage R's changes since the previous pin into a
   table like the one below: one row per path of
   `git -C <R app dir> diff --name-status <old tag> <new tag>`, each with an
   owner sub-project or "not relevant".
3. Run the gates: `tests/parity/`, `tests/test_r_template_mapper.py`,
   `tests/test_r_template_catalogue.py`, `tests/test_templates.py`, then the
   CI unit command and the full e2e gate. A red `test_r_rules_parity.py`
   means R's rule table changed (`sespy/constants.py::DAPSIWRM_ADJACENCY_RULES`
   must follow); a red `test_r_category_parity.py` means R's
   `.determine_template_category` changed (`sespy/r_template_catalogue.py`
   must follow). Finally `python -m scripts.sync_r_templates --r-root <R app dir> --check`
   must report no drift.

Live drift against laguna (`tests/parity/check_live.py`) is owned by **K1**
in the R-parity roadmap; P1a and P2 read R only through these fixtures and
the sync script.

## R changes v1.31.0 → v1.33.0 (triaged 2026-10-22)

`git -C <R app dir> diff --name-status v1.31.0 v1.33.0`: 71 paths, all
under `MarineSABRES_SES_Shiny/` (prefix omitted). The 9 files SESPy pinned
before P1b (the 7 templates, `functions/dapsiwrm_connection_rules.R` and
`functions/template_loader.R`) are identical at the two tags (`git diff
--quiet v1.31.0 v1.33.0 -- <the 9 paths>` exits 0). P1b adds 3 R sources
(`constants.R`, `functions/response_measures_schema.R`,
`functions/stakeholder_schema.R`) and 6 translation files to the pin, at
v1.33.0; 3 of those 9 changed since v1.31.0 (rows 11, 19 and 67), the other 6
did not. R 1.32.0 = WS-10 workshop elicitation (D5.2); R 1.32.1–1.32.3 =
WS-10 follow-ups (tenet validation, translated workbooks); R 1.32.4 =
feedback-list fix and triage skill (not WS-10); R 1.33.0 = user-feedback fixes
(AI-assistant templates and connection review, reports and plot downloads,
loop plots, Scenario Builder, user level, Getting Started, Caribbean
countries). P15 is the proposed new sub-project for WS-10 (after P4; it
writes `TenetSource`).

| # | Status | Path | Change | Owner |
|---|---|---|---|---|
| 1 | D | `.claude/settings.local.json` | personal Claude Code permissions file untracked (`035a3d9`) | not relevant |
| 2 | M | `.claude/skills/feedback-triage/SKILL.md` | feedback-triage skill also triages the fallback feedback log; confirm step no longer puts the title in an ssh command | not relevant |
| 3 | M | `.claude/skills/feedback-triage/mark_resolved_remote.R` | marker writes `null` as null and keeps the log's group and mode | not relevant |
| 4 | M | `.gitattributes` | `text eol=lf` for `data/wp5_tenet_guiding_questions.json` | not relevant |
| 5 | M | `.gitignore` | ignores `.claude/settings.local.json` | not relevant |
| 6 | M | `CHANGELOG.md` | 1.32.0–1.33.0 entries (source of this triage) | not relevant |
| 7 | M | `DESCRIPTION` | version 1.33.0; `testthat (>= 3.1.7)` | not relevant |
| 8 | M | `VERSION` | version 1.33.0 | not relevant |
| 9 | M | `VERSION_INFO.json` | version metadata ("User feedback fixes (October 2026)") | not relevant |
| 10 | M | `app.R` | loads `modules/wp5_workshop_module.R`, adds the `pims_workshops` tab and passes the register API returned by `response_measures_server` to `wp5_workshop_server` (P15); passes `project_data` to the user-level modal handlers (P12) | P12, P15 |
| 11 | M | `constants.R` | `TenetSource` appended as the 34th and last `RM_REGISTER_COLUMNS` entry (after the 11 `Tenet_*`; default `""`; not in `RM_DISPLAY_COLUMNS`; R 1.32.0) (P1b); `WORKSHOP_*` constants and `WP5_WORKSHOP_MIN_APP_VERSION` = "1.32.0" (P15) | P1b, P15 |
| 12 | M | `data/country_governance_db.json` | 99 → 105 countries (+MQ, GP, MF as EU members; +HN, NI, GT as `latin_american`); Caribbean list 21 → 27; 11 seas and 15 conventions/bodies unchanged; `version` still `1.0` and `last_updated` unchanged | K1 |
| 13 | A | `data/wp5_tenet_guiding_questions.json` | D5.2 Annex 4 tenet guiding questions: 11 English texts in `EBM_TENETS` order with source page, plus the 5-point scale codes | P15 (§3 allow-list) |
| 14 | A | `docs/superpowers/plans/2026-10-18-wp5-ws10-workshop-elicitation.md` | R plan (reference reading) | not relevant |
| 15 | A | `docs/superpowers/specs/2026-10-18-wp5-ws10-workshop-elicitation-design.md` | R spec (reference for P15) | not relevant |
| 16 | M | `functions/data_structure.R` | JSON load runs `normalize_workshops` on `data$data$pims$workshops` and stamps `min_app_version` 1.32.0 when a workshop or a `TenetSource` value exists (P15); also calls `repair_template_connection_matrices` (R-only matrix storage, not relevant) | P15 |
| 17 | M | `functions/feedback_analyzer.R` | feedback-log loader tolerates `{}` and `[]` fields; mark functions write `null` as null (1.32.4) | not relevant |
| 18 | M | `functions/report_generation.R` | `generate_full_content(data, sections)` honours the Prepare Report section ids; new DAPSI(W)R(M) elements and CLD summary sections; recommendations text follows its checkbox | P14 / P6c |
| 19 | M | `functions/response_measures_schema.R` | `normalize_response_measures` validates tenet levels (1.32.1): case and spaces tidied, only `TENET_LEVELS` codes kept, `intermediate` only on `ecol_effective`, anything else blanked and logged | P1b |
| 20 | M | `functions/scenario_network.R` | `scenario_baseline_edges()`: a saved CLD without edge ids or labels gets `from->to` ids and node labels; removing links on a CLD without edges no longer errors | P8 |
| 21 | M | `functions/ui_sidebar.R` | PIMS menu item `pims_workshops` ("Workshop elicitation (D5.2)") | P15 |
| 22 | M | `functions/wp5_readiness.R` | `xl_translate_headers()`: readiness template and export workbooks get translated column headers, the `answers` sheets keep code headers; the workshop workbook shares the helper (1.32.2) | P4 |
| 23 | A | `functions/wp5_workshop.R` | workshop helpers: storage and `normalize_workshops`, poll and tenet summaries, write-back proposal (median ≥ 4 full; 3 to 4 intermediate on `ecol_effective`, otherwise minimal; below 3 minimal; at least 3 valid ratings), apply records with undo, multilingual template import, xlsx template and export | P15 |
| 24 | M | `global.R` | sources `functions/wp5_workshop.R` | P15 |
| 25 | M | `modules/ai_isa/action_handlers.R` | the preview window's Save calls the assistant's save (it only showed a message); AI wizard parity, re-check then | P13 |
| 26 | M | `modules/ai_isa/data_persistence.R` | connections go to the forward matrix of their category pair (`AI_ISA_FORWARD_MATRIX`); the reverse matrix of a swap starts as `""`, not `0`; `apply_connection_swaps` refuses a swap whose reversed pair is not a DAPSIWRM link; `repair_template_connection_matrices` rebuilds legacy-named matrices (R-only storage, not relevant); AI wizard parity, re-check then | P13 |
| 27 | M | `modules/ai_isa/template_handlers.R` | the 4 assistant templates (overfishing, pollution, tourism, climate) use the current matrix names (`d_a`, `a_p`, `p_mpf`, `mpf_es`, `es_gb`) instead of legacy ones (R-only storage); AI wizard parity, re-check then | P13 |
| 28 | M | `modules/ai_isa_assistant_module.R` | swaps go through `apply_connection_swaps` (refused ones are left out and reported); Save always saves the current state (it returned early after the auto-save) | P13 |
| 29 | M | `modules/analysis_decision_lens.R` | factor plot built once for the page and a new PNG download; headroom so the top labels are not clipped | P3 |
| 30 | M | `modules/analysis_leverage.R` | PNG export button on the leverage network; re-triage when the owning analysis is ported | not relevant |
| 31 | M | `modules/analysis_loops.R` | loop strength and reinforcing/balancing distribution plots were blank, now drawn; participation plot labels no longer cut off; PNG downloads and PNG export on the loop network; re-triage when the owning analysis is ported | not relevant |
| 32 | M | `modules/analysis_simplify.R` | PNG download of the impact chart and PNG export on the network views; re-triage when the owning analysis is ported | not relevant |
| 33 | M | `modules/entry_point_module.R` | Getting Started steps 2–4: checkbox ticks are stored when the user leaves the step, not on every tick (flicker, lost ticks); Skip clears the step | P11 |
| 34 | M | `modules/export_reports_module.R` | after the HTML report opens, a dialog offers it as a download and says the link only works during the session; SESPy's `report_export` already downloads directly | P14 / P6c |
| 35 | M | `modules/prepare_report_module.R` | HTML, PDF and Word pass the "Include sections" checkboxes (`options$sections`); Word uses `generate_report_content` and `render_report_safely` instead of `generate_word_report` (same content as HTML); same download dialog | P14 / P6c |
| 36 | M | `modules/response_module.R` | register API gains `update(id, fields)` (merges into the row, re-normalises, syncs to the project; FALSE for an unknown ID; `Cost` as a number) and the server now returns the API plus `data` (1.32.0) | P1b |
| 37 | M | `modules/scenario_builder_module.R` | uses `scenario_baseline_edges`, so creating a scenario on a CLD without edge ids no longer ends the session | P8 |
| 38 | A | `modules/wp5_workshop_module.R` | PIMS "Workshop elicitation (D5.2)" page: set-up, entry (form or xlsx/csv template, consent gate), results (poll ranking, tenet heat table, xlsx export), apply to the register with undo | P15 |
| 39 | A | `scripts/tests/test_wp5_tenet_questions.py` | R's data-file test: the 11 questions are found in D5.2 Annex 4 (pp. 219–222) | P15 |
| 40 | M | `server/modals.R` | `stash_project_before_reload()`: changing the user level keeps the project across the page reload, as the language change does; a failed stash cancels the change | P12 |
| 41 | M | `server/project_io.R` | toast after loading a project whose template links were rebuilt ("N links restored"); R-only repair, re-check with AI wizard parity | P13 |
| 42 | M | `tests/ci_run_file.R` | CI runner reads the zero-pass allowlist before running the test file | not relevant |
| 43 | A | `tests/testthat/test-ai-isa-save-after-autosave.R` | AI assistant Save and preview Save after the auto-save | P13 |
| 44 | A | `tests/testthat/test-ai-isa-swap-validity.R` | `apply_connection_swaps` refuses invalid reversals, applies valid ones | P13 |
| 45 | A | `tests/testthat/test-ai-isa-template-connections.R` | every approved connection of the 4 assistant templates appears in the diagram | P13 |
| 46 | A | `tests/testthat/test-analysis-loops-plots.R` | loop plots render and download | not relevant |
| 47 | A | `tests/testthat/test-analysis-plot-downloads.R` | Decision Lens factor plot and simplification impact chart PNG downloads, network PNG export | P3 |
| 48 | M | `tests/testthat/test-entry-point-module.R` | ticks committed on leaving the step; Skip clears them | P11 |
| 49 | M | `tests/testthat/test-feedback-analyzer.R` | feedback loader tolerates `{}` and `[]` fields | not relevant |
| 50 | M | `tests/testthat/test-knowledge-base.R` | Caribbean list includes MQ, GP, MF (EU members) and HN, NI, GT; every country listed for a sea has a record | K1 |
| 51 | M | `tests/testthat/test-prepare-report-module.R` | HTML download dialog; Word report uses the shared content | P14 / P6c |
| 52 | A | `tests/testthat/test-repair-template-matrices.R` | `repair_template_connection_matrices` rebuilds forward matrices from the saved connection list | not relevant |
| 53 | A | `tests/testthat/test-report-sections.R` | `generate_full_content(sections)`: section ids, DAPSI(W)R(M) elements, CLD summary | P14 / P6c |
| 54 | M | `tests/testthat/test-response-measures-schema.R` | tenet-level validation: invalid values and `intermediate` outside `ecol_effective` blanked, case and spaces tidied, idempotent | P1b |
| 55 | M | `tests/testthat/test-response-module.R` | register API: `update` merges and re-normalises, FALSE for an unknown ID, the server returns the API | P1b |
| 56 | M | `tests/testthat/test-scenario-builder-module.R` | activating a scenario on a CLD without edge ids does not close the session | P8 |
| 57 | M | `tests/testthat/test-scenario-network.R` | `scenario_baseline_edges` ids and labels; removed links on a CLD without edges | P8 |
| 58 | A | `tests/testthat/test-user-level-keeps-project.R` | changing the user level stashes the project before the reload | P12 |
| 59 | M | `tests/testthat/test-wp5-readiness.R` | translated workbook headers; the answers sheets keep their import codes | P4 |
| 60 | A | `tests/testthat/test-wp5-workshop-integration.R` | real register and real workshop page on one project: apply and undo survive later register edits | P15 |
| 61 | A | `tests/testthat/test-wp5-workshop-module.R` | workshop module: consent gate, set-up lock, apply and undo through a fake register | P15 |
| 62 | A | `tests/testthat/test-wp5-workshop.R` | workshop helpers: storage, summaries, write-back mapping, import and export, version stamp | P15 |
| 63 | M | `translations/common/buttons.json` | `common.buttons.download_png` ("Download PNG"), used by the Decision Lens plot (P3) and by loop, leverage and simplify (not relevant) | P3 |
| 64 | M | `translations/common/messages.json` | new `context_user_level_change_save` (P12), `html_report_link_temporary` (P14 / P6c) and `template_links_restored` (P13); `progress_restored_after_language_change` now says "after the page reload" (P12) | P12, P13, P14 / P6c |
| 65 | M | `translations/modules/analysis_loops.json` | 3 new keys for the loop plots (`length_axis`, `dominance_axis`, `download_png`) | not relevant |
| 66 | M | `translations/modules/isa_data_entry.json` | AI-assistant strings only (all five keys are `modules.isa.ai_assistant.*`): "Save to project", "connections saved to the project", new `swap_refused`, two "navigate to ISA Data Entry" keys removed; no ISA-entry string changed, nothing for P1b | P13 |
| 67 | M | `translations/modules/response_measures.json` | register titles reworded (1.32.2): `modules.response.measures.response_measures_register` in lt, no, el and `modules.response.measures.response_register` in de, lt, no, el; both keys are in the subset SESPy ships | P1b |
| 68 | M | `translations/modules/scenario_builder.json` | `modules.scenario.builder.create`: "Create CLD networks and run analysis tools" → "Create" | P8 |
| 69 | M | `translations/modules/wp5_readiness.json` | 15 new `modules.wp5_readiness.xl.*` workbook header keys, 9 languages (1.32.2, LT label word 1.32.3) | P4 |
| 70 | A | `translations/modules/wp5_workshop.json` | 127 keys, 9 languages: page strings and the 11 tenet questions (`modules.wp5_workshop.question.<tenet>`); outside `data/`, so always vendored | P15 |
| 71 | M | `translations/ui/sidebar.json` | `ui.sidebar.workshop_elicitation` | P15 |

Load DA actor list: P4 (user decision 2026-10-21).

## R changes v1.29.0 → v1.31.0 (triaged 2026-10-18)

`git -C <R app dir> diff --name-status e33faea v1.31.0`: 42 paths, all
under `MarineSABRES_SES_Shiny/` (prefix omitted). None of them is a pinned
file. R 1.30.0 = WP5 governance profiles (WS-9a), R 1.31.0 = WP5
governance-readiness check (WS-9b).

| # | Status | Path | Change | Owner |
|---|---|---|---|---|
| 1 | M | `.gitattributes` | `text eol=lf` for the two new WP5 data files | not relevant |
| 2 | M | `CHANGELOG.md` | 1.30.0 and 1.31.0 entries (source of this triage) | not relevant |
| 3 | M | `DESCRIPTION` | version 1.31.0 | not relevant |
| 4 | M | `VERSION` | version 1.31.0 | not relevant |
| 5 | M | `VERSION_INFO.json` | version metadata | not relevant |
| 6 | M | `app.R` | registers the readiness page and the governance-context sub-module | P4 |
| 7 | M | `constants.R` | `Policy_Target` in `ISA_INDICATOR_COLUMNS`; stakeholder columns `NERoles`, `SourceId` (P1b); `WP5_GOV_*`, `WP5_POLICY_TARGETS`, readiness constants and min-app versions (P4) | P1b, P4 |
| 8 | M | `data/country_governance_db.json` | 97 → 99 countries (Greenland, Faroe Islands), 8 → 15 regional conventions/bodies | K1 |
| 9 | A | `data/wp5_governance_profiles.json` | D5.4 governance profiles (curated data) | P4 (§3 allow-list) |
| 10 | A | `data/wp5_readiness_items.json` | D5.4 readiness item bank | P4 (§3 allow-list) |
| 11 | A | `docs/superpowers/plans/2026-10-17-wp5-ws9a-governance-profiles.md` | R plan (reference reading) | not relevant |
| 12 | A | `docs/superpowers/plans/2026-10-17-wp5-ws9b-readiness-check.md` | R plan (reference reading) | not relevant |
| 13 | A | `docs/superpowers/specs/2026-10-17-wp5-ws9a-governance-profiles-design.md` | R spec (reference for P1b/P4) | not relevant |
| 14 | A | `docs/superpowers/specs/2026-10-17-wp5-ws9b-readiness-check-design.md` | R spec (reference for P4) | not relevant |
| 15 | M | `functions/data_structure.R` | stakeholder register gains `NERoles`/`SourceId`; `next_element_id`/`safe_counter` (duplicate-row fix `33ddd96`) (P1b); empty `pims$readiness` block and its load normalisation (P4) | P1b, P4 |
| 16 | M | `functions/indicator_snapshot.R` | `Policy_Target` input id; `project_has_policy_target()` | P1b |
| 17 | M | `functions/isa_form_builders.R` | `Policy_Target` field in the indicator row; free-text select | P1b |
| 18 | A | `functions/stakeholder_schema.R` | stakeholder schema and D5.4 roles (Newton & Elliott typology) | P1b |
| 19 | M | `functions/ui_sidebar.R` | "Governance readiness (D5.4)" menu item | P4 |
| 20 | A | `functions/wp5_governance.R` | D5.4 governance-profile helpers | P4 |
| 21 | A | `functions/wp5_readiness.R` | readiness scoring, storage, import/export | P4 |
| 22 | M | `global.R` | sources the three new function files | P1b, P4 |
| 23 | M | `modules/isa_data_entry_module.R` | stamps min app version when an element has a `Policy_Target` | P1b |
| 24 | M | `modules/pims_stakeholder_module.R` | D5.4 roles column, "Load DA actor list"; duplicate-row fix `33ddd96` | P1b |
| 25 | M | `modules/response_module.R` | "Governance context (D5.4)" tab, register add API; duplicate-row fix `33ddd96` | P4 |
| 26 | A | `modules/wp5_governance_context_module.R` | governance-context tab with "Add to register" | P4 |
| 27 | A | `modules/wp5_readiness_module.R` | WS-9b readiness page in PIMS | P4 |
| 28 | A | `scripts/tests/test_wp5_governance_profiles.py` | R's data-file tests | P4 |
| 29 | A | `scripts/tests/test_wp5_readiness_items.py` | R's data-file tests | P4 |
| 30 | M | `tests/testthat/test-indicator-snapshot.R` | `Policy_Target` tests | P1b |
| 31 | M | `tests/testthat/test-pims-stakeholder-module.R` | roles, actor list, duplicate-row tests | P1b |
| 32 | M | `tests/testthat/test-response-module.R` | register add / duplicate-row tests | P4 |
| 33 | A | `tests/testthat/test-wp5-governance-context-module.R` | governance tab tests | P4 |
| 34 | A | `tests/testthat/test-wp5-governance-profiles.R` | profile data tests | P4 |
| 35 | A | `tests/testthat/test-wp5-governance.R` | governance helper tests | P4 |
| 36 | A | `tests/testthat/test-wp5-readiness-items.R` | item bank tests | P4 |
| 37 | A | `tests/testthat/test-wp5-readiness-module.R` | readiness page tests | P4 |
| 38 | A | `tests/testthat/test-wp5-readiness.R` | readiness scoring tests | P4 |
| 39 | M | `translations/modules/indicator_registry.json` | `Policy_Target` strings | P1b |
| 40 | A | `translations/modules/wp5_governance.json` | governance strings (9 languages) | P4 |
| 41 | A | `translations/modules/wp5_readiness.json` | readiness strings (9 languages) | P4 |
| 42 | M | `translations/ui/sidebar.json` | `ui.sidebar.governance_readiness` | P4 |

**Check item (SESPy stakeholders page):** R commit `33ddd96` ("adding a
second stakeholder or measure no longer creates duplicate rows") fixed
`generate_element_id(prefix, n)` returning every id 1..n at the stakeholder,
engagement, communication and response-measure add sites. Check that
SESPy's stakeholders page (`sespy/modules/pims_stakeholders.py`) adds exactly
one row per click and allocates ids safely for loaded projects. Owners: P1b
(stakeholder schema), P4 (response register).

**Outcome (P1b, v1.15.0):** the stakeholders page adds one row per click (`tests/test_stakeholders_module.py::test_add_adds_exactly_one_row`) and allocates ids from R's persisted counter (`Project.stakeholder_counter`); response-measure ids use `safe_counter` (`add_measure`).
