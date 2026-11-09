# K1 Knowledge-Base Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** SESPy's AI wizard, country lists and reports use R's
knowledge-base data exactly as R does, through a shared, provenance-tracked
reference-data layer. The release is SESPy v1.16.0, project schema 9.

**Architecture:** R's JSON knowledge files are vendored by the existing
sync script. A process-level registry (`sespy/r_kb.py`) can overlay
laguna's live copies, and each session pins one immutable snapshot. Pure
ports of R's lookup, suggestion and report functions read that snapshot.
The wizard gets suggestion chips (built on a pending-write overlay with
row-id generations), the Export Report page gets a Regional Context
section, and saves are stamped with per-file provenance. The deploy gets a
pre-flight check and an atomic swap.

**Tech Stack:** Python 3.11+, Shiny for Python 1.7, pytest, Playwright
(e2e), R 4.4.1 (fixture capture only), bash (`deploy.sh`), micromamba env
`shiny`.

**Spec:** `docs/superpowers/specs/2026-11-09-k1-knowledge-base-parity-design.md`
(rev 6, approved). Read it alongside this plan. Section references (§) are
to the spec.

**Reference material:** in the gitignored `.superpowers/k1-prototypes/` of
the **main checkout**.
- `kbport.py` matched R on 4,830 suggestion cells.
- `r_capture.R` and `r_report.R` are headless R capture scripts.
- `compare.py` is the comparison harness.
- `chips/app_gen.py` and `chips/drive_gen.py` are the chip prototype and its
  Playwright driver; with `CLEAR_ON_ENTRY=1 CLEAR_AFTER_WRITE=1` they pass
  28/28 scenarios.

**Never move or delete that folder.** If you work in a git worktree, read
the prototypes from the main checkout path:
`C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESPy\.superpowers\k1-prototypes\`.

## Global Constraints

- **Python** runs only through `micromamba run -n shiny python …`.
  - Never create venvs, never `pip install`.
  - Never use a multi-line `python -c` or `python - <<EOF`; write a script
    file instead.
- **Version and pins:** version `1.16.0`, `PROJECT_SCHEMA_VERSION = 9`,
  `SCHEMA_MIN_READER[9] = "1.16.0"`. The R pin is `v1.34.2`, commit
  `edb42fd`.
- **Allow-list, never a glob,** for runtime reference files:
  `ses_knowledge_db.json` and `country_governance_db.json`, both with
  version key `version`.
- **Hashing** uses only `sespy/r_sync.py::sha256_norm` and
  `sha256_text_norm`. `.gz` fixtures are hashed as
  `sha256_norm(json.loads(gzip.decompress(bytes)))`.
- **Module servers:** no K1 code reads the registry outside `app.py`'s
  `server()`. `snapshot` and `reference_reads` are **keyword-optional**
  parameters everywhere they are added.
- **R parity:** R's behaviour is reproduced exactly, quirks included (§1.1
  decision 2, §4.2). Never "fix" an R quirk in SESPy.
- **Regional Context headings** are English literals. The `modules.kb_report.*`
  i18n keys are **not** used.
- **New R i18n keys** are vendored only via `TRANSLATION_SUBSETS`:
  - from `isa_data_entry.json`, under `modules.isa.ai_assistant.`:
    `from_knowledge_database`, `governance_suggestion_tooltip`,
    `socioeconomic_suggestion_tooltip`, `tailored_for`, `eu_member_states`,
    `non_eu_countries`, `skip_this_question`;
  - from `report_context.json`: `modules.report_context.include_context`.
- **SESPy-only keys** (provenance toasts, About section labels) go in
  `sespy/translations/core.json`, inside the `"translation"` wrapper.
- **e2e selectors** are namespaced ids or the `data-row` hook. Never
  `[id$=…]`, and never a bare `text=`.
- **Gates:**
  - CI and tests use vendored data only;
  - the e2e runner sets `SESPY_R_DATA_DIR=""`;
  - the full e2e gate runs with no other heavy jobs on the machine.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  Never push without the user's say-so.

## Review Focus

1. **A legacy or unknown sea slug** in a loaded project (e.g. SP1's
   `macaronesia`, or `""`) gives generic or empty suggestions, no Regional
   Context section, and **no exception**. Tests in Tasks 6 and 14.
2. **R-imported free-text ecosystem types** (e.g. "Coastal lagoon and
   delta", "Posidonia meadows") resolve through R's regex cascade exactly
   as R does. Test in Task 6.
3. **Case and whitespace variants** of a chip's text ("trawl fishing" vs
   "Trawl fishing", a trailing space): the chip is selected only on an
   exact match after `.strip()` (case-sensitive, as R's `%in%`). A case
   variant is a separate row and is not flagged as a duplicate. Test in
   Task 13.
4. **A pipe `|` or newline** in KB rationale or references, or in a user
   label: the Regional Context evidence table stays one row per connection,
   with pipes escaped as R does. Test in Task 7.
5. **Live override files** that are present but unreadable (permissions) on
   the server: the session falls back to vendored data, logs a transition,
   and About shows "vendored". Test in Task 5.

---

### Task 0: Version bump to 1.16.0

**Files:**
- Modify: `sespy/__init__.py:3`, `pyproject.toml` (`version`), `docs/MANUAL.md` (version line)
- Test: existing `tests/test_manual.py`

**Interfaces:**
- Produces: `sespy.__version__ == "1.16.0"`.

- [ ] **Step 1: Bump the three version lines to `1.16.0`.**
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_manual.py -q`.
  Expected: PASS.
- [ ] **Step 3: Commit** `chore(k1): version 1.16.0`.

---

### Task 1: Sync script — three input kinds, `build_pin`, manifest, K1 translation keys

**Files:**
- Modify: `sespy/r_template_catalogue.py` (constants at :44-72; `sync` at :296-408)
- Test: `tests/test_r_template_catalogue.py`, plus a new `tests/test_k1_sync.py`

