# K1 — General knowledge-base parity — design

**Status:** Draft, 2026-11-09. Branch `docs/k1-design` (from `main` 999ed6e).
**Umbrella:** `docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md`
(branch `docs/r-parity-roadmap`), §2 "K1" and §3 "Rules that apply to every
sub-project". Every §3 rule binds this sub-project. This document restates the
rules only where K1 has to make them concrete.
**Release:** SESPy **v1.16.0**, project schema **9**.
**R pin:** **v1.34.2 @ `edb42fd`**. This is the version running on laguna
(checked 2026-11-09: `/srv/shiny-server/marinesabres/VERSION_INFO.json`).
`ses_knowledge_db.json`, `country_governance_db.json` and
`ses_connection_knowledge_base.R` did not change between v1.33.0 and v1.34.2.

---

## 1. Intent

When a SESPy user runs the AI ISA wizard, it should know what R's wizard
knows about their sea, habitat and countries:

- the same suggested DAPSI(W)R(M) elements, in the same order and with the
  same source badges;
- the same country lists;
- the same connection polarity, strength and relevance scoring.

A report generated from the result should carry the same "Regional Context"
section R writes. This is one-way parity, R → SESPy. R stays the source of
truth for the data and for the behaviour, including its quirks.

K1 is also the first sub-project that reads R data at runtime. So it builds
the shared reference-data layer that P4, P5, P6 and P8 reuse:

- the vendored copies;
- the optional live override;
- per-session snapshots;
- provenance in saved projects;
- the live drift check (`check_live.py`).

### 1.1 Decisions taken (user, 2026-11-09)
These answer three findings from the code reading. The R files cited are at
v1.34.2.

1. **Extension-pair suggestions are dropped from K1.** R's live wizard never
   suggests R→R, P→P or MPF→MPF connections:
   - `step_navigation.R:92` calls `generate_connections(rv$elements)` with no
     sea or habitat. This is the only call site.
   - So the KB-seeding block (`connection_generator.R:812-919`) never runs.
   - The lines the roadmap cites (`connection_generator.R:620-639`) are the
     `matrix_map` of `convert_matrices_to_connections`, which parses *saved*
     matrices.

   K1 corrects the roadmap's K1 bullet and its "Done when", the P1a spec
   (`2026-10-17-p1a-link-rules-template-mapper-design.md:85-88`) and
   `CHANGELOG.md:206-207` (§9).
2. **SESPy reproduces R's sea + habitat lookup exactly, quirks included, and
   the quirks are reported upstream.** The known effects (pinned by a test, §7):
   - every Indian Ocean habitat resolves to `indian_ocean_coral_reef`;
   - Pacific "Coral reef" resolves to `pacific_island_atoll`;
   - `tropical_mangrove` and the three `macaronesia_*` contexts can never be
     reached;
   - `irish_sea`, `east_atlantic` and `other` fall back to `generic_fallback`.

   An issue for the R repository is drafted (§9). SESPy follows R's fix at a
   later re-pin.
3. **The wizard's countries come from R's `country_governance_db.json`**
   (vendored by K1). `regional_seas.json` keeps sea names, ecosystem types and
   common issues; its `countries`, `country_codes` and `eu_member_codes` go
   away (§4.3). Visible effects:
   - Caribbean grows from 13 to 27 countries;
   - Pacific loses CN, JP, PH, ID and CL;
   - North Sea loses FR;
   - the EU set gains MQ, GP and MF where R lists them.

### 1.2 Facts this design rests on (verified 2026-11-09 at v1.34.2)

**`data/ses_knowledge_db.json`**
- Top-level keys: `version` "1.0", `description`, `last_updated`, `contexts`,
  `generic_fallback`, `cross_ecosystem_links`.
- `contexts` holds **33** entries keyed `<sea>_<habitat>`. Each has
  `regional_sea`, `habitat` and `description`, plus 7 category lists
  (`drivers`, `activities`, `pressures`, `states`, `impacts`, `welfare`,
  `responses`) of `{name, relevance}` and a `connections` list.
- Exceptions: one element carries a `description`, one a `flag`, and one has
  no `relevance` (R defaults it to 0.5).
