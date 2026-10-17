# R sync record

SESPy reads a few files from the R MarineSABRES SES Toolbox as **test
fixtures**. They never ship to the server. This page is the human record of
which R release they come from. The machine-readable pin is
[`tests/parity/r_sync.json`](../../tests/parity/r_sync.json), which
`tests/parity/test_r_sync.py` checks; it also checks that this page lists
exactly the same hashes. Update both in the same commit.

## Current pin

- **R release:** MarineSABRES_SES_Shiny **v1.29.0**, commit `e33faea`.
- **Adopted in:** SESPy 1.13.0 (P1a: link rules, schema v7, R template mapper).
- **Roadmap baseline:** moved from v1.28.0 (`e3c3b77`) to v1.29.0. The files
  below are unchanged between the two.

| Fixture | Hash |
|---|---|
| `tests/parity/r_templates/Aquaculture_SES_Template.json` | `d24154498ce843d0f10e2b724340ca63878002e63486132d933ef777d844c946` |
| `tests/parity/r_templates/Caribbean_SES_Template.json` | `7c38efa11232215eea9754c2831e8beaec31eb8d7a90618a16d3834af9bd5961` |
| `tests/parity/r_templates/ClimateChange_SES_Template.json` | `ab8cbaca91842fdc8cf87e46d0b0d20e14d298f38c21379dcaf27c8650f92ae3` |
| `tests/parity/r_templates/Fisheries_SES_Template.json` | `f04c3673afad34f2424e3ebaf3944f9e117dda87efb537960e4c14ef16c04da6` |
| `tests/parity/r_templates/OffshoreWind_SES_Template.json` | `a7657b88a1046d0590e4dcfdea39852cf2a4cdfa7629a2f14564753079c6debf` |
| `tests/parity/r_templates/Pollution_SES_Template.json` | `d3da39cf77605a35c7d3accbdd4b37830753443230f88d22c59e971c60332e56` |
| `tests/parity/r_templates/Tourism_SES_Template.json` | `1c0af86d3737cdb306ccc8eb0107fbe1ac75b41c4fede2dd56dc265c9983662e` |
| `tests/parity/r_rules/dapsiwrm_connection_rules.R` | `ca4294f10974af34adf7dad9fe029318955c1c498356224b656a3e69525422a5` |

The JSON templates are hashed with `sespy.r_sync.sha256_norm` (the parsed
JSON, so key order, CRLF and a BOM do not matter). The `.R` file is hashed
with `sespy.r_sync.sha256_text_norm` (text with CRLF normalised to LF).
`Caribbean_SES_Template_backup.json` is not a fixture.

## Laguna verification (2026-10-17)

The R app deployed on laguna (`/srv/shiny-server/marinesabres`) was
v1.29.0 on 2026-10-17. Its 7 templates and its
`functions/dapsiwrm_connection_rules.R` have the same hashes as the local
checkout, so the pin above matches what users run.

## Adopting a new R release

1. Copy the 7 `data/*_SES_Template.json` files to `tests/parity/r_templates/`
   and `functions/dapsiwrm_connection_rules.R` to `tests/parity/r_rules/`.
2. Regenerate `tests/parity/r_sync.json` and update the table above.
3. Run `tests/parity/` and `tests/test_r_template_mapper.py`; a red
   `test_r_rules_parity.py` means the rule table changed and
   `sespy/constants.py::DAPSIWRM_ADJACENCY_RULES` must follow.

Live drift against laguna (`tests/parity/check_live.py`) is owned by **K1**
in the R-parity roadmap; P1a uses these files only as test fixtures.
