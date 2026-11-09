# K1 — General knowledge-base parity — design

**Status:** Draft rev 6, 2026-11-09. Revised after the builder check and
four review rounds (round 4: fresh read + a 28-scenario browser check of
the chip mechanism, all passing):
1. fresh read, cross-spec, dry run;
2. fresh read, a Playwright chip prototype, an ops/production review;
3. fresh read, cross-spec, plan readiness. Branch `docs/k1-design`,
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
   - The lines the roadmap cites (`:625-640`, inside `:620-639`) are the `matrix_map` of
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
7. **The deploy pre-flight blocks only on broken files.** It blocks on
   unreadable or invalid live files and on a shipped copy that differs from
   its pin. Content drift between laguna's live R files and the pin warns
   but does not block (§4.8). This deviates from umbrella §3 (§9).

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
- Top-level keys: `version` "1.0", `description`, `last_updated`,
  `countries_by_sea` (11 seas), `countries` (**105**),
  `governance_elements` (6 groups),
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
- **G7 Live check:** `tests/parity/check_live.py` as a `deploy.sh`
  pre-flight. It blocks on broken files and warns on drift (§4.8).
- **G8 Re-pin** all pins to v1.34.2. Triage every changed R path between
  v1.33.0 and v1.34.2, one row per path in `R_SYNC.md` as P1b did (§4.9).
- **G9 Safe deploy:** an atomic `sespy/` swap, a MosaicSES restart, and a
  stated MosaicSES compatibility contract (§4.10).

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
  logs a warning and falls back. The deploy pre-flight blocks on broken
  live files and only warns on content drift.
- Workers serving different data to concurrent users, or a deploy that is
  blocked for a hotfix or rollback.
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
- They are loaded **eagerly when `sespy.r_kb` is imported**. If one is
  missing or invalid, the import fails loudly, because a broken build must
  not start.
- **Manifest.** `sespy/data/r_kb/manifest.json` = `{r_tag, r_commit,
  files: {name: sha256_norm}}` is written by `sync` and pinned. It is the
  app's only runtime source for the R tag: `tests/` does not ship, and the
  data files say `version` "1.0".
  - A vendored entry is labelled "R <r_tag>".
  - A shared entry whose hash equals the manifest's is labelled "R <r_tag>".
  - Otherwise it is labelled "shared, differs from R <r_tag>".
  - `<R_DATA_DIR>/../VERSION_INFO.json` is read **optionally** (read-only,
    never validated, never blocking). When present, its version is shown
    as "live R <version>".
- Importing `sespy.r_kb` reads nothing relative to `APP_DIR`. That happens
  only when `app.py` calls `configure(app_dir)`.
- They ship with the code. Deploy atomicity: §4.10.

**Override location:**
- `SESPY_R_DATA_DIR` is read from the environment, else from
  `APP_DIR/server_settings.env` (`KEY=value` lines).
- If the variable is **present in `os.environ`, even empty, it wins** and
  the file is not read. The e2e runner sets it to `""` in `_child_env`
  (`run_e2e.py:55-65`).
- `APP_DIR` is the directory of the running `app.py`, passed in by
  `app.py`. It is **never** the location of the `sespy` package. On laguna,
  MosaicSES's `sespy/` is a symlink to SESPy's copy, so a package-relative
  lookup would read SESPy's settings.
- MosaicSES has no settings file, so it gets vendored data.

**Settings-file rules:**
- **Created only if absent.** `deploy.sh` creates
  `$APP_DIR/server_settings.env` only when it is absent, with
  `umask 022; [ -e f ] || printf 'SESPY_R_DATA_DIR=%s\n' /srv/shiny-server/marinesabres/data > f; chmod 0644 f`.
  Otherwise it never touches the file.
- **Never wiped by deploy.** The file sits beside `app.py`. `deploy.sh`
  removes only `sespy/`, `__pycache__` and `docs/screenshots` (:80), and
  scp merges, so the file survives.
- **Gitignored.** `server_settings.env` is added to `.gitignore`, since the
  server's `APP_DIR` has a `.git`.
- **Read at every `refresh()`** (cheap), so editing it needs no restart.
- **Empty means off.** `SESPY_R_DATA_DIR=` (empty) disables the override.
  Locally, `app.py`'s directory is the repo root; the e2e runner sets
  `SESPY_R_DATA_DIR=` explicitly, so a stray local file can never feed live
  data into tests.

**Snapshots:**
- A process-level `_Registry` holds the current immutable
  `Snapshot(files: {name: Entry(data, sha256_norm, source, version)},
  taken_at)`.
- `_Registry.refresh()` stats each override file. The change key is
  `(st_ino, st_size, st_mtime_ns, st_ctime_ns)`: ctime cannot be preserved
  by `cp -p` or `rsync -t`, and it changes on a rename swap.
- If any key changed, it parses and validates **all** override files and
  swaps the snapshot by atomic reference assignment **only if all pass**.
  A snapshot never mixes a new KB with old governance data.
- A failed stat or parse is never recorded as "seen", so the next session
  retries.
- Validation means the required keys, the minimum counts and the major
  version.
- Parsing runs on the event loop inside `server()`. After an R change, the
  first session on each worker pauses briefly (the KB is 1.1 MB), which is
  accepted.
- Any cache in `kb_suggestions` is keyed on the snapshot's hashes, never
  process-global (the `Translator._lang` precedent).

