# K1 — General knowledge-base parity — design

**Status:** Draft rev 3, 2026-11-09. Revised after the builder check and
review round 1 (fresh read, cross-spec, dry run). Branch `docs/k1-design`,
from `main` 999ed6e.

**K1 is split** (decision 4). This document specifies K1 (v1.16.0). §8
records the scope and the decisions already taken for **K1b**
(connection-scorer parity), which gets its own spec and plan later.

**Umbrella:** `docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md`
(branch `docs/r-parity-roadmap`), §2 "K1" and §3 "Rules that apply to every
sub-project". Every §3 rule binds this sub-project. Deviations are listed in
§1.1 and §9, together with the umbrella edits they require.

**Release:** SESPy **v1.16.0**, project schema **9**.

**R pin:** **v1.34.2 @ `edb42fd`**, which is what laguna runs (checked
2026-11-09 in `/srv/shiny-server/marinesabres/VERSION_INFO.json`).

**Evidence already gathered:** the round-1 dry run built a Python port of
R's lookup and suggestion code and compared it with R run headless.
- **Lookup:** all **69** SESPy sea × ecosystem choices matched, with 0
  mismatches.
- **Suggestions:** `get_context_suggestions(return_sources = TRUE)` was run
  over **4,830 cells**: 69 choices × 7 categories × 5 issue sets × 2 country
  sets. Items, order and sources all matched, with 0 mismatches, across 284
  relevance ties.
- **Prototypes:** `kbport.py`, `r_capture.R`, `compare.py`, `r_report.R`
  and related scripts are kept in the main checkout under the gitignored
  `.superpowers/k1-prototypes/`. The plan may build on them.

---

## 1. Intent

When a SESPy user runs the AI ISA wizard, it should know what R's wizard
knows about their sea, habitat and countries:
- the same suggested DAPSI(W)R(M) elements, in the same order, with the same
  source badges;
- the same country lists.

A report made from the result carries the same "Regional Context" section R
writes. Later, K1b brings the same connection scoring as R run with ML off.

Parity runs one way, R → SESPy. R stays the source of truth for the data and
the behaviour, quirks included.

K1 is also the first sub-project that reads R data at runtime. So it builds
the shared reference-data layer that P4, P5, P6, P8 and K1b reuse:
- vendored copies;
- an optional live override;
- per-session snapshots;
- provenance in saved projects;
- the live drift check.

### 1.1 Decisions (user, 2026-11-09)
1. **Extension-pair suggestions are dropped.** R's live wizard never
   suggests R→R, P→P or MPF→MPF:
   - `step_navigation.R:92` calls `generate_connections(rv$elements)` with
     no sea or habitat. It is the only call site.
   - So the KB-seeding block (`connection_generator.R:812-919`) never runs.
   - The lines the roadmap cites (`:620-639`) are the `matrix_map` of
     `convert_matrices_to_connections`. They parse saved matrices.

   Corrections owed: §9.
2. **SESPy reproduces R's sea + habitat lookup exactly, quirks included,
   and the quirks are reported upstream.** 28 of the 69 SESPy choices land
   on a context other than the one their name suggests. The full table goes
   into the §7 lookup fixture and the §9 issue draft. Highlights:
   - Every **Pacific** choice resolves to `pacific_island_atoll`. Island and
     Atoll get there by prefix match; the rest fall back to the sea's first
     context.
   - Every **Indian Ocean** choice resolves to `indian_ocean_coral_reef`.
     `indian_ocean_island` can never be reached.
   - `tropical_mangrove` and the three `macaronesia_*` contexts can never be
     reached.
   - Fallbacks to another habitat in the same sea:
     - North Sea Open coast, Rocky shore and Sandy beach → `north_sea_offshore`;
     - Mediterranean Sandy beach and Offshore → `mediterranean_lagoon`;
     - Black Sea Delta, Lagoon, Offshore and Estuary → `black_sea_open_coast`;
     - Caribbean Mangrove, Sandy beach and Open coast → `caribbean_coral_reef`;
     - Arctic Open ocean, Coastal waters and Continental shelf → `arctic_sea_ice`.
   - Atlantic "Coastal upwelling" resolves exactly to `atlantic_open_coast`,
     through the bare `coast(?!al lagoon)` branch.
   - `irish_sea` and `east_atlantic` have no contexts.
     - The wizard shows **KB-badged** items from `generic_fallback`.
     - The report has **no** site context, because
       `get_kb_context_for_report` needs a real context.
3. **The wizard's countries come from R's `country_governance_db.json`.**
   `regional_seas.json` keeps sea names, ecosystem types and common issues.
   Its `countries`, `country_codes` and `eu_member_codes` go away (§4.3).

   Visible changes, checked against `countries_by_sea`:

   | Sea | Loses | Gains |
   |---|---|---|
   | Pacific | CN, JP, PH, ID, CL, US | FM, KI, MH, NR, PW, SB, TO, TV, VU, WS |
   | Caribbean | FR, NL | AG, CR, DM, GD, GP, GT, HT, KN, LC, MF, MQ, NI, PA, PR, VC, VI |
   | Atlantic | CA, NO, US | AR, CV, FO, GL, SN, UY |
   | East Atlantic | IS, NO | GM, GW |
   | Indian | – | MU, SC, SO, YE |
   | Arctic | – | FO, GL |
   | North Sea | FR | – |

   The EU set gains GP, MF and MQ.