- Totals: 1,260 elements and 1,185 connections. A connection has `from`,
  `from_type`, `to`, `to_type`, `polarity`, `strength`, `confidence` (2–5),
  `rationale`, `references[]`, `temporal_lag` and `reversibility`.
- `strength` includes the non-standard value "moderate" 40 times.
- `generic_fallback` has a description and the 7 lists but no connections.
- There are **20** `cross_ecosystem_links`, and **no R code reads them**.

**`data/country_governance_db.json`**
- Top-level keys: `version` "1.0", `last_updated`, `countries_by_sea`
  (11 seas), `countries` (**105** records), `governance_elements` (6 groups),
  `socioeconomic_elements` (3 income levels), `regional_conventions`
  (**15** bodies).
- A country record has `code`, `name_en`, `eu_member`, `income_level`,
  `governance_group` and `regional_conventions[]`.
- At v1.31.0 there were 99 countries. `version` was not bumped when 6 were
  added.

**`data/ses_connection_knowledge_base.R`**
- `SES_CONNECTION_DB` (l.47): 137 pattern rules with `from_type`, `to_type`,
  `from_pattern`, `to_pattern`, `probability`, `polarity`, `strength` and
  `source`.
- `SES_SYNONYM_DB` (l.1025): 17 synonym groups.
- Functions: `lookup_knowledge_base` (l.1094), `.synonym_match` (1161),
  `.keyword_idf_weight` (1198), `calculate_enhanced_relevance` (1237) and
  `analyze_phrase_polarity` (1363).
- `global.R:698` sources the file, so in R these functions **always** exist.
  `connection_generator.R` calls them first (:66, :203, :268, :476).

**SESPy's current state**
- `sespy/connection_scorer.py` ported only R's *inline fallback* branches,
  which R runs only when those functions are missing. So SESPy's connection
  suggestions already differ from R's.
- The wizard (`sespy/wizard.py:36-49`) asks for sea (step 0), ecosystem (1),
  countries as *names* (2) and issues (3).
- Steps 4–10 are free-text inputs with **no element suggestions**
  (`sespy/modules/ai_isa_wizard.py:131-194`).
- Only sea and ecosystem are written to `ProjectMetadata`. R saves the same
  two fields; neither app stores country in the project.
- `PROJECT_SCHEMA_VERSION = 8`, `SCHEMA_MIN_READER = {7: "1.13.0", 8: "1.15.0"}`
  (`sespy/data_structure.py:22,27`).
- `sespy/data/` does not exist.
- `deploy/deploy.sh` has no pre-flight step and no `server_settings.env`
  handling. It deletes `$APP_DIR/sespy` on every deploy (:80).
- `app.py` reads no environment variables.

---

## 2. Goals, non-goals, anti-goals

### Goals
- **G1 Reference-data layer** (`sespy/r_kb.py`), as roadmap §3 specifies:
  - allow-listed vendored copies in `sespy/data/r_kb/`;
  - an optional `SESPY_R_DATA_DIR` override, reached through a
    server-preserved `server_settings.env`;
  - validation, atomic snapshots, and a snapshot pinned per session;
  - a fallback to the last good copy, else the vendored one;
  - strictly read-only access.
- **G2 Element suggestions** in wizard steps 4–10, equal to R's
  `get_context_suggestions(..., return_sources = TRUE)`: same items, same
  order, same source labels, first 12 shown. Shown as toggle chips with the
  KB, GOV and SE badges.
- **G3 Country lists** in step 2 from the vendored governance database, with
  an EU badge as in R (`ai_isa_assistant_module.R:1371-1384`). Selections are
  held as ISO codes.
- **G4 Connection-scorer parity:** port `lookup_knowledge_base`,
  `calculate_enhanced_relevance` and `analyze_phrase_polarity`, and make
  `connection_scorer.py` call them first, as R does. `SES_CONNECTION_DB` and
  `SES_SYNONYM_DB` ship as a vendored JSON export (vendored-only; the override
  never applies).
- **G5 Regional Context report section** in HTML, PDF and Word, equal in
  content to R's `format_kb_section_for_report`. It is gated, like R, on the
  project having both a sea and an ecosystem. It includes R's
  recommendations additions (`report_generation.R:476-509`).
- **G6 Provenance:** `metadata.reference_data` is written on save. On load,
  SESPy warns when it differs from the session's snapshot. This is a
  **schema bump to 9**.
