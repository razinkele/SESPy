# P2 — Curated R templates in the SESPy gallery

Status: design approved section by section with the user (2026-10-18); review
rounds 1 (fresh read, cross-spec, dry run), 2 (fresh read, dry run with a
working prototype) and 3 (coherence read, prototype incl. a real sync against
R v1.31.0) applied; spec awaiting user review.
Roadmap: `docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md`
(branch `docs/r-parity-roadmap`), section "P2 — Curated templates".
Builds on P1a (SESPy v1.13.0): `sespy/r_template_mapper.py`,
`sespy/r_sync.py`, `tests/parity/`.
Target release: **SESPy v1.14.0**. No schema bump: every metadata field P2
writes already exists in schema 7.

## 1. Purpose and success

SESPy's template gallery offers 4 SESPy-authored examples. R
(MarineSABRES_SES_Shiny, the source of truth) ships 7 curated templates. P2
puts R's 7 into SESPy's gallery, converted by P1a's mapper, kept in sync with
R by a script and a drift test, and re-pins R.

**Done when:**
- the gallery shows two groups, "MarineSABRES templates" (7) and "SESPy
  examples" (4);
- each R template loads, and its link count and every link's sign equal the
  **raw R JSON** (checked directly, not only via the mapper), and its ISA
  equals the mapper's conversion of the pinned file;
- `scripts/sync_r_templates.py --check` reports no drift against the pin;
- R is re-pinned to v1.31.0 in `tests/parity/r_sync.json` and
  `docs/parity/R_SYNC.md`, and R's changes since v1.29.0 are triaged there
  (§9).

## 2. Decisions

Taken with the user (2026-10-18):