4. **K1 is split.** Connection-scorer parity and the R → JSON export of
   `SES_CONNECTION_DB` / `SES_SYNONYM_DB` become **K1b** (§8). Live R almost
   certainly blends a torch ML score into connection relevance (§1.2), and
   the scorer brings its own output decisions.
5. **(K1b)** Accepted wizard connections carry R's `strength` and integer
   `confidence`.
6. **(K1b)** The scorer keeps only R's 10 type pairs, in R's order, and
   drops `responses_states`.

**Calls made while revising (mine; flagged for the user's check):**
- **Wizard steps 2 (countries) and 3 (main issue) become skippable,** as in
  R (`skip_question`, `ai_isa_assistant_module.R:2124-2154`). Today
  `_on_next` rejects an empty `choice_many` (`ai_isa_wizard.py:531-539`).
  Without the change, SESPy users would always get GOV items, and the
  parity cells with no countries or no issue could never happen in SESPy.
- **R's KB "regional recommendation" lines are deferred to P14** (Report
  prep). Details in §4.7.

### 1.2 Facts this design rests on (verified at v1.34.2)

**`data/ses_knowledge_db.json`**
- Top-level keys: `version` "1.0", `description`, `last_updated`,
  `contexts`, `generic_fallback`, `cross_ecosystem_links`.
- `contexts` holds **33** entries, keyed `<sea>_<habitat>`, in a fixed file
  order. Each has `regional_sea`, `habitat` and `description`, 7 category
  lists (`drivers` … `responses`) of `{name, relevance}`, and `connections`.
- One element (mediterranean_island, pressures) has no `relevance` but has
  a `description`; R defaults its relevance to 0.5. Another element carries a
  `flag`.
- Totals: 1,260 elements and 1,185 connections. A connection has `from`,
  `from_type`, `to`, `to_type`, `polarity`, `strength`, `confidence` (2–5),
  `rationale`, `references[]`, `temporal_lag` and `reversibility`.
- `generic_fallback` has the 7 lists but no connections.
- **Every** context and the fallback have all 7 categories non-empty at
  relevance ≥ 0.5.
- There are 20 `cross_ecosystem_links`, and no R code reads them.

**`data/country_governance_db.json`**
- Top-level keys: `version` "1.0", `last_updated`, `countries_by_sea`
  (11 seas), `countries` (**105**), `governance_elements` (6 groups),
  `socioeconomic_elements` (3 income levels), `regional_conventions`
  (**15**).
- A country record has `code`, `name_en`, `eu_member`, `income_level`,
  `governance_group` and `regional_conventions[]`.
- There were 99 countries at v1.31.0. The 6 added since came with no
  `version` bump.

**R's wizard**
- `get_context_suggestions(category, regional_sea, ecosystem_type,
  main_issue, countries, return_sources = TRUE)` is called at
  `ai_isa_assistant_module.R:1507`, and its observers at :2029.
- `main_issue` is a character vector, tested with `any(grepl(...))` in
  if / else-if order.
- `countries` is a vector of ISO codes, in click order (:1877).
- Up to 12 suggestions are shown (:1523).

**R's ML model (K1b only)**
- `calculate_relevance` blends `0.3 × keyword + 0.7 × ML` when
  `ml_model_available()` (`connection_generator.R:286-318, 502-510`).
- `ML_ENABLED` defaults to TRUE (`global.R:744`, env
  `MARINESABRES_ML_ENABLED`).
- On laguna torch is installed, `models/checkpoint_*.pt` exist, and no
  server config sets the variable. So live R almost certainly runs with ML on.
- K1's features never touch ML.

**SESPy's current state**
- **Wizard steps:** sea (0), ecosystem (1), countries (2, as names) and
  issues (3) (`sespy/wizard.py:36-49`). Steps 4–10 are free-text rows with
  no suggestions (`sespy/modules/ai_isa_wizard.py:131-194`).
- **Saved metadata:** only sea and ecosystem are written to
  `ProjectMetadata`. R saves the same two fields, and neither app stores the
  country.
- **Connection scorer:** `sespy/connection_scorer.py` ported only R's inline
  fallback branches, and it scores 11 pairs (R's 10 plus
  `responses_states`). K1b fixes this.
- **Schema:** `PROJECT_SCHEMA_VERSION = 8`,
  `SCHEMA_MIN_READER = {7: "1.13.0", 8: "1.15.0"}`
  (`sespy/data_structure.py:22,27`). `min_sespy_version` is stamped on the
  serialised dict only (`:556-561`).
- **Files and deploy:**
  - `sespy/data/` does not exist.
  - `deploy/deploy.sh` replaces `$APP_DIR/sespy` wholesale (:80), has no
    pre-flight step, and runs in Git Bash, where there is no `python` on PATH.
  - `app.py` reads no environment variables.
- **Report:** `sespy/report.py` has a title/meta block, then the Summary,
  Feedback loops, Top centrality and Leverage sections (:100-160). It
  renders through `render_html/pdf/docx(project)` (:236/243/263), and
  `report_export.py:87-110` calls these, including an HTML preview.
- **Sync script:** `sespy/r_template_catalogue.py::sync` (:374-389)
  **rebuilds** `tests/parity/r_sync.json` from scratch. `files` gets only its
  own `INPUTS`; `accepted_warnings` gets only template warnings.

---

## 2. Goals, non-goals, anti-goals

