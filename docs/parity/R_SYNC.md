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
- **R release:** MarineSABRES_SES_Shiny **v1.29.0**, commit `e33faea`.

| File | Hash |
|---|---|
| `tests/parity/r_rules/dapsiwrm_connection_rules.R` | `ca4294f10974af34adf7dad9fe029318955c1c498356224b656a3e69525422a5` |
| `tests/parity/r_templates/Aquaculture_SES_Template.json` | `d24154498ce843d0f10e2b724340ca63878002e63486132d933ef777d844c946` |
| `tests/parity/r_templates/Caribbean_SES_Template.json` | `7c38efa11232215eea9754c2831e8beaec31eb8d7a90618a16d3834af9bd5961` |
| `tests/parity/r_templates/ClimateChange_SES_Template.json` | `ab8cbaca91842fdc8cf87e46d0b0d20e14d298f38c21379dcaf27c8650f92ae3` |
| `tests/parity/r_templates/Fisheries_SES_Template.json` | `f04c3673afad34f2424e3ebaf3944f9e117dda87efb537960e4c14ef16c04da6` |
| `tests/parity/r_templates/OffshoreWind_SES_Template.json` | `a7657b88a1046d0590e4dcfdea39852cf2a4cdfa7629a2f14564753079c6debf` |
| `tests/parity/r_templates/Pollution_SES_Template.json` | `d3da39cf77605a35c7d3accbdd4b37830753443230f88d22c59e971c60332e56` |
| `tests/parity/r_templates/Tourism_SES_Template.json` | `1c0af86d3737cdb306ccc8eb0107fbe1ac75b41c4fede2dd56dc265c9983662e` |

**Accepted sync warnings:** none.
<!-- r-sync:end -->

- **Adopted in:** SESPy 1.14.0 (P2: curated R templates in the gallery);
  laguna verification of the new pin follows the 1.14.0 deploy. The
  previous pin, v1.29.0 (`e33faea`), was adopted in SESPy 1.13.0 (P1a).
- **Roadmap baseline:** moved from v1.29.0 (`e33faea`) to v1.31.0
  (`4b53b7d`). The pinned files are unchanged between the two tags
  (`git diff --quiet e33faea v1.31.0 -- <the 9 paths>` exits 0).

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