| Topic | Decision |
|---|---|
| Gallery presentation | Grouped, with badges (category, complexity, version, regional sea). No complexity filter (SESPy has no user levels until P12), no icons, no preview. |
| Names | R's `template_name` + `" (MarineSABRES)"`. R's names are otherwise unchanged (so R's Aquaculture template is "Coastal Lagoon (MarineSABRES)"). |
| Delivery | **Approach A**: pre-converted SESPy project JSONs + a generated `catalogue.json`; a unit test guards drift. No runtime conversion; no gallery data inside project files. |
| R pin | v1.31.0, commit `4b53b7d` (2026-10-18). The 8 files pinned by P1a are unchanged since v1.29.0 (`git diff --quiet e33faea v1.31.0` over them exits 0). |

Taken in review round 1 (rulings, recorded so the user can revisit):

| Topic | Ruling | Why |
|---|---|---|
| Off-rule links / type mismatches in a future R release | Reported; the sync **fails unless** `--accept-warnings` is passed. Accepted warnings are persisted in `tests/parity/r_sync.json` (`"accepted_warnings": []` today) and listed in R_SYNC.md's generated block; a `--check` / `--from-fixtures` run treats exactly those as accepted. | P1a's decision is allow-and-warn; a hard fail would block adopting R data, and a prose-only record would leave CI red. Today all 7 have 0 of both. |
| `metadata.regional_sea` in shipped projects | **R's slug** (`north_sea`), as P1a's mapper writes it. The display label lives only in the catalogue and on the card. | SESPy's AI ISA wizard writes slugs into the same field (`ai_isa_wizard.py:85-92,574`); K1 keys contexts by sea slug. |
| `metadata.ecosystem_type` | Left `""`. R's habitat is not mapped. | Nothing in SESPy reads it for templates (the wizard starts from empty answers); K1 owns sea × habitat keys and will decide. YAGNI. |
| Line endings | Comparisons in `--check` and tests normalise CRLF → LF (JSON compared parsed; text via `sha256_text_norm`). Writes use `Path.write_bytes(text.encode("utf-8"))` (LF). No `.gitattributes` change. | The user's checkout has `core.autocrlf=true`; blobs are LF, working files CRLF; `write_text` would write CRLF on Windows. |
| Where the logic lives | `sespy/r_template_catalogue.py` (pure, Shiny-free); `scripts/sync_r_templates.py` is a thin CLI wrapper run as `python -m scripts.sync_r_templates` from the repo root. | Testable by import; avoids the `scripts/` namespace-package and stray `tests` package shadowing; `-m` from the root uses this checkout's `sespy`, not the editable install's. |
| `template_loader.R` | Added as a 9th pinned, hashed file, **and** a content-parity test (`tests/parity/test_r_category_parity.py`) compares R's `.determine_template_category` with the Python port. | A hash alone is rewritten by the sync; the parity test makes drift in R's category rule fail. |
| Empty R `complexity` | `""` (R keeps it, `%||%` only replaces NULL) → `"simple"`, R's stated default. | Keeps "always non-empty" true. |
| i18n namespace | New keys live under `templates.*` in `core.json`, not R's `modules.*` per-module files. | R has no keys for categories/complexity (it shows the English value); SESPy's existing templates keys are `templates.*`. The roadmap's §3 i18n rule gets a note (§9). |
| Card regional label without a slug | Falls back to R's `regional_context.region` text (Caribbean → "Caribbean Sea"), label only. | Keeps the roadmap's "applicable regions" visible on every card without changing project metadata. |

## 3. Sync

### 3.1 CLI — `scripts/sync_r_templates.py`

```
micromamba run -n shiny python -m scripts.sync_r_templates --r-root <R app dir> [--rev <tag>] [--check] [--accept-warnings]
micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures [--check]
```
(run from the repo root)

- Thin wrapper: parses arguments, calls
  `sespy.r_template_catalogue.sync(...)`, prints `result.lines`, exits with
  `result.code`. `scripts/` gets an `__init__.py`.
- API:
  `sync(*, repo_root: Path, r_root: Path | None = None, rev: str | None = None,
  from_fixtures: bool = False, check: bool = False,
  accept_warnings: bool = False) -> SyncResult` where
  `SyncResult(code: int, lines: list[str])` (frozen dataclass). **Every read
  of SESPy data files (fixtures, pin, R_SYNC.md, shipped outputs) and every
  write is under `repo_root`**, so tests point it at a `tmp_path` copy; code
  and constants (the mapper, `regional_seas.json`) come from the imported
  `sespy` package. The CLI passes `repo_root` = the directory containing
  `scripts/` (from `__file__`). `r_root` is required unless `from_fixtures`.
  `--from-fixtures` with `--accept-warnings` → exit 1 (fixture mode never
  writes `r_sync.json`, so the acceptance would be lost). `--rev` must be a
  release tag matching `^v\d+\.\d+\.\d+$`; anything else → exit 1.
  `lines` names each written / differing path, each changed pinned-file hash
  (old → new), and every warning.
- `--r-root` is the R app directory (`.../SESToolbox/MarineSABRES_SES_Shiny`),
  inside a larger git repo; paths are resolved with
  `git -C <r-root> rev-parse --show-prefix`.
- Inputs are read with `git -C <r-root> show <rev>:<prefix><path>` — **never
  checkout, switch or stash** in the R repo. `--rev` defaults to the tag in
  `tests/parity/r_sync.json`; the recorded commit is
  `git rev-parse --short=7 <rev>^{commit}` (fixed width).
- `--from-fixtures` reads the inputs from `tests/parity/` instead (tests and
  offline runs); fixture, pin and hash writing is then skipped and
  `r_tag`/`r_commit` come from `tests/parity/r_sync.json`.

### 3.2 Inputs (constant list in the module)

- `data/{Aquaculture,Caribbean,ClimateChange,Fisheries,OffshoreWind,Pollution,Tourism}_SES_Template.json`
- `functions/dapsiwrm_connection_rules.R` (P1a)
- `functions/template_loader.R` (new: source of the category port)

A template added or removed in R is a deliberate change to this list, never
silent.

### 3.3 `sync()` — all in memory, then write

1. Read all inputs.
2. Convert each template with `convert_r_template(raw, key=<file stem>)`.
   A `ValueError` → exit 1, **nothing written**. Collect each report's
   `off_rule_links` and `type_mismatches` as warning entries
   `{"template": "<stem>", "kind": "off_rule_link", "from": "<id>", "to": "<id>"}`
   or `{"template": "<stem>", "kind": "type_mismatch", "text": "<report string>"}`
   (scoped to the template: ids like `D001` repeat across templates). An entry
   matches an accepted one only if every field is equal. Any unaccepted entry
   and `--accept-warnings` not set → exit 1, nothing written, all listed. With
   `--accept-warnings` they are accepted. When `r_sync.json` is written,
   `accepted_warnings` = exactly the entries that occur in this run (accepted
   ones that no longer occur are dropped), sorted by
   `(template, kind, from, to, text)`.
   A failed `git show` (bad rev, path missing at the rev) → exit 1, nothing
   written, the failing path listed.
3. Post-process each Project (module code; the mapper stays R-exact):
   `metadata.name = <mapper's metadata.name> + " (MarineSABRES)"` (the mapper
   already applies R's name fallbacks). Everything else is the
   mapper's output unchanged (`regional_sea` = R's slug; `ecosystem_type`
   stays `""`).
4. Serialise each project with **`project.to_json() + "\n"`**, written with
   `Path.write_bytes(text.encode("utf-8"))`. Never
   `persistent_storage.project_to_bytes` or `save_project_atomic`: both stamp
   `modified_at` with the run time. `created_at`/`modified_at` stay R's
   `created_date`; `to_json` stamps `min_sespy_version` at the schema floor
   (1.13.0), not the running version.
5. Build `catalogue.json` (§4), serialised `json.dumps(..., indent=2,
   ensure_ascii=False) + "\n"`. If any always-non-empty field (§4) would be
   empty → exit 1, nothing written.
6. Unless `--from-fixtures`: build the fixture copies (raw bytes as read; the
   7 templates stay in `tests/parity/r_templates/`, the rules file stays in
   `tests/parity/r_rules/`, and only `template_loader.R` goes to the new
   `tests/parity/r_source/`), the new `tests/parity/r_sync.json` (9 files,
   plus `accepted_warnings`) and the **generated block** of
   `docs/parity/R_SYNC.md`. The block is everything between
   `<!-- r-sync:begin -->` and `<!-- r-sync:end -->`, exactly:
   ```
   - **R release:** MarineSABRES_SES_Shiny **v1.31.0**, commit `4b53b7d`.

   | File | Hash |
   |---|---|
   | `tests/parity/r_templates/Aquaculture_SES_Template.json` | `<64 hex>` |
   ... (one row per pinned file, sorted by path)

   **Accepted sync warnings:** none.
   ```
   (the last line lists each accepted entry as `- <template>: <kind> <from> -> <to>`
   or `- <template>: <kind> <text>` when there are any). The block between
   the markers is `\n` + the text above + `\n`.
   The markers are added by hand (§9) before the first real sync; missing or
   duplicated markers → exit 1, nothing written. Prose outside the markers is
   never touched.
7. `--check`: compare every output with what is under `repo_root` — JSON
   parsed, text with CRLF → LF — list each differing path, exit 1 if any
   differ, write nothing. Otherwise write all outputs, then exit 0.

Outputs: `sespy/templates/marinesabres/<stem>.json` (7),
`sespy/templates/marinesabres/catalogue.json`, plus (not `--from-fixtures`)
the fixtures, `r_sync.json` and the R_SYNC.md block.

## 4. Catalogue — `sespy/templates/marinesabres/catalogue.json`

```json
{
  "r_tag": "v1.31.0",
  "r_commit": "4b53b7d",
  "templates": [
    {
      "file": "OffshoreWind_SES_Template.json",
      "name": "Offshore Wind Energy (MarineSABRES)",
      "description": "...",
      "category": "Energy",
      "complexity": "complex",
      "version": "2.2",
      "regional_sea_label": "North Sea",
      "source": "...",
      "usage_notes": "",
      "element_count": 23,
      "connection_count": 27
    }
  ]
}
```

- `templates` sorted by `name`, case-insensitive. Index 0 is therefore
  "Caribbean Island - Comprehensive SES Template (MarineSABRES)" (78 elements).
- `file`: shipped file name in the same directory (R file stem, 1:1).
- **Always non-empty:** `file`, `name`, `description`, `category`,
  `complexity`, `version`, and the two counts (> 0). May be `""`:
  `regional_sea_label` (Caribbean has no regional sea), `source`,
  `usage_notes` (only Caribbean has notes).
- `regional_sea_label`: `get_regional_seas()[slug]["name"]` for a known slug;
  an unknown slug title-cased with `_` → space; no slug → R's
  `regional_context.region` if it is a non-empty string (Caribbean →
  "Caribbean Sea"), else `""`.
- `category`: exact port of R's `.determine_template_category`
  (`functions/template_loader.R:359-371` at v1.31.0): `main_issues` NULL →
  "General"; more than one element → "Multi-Stressor"; otherwise R's regex
  table, unanchored, case-insensitive, **first match in R's order** →
  Extraction / Recreation / Production / Pollution / Climate / Energy;
  otherwise "General". A scalar string counts as one issue; an empty list
  falls through to "General". Expected today: Aquaculture Production,
  Caribbean Multi-Stressor, ClimateChange Climate, Fisheries Extraction,
  OffshoreWind Energy, Pollution Pollution, Tourism Recreation.
- `complexity` = R `complexity`; absent, NULL or `""` → `"simple"`.
- `source` = R `metadata.source` or `""`; `usage_notes` = R `usage_notes` or
  `""`.
- Counts = the converted project's element / connection counts (Measures
  folded into Responses).

