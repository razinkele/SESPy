# P2 — Curated R templates in the SESPy gallery

Status: design approved section by section with the user (2026-10-18); spec
awaiting user review.
Roadmap: `docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md`
(branch `docs/r-parity-roadmap`), section "P2 — Curated templates".
Builds on P1a (SESPy v1.13.0): `sespy/r_template_mapper.py`,
`sespy/r_sync.py`, `tests/parity/`.
Target release: **SESPy v1.14.0**. No schema bump (no new serialised fields).

## 1. Purpose and success

SESPy's template gallery offers 4 SESPy-authored examples. R
(MarineSABRES_SES_Shiny, the source of truth) ships 7 curated templates. P2
puts R's 7 into SESPy's gallery, converted by P1a's mapper, kept in sync with
R by a script and a drift test.

**Done when:**
- the gallery shows two groups, "MarineSABRES templates" (7) and "SESPy
  examples" (4);
- each R template loads, and its elements, links and signs equal the
  conversion of the pinned R JSON (roadmap: "each converted template's link
  count and signs equal the R JSON");
- `scripts/sync_r_templates.py --check` reports no drift against the pin;
- R is re-pinned to v1.31.0 in `tests/parity/r_sync.json` and
  `docs/parity/R_SYNC.md`.

## 2. Decisions (taken with the user, 2026-10-18)

| Topic | Decision |
|---|---|
| Gallery presentation | Grouped, with badges (category, complexity, version, regional sea). No complexity filter (SESPy has no user levels until P12), no icons, no preview. |
| Names | R's `template_name` + suffix `" (MarineSABRES)"`. R's names are not otherwise changed. |
| Delivery | **Approach A**: pre-converted SESPy project JSONs + a generated `catalogue.json`, written by `scripts/sync_r_templates.py`; a unit test guards drift. Not converted at runtime; no gallery data inside project files. |
| R pin | v1.31.0 (commit `4b53b7d`, 2026-10-18). None of the 8 pinned files changed since v1.29.0 (`git diff --quiet e33faea v1.31.0` over them exits 0), so fixture hashes are unchanged. |

## 3. Sync script — `scripts/sync_r_templates.py`

```
micromamba run -n shiny python scripts/sync_r_templates.py --r-root <R app dir> [--rev v1.31.0] [--check]
```

- `--r-root` is the R app directory (`.../SESToolbox/MarineSABRES_SES_Shiny`);
  it is inside a larger git repo, so paths are resolved relative to the repo
  root with `git -C <r-root> rev-parse --show-prefix`.
- Reads every input with `git -C <r-root> show <rev>:<path>` — **never checks
  out, switches or stashes** in the R repo. `--rev` defaults to the tag in
  `tests/parity/r_sync.json`; the resolved commit (`<rev>^{commit}`, short
  form) is what gets recorded.
- Inputs: the 7 `data/{Aquaculture,Caribbean,ClimateChange,Fisheries,OffshoreWind,Pollution,Tourism}_SES_Template.json`
  and `functions/dapsiwrm_connection_rules.R`. `Caribbean_SES_Template_backup.json`
  is never read. The file list is a constant in the script; a template added
  or removed in R is a deliberate script change, not silent.
- Steps:
  1. Write the raw bytes to `tests/parity/r_templates/` and
     `tests/parity/r_rules/` (unchanged layout from P1a). With
     `--from-fixtures` (§8) the inputs *are* these files, so this step and
     step 2 are skipped and `r_tag`/`r_commit` are taken from
     `tests/parity/r_sync.json`.
  2. Recompute `sha256_norm` / `sha256_text_norm` (`sespy/r_sync.py`) and
     rewrite `tests/parity/r_sync.json` (`r_tag`, `r_commit`, `files`) and the
     hash table + pin lines in `docs/parity/R_SYNC.md`.
  3. Convert each template with `convert_r_template(raw, key=<file stem>)`.
     **Fail** (exit 1, nothing written for any template) if a report has
     `off_rule_links` or `type_mismatches`.
  4. Post-process the Project (script only — the mapper stays R-exact):
     - `metadata.name = template_name + " (MarineSABRES)"`;
     - `metadata.regional_sea` = display name from
       `sespy.regional_seas.get_regional_seas()[slug]["name"]` when R's
       `regional_context.regional_sea` slug is known; an unknown slug is
       title-cased with `_` → space; absent (Caribbean) stays `""`;
     - `metadata.ecosystem_type` = R's `regional_context.habitat` with `_` →
       space and the first letter capitalised (`rocky_shore` → "Rocky shore");
       absent stays `""`.
  5. Write `sespy/templates/marinesabres/<stem>.json` via
     `persistent_storage.project_to_bytes` (schema 7, stamped
     `min_sespy_version`). `created_at`/`modified_at` come from R's
     `created_date`, so output does not depend on run time.
  6. Write `sespy/templates/marinesabres/catalogue.json` (§4).
- `--check`: perform every step in memory, write nothing, print each file that
  would change, exit 1 if any would. Exit 0 = in sync.
- Output is deterministic: JSON written with sorted catalogue order (§4),
  `ensure_ascii=False`, 2-space indent, trailing newline, LF line endings.

## 4. Catalogue — `sespy/templates/marinesabres/catalogue.json`

```json
{
  "r_tag": "v1.31.0",
  "r_commit": "4b53b7d",
  "templates": [
    {
      "file": "OffshoreWind_SES_Template.json",
      "r_key": "OffshoreWind_SES_Template",
      "name": "Offshore Wind Energy (MarineSABRES)",
      "description": "...",
      "category": "Energy",
      "complexity": "complex",
      "version": "2.2",
      "regional_sea": "north_sea",
      "regional_sea_label": "North Sea",
      "habitat": "offshore",
      "source": "...",
      "usage_notes": "",
      "element_count": 23,
      "connection_count": 27
    }
  ]
}
```

- `templates` sorted by `name` (case-insensitive).
- `file` is the shipped file name in the same directory (named after R's file
  stem so a sync maps 1:1).
- `category` is a port of R's `.determine_template_category`
  (`functions/template_loader.R:368-385`): more than one entry in
  `regional_context.main_issues` → "Multi-Stressor"; otherwise R's regex
  table in R's order → Extraction / Recreation / Production / Pollution /
  Climate / Energy; otherwise "General". The port is a pure function with a
  unit test against every pinned fixture (Caribbean → Multi-Stressor).
- `complexity` = R `complexity` (default `"simple"`, as R).
- `usage_notes` = R `usage_notes` or `""`.
- Counts are the converted project's element / connection counts (Measures are
  folded into Responses, so counts are SESPy's, not R's raw category sums).