### Goals
- **G1 Reference-data layer** (`sespy/r_kb.py`), per umbrella §3 (§4.1).
- **G2 Element suggestions** in wizard steps 4–10, equal to R's
  `get_context_suggestions(..., return_sources = TRUE)`: items, order and
  source labels. Up to the first 12 are shown as toggle chips with KB, GOV
  and SE badges (§4.2, §4.3).
- **G3 Countries** in step 2 come from the governance database, grouped as
  EU and non-EU like R. Values are ISO codes. Steps 2 and 3 become skippable
  (§4.3).
- **G4 (K1b, §8)** Connection-scorer parity.
- **G5 Regional Context report section** in HTML, PDF and Word, equal in
  content to R's `format_kb_section_for_report`, behind R's toggle (§4.7).
- **G6 Provenance:** `metadata.reference_data`, written at serialisation
  and checked on load. This is the schema bump to 9 (§4.6).
- **G7 Live drift check:** `tests/parity/check_live.py` as a `deploy.sh`
  pre-flight (§4.8).
- **G8 Re-pin** all pins to v1.34.2. Triage every changed R path between
  v1.33.0 and v1.34.2, one row per path in `R_SYNC.md` as P1b did (§4.9).

### Non-goals
- Extension-pair suggestions (decision 1).
- Fixing R's habitat lookup (decision 2).
- R's torch ML model; the roadmap §4 puts torch out of scope.
- Connection-scorer changes. They are K1b; K1 leaves `connection_scorer.py`
  and wizard step 11 untouched.
- `cross_ecosystem_links` as a feature. They are vendored as part of the
  file, and nothing reads them, as in R.
- `ses_knowledge_db_offshore_wind.json`. Only R's `scripts/` read it.
- The WP5 files (P4/P8). The layer must take them later with allow-list
  rows only (§4.1).
- Storing the country in the project, which neither app does. The report
  uses all countries of the sea, as R does.
- R's KB regional recommendation lines (→ P14, §4.7).
- Translating KB content or the Regional Context headings. R prints both in
  English (§4.7).

### Anti-goals (failures even if it "works")
- Suggestions that differ from R's for the same inputs.
- Live R data changing under a running session.
- Any write into R's data directory.
- A broken override taking the app down. In the app, a broken override
  logs a warning and falls back. In the deploy pre-flight, drift fails
  loudly, by design.
- Re-typed R data.
- A sync run that silently drops pins.

---

## 3. Constraints carried from the roadmap
- **Allow-list, never a glob.** K1's runtime allow-list is
  `ses_knowledge_db.json` and `country_governance_db.json`, both with
  version key `version`. K1b adds `ses_connection_db.json`.
- **Hashing:** only `sespy/r_sync.py::sha256_norm` and `sha256_text_norm`.
- **Pins:** `tests/parity/r_sync.json` is machine-readable, and
  `docs/parity/R_SYNC.md` mirrors it in the same commit; a test checks the
  two agree. Mechanics: §4.9.
- **Schema rules:**
  - every new serialised field bumps the schema: `PROJECT_SCHEMA_VERSION = 9`,
    `SCHEMA_MIN_READER[9] = "1.16.0"`;
  - the first commit bumps `__version__`, `pyproject.toml` and the MANUAL
    line together;
  - the branch that merges second renumbers.
  - Every save is stamped `min_sespy_version >= 1.16.0`, because the floor
    is keyed on the schema. This holds even when `reference_data` is `{}`.
  - Tests that pin the schema number move with it: `test_data_structure.py`,
    the newer-file and stamp tests in `test_schema_v7.py`, and
    `test_r_template_catalogue.py`. The builder greps for others.
- **MosaicSES:**
  - Its unit suite and full e2e run against the K1 branch before merge,
    with PYTHONPATH pointed at the branch worktree (editable-install trap).
  - Its pattern-scoped selectors are re-grepped against the new chip,
    country and report ids.
  - After deploy, `deploy/verify_live.py` runs against live MosaicSES.
  - MosaicSES reads only sea names and uses no K1 feature. So K1 adds **no**
    MosaicSES `server_settings.env` and no deploy-script change; MosaicSES
    gets vendored data (§4.1). This is a deviation from umbrella §3; see §9.
- **Full e2e gate,** with no heavy jobs running concurrently. CI and tests
  use vendored data only.
