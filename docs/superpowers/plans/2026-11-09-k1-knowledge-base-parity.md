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

**Tech Stack:** Python 3.11+, Shiny for Python (the env imports 1.9.0; see the Environment notes), pytest, Playwright
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

**Dry-run worktree (reference only).** The plan review executed Tasks 0–4
in the detached worktree `C:\Users\arturas.baziukas\AppData\Local\sespy-k1-dry`
(`abfb79e`). It is useful for comparing approaches, e.g. its
`_local_pin_hashes`, the fixture shapes and the greedy country cover set.
It predates this plan's round-1 fixes, so implement from **this** plan, not
by cherry-picking.

**Environment notes:**
- The `shiny` env currently imports **Shiny 1.9.0**; it changed mid-session
  on 2026-11-09. Confirm the version before starting.
- R: `C:\Program Files\R\R-4.4.1\bin\Rscript.exe` with `jsonlite` 2.0.0.
- `R_APP` below means the R app directory
  `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny`
  (**not** the SESToolbox root: sync uses `git rev-parse --show-prefix`).
- A stray site-packages `tests` package shadows `tests.*` imports, and
  `tests/` has no `__init__.py`. Tests import helpers by inserting the
  helper's directory into `sys.path` (the existing pattern), e.g.
  `sys.path.insert(0, str(Path(__file__).parent / "parity"))` then
  `from k1_fixtures import load_k1_fixture`.
- A stale editable install maps `sespy` to the main checkout. In a
  worktree, always run with `PYTHONPATH=<worktree root>`. Subprocess tests
  that import `sespy` set `PYTHONPATH` explicitly and assert on
  `sespy.__file__`.
- **Server-side tests** use `from shiny.testserver import test_server` (see
  `shiny skills path shiny-for-python` → `references/test-server.md`, and
  e.g. `tests/test_templates_module.py`). The pattern:
  - wrap the module server in a bare `server(input, output, session)` and
    keep reactives in a holder list;
  - use `ts.make_scope("wizard")`;
  - press a button with `set_inputs(btn=0)` then `set_inputs(btn=1)`;
  - capture toasts by monkeypatching `shiny.ui.notification_show`;
  - read internals with `shiny.testmode.export_test_values`.

  **One `set_inputs(a=…, b=…)` call is exactly one flush**: that is how
  "same tick" scenarios are written. Every rendered
  `entry_{gen}_{target}_{i}` must be set explicitly, because unset inputs
  raise SilentException. Verified rules from the plan review:
  - **Prime every button with 0** in an earlier `set_inputs` call (the
    `chip_*` buttons included). Setting a button straight to 1 does
    nothing.
  - **Within one `set_inputs`, effects run in keyword-argument order**,
    not registration order. Put `chip_…` before `wizard_next` for
    *chip-then-next*, and before `wizard_back` for *chip-and-back*.
  - **`ui.update_text` has no effect in `test_server`**, because there is
    no client. Simulate the echo with a following
    `set_inputs(entry_…=value)`. Assert the call with a spy monkeypatched
    onto `shiny.ui.update_text`.
  - Exports are namespaced; read them through `ts.make_scope("wizard")`.
    Rendered outputs read as `scope.get_output("chips_drivers").value["html"]`.
  - Worked example: `.superpowers/k1-prototypes/` has no copy, but the
    review's probe scripts are in the session scratchpad. The pattern:

```python
with test_server(server) as ts:          # server wraps ai_isa_wizard_server("wizard", ...)
    w = ts.make_scope("wizard")
    w.set_inputs(wizard_start=0, wizard_next=0, wizard_back=0,
                 **{f"chip_drivers_{i}": 0 for i in range(12)})   # prime
    # ... drive to step 4 ...
    w.set_inputs(**{f"entry_{g}_drivers_0": ""})          # g from get_export("gen")
    w.set_inputs(chip_drivers_3=1)                         # fill (spy update_text)
    w.set_inputs(**{f"entry_{g}_drivers_0": "KB item"})   # manual client echo
    assert w.get_export("pending").value == {"drivers": {}}
    assert "chip-on" in w.get_output("chips_drivers").value["html"]
```
  - **The translator is process-wide.** Any test that imports `app.py`
    calls `_i18n.set_default(T)` (`app.py:82`), and from then on `t()`
    returns English instead of keys, so a text assertion that passes alone
    fails in the full CI run. Every wizard/report/About test file pins it
    with an autouse fixture,
    `monkeypatch.setattr(sespy.i18n, "get_default", lambda: <fixed Translator or None>)`,
    and asserts outcomes (e.g. a failed Next) through exports and state,
    not toast wording.
- **PowerShell:** `$env:X=''` *deletes* the variable. To turn the override
  off in a shell, use `SESPY_R_DATA_DIR=off` (spec §4.1 accepts `off` as
  well as empty).
- **Starting and stopping a server for browser checks:**
  `Start-Process <env>\python.exe -m shiny run` dies silently with no
  log; start through `micromamba.bat run -n shiny python -m shiny run
  --port N app.py` with `-RedirectStandardOutput`/`-RedirectStandardError`.
  `Get-NetTCPConnection -LocalPort N -State Listen` can report
  `OwningProcess 0` for a live server, so kill by command line instead:
  `Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -match "--port N" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`.

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
  - Each key needs **all 9 languages** (en es fr de lt pt it no el);
    `test_i18n.py::test_loader_handles_all_supported_languages` enforces
    this.
  - Insert keys **textually**, matching the file's formatting. Never
    re-serialise `core.json` wholesale: `json.dumps` churns about 1,900
    lines.
- **e2e selectors** are namespaced ids or the `data-row` hook. Never
  `[id$=…]`, and never a bare `text=`.
- **Gates:**
  - CI and tests use vendored data only;
  - the e2e runner sets `SESPY_R_DATA_DIR=off`;
  - the full e2e gate runs with no other heavy jobs on the machine.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  Never push without the user's say-so.

## Review Focus

1. **An unknown sea slug** in a loaded project (e.g. `"atlantis"`, or
   `""`) gives generic or empty suggestions, no Regional Context section,
   and **no exception**. SP1's legacy `macaronesia` is *not* unknown: R
   resolves it to `macaronesia_island`, and SESPy must do the same. Tests
   in Tasks 6 and 14.
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

- [ ] **Step 1: Bump the three version lines to `1.16.0`.** The MANUAL
  line also carries a month; set it to "November 2026".
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
  - `REMOVED_INPUTS: frozenset[str] = frozenset()`, a module constant that a
    re-pin edits **deliberately** when an input is retired. `sync` passes
    it as `removed_inputs`, never a derived set (a derived set would make
    the guard vacuous).
  - `_local_pin_hashes(repo_root: Path, r_tag: str) -> tuple[dict[str, str], list[str]]`
    gunzips each local pin **once** and returns `(hashes, errors)`. A
    fixture whose `fixture_r_tag` ≠ `r_tag` is an error. `fixture_r_tag`
    returns `""` when the tag is absent.
- **Order inside `sync`:**
  1. run `_local_pin_hashes` (the tag check) **before** any input is read;
  2. in git mode, fetch `INPUTS` and `RUNTIME_INPUTS` with `git show`;
  3. in fixture mode, read the `RUNTIME_INPUTS` from their vendored targets
     in **their own loop** (the existing `data/` rule at :327 iterates
     `INPUTS` only);
  4. build outputs and the manifest;
  5. in git mode only, call `build_pin`. Fixture mode never writes the pin.