## 5. Mapper hardening (P1a follow-up)

`sespy/r_template_mapper.py`, the first commit after the version bump:
- `connections` absent or `None` → no connections (R `%||% list()`); any
  other non-list (dict, string, `{}`, `""`, number) → `ValueError`. The type is
  checked before any `or` fallback.
- a connection that is not a dict → `ValueError`.
- connection `from_id`/`to_id` are `str()`-coerced when not `None` (a missing
  endpoint still reports "unknown element id None"); integer ids on both sides
  then match.
- an element id of `0` is accepted (`id` missing / `None` / `""` still
  raises).
Each case gets a unit test that fails today for the stated reason.

## 6. Gallery

### 6.1 Listing (`sespy/templates/__init__.py`)
- `TemplateInfo` gains defaulted fields: `group: str = "sespy"`,
  `category: str = ""`, `complexity: str = ""`, `version: str = ""`,
  `regional_sea_label: str = ""`, `source: str = ""`, `usage_notes: str = ""`.
  Existing callers use keywords, so nothing else changes.
- New `list_catalogue(directory: Path | None = None) -> list[TemplateInfo]`
  reads `<directory or the package's templates/marinesabres>/catalogue.json`
  only (no project parsing at list time); `group="marinesabres"`,
  `da_site=""`, `file` = absolute path. Each entry is validated: the always-non-empty
  fields (§4) are non-empty strings, the counts are ints > 0, the §4 keys present (all
  of `file, name, description, category, complexity, version,
  regional_sea_label, source, usage_notes, element_count, connection_count`),
  `(dir / file).resolve().is_relative_to(dir.resolve())` (both sides
  resolved, so 8.3 short paths and a symlinked `sespy/` work), and
  `is_file()`. A bad entry is
  skipped with a WARNING on the module logger; a missing or unparsable
  catalogue → `[]` + WARNING.