## 5. Mapper hardening (P1a follow-up, lands first)

`sespy/r_template_mapper.py`, because P2 is the first code that reads R files
outside tests:
- connection `from_id` / `to_id` are `str()`-coerced like element ids;
- an element id of `0` is accepted (`id` missing/None/"" still raises);
- a connection that is not a dict, or `connections` that is not a list,
  raises `ValueError` (today: `AttributeError`).
Each gets a unit test; existing mapper tests stay green.

## 6. Gallery

### 6.1 Listing (`sespy/templates/__init__.py`)
- `TemplateInfo` gains optional fields (defaults keep the existing 4 working):
  `group: str = "sespy"`, `category: str = ""`, `complexity: str = ""`,
  `version: str = ""`, `regional_sea_label: str = ""`, `usage_notes: str = ""`.
- New `list_catalogue() -> list[TemplateInfo]` reads `catalogue.json` only
  (no project parsing at list time), `group="marinesabres"`, `file` = absolute
  path of the shipped JSON. Missing or unreadable catalogue → `[]` and a
  WARNING on the module logger (gallery still shows the SESPy examples).
- `list_templates()` keeps globbing **top-level** `*.json` only (the
  `marinesabres/` subdirectory is not picked up by it); behaviour unchanged.
- Load stays `load_template(file)` → `load_project` → `validate_project_payload`
  for both groups.
- Packaging: `pyproject.toml` package-data glob includes
  `templates/marinesabres/*.json`.

### 6.2 Module (`sespy/modules/templates.py`)
- The templates calc returns `list_catalogue() + list_templates()`
  (MarineSABRES first, then SESPy examples in current filename order); the
  index into this combined list is what the pre-wired buttons use.
- Two group headers (`h4`), each followed by its cards. Header ids:
  `templates-group_marinesabres`, `templates-group_sespy`.
- Card (same structure as today): `h5` name; badge row for MarineSABRES cards
  (category, complexity label, `v<version>`, regional sea label when set),
  rendered as `span.badge` inside `div.sespy-template-badges`; counts line
  "N elements · M connections" with " · da_site" only when `da_site` is
  non-empty (this also tidies Minimal Demo); description; usage notes (if
  any) inside a collapsed `<details>` with a translated summary; Load button.
- `MAX_TEMPLATES` stays 16; a unit test asserts
  `len(list_catalogue()) + len(list_templates()) <= MAX_TEMPLATES`.
- Toast unchanged: `t("templates.loaded") + f" ({info.name})"`.