- In fixture mode, `--check` compares local-pin hashes with
  `pin_old["files"]`, and the rebuilt manifest and vendored outputs with
  disk. `RUNTIME_INPUTS` are written as raw bytes.

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
- [ ] **Step 4: Update the existing sync tests** so they keep passing on
  their own fake R repos. This is the bulk of the task.
  - **`tests/test_r_template_catalogue.py`:**
    - `_fake_r`: create `modules/`, and write stubs for every
      `K1_R_SOURCES` path, both `RUNTIME_INPUTS` and the two new
      translation files (with exactly the 8 keys).
      - `sync` does not validate runtime inputs, so their stubs need only
        be small JSON objects.
    - `_tree` (:38): copy `tests/parity` with
      `shutil.ignore_patterns('*.py', 'k1')`, so the real fixtures are
      never copied. `sespy/data/r_kb/` doesn't exist until Task 3, so
      **write** into the tree:
      - stub runtime targets;
      - a matching `manifest.json`;
      - tiny stub `.gz` local pins whose `r_tag` equals the tag each `sync`
        call targets: the pin's own tag in fixture mode, `rev` in git mode.

      Fixture-mode `--check` tests also add the stub hashes to the tree's
      pin, since the real pin has no local-pin entries until Task 3. This
      keeps the tag guard live in every test and the suite fast.
    - Update the hard-coded literals:
      - the `changed == …` set at :290;
      - the "wrote" counts at :297 and :324 (+ the manifest and the 2
        stems);
      - `:406` → 33, with `sorted(pin["files"])` == the union of all kinds;
      - `test_vendored_translation_key_counts` gains `isa_data_entry: 7`
        and `report_context: 1`;
      - `test_check_in_git_mode_passes_on_a_crlf_copy` skips `.gz` when
        converting to CRLF.
  - **`tests/parity/test_r_sync.py`:**
    - `:27` → 33;
    - `test_pin_shape`: r_translations 6 → 8;
    - `test_fixture_hash_matches_pin` uses `hash_local_pin` for `.json.gz`.
  - **Real-repo assertions stay red until Task 3:** `tests/parity/test_r_sync.py`,
    and in `tests/test_r_template_catalogue.py` the real-root
    `test_committed_tree_has_no_drift` (:655), the
    `("v1.33.0","4017feb")` → `("v1.34.2","edb42fd")` literal at :652, and
    `_as_crlf`'s real-root use.
  - Every fake-repo test must be **green now**.
- [ ] **Step 5: Run** `micromamba run -n shiny python -m pytest tests/test_k1_sync.py tests/test_r_template_catalogue.py -q`.
  Expected: PASS, with runtime comparable to before (about 30–40 s, not
  minutes). `tests/parity/test_r_sync.py` is still red; that is expected
  until Task 3.
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
  - `lookup`: `{"choices": [{sea, ecosystem, key, match}] (69 rows),
    "free_text": [{sea, ecosystem, key, match}]}`.
    - `match` is one of `exact | prefix | sea_only | fallback`.
    - R's `fallback` (no context; null key) corresponds to SESPy's
      `find_context(...) is None`.
    - `free_text` holds three R-import strings: `("baltic","Coastal lagoon
      and delta")`, `("mediterranean","Posidonia meadows")` and
      `("baltic","Schären archipelago")`.
  - `suggestions_grid`: `{"sources": {list_id: [[name, source]…]}, "cells":
    [{sea, ecosystem, category, issues, countries, items: list_id}]}`.
    Each distinct ordered list is stored once (about 1,400 ids) and
    referenced.
  - `habitat_specific`: `[{sea, ecosystem, category, items}]`.
  - `countries`: `{sea: [{code, name_en, eu_member}]}` for the 11 seas.
  - `report`: `{case_id: {sea, ecosystem, edges: [[from_label, to_label]…],
    markdown}}` for `baltic_lagoon`, `med_seagrass` and `irish_sea`. The
    inputs travel with the expected output, so Python tests never re-type
    them.