- `list_templates()` keeps globbing top-level `*.json` only (the subdirectory
  is not picked up — verified).
- Load is unchanged for both groups: `load_template(file)` → `load_project` →
  `validate_project_payload`.
- Packaging: `pyproject.toml` package-data adds `templates/marinesabres/*.json`;
  a unit test reads the glob list and asserts it covers that path.

### 6.2 Module (`sespy/modules/templates.py`)
- The calc returns `list_catalogue() + list_templates()`; the combined index
  drives the pre-wired buttons (`MAX_TEMPLATES` stays 16; a unit test asserts
  the combined length ≤ 16).
- Two group headers (`h4`) with ids from `session.ns("group_marinesabres")`
  / `session.ns("group_sespy")` (as `cld_visualization.py:317` does), so they
  render `templates-group_marinesabres`, `templates-group_sespy` (a plain
  `id=` inside `render.ui` is **not** namespaced). A group with no entries
  renders no header. The list contains no `h5` other than card names
  (several e2e scripts find a card's index from the `h5` list).
- Card, same structure as today: `h5` name; for MarineSABRES cards a badge row
  `div.sespy-template-badges` of `span.badge` (category, complexity label,
  `v<version>`, regional sea label when set); counts line (existing rule:
  " · da_site" only when set); description; a collapsed `<details>` "About
  this template" holding `source` and `usage_notes` when either is set; Load
  button.
- Toast unchanged: `t("templates.loaded") + f" ({info.name})"`.

### 6.3 Translations (`sespy/translations/core.json`, all 9 languages)
New SESPy keys (R has none for these — it passes the English category through
`i18n$t()` and shows it untranslated — so this goes beyond R and uses the
`templates.*` namespace): `templates.group_marinesabres`,
`templates.group_sespy`, `templates.about`, `templates.complexity_simple`,
`templates.complexity_complex`, and `templates.category_<slug>` for
`multi_stressor, extraction, recreation, production, pollution, climate,
energy, general`. Slug = `value.lower().replace("-", "_")`. `t()` returns the
key on a miss (`i18n.py:98`), so the module checks `t(k) == k` and then shows
the raw R value (e.g. a future R complexity "moderate"), never the key string;
a unit test pins this. Template names, descriptions, source and notes stay
English.

## 7. A loaded R template

- Metadata: suffixed name; R description; `origin = "r_template"`;
  `r_template_version`; `regional_sea` = R slug; `ecosystem_type` = `""`;
  `created_at`/`modified_at` = R `created_date`; other fields empty.
- ISA: exactly P1a's conversion (Measures folded into Responses with
  `r_extra["r_kind"]="measure"`, R types in `r_extra["r_type"]`, descriptions
  kept); 0 off-rule links today, so no `sespy.link_rules` warning.