**Per-session pinning:**
- `app.py`'s `server()` calls `refresh()`, then takes `snapshot =
  registry.current()` once. It passes `snapshot` as a keyword argument to
  every module server that needs it (wizard, report export,
  `quick_actions_server`, `topbar_actions_server`), the same way
  `project_data` is passed. The wizard, report export and
  `quick_actions_server` also receive `reference_reads` (§4.6).
- Any future module that reads reference data (P4, P6) must likewise
  receive `snapshot` and `reference_reads` as keyword-optional arguments.
- No K1 code reads the registry anywhere else.
- The session's provenance comes from this snapshot.

**Failure, deterministic across workers:**
- **Directory missing or unreadable** (e.g. R moved `data/` to `data.bak`):
  every worker switches to **vendored**. Old workers drop their shared copy
  too, so concurrent users never see different suggestions.
- **One allow-listed file missing from a present directory:** treated like
  an invalid file (keep last good, else vendored, retry next session).
- **A file present but unparsable or invalid** (a torn read during an R
  deploy): keep the last good snapshot, else vendored, and retry on the
  next session.
- **Logging:** each **transition** (shared → vendored, vendored → shared,
  last-good kept) is logged with file, reason and hashes, not only the
  first failure.
- It never writes into R's directory.

**Visibility.** The **About** modal gains a "Reference data" section,
element id `about-reference-data`. Per allow-listed file it shows the
source (shared or vendored), the manifest label, the optional live R
version and a short hash, all from the session snapshot. That lets anyone
check what laguna serves without reading worker logs, which shiny-server
deletes. `topbar_actions_server` receives `snapshot` (it is in the
module-server list above), and `_about_modal` (`topbar_actions.py:254`)
takes it as a parameter.

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
- **Changing the sea after Back.** When step 0's answer changes, `_on_next`
  for step 0 filters `wizard_answers["countries"]` to codes present in the
  new sea's `countries_by_sea` list. Step 2 then shows only those as
  selected.
- R's 12th sea, `other`, stays excluded, as in SP2.

**Steps 2 and 3** are skippable (call in §1.1):
- Next with an empty selection is accepted and records `[]`.
- A "Skip" button (`wizard-skip_{target}`, labelled with R's
  `modules.isa.ai_assistant.skip_this_question`) does the same, as in R.
- R lays out countries as buttons under "EU member states" / "Non-EU
  countries" headings, with a per-country EU badge (module :1362-1432).
  SESPy adapts this to selectize **optgroups** with those headings
  (`eu_member_states`, `non_eu_countries`), which are R's keys.

**Codes and names:**
- `WizardState.countries` holds codes.
- A new `WizardState.country_names` holds the names, resolved from the
  session snapshot when the state is assembled.
- `claude_backend.py:313` uses `country_names`. The SP4 prompt content
  stays the same as today for the same picks.
- The code-to-name helper takes the snapshot as an argument.
- `regional_seas.json` loses `countries`, `country_codes` and
  `eu_member_codes`. `get_eu_member_codes()` is deleted with its tests;
  MosaicSES does not import it. Tests that read the removed fields move to
  the governance data.
- Four call sites in `test_wizard_e2e.py` pass `['Lithuania']`
  (:79, :113, :320, :404); all four become codes.

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

*Two problems with today's code that chips would expose* (both found by the
round-2 prototype):
- The renderer's "priority" is a truthiness fallback,
  `current_values[i] or saved[i]` (`:168`). A row blanked by the server
  (`""`) falls back to its saved value on the next re-render, so a
  deselected chip comes back.
- `ui.update_text` is not visible in `input.entry_*` until the client
  echoes it, one round trip later. Two chip clicks in one tick target the
  same "empty" row. A chip click followed by Next in the same tick reads
  stale rows.

*Row-id generations.* Shiny keeps an input's last value after its element
leaves the DOM. So rows from an earlier wizard run, or from an earlier visit
to the same step, would still "exist" with old text. Row ids therefore
carry a generation: `entry_{gen}_{target}_{i}`.
- `gen` is a per-target counter, bumped on `_on_modal_replace` and
  whenever a step is entered (Next into it, or Back into it).
- Within one visit, rows keep their ids, so typing and chips work as below.
- **Stable test hook.** Each current-generation row input carries
  `data-row="{target}_{i}"` (it is unique, since only the current
  generation is in the DOM). e2e selectors use
  `#wizard-freeform_{target}_container [data-row="{target}_{i}"]`, never
  `[id$=…]`. The existing `#wizard-entry_{target}_{i}` selectors in
  `test_wizard_e2e.py` (:86, :120, :360-361, :378, :381, :413) are
  rewritten to it.
- On every entry, a new visit renders from `wizard_answers` (saved) with no
  live values, so stale text can never win.
- **Behaviour change (my call):** unsaved text typed on a step is discarded
  by Back; only Next persists it. Today it survives Back only by accident,
  through sticky input ids. R's wizard has no unsaved state at all, because
  each pick is applied immediately. Recorded in the CHANGELOG.
- Shiny never drops keys from `input`, so each visit leaves a few dead
  entries (measured: 5 → 87 keys over 20 Back/Next cycles with 3 rows).
  That is linear in user actions, freed at session end, and accepted.
- Chip ids need no generation; they are action buttons whose count does not
  matter.