- **G7 Live drift check:** `tests/parity/check_live.py`, read-only over SSH,
  runs as a `deploy.sh` pre-flight step and can be run by hand.
- **G8 Re-pin** to v1.34.2. Triage R releases v1.33.0 → v1.34.2 into
  `R_SYNC.md` (only `modules/ai_isa/ui_renderers.R` changed among K1's files:
  a step title is now translated).

### Non-goals
- **Extension-pair suggestions** (decision 1).
- **Fixing R's habitat lookup** (decision 2).
- **`cross_ecosystem_links` as a feature.** They are vendored as data because
  they are part of the file, but nothing reads them. R does nothing with them
  either.
- **`ses_knowledge_db_offshore_wind.json`**: R reads it only from `scripts/`,
  so it is not vendored.
- **`ses_knowledge_db_wp5_mechanisms.json` and the other WP5 files**: they
  belong to P4 and P8. K1's loader must accept them later without changes.
- **Storing the country in the project.** Neither app does this. The report
  uses all countries of the sea, as R does (`get_governance_context(regional_sea)`
  is called without countries).
- **R's hardcoded `.get_governance_elements_hardcoded` fallback.** It runs
  only if the governance database fails to load. SESPy always has the
  vendored copy, so this branch never runs.
- **Translation of KB content.** R shows element names, descriptions and
  rationale in English; so does SESPy.

### Anti-goals (a failure even if it "works")
- Suggestions that differ from R's for the same inputs.
- A live R data change reaching a session mid-run. A session sees one
  snapshot from start to end.
- Any write into R's data directory.
- A missing or broken override taking the app down or blocking a deploy
  silently. On failure the app logs one warning and falls back. The
  *pre-flight* drift check fails loudly, by design.
- Re-typed R data. Everything comes from R files by script, and everything is
  hash-pinned.

---

## 3. Constraints carried from the roadmap (as given, not choices)
- **Allow-list, never a glob.** K1's runtime allow-list:
  - `ses_knowledge_db.json` (version key `version`);
  - `country_governance_db.json` (version key `version`);
  - the vendored-only export `ses_connection_db.json`, made from
    `SES_CONNECTION_DB` and `SES_SYNONYM_DB` (§4.5).

  Each allow-list entry names its required top-level keys, its per-file
  minimum entry counts, and its version key.
- **Hashing** uses `sespy/r_sync.py::sha256_norm` and `sha256_text_norm` only.
- **Pins:** `tests/parity/r_sync.json` is the machine-readable pin and
  `docs/parity/R_SYNC.md` its human mirror, updated in the same commit. A
  test checks the two agree.
- **Schema rules:**
  - every new serialised field bumps `PROJECT_SCHEMA_VERSION`;
  - add `SCHEMA_MIN_READER[9] = "1.16.0"`;
  - the first commit bumps `__version__`, `pyproject.toml` and the MANUAL
    line together;
  - if another branch claims 1.16.0 or schema 9 first, the branch that
    merges second renumbers.
- **MosaicSES:** K1 bumps the schema, so MosaicSES's unit tests and full e2e
  run against the K1 branch before merge, and the live MosaicSES is checked
  after deploy.
  - The `newer_build` guard (node M) is already live.
  - MosaicSES also gets its own `APP_DIR/server_settings.env`, preserved by
    its deploy script.
- **Full e2e gate** with no heavy jobs running concurrently. CI and tests use
  vendored data only.
- **i18n:** new strings adopt R's `modules.*` keys in a separate
  `sespy/translations/*.json` file, copied by script from R's translation
  files. They cover `modules.isa.ai_assistant.*` (tooltips, "Tailored for",
  "Other (enter your own)") and `modules.kb_report.*` (report headings).
  SESPy-only keys may live in `core.json`.

---

## 4. Design

### 4.1 Reference-data layer — `sespy/r_kb.py`
**Allow-list table** (module constant): `file → {required_keys,
min_counts: {path: n}, version_key, override: bool}`.
- `min_counts` for `ses_knowledge_db.json`: contexts ≥ 33, generic_fallback
  present, cross_ecosystem_links ≥ 0.