- Caribbean (78 elements, 140 links) loads normally; analyses with node limits
  (Boolean ≤ 12) already report "too large". The "complex" badge is the only
  size signal.
- Save, autosave and MosaicSES behave as for any v7 project.

## 8. Testing

TDD throughout.

**Unit:**
- `tests/test_r_template_catalogue.py` (imports `sespy.r_template_catalogue`):
  - drift guard, per pinned fixture: the shipped file's `isa_data` equals the
    conversion's, and the listed metadata fields (name, description,
    regional_sea, ecosystem_type, origin, r_template_version, created_at)
    match, compared **individually — never `Project ==`** (round-tripping
    stamps `min_sespy_version`);
  - raw-R check, per fixture: link count and each link's sign equal the raw R
    JSON's `connections` (independent of the mapper);
  - catalogue equals what `sync(--from-fixtures)` builds (parsed);
  - determinism: building twice gives identical bytes; `modified_at ==
    created_at`; output ends with `"\n"`;
  - `sync(from_fixtures=True, check=True)` on the committed tree returns 0,
    including when the files on disk are CRLF (test writes a CRLF copy into
    `tmp_path` and points the check there);
  - atomicity: a fixture made to raise `ValueError` → exit 1 and no file in
    `tmp_path` changed; an off-rule link without `accept_warnings` → exit 1,
    with it → 0;
  - category port: the 7 expected values (§4) plus synthetic cases for NULL,
    empty list, scalar string, >1 issues, each regex branch, and order
    precedence ("wind farm" → Production);
  - regional-sea label: known slug, unknown slug, no slug with a `region`
    (Caribbean → "Caribbean Sea"), neither → `""`;
  - complexity `""` / absent → "simple";
  - an empty always-non-empty field → exit 1, nothing written;
  - markers missing or duplicated in R_SYNC.md (non-fixture mode) → exit 1,
    nothing written. The fake `r_root` is a real git repo built in
    `tmp_path`: `git init`, the app in a subdirectory (so the prefix is
    non-empty), the fixtures committed and tagged; `git show` on a missing path
    → exit 1;
  - `accepted_warnings`: an accepted off-rule link passes a later
    `check=True`; a warning accepted for template A is not accepted for
    template B; an accepted warning that no longer occurs is dropped;
  - written files are LF on disk (read bytes, no `\r\n`).