*The pending overlay.* A reference prototype with generations, run with
the `CLEAR_ON_ENTRY=1 CLEAR_AFTER_WRITE=1` switches that this text now
specifies, passes **all 28** browser scenarios (round-4 verification). It
is kept in the gitignored `.superpowers/k1-prototypes/chips/`:
`app_gen.py`, with its Playwright driver `drive_gen.py`. The plan ports
from it.
- A new `pending: reactive.Value[dict[target, dict[int, str]]]` records
  **every server-issued row write**: a chip fill, a chip-added row, a
  deselect blank, and the "re-added index starts blank" tombstone below.
- **Effective row value** = `pending[i]` if present (including `""`), else
  the live input if it **exists** (even `""`), else `saved[i]`, else `""`.
  - "Exists" means the input has been registered for the **current
    generation**. Reading it does not raise `SilentException`.
  - This replaces the truthiness fallback. Generations handle stale values
    from Replace and from earlier visits; the overlay handles stale values
    within a visit (Remove, then Add).
- **Row count** = `max(freeform_counts[target], len(saved), max(pending
  indices) + 1, 1)`. The renderer, the chips, the click handlers,
  `_on_next` **and the Add and Remove handlers** all use it.
  - Add sets `freeform_counts = rowcount + 1`.
  - Remove sets `freeform_counts = max(rowcount - 1, 1)`. Because the count
    includes `len(saved)`, Remove cannot go below the saved length after a
    Back. That is today's behaviour, kept as is: saved entries are removed
    by blanking them, which chips do and the user can do by clearing the
    text.
- **Every reader uses effective values:** the renderer, the chip output,
  the chip handlers' "first empty row" and "already selected" checks, and
  **`_on_next`'s freeform read** (replacing the raw `input[...]` read at
  :549-552).
- **Clearing.** A small effect per target drops a pending entry as soon as
  the live input reports the same value.
- **Lifetime:**
  - `_on_next` clears `pending[target]` **after a successful write**
    (validation passed), not after the read. On a validation failure
    pending is kept, so a chip-added row survives the failed Next;
  - `pending[target]` is dropped **whenever `gen[target]` is bumped** (step
    entry and Replace), so a chip clicked in the same tick as Back never
    leaks into the next visit;
  - Remove drops pending indices at or above the new count;
  - `_on_modal_replace` resets `pending` next to `freeform_counts.set({})`
    (:471-472) and bumps every generation;
  - Add sets `pending[n] = ""` when index n still holds a stale non-empty
    live value in the current generation.
- **Renderer dependencies.** `_render_freeform_multiple` reads `pending` and
  live inputs under `isolate()`, so clearing a pending entry does not
  re-render the step. It keeps reading `wizard_answers` and
  `freeform_counts` reactively, as `wizard_step_render` (:1007) does today.

*Rules for chips:*
1. **Chips never write `wizard_answers`.** Only `_on_next` does, so the
   idempotency block stays correct.
2. **Separate output.** Chips render in their own `@render.ui` output,
   `chips_{target}`. It computes effective values **reactively** (no
   isolate) over the full row count.
   - A chip shows as selected when any effective row equals its text. That
     includes a chip-added row that has not rendered yet, and text typed by
     hand.
   - "Equals" compares `.strip()`-ed text, exact and case-sensitive,
     matching `_on_next` and R's `%in%`.
   - Re-rendering on keystrokes is accepted. Text inputs debounce about
     250 ms, so a chip click inside that window sees the previous typed
     value, exactly as Next does today.
3. **Click handlers.**
   - There are 7 × 12 handlers (`chip_{target}_{i}`), registered once at
     server start, in the pattern of `_make_add_handler`.
   - At click time the handler recomputes the suggestion list and maps
     index i to its text. If i is past the end of the list, it does
     nothing.
   - A chip handler whose target is not the current step's target does
     nothing. This covers Next followed by a chip in the same tick.
4. **Selecting** a chip:
   - if an effective row is empty, set `pending[k] = text` for the first
     one, and call `ui.update_text` if that input exists;
   - otherwise set `pending[n] = text` and bump `freeform_counts`, so the
     new row renders with the text.
5. **Deselecting** sets `pending[k] = ""` for **every** effective row equal
   to the text, and calls `update_text("")` where the input exists. Nothing
   shifts. This mirrors R's `Filter` removing all matches (module :2050).
6. **Caption.** " (Tailored for <translated sea name> - <ecosystem>)", with
   R's parentheses, key and " - " separator, shown when a sea is set
   (:1574-1582).
7. **No max-elements limit.** SESPy has no user-level setting. Known
   difference, recorded in the CHANGELOG.