**Interfaces:**
- Produces:
  - `RUNTIME_INPUTS: dict[str, str]` = `{"data/ses_knowledge_db.json":
    "sespy/data/r_kb/ses_knowledge_db.json", "data/country_governance_db.json":
    "sespy/data/r_kb/country_governance_db.json"}`
  - `MANIFEST_PATH = "sespy/data/r_kb/manifest.json"`
  - `LOCAL_PINS: tuple[str, ...]`, the five paths
    `tests/parity/r_fixtures/k1/{lookup,suggestions_grid,habitat_specific,countries,report}.json.gz`
  - `K1_R_SOURCES = ("functions/ses_knowledge_db_loader.R",
    "modules/ai_isa_knowledge_base.R", "functions/country_governance_loader.R",
    "functions/kb_report_helpers.R", "functions/report_generation.R")`.
    These go into `INPUTS` → `tests/parity/r_source/<basename>`.
  - `TRANSLATION_SUBSETS` gains `"isa_data_entry": ("modules.isa.ai_assistant.from_knowledge_database",
    "modules.isa.ai_assistant.governance_suggestion_tooltip",
    "modules.isa.ai_assistant.socioeconomic_suggestion_tooltip",
    "modules.isa.ai_assistant.tailored_for",
    "modules.isa.ai_assistant.eu_member_states",
    "modules.isa.ai_assistant.non_eu_countries",
    "modules.isa.ai_assistant.skip_this_question")` and
    `"report_context": ("modules.report_context.include_context",)`.
  - `build_manifest(r_tag: str, r_commit: str, runtime_hashes: dict[str, str]) -> bytes`.
    It returns `{"r_tag", "r_commit", "files": {basename: sha256_norm}}`,
    indent=2, LF, newline-terminated.
  - `hash_local_pin(path: Path) -> str`, using the gz rule from Global
    Constraints.
  - `fixture_r_tag(path: Path) -> str`, the top-level `r_tag` of a gunzipped
    fixture.
  - `build_pin(pin_old: dict, files_new: dict[str, str], warnings_new: list[dict],
    *, r_tag: str, r_commit: str, removed_inputs: frozenset[str] = frozenset()) -> dict`.
    It raises `ValueError` listing the paths in
    `set(pin_old["files"]) - set(files_new) - removed_inputs`.

- [ ] **Step 1: Write failing tests** in `tests/test_k1_sync.py`:

```python
def test_build_pin_fails_on_dropped_path():
    old = {"r_tag": "v1.33.0", "r_commit": "4017feb",
           "files": {"a": "1", "b": "2"}, "accepted_warnings": []}
    with pytest.raises(ValueError, match="b"):
        build_pin(old, {"a": "1"}, [], r_tag="v1.34.2", r_commit="edb42fd")

def test_build_pin_allows_declared_removal():
    old = {"r_tag": "v1.33.0", "r_commit": "x", "files": {"a": "1", "b": "2"},
           "accepted_warnings": []}
    pin = build_pin(old, {"a": "1"}, [], r_tag="v1.34.2", r_commit="edb42fd",
                    removed_inputs=frozenset({"b"}))
    assert pin["files"] == {"a": "1"} and pin["r_tag"] == "v1.34.2"

def test_build_pin_regenerates_warnings():
    old = {"r_tag": "v", "r_commit": "c", "files": {}, "accepted_warnings": [{"kind": "stale"}]}
    assert build_pin(old, {}, [], r_tag="v1.34.2", r_commit="c")["accepted_warnings"] == []

def test_gz_hash_ignores_gzip_mtime(tmp_path):
    # two gzips of the same JSON with different mtime → same hash
    ...
    assert hash_local_pin(p1) == hash_local_pin(p2)

def test_manifest_shape():
    m = json.loads(build_manifest("v1.34.2", "edb42fd", {"sespy/data/r_kb/ses_knowledge_db.json": "h1"}))
    assert m == {"r_tag": "v1.34.2", "r_commit": "edb42fd", "files": {"ses_knowledge_db.json": "h1"}}

def test_fixture_tag_mismatch_is_reported(tmp_path): ...   # sync returns code 1 naming the fixture
```

- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_k1_sync.py -q`.
  Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** the constants and functions above.
  - Rewire `sync` so that:
    - in git mode, `RUNTIME_INPUTS` are fetched like `INPUTS` (same
      `{prefix}{r_path}` form) and written to their targets;
    - `files` = hashes of `INPUTS` fixtures + `RUNTIME_INPUTS` targets +
      `MANIFEST_PATH` + `LOCAL_PINS`;
    - the pin goes through `build_pin`;
    - a `LOCAL_PINS` fixture whose `fixture_r_tag` ≠ the target `r_tag` is
      an error;
    - in `--from-fixtures` mode, `RUNTIME_INPUTS` are read from their
      vendored targets and the manifest is rebuilt and compared.
  - `.gz` paths never go through `_hash` or `_same`.
  - `--check` compares the rebuilt manifest, the vendored outputs and the
    local-pin hashes with disk.
- [ ] **Step 4: Update the two hard-coded counts.**
  - `tests/parity/test_r_sync.py:27` and `tests/test_r_template_catalogue.py:406`
    assert the new total: 18 + 5 R sources + 2 translations + 2 runtime + 1
    manifest + 5 local = **33**.
  - The `sorted(pin["files"]) == sorted(INPUTS.values())` assertion becomes
    the union of all kinds.
  - **Do not run these yet:** they go green in Task 3.
- [ ] **Step 5: Run** `micromamba run -n shiny python -m pytest tests/test_k1_sync.py -q`.
  Expected: PASS.
- [ ] **Step 6: Commit** `feat(k1): sync script vendors KB data, pins fixtures and manifest`.

---

### Task 2: R fixture capture script and the five fixtures

**Files:**
- Create: `scripts/capture_k1_fixtures.R`, `tests/parity/k1_fixtures.py`, `tests/parity/r_fixtures/k1/*.json.gz` (5)
- Test: `tests/parity/test_k1_fixture_shape.py`

**Interfaces:**
- Produces:
  - `load_k1_fixture(name: str) -> dict`, which returns the fixture's
    `data` (names: `lookup`, `suggestions_grid`, `habitat_specific`,
    `countries`, `report`);
  - `K1_FIXTURE_TAG = "v1.34.2"`.
- **Fixture shapes** (each file is `{"r_tag", "r_commit", "data"}`):
  - `lookup`: `[{sea, ecosystem, key, match}]` for all 69 SESPy choices.
    `match` is one of `exact | prefix | sea_only | fallback`.
  - `suggestions_grid`: `{"sources": {list_id: [names…]}, "cells":
    [{sea, ecosystem, category, issues, countries, items: [[name, source]…]}]}`.
  - `habitat_specific`: `[{sea, ecosystem, category, items}]`.
  - `countries`: `{sea: [{code, name_en, eu_member}]}` for the 11 seas.
  - `report`: `{case_id: markdown}` for `baltic_lagoon`, `med_seagrass`
    and `irish_sea`.

- [ ] **Step 1: Write the failing shape test.** For each of the 5 names,
  `load_k1_fixture` returns non-empty data; the tag is `v1.34.2`;
  `len(lookup) == 69`. The grid covers every (sea, ecosystem) of
  `sespy/regional_seas.json` × the 7 categories × 7 issue sets × the
  country sets of §7.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/parity/test_k1_fixture_shape.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Write `scripts/capture_k1_fixtures.R`** from
  `.superpowers/k1-prototypes/r_capture.R` and `r_report.R`.
  - **Guards:** fail unless the R working tree is clean and
    `git describe --tags` equals `v1.34.2`.
  - **Setup:** `setwd(<R app>)`; stub `debug_log <- function(...) invisible(NULL)`;
    define `%||%` if missing; force `Sys.setenv(MARINESABRES_ML_ENABLED="FALSE")`.
  - **Sources:** `modules/ai_isa_knowledge_base.R`,
    `functions/ses_knowledge_db_loader.R`,
    `functions/country_governance_loader.R` and
    `functions/kb_report_helpers.R`.
  - **Issue sets:** exactly `list(character(0), "Overfishing",
    "Eutrophication", c("Eutrophication","Overfishing"), "Marine litter",
    "Tourism pressure", "Climate change")`.
  - **Country sets per sea:** `character(0)`, the first two codes of
    `countries_by_sea[[sea]]` in both orders, and one fixed set covering
    all 6 governance groups, all 3 income levels and all 15 conventions.
    Choose it with a small greedy pick in the script, then hard-code it in
    the script for reproducibility.
  - **Report cases** (built in the script, matching §7):
    - `baltic_lagoon`: 6 elements, 5 connections, 2 of them matching KB
      edges, plus 1 edge with an empty label;
    - `med_seagrass`: elements only;
    - `irish_sea`.

    Each output is `paste0("# Regional Context\n\n",
    format_kb_section_for_report(kb, matched, gov))`.
  - **Output:** write gzipped JSON to `tests/parity/r_fixtures/k1/`.
- [ ] **Step 4: Run it** with
  `"C:\Program Files\R\R-4.4.1\bin\Rscript.exe" scripts/capture_k1_fixtures.R "<R app path>"`.
  Expected: 5 files written, in about 90 s. Then run `attrib +P` on
  `tests/parity/r_fixtures`.
- [ ] **Step 5: Write `tests/parity/k1_fixtures.py`;** run the shape test.
  Expected: PASS.
- [ ] **Step 6: Add `*.gz binary`** to `.gitattributes` (create the file if
  absent), then commit `test(k1): R v1.34.2 knowledge-base fixtures`.

---

### Task 3: Re-pin to R v1.34.2 and triage

**Files:**
- Modify (generated by sync): `tests/parity/r_sync.json`, `docs/parity/R_SYNC.md`, `tests/parity/r_source/*`, `tests/parity/r_translations/*`, `sespy/translations/modules/{isa_data_entry,report_context}.json`, `sespy/data/r_kb/*`
- Modify by hand: `docs/parity/R_SYNC.md` (triage table)

**Interfaces:**
- Consumes: Task 1's `sync`, Task 2's fixtures.
- Produces: vendored `sespy/data/r_kb/{ses_knowledge_db,country_governance_db,manifest}.json`.

- [ ] **Step 1: Run** `micromamba run -n shiny python -m scripts.sync_r_templates --r-root "<R app path>" --rev v1.34.2`.
  Expected: exit 0, with `wrote …` for every vendored file and the pin.
  - If template warnings appear, review them; rerun with
    `--accept-warnings` only if they match the R changes.
- [ ] **Step 2: Triage.** Add a "v1.33.0 → v1.34.2" table to `R_SYNC.md`
  with one row per path of `git diff --stat v1.33.0 v1.34.2` (44 rows).
  - Format: as P1b's table.
  - Rows that need notes: `modules/ai_isa_assistant_module.R` (badge
    tooltip fix), `translations/modules/isa_data_entry.json`,
    `modules/ai_isa/ui_renderers.R`, and `constants.R` (owned by P4/PIMS,
    and P1b's fixture hash moves).
- [ ] **Step 3: Run** `micromamba run -n shiny python -m pytest tests/parity tests/test_r_template_catalogue.py tests/test_k1_sync.py -q`.
  Expected: PASS, including the P1b parity tests against the new
  `constants.R`.
- [ ] **Step 4: Run** `micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures --check`.
  Expected: exit 0.
- [ ] **Step 5: Pin the vendored data locally** against OneDrive
  dehydration (spec §4.10): `attrib +P "sespy\data\r_kb\*" /S`.
- [ ] **Step 6: Commit** `chore(k1): re-pin R v1.34.2 (edb42fd), triage 44 paths`.

---

### Task 4: `sespy/r_kb.py` — allow-list, vendored load, snapshot types, packaging

**Files:**
- Create: `sespy/r_kb.py`
- Modify: `pyproject.toml` (`[tool.setuptools.package-data]` gains `"data/r_kb/*.json"`)
- Test: `tests/test_r_kb.py`

**Interfaces:**
- Produces:
  - `AllowRow(name: str, required_keys: tuple[str, ...], min_counts: dict[str, int],
    version_key: str, override: bool)`.
  - `ALLOW_LIST: tuple[AllowRow, ...]`, holding the two rows of spec §4.1.
    Required keys:
    - KB: `version`, `contexts`, `generic_fallback`, `cross_ecosystem_links`;
    - governance: `version`, `description`, `countries_by_sea`, `countries`,
      `governance_elements`, `socioeconomic_elements`, `regional_conventions`.
  - `version_major(value: int | str) -> int`.
  - `validate(row: AllowRow, data: Any, vendored_major: int) -> str | None`,
    returning None when valid, else a reason.
  - `Entry(data: Any, sha256_norm: str, source: Literal["vendored","shared"],
    version: str)`, a frozen dataclass, with
    `provenance(vendored_r_tag: str) -> dict`, which returns exactly
    `{source, sha256_norm, version, vendored_r_tag}`.
  - `Snapshot(files: Mapping[str, Entry], taken_at: float, manifest: dict,
    live_r_version: str | None)`, frozen, with:
    - `get(name) -> Any` (the data);
    - `kb()`;
    - `governance()`;
    - `provenance(name) -> dict`;
    - `label(name) -> str`, returning "R v1.34.2" or
      "shared, differs from R v1.34.2".
  - `VENDORED: Snapshot`, built **at import**. A missing or invalid
    vendored file raises `RuntimeError` naming it.

- [ ] **Step 1: Write failing tests:**
  - `test_vendored_snapshot_loads` (both files, source "vendored", hashes
    equal the manifest);
  - `test_version_major_int_and_string` (`2 → 2`, `"1.0" → 1`);
  - `test_validate_rejects_missing_key_and_small_count`;
  - `test_provenance_has_no_data_key`;
  - `test_label_vendored`, which asserts `VENDORED.label("ses_knowledge_db.json") == "R v1.34.2"`;
  - `test_package_data_covers_allow_list`: parse `pyproject.toml` and
    assert the glob covers every allow-list name and `manifest.json`;
  - `test_import_fails_without_vendored_file`: run in a subprocess with a
    temp copy of `sespy/` missing one file, and expect a non-zero exit.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_r_kb.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the interfaces above in `sespy/r_kb.py`. Read
  the files with `importlib.resources` relative to the package; nothing
  relative to `APP_DIR`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Add a slow-marked test** `test_wheel_contains_r_kb`, which
  builds a wheel into `tmp_path` and lists its contents. Register the
  marker if it is absent. Run
  `micromamba run -n shiny python -m pytest tests/test_r_kb.py -m slow -q`.
  Expected: PASS.
- [ ] **Step 6: Commit** `feat(k1): reference-data allow-list and vendored snapshot`.

---

### Task 5: Registry — override, settings file, change detection, fallback

**Files:**
- Modify: `sespy/r_kb.py`
- Test: `tests/test_r_kb_registry.py`

**Interfaces:**
- Consumes: Task 4's types.
- Produces:
  - `configure(app_dir: Path) -> None`;
  - `refresh() -> None`;
  - `current() -> Snapshot`;
  - `hashes_for_load_check(name) -> tuple[str, str | None]`, returning
    `(vendored_hash, last_parsed_shared_hash)`.
- **Behaviour:** spec §4.1.
  - **Env precedence:** if `"SESPY_R_DATA_DIR" in os.environ` (even empty),
    it wins; else read `app_dir/server_settings.env` at every `refresh()`.
    An empty value turns the override off.
  - **Change key:** `(st_ino, st_size, st_mtime_ns, st_ctime_ns)` per
    override file.
  - **Swap:** parse and validate **all** override files; swap only if all
    pass.
  - **Missing or unreadable directory:** vendored on this worker, even if
    it previously had shared data.
  - **A missing or invalid file in a present directory:** keep last good,
    else vendored.
  - A failure is never recorded as seen.
  - **Live R version:** read `<dir>/../VERSION_INFO.json` optionally.
  - **Logging:** each transition at WARNING: `r_kb.transition file=<f>
    from=<src> to=<src> reason=<r> hash=<h8>`.
  - **No writes**, ever.

- [ ] **Step 1: Write failing tests,** all with `tmp_path` and monkeypatched
  env:
  - `test_override_valid_becomes_shared`;
  - `test_env_present_empty_disables_file` (write a settings file, set env
    `""`, and the source stays vendored);
  - `test_settings_file_reread_each_refresh`;
  - `test_corrupt_keeps_last_good_then_retries`;
  - `test_too_small_and_wrong_major_rejected`;
  - `test_one_bad_file_means_no_swap` (KB new + governance corrupt → both
    stay old);
  - `test_missing_dir_goes_vendored_even_after_shared`;
  - `test_unreadable_dir_goes_vendored` (Review Focus 5; skip on Windows
    if chmod is ineffective, and also simulate with a monkeypatched
    `os.stat` raising `PermissionError`);
  - `test_same_size_same_mtime_rewrite_detected` (set the mtime back with
    `os.utime`, and assert the swap through ctime/inode);
  - `test_two_sessions_keep_their_snapshots` (`a = current()`, swap the
    file, `refresh()`, `b = current()`, then `a.kb() != b.kb()` and `a` is
    unchanged);
  - `test_never_writes` (snapshot the directory's mtimes and file list
    before and after);
  - `test_transition_logged` (caplog contains `r_kb.transition`).
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_r_kb_registry.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** in `sespy/r_kb.py`: a module-level `_Registry`
  instance behind `configure`, `refresh` and `current`, with snapshot
  replacement by plain attribute assignment.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): reference-data registry with live override and safe fallback`.

---

### Task 6: `sespy/kb_suggestions.py` — lookup and suggestions

**Files:**
- Create: `sespy/kb_suggestions.py`
- Test: `tests/test_kb_suggestions.py`

**Interfaces:**
- Consumes: plain dicts (`snapshot.kb()`, `snapshot.governance()`); no
  snapshot import.
- Produces:
  - `build_context_key(sea: str | None, habitat: str | None) -> str | None`.
  - `find_context(kb: dict, sea, habitat) -> tuple[str, dict, str] | None`,
    returning `(key, context, match)` with `match` one of `exact | prefix |
    sea_only`.
  - `get_context_elements(kb, sea, habitat, category, min_relevance=0.0) -> list[str]`.
  - `get_context_connections(kb, sea, habitat) -> list[dict]`.
  - `deduplicate_suggestions(items: list[str]) -> list[str]`.
  - `get_habitat_specific_suggestions(category, sea, ecosystem) -> list[str]`.
  - `get_governance_elements(gov: dict, codes: list[str], category: str) -> list[str]`.
  - `get_socioeconomic_elements(gov, codes, category) -> list[str]`.
  - `countries_for_sea(gov, sea) -> list[dict]`, where each item is
    `{code, name_en, eu_member}` in `countries_by_sea` order.
  - `get_context_suggestions(kb, gov, category, sea, ecosystem,
    main_issue: list[str], countries: list[str]) -> list[tuple[str, str]]`,
    returning `(name, source)` pairs. `source` is one of `knowledge_db,
    governance, socioeconomic, regional, issue, ecosystem, habitat,
    generic`.
- **Algorithm:** port from `.superpowers/k1-prototypes/kbport.py`, which
  already matches R. Every trap in spec §4.2 applies:
  - `re.split(r"\s+", …)`;
  - the single-pass suffix strip;
  - `intersect` uniqueness against a duplicate-counting denominator;
  - JSON file order;
  - a stable descending sort;
  - "any issue matches" in R's branch order;
  - an unmapped governance category returns `[]`;
  - codes are upper-cased.

- [ ] **Step 1: Write failing fixture-driven tests:**
  - `test_lookup_matches_r` over `load_k1_fixture("lookup")`: key and match
    for all 69 rows;
  - `test_suggestions_grid_matches_r` over every grid cell, comparing full
    ordered `[[name, source]]`;
  - `test_habitat_specific_matches_r`;
  - `test_countries_for_sea_matches_r`;
  - `test_decision2_quirks_named`, a table of 5 named cases from §1.1(2):
    Pacific Coral reef → `pacific_island_atoll`; Indian Island →
    `indian_ocean_coral_reef`; Atlantic Coastal upwelling →
    `atlantic_open_coast` exact; Irish Sea → None; North Sea Sandy beach →
    `north_sea_offshore`;
  - `test_legacy_sea_slug_no_exception`: `"macaronesia"` and `""` give
    generic-fallback items and `find_context(...) is None` (Review Focus 1);
  - `test_free_text_ecosystems`: "Coastal lagoon and delta" →
    `<sea>_lagoon`; "Posidonia meadows" → `mediterranean_seagrass`;
    "Schären archipelago" → `baltic_rocky_coast` (Review Focus 2). Add the
    exact expected keys to the R capture as a 6th mini-table if the 3
    cases are not covered, or assert them against the cascade order and
    note that in a comment.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_kb_suggestions.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the interfaces.
- [ ] **Step 4: Run the tests.** Expected: PASS (all grid cells).
- [ ] **Step 5: Commit** `feat(k1): R-exact knowledge-base lookup and suggestions`.

---

### Task 7: `sespy/kb_report.py` — Regional Context content

**Files:**
- Create: `sespy/kb_report.py`
- Test: `tests/test_kb_report.py`

**Interfaces:**
- Consumes: `find_context`, `get_context_elements` and
  `get_context_connections` (Task 6).
- Produces:
  - `RegionalContext(site_description: str | None, top_elements:
    list[tuple[str, list[str]]], evidence: list[EvidenceRow],
    frameworks: list[str], country_groups: list[tuple[str, str]])`.
  - `EvidenceRow(connection: str, rationale: str, references: str,
    temporal_lag: str, reversibility: str)`.
  - `build_regional_context(kb, gov, sea, ecosystem, edges:
    list[tuple[str, str]]) -> RegionalContext | None`. It returns None when
    there is no content (R :173-175).
  - `to_markdown(rc: RegionalContext) -> str`, R's exact markdown,
    beginning with `# Regional Context`.
  - `CATEGORY_LABELS`, R's literals ("Drivers (D)" …).
  - `HEADINGS`, R's six heading texts.
- **R behaviours:**
  - relevance ≥ 0.8;
  - KB names of 2 characters or fewer are skipped;
  - the first KB match wins;
  - an empty user label matches everything;
  - `|` is escaped as `\|` in rationale and references;
  - references are joined with `"; "`.

- [ ] **Step 1: Write failing tests:**
  - `test_report_markdown_matches_r` for the 3 cases of
    `load_k1_fixture("report")`, after whitespace normalisation;
  - `test_irish_sea_governance_only` (`site_description is None`,
    frameworks non-empty);
  - `test_empty_label_matches_all`;
  - `test_pipe_and_newline_in_rationale_escaped`: a KB connection whose
    rationale has `|` and `\n` renders as one table row with `\|`
    (Review Focus 4);
  - `test_no_content_returns_none` (sea `"other"`).
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_kb_report.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** by porting `kb_report_helpers.R:42-369`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): Regional Context report content, R-exact`.

---

### Task 8: Schema 9 — `reference_data` field and template regeneration

**Files:**
- Modify: `sespy/data_structure.py` (:22, :27, `ProjectMetadata` :283-303, `Project.from_dict` :584-)
- Regenerate: `sespy/templates/marinesabres/*.json` (7) via sync
- Test: create `tests/test_schema_v9.py`; update `tests/test_data_structure.py`, `tests/test_schema_v7.py` and `tests/test_r_template_catalogue.py` where they pin 8

**Interfaces:**
- Produces:
  - `PROJECT_SCHEMA_VERSION = 9`;
  - `SCHEMA_MIN_READER[9] = "1.16.0"`;
  - `ProjectMetadata.reference_data: dict = field(default_factory=dict,
    kw_only=True)`.
- **`from_dict`:** keep `reference_data` only if it is a `dict` whose
  values are all `dict`s; otherwise drop it with a `_log.warning`.

- [ ] **Step 1: Write failing tests** in `tests/test_schema_v9.py`:
  - `test_roundtrip_reference_data`;
  - `test_malformed_reference_data_dropped_with_warning` (a list, and a
    dict with a non-dict value);
  - `test_save_stamps_1_16_0_even_when_empty`;
  - `test_v8_reader_drops_field`: simulate the pre-K1 unknown-key filter by
    deleting the field from the valid keys, and assert load succeeds.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_schema_v9.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the field and the schema constants.
  - Grep `tests/` for `PROJECT_SCHEMA_VERSION`, `== 8` and `"1.15.0"`, and
    update every schema pin.
- [ ] **Step 4: Regenerate templates** with
  `micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures`.
  Expected: the 7 template files change (gaining `reference_data: {}` and
  the 1.16.0 stamp); nothing else changes.
- [ ] **Step 5: Run** `micromamba run -n shiny python -m pytest tests -q -k "not e2e" -p no:cacheprovider`.
  Expected: PASS.
- [ ] **Step 6: Commit** `feat(k1): project schema 9 with reference_data` (one commit, with the templates).

---

### Task 9: Serialisation threading and `current_provenance`

**Files:**
- Modify: `sespy/data_structure.py` (`Project.to_dict`/`to_json` :555-582), `sespy/persistent_storage.py` (:144, :183), `sespy/autosave.py` (:87), `sespy/r_kb.py`
- Test: `tests/test_provenance.py`

**Interfaces:**
- Consumes: Task 4's `Snapshot.provenance` and Task 8's field.
- Produces:
  - `Project.to_dict(*, reference_data: dict | None = None)` and
    `to_json(*, indent=2, reference_data=None)`. `None` writes
    `metadata.reference_data` as is; a dict replaces it **in the output
    only**.
  - `save_project_atomic(project, path, *, reference_data=None)`.
  - `project_to_bytes(project, *, reference_data=None)`.
  - `write_autosave(project_or_isa, *, token, reference_data=None)`.
  - `r_kb.current_provenance(meta: ProjectMetadata, snapshot: Snapshot,
    reads: frozenset[str]) -> dict`, returning
    `{**meta.reference_data, **{f: snapshot.provenance(f) for f in reads}}`.

- [ ] **Step 1: Write failing tests:**
  - `test_to_dict_default_unchanged` (no kwarg → identical to Task 8's
    output);
  - `test_overlay_in_output_only` (the project object is unchanged
    afterwards);
  - `test_merge_keeps_unread_loaded_entries`;
  - `test_merge_replaces_read_entries`;
  - `test_saved_file_has_no_data_key_and_is_small` (<50 KB with both
    files read);
  - `test_callers_pass_nothing` (`Project.to_dict()` and
    `r_template_catalogue` `to_json()` work unchanged);
  - `test_autosave_overlay_written`.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_provenance.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the keyword threading and `current_provenance`.
- [ ] **Step 4: Run** the new tests plus `tests/test_persistent_storage.py`
  and `tests/test_autosave.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): provenance stamped at serialisation`.

---

### Task 10: `app.py` wiring — snapshot, `reference_reads`, resets, load check

**Files:**
- Modify: `app.py` (:173-320), `sespy/modules/project_io.py` (`quick_actions_server` :103; autosave :142-161; save :292-318; New :381-384), `sespy/modules/templates.py` (only to confirm `template_loaded` exists; no change expected), `sespy/translations/core.json`
- Test: `tests/test_k1_wiring.py` (Shiny test tooling; see `shiny skills path` → `references/testing.md`)

**Interfaces:**
- Consumes: Tasks 5 and 9.
- Produces:
  - In `server()`: `r_kb.refresh(); snapshot = r_kb.current();
    reference_reads = reactive.value(frozenset())`.
  - `r_kb.configure(Path(__file__).parent)` is called once at `app.py`
    import.
  - `add_reads(reads: reactive.Value[frozenset[str]], names: Iterable[str])
    -> None` in `sespy/r_kb.py`. It reads under `isolate()` and calls
    `set` only if a name is new.
  - `quick_actions_server(..., snapshot: Snapshot | None = None,
    reference_reads: reactive.Value[frozenset[str]] | None = None)`. Save
    and autosave pass `reference_data=current_provenance(...)`. Autosave
    reads `reference_reads` under `isolate()`.
  - **Reset:** `reference_reads.set(frozenset())` on
    `event_bus.project_loaded`, `event_bus.template_loaded` and in `_on_new`.
  - **Load check:** in the same effect family as `_newer_build_warning`
    (`project_io.py:242-269`). For each entry it compares with
    `snapshot.files[f].sha256_norm` and `r_kb.hashes_for_load_check(f)`,
    and toasts `core.json` keys `kb.provenance_differs` and
    `kb.provenance_unavailable`. The text is in §4.6; show
    `vendored_r_tag`; ignore entries without `sha256_norm`.

- [ ] **Step 1: Write failing tests:**
  - `test_reads_reset_on_project_loaded`, `test_reads_reset_on_template_loaded`,
    `test_reads_reset_on_new`;
  - `test_add_reads_no_self_invalidation` (inside a render, `add_reads`
    twice with the same name → one invalidation);
  - `test_toast_differs_and_unavailable` (feed a project with a foreign
    hash and with the vendored hash under a shared snapshot);
  - `test_autosave_includes_reads_after_isa_change`.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_k1_wiring.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the wiring. Pass `snapshot` to the wizard,
  report export, `quick_actions_server` and `topbar_actions_server`, and
  `reference_reads` to the first three. Tasks 11, 14 and 15 add the
  parameters on the receiving side; here add them as accepted-but-unused
  keyword-optional parameters.
- [ ] **Step 4: Run** the tests plus `tests/test_autosave.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): session snapshot, reference reads and provenance toasts`.

---

### Task 11: Country step and skippable steps 2–3

**Files:**
- Modify: `sespy/wizard.py`, `sespy/modules/ai_isa_wizard.py` (`_render_choice_many` :107-128; `_on_next` :510-668; `_assemble_wizard_state` :670), `sespy/data_structure.py` (`WizardState` :763-772), `sespy/claude_backend.py:313`, `sespy/regional_seas.json`, `sespy/regional_seas.py`, `tests/test_regional_seas.py`, `tests/test_wizard.py`
- Test: `tests/test_wizard_countries.py`

**Interfaces:**
- Consumes: `countries_for_sea` (Task 6), `snapshot` (Task 10), `add_reads`.
- Produces:
  - `ai_isa_wizard_server(..., snapshot=None, reference_reads=None)`. With
    `snapshot=None` it uses `r_kb.VENDORED`, which keeps MosaicSES and the
    tests working.
  - `WizardState.country_names: list[str] = field(default_factory=list)`.
  - `country_names_for(gov: dict, codes: list[str]) -> list[str]` in
    `sespy/kb_suggestions.py`.
  - The step-2 selectize has optgroups `eu_member_states` and
    `non_eu_countries` (R keys). Option values are codes; labels are
    `name_en`.
  - A Skip button `skip_{target}` on steps 2 and 3, labelled
    `modules.isa.ai_assistant.skip_this_question`, records `[]` and
    advances.
  - Empty Next is accepted on steps 2 and 3.
  - **Sea change:** `_on_next` for step 0 filters
    `wizard_answers["countries"]` to the new sea's codes.
  - `claude_backend.py:313` joins `state.country_names`.
  - `regional_seas.json` loses `countries`, `country_codes` and
    `eu_member_codes`; `get_eu_member_codes` is deleted along with its
    tests.

- [ ] **Step 1: Write failing tests:**
  - `test_country_choices_from_governance` (Pacific has FM and no CN;
    Caribbean has 27);
  - `test_values_are_codes_and_names_resolved`;
  - `test_empty_next_allowed_on_steps_2_3`;
  - `test_skip_button_records_empty`;
  - `test_sea_change_filters_codes`;
  - `test_claude_prompt_uses_names`;
  - `test_country_order_kept` (selection order passed through to
    `WizardState.countries`).
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_wizard_countries.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Check country order after Back in a browser.**
  - Start the app (`micromamba run -n shiny python -m shiny run --port 8771 app.py`).
  - Pick two countries in reverse option order, go Next, then Back, then
    Next.
  - If the order comes back in option order, restore the saved order by
    emitting the selected codes first, in saved order, in
    `_render_choice_many`, and add `test_back_preserves_country_order`.
  - Kill the server on 8771.
- [ ] **Step 5: Run** the new tests plus `tests/test_wizard.py` and
  `tests/test_regional_seas.py`. Expected: PASS.
- [ ] **Step 6: Commit** `feat(k1): wizard countries from R governance data; steps 2-3 skippable`.

---

### Task 12: Pending overlay and row-id generations (no chips yet)

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` (`_render_freeform_multiple` :131-194; Add/Remove :487-508; `_on_next` freeform read :540-564 and write :654-663; `_on_modal_replace` :453-475; `_on_back` :821; `wizard_step_render` :977)
- Test: `tests/test_wizard_overlay.py`

**Interfaces:**
- Produces:
  - Module-local `pending: reactive.Value[dict[str, dict[int, str]]]` and
    `gen: reactive.Value[dict[str, int]]`.
  - Row ids are `entry_{gen}_{target}_{i}`. Each row input has the
    attribute `data-row="{target}_{i}"`.
  - `effective_rows(target) -> list[tuple[bool, str]]` (exists, value).
    Value is pending, else live-if-exists, else saved.
  - `row_count(target) -> int`, defined in §4.3.
  - **Lifetime rules** (§4.3, rev 6):
    - clear `pending[target]` **after a successful write** in `_on_next`;
    - drop `pending[target]` on every `gen[target]` bump (step entry and
      Replace);
    - Remove drops indices at or above the new count;
    - Add tombstones a stale live index.
  - `_render_freeform_multiple` reads `pending` and live inputs under
    `isolate()`, and `answers` and counts reactively.
- **Port from** `.superpowers/k1-prototypes/chips/app_gen.py` (the
  `CLEAR_ON_ENTRY` and `CLEAR_AFTER_WRITE` branches on).

- [ ] **Step 1: Write failing tests** (Shiny test tooling, driving inputs
  and buttons):
  - `test_back_deselect_add_stays_blank` (via pending `""`);
  - `test_remove_then_add_no_stale_text`;
  - `test_replace_then_reenter_blank`;
  - `test_failed_next_keeps_pending_row`;
  - `test_back_next_idempotent`;
  - `test_unsaved_text_discarded_by_back` (documents the behaviour change).
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_wizard_overlay.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new tests plus `tests/test_wizard.py`. Expected: PASS.
- [ ] **Step 5: Commit** `refactor(k1): wizard rows use a pending overlay and per-visit ids`.

---

### Task 13: Suggestion chips

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py`, `sespy/www/` (chip CSS if needed)
- Test: `tests/test_wizard_chips.py`

**Interfaces:**
- Consumes: `get_context_suggestions` (Task 6), Task 12's overlay,
  `add_reads`, `snapshot`.
- Produces:
  - Output `chips_{target}` (`@render.ui`) rendering up to 12 chips
    `chip_{target}_{i}`. Each shows `name` plus a badge span with class
    `kb-badge kb-badge-{KB|GOV|SE}` for sources `knowledge_db`,
    `governance` and `socioeconomic`. The tooltip uses R's keys. A
    selected chip has class `chip-on`, others `chip-off`.
  - A caption ` (Tailored for <translated sea name> - <ecosystem>)`
    (R key `tailored_for`), shown when a sea is set.
  - 7 × 12 handlers registered once. They recompute the list at click
    time, do nothing past its end, and do nothing if the target is not the
    current step.
  - Select and deselect follow rules 4 and 5.
  - Computing suggestions calls `add_reads(reference_reads,
    {"ses_knowledge_db.json", "country_governance_db.json"})`.

- [ ] **Step 1: Write failing tests:**
  - `test_chips_match_r_first_12` (Baltic lagoon, drivers, 2 codes: equals
    the first 12 of the Task 6 output);
  - `test_select_fills_first_empty_then_adds_row`;
  - `test_deselect_blanks_all_matches_in_place`;
  - `test_hand_typed_text_selects_chip_including_trailing_space`;
  - `test_case_variant_is_distinct` (Review Focus 3);
  - `test_two_different_chips_same_flush`;
  - `test_chip_then_next_same_flush`;
  - `test_chip_for_other_target_ignored`;
  - `test_reads_recorded_once`.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_wizard_chips.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Replay the prototype driver's scenario list** against the
  real app. Adapt `chips/drive_gen.py` into a throwaway script in the
  session scratchpad, run it on port 8772, and kill the server afterwards.
  Expected: all scenarios pass.
- [ ] **Step 5: Run** the tests plus `tests/test_wizard.py`. Expected: PASS.
- [ ] **Step 6: Commit** `feat(k1): knowledge-base suggestion chips in wizard steps 4-10`.

---

### Task 14: Regional Context in HTML, PDF and Word; the toggle

**Files:**
- Modify: `sespy/report.py` (CSS :44-50; template after :100; `_build_context` :182; `render_html/pdf/docx` :236/243/263), `sespy/modules/report_export.py` (:20-110)
- Test: `tests/test_report.py`, plus a new `tests/test_report_regional.py`

**Interfaces:**
- Consumes: `build_regional_context` (Task 7), `add_reads`, `snapshot`.
- Produces:
  - `render_html(project, *, snapshot=None, include_regional_context=False)`;
    the same signature for `render_pdf` and `render_docx`.
  - The section renders only if `include_regional_context`, `snapshot`,
    and non-empty `regional_sea` and `ecosystem_type` are all present, and
    `build_regional_context(...)` is not None.
  - **HTML:** `<h2>Regional Context</h2>`, then h3–h5 for R's levels, with
    h4 and h5 CSS added. **Word:** Heading 2–5 and a 5-column table.
  - **Edges:** `isa_data.connections` in list order, ids mapped to labels.
  - A checkbox `report_export-include_regional_context` (label key
    `modules.report_context.include_context`), default `True`.
  - The preview depends on it.
  - Generating the section calls `add_reads`.
  - A failure omits the section with a WARNING log.

- [ ] **Step 1: Write failing tests:**
  - `test_html_section_present_baltic`;
  - `test_section_absent_when_sea_empty` and
    `test_section_absent_for_legacy_slug` (Review Focus 1);
  - `test_irish_sea_governance_only_html`;
  - `test_docx_has_heading_levels_and_table`;
  - `test_defaults_keep_old_output` (`render_html(project)` is identical to
    the pre-K1 output);
  - `test_generation_error_omits_section` (monkeypatch
    `build_regional_context` to raise).
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_report_regional.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new tests plus `tests/test_report.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): Regional Context section in HTML, PDF and Word reports`.

---

### Task 15: About modal — Reference data section

**Files:**
- Modify: `sespy/modules/topbar_actions.py` (`_about_modal` :254; `topbar_actions_server` :313), `sespy/translations/core.json`
- Test: `tests/test_topbar_reference_data.py`

**Interfaces:**
- Consumes: `snapshot` (Task 10), `Snapshot.label`, `live_r_version`.
- Produces:
  - `topbar_actions_server(..., snapshot=None)`;
  - `_about_modal(translator, *, snapshot=None)`, which renders
    `div#about-reference-data` with one row per allow-listed file: name,
    source, label, `live R <v>` when known, and the first 8 characters of
    the hash. The core.json keys are `about.reference_data*`.

- [ ] **Step 1: Write failing tests:**
  - `test_about_lists_both_files_vendored` (text contains "vendored" and
    "R v1.34.2");
  - `test_about_shared_differs_label`;
  - `test_about_without_snapshot_omits_section`.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_topbar_reference_data.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): About shows which reference data is live`.

---

### Task 16: `tests/parity/check_live.py`

**Files:**
- Create: `tests/parity/check_live.py` (no `test_` prefix)
- Test: `tests/parity/test_check_live.py`

**Interfaces:**
- Consumes: `ALLOW_LIST` (Task 4), `RUNTIME_INPUTS`, `MANIFEST_PATH` (Task 1), `r_sync.json`.
- Produces a CLI:
  `check_live.py --pin tests/parity/r_sync.json --stage DIR [--live DIR]
  [--strict] [--warn-only] [--fetch [--server S --app-dir D]] [--perms FILE]`.
- **Exit codes:**
  - 0: ok, or drift only (unless `--strict`);
  - 2: a structural problem, a shipped-copy mismatch, or drift with
    `--strict`.

  `--warn-only` forces 0 and prints everything.
- `--live` absent means the override is off: skip checks 1 and 3; check 2
  always runs.
- `--perms FILE` contains `stat -c '%a %U %G %n'` lines for each file and
  each parent directory. Exit 2 unless user `shiny` can read the files and
  traverse the directories (other r/x, or group `shiny` r/x).
- `--fetch` reads `DEPLOY_SERVER`/`DEPLOY_DIR` from `deploy/config.env`
  (overridable), copies over `ssh`/`scp` into a temp directory, then
  checks.

- [ ] **Step 1: Write failing tests,** driving `main(argv) -> int` on
  `tmp_path` trees:
  - `test_ok`;
  - `test_structural_missing_key_exits_2`;
  - `test_unreadable_by_shiny_exits_2`;
  - `test_shipped_copy_mismatch_exits_2`;
  - `test_drift_warns_exit_0`;
  - `test_drift_strict_exits_2`;
  - `test_warn_only_forces_0`;
  - `test_override_off_still_checks_shipped_copy`;
  - `test_not_collected_by_pytest` (the file name has no `test_` prefix).
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/parity/test_check_live.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): live reference-data pre-flight checker`.

---

### Task 17: `deploy.sh` — pre-flight, settings file, atomic swap, MosaicSES restart

**Files:**
- Modify: `deploy/deploy.sh`, `deploy/config.env.example`, `.gitignore`
- Test: `tests/test_deploy_script.py` (static checks with `bash -n` and grep-level assertions; no ssh)

**Interfaces:**
- Consumes: Task 16's CLI.
- Produces, in order:
  1. Parse `--rollback`. If `SESPY_SKIP_LIVE_CHECK` is set, echo
     `skipping live check: <reason>`.
  2. Stage as today.
  3. Read the server's `server_settings.env`. If it is absent, use the
     default `/srv/shiny-server/marinesabres/data`.
  4. When the value is non-empty, `scp` the override files and the R
     `VERSION_INFO.json` into `$STAGE/.live/`, and write
     `$STAGE/.live/perms.txt` via `ssh stat` on each file and parent
     directory.
  5. Run `${SESPY_PY:-micromamba run -n shiny python} tests/parity/check_live.py
     --pin tests/parity/r_sync.json --stage "$STAGE"
     [--live "$STAGE/.live" --perms "$STAGE/.live/perms.txt"]
     [--warn-only if --rollback]`. Abort on non-zero. If `check_live.py`
     is absent from the checkout, print a message and continue.
  6. Remove `$STAGE/.live` before upload.
  7. Upload to `$APP_DIR/sespy.incoming/` (with the other runtime items as
     today). Then on the server: stash `logs` →
     `mv sespy sespy.old && mv sespy.incoming sespy` → restore `logs` →
     `rm -rf sespy.old`.
  8. On the server, create the settings file if it is absent:
     `umask 022; [ -e f ] || printf 'SESPY_R_DATA_DIR=%s\n' /srv/shiny-server/marinesabres/data > f; chmod 0644 f`.
  9. Touch `restart.txt`. If `DEPLOY_MOSAIC_DIR` is set, also touch
     `$DEPLOY_MOSAIC_DIR/restart.txt`.
- `config.env.example` documents `DEPLOY_MOSAIC_DIR` as optional.
- `.gitignore` gains `server_settings.env`.

- [ ] **Step 1: Write failing tests:**
  - `test_bash_syntax` (`bash -n deploy/deploy.sh`);
  - `test_uses_incoming_swap`;
  - `test_settings_file_created_only_if_absent_with_0644`;
  - `test_rollback_passes_warn_only`;
  - `test_skip_env_var_echoed`;
  - `test_mosaic_restart_conditional`;
  - `test_gitignore_has_server_settings`.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_deploy_script.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): deploy pre-flight, atomic swap, MosaicSES restart`.

---

### Task 18: MosaicSES compatibility guard

**Files:**
- Test: `tests/test_mosaicses_contract.py`

**Interfaces:**
- Consumes: the §4.10 contract.

- [ ] **Step 1: Write the test.** Using `inspect.signature`, assert that
  `isa_data_entry_server`, `Project.to_dict`, `Project.from_dict`, the
  `ProjectMetadata` constructor (required fields unchanged) and
  `get_regional_seas()` still accept MosaicSES's calls:
  - no new required parameters;
  - `snapshot` and `reference_reads`, wherever present, have defaults;
  - `get_regional_seas()[sea]` still has `name`, `ecosystem_types` and
    `common_issues`;
  - `import sespy.r_kb` in a subprocess with cwd set to a temp directory
    succeeds.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_mosaicses_contract.py -q`.
  Expected: PASS (it guards; it is written after the code exists).
- [ ] **Step 3: Commit** `test(k1): MosaicSES compatibility contract`.

---

### Task 19: e2e

**Files:**
- Create: `tests/test_kb_wizard_e2e.py`
- Modify: `tests/test_wizard_e2e.py` (country codes at :79, :113, :320, :404; row selectors at :86, :120, :360-361, :378, :381, :413 become `#wizard-freeform_{target}_container [data-row="{target}_{i}"]`), `tests/run_e2e.py` (`_child_env` gains `env["SESPY_R_DATA_DIR"] = ""`)

**Interfaces:**
- Consumes: everything above. Wait for the nav with the project's existing
  helper pattern (see `tests/test_wizard_e2e.py`).

- [ ] **Step 1: Write `tests/test_kb_wizard_e2e.py`** with the 7 steps of
  spec §7 e2e, in that order:
  1. Baltic → Coastal lagoon → 2 codes → Skip step 3.
  2. KB- and GOV-badged chips.
  3. Select 3 chips, deselect the middle, and check the order kept.
  4. Hand-typed text selects its chip.
  5. Back to step 2, then Next: country order kept.
  6. Finish, export the report, Regional Context present.
  7. About `#about-reference-data` shows "vendored" and "R v1.34.2".
- [ ] **Step 2: Update `test_wizard_e2e.py` and the runner.**
- [ ] **Step 3: Kill anything on port 8000** first (it reuses stale
  servers; see memory), then run the full suite detached with
  `Start-Process` + a log, as in the project's long-run practice:
  `micromamba run -n shiny python tests/run_e2e.py`.
  Expected: every script passes; the count is the previous 37 + 1.
- [ ] **Step 4: Commit** `test(k1): knowledge-base wizard e2e; wizard e2e on codes and data-row hooks`.

---

### Task 20: Release docs, roadmap edits, upstream drafts, gates

**Files:**
- Modify: `CHANGELOG.md`, `docs/MANUAL.md`, `docs/screenshots/*` (via `tests/make_docs_screenshots.py`), `docs/superpowers/specs/2026-10-17-p1a-link-rules-template-mapper-design.md:85-88`
- Modify on branch `docs/r-parity-roadmap`: the umbrella roadmap, with every bullet of spec §9 "Umbrella edits"
- Create: `docs/parity/upstream-drafts/k1-r-issues.md` (4 issue drafts, spec §9)

- [ ] **Step 1: CHANGELOG 1.16.0.** Name K1 and R v1.34.2, and list:
  - the features;
  - the known differences: no max-elements limit; unsaved step text
    discarded by Back; R's recommendation lines deferred to P14;
    countries changed per the §1.1(3) table;
  - the schema-9 forward-fix rollback policy;
  - the post-deploy checklist: worker `python -s` shows 1.16.0; About
    shows shared "R v1.34.2"; MosaicSES `verify_live.py --expect-version
    <v>`, where `<v>` comes from the deployed
    `MosaicSES/multises_app/__init__.py`.
- [ ] **Step 2: MANUAL K1 section and screenshots.** Fix the CHANGELOG
  extension-pair lines at :206-207 and the P1a spec lines.
- [ ] **Step 3: Roadmap edits** on `docs/r-parity-roadmap` (checkout via a
  worktree in `C:/Users/arturas.baziukas/AppData/Local/sespy-roadmap`, with
  `-c core.longpaths=true`). Apply every §9 bullet and commit there.
- [ ] **Step 4: Write the upstream drafts file,** including the 69-row
  lookup table generated from `load_k1_fixture("lookup")`.
- [ ] **Step 5: Gates.**
  - The full unit suite:
    `micromamba run -n shiny python -m pytest tests -q -p no:cacheprovider`.
  - The full e2e (Task 19).
  - MosaicSES: its unit tests and full e2e with
    `PYTHONPATH=<K1 worktree or checkout>`. Re-grep its pattern selectors
    against the new ids. Then open a schema-9 file in a v1.15.x worktree
    and assert `newer_build` and that autosave refuses to overwrite.
  - `check_live.py --fetch` against laguna. Expected: exit 0, with drift
    warnings allowed.
- [ ] **Step 6: Commit** `docs(k1): 1.16.0 release notes, manual, screenshots, roadmap and upstream drafts`.
  Stop here: the merge, tag and deploy need the user's go-ahead.