- `tests/parity/test_r_category_parity.py`: extract `.determine_template_category`
  from `tests/parity/r_source/template_loader.R` and assert its regex table,
  order and branches (NULL → General, length > 1 → Multi-Stressor, fallback
  General) equal the Python port's constants. The file is read with CRLF → LF
  normalised (`read_text` / `.replace("\r\n", "\n")`), never raw bytes, and
  the test guards that the number of `if (` rules equals 2 + the port's rule
  count.
- The §8 helper that builds the fake git repo passes `-c core.longpaths=true`
  to every `git` call (long Windows temp paths).
- `tests/test_templates.py` additions: `list_catalogue()` returns 7 entries
  with the always-non-empty fields of §4 set; names unique across both groups;
  every MarineSABRES name ends with `" (MarineSABRES)"`; every catalogue file
  loads via `load_project` and its counts equal the catalogue's; combined
  count ≤ `MAX_TEMPLATES`; via `list_catalogue(directory=tmp_path/...)`:
  missing catalogue → `[]` + warning; malformed entry (missing key, empty
  name, count 0 or non-int) and dangling / escaping `file` → skipped +
  warning; an unresolved / 8.3-short `directory` still returns all 7
  (`skipif` not Windows); package-data glob covers
  `templates/marinesabres/*.json`.
- `tests/test_r_template_mapper.py`: the §5 cases.
- `tests/parity/test_r_sync.py`: the pin is no longer a literal — the test
  asserts R_SYNC.md's generated pin line equals `r_sync.json` (`r_tag`,
  `r_commit`), and the file count is 9.
- `tests/test_i18n.py`: §6.3 key presence in all 9 languages.
- `test_server` test of the templates module (pattern of
  `tests/test_isa_entry_link_rules.py`: patch `ui.notification_show`, set
  `load_template_0` to 0 then 1): both group headers render with namespaced
  ids; the first card shows its badges; loading index 0 sets a project named
  exactly "Caribbean Island - Comprehensive SES Template (MarineSABRES)"
  (read `project_data` inside `reactive.isolate()`); a category/complexity
  value with no translation key renders the raw value.

**e2e:**
- `tests/test_templates_e2e.py`: clicks the "Coastal Tourism SES" card's Load
  by locating the card by its exact `h5` text (index 0 is now Caribbean), not
  `load_template_0`; the "Offshore Wind" substring check becomes an exact-name
  check for "Offshore Wind Farm SES"; the stale index-0 comment and the
  "≥ 15 elements" claim are fixed.
- New `tests/test_r_templates_e2e.py`: `#templates-group_marinesabres` and
  `#templates-group_sespy` visible; the "Offshore Wind Energy (MarineSABRES)"
  card shows its badges; Load → toast contains the name; the test polls until
  the CLD shows **exactly 23** nodes (the seeded sample already has 17, so
  polling for `n > 0` would prove nothing; OffshoreWind is the only template
  with 23 elements; the CLD shows every DAPSIWRM type by default). Namespaced
  ids, no bare `text=` selectors.

**Gates:** CI unit command; `python -m scripts.sync_r_templates --r-root … --check`
at the pin; full e2e gate run solo (reds rerun solo before believed); full
MosaicSES suite (shared env); in-loop reviews until a round has no
Critical/Important.

## 9. Docs, R triage and release

- Commit order: (1) version bump to 1.14.0 (`__init__`, `pyproject`, MANUAL
  line); (2) mapper hardening (§5); (3) the R_SYNC.md hand edits that add the
  markers (below); (4) `sespy/r_template_catalogue.py` + script + the tests
  that run against `tmp_path` builds; (5) the first real run,
  `python -m scripts.sync_r_templates --r-root <R> --rev v1.31.0`, committed
  as the re-pin + shipped templates + catalogue + `r_source/template_loader.R`
  together with the tests that need them (drift guard, catalogue equality,
  `test_r_category_parity.py`, `test_r_sync` with 9 files), so nothing ever
  ships stamped v1.29.0 and every commit is green; then the gallery, e2e and
  docs.