### 6.3 Translations (`sespy/translations/core.json`, all 9 languages)
New keys: `templates.group_marinesabres`, `templates.group_sespy`,
`templates.complexity_simple`, `templates.complexity_complex`,
`templates.usage_notes`, and `templates.category_<slug>` for the 8 categories
(`multi_stressor`, `extraction`, `recreation`, `production`, `pollution`,
`climate`, `energy`, `general`). The catalogue stores R's English category;
the module maps it to the key. Template names, descriptions, source and usage
notes stay English (as today).

## 7. A loaded R template

- Metadata: name with suffix; R description; `origin = "r_template"`,
  `r_template_version`; `regional_sea` / `ecosystem_type` per §3 step 4;
  other metadata fields empty.
- ISA: exactly P1a's conversion — Measures folded into Responses with
  `r_extra["r_kind"] = "measure"`, R element types in `r_extra["r_type"]`,
  connection descriptions kept, 0 off-rule links (so no `sespy.link_rules`
  warning on load).
- Large templates (Caribbean: 78 elements, 140 links) load normally; analyses
  with node limits (Boolean ≤ 12) already report "too large". Only the
  "complex" badge signals size.
- Save / autosave / MosaicSES behave as for any v7 project.

## 8. Testing

TDD throughout.

**Unit:**
- `tests/test_sync_r_templates.py`:
  - drift guard: for each pinned fixture, `convert_r_template` + §3 step 4
    post-processing equals the shipped file's parsed project (elements,
    connections incl. polarity/strength/confidence/description, name,
    description, regional_sea, ecosystem_type, origin, r_template_version) —
    compared parsed, not byte-wise, so a later `min_sespy_version` change does
    not break it;
  - catalogue entries equal what the script would generate (in-process);
  - category port: each fixture's expected category, plus synthetic cases for
    each regex branch and the >1-issue rule;
  - regional-sea label mapping (known slug, unknown slug, absent);
  - `--check` on the committed tree exits 0 (run the script's `main()` in
    process against a pinned-fixture source; the test does not need the R
    repo — the script accepts `--from-fixtures` to read inputs from
    `tests/parity/` instead of `git show`, used by tests and offline runs).
- `tests/test_templates.py` additions: `list_catalogue()` returns 7 entries,
  every field set; names unique across both groups; every MarineSABRES name
  ends with `" (MarineSABRES)"`; every catalogue file loads via
  `load_project`; catalogue counts equal the loaded project's counts; combined
  count ≤ `MAX_TEMPLATES`; missing catalogue → `[]` + warning.
- `tests/test_r_template_mapper.py` additions for §5.
- `tests/parity/test_r_sync.py`: pin literals → v1.31.0 / `4b53b7d`.
- `tests/test_i18n.py`: key presence for §6.3.
- `test_server` test of the templates module: both group headers render; a
  MarineSABRES card shows its badges; loading index 0 sets a project whose
  name ends with " (MarineSABRES)".

**e2e:**
- `tests/test_templates_e2e.py`: select cards by exact name (not index 0 or
  the "Offshore Wind" substring); fix the stale index-0 comment and the
  "every template has ≥ 15 elements" claim.
- New `tests/test_r_templates_e2e.py`: both group headers visible; the
  "Offshore Wind Energy (MarineSABRES)" card shows its badges; Load → toast
  contains the name; CLD shows 23 nodes (no SESPy template has 23 elements, so
  this proves the load). Namespaced ids, no bare `text=` selectors.

**Gates:** CI unit command; `scripts/sync_r_templates.py --check` (against
the R repo at the pin); full e2e gate run solo (reds rerun solo before being
believed); full MosaicSES suite (shared env); in-loop reviews until a round
has no Critical/Important.

## 9. Docs and release

- `docs/MANUAL.md` templates paragraph: 11 templates in two groups, badges,
  the "(MarineSABRES)" suffix; version line 1.14.0.
- `README.md` lines listing templates and template tests.
- Re-shoot `docs/screenshots/templates.png` only.
- `docs/parity/R_SYNC.md`: pin v1.31.0; "Adopting a new R release" now says
  "run `scripts/sync_r_templates.py --r-root … --rev <tag>`, review the diff,
  run the gates".
- `CHANGELOG.md` `[1.14.0]`: P2, R v1.31.0 pin, the 7 templates, mapper
  hardening, gallery groups/badges.
- Version bump to 1.14.0 is the first commit (`__init__`, `pyproject`,
  MANUAL line), as in P1a.
- Release: merge onto `origin/main`, tag v1.14.0, deploy to laguna, live check
  that the gallery shows both groups and an R template loads; recheck live
  MosaicSES. Each step with the user's go-ahead.

## 10. Out of scope

Template icons; complexity filter / user levels (P12); preview, connection
review or customise-before-load (R's flow); translated template names,
descriptions or notes; regional filtering; KB-context-derived templates and
anything else in K1.