*Scenarios the unit and e2e tests must cover* (the prototype's set):
- select 3 chips with one empty row;
- deselect the middle chip;
- hand-typed text, including a trailing space;
- Add and Remove interleaved with chip clicks;
- Back, deselect a saved item, Add: the row stays blank;
- type in row 1, Remove, then select a chip with no empty row;
- two clicks on **different** chips in the same tick, with and without an
  empty row. Two same-tick clicks on one chip merge on the client into one
  event; a real double-click is two separate clicks;
- chip + Back in the same tick, then re-enter the step: no leaked text;
- a chip that adds a row + Next in the same tick, with Next failing
  validation: the row survives;
- a chip then Next in the same tick, on the fill path and on the added-row
  path;
- Back/Next idempotency;
- the Replace flow resetting the overlay;
- **Replace, then re-enter step 4:** no text from the previous run;
- **chip + Next in the same tick, then Back:** the row shows the saved text;
- **changing the sea after Back:** the country codes saved for the old sea
  are filtered to the new sea's list before suggestions are computed.

**Country order after Back (verify in the browser first).**
`_render_choice_many` re-renders with `selected=` (:122-128). Selectize may
rebuild its items in option (DOM) order rather than click order, and that
order changes governance and suggestion order.
- The builder checks this in a browser.
- If it is so, the renderer restores the saved order, e.g. through
  selectize's `items` option or by emitting the selected options first, in
  saved order.
- An e2e goes Back and Next and asserts the order.

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

**Where loaded entries live.** `from_dict` keeps them on
`project_data.metadata.reference_data`. `replace()` and
`with_modified_now()` carry them along (`data_structure.py:656-660`).

**What is read this session.** A session-level `reference_reads:
reactive.Value[frozenset[str]]` is created in `app.py`'s `server()`, next
to the snapshot, and passed to the module servers like `event_bus`.
- **Writers add file names to it:**
  - the wizard, when it computes suggestions or countries → both files;
  - report export, when it generates a Regional Context section → both
    files. An HTML preview counts, since it shows KB content.
- **No self-invalidation.** Shiny's `Value.set` compares by identity
  (`_reactives.py:510`), so a render that does `rr.set(rr.get() | {...})`
  would loop. Writers read `reference_reads` under `isolate()` and call
  `set` **only when a name is actually new**. This matters for the chips
  output and the report preview, which are renders.
- **Reading the session's provenance.** One helper,
  `r_kb.current_provenance(meta, snapshot, reads) -> dict`, computes the
  merged dict below. Save, autosave and download use it, and so will P5's
  Excel export and P6c's appendix. They add their own files to `reads`
  first and never read raw `metadata.reference_data`.
- **Reset to empty whenever the project is replaced:** on
  `event_bus.project_loaded` (upload, restore, recent, import), on
  `template_loaded`, and on New (`project_io.py:382-384`, which today emits
  `isa_change` and `cld_update` but no load event; the builder adds the
  reset there). Wizard Replace keeps the
  metadata, so it keeps the set.

**Writing — at serialisation.** `project_data` is never mutated for
provenance.
- The stamp is computed as `merged = {**meta.reference_data, **{f:
  snapshot.files[f].provenance() for f in reference_reads}}`.
  - `Entry.provenance()` returns exactly `{source, sha256_norm, version,
    vendored_r_tag}`; the tag comes from the manifest.
  - It never includes `data`. A test asserts that a saved file carries no
    `data` key and stays small.
- It is threaded through a new keyword argument, default `None`, meaning
  "write `meta.reference_data` as is":
  - `Project.to_dict(reference_data=...)` and `to_json(...)`;
  - `persistent_storage.save_project_atomic(...)` and
    `project_to_bytes(...)`;
  - `autosave.write_autosave(...)`.
- `quick_actions_server` (`app.py:198`; save, download and autosave in
  `project_io.py:142-161, 292-318`) receives `snapshot` and
  `reference_reads`, and passes `merged`.
- Autosave reads `reference_reads` under `isolate()`, so a KB read alone
  never triggers an autosave. The read reaches disk with the next
  `isa_change`, which is accepted.
- Callers outside a session (MosaicSES's `c.project.to_dict()`, the
  template catalogue's `to_json()` at `r_template_catalogue.py:189`) pass
  nothing and keep working.
- Effect: "no read, no change", so an unrelated save never drops loaded
  provenance.
- P4, P5 and P6 add their own writers. This is the per-file form of
  umbrella §3's "write on save" (deviation recorded in §9).
- **Known side effect:** `asdict(metadata)` now always writes
  `"reference_data": {}`. The 7 shipped `sespy/templates/marinesabres/*.json`
  files are regenerated in the same commit as the schema bump, and
  MosaicSES compartment dicts gain the key too.

**Checking on load.** One effect, keyed on the same load events as the
reset (placed like `_newer_build_warning`, `project_io.py:242-269`), reads
`project_data.get().metadata.reference_data`. For each entry it compares
`sha256_norm` with three hashes:
- the session snapshot's;
- the vendored copy's;
- the registry's **last parsed** shared copy's. This is held in memory and
  never re-read at load.

Outcomes:
- **Equal to the snapshot's:** silent.
- **Equal to vendored or shared, but not to the snapshot's:** toast "This
  project was saved with different reference data (<file>, R
  <vendored_r_tag>); suggestions and report context may differ."
- **Equal to none:** the same toast, plus "the original reference data is
  not available on this server."
- **An entry without `sha256_norm`:** ignored.

The version key is not shown, because both R files say "1.0" and never
bump. `vendored_r_tag` is the R tag of SESPy's vendored copy, even when
`source` is "shared"; it tells the reader which SESPy pin was current.
Toast keys go in `core.json`.

**Tests:**
- The schema-9 round trip.
- An older reader drops the field.
- The merge rule: load a file with provenance, make an unrelated save, and
  the entries are kept.
- The three toasts.

### 4.7 Regional Context section — `sespy/kb_report.py`, `sespy/report.py`
**Ports:**
- `get_kb_context_for_report`: relevance ≥ 0.8 and the context
  description. With no real context (e.g. Irish Sea) there is no Site
  Ecological Context and no Key Elements subsection. Governance still
  prints. The whole section is omitted only when the body is empty
  (`report_generation.R:173-175`).
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

**Heading levels.** SESPy's report title is `<h1>` and its sections are
`<h2>` (`report.py:93,102`). So R's levels shift down by one: "Regional
Context" is `<h2>`, "Site Ecological Context" is `<h3>`, and so on down to
`<h5>`. The text is unchanged. The report CSS (`report.py:44-48`) styles
only h1–h3, so h4 and h5 styles are added. Word uses Heading 2–5.

**Placement:** after SESPy's title/meta block, before Summary
(`report.py:~100`), mirroring R's `header + intro + regional + content`.
- HTML and PDF render through the existing template.
- Word renders through `render_docx`, with the same heading levels, lists
  and the 5-column evidence table.

**Gate and toggle:**
- The section is rendered when `regional_sea` and `ecosystem_type` are
  **non-empty** (SESPy defaults them to `""`; R tests `!is.null`) and the
  toggle is on.
- The toggle is a checkbox on Export Report (`report_export-include_regional_context`),
  labelled with R's `modules.report_context.include_context`. It defaults
  to **on** unconditionally, as R's checkbox does
  (`prepare_report_module.R:65-67`). The non-empty gate above decides
  whether anything renders.
- If generation fails, the section is omitted and a warning is logged
  (R :176-179).

**API change:**
- `render_html`, `render_pdf` and `render_docx` gain the keyword parameters
  `snapshot=None` and `include_regional_context=False`. These defaults keep
  existing callers and tests unchanged.
- `report_export.py` passes the session snapshot and the toggle, and adds
  to `reference_reads` when the section is generated.
- The HTML preview (`report_export.py:97-110`) depends on the toggle.
- No module global is used.

**Deferred to P14:** R's KB regional recommendation lines
(`report_generation.R:476-509`). R emits them only in the full report,
under "### Strategic Recommendations" in the Leverage section, when
leverage results exist (:905-906), and only if the Recommendations box is
ticked (:950). That box is off by default (`prepare_report_module.R:63`).
SESPy has no Prepare Report options yet; P14 ports that module, so the
lines go there (§9).

### 4.8 `check_live.py` and the deploy pre-flight
**Decision (user, 2026-11-09): block only on broken files.** This deviates
from umbrella §3, which blocks on any drift (§9). A content drift does not
endanger production: the app reads the live files and validates them
itself. Blocking on drift would gate hotfixes and rollbacks after every R
redeploy.

**Fetching is done by `deploy.sh`**, with its own `ssh`/`scp` and the
`$SERVER` it is deploying to, so it honours the env override at :27-30 and
uses the same ssh agent.
1. Read the server's `$APP_DIR/server_settings.env` to get
   `SESPY_R_DATA_DIR`.
   - **If the file is absent** (the first K1 deploy), use the default path
     that the create step is about to write, so live data is never switched
     on unchecked.
   - **If the value is empty** (override off), skip only the live checks
     (fetch, and checks 1 and 3 below). The shipped-copy check 2 always
     runs.
2. Copy each **`override: true`** allow-list file, and the R app's
   `VERSION_INFO.json`, into `$STAGE/.live/`.
3. Check that user `shiny` can read each file and traverse the directory
   path, with `sudo -n -u shiny test -r <file>` where available, else by
   checking `stat -c '%a %U %G'` on the file and on each parent directory
   (read + execute for other or for group `shiny`).

**Checking is pure local hashing:**
`${SESPY_PY:-micromamba run -n shiny python} tests/parity/check_live.py
--live "$STAGE/.live" --stage "$STAGE" --pin tests/parity/r_sync.json`.
- It runs from the **working tree**: `check_live.py` and `r_sync.json` are
  read from the repo, because `$STAGE` ships no `tests/`.
- The script has no `test_` prefix and stays outside pytest collection.
- **Run by hand after an R deploy:** `check_live.py --fetch` performs the
  same ssh fetch itself into a temp directory, then checks. `SERVER` and
  `APP_DIR` come from `deploy/config.env` (`DEPLOY_SERVER`, `DEPLOY_DIR`),
  overridable by `--server` and `--app-dir`.
1. **Structural (blocks):** a live file is unreadable; or it fails its
   allow-list row (required keys, minimum counts, major version); or it
   is not readable by user `shiny` (neither world-readable nor group
   `shiny`). Exit 2.
2. **Shipped copy (blocks):** the staged `RUNTIME_INPUTS` targets and
   `manifest.json` (named one by one, no glob) differ from their pins in
   `r_sync.json`, i.e. a stale or dehydrated build. Exit 2.
3. **Drift (warns):** the live hash differs from the pin. A loud banner
   names each file, the live R version and both hashes, and suggests
   re-vendoring. Exit 0, or exit 2 with `--strict`.
4. **Escape:** `deploy.sh` reads `SESPY_SKIP_LIVE_CHECK="<reason>"`; if it
   is set, `deploy.sh` does not call `check_live.py` and echoes the reason.
5. **Rollbacks are never gated.** A new `deploy.sh --rollback` flag passes
   `--warn-only` to `check_live.py`, which then reports every finding and
   exits 0. When deploying a tag older than K1,
   `check_live.py` is absent from the checkout, and `deploy.sh` (from the
   current working tree) skips the check with a message. No server-version
   detection is attempted.

`accepted_live` is not needed and is not added. `r_sync.json` keeps only
`accepted_warnings`.

### 4.9 Pins, sync script and triage
**Sync script.** K1 **extends** `sespy/r_template_catalogue.py::sync` (the
module behind `python -m scripts.sync_r_templates`), so one run vendors and
pins everything. Three kinds of input:
1. **`INPUTS`** (existing, `dict[R path → repo path]`, fetched with
   `git show tag:path`). It gains:
   - the R sources K1 ports, to `tests/parity/r_source/`:
     `functions/ses_knowledge_db_loader.R`,
     `modules/ai_isa_knowledge_base.R`,
     `functions/country_governance_loader.R`,
     `functions/kb_report_helpers.R` and
     `functions/report_generation.R`. A re-pin diff then shows logic
     changes, not only data changes;
   - The translation stems `isa_data_entry` and `report_context`, added
     **through `TRANSLATION_SUBSETS`** rather than as separate `INPUTS`
     rows: `INPUTS` already includes every subset stem, and the vendored
     file is named after the R stem (`r_template_catalogue.py:51-71`).
     - The keys, all present at v1.34.2:
       - in `translations/modules/isa_data_entry.json`,
         `modules.isa.ai_assistant.` + `from_knowledge_database`,
         `governance_suggestion_tooltip`,
         `socioeconomic_suggestion_tooltip`, `tailored_for`,
         `eu_member_states`, `non_eu_countries` and `skip_this_question`.
         `eu_member_state` (R's per-country badge tooltip) is not used,
         because optgroups replace the badge; the prefix rule pulls it in
         harmlessly;
       - in `translations/modules/report_context.json`,
         `modules.report_context.include_context`.
     - Prefix matching (`r_template_catalogue.py:226-235`) also selects
       `key_*` siblings; that is harmless here, and exact keys are listed.
   - Paths use the same `MarineSABRES_SES_Shiny/…` prefix form as the
     existing entries, because the R git root is `SESToolbox`.
2. **`RUNTIME_INPUTS`** (new): `data/ses_knowledge_db.json` and
   `data/country_governance_db.json`, copied to `sespy/data/r_kb/`. This
   set is also `check_live.py`'s map from R path to vendored path, and K1b
   adds its export to it.
   - `sync` also writes `sespy/data/r_kb/manifest.json` (§4.1). It is a
     **generated output**, like the converted templates: `sync` writes it
     from `r_tag`, `r_commit` and the `RUNTIME_INPUTS` hashes, pins its
     `sha256_norm` under `files`, and `--check` compares a rebuild with
     disk. "All three kinds" in the count test means `INPUTS`,
     `RUNTIME_INPUTS` (plus the manifest) and `LOCAL_PINS`.
   - These are pins of a **new class**: vendored runtime outputs. P1b
     pinned only fixtures. It is consistent with umbrella §3's "vendored
     files".
   - In `--from-fixtures` mode the `data/` prefix rule (:327) reads them
     from the already-vendored copies. `--check` compares rebuilt outputs
     with disk, as for templates.
3. **`LOCAL_PINS`** (new): paths hashed from disk, never fetched or
   written. These are the five K1 fixtures under
   `tests/parity/r_fixtures/k1/` (§7).
   - `.gz` files are hashed as `sha256_norm(json.loads(gunzip(file)))`,
     keeping §3's two-helper rule and staying immune to the gzip header
     mtime. They bypass `_hash`/`_same`, which decode UTF-8 (:273-275).
   - Each fixture's top-level `r_tag` is read after gunzip. `sync` fails
     when it differs from the target `r_tag`, so fixtures go stale loudly
     on a re-pin.
   - `--check` re-hashes them from disk.

**Rebuild rule.**
- Factor out a pure `build_pin(pin_old, files_new, warnings_new) -> pin_new`.
- `files` is rebuilt from all three kinds.
- `accepted_warnings` is regenerated from current warnings, as today, so
  stale acceptances drop by design.
- Fail when `set(pin_old.files) - set(pin_new.files)` is non-empty, unless
  the path was removed from the input lists in the same change.
- Unit tests call `build_pin` directly, so CI needs no R checkout.
- The two hard-coded counts (`tests/parity/test_r_sync.py:27`,
  `tests/test_r_template_catalogue.py:406`) become the new totals, and
  `sorted(pin["files"]) == sorted(INPUTS.values())` becomes "all three
  kinds".

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

### 4.10 Deploy atomicity, MosaicSES contract, rollback
**Atomic SESPy deploy.** `deploy.sh:80-84` does `rm -rf sespy` and then a
long scp. A worker spawned in that window, in SESPy or in MosaicSES
through the symlink, sees missing code, and now missing vendored data
too. K1 adopts MosaicSES's swap:
1. upload to `sespy.incoming/`;
2. `mv sespy sespy.old && mv sespy.incoming sespy`;
3. remove `sespy.old`.

The `logs/` stash-and-restore moves into the same sequence.

**MosaicSES restart.**
- `deploy/config.env` (and `config.env.example`) gains an optional
  `DEPLOY_MOSAIC_DIR` (on laguna `/srv/shiny-server/MosaicSES`).
- When it is set, SESPy's deploy touches `$DEPLOY_MOSAIC_DIR/restart.txt`,
  so MosaicSES's workers stop mixing old in-memory sespy modules with new
  files on disk.
- SESPy has no release script. So, after a K1 deploy, a **manual checklist
  step** (listed in the CHANGELOG release notes and the plan's release
  task) runs MosaicSES's
  `micromamba run -n shiny python deploy/verify_live.py --expect-version <v>`
  from the MosaicSES checkout. `<v>` is the version in the deployed
  MosaicSES's `multises_app/__init__.py`, read over ssh.
- `deploy.sh` itself only touches `restart.txt`.
- This is a change to **SESPy's** deploy script only. MosaicSES's own
  deploy script is unchanged (§3).

**MosaicSES compatibility contract.** The round-2 grep found that MosaicSES
uses `get_regional_seas()` (names and ecosystem types),
`isa_data_entry_server`, the analysis servers, and
`Project`/`ProjectMetadata` with `to_dict`/`from_dict`. It does not use the
wizard, report export, `render_*`, `WizardState` or the removed country
fields. So:
- `snapshot` and `reference_reads` are **keyword-optional** wherever they
  are added;
- they never appear on `Project.to_dict`/`from_dict` as required
  arguments, on the `ProjectMetadata` constructor, or on
  `isa_data_entry_server`;
- `get_regional_seas()` keeps `name`, `ecosystem_types` and
  `common_issues`;
- importing `sespy.r_kb` reads nothing relative to `APP_DIR`.

A unit test imports MosaicSES's call sites' signatures (or a copied
fixture of them) to guard this.

**Rollback is one-way.** After 1.16.0, every save and autosave is stamped
schema 9 and `min_sespy_version` 1.16.0. That includes MosaicSES
compartments saved through `to_dict`. On a rollback to 1.15.x these files
read as `newer_build`, and autosave refuses to overwrite them
(`autosave.py:93-98`). The release notes say so, and the policy is
**forward-fix** rather than roll back after users have saved. The
MosaicSES gate includes opening a schema-9 file in 1.15.x to confirm the
read-only behaviour. Mechanics: a scripted manual step outside the unit suite.
1. Make a worktree at the latest v1.15.x tag.
2. Point PYTHONPATH at it.
3. Open one schema-9 SESPy save and one MosaicSES compartment save.
4. Assert `newer_build`, and that autosave refuses to overwrite.

**OneDrive.** `attrib +P` pins `sespy/data/r_kb/` and
`tests/parity/r_fixtures/` locally (the screenshots precedent).
`.gitattributes` gains `*.gz binary`.

---

## 5. Data flow (one session)
1. **Session start** (`server()`): `refresh()` runs, the snapshot is pinned,
   and the snapshot and `reference_reads` are passed to the modules.
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
- **Override problems:** the transition is logged (§4.1), then fallback.
  The UI shows no error; About shows the source.
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
- Output is gzipped JSON under `tests/parity/r_fixtures/k1/`, in five
  files:
  - `lookup.json.gz`
  - `suggestions_grid.json.gz`
  - `habitat_specific.json.gz`
  - `countries.json.gz`
  - `report.json.gz`

  Each has top-level `r_tag`, `r_commit` and `data` keys. The per-source
  lists are stored once and referenced; the dry run's raw output was 5.6 MB
  before this.
- It first checks that the R working tree is clean and that
  `git describe --tags` equals the target tag. The R app is the
  `MarineSABRES_SES_Shiny/` subdirectory of the `SESToolbox` repository;
  the tag is an annotated tag object (`v1.34.2^{commit}` = `edb42fd`).

**Suggestion grid:** every SESPy sea × that sea's ecosystem types × 7
categories, crossed with:
- issue sets, as **literal strings, the same for every sea** (R matches
  with `grepl`, so the sea's `common_issues` list is irrelevant): `[]`,
  `["Overfishing"]`, `["Eutrophication"]`,
  `["Eutrophication","Overfishing"]`, `["Marine litter"]`,
  `["Tourism pressure"]` and `["Climate change"]`;
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

  Add one edge with an empty label. The fixture includes R's
  `# Regional Context` wrapper (added at `report_generation.R:174`, not by
  the formatter), so SESPy's section is compared with it. The comparison
  is after whitespace normalisation, against SESPy's section rendered to
  markdown or to an equivalent structure (builder's choice).

**Unit tests (beyond the fixtures):**
- **Layer:**
  - valid, corrupt, too small and wrong-major overrides;
  - a missing directory gives vendored data, including for a worker that
    previously had the shared copy;
  - a torn read keeps the last good copy, and the next session retries;
  - a same-size, same-mtime rewrite is detected through ctime and inode;
  - set-wise validation: one bad file means no swap;
  - two sessions keep their own snapshots across a file swap;
  - no writes;
  - transitions are logged;
  - integer and string version majors;
  - an empty `SESPY_R_DATA_DIR=` turns the override off;
  - importing `sespy.r_kb` with a vendored file missing fails.
- **Chips:** every scenario listed in §4.3, run against the real module
  with Shiny's test tooling, or as e2e where the browser round-trip is the
  point.
- **Schema and provenance:** §4.6, including:
  - the reset on project load, template load and New;
  - a callers-pass-nothing test for `to_dict()`.
- **Packaging:** a fast test asserts that
  `[tool.setuptools.package-data]` covers every allow-listed file and
  `manifest.json`. A slow-marked test builds a wheel and lists its
  contents.
- **Sync:** `build_pin` unit tests for dropped paths, regenerated warnings
  and the fixture R-tag mismatch.
- **check_live:**
  - each exit path: structural, shipped-copy mismatch, drift warning,
    `--strict`, skip variable, rollback;
  - all of them run on local fixture directories.
- **MosaicSES contract:** the §4.10 guard test.

**e2e:** a new script `tests/test_kb_wizard_e2e.py` with namespaced
selectors.
1. Choose Baltic → Coastal lagoon → 2 countries, then **skip** step 3
   with the Skip button.
2. Step 4 shows KB- and GOV-badged chips.
3. Select three chips, deselect the **middle** one, and assert the other
   two rows keep their text and order.
4. Type a chip's text by hand and see it selected.
5. Go Back to step 2 and Next again: the country order is unchanged.
6. Finish, then export a report and check that Regional Context is present.
7. About's `#about-reference-data` shows source "vendored" and "R v1.34.2".
   The runner sets `SESPY_R_DATA_DIR=`.

`test_wizard_e2e.py` is updated for country codes and optional steps 2–3.

**Gates:**
- the full unit suite;
- the full e2e run (`tests/run_e2e.py`);
- MosaicSES unit and full e2e against the branch (§3);
- the pre-flight running clean against laguna.

**Done when:**
- all gates are green;
- the pins are re-pinned and triaged (§4.9);
- `deploy.sh` runs the pre-flight;
- the CHANGELOG names K1, R v1.34.2 and the known differences;
- the MANUAL has a K1 section and the version line;
- screenshots are regenerated with `tests/make_docs_screenshots.py`;
- after deploy:
  - the worker's `python -s` reports 1.16.0;
  - a fresh live session's About shows `source=shared` labelled
    "R v1.34.2", with live R 1.34.2;
  - MosaicSES has been restarted and its `verify_live.py` passes;
- the release notes state the one-way schema-9 rollback policy (§4.10).

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
- **Header and §3 Sync tracking:** the baseline becomes v1.34.2 @ `edb42fd`.
- **§3 release line:** add "K1 = v1.16.0 (schema 9); K1b = v1.17.0".
- **K1 section:**
  - the R-source line drops `data/ses_connection_knowledge_base.R` (→ K1b)
    and `report_generation.R:481-499` (→ P14);
  - remove the extension-pair bullet (decision 1);
  - restate "Done when" as the §7 criteria: the full suggestion grid, the
    lookup, countries and report fixtures, and a pre-flight that blocks
    broken files and warns on drift;
  - pin v1.34.2, with counts 105 countries, 15 conventions and 11 seas;
  - note that `cross_ecosystem_links` are unused;
  - drop the stale "if K1 is the first schema bump, M is its prerequisite"
    sentence, since P1b made the first bump.
- **Graph and P8:** add K1 → P8 (P8 reads `wp5_scenarios_ssp` and
  `wp5_worldview_matrix` through the layer), and add K1 to P8's "Depends
  on".
- **P9:** its "Depends on" line and its "K1's KB and synonyms" bullet
  become K1 (KB) plus K1b (synonyms).
- **P5 and P6c:** they read provenance through
  `r_kb.current_provenance(...)`, not raw `metadata.reference_data`.
- **New K1b node and section** (v1.17.0, depends on K1):
  - move the `ses_connection_knowledge_base.R` / `SES_CONNECTION_DB` /
    `SES_SYNONYM_DB` export bullet into it;
  - add the edges K1b → P9, and K1b → P13 if P13's spec confirms the need;
  - in the §3 allow-list, change "export (K1)" to "(K1b)";
  - add K1b to the §3 release sequence.
- **Record that live R runs torch ML,** and that SESPy matches R run with ML
  off.
- **§3 MosaicSES:**
  - its settings file is deferred to the first sub-project whose features
    MosaicSES uses;
  - new rules for every later sub-project: the keyword-optional
    `snapshot`/`reference_reads` contract, and SESPy's deploy touching
    MosaicSES's `restart.txt` through `DEPLOY_MOSAIC_DIR` (§4.10).
- **§3 Provenance:** written per file, when read, with the merge rule
  (§4.6).
- **§3 Drift check (user decision):** the deploy pre-flight blocks only on
  broken or unreadable live files and on a shipped copy that differs from
  the pin. Content drift warns, `--strict` blocks, and
  `SESPY_SKIP_LIVE_CHECK` skips. Rollbacks are never gated (§4.8).
- **§3 Override:**
  - the settings file is re-read at every `refresh()`, not once at startup;
  - the change key is `(ino, size, mtime_ns, ctime_ns)`, not size and
    mtime;
  - "reloads on change" becomes the set-wise swap;
  - a missing directory means vendored data on every worker;
  - every transition is logged, not one warning;
  - an env var that is present, even empty, wins (§4.1).
- **§3 Drift check, mechanics:** `deploy.sh` fetches over ssh and
  `check_live.py` only hashes locally. `check_live.py --fetch` is the
  run-by-hand mode after an R deploy (§4.8).
- **P14:** add "K1's KB regional recommendation lines
  (`report_generation.R:476-509`), behind the Recommendations option". Add a
  note to row 18 of R_SYNC.md's v1.31 → v1.33 triage table (`R_SYNC.md:227`).

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
- Whether `pending` is one dict or one value per target.