- `docs/parity/R_SYNC.md` (hand edits, outside the markers):
  - wrap only the pin line and the hash table of "## Current pin" in
    `<!-- r-sync:begin -->` / `<!-- r-sync:end -->`; move the "Adopted in" and
    "Roadmap baseline" bullets outside the block and reword them ("Adopted in
    SESPy 1.14.0"; baseline moved v1.29.0 → v1.31.0, pinned files unchanged);
  - "Laguna verification (2026-10-17)" states its scope: it covered the 8
    P1a files; `template_loader.R` is pinned from git only (not checked on
    laguna);
  - intro: R files under `tests/parity/` still never ship; the 7 templates
    ship as SESPy projects converted from them; "update both in the same
    commit" becomes "the sync script updates the pin, the hashes and this
    block together";
  - "Adopting a new R release" steps 1–2 rewritten around the sync script;
    the "Roadmap baseline" bullet no longer says "the files below"
    (the table is now inside the generated block);
  - "Adopted in SESPy 1.14.0", laguna verification after deploy;
  - "Adopting a new R release" → run the sync script, review the diff, triage
    R's changes, run the gates;
  - **R changes v1.29.0 → v1.31.0 triage**: one row per path from
    `git diff --name-status e33faea v1.31.0` (42 rows; `--stat` truncates
    paths), each with an owner sub-project or "not relevant", e.g.
    `country_governance_db.json` → K1 (97 → 99 countries, 8 → 15 regional
    conventions), `wp5_governance_profiles.json` / `wp5_readiness_items.json`
    and the WS-9b readiness page → P4, `Policy_Target` indicator field and
    stakeholder roles → P1b, R's new `.gitattributes` → not relevant. Also
    note R commit `33ddd96` (duplicate rows on a second stakeholder / measure)
    as a check item for SESPy's stakeholders page. Complete = every path
    listed.
  - the 9 pinned files are identical at v1.29.0 and v1.31.0, so a laguna R
    still at v1.29.0 does not affect them;
- `docs/MANUAL.md` templates paragraph: 11 templates in two groups, badges,
  the "(MarineSABRES)" suffix, and that "Coastal Lagoon (MarineSABRES)" is R's
  aquaculture template; version line 1.14.0.
- `README.md` lines listing templates and template tests.
- Re-shoot `docs/screenshots/templates.png` only.
- `CHANGELOG.md` `[1.14.0]`: P2, R v1.31.0 pin, the 7 templates, mapper
  hardening, gallery groups and badges.
- **Roadmap edits** (branch `docs/r-parity-roadmap`, same release cycle):
  header pin / SESPy version; P2 section (R source v1.31.0 + `template_loader.R`;
  replace "ship them in `sespy/templates/` beside SESPy's 4" with
  `sespy/templates/marinesabres/` + `catalogue.json`; replace "gallery cards
  read `ConversionReport.template_meta`" with "cards read `catalogue.json`";
  v1.14.0);
  P12 gains R's template complexity filter (`template_ses_module.R:125-141`,
  deferred from P2); P13 gains R's template preview / customise-before-load
  flow; the triage owners above (K1 country count re-check — R v1.30.0 added
  Greenland and the Faroe Islands; P1b `Policy_Target` and stakeholder roles;
  P4 WP5 governance profiles, readiness items and readiness page; §3
  allow-list gains the two WP5 data files); §3 i18n gains a note that
  SESPy-only UI keys with no R counterpart may live in `core.json`.
- Release: merge onto `origin/main`, tag v1.14.0, deploy to laguna, live check
  that the gallery shows both groups and an R template loads (this also proves
  the new JSONs reached the server); recheck live MosaicSES. Each step with
  the user's go-ahead.

## 10. Out of scope

Template icons; complexity filter / user levels (P12); preview, connection
review or customise-before-load (P13); translated template names,
descriptions or notes; regional filtering; KB-context-derived templates and
everything else in K1; implementing any of the triaged R changes.