- `min_counts` for `country_governance_db.json`: countries ≥ 105,
  regional_conventions ≥ 15, countries_by_sea ≥ 11.

  These are the v1.34.2 counts. They are *minimums*, so R may grow.
- The connection-DB export has `override: false`.

**Vendored copies** live in `sespy/data/r_kb/`. They ship in the wheel
through `[tool.setuptools.package-data]`; a packaging test proves it.
`deploy.sh` stops deleting them: they are inside `sespy/`, which deploy
replaces wholesale, and that is fine because they are code-shipped data.

**Override:**
- `SESPY_R_DATA_DIR` comes from the environment, else from
  `APP_DIR/server_settings.env` (simple `KEY=value` lines, read once at
  `app.py` import).
- `deploy.sh` creates `server_settings.env` only if it is absent, containing
  `SESPY_R_DATA_DIR=/srv/shiny-server/marinesabres/data`. Otherwise it
  preserves the file.
- The file lives at `APP_DIR` level, outside `sespy/`, so the wholesale
  `sespy/` replacement never touches it. Same idea as `feedback.db`'s
  stash-and-restore, but simpler.

**Loading and snapshots:**
1. Parse the file.
2. Validate it: required keys; min counts; the version key's major equal to
   the vendored copy's major.
3. Publish an immutable `Snapshot(files: {name: (data, sha256_norm, source,
   version)}, taken_at)` by atomic reference swap.

At **session start**:
- the layer re-stats size and mtime of each override file and reloads on
  change;
- the session stores the current snapshot (a session-scoped object, never a
  module global read at call time);
- every K1 read in that session goes through the pinned snapshot.

On any failure (missing directory, parse error, validation failure) the layer
keeps the last good snapshot, else the vendored one, and logs **one** warning
per failure kind per process.

**API:**
- `current_snapshot()`
- `snapshot.kb()`
- `snapshot.governance()`
- `snapshot.connection_db()`
- `snapshot.provenance()`, which returns the dict for §4.6

The exact module layout is left to the builder.

### 4.2 Element suggestions — `sespy/kb_suggestions.py`
A pure-function port that is exact in order and filtering:
- `build_context_key`, `find_context`, `get_context_elements` and
  `get_context_connections` (`ses_knowledge_db_loader.R:94-307`);
- `deduplicate_suggestions` (`ai_isa_knowledge_base.R:233-283`);
- the hardcoded universal / regional / issue / ecosystem lists, verbatim
  (:325-525);
- `get_habitat_specific_suggestions` (:642 onward), used only when the KB
  returns nothing;
- `get_governance_elements` and `get_socioeconomic_elements`
  (`country_governance_loader.R:184-287`), including `.map_category`'s
  quirks: `activities` maps to no governance category, and `a` maps to
  `drivers`;
- `get_context_suggestions(category, sea, ecosystem, main_issue, countries) ->
  [(name, source)]`.

The details that decide parity:
- **Regex translation.** R's regexes are translated one by one, including
  `sch.ren|sk.rg.rd` and the PCRE negative lookahead in
  `coast(?!al lagoon)`. Python's `re` supports both.
- **The habitat-key cascade order is load-bearing.** Its `if … else if`
  order is kept exactly.
- **Context iteration order.** The prefix and sea-only fallbacks walk
  `names(db$contexts)` in **file order**. Python's `json` keeps insertion
  order, and SESPy must not sort it.