- [ ] **Step 1: Write the failing shape test.**
  - For each of the 5 names, `load_k1_fixture` returns non-empty data and
    the tag is `v1.34.2`.
  - `len(lookup["choices"]) == 69` and `len(lookup["free_text"]) == 3`.
  - The grid covers every (sea, ecosystem) of `sespy/regional_seas.json` ×
    7 categories × 7 issue sets × 4 country sets (13,524 cells). The
    country sets are derived from the fixture's own `countries` data,
    because governance is not vendored until Task 3.
  - Import with the `sys.path` pattern from the Environment notes.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/parity/test_k1_fixture_shape.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Write `scripts/capture_k1_fixtures.R`** from
  `.superpowers/k1-prototypes/r_capture.R` and `r_report.R`.
  - **Arguments:** `Rscript scripts/capture_k1_fixtures.R <R_APP>`. The
    script resolves SESPy's `sespy/regional_seas.json` and the output
    directory from its own location.
  - **Guards:** fail unless `git describe --tags` equals `v1.34.2` **and**
    `git status --porcelain -- <the 4 sourced .R files>
    data/ses_knowledge_db.json data/country_governance_db.json` is empty.
    The R checkout carries unrelated local edits (e.g. `CONTRIBUTING.md`),
    so a whole-tree clean check would never pass.
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
    `countries_by_sea[[sea]]` in both orders, and the fixed cover set
    `c("FR","RU","FM","ZA","BZ","DK","AU")`. That set covers all 6
    governance groups, all 3 income levels and all 15 conventions (24
    features; an empty conventions list is not a feature).
  - **Report cases** (built in the script; only sea, ecosystem and edge
    labels reach R's formatter):
    - `baltic_lagoon` ("Coastal lagoon"): **5 edges**, 2 matching KB
      connections, 2 not matching, 1 with an empty from-label;
    - `med_seagrass` ("Seagrass meadow"): no edges;
    - `irish_sea` ("Open coast"): no edges, so governance only.

    Each `markdown` is `paste0("# Regional Context\n\n",
    format_kb_section_for_report(kb, matched, gov))`, stored with its
    inputs.
  - **Output:** write gzipped JSON to `tests/parity/r_fixtures/k1/`.
  - In the script, dedup the item lists in O(n), with a hash map from the
    serialised list to its id.
- [ ] **Step 4: Run it detached.** It takes **about 20 minutes** (about
  88 ms per cell × 13,524 cells, measured in the dry run), and a
  backgrounded Bash call dies at 600 s. So use PowerShell:
  `Start-Process -WindowStyle Hidden -FilePath "C:\Program Files\R\R-4.4.1\bin\Rscript.exe" -ArgumentList 'scripts/capture_k1_fixtures.R','<R_APP>' -RedirectStandardOutput <log> -RedirectStandardError <log>.err`.
  - Poll with bounded `Start-Sleep` calls until the 5 files exist and the
    log ends.
  - Expected: 5 files written. Sizes are roughly: suggestions_grid about
    190 KB gz, the others under 10 KB each.
  - Then, **with the PowerShell tool**, run
    `attrib +P "tests\parity\r_fixtures\*" /S /D`.
- [ ] **Step 5: Write `tests/parity/k1_fixtures.py`;** run the shape test.
  Expected: PASS.
- [ ] **Step 6: Add `*.gz binary`** to a new `.gitattributes` (none exists
  today), then commit `test(k1): R v1.34.2 knowledge-base fixtures`.
  `tests/parity/test_r_sync.py` stays red until Task 3, as expected.

---

### Task 3: Re-pin to R v1.34.2 and triage

**Files:**
- Modify (generated by sync): `tests/parity/r_sync.json`, `docs/parity/R_SYNC.md`, `tests/parity/r_source/*`, `tests/parity/r_translations/*`, `sespy/translations/modules/{isa_data_entry,report_context}.json`, `sespy/data/r_kb/*`
- Modify by hand: `docs/parity/R_SYNC.md` (triage table)

**Interfaces:**
- Consumes: Task 1's `sync`, Task 2's fixtures.
- Produces: vendored `sespy/data/r_kb/{ses_knowledge_db,country_governance_db,manifest}.json`.

- [ ] **Step 1: Run** `micromamba run -n shiny python -m scripts.sync_r_templates --r-root "<R_APP>" --rev v1.34.2`.
  Expected: exit 0, with `wrote …` for every vendored file and the pin.
  - If template warnings appear, review them; rerun with
    `--accept-warnings` only if they match the R changes.
- [ ] **Step 2: Triage.** Add a "v1.33.0 → v1.34.2" table to `R_SYNC.md`
  with one row per path of `git diff --name-status v1.33.0 v1.34.2 -- .`,
  run in `R_APP` (44 rows).
  - Format: as P1b's table, with a Status column.
  - **Every** row gets a real one-line description and an owner. No
    placeholders.
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
  dehydration (spec §4.10). Use the PowerShell tool, because Git Bash
  mangles `/S`: `attrib +P "sespy\data\r_kb\*" /S /D`.
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
    assert a package-data glob covers `data/r_kb/<name>` for every
    allow-list name and `manifest.json`. Match **per path component**
    (split on `/`, then `fnmatch` each part), because plain `fnmatch`'s `*`
    crosses `/` and the existing `"*.json"` would pass vacuously;
  - `test_import_fails_without_vendored_file`: run in a subprocess with
    `PYTHONPATH` set to a temp copy of the package that is missing one
    file. Assert that `sespy.__file__` is in the temp copy, and expect a
    non-zero exit.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_r_kb.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the interfaces above in `sespy/r_kb.py`. Read
  the files with `importlib.resources` relative to the package; nothing
  relative to `APP_DIR`.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Add a slow-marked test** `test_wheel_contains_r_kb`.
  - It runs `python -m build --wheel --no-isolation --outdir <tmp_path>`
    (offline, with `build` in the env) and lists the wheel's contents.
  - It starts with `pytest.importorskip("build")`, because CI's `[test]`
    extra lacks it.
  - In `pyproject.toml` `[tool.pytest.ini_options]`, add
    `markers = ["slow: builds artefacts; run with -m slow"]` and
    `addopts = "-m \"not slow\""`, so slow tests are deselected by default.
  - Run `micromamba run -n shiny python -m pytest tests/test_r_kb.py -m slow -q`.
    Expected: PASS (about 25 s).
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
    `(vendored_hash, last_parsed_shared_hash)`. `last_parsed_shared` is
    the hash of the last shared copy that **validated**: it survives a
    fallback to vendored, and is None before any shared parse.
  - Module internals: `ENV_VAR`, `SETTINGS_FILE`, `_Registry`, and the
    instance `_REGISTRY`. The logger is `sespy.r_kb`.
- **Behaviour:** spec §4.1.
  - **Env precedence:** if `"SESPY_R_DATA_DIR" in os.environ`, it wins;
    else read `app_dir/server_settings.env` at every `refresh()`.
    - An empty value **or `off`** (case-insensitive) turns the override
      off.
    - `off` exists because Windows can drop variables set to `""`, so the
      e2e runner and every manual run use `off`.
    - **Settings-file format (the one parse rule, shared with Task 17's
      deploy fetch):** never `source` it. Take the **last** line matching
      `^SESPY_R_DATA_DIR=`, strip the prefix and surrounding whitespace;
      empty or `off` (case-insensitive) means off. A file with no such
      line, and an absent file, mean the default
      `/srv/shiny-server/marinesabres/data`. Test:
      `test_settings_file_last_line_wins_and_off`.
  - **Change key:** `(st_ino, st_size, st_mtime_ns, st_ctime_ns)` per
    override file.
  - **Swap:** parse and validate **all** override files; swap only if all
    pass.
  - **Missing or unreadable directory:** vendored on this worker, even if
    it previously had shared data.
  - **A missing or invalid file in a present directory:** keep last good,
    else vendored.
  - A failure is never recorded as seen.
  - **Live R version:** read `<dir>/../VERSION_INFO.json` optionally; the
    value is its `version` key.
  - **Logging:** each transition at WARNING: `r_kb.transition file=<f>
    from=<src> to=<src|last-good> reason=<r> hash=<h8>`. Keeping the last
    good copy logs `to=last-good`.
  - **No writes**, ever.

- [ ] **Step 1: Write failing tests,** all with `tmp_path` and monkeypatched
  env:
  - `test_override_valid_becomes_shared`;
  - `test_env_off_disables_file` (write a settings file, set env `off`, and
    the source stays vendored), plus the same with `""` (skip if the
    platform drops empty variables);
  - `test_settings_file_reread_each_refresh`;
  - `test_corrupt_keeps_last_good_then_retries`;
  - `test_too_small_and_wrong_major_rejected`;
  - `test_one_bad_file_means_no_swap` (KB new + governance corrupt → both
    stay old);
  - `test_missing_dir_goes_vendored_even_after_shared`;
  - `test_unreadable_dir_goes_vendored` (Review Focus 5; skip on Windows
    if chmod is ineffective, and also simulate with a monkeypatched
    `os.stat` raising `PermissionError`);
  - `test_same_size_same_mtime_rewrite_detected`: rewrite via a temp file +
    `os.replace` (a rename swap, as R's deploy does) with identical size
    and the mtime restored by `os.utime`; assert the swap through the inode
    and ctime change. An in-place rewrite is **not** detectable on Windows,
    where `st_ctime_ns` is the creation time;
  - `test_hashes_for_load_check` (None before a shared parse; survives a
    fallback);
  - also `test_label_shared_differs`, `test_missing_file_in_present_dir`,
    `test_unchanged_files_not_reparsed`, `test_live_r_version_read` and
    `test_unconfigured_registry_is_vendored`;
  - `test_two_sessions_keep_their_snapshots` (`a = current()`, swap the
    file, `refresh()`, `b = current()`, then `a.kb() != b.kb()` and `a` is
    unchanged);
  - `test_never_writes` (snapshot the directory's mtimes and file list
    before and after);
  - `test_transition_logged` (caplog contains `r_kb.transition`).
  Each test monkeypatches `r_kb._REGISTRY` with a fresh `r_kb._Registry()`.
  A file that is still broken re-logs `to=last-good` once per `refresh()`,
  which is accepted. With no last-good copy, the log says `to=vendored`.
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
- **Algorithm:** port lookup, grid suggestions and dedup from
  `.superpowers/k1-prototypes/kbport.py`, which matches R for those.
  **Port from R directly, not kbport** (kbport lacks or breaks these):
  - `get_habitat_specific_suggestions`: about 300 lines,
    `ai_isa_knowledge_base.R:642-942`, a nested `switch` by sea group with
    defaults (kbport raises `NotImplementedError` here);
  - `get_context_connections`: `ses_knowledge_db_loader.R:262-307`;
  - `sea=None`/`""`: R's `paste0(character(0), "_")` is `"_"`, so no
    context matches and the result is None (kbport crashes); `("baltic",
    None)` resolves `sea_only` like R;
  - a JSON `"relevance": null` counts as 0.5 (R's `%||%`; kbport crashes).

  Every trap in spec §4.2 applies:
  - `re.split(r"\s+", …)`;
  - the single-pass suffix strip;
  - `intersect` uniqueness against a duplicate-counting denominator;
  - JSON file order;
  - a stable descending sort;
  - "any issue matches" in R's branch order;
  - an unmapped governance category returns `[]`;
  - codes are upper-cased.

- [ ] **Step 1: Write failing fixture-driven tests:**
  - `test_lookup_matches_r` over `load_k1_fixture("lookup")["choices"]`:
    key and match for all 69 rows. R's `fallback` maps to
    `find_context(...) is None`;
  - `test_suggestions_grid_matches_r` over every grid cell, comparing full
    ordered `[[name, source]]`;
  - `test_habitat_specific_matches_r`;
  - `test_countries_for_sea_matches_r`;
  - `test_decision2_quirks_named`, a table of 5 named cases from §1.1(2):
    Pacific Coral reef → `pacific_island_atoll`; Indian Island →
    `indian_ocean_coral_reef`; Atlantic Coastal upwelling →
    `atlantic_open_coast` exact; Irish Sea → None; North Sea Sandy beach →
    `north_sea_offshore`;
  - `test_unknown_sea_slug_no_exception`: `"atlantis"` (no `atlantis_*`
    context, no `countries_by_sea` entry) and `""` give generic-fallback
    items and `find_context(...) is None` (Review Focus 1);
  - `test_legacy_macaronesia_resolves_like_r`: SP1's `"macaronesia"` with
    `"Open coast"` resolves **exact** to `macaronesia_open_coast`, and with
    `"Coral reef"` (no macaronesia context) resolves `sea_only` to
    `macaronesia_island`, both as R does (verified with Rscript; not a bug
    to fix);
  - `test_none_sea_or_ecosystem_like_r`: `(None, "Open coast")` and
    `("", None)` → None, no exception; `("baltic", None)` → `sea_only`;
  - `test_null_relevance_is_half`: a synthetic KB with `"relevance": null`
    ranks the element as 0.5;
  - `test_free_text_ecosystems_match_r` over `lookup["free_text"]`, R's own
    resolution of the three R-import strings (Review Focus 2).
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_kb_suggestions.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the interfaces.
- [ ] **Step 4: Run the tests.** Expected: PASS (all grid cells; the
  13,524-cell grid test alone takes about 3.5 min).
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
    there is no content (`functions/report_generation.R:173-175`;
    `kb_report_helpers.R:364-366`).
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
    `load_k1_fixture("report")`. Build each from the case's own `sea`,
    `ecosystem` and `edges`, and compare `to_markdown` with its `markdown`
    after whitespace normalisation;
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
- Test: create `tests/test_schema_v9.py`. Update the schema pins:
  - `tests/test_schema_v8.py:37-38, 43-44, 50` (use
    `SCHEMA_MIN_READER[PROJECT_SCHEMA_VERSION]`);
  - `tests/test_data_structure.py:17-18`;
  - `tests/test_schema_v7.py`;
  - `tests/test_r_template_catalogue.py:225, 693`
    (`test_shipped_templates_are_schema_9`, which also asserts
    `reference_data == {}`).

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
  Expected: the 7 template files change content (gaining
  `reference_data: {}` and the 1.16.0 stamp). `git status` may also show
  `catalogue.json`, `manifest.json` and the two translation files as
  touched, with line endings only and an empty diff.
- [ ] **Step 5: Run the CI unit set:**
  `micromamba run -n shiny python -m pytest tests -q -p no:cacheprovider --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`.
  - Expected: PASS, except
    `test_analysis_boolean_clamp.py::...[50-12]`, which already fails on
    the baseline (a test_server 5 s timeout under load). It is not a K1
    regression; note it, don't fix it here.
  - The full run takes about 10 minutes now, and about 18 minutes once
    Tasks 6 and 11–13 land (the grid test plus the wizard server tests).
    Run it detached and poll in bounded `Start-Sleep` calls.
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
    `to_json(*, indent=2, reference_data=None)` (`indent` is already
    keyword-only today). `None` writes
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
- Modify: `app.py` (:173-330), `sespy/modules/ai_isa_wizard.py`, `sespy/modules/report_export.py` and `sespy/modules/topbar_actions.py` (signatures only), `sespy/modules/project_io.py` (`quick_actions_server` :103; autosave :142-161; save :292-318; New :381-384), `sespy/modules/templates.py` (only to confirm `template_loaded` exists; no change expected), `sespy/translations/core.json`
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
    `set` only if a name is new. `add_reads(None, ...)` is a no-op (callers
    mounted without `reference_reads`, e.g. MosaicSES); test
    `test_add_reads_none_is_noop`. `r_kb` stays stdlib-only at import, so
    `from shiny import reactive` is a lazy import inside this function.
  - When `snapshot` or `reference_reads` is None, save and autosave pass
    `reference_data=None`, and the load check is skipped.
  - `quick_actions_server(..., snapshot: Snapshot | None = None,
    reference_reads: reactive.Value[frozenset[str]] | None = None)`. Save
    and autosave pass `reference_data=current_provenance(...)`. Autosave
    reads `reference_reads` under `isolate()`.
  - **Reset and load check are one effect:**
    `@reactive.event(event_bus.project_loaded, event_bus.template_loaded, ignore_init=True)`.
    It resets `reference_reads` to `frozenset()`, then runs the check,
    reading `project_data` under `isolate()`. It never reacts to
    `project_data` itself, which would re-check on every edit. `_on_new`
    resets `reference_reads` directly.
  - **Toasts:** one per file, id `kb-provenance-<file>`, `type="warning"`,
    `duration=None` (sticky). Stale toasts are not removed on the next
    load. Entries for files the snapshot doesn't have are skipped.
  - **Load check details,** placed beside `_newer_build_warning`
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
  - `test_toast_silent_when_equal_to_snapshot`;
  - `test_toast_differs_for_vendored_and_for_last_parsed_shared` (two
    cases);
  - `test_toast_unavailable_for_foreign_hash`;
  - `test_autosave_includes_reads_after_isa_change`. Set the browser-token
    input, satisfy `recovery_checked`, and monkeypatch
    `sespy.modules.project_io.write_autosave` to capture the call.

  - `test_save_download_carries_provenance`. `test_server` cannot press a
    `render.download_button`, so call
    `session._downloads["save_project"].handler()` under `isolate()`. This
    is a private API, accepted for this one test.

  Compose `quick_actions_server` in a bare root-level test server (it is
  not a module, so there is no `make_scope`). Never import `app.py`:
  `server()` and `dashboard._restore_view_from_url` read
  `clientdata.url_search()` before `test_server` sends client data, and
  that raises ValueError.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_k1_wiring.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the wiring. Pass `snapshot` to the wizard,
  report export, `quick_actions_server` and `topbar_actions_server`, and
  `reference_reads` to the first three.
  - This task adds the keyword-optional parameters to all four servers
    (`report_export_server(..., snapshot=None, reference_reads=None)` and
    so on). The other three are accepted but not yet used.
  - Tasks 11, 14 and 15 **use** them.
- [ ] **Step 4: Run** the tests plus `tests/test_autosave.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): session snapshot, reference reads and provenance toasts`.

---

### Task 11: Country step and skippable steps 2–3

**Files:**
- Modify: `sespy/wizard.py`, `sespy/modules/ai_isa_wizard.py` (`_render_choice_many` :107-128; `_on_next` :510-668; `_assemble_wizard_state` :670), `sespy/data_structure.py` (`WizardState` :763-772), `sespy/claude_backend.py:313`, `sespy/regional_seas.json`, `sespy/regional_seas.py`, `tests/test_regional_seas.py`, `tests/test_wizard.py`, `tests/test_claude_backend.py` (:150 state gains `country_names`; :167 asserts names)
- Test: `tests/test_wizard_countries.py`

**Interfaces:**
- Consumes: `countries_for_sea` (Task 6), `snapshot` (Task 10), `add_reads`.
- Consumes (added in Task 10): `ai_isa_wizard_server(..., snapshot=None,
  reference_reads=None)`. With `snapshot=None` it uses `r_kb.VENDORED`,
  which keeps MosaicSES and the tests working.
- Produces:
  - `WizardState.country_names: list[str] = field(default_factory=list)`.
  - `country_names_for(gov: dict, codes: list[str]) -> list[str]` in
    `sespy/kb_suggestions.py`.
  - The step-2 selectize has optgroups `eu_member_states` and
    `non_eu_countries` (R keys). Option values are codes; labels are
    `name_en`.
  - A Skip button `skip_{target}` on steps 2 and 3, labelled
    `modules.isa.ai_assistant.skip_this_question`, records `[]` and
    advances.
  - The Skip handler acts only when its target is the current step and
    the wizard is active (the same guard as the chip handlers).
  - Empty Next is accepted on steps 2 and 3. `_on_next` reads
    `answer_countries` with `SilentException` caught, because the input is
    unset when nothing was ever selected.
  - Tests in this task assert through answers/`WizardState`, never by
    grepping `entry_<target>_<i>` ids: Task 12 changes those ids to
    `entry_{gen}_{target}_{i}`.
  - **Sea change:** `_on_next` for step 0 filters
    `wizard_answers["countries"]` to the new sea's codes.
  - `claude_backend.py:313` joins `state.country_names`.
  - `regional_seas.json` loses `countries`, `country_codes` and
    `eu_member_codes`; `get_eu_member_codes` is deleted along with its
    tests.

- [ ] **Step 1: Write failing tests:**
  - `test_country_choices_from_governance` (Pacific has FM and none of
    CN, JP, ID, PH, CL; Caribbean has 27 and neither FR nor NL; Atlantic
    has no US; DK/FR/NL names carry no "(Greenland)"/"(overseas)"
    suffix);
  - in `tests/test_regional_seas.py`, **delete** the per-sea country spot
    checks (atlantic US, pacific JP, caribbean FR/NL): the JSON no longer
    has countries. Country coverage lives in Task 6's
    `test_countries_for_sea_matches_r` and the test above;
  - `test_values_are_codes_and_names_resolved`;
  - `test_empty_next_allowed_on_steps_2_3`;
  - `test_skip_button_records_empty`;
  - `test_sea_change_filters_codes`;
  - `test_claude_prompt_uses_names`;
  - `test_country_order_kept` (selection order passed through to
    `WizardState.countries`);
  - `test_countries_record_reads` (rendering step 2 adds both files to
    `reference_reads`);
  - `test_other_sea_excluded` (`other` is not offered in step 0, as in
    SP2).
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_wizard_countries.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Check country order after Back in a browser.**
  - Start the app with `SESPY_R_DATA_DIR=off` set in the environment
    (`micromamba run -n shiny python -m shiny run --port 8771 app.py`).
  - Pick two countries in reverse option order, go Next, then Back, then
    Next.
  - It **will** come back in option order: the plan review measured that
    selectize rebuilds items from `<option selected>` in DOM order, and
    optgroups prevent reordering the options across groups. The forward
    path is fine, because `getValue()` returns click order.
  - Restore the order by passing `options={"plugins": ["remove_button"],
    "items": saved_codes}` to `ui.input_selectize` (shiny.js hands
    `options` to selectize, and user settings override the element's). If
    that fails in the browser, call
    `ui.update_selectize("answer_countries", selected=saved_codes)` after
    render.
  - Confirm in the browser, and add `test_back_preserves_country_order`
    (asserting the options payload) plus the e2e step in Task 19.
  - Add `test_country_optgroups` (the rendered HTML has two `<optgroup>`s
    with R's labels).
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
  - Row ids are `entry_{gen}_{target}_{i}`.
  - Each row's **`<input>` element** carries `data-row="{target}_{i}"`.
    `ui.input_text` takes no attrs, so set it on the child:
    `[c for c in tag.children if getattr(c, "name", None) == "input"][0].attrs["data-row"] = f"{target}_{i}"`.
    On the wrapper div, Playwright's `fill()` would fail.
  - The rows container id becomes
    `resolve_id(f"freeform_{target}_container")`
    (`from shiny.module import resolve_id`), so the DOM id is
    `wizard-freeform_{target}_container`. Ids inside a module's
    `@render.ui` are **not** namespaced automatically; today it renders as
    `freeform_drivers_container`.
  - **Exports for tests,** with string keys (orjson rejects int keys):
    `export_test_values(pending=lambda: {t: {str(i): v for i, v in d.items()} for t, d in pending.get().items()}, gen=lambda: dict(gen.get()))`.
  - `effective_rows(target) -> list[tuple[bool, str]]` (exists, value).
    Value is pending, else live-if-exists, else saved.
  - `row_count(target) -> int`, defined in §4.3.
  - **Clearing effect,** one per target (prototype `mk_clear`,
    `app_gen.py:187-200`): drop a pending entry as soon as the live input
    of the current generation reports the same value. Without it, pending
    keeps masking what the user types next.
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
  - `test_remove_then_add_no_stale_text`;
  - `test_replace_then_reenter_blank`;
  - `test_failed_next_keeps_pending_row`: without chips the only pending
    source is the Add tombstone (type in row 1, Remove, Add over the stale
    live value), then a Next that fails validation; a failed Next does not
    re-render, so assert the `pending` export, not rendered rows;
  - `test_back_next_idempotent`;
  - `test_unsaved_text_discarded_by_back` (documents the behaviour change).
  - **Reading internals:** tests read `pending` and `gen` through the
    exports above; no seam parameter is added. The overlay tests that need
    a deselect or a fill move to Task 13, where chips exist:
    `test_back_deselect_add_stays_blank` and
    `test_typing_after_server_fill_wins` (fill via a chip, echo the value
    with `set_inputs`, then type `Y`, and the effective value is `Y`).
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
  - A caption, shown when a sea is set, built as R does
    (`ai_isa_assistant_module.R:1574-1582`): ` (` + `t("tailored_for")`
    in the key's own casing (en "tailored for") + ` ` + sea name, then
    ` - <ecosystem>` **only if** an ecosystem is set, then `)`. The sea
    name is the English `REGIONAL_SEAS[slug]["name"]`: SESPy has no
    per-sea i18n keys (R's `name_i18n`), a known difference for the
    CHANGELOG. Tests: `test_caption_without_ecosystem`,
    `test_caption_with_ecosystem`.
  - Each `chips_{target}` render returns empty unless its target is the
    current step, so the suggestion pipeline runs once per change, not
    seven times. Test: `test_chips_render_only_current_step` (spy on
    `get_context_suggestions`: one call per step change).
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
  - `test_two_different_chips_same_flush_with_empty_row` and
    `test_two_different_chips_same_flush_without_empty_row`;
  - `test_chip_then_next_same_flush_fill_path` and
    `test_chip_then_next_same_flush_added_row_path`;
  - `test_chip_then_next_same_flush_then_back_shows_saved`;
  - `test_chip_and_back_same_flush_then_reenter_no_leak`;
  - `test_add_remove_interleaved_with_chips`;
  - `test_type_row1_remove_then_chip_with_no_empty_row`;
  - `test_added_row_chip_and_failing_next_same_flush_keeps_row`;
  - `test_chip_for_other_target_ignored`;
  - `test_reads_recorded_once`;
  - `test_back_deselect_add_stays_blank` and
    `test_typing_after_server_fill_wins` (moved here from Task 12).

  "Same flush" means one `set_inputs(...)` call carrying both inputs.
  `test_server` has no client, so `ui.update_text` is never echoed: tests
  simulate the echo with a following `set_inputs(entry_…=value)`.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_wizard_chips.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Replay the prototype driver's scenario list** against the
  real app in a browser, as an extra check beyond the committed tests.
  - Adapt `chips/drive_gen.py` into a throwaway script in the session
    scratchpad. The prototype's `debug` and `meta` outputs do not exist in
    the real app: run with `SHINY_TESTMODE=1` and read `pending`/`gen`
    through the test-mode exports where a scenario asserts server state;
    scenarios that assert render or input-key **counts** (X3b, X4) have
    no equivalent and are dropped, and the report says which.
  - Run the app on port 8772 with `SESPY_R_DATA_DIR=off` (see Environment
    notes for start/kill), and kill the server afterwards.
  - Expected: every kept scenario passes. Known, accepted: after Back,
    rows keep the stale `freeform_counts` (2 saved items can render as
    3–4 rows with trailing blanks); saved answers are correct. This is
    today's Back behaviour and the spec's row-count rule, not a
    regression.
- [ ] **Step 5: Run** the tests plus `tests/test_wizard.py`. Expected: PASS.
- [ ] **Step 6: Commit** `feat(k1): knowledge-base suggestion chips in wizard steps 4-10`.

---

### Task 14: Regional Context in HTML, PDF and Word; the toggle

**Files:**
- Modify: `sespy/report.py` (CSS :44-50; template after :100; `_build_context` :182; `render_html/pdf/docx` :236/243/263), `sespy/modules/report_export.py` (:20-110), `app.py` (:158, the `report_export_ui` mount)
- Test: `tests/test_report.py`, plus a new `tests/test_report_regional.py`; golden `tests/fixtures/report_default_golden.html`

**Interfaces:**
- Consumes: `build_regional_context` (Task 7), `HEADINGS` (Task 7), `add_reads`, `snapshot`.
- Produces:
  - **One pure gate,** in `sespy/report.py`:
    `regional_context_for(project, snapshot) -> RegionalContext | None`.
    It returns None unless `snapshot` is not None, `regional_sea` and
    `ecosystem_type` are non-empty, and `build_regional_context(...)` is
    not None; an exception inside it logs WARNING and returns None. Both
    the renderers and `report_export` call it; nothing else re-implements
    the gate.
  - `render_html(project, *, snapshot=None, include_regional_context=False)`;
    the same signature for `render_pdf` and `render_docx`. The section
    renders iff `include_regional_context` and
    `regional_context_for(...)` is not None.
  - **No snapshot → no section** (unlike the wizard, which falls back to
    `r_kb.VENDORED`): a report must say which data it used, and only a
    snapshot carries provenance.
  - **HTML:** `<h2>Regional Context</h2>`, then h3–h5 for R's levels, with
    h4 and h5 CSS added. **Word:** Heading 2–5 and a 5-column table.
    Heading text comes from `kb_report.HEADINGS`, never retyped.
  - **Edges:** `isa_data.connections` in list order, ids mapped to labels;
    an id with no element maps to the id itself (as `_build_context`
    does).
  - A checkbox, module-local id `include_regional_context`, with DOM id
    `report-include_regional_context` (the module is mounted as
    `"report"`). Label key `modules.report_context.include_context`;
    default `True`. `report_export_ui` gains a `translator` parameter (the
    `topbar_actions_ui(T)` precedent); `app.py:158` passes `T`.
  - `report_export_server(..., snapshot=None, reference_reads=None)`, as
    added in Task 10.
  - The preview output reads the checkbox, so toggling re-renders it.
  - When the toggle is on and `regional_context_for(...)` is not None,
    `report_export` calls `add_reads(reference_reads, {"ses_knowledge_db.json",
    "country_governance_db.json"})` (a no-op when `reference_reads` is None).

- [ ] **Step 0: Save the golden first.** Before any code change, generate
  `tests/fixtures/report_default_golden.html` from the current
  `render_html(project)` with `sespy.report.datetime` monkeypatched to a
  fixed instant (a scratchpad script); commit it with Step 1's tests.
- [ ] **Step 1: Write failing tests:**
  - `test_html_section_present_baltic`: built from
    `load_k1_fixture("report")["baltic_lagoon"]`; assert every `HEADINGS`
    entry and every evidence row of the fixture appear, **in order**;
  - `test_section_absent_when_sea_empty` and
    `test_section_absent_for_unknown_slug` (`"atlantis"`; Review Focus 1);
  - `test_irish_sea_governance_only_html`;
  - `test_docx_has_heading_levels_and_table`;
  - `test_defaults_keep_old_output`: `render_html(project)` equals a golden
    saved **before Step 3**. Monkeypatch `sespy.report.datetime`, because
    `_build_context` stamps the time to the minute;
  - `test_generation_error_omits_section` (monkeypatch
    `build_regional_context` to raise);
  - `test_no_snapshot_no_section`;
  - in `test_server` (see Environment notes): `test_checkbox_default_true`,
    `test_preview_depends_on_toggle` (preview text changes when the box is
    set False), and `test_report_export_records_reads_only_when_generated`
    (reads stay empty with the toggle off or sea empty; both names appear
    once with it on).
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_report_regional.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
  - python-docx 1.2.0 builds the docx: `add_heading(level=2..5)` and a
    5-column table (style `"Light Grid Accent 1"`), both verified.
  - `_TEMPLATE` is a Jinja string; insert after the meta `</p>` (:100).
  - `render_pdf` (:259) passes the new kwargs through to `render_html`.
- [ ] **Step 4: Run** the new tests plus `tests/test_report.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): Regional Context section in HTML, PDF and Word reports`.

---

### Task 15: About modal — Reference data section

**Files:**
- Modify: `sespy/modules/topbar_actions.py` (`_about_modal` :254; `topbar_actions_server` :313), `sespy/translations/core.json`
- Test: `tests/test_topbar_reference_data.py`

**Interfaces:**
- Consumes: `snapshot` (Task 10), `Snapshot.label`, `live_r_version`.
- Consumes (added in Task 10): `topbar_actions_server(..., snapshot=None)`.
- Produces:
  - Both callers (`topbar_actions.py:333` and `:369`) pass `snapshot=`.
    The section sits in the About modal's **Overview** panel, so it is
    visible when the modal opens.
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
  `check_live.py [--pin P] [--stage DIR] [--live DIR] [--strict]
  [--warn-only] [--fetch [--server S --app-dir D]] [--perms FILE]
  [--print-override-names]`.
  - Defaults: `--pin tests/parity/r_sync.json`, `--stage` = the repo root
    (the `RUNTIME_INPUTS` targets are repo-relative). The script inserts
    its own repo root (`Path(__file__).resolve().parents[2]`) at
    `sys.path[0]` before `import sespy`, so the stale editable install and
    a rollback worktree never import the wrong `sespy`.
  - `--print-override-names` prints `[r.name for r in ALLOW_LIST if
    r.override]`, one per line, exit 0. `deploy.sh` uses it (bash cannot
    read `ALLOW_LIST`).
  - **Validation baseline:** live files are validated against the major
    of the **staged** vendored copy (`<stage>/sespy/data/r_kb/`), not the
    imported `r_kb.VENDORED`.
- **Exit codes:**
  - 0: ok, or drift only (unless `--strict`);
  - 2: a structural problem, a shipped-copy mismatch, or drift with
    `--strict`;
  - 3: `--fetch` only, the ssh/scp connection itself failed (not
    overridden by `--warn-only`).

  `--warn-only` forces 0 and prints everything.
- `--live` absent means the override is off: skip checks 1 and 3; check 2
  always runs.
- `--perms FILE` contains one line per path, in one of two forms:
  - `sudo-test <path> ok|fail`, written when `deploy.sh` can run
    `sudo -n -u shiny test -r <path>` (preferred);
  - `stat <%a> <%U> <%G> <path>`, for each file and each parent directory.

  Exit 2 on any `fail`, or unless `shiny` can read the files and traverse
  the directories: owner `shiny` with u r/x, or group `shiny` with g r/x,
  or other r/x. Parse the **last 3 digits** of `%a` (setgid/sticky give 4
  digits). A file with no `stat` lines for its parent directories is a
  `fail`. Expect the `stat` form on laguna, because a passwordless
  `sudo -u shiny` for razinka is unverified.
- `--live DIR` may contain `missing.txt` (one allow-listed name per line,
  written by `deploy.sh` when a fetch failed): each listed name is a
  structural problem.
- `--fetch` reads `DEPLOY_SERVER`/`DEPLOY_DIR` from `deploy/config.env`
  (`--server`/`--app-dir` override), then does exactly what Task 17 steps
  3–4 do: read `server_settings.env` with the Task 5 parse rule (absent →
  the default path), fetch the override files and `VERSION_INFO.json`
  into a temp directory, write the perms file in the `stat` form, then
  check. An ssh/scp failure of the connection itself (not a missing file)
  exits 3 with the command and stderr. It runs `ssh`/`scp` from `PATH` via
  `subprocess`; on Windows that is OpenSSH's `ssh.exe` (its own agent,
  not Git Bash's).

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
  - `test_missing_txt_is_structural` and `test_missing_txt_warn_only_exits_0`;
  - `test_perms_four_digit_mode`, `test_perms_missing_parent_line_fails`,
    `test_perms_sudo_test_fail`;
  - `test_print_override_names`;
  - `test_fetch_reads_config_env` (monkeypatch `subprocess.run`; assert
    the host/path from a temp `config.env` and the settings-file read
    come first);
  - `test_not_collected_by_pytest`: run `pytest --collect-only -q
    tests/parity` in a subprocess; assert `check_live.py` is not in the
    output.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/parity/test_check_live.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(k1): live reference-data pre-flight checker`.

---

### Task 17: `deploy.sh` — pre-flight, settings file, atomic swap, MosaicSES restart

**Files:**
- Modify: `deploy/deploy.sh`, `deploy/config.env.example`, `.gitignore`
- Test: `tests/test_deploy_script.py` (a behavioural harness with executing ssh/scp stubs against a temp fake server; no network)

**Interfaces:**
- Consumes: Task 16's CLI.
- **Repo root:** `REPO_ROOT="${DEPLOY_REPO_ROOT:-$SCRIPT_DIR/..}"`. This
  is how rollback works (spec §4.8.5): the **current** `deploy.sh` deploys
  a worktree of the old tag (`git worktree add <dir> v1.15.0`, then
  `DEPLOY_REPO_ROOT=<dir> deploy/deploy.sh --rollback`); checking out the
  old tag would run the old script, which has no `--rollback` and no
  atomic swap. Document the procedure in the CHANGELOG (Task 20 Step 1).
- **Python:** check_live runs as `PYTHONPATH="$REPO_ROOT"
  ${SESPY_PY:-micromamba run -n shiny python} "$REPO_ROOT/tests/parity/check_live.py" ...`;
  path arguments go through `"$(cygpath -w "$p")"` when `cygpath` exists
  (native `micromamba.exe` does not understand MSYS `/tmp/...` paths).
- Produces, in order:
  1. Parse `--rollback`. If `SESPY_SKIP_LIVE_CHECK` is set, echo
     `skipping live check: <reason>`.
  2. Stage as today.
  3. Read the server's settings file without sourcing it:
     `ssh "$SERVER" "if [ -e '$APP_DIR/server_settings.env' ]; then cat '$APP_DIR/server_settings.env'; else echo __ABSENT__; fi"`,
     then apply **Task 5's parse rule** locally (`__ABSENT__` or no
     matching line → the default `/srv/shiny-server/marinesabres/data`;
     empty or `off`, case-insensitive → override off).
  4. When the override is on, fetch each name from `check_live.py
     --print-override-names` plus the optional `$DIR/../VERSION_INFO.json`
     into `$STAGE/.live/`, each as `scp -q "$SERVER:$DIR/<name>"
     "$STAGE/.live/" || echo "<name>" >> "$STAGE/.live/missing.txt"`
     (never aborts under `set -e`; a missing `VERSION_INFO.json` is not
     recorded). Write `$STAGE/.live/perms.txt` with `stat -c 'stat %a %U
     %G %n'` on each file and each parent directory up to `/`. The
     `sudo-test` form is used **only** when `DEPLOY_SUDO_TEST=1` (a denied
     `sudo` can raise auth alerts on the server); then run `sudo -n -u
     shiny true` once and, if it fails, fall back to `stat` for every
     path.
  5. **Only if `SESPY_SKIP_LIVE_CHECK` is unset**, run check_live
     `--stage "$STAGE" [--live "$STAGE/.live" --perms "$STAGE/.live/perms.txt"]
     [--warn-only if --rollback]`. Abort on non-zero. If `check_live.py`
     is absent from the checkout, print a message and continue.
     `--rollback` is therefore never gated: fetch failures land in
     `missing.txt`, and `--warn-only` exits 0.
  6. Remove `$STAGE/.live` before upload.
  7. **Server-side recovery prologue** (one ssh): if `sespy/` is absent
     and `sespy.old/` exists, `mv sespy.old sespy`; then `rm -rf
     sespy.old`; if `sespy/logs` is absent and `.deploy-keep/logs` exists
     (left by the old script), move it to `sespy/logs`.
  8. **Upload and swap, in this order** (a new `app.py` against the old
     `sespy` crashes on `import sespy.r_kb`; the reverse is safe because
     the new kwargs are keyword-optional):
     1. `rm -rf "$APP_DIR/sespy.incoming"`;
     2. `scp -rq "$STAGE/sespy" "$SERVER:$APP_DIR/sespy.incoming"` (no
        trailing slash: newer OpenSSH's SFTP mode fails on a slash target
        that does not exist);
     3. if `sespy/logs` exists, `mv sespy/logs sespy.incoming/logs`, so
        `feedback.db` is never overwritten;
     4. if `sespy/` exists, `mv sespy sespy.old`; then `mv sespy.incoming
        sespy && rm -rf sespy.old`;
     5. today's pre-clean (`rm -rf __pycache__ docs/screenshots` on the
        server), then scp the other runtime items (`sespy` excluded from
        the `"$STAGE"/*` glob);
     6. create the settings file if absent: `umask 022; [ -e f ] ||
        printf 'SESPY_R_DATA_DIR=%s\n' /srv/shiny-server/marinesabres/data
        > f; chmod 0644 f`;
     7. touch `restart.txt`; if `DEPLOY_MOSAIC_DIR` is set, also touch
        `$DEPLOY_MOSAIC_DIR/restart.txt`.
     - Drop the old `.deploy-keep` logic (the prologue recovers a
       leftover). MosaicSES's `ln -sfn '$SESPY_APP_DIR/sespy'` is
       path-based, so it survives the swap.
- `config.env.example` documents `DEPLOY_MOSAIC_DIR`, `DEPLOY_REPO_ROOT`
  and `DEPLOY_SUDO_TEST` as optional.
- `.gitignore` gains `server_settings.env`.
- **Spec correction** (Task 20 Step 2b): §4.8 says `deploy.sh` honours the
  env override at :27-30; it does not when `deploy/config.env` exists,
  because that file is sourced after the env.

- [ ] **Step 1: Write failing tests.** Two kinds:
  - **A behavioural harness** (preferred over greps). The stubs must
    **execute**, against a fake server tree, so state assertions are real:
    - Build a temp fake repo: `deploy/deploy.sh` copied in, **no
      `config.env`** (the real one is sourced after the env and would
      point the run at laguna's host and path), a minimal `app.py`,
      `sespy/__init__.py` + `sespy/data/r_kb/` copies,
      `docs/MANUAL.md`, an empty `docs/screenshots/`,
      `tests/parity/r_sync.json`, and `tests/parity/check_live.py`
      (present or absent per test). Run with `DEPLOY_REPO_ROOT` unset
      (the copied script resolves its own root).
    - Env: `DEPLOY_SERVER=fake@host`, `DEPLOY_DIR=<tmp>/server/app`,
      `SESPY_PY=<stub>`, `PATH=<stubs>:$PATH`.
    - Stub `ssh` logs argv then runs `bash -c "${@: -1}"` locally. Stub
      `scp` logs argv, strips the `host:` prefix and runs `cp -r`. Stub
      `sudo` exits 1 (Windows ships `C:\WINDOWS\system32\sudo`). Stub
      `git` as today. Stub check_live (`SESPY_PY`) logs argv; on
      `--print-override-names` it prints the two allow-listed names and
      exits 0, otherwise it exits with `$STUB_EXIT`.
    - If `check_live.py` is absent from the repo, steps 4–5 are both
      skipped with one message (no names to fetch); test
      `test_absent_check_live_skips_fetch_and_check`.
    - Invoke the bash from `shutil.which("bash")` (in the env, the bundled
      MSYS `Library\usr\bin\bash.EXE`, not Git Bash); skip the module if
      it is None.

  Tests:
  - `test_bash_syntax` (`bash -n deploy/deploy.sh`);
  - `test_first_deploy_without_existing_sespy` (fake server has no app
    dir; afterwards `sespy/` exists, no `sespy.old`, no
    `sespy.incoming`);
  - `test_uses_incoming_swap` and `test_app_py_uploaded_after_swap` (scp
    log order);
  - `test_logs_moved_into_incoming_before_swap` (a `sespy/logs/feedback.db`
    with known bytes survives byte-identical);
  - `test_recovers_interrupted_swap` (fake server has only `sespy.old/`
    with `logs/feedback.db`: it survives) and
    `test_recovers_deploy_keep_logs`;
  - `test_incoming_removed_before_upload` (a leftover `sespy.incoming/x`
    is gone and not nested);
  - `test_settings_file_created_only_if_absent_with_0644` (an existing
    file is untouched; a new one has the default line);
  - `test_settings_off_skips_fetch` (file says `SESPY_R_DATA_DIR=OFF`: no
    scp of override files, no `--live`);
  - `test_fetch_failure_recorded_not_fatal` (an absent live file appears
    in the `missing.txt` passed to check_live; the run continues to
    check_live);
  - `test_check_live_nonzero_aborts_before_upload`;
  - `test_rollback_passes_warn_only`;
  - `test_skip_env_var_guards_check_live_call` (no check_live call, and
    the reason is echoed);
  - `test_override_names_from_check_live` (the fetch list equals
    `--print-override-names` output);
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

- [ ] **Step 1: Write the test.** Encode MosaicSES's **real calls** and run
  them; do not assert on `inspect.signature` of a module server
  (`@module.server` returns `(id, *args, **kwargs)` with no `__wrapped__`
  in Shiny 1.9.0, so such an assertion can never fail).
  - `test_isa_data_entry_mosaic_call`: inside `test_server` (see
    Environment notes), call exactly MosaicSES's
    `compartments.py:362-367` form,
    `isa_data_entry_server("entry", project_data=rv,
    event_bus=create_event_bus(), translator=None)`, with `rv` a
    `reactive.value(Project(...))`; flush; assert no exception and that
    the module's outputs render. Same for `cld_viz_server("cld",
    project_data=rv, event_bus=bus)`.
  - `test_plain_function_calls_bind`: for plain functions use
    `inspect.signature(f).bind(...)` with MosaicSES's exact arguments:
    `Project.to_dict(p)`, `Project.from_dict(d)`, `ProjectMetadata(...)`
    with the fields `bowtie_bridge.py`/`state.py` pass, and
    `get_regional_seas()`.
  - `test_regional_seas_shape`: `get_regional_seas()[sea]` still has
    `name`, `ecosystem_types` and `common_issues` for every sea
    (MosaicSES `project_setup.py:145` reads `name`).
  - `test_mosaic_import_surface`: every name MosaicSES imports from
    `sespy` still imports. Hard-code the list (from
    `grep "from sespy" MosaicSES/{multises,multises_app}` at the time of
    writing): `sespy.autosave.token_key`, `valid_token`;
    `sespy.regional_seas.get_regional_seas`; `sespy.constants`
    `DA_SITES`, `SPATIAL_SCALES`, `TEMPORAL_SCALES`,
    `ELEMENT_ID_PREFIX`; `sespy.dashboard` `NavItem`, `StepperItem`;
    `sespy.data_structure` `Connection`, `Element`, `IsaData`, `Project`,
    `ProjectMetadata`; `sespy.event_bus` `EventBus`, `create_event_bus`;
    `sespy.i18n.Translator`; `sespy.utils.next_id`;
    `sespy.network.remove_nodes`; and the `sespy.modules.*` server/ui
    pairs imported by `compartments.py:21-41`. If the MosaicSES checkout
    exists at `../MosaicSES`, additionally re-derive the list by regex
    and fail on any name missing from the hard-coded one (so the list
    cannot silently go stale).
  - `test_r_kb_imports_from_repo_under_test`: `import sespy.r_kb` succeeds
    in a subprocess with cwd set to a temp directory and `PYTHONPATH` set
    to the repo under test. The test asserts that `sespy.__file__` is under
    that repo; the stale editable install would otherwise import the main
    checkout.
- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_mosaicses_contract.py -q`.
  Expected: PASS (it guards; it is written after the code exists).
- [ ] **Step 3: Commit** `test(k1): MosaicSES compatibility contract`.

---

### Task 19: e2e

**Files:**
- Create: `tests/test_kb_wizard_e2e.py`
- Modify: `tests/test_wizard_e2e.py` (country codes at :79, :113, :320, :404; row selectors at :86, :120, :360-361, :378, :381, :413 become `#wizard-freeform_{target}_container [data-row="{target}_{i}"]`), `tests/run_e2e.py` (`_child_env` gains `env["SESPY_R_DATA_DIR"] = "off"`)

**Interfaces:**
- Consumes: everything above.
  - Wait for the nav with SESPy's pattern
    `page.wait_for_selector("#sespy_nav_wizard", timeout=60000)` then click
    (`test_wizard_e2e.py:23`). SESPy has no `_e2e_nav.py`; that helper is
    MosaicSES's.
  - `test_wizard_e2e.py:378/381` use `document.getElementById(...)`; they
    become `document.querySelector('#wizard-freeform_{t}_container [data-row="{t}_{i}"]')`.
  - The e2e suite is expected to be red from Tasks 11–12 until this task
    (country codes and row ids change).

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
  Step 6 of the KB e2e asserts in the report preview iframe
  (`page.frame_locator('#report-report_preview iframe')`), not a download.
- [ ] **Step 3: Kill anything on port 8000** first (it reuses stale
  servers; see memory; kill by command line as in Environment notes), then run the full suite detached with
  `Start-Process` + a log, as in the project's long-run practice:
  `micromamba run -n shiny python tests/run_e2e.py`. Wait by polling the
  log in bounded `Start-Sleep` PowerShell calls (a background monitor
  never wakes a subagent); afterwards verify port 8000 is free and
  `git status` is clean.
  Expected: every script passes; the count is the previous 37 + 1.
- [ ] **Step 4: Commit** `test(k1): knowledge-base wizard e2e; wizard e2e on codes and data-row hooks`.

---

### Task 20: Release docs, roadmap edits, upstream drafts, gates

**Files:**
- Modify: `CHANGELOG.md`, `docs/MANUAL.md`, `docs/screenshots/*` (via `tests/make_docs_screenshots.py`), `docs/superpowers/specs/2026-10-17-p1a-link-rules-template-mapper-design.md:85-88`, `docs/parity/R_SYNC.md`, `docs/superpowers/specs/2026-11-09-k1-knowledge-base-parity-design.md`
- Line numbers below are pre-Step-1; Step 1 inserts text above them, so
  locate each edit by its quoted content.
- Modify on branch `docs/r-parity-roadmap`: the umbrella roadmap, with every bullet of spec §9 "Umbrella edits"
- Create: `docs/parity/upstream-drafts/k1-r-issues.md` (4 issue drafts, spec §9)

- [ ] **Step 1: CHANGELOG 1.16.0.** Name K1 and R v1.34.2, and list:
  - the features;
  - the known differences: no max-elements limit; unsaved step text
    discarded by Back; R's recommendation lines deferred to P14;
    countries changed per the §1.1(3) table (governance-driven lists drop
    countries SP2 offered, e.g. Atlantic US, Pacific CN/JP/ID/PH/CL,
    Caribbean FR/NL; DK/FR/NL lose their "(Greenland)"/"(overseas)"
    suffix, which also changes the AI prompt text for those picks); the
    chip caption names the sea in English (no per-sea translations);
    no Select All / Clear All on the country step (selectize optgroups
    instead of R's EU/non-EU buttons); chip matching compares
    whitespace-stripped text;
  - the schema-9 forward-fix rollback policy, and the rollback procedure
    (Task 17: `git worktree add <dir> v1.15.0`, then
    `DEPLOY_REPO_ROOT=<dir> deploy/deploy.sh --rollback` from the
    current checkout);
  - the pre-deploy checklist (no commit): the gitignored
    `deploy/config.env` gains `DEPLOY_MOSAIC_DIR=/srv/shiny-server/MosaicSES`,
    or MosaicSES is never restarted;
  - the post-deploy checklist: worker `python -s` shows 1.16.0; About
    shows shared "R v1.34.2"; MosaicSES `verify_live.py --expect-version
    <v>`, where `<v>` is `__version__` in the deployed
    `MosaicSES/multises/__init__.py` (the file `verify_live.py` reads;
    `multises_app/__init__.py` has no version).
- [ ] **Step 2: MANUAL K1 section and screenshots.** Fix the CHANGELOG
  bullet "R's AI generator also suggests the extension pairs…" and the
  P1a spec lines.
- [ ] **Step 2b: In this repo,** add the §9 P14 note to the
  `R_SYNC.md` row for `functions/report_generation.R` in the v1.31 → v1.33
  table (find it by content; Task 3 inserted a table above it). Also
  correct the spec claims found wrong in the plan review:
  - §4.8: `deploy.sh` does not honour the env override when
    `deploy/config.env` exists (it is sourced after the env);
  - §4.8.5: rollback runs the current `deploy.sh` with
    `DEPLOY_REPO_ROOT` pointing at a worktree of the old tag;
  - §4.10: the MosaicSES version lives in `multises/__init__.py`;
  - §4.3: "SP4 prompt content stays the same for the same picks" is false
    for DK, FR and NL (their names lose the SP2 suffix);
  - §4.3 chip rule 6: the caption is R's `tailored_for` text in the key's own
    casing, the ecosystem part is conditional, and the sea name is
    English;
  - §4.2 / plan Task 6: macaronesia + "Open coast" resolves **exact**;
    only habitats with no macaronesia context fall to `sea_only`;
  - §9: the R_SYNC row reference (by content, not line);
  - §4.9: the prefix rule does **not** pull in `eu_member_state`;
  - §4.9: the `data/` rule does not cover `RUNTIME_INPUTS` in fixture mode;
  - §4.7: the checkbox DOM id is `report-include_regional_context`;
  - §4.3: the container DOM id is `wizard-freeform_{target}_container`
    via `resolve_id`;
  - the macaronesia example: SP1's slug resolves like R, so it is not an
    "unknown slug".
- [ ] **Step 3: Roadmap edits** on `docs/r-parity-roadmap` (checkout via a
  worktree in `C:/Users/arturas.baziukas/AppData/Local/sespy-roadmap`, with
  `-c core.longpaths=true`). Apply every §9 bullet and commit there.
- [ ] **Step 4: Write the upstream drafts file,** including the 69-row
  lookup table generated from `load_k1_fixture("lookup")`.
- [ ] **Step 5: Gates.**
  - The CI unit set (Task 8 Step 5's command, with its ignores).
  - The full e2e (Task 19).
  - MosaicSES: first compare the local `multises/__init__.py`
    `__version__` with laguna's (`ssh … cat
    /srv/shiny-server/MosaicSES/multises/__init__.py`); if the local one
    is behind, `git pull` it (the local checkout has lagged live before).
    Then its unit tests and full e2e with
    `PYTHONPATH=<K1 worktree or checkout>`. Re-grep its pattern selectors
    against the new ids.
  - **v1.15.x read-only check,** as a scratchpad script:
    `git worktree add <scratch>/v115 v1.15.0`; with
    `PYTHONPATH=<scratch>/v115`, load one SESPy and one MosaicSES schema-9
    file; assert the load reports `newer_build` and that autosave refuses
    to overwrite; then `git worktree remove <scratch>/v115`.
  - `micromamba run -n shiny python tests/parity/check_live.py --fetch`
    against laguna (defaults: `--pin tests/parity/r_sync.json`, `--stage`
    = repo root). Expected: exit 0, with drift warnings allowed; exit 3
    means the ssh connection itself failed.
- [ ] **Step 6: Commit** `docs(k1): 1.16.0 release notes, manual, screenshots, roadmap and upstream drafts`.
  Stop here: the merge, tag and deploy need the user's go-ahead.