- **i18n,** following P1b's convention:
  - R key subsets are copied by script into
    `sespy/translations/modules/isa_data_entry.json` (only the
    `modules.isa.ai_assistant.*` keys K1 uses: source-badge tooltips,
    "Tailored for", EU/non-EU group labels, skip) and
    `sespy/translations/modules/report_context.json`
    (`modules.report_context.include_context`, the label of R's checkbox).
  - The R source files are pinned as fixtures under
    `tests/parity/r_translations/`, and a test checks the strings are equal.
  - `modules.kb_report.*` is **not** adopted (§4.7).
  - SESPy-only keys (provenance toasts) go in `core.json`.

---

## 4. Design

### 4.1 Reference-data layer — `sespy/r_kb.py`
**Allow-list rows** (a module constant). Each row maps a file to:
- `required_keys`;
- `min_counts`, a dict whose keys are dotted paths into the parsed JSON and
  whose values are minimum `len()`, e.g. `{"contexts": 33,
  "cross_ecosystem_links": 0}` and `{"countries": 105,
  "regional_conventions": 15, "countries_by_sea": 11}` (the v1.34.2 counts);
- `version_key`;
- `override: bool`.

**Version check:** the major of the version key is compared with the
vendored copy's.
- An integer value (`schema: 2`) is its own major.
- A string (`"1.0"`) has the part before the first `.` as its major.

**Generic access:** `snapshot.get(name)` returns any allow-listed file.
- Convenience accessors `kb()` and `governance()` wrap it.
- K1b adds `connection_db()`. In K1 the name is simply not on the list.
- P4, P6 and P8 files need only new rows.

**Vendored copies:**
- They live in `sespy/data/r_kb/<file>`.
- `[tool.setuptools.package-data]` gains `"data/r_kb/*.json"`, and a
  packaging test checks the wheel.
- `deploy.sh` replaces `sespy/` wholesale, so the copies ship with the code.
  No deploy change is needed for them.

**Override location:**
- `SESPY_R_DATA_DIR` is read from the environment, else from
  `APP_DIR/server_settings.env` (`KEY=value` lines).
- `APP_DIR` is the directory of the running `app.py`, passed in by
  `app.py`. It is **never** the location of the `sespy` package. On laguna,
  MosaicSES's `sespy/` is a symlink to SESPy's copy, so a package-relative
  lookup would read SESPy's settings.
- MosaicSES has no settings file, so it gets vendored data.

**Deploy handling of the settings file:**
- `deploy.sh` creates `$APP_DIR/server_settings.env` only when it is absent,
  containing `SESPY_R_DATA_DIR=/srv/shiny-server/marinesabres/data`.
  Otherwise it never touches it.
- The file sits beside `app.py`, outside the replaced `sespy/` folder.

**Snapshots:**
- A process-level `_Registry` holds the current immutable
  `Snapshot(files: {name: Entry(data, sha256_norm, source, version)},
  taken_at)`.
- `_Registry.refresh()` re-stats the size and mtime of each override file.
  If any changed, it parses and validates them and swaps the snapshot by
  atomic reference assignment.
- Validation means the required keys, the minimum counts and the major
  version.

**Per-session pinning:**
- `app.py`'s `server()` calls `refresh()`, then takes `snapshot =
  registry.current()` once. It passes `snapshot` as a keyword argument to
  every module server that needs it (wizard, report export, project I/O),
  the same way `project_data` is passed.
- No K1 code reads the registry anywhere else.
- The session's provenance comes from this snapshot.

**Failure:**
- On any failure (missing directory, parse error, failed validation) the
  registry keeps the last good snapshot, else the vendored one.
- It logs one warning per (file, failure kind) per process.
- It never writes into R's directory.

### 4.2 Element suggestions — `sespy/kb_suggestions.py`
This is a pure-function port, exact in order and filtering. Every function
takes the snapshot data as an argument; none reads a global. It covers:
- `build_context_key`, `find_context` (with match kind), `get_context_elements`
  and `get_context_connections` (`ses_knowledge_db_loader.R:94-307`);
- `deduplicate_suggestions` (`ai_isa_knowledge_base.R:233-283`);
- the hardcoded universal, regional, issue and ecosystem lists, verbatim
  (:325-525);
- `get_habitat_specific_suggestions` (:642 onward), used only when the KB
  returns nothing. That cannot happen with the pinned data, but it can with
  an override, so it gets direct fixtures (§7);
- `get_governance_elements` and `get_socioeconomic_elements`
  (`country_governance_loader.R:184-287`);
- `get_context_suggestions(category, sea, ecosystem, main_issue: list[str],
  countries: list[str]) -> list[tuple[name, source]]`.

**Parity details** (each one was confirmed by the dry run or is a known
trap for a naive port):
- **KB call.** The KB is queried with `min_relevance = 0.5` (:304). Three or
  more KB items suppress the universal list (:321).
- **Habitat-key cascade.** The `if … else if` chain is kept in order.
  Regexes are translated one by one, including `sch.ren|sk.rg.rd` and the
  PCRE lookahead in `coast(?!al lagoon)`.
- **Context iteration** uses JSON file order and is never sorted.
- **Relevance.** Missing relevance becomes 0.5. Empty names are dropped.
- **Sort.** Descending and stable, like R's radix `order(decreasing=TRUE)`.
- **`main_issue` matching.** It is a list. Each branch tests "any issue
  matches", in R's branch order. For example, with
  `["Eutrophication", "Overfishing"]` activities take the fishing branch
  and pressures take the eutrophication branch.
- **Combining sources.** R's `unique()` is exact and case-sensitive. It
  runs on the concatenation in R's order: KB, universal, regional,
  ecosystem, habitat, issue, governance, socioeconomic. Then
  `deduplicate_suggestions` runs.
- **`deduplicate_suggestions` traps:**
  - `strsplit(x, "\\s+")` keeps a leading empty token. Python's
    `str.split()` does not, so use `re.split(r"\s+", x)`.
  - `gsub("ing$|ed$|s$", "")` strips one suffix in a single pass, and can
    leave `""`.
  - `intersect()` returns unique words, but the `min(length(...))`
    denominator counts duplicates.
  - The removal rule (keep the shorter one; `break` on removing `i`) is
    kept exactly.
- **Source map precedence:** knowledge_db > governance > socioeconomic >
  regional > issue > ecosystem > habitat > generic.
- **Governance mechanism.** For categories other than drivers, responses
  and welfare, R's `.map_category` raises "subscript out of bounds". The
  `tryCatch` then routes to `.get_*_hardcoded`, which return empty for
  those categories. Port the *effect*: an unmapped category returns `[]`.
- **Country codes** are upper-cased (`.resolve_countries`). Governance
  groups and conventions follow the order the countries are passed in.
- **Category names** are R's plural slugs, which match SESPy's step targets.

### 4.3 Wizard changes — `sespy/wizard.py`, `sespy/modules/ai_isa_wizard.py`

**Step 2 (countries):**
- A selectize built from `governance.countries_by_sea[sea]`, resolved
  through `countries[code]`, with **optgroups** "EU" and "Non-EU" as in R
  (module :1360-1432; group labels from R's keys).
- Each option shows `name_en` and has the code as its value.
- Selection order is kept: selectize keeps click order, and the codes are
  passed in that order.
- R's 12th sea, `other`, stays excluded, as in SP2.

**Steps 2 and 3** accept an empty answer and record `[]` (call in §1.1).

**Codes and names:**
- `WizardState.countries` holds codes.
- A new `WizardState.country_names` holds the names, resolved from the
  session snapshot when the state is assembled.
- `claude_backend.py:313` uses `country_names`. The SP4 prompt content
  stays the same as today for the same picks.
- The code-to-name helper takes the snapshot as an argument.
- `regional_seas.json` loses `countries`, `country_codes` and
  `eu_member_codes`. Tests that read those fields move to the governance
  data.

**Steps 4–10, suggestion chips.** This replaces rev 2's description, which
did not fit the row model.

*How the rows work today:*
- A step's rows are `input_text`s with ids `entry_{target}_{i}`.
- `_render_freeform_multiple` re-renders them with the value priority
  live > saved (`:155-168`). Live values are read under `isolate()`.
- `wizard_answers[target]` is written only by `_on_next` (:661). The
  step-4–10 idempotency block reads it as "the batch already written to
  isa_data" (:602-626).
- Remove drops the last row (:496-502).

*Rules for chips:*
1. **Chips never write `wizard_answers`.** Only `_on_next` does, so the
   idempotency block stays correct.
2. **Separate output.** Chips render in their own `@render.ui` output,
   `chips_{target}`. It reads the row inputs `entry_{target}_{i}`
   **reactively** (no `isolate`), so a chip shows as selected when any row
   equals its text, including text the user typed by hand.
   - "Equals" compares `.strip()`-ed text, exact and case-sensitive. That
     matches `_on_next`'s strip and R's exact `%in%`.
   - Re-rendering the chips on every keystroke is accepted, because the
     output is small.
3. **Click handlers.**
   - There are 7 × 12 handlers (`chip_{target}_{i}`), registered once at
     server start, in the pattern of `_make_add_handler`.
   - At click time the handler recomputes the suggestion list for the
     current context and maps index i to its text, so a stale index never
     adds the wrong text.
4. **Selecting a chip:**
   - If an empty row exists, the handler fills the first empty row with
     `ui.update_text`.
   - Otherwise it adds a staged row. A new
     `staged_rows: reactive.Value[dict[target, dict[int, str]]]` gets the
     text at index n, and `freeform_counts` is bumped.
     `_render_freeform_multiple` gains the priority
     **live > staged > saved**.
   - A staged entry is cleared once the live input reports the same value.
5. **Deselecting a chip** blanks **every** row whose stripped value equals
   the text, **in place**, with `ui.update_text(value="")`. Nothing shifts.
   - `_on_next` already skips empty rows.
   - This mirrors R's remove, which takes out all matching elements with
     `Filter` (module :2050).
6. **Caption.** "Tailored for <translated sea name> - <ecosystem>" uses R's
   key and R's " - " separator, and shows when a sea is set (:1574-1582).
7. **No max-elements limit.** SESPy has no user-level setting. Known
   difference, recorded in the CHANGELOG.

### 4.4 – 4.5 (moved to K1b, §8)

### 4.6 Provenance — schema 9
**The field:**
- `ProjectMetadata.reference_data: dict =
  field(default_factory=dict, kw_only=True)`.
- `from_dict` keeps it only if it is a dict of dicts, and drops it with a
  warning otherwise. Older readers drop the whole field through the
  existing unknown-key filter.
- An entry is `{file: {source: "vendored"|"shared", sha256_norm, version,
  vendored_r_tag}}`.

**Writing it — at serialisation, never into live state:**
- Like `min_sespy_version`, it is stamped onto the output dict by save,
  autosave and download, which receive the session snapshot.
  `project_data` is never mutated.
- An entry for a file is written when this session **read that file for
  this project**:
  - the wizard computed suggestions or countries → both files;
  - a Regional Context section was generated for an export → both files.

  An HTML preview counts as generated. That is accepted: preview means the
  user looked at KB content.
- **Merge rule:** entries for files read this session are replaced by the
  snapshot's values. Entries loaded from the file for files not read this
  session are **kept** as loaded. So "no read, no change", and an unrelated
  save never drops provenance.
- P4, P5 and P6 extend the "read" triggers for their files. This is the
  per-file form of umbrella §3's "write on save" (deviation recorded in §9).

**Checking on load.** For each recorded entry, compare its `sha256_norm`
with three hashes: the session snapshot's, the vendored copy's and the
current shared copy's (the registry exposes all three read-only for this
check only).
- **Equal to the snapshot's:** silent.
- **Equal to vendored or shared, but not to the snapshot's:** toast "This
  project was saved with different reference data (<file> <version>);
  suggestions and report context may differ."
- **Equal to none:** the same toast, plus "the original reference data is
  not available on this server."
- Toast keys go in `core.json`.

**Tests:**
- The schema-9 round trip.
- An older reader drops the field.
- The merge rule: load a file with provenance, make an unrelated save, and
  the entries are kept.
- The three toasts.

### 4.7 Regional Context section — `sespy/kb_report.py`, `sespy/report.py`
**Ports:**
- `get_kb_context_for_report`: relevance ≥ 0.8, the context description,
  and no section when there is no real context (e.g. Irish Sea).
- `match_user_connections_to_kb`:
  - the first matching KB connection wins;
  - a KB name of 2 characters or fewer is skipped. The skip applies to KB
    names only;
  - matching is a substring test in either direction, case-insensitive,
    with R's three-part test;
  - **an empty user label matches everything**, because
    `grepl("", x, fixed=TRUE)` is TRUE. Reproduced, and noted in the
    upstream issue draft.
- `get_governance_context(regional_sea)`, called without countries as in
  R. It prints raw convention keys and governance-group keys.
- `format_kb_section_for_report(..., i18n=NULL)`.

**Input edges:** the project's `isa_data.connections` in list order, with
source and target ids mapped to element labels. Evidence rows follow that
order. R uses `cld$edges`, else `create_edges_df(adjacency)`; for a project
imported from R, row order may differ, which is accepted. Tests compare
rows as a sequence for SESPy-built fixtures.

**Headings are English literals with R's markdown levels.** R calls the
formatter without i18n (`report_generation.R:172`), so R always prints:
- "# Regional Context"
- "## Site Ecological Context"
- "### Key DAPSI(W)R(M) Elements from Knowledge Base"
- "### Scientific Evidence for Connections"
- "### Relevant Governance Frameworks"
- "#### Country-Specific Governance Groups"

The category labels are R's literals ("Drivers (D)" …).

**Placement:** after SESPy's title/meta block, before Summary
(`report.py:~100`), mirroring R's `header + intro + regional + content`.
- HTML and PDF render through the existing template.
- Word renders through `render_docx`, with the same heading levels, lists
  and the 5-column evidence table.

**Gate and toggle:**
- The section is rendered when `regional_sea` and `ecosystem_type` are
  **non-empty** (SESPy defaults them to `""`; R tests `!is.null`) and the
  toggle is on.
- The toggle is a checkbox on Export Report, labelled with R's
  `modules.report_context.include_context`. It defaults to on when a sea is
  set, as in R.
- If generation fails, the section is omitted and a warning is logged
  (R :176-179).

**API change:** `render_html`, `render_pdf` and `render_docx` gain
`snapshot` and `include_regional_context` keyword parameters, and
`report_export.py` passes the session snapshot. No module global is used.

**Deferred to P14:** R's KB regional recommendation lines
(`report_generation.R:476-509`). R emits them only in the full report,
under "### Strategic Recommendations" in the Leverage section, when
leverage results exist (:905-906), and only if the Recommendations box is
ticked (:950). That box is off by default (`prepare_report_module.R:63`).
SESPy has no Prepare Report options yet; P14 ports that module, so the
lines go there (§9).

### 4.8 `check_live.py` and the deploy pre-flight
`tests/parity/check_live.py`:
- It is outside pytest collection: no `test_` prefix, and `testpaths`
  stays as configured.
- It is run as `${SESPY_PY:-micromamba run -n shiny python}
  tests/parity/check_live.py`.

**Steps:**
1. Read `DEPLOY_SERVER` from `deploy/config.env`.
2. Over one SSH session, read the server's `$APP_DIR/server_settings.env`
   to get `SESPY_R_DATA_DIR` (default `/srv/shiny-server/marinesabres/data`).
3. Fetch each allow-listed file, plus `VERSION_INFO.json` from its parent.
4. Compute `sha256_norm` locally and compare it with the vendored pin in
   `r_sync.json`.

**Outcome:**
- It exits non-zero on any mismatch, naming each file, the live R version
  and the hashes.
- A mismatch is accepted only by an exact entry in a new `accepted_live`
  list in `r_sync.json`: `[{file, live_sha256_norm, r_version, reason,
  date}]`. The JSON is authoritative, and `R_SYNC.md` mirrors it.
- `deploy.sh` runs it first and aborts on a non-zero exit.

### 4.9 Pins, sync script and triage
**Sync script.** K1 **extends** `sespy/r_template_catalogue.py::sync` (or
the module behind `python -m scripts.sync_r_templates`), so one run vendors
and pins everything. `INPUTS` gains:
- `data/ses_knowledge_db.json` and `data/country_governance_db.json`, both
  to `sespy/data/r_kb/` (runtime);
- the R sources K1 ports, to `tests/parity/r_source/`:
  `functions/ses_knowledge_db_loader.R`,
  `modules/ai_isa_knowledge_base.R`,
  `functions/country_governance_loader.R`,
  `functions/kb_report_helpers.R` and `functions/report_generation.R`.
  They are pinned so that a re-pin diff shows logic changes, not only data
  changes;
- R's `translations/modules/isa_data_entry.json` (and the report-context
  file), to `tests/parity/r_translations/`;
- the K1 fixtures under `tests/parity/r_fixtures/k1/`. They are produced by
  the R capture script (§7), so they are pinned by hash, not copied.

**Rebuild rule.** The rebuild carries over `accepted_warnings` *and*
`accepted_live`. A test runs `sync --check` and fails if any pinned path or
acceptance would be dropped. The hard-coded `len(paths) == 18` assertion
becomes the new count.

**`check_live.py` path map.** It uses the `INPUTS` entries marked
`runtime` (R path → vendored path).

**Triage.** `git diff --stat v1.33.0 v1.34.2` lists 44 paths, and each gets
a row in `R_SYNC.md` (P1b format). Rows that matter to K1:
- `modules/ai_isa_assistant_module.R`: a source-badge tooltip fix, which
  affects the K1 badge tooltips;
- `translations/modules/isa_data_entry.json`;
- `modules/ai_isa/ui_renderers.R`;
- `constants.R`: adds `DA_CASE_STUDIES` / `DA_SITE_CHOICES`, owned by
  P4/PIMS. It is P1b's pinned fixture, so its hash moves and P1b's parity
  tests must stay green.

All 18 existing pins move to v1.34.2.

---

## 5. Data flow (one session)
1. **Server start:** `refresh()` runs, the snapshot is pinned and passed to
   the modules.
2. **Steps 0–3:** the user picks sea, ecosystem, optional countries (codes,
   click order) and optional issues.
3. **Steps 4–10:** chips come from `get_context_suggestions` against the
   pinned snapshot. Clicks edit the rows; Next writes elements as today.
4. **Step 11:** `suggest_connections`, unchanged in K1.
5. **Save, autosave or download:** the output dict is stamped with
   `reference_data` using the merge rule.
6. **Export Report:** the Regional Context section is built from the
   snapshot.
7. **Load:** provenance is checked against the three hashes, and a toast
   appears if needed.

---

## 6. Error handling
- **Override problems:** one log warning, then fallback. The UI shows no
  error.
- **Unknown sea or ecosystem:** R's behaviour (generic fallback or empty
  lists), never an exception.
- **Report section errors:** the section is omitted with a warning; the
  rest renders.
- **Malformed `reference_data` on load:** ignored with a warning; it never
  blocks a load.

---

## 7. Testing — how "Done" is proven
**R capture script:** `scripts/capture_k1_fixtures.R`, run by hand with
Rscript at the pinned tag.
- Setup: `setwd(R repo)`, a `debug_log` stub, and a `%||%` definition if R
  is older than 4.4.
- It sources `modules/ai_isa_knowledge_base.R`,
  `functions/ses_knowledge_db_loader.R`,
  `functions/country_governance_loader.R` and
  `functions/kb_report_helpers.R`. Shiny and i18n are not needed; this was
  confirmed headless in about 82 s.
- Output is gzipped JSON under `tests/parity/r_fixtures/k1/`. The
  per-source lists are stored once and referenced; the dry run's raw output
  was 5.6 MB before this.

**Suggestion grid:** every SESPy sea × that sea's ecosystem types × 7
categories, crossed with:
- issue sets: `[]`, `["Overfishing"]`, `["Eutrophication"]`,
  `["Eutrophication","Overfishing"]`, `["Marine litter"]`, `["Tourism"]`,
  `["Climate change"]`, using the exact strings from the sea's
  `common_issues`;
- country sets: `[]`, the sea's first two codes in both orders, and one
  code set covering all 6 governance groups, all 3 income levels and all
  15 conventions.

SESPy must match the full ordered list and the source map, beyond the first
12. This supersedes the roadmap's narrower "3 contexts" criterion.

**Further fixtures:**
- **Lookup table:** `find_context` key and match kind for all 69 choices,
  which pins decision 2.
- **`get_habitat_specific_suggestions`:** direct fixtures for each
  (sea, ecosystem, category) branch it has.
- **Countries:** `get_countries_for_sea` for the 11 seas.
- **Report:** `format_kb_section_for_report` markdown for 3 SESPy-built
  projects, each defined in the fixture script:
  - Baltic lagoon: 6 elements, 5 connections, 2 of which match KB edges;
  - Mediterranean seagrass: elements only;
  - Irish Sea: governance only.

  Add one edge with an empty label. Compare after whitespace normalisation
  with SESPy's section rendered to markdown, or to an equivalent structure
  (builder's choice).

**Unit tests (beyond the fixtures):**
- **Layer:** valid, missing, corrupt, too small and wrong-major overrides;
  two sessions keep their own snapshots across a file swap; no writes; one
  warning per kind; integer and string version majors.
- **Chips:**
  - select fills the first empty row;
  - select with no empty row stages a row;
  - deselect blanks all matching rows in place;
  - a hand-typed text shows its chip as selected;
  - Back/Next idempotency with chips.
- **Schema and provenance:** §4.6.
- **Packaging:** the wheel contains the allow-listed `sespy/data/r_kb/*`.
- **Sync:** `--check` detects a dropped pin or acceptance.

**e2e:** a new script `tests/test_kb_wizard_e2e.py` with namespaced
selectors.
1. Choose Baltic → Coastal lagoon → 2 countries.
2. Step 4 shows KB- and GOV-badged chips.
3. Select three chips, deselect the **middle** one, and assert the other
   two rows keep their text and order.
4. Type a chip's text by hand and see it selected.
5. Skip step 3 once.
6. Finish, then export a report and check that Regional Context is present.

`test_wizard_e2e.py` is updated for country codes and optional steps 2–3.

**Gates:**
- the full unit suite;
- the full e2e run (`tests/run_e2e.py`);
- MosaicSES unit and full e2e against the branch (§3);
- `check_live.py` passing against laguna.

**Done when:**
- all gates are green;
- the pins are re-pinned and triaged (§4.9);
- `deploy.sh` runs the pre-flight;
- the CHANGELOG names K1, R v1.34.2 and the known differences;
- the MANUAL has a K1 section and the version line;
- screenshots are regenerated with `tests/make_docs_screenshots.py`;
- after deploy, the worker's `python -s` reports 1.16.0 and
  `verify_live.py` passes.

---

## 8. K1b — connection-scorer parity (decided scope; own spec and plan later)
**Release:** v1.17.0, renumbered if needed. No schema bump: `Connection`
already has `strength` and `confidence`. It depends on K1's layer.
- **Target:** R run with `MARINESABRES_ML_ENABLED=FALSE` (decision 4). The
  capture script forces it.
- **Port:** `lookup_knowledge_base`, `.synonym_match`, `.keyword_idf_weight`,
  `calculate_enhanced_relevance` and `analyze_phrase_polarity`, reading
  `snapshot.connection_db()`. `connection_scorer.py` calls them first, as R
  does (`connection_generator.R:66, 203, 268, 476`).
- **Decision 5:**
  - `ConnectionSuggestion` gains R's `strength` and integer `confidence`
    (4 for an exact match, 3 for a synonym or default).
  - The 0..1 relevance stays a separate field, used by `_dedup_accepted`
    against Claude's 0..1 confidences.
  - The accept path (`ai_isa_wizard.py:926-928`) writes strength and
    confidence onto `Connection`.
  - The K1b spec decides how SP4 merges are won now that R's continuous
    relevance replaces the old 0.3 / 0.6 / 0.9 steps.
- **Decision 6:** R's 10 pairs only, in R's order: D-A, A-P, P-S, S-I, I-W,
  R-P, W-D, W-R, R-D, R-A. The SP3 goldens are re-derived from R.
- **Export:** `scripts/export_r_connection_db.R` writes
  `sespy/data/r_kb/ses_connection_db.json` =
  `{r_tag, connection_db, synonym_db}`, with regexes verbatim.
  - Vendored only (`override: false`).
  - Pinned by `sha256_text_norm` on the `.R` source and `sha256_norm` on
    the JSON, through the extended sync script.
  - `lookup_knowledge_base` and `.synonym_match` use `grepl(perl=TRUE)`;
    only `.keyword_idf_weight` uses R's TRE engine.
- **No temporal lag:** `SES_CONNECTION_DB` has no `temporal_lag` field.
- **Downstream:** umbrella P9 ("type suggestions from K1's KB and
  synonyms") and possibly P13 depend on K1b (§9).
- **Tests:**
  - R's `generate_connections` output, with ML off, for the P2 template
    projects and 3 wizard fixtures, matched on
    `(from, to, polarity, strength, confidence)` and order;
  - `lookup_knowledge_base` and `analyze_phrase_polarity` over a phrase
    table.

No MosaicSES code uses `suggest_connections` or `ConnectionSuggestion`.

---

## 9. Follow-ups this sub-project owns
**Umbrella edits** (branch `docs/r-parity-roadmap`, committed with K1):
- **K1 section:**
  - remove the extension-pair bullet and fix "Done when" (decision 1);
  - pin v1.34.2, with counts 105 countries, 15 conventions and 11 seas;
  - note that `cross_ecosystem_links` are unused.
- **New K1b node and section** (v1.17.0, depends on K1):
  - move the `ses_connection_knowledge_base.R` / `SES_CONNECTION_DB` /
    `SES_SYNONYM_DB` export bullet into it;
  - add the edges K1b → P9, and K1b → P13 if P13's spec confirms the need;
  - in the §3 allow-list, change "export (K1)" to "(K1b)";
  - add K1b to the §3 release sequence.
- **Record that live R runs torch ML,** and that SESPy matches R run with ML
  off.
- **§3 MosaicSES:** its settings file is deferred to the first sub-project
  whose features MosaicSES uses.
- **§3 Provenance:** written per file, when read, with the merge rule
  (§4.6).
- **P14:** add "K1's KB regional recommendation lines
  (`report_generation.R:476-509`), behind the Recommendations option". Add a
  note to R_SYNC row 18.

**Other corrections:**
- **P1a spec and CHANGELOG:** correct the extension-pair description
  (`2026-10-17-p1a-…-design.md:85-88`, `CHANGELOG.md:206-207`).

**Upstream R issues (drafts only; the user files them):**
1. Habitat lookup quirks, with the full 69-row resolved-key table from the
   §7 fixture. This includes the unreachable `indian_ocean_island`,
   `tropical_mangrove` and `macaronesia_*` contexts, and the empty-label
   match-all in `match_user_connections_to_kb`.
2. The KB-seeding path in `generate_connections` is never called
   (`step_navigation.R:92` passes no context).
3. `.map_category` raises on unmapped categories and relies on `tryCatch`.
4. `country_governance_db.json` gained 6 countries without a `version` or
   `last_updated` bump.

## 10. Left to the builder
- Module boundaries inside `sespy/`; the names above are suggestions.
- The markdown-vs-structure comparison for the report test.
- Chip styling, matching SESPy's wizard look.
- One R script or two for capture and export.
- Whether `staged_rows` is one dict or one value per target.