- **Sort stability.** R's `order(decreasing = TRUE)` on doubles uses the
  stable radix method, so ties keep file order. Python's `sorted(...,
  key=-relevance)` is also stable and matches.
- **Missing relevance** defaults to 0.5. Empty names are dropped.
- **`unique()` then `deduplicate_suggestions`**, in R's concatenation order:
  KB, universal, regional, ecosystem, habitat, issue, governance,
  socioeconomic.
- **The source map** uses R's precedence: knowledge_db > governance >
  socioeconomic > regional > issue > ecosystem > habitat > generic.
- **Category names** use R's plural slugs. SESPy's step targets already match
  them (`drivers` … `responses`).

### 4.3 Wizard changes — `sespy/wizard.py`, `sespy/modules/ai_isa_wizard.py`
**Step 2 (countries):**
- Choices come from `governance.countries_by_sea[sea]`, resolved through
  `countries[code]`.
- Labels show `name_en` and an "EU" badge when `eu_member`. Values are ISO
  codes.
- `WizardState.countries` holds codes. SP4's Claude backend consent text and
  payload use names derived from the codes, so the visible behaviour is
  unchanged.
- `regional_seas.json` loses `countries`, `country_codes` and
  `eu_member_codes`. `regional_seas.py` exposes a code→name helper built on
  the governance snapshot, for callers that used the removed fields.
- R's 12th sea, `other`, stays excluded, as in SP2. It has no countries and
  no contexts.

**Steps 4–10:**
- Above the existing free-text rows, show up to 12 suggestion chips from
  `get_context_suggestions`, each with its KB, GOV or SE badge (tooltip
  strings from R's keys).
- A caption "Tailored for <sea> – <ecosystem>" appears when a sea is set
  (R :1574-1582).
- Clicking a chip **toggles** it:
  - if no row in this step has exactly that text, it adds a row with that
    text;
  - otherwise it removes that row.

  This mirrors R's add/remove observer (:2047-2060), including duplicate
  protection.
- Free-text rows that don't match a chip stay as they are. R lists them
  separately as custom elements; SESPy's rows already show them.
- Chip state (selected / not) is derived from the current rows on each
  render. It is never stored separately.
- **Builder's call:** the max-elements-per-category limit
  (`get_level_config(user_level)`). It applies only if SESPy has an
  equivalent user-level setting. Today it does not, so there is no limit.
  Note this in the CHANGELOG as a known difference.

The SP1 step-4–10 idempotency block (remove the old batch on a changed
answer) keeps working, because chips just edit the same rows.

### 4.4 Connection-scorer parity — `sespy/connection_scorer.py`
- **Port the functions.** Port `lookup_knowledge_base`, `.synonym_match`,
  `.keyword_idf_weight`, `calculate_enhanced_relevance` and
  `analyze_phrase_polarity` into `sespy/connection_kb.py`. They read
  `snapshot.connection_db()`.
- **Change the call order.** In `connection_scorer.py`, `detect_polarity`,
  `calculate_relevance`, the phrase analysis and the strength/lag lookup
  call these first, exactly as R's `connection_generator.R` does (:66, :203,
  :268, :476). The existing ported fallbacks stay as the "not available"
  branch, which in practice no longer runs.
- **Keep current outputs.** `suggest_connections`' signature and its output
  type stay as they are. MosaicSES and the SP4 merge path depend on them.
  - Golden tests for the *current* scorer output will change.
  - Each changed golden is re-derived from R (§7), never hand-edited to pass.
- **Unchanged structure.** The 10 scored type pairs stay as they are
  (`generate_connections` only scores those). This is decision 1 restated.

### 4.5 R → JSON export of the connection DB
`scripts/export_r_connection_db.R` (a new R script, committed in SESPy and
run by hand with R) sources R's file at the pinned tag and writes
`sespy/data/r_kb/ses_connection_db.json` as
`{"r_tag", "connection_db": [...], "synonym_db": {...}}`.
- Regex patterns are exported verbatim.
- **Builder check:** confirm that every pattern means the same in R's TRE or
  PCRE engine (whichever `grepl` call R uses) and in Python's `re`. List any
  pattern that doesn't, and give it a translated equivalent with a test.

`r_sync.json` pins two hashes for this export:
- the `.R` source, via `sha256_text_norm`;
- the JSON, via `sha256_norm`.

A drift test re-runs nothing in CI. It only checks the pins agree.

### 4.6 Provenance — schema 9
`ProjectMetadata.reference_data: dict` (default `{}`) maps each file to
`{source: "vendored"|"shared", sha256_norm, version, vendored_r_tag}`.
- It has explicit `to_dict`/`from_dict` handling, and older readers drop it
  through the existing unknown-key filter.
- **When it is written:**
  - on every save and autosave, from the session snapshot;
  - only when the project *used* K1 data, meaning the wizard ran with a sea
    set or a Regional Context section was rendered. Otherwise it stays `{}`.
  - **Builder's call** on the exact trigger. The rule to keep: a project
    that never touched the KB carries no provenance, so unrelated saves
    don't churn.
- **On load,** SESPy compares the recorded entries with the session snapshot:
  - all equal: silent;
  - the recorded hash matches the vendored or the live copy, but not the
    snapshot in use: a toast says the reference data differs from when the
    project was saved;
  - the hash matches neither: a toast says "reference data unavailable;
    results may differ".

  New i18n keys go in `core.json`, since R has no equivalent.
- `SCHEMA_MIN_READER[9] = "1.16.0"`.

### 4.7 Regional Context section — `sespy/report.py`, `sespy/kb_report.py`
- **Port the R helpers:**
  - `get_kb_context_for_report` (relevance ≥ 0.8; the context description);
  - `match_user_connections_to_kb` (the first matching KB connection wins;
    names of 2 characters or fewer are skipped; matching is a
    case-insensitive substring test in either direction);
  - `get_governance_context(regional_sea)`, called without countries as in R.
    It prints raw convention keys and governance-group keys, as R does.
  - `format_kb_section_for_report`.
- **Placement:** the section goes after the report header and project
  overview, and before the analysis sections, mirroring R's
  `header + intro + regional + content`.
- **Format:**
  - HTML and PDF render it through the existing template.
  - Word renders it through `render_docx` with the same headings, lists and
    the 5-column evidence table.
- **Toggle:** an "Include regional context" checkbox on the Export Report
  page. It defaults to on when the project has a regional sea, as in R
  (`options$include_regional_context %||% !is.null(regional_sea)`).
- **Recommendations:** the additions (`report_generation.R:476-509`: top 3
  pressures and responses plus frameworks) go into the matching place in
  SESPy's report. **Builder check:** read :476-509 and map each addition to a
  SESPy report section; flag anything that has no home.

### 4.8 `check_live.py` and `deploy.sh`
`tests/parity/check_live.py` is excluded from pytest collection (the name
has no `test_` prefix, and the location is confirmed in `pyproject`).
1. It reads `DEPLOY_SERVER` from `deploy/config.env`.
2. Over one read-only SSH session it fetches the live R files on the
   allow-list.
3. It compares `sha256_norm` against `r_sync.json` and also reports the live
   `VERSION_INFO.json` version.
4. It exits non-zero on any mismatch and names each file.

`deploy.sh` runs it first. A mismatch aborts the deploy unless R_SYNC.md
records an explicit acceptance (`accepted_warnings` in `r_sync.json`, which
already exists).

---

## 5. Data flow (one session)
1. **Session start:** `r_kb` re-stats the override files, maybe reloads,
   and the session pins the snapshot.
2. **Wizard steps 0–3:** the user picks sea, ecosystem, countries (codes) and
   issues.
3. **Steps 4–10:** `get_context_suggestions(...)` runs against the pinned
   snapshot and shows chips; chip clicks edit the rows.
4. **Step 11:** `suggest_connections` runs, with the KB-first scorer.
5. **Save:** `metadata.reference_data` comes from the pinned snapshot.
6. **Export Report:** the Regional Context section comes from the pinned
   snapshot.
7. **Load:** provenance is compared with the pinned snapshot, and a toast
   appears if they differ.

---

## 6. Error handling
- **Override problems** (missing, unparsable, too small, major-version
  mismatch): one warning in the log, then fallback (§4.1). The UI never shows
  an error for this.
- **Unknown sea or ecosystem:** R's own behaviour, i.e. generic fallback or
  empty lists. Never an exception.
- **Report section errors:** the section is omitted and a warning is logged,
  like R's `tryCatch` (:176-179). The rest of the report renders.
- **A malformed `reference_data` in a loaded project:** ignored with a
  warning. It never blocks a load.

---

## 7. Testing — how "Done" is proven
**R fixtures.** They are captured once at v1.34.2 by an R script committed in
SESPy and stored under `tests/parity/r_fixtures/k1/`. Unit tests compare
against them; they never re-run R.
- **Suggestion parity.** Run `get_context_suggestions(..., return_sources =
  TRUE)` over a grid: all 11 seas × each sea's ecosystem types × 7
  categories × issue ∈ {none, "Overfishing…", "Eutrophication…"} × countries
  ∈ {none, 2 representative codes per sea}.
  - Store the full ordered list and the source map.
  - SESPy must match exactly, beyond the first 12.
  - This supersedes the roadmap's narrower "3 contexts" criterion.
- **Lookup quirks.** A table test pins `find_context` for every sea ×
  ecosystem choice, using R's resolved key and match kind. The decision-2
  cases appear there by name, so an upstream fix shows up as a fixture diff
  at the next re-pin.
- **Countries.** `get_countries_for_sea` for all 11 seas, plus governance and
  socioeconomic elements for a code set covering all 6 governance groups,
  all 3 income levels and all 15 conventions.
- **Connection scorer.** Capture R's `generate_connections` output for the
  P2 template projects and 3 wizard-built fixtures; SESPy must match
  `(from, to, polarity, strength, confidence)` exactly. Capture
  `lookup_knowledge_base` and `analyze_phrase_polarity` for a phrase table.
- **Report.** `format_kb_section_for_report` markdown for 3 projects
  (Baltic lagoon, Mediterranean seagrass, Irish Sea → empty site context),
  compared after whitespace normalisation with SESPy's section rendered to
  markdown, or to an equivalent structure if SESPy has no markdown path
  (builder's choice).

**Layer tests:**
- override valid, missing, corrupt, too small, and wrong major;
- the snapshot is pinned per session: two sessions, swap the file between
  their starts, and each keeps its own;
- no writes;
- one warning per kind.

**Schema tests:**
- the schema 9 round-trip;
- an older reader drops the field (MosaicSES `newer_build` path);
- the three provenance toasts.

**Packaging:** the wheel contains `sespy/data/r_kb/*` from the allow-list.

**e2e** (new script `tests/test_kb_wizard_e2e.py`, scoped namespaced
selectors):
- pick Baltic → Coastal lagoon → 2 countries;
- step 4 shows KB-badged chips;
- toggle a chip on and off;
- finish;
- export the report with Regional Context present.

Also extend the existing `test_wizard_e2e.py` for the country-code change.

**Gates:**
- full unit suite;
- full e2e (`tests/run_e2e.py`);
- MosaicSES unit and full e2e against the K1 branch, with PYTHONPATH pointed
  at the branch worktree (the editable-install trap);
- `check_live.py` passes against laguna.

**Done when** all of the above are green, `R_SYNC.md` is re-pinned to
v1.34.2 with the triage, and the deploy pre-flight runs `check_live.py`.

---

## 8. Size and split
This is the largest sub-project so far after P1b. Parts G1, G3, G6, G7 and
G8 are the infrastructure; G2 and G5 are the user-visible KB features; G4 is
the connection-scorer parity.

**Proposed split if the plan exceeds about 20 tasks:**
- **K1a:** G1, G2, G3, G5, G6, G7, G8. One schema bump; v1.16.0.
- **K1b:** G4 together with the export. v1.17.0; no schema bump, since it
  adds no serialised field.

K1b depends only on K1a's layer. This is open for the user to accept or
reject at plan time.

---

## 9. Follow-ups this sub-project owns
- **Roadmap corrections** (branch `docs/r-parity-roadmap`):
  - remove the K1 extension-pair bullet and fix its "Done when";
  - the K1 pin becomes v1.34.2;
  - record that `cross_ecosystem_links` are unused in R.
- **P1a spec and CHANGELOG:** correct the extension-pair description
  (`2026-10-17-p1a-…-design.md:85-88`, `CHANGELOG.md:206-207`).
- **Upstream R issue (draft only; the user files it):** "Habitat lookup sends
  Indian Ocean habitats to coral reef; tropical_mangrove and macaronesia_*
  contexts unreachable; irish_sea / east_atlantic have no contexts". Include
  the resolved-key table from §7.
- **Upstream R issue (draft only):** the KB-seeding path in
  `generate_connections` is never called (`step_navigation.R:92` passes no
  context), so it is dead code or a missing argument.
- **Upstream note:** `country_governance_db.json` gained 6 countries without
  a `version` or `last_updated` bump. That defeats version checks; suggest
  bumping.

## 10. Left to the builder
- Module boundaries inside `sespy/` (the names above are suggestions).
- The exact provenance-write trigger, within the rule in §4.6.
- The markdown-vs-structure comparison for the report test.
- Chip styling. Match SESPy's existing wizard look. R's colours are not
  required.
- Whether the export script and the fixture-capture script are one R script
  or two.
