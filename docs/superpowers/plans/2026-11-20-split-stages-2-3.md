# Split stages 2–3: sespy-app 1.0.0 and library 1.18.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- Extract the Shiny app into a new repo, `razinkele/sespy-app` (package `sespy_app`, version 1.0.0), with its history.
- Shrink SESPy to a pure library, version 1.18.0.
- Prove both against each other and against MosaicSES 0.9.2 before either is tagged.

No laguna deploy happens here; plan 4 does the cutover.

**Architecture:**
- **Library.** It is built locally first, on branch `feat/split-stage3-library`. It deletes the app files, drops the UI dependencies, pins the consumer API, and moves CI to library-only jobs.
- **App.** It comes from a rehearsed `git filter-repo` run on a fresh clone. One task rewrites the imports and adds the package skeleton, one retargets the tests and CI, and one rewrites the deploy script, which now vendors the pinned library and moves `feedback.db`.
- **Gates.** These run on the split layout: the app (unit + full e2e) and MosaicSES (full suite) run against the shrunk library through `PYTHONPATH`. Only after that do the tags and pushes happen, all of them hand-offs to the user.

**Tech Stack:** Python 3.11+, Shiny for Python 1.7, pytest, Playwright, git-filter-repo (a40bce548d2c, in the `shiny` env), bash deploy scripts, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-19-library-app-split-design.md` (§4, §5.2–5.4, §6, §7, §8 stages 2–3, §9, Appendix A/B). This is plan 3 of 4:
- plan 1 = stage 1 (v1.17.1, live);
- plan 2 = MosaicSES bridge (0.9.2, live);
- plan 4 = cutover deploy, MosaicSES cleanup release, Nid4Ocean re-pin.

## Global Constraints

- **Workspaces.**
  - Library: worktree `C:/Users/arturas.baziukas/AppData/Local/sespy-lib18`, branch `feat/split-stage3-library`, based on `origin/main` @ `4ee72ba` (v1.17.1).
  - App: a fresh clone at `C:/Users/arturas.baziukas/AppData/Local/sespy-app` (outside OneDrive), branch `main`.
  - Every command names its tree.
- **Python.** Only the micromamba `shiny` env (`micromamba run -n shiny …`). No venv, no `pip install`.
- **No editable `sespy-app` in the shared env** before the cutover. *Ruling vs spec §6:* MosaicSES's `release.sh` (0.9.2) refuses to run when `sespy_app` is importable locally and laguna has none, and MosaicSES's local runs would silently switch to `sespy_app`. Combine trees with `PYTHONPATH` only.
- **The split-layout `PYTHONPATH`.** App runs use `PYTHONPATH=<app>;<lib18>`. MosaicSES runs use `PYTHONPATH=<mosaic>;<app>;<lib18>`, with Windows `;` separators.
  - The env's editable `sespy` is a stale monolith that still has `sespy.modules`.
  - Every gate run first prints `sespy.__file__`, `sespy.__version__` and `importlib.util.find_spec("sespy.modules")`, which must be `None`.
- **The agent never** pushes, creates repos, merges, tags or deploys, never uses ssh, and never reads `deploy/config.env`. Each of these is a hand-off, given as a **short single-line** `!` command, because long lines wrap and break when pasted.
- **Never edit a tree while its gate runs.**
- **Versions.**
  - Library `1.18.0` in `pyproject.toml` and `sespy/__init__.py`.
  - App `1.0.0` in `pyproject.toml` and `sespy_app/__init__.py`, which must hold a sed-able line `__version__ = "1.0.0"` (MosaicSES `release.sh` reads it).
- **The library is not on PyPI** (`https://pypi.org/pypi/sespy/json` returns 404). The app depends on it as `sespy[pdf,bayes] @ git+https://github.com/razinkele/SESPy@v1.18.0`. *Ruling vs spec §6 "`sespy[pdf,bayes]==<pinned>`":* an exact-version pin cannot resolve.
- **CHANGELOG ownership.** *Ruling (spec §4.2 vs stage 3):* both repos keep `CHANGELOG.md`.
  - The library's continues with `## 1.18.0`.
  - The app's (the filtered copy, with full history) gets a top note, "from 1.0.0 this is the sespy-app changelog; earlier entries are SESPy's", followed by `## 1.0.0`.
- **No behaviour change** in the app or in saved project files (spec §2 anti-goals). A v1.17 project loads identically.
- **Lint.**
  - Library: `ruff check sespy tests scripts`, no new findings over the 4ee72ba baseline (CI showed 44).
  - App: `ruff check sespy_app tests app.py`, no new findings over the same files at 4ee72ba.
- **Shiny reference.** Read `references/testing.md` and `modules-core.md` from `micromamba run -n shiny shiny skills path shiny-for-python` before touching reactive code or tests (repo CLAUDE.md).

## Rulings (vs spec wording)

1. **App module names.**
   - `sespy/ui_i18n.py` → `sespy_app/i18n.py` (the MosaicSES bridge imports this name).
   - `sespy/ui_r_kb.py` → `sespy_app/kb_reads.py`, so that `r_kb` keeps meaning the library module inside the app.
2. **App test list = spec Appendix A's rule.** It is not "everything outside `library_tests.txt`": `tests/conftest.py` and `tests/_ui_blocker.py` stay library-only. The app also carries `tests/parity/k1_fixtures.py` and `tests/parity/r_fixtures/` for `test_report_regional.py`. These are copies with history; the library keeps its own.
3. **Library deletes its app tests in stage 3.** After the shrink, every remaining test is a library test. `library_tests.txt` and `run_library_tests.py` stay, as the CI no-UI gate.
4. **`test_public_api.py` passes on first run.** It is a pin over names that already exist, not new behaviour. Its RED step is a deliberately misspelled name, run once and then removed.
5. **The app's `deploy.sh` replaces `--rollback`'s old-layout path.** It does app-to-app rollback only. Rolling back across the cutover follows spec §9's manual steps, which plan 4 writes.

## Review Focus

1. **An app import that only works because the monolith is still on the path.** A missed rewrite (`from sespy.modules…`, a `monkeypatch.setattr("sespy.dashboard…")` string, a `sespy/www` path) passes against 1.17.1. Expected: the app suite runs only with `sespy.modules` unimportable. Test: Task 5, the `tests/conftest.py` session guard, plus `test_no_monolith_strings`.
2. **Old workers during the cutover deploy.** A pre-cutover worker still running writes feedback through its old `feedback_store`, recreating `sespy/logs/feedback.db` inside the new library dir. Expected: the DB is never deleted, and after the swap it is rescued to `logs.rescued-<ts>` with a warning. Test: Task 6, `test_old_worker_db_after_swap_is_rescued`.
3. **MosaicSES during the swap.** MosaicSES links `sespy_app` and must never see the shrunk `sespy/` without `sespy_app/`. Expected: `sespy_app/` is swapped in before `sespy/`, and `app.py` is replaced after both. Test: Task 6, `test_swap_order_app_package_first`.
4. **Deploying with the wrong library checkout** (not at the pinned tag, a different `__version__`, or a dirty tree). Expected: abort before upload, with a message naming the expected tag. Test: Task 6, `test_library_root_must_match_pin`.
5. **The library installed without UI deps runs every test, not just the manifest.** Expected: `pip install -e .[test]` pulls in no shiny, htmltools or pyvis, and all of `tests/` passes. Test: Task 2, CI job `unit-tests`, plus `test_dependencies_exclude_ui`.

---

### Task 1: Library: pin the consumer API

**Tree:** `sespy-lib18`.

**Files:**
- Create: `tests/test_public_api.py`
- Modify: `tests/library_tests.txt` (add the file)

**Interfaces:**
- Produces: `tests/test_public_api.py`, with one parametrized test `test_consumer_name_exists(module, name)`. It runs `importlib.import_module(f"sespy.{module}")` and asserts `hasattr`. Names, recorded once from MosaicSES 0.9.2 (`b5daf1e..de94990`) and Nid4Ocean `main` (re-derived 2026-11-20):
  - `constants`: `ELEMENT_ID_PREFIX`, `DA_SITES`, `SPATIAL_SCALES`, `TEMPORAL_SCALES`, `DAPSIWRM_ADJACENCY_RULES`, `normalize_delay`, `CONFIDENCE_OPACITY`, `EDGE_COLORS`, `ELEMENT_COLORS`, `ELEMENT_SHAPES`
  - `data_structure`: `Connection`, `Element`, `IsaData`, `Project`, `ProjectMetadata`, `PROJECT_SCHEMA_VERSION`, `SCHEMA_MIN_READER`, `to_visnetwork`
  - `utils`: `next_id`
  - `network`: `CENTRALITY_METRICS`, `centrality_metrics`, `leverage_scores`, `to_digraph`, `remove_nodes`, `feedback_loops`, `classify_loops`, `intervention_impact`, `causal_paths`, `delay_edge_kwargs`
  - `dynamics`: `token_diffusion`, `isa_to_dynamics_matrix`, `isa_to_numeric_matrix`, `randomize_matrix`, `create_boolean_rules`, `boolean_attractors`
  - `regional_seas`: `get_regional_seas`
  - `autosave`: `token_key`, `valid_token`
  - `i18n`: `set_default`, `get_default`, `load_translations`, `Translator`, `_default_translator`. `_default_translator` is private but written by MosaicSES tests.
- Plus:
  - `test_project_from_dict_exists` asserts `callable(Project.from_dict)`.
  - `test_translations_dir_is_package_data` asserts `(Path(sespy.__file__).parent / "translations" / "core.json").is_file()`.

- [ ] **Step 1: Write the test with one misspelled name** (`"network", "causal_pathz"`). Run `micromamba run -n shiny python -m pytest tests/test_public_api.py -q`. Expected: exactly that case fails.
- [ ] **Step 2: Fix the name; run again.** Expected: all pass. Also run `micromamba run -n shiny python scripts/run_library_tests.py`. Expected: exit 0.
- [ ] **Step 3: Commit** with the message `test(split): pin the library names MosaicSES and Nid4Ocean import`.

---

### Task 2: Library: delete the app; drop UI deps; library-only CI; 1.18.0

**Tree:** `sespy-lib18`.

**Files:**
- Delete (`git rm -r`):
  - `app.py`, `www/`, `deploy/`, `environment.yml`, `docs/MANUAL.md`, `docs/screenshots/`;
  - `sespy/modules/`, `sespy/dashboard.py`, `sespy/browser_token.py`, `sespy/event_bus.py`, `sespy/feedback_store.py`, `sespy/ui_i18n.py`, `sespy/ui_r_kb.py`, `sespy/www/`;
  - every app-side test: the `tests/*.py` entries in `docs/superpowers/plans/split-stage2/filter-repo-paths.txt`, plus `tests/fixtures/bot_*.csv`.
  - Keep `tests/parity/` whole, `tests/fixtures/report_default_golden.html`, `tests/conftest.py`, `tests/_ui_blocker.py`, and `data/`.
- Modify:
  - `pyproject.toml`:
    - version `1.18.0`;
    - description: "SESPy: Python library for DAPSI(W)R(M) social-ecological system modelling, analysis and R SES Toolbox parity (Horizon Europe Marine-SABRES)";
    - `dependencies` minus `shiny`, `htmltools`, `pyvis-optimized`;
    - the `test` extra minus `pytest-playwright`;
    - package data minus `www/*.css`.
  - `sespy/__init__.py`: `__version__ = "1.18.0"`; reword the docstring to the library description.
  - `README.md`: library README, covering install (`pip install "sespy @ git+https://github.com/razinkele/SESPy@v1.18.0"`), the module map, the app pointer (`razinkele/sespy-app`) and consumers.
  - `CHANGELOG.md`: `## 1.18.0`, "SESPy is now a library; the Shiny app moved to razinkele/sespy-app (1.0.0). Removed: sespy.modules, dashboard, browser_token, event_bus, feedback_store, ui_i18n, ui_r_kb, www; shiny/htmltools/pyvis are no longer dependencies."
  - `.github/workflows/ci.yml`:
    - remove the `full-app` and `e2e` jobs;
    - lint becomes `ruff check sespy tests scripts`;
    - `unit-tests` runs `pip install -e .[test]` then `pytest tests/ -q` with its coverage args, minus any app paths or `--ignore` entries that no longer exist;
    - keep `library-no-ui`.
  - `tests/library_tests.txt`: now covers every remaining test file. Drop `test_split_manifest`'s app-test assertions that no longer apply; keep `test_every_entry_exists`.
- Create: `tests/test_dependencies.py`, with `test_dependencies_exclude_ui`. It parses `pyproject.toml` and asserts that no requirement in `dependencies` or any extra is named `shiny`, `htmltools`, `pyvis-optimized` or `pytest-playwright`.

**Interfaces:**
- Consumes: Task 1's `test_public_api.py`, which must stay green.
- Produces: a library tree where `find_spec("sespy.modules") is None`. Tasks 4–7 use it through `PYTHONPATH`.

- [ ] **Step 1: Write `tests/test_dependencies.py`** and run it. Expected: FAIL, naming `shiny`, `htmltools`, `pyvis-optimized` and `pytest-playwright`.
- [ ] **Step 2: Make the deletions and modifications** listed under Files.
- [ ] **Step 3: Verify.**
  - `micromamba run -n shiny python -m pytest tests -q -p no:cacheprovider` (full library suite). Expected: 0 failed.
  - `micromamba run -n shiny python scripts/run_library_tests.py`. Expected: exit 0.
  - `git grep -nE "sespy\.(modules|dashboard|event_bus|browser_token|feedback_store|ui_i18n|ui_r_kb)|sespy/www|shiny" -- sespy scripts .github pyproject.toml`. Expected: nothing except comments that explain the split.
  - Ruff over `sespy tests scripts`. Expected: no new findings.
- [ ] **Step 4: Commit** with the message `release: 1.18.0 — SESPy is a library; the app moved to sespy-app`. **Do not push or tag** (Task 8).

---

### Task 3: App: filter-repo extraction

**Tree:** a new clone at `C:/Users/arturas.baziukas/AppData/Local/sespy-app`.

**Files:** the whole repo, as produced by the rehearsed command. Rehearsed 2026-11-20: 358 commits, no tags, `sespy_app/` laid out as below, no `sespy/` left.

- [ ] **Step 1: Clone and filter.**
  ```
  git clone --single-branch --branch main --no-tags https://github.com/razinkele/SESPy C:/Users/arturas.baziukas/AppData/Local/sespy-app
  cd C:/Users/arturas.baziukas/AppData/Local/sespy-app && git reset --hard 4ee72ba
  micromamba run -n shiny git-filter-repo --force --paths-from-file <sespy-lib18>/docs/superpowers/plans/split-stage2/filter-repo-paths.txt
  ```
  `--paths-from-file` holds the keep-paths and the `old==>new` renames (e.g. `sespy/ui_i18n.py==>sespy_app/i18n.py`). On Windows pass the file with `cygpath -w`.
- [ ] **Step 2: Verify the result.**
  - `git tag -l` is empty.
  - `ls sespy_app` gives `browser_token.py dashboard.py event_bus.py feedback_store.py i18n.py kb_reads.py modules www`.
  - `test -e sespy` fails.
  - `git log --oneline --follow -- sespy_app/i18n.py` reaches `e9c8a53`-equivalent "plain library Translator + resolver hook".
  - `ls tests/*.py | wc -l` is 88, and `tests/parity` holds `k1_fixtures.py r_fixtures`.
  - Record the commit count.
- [ ] **Step 3: No commit.** filter-repo rewrote history. There is no remote; Task 8 adds it.

---

### Task 4: App: package skeleton, absolute imports, both versions in About

**Tree:** `sespy-app`.

**Files:**
- Create: `sespy_app/__init__.py` (docstring + `__version__ = "1.0.0"`), `tests/test_version.py`
- Modify:
  - every `sespy_app/**/*.py` (imports);
  - `app.py` (imports, `TRANSLATIONS_DIR`);
  - `sespy_app/modules/topbar_actions.py:17-18,27,63`;
  - `sespy_app/dashboard.py:27`;
  - `sespy_app/i18n.py:36`;
  - `pyproject.toml`;
  - `.gitignore` (adds `sespy_app/logs/`).

**Interfaces:**
- **Import rewrite rule.** Apply it by hand: 16 bare `from .. import X` lines are not sed-safe.
  - App-layer targets become `sespy_app.<x>`: `event_bus`, `browser_token`, `dashboard`, `feedback_store`, `modules`, `ui_i18n`→`i18n`, `ui_r_kb`→`kb_reads`, `._notify`.
  - Everything else becomes `sespy.<x>`: `data_structure`, `constants`, `input_utils`, `recent_projects`, `r_kb`, `persistent_storage`, `utils`, `claude_backend`, `autosave`, `wizard`, `templates`, `response_register`, `report`, `qsem_import`, `network`, `link_rules`, `kb_suggestions`, `excel_import`, `dynamics`, `bayes`, `bookmark`, `i18n` (library).
  - Mixed lines split, e.g. `topbar_actions.py:18 from .. import feedback_store, r_kb` → `from sespy_app import feedback_store` + `from sespy import r_kb`.
  - `sespy_app/i18n.py:36 from . import i18n as _lib` → `from sespy import i18n as _lib`. Left alone, it would import itself.
- **`app.py`.**
  - `from sespy.<app-layer>` → `from sespy_app.<…>`, using `sespy_app.i18n` and `sespy_app.kb_reads`.
  - `TRANSLATIONS_DIR = Path(sespy.__file__).parent / "translations"` (spec §4.1).
  - The `r_kb.configure(...)` statement stays top-level and starts with `r_kb.configure(`.
- **Versions** (spec §5.4).
  - `dashboard.py` shows `sespy_app.__version__` in the brand.
  - About shows `f"SESPy app {sespy_app.__version__} · sespy library {sespy.__version__}"`.
  - `topbar_actions._REPO_ROOT` stays `parents[2]`; still valid, since `sespy_app/modules/` sits at the same depth.
- **`pyproject.toml`.**
  - name `sespy-app`; version `1.0.0`;
  - description "Research-oriented Shiny for Python UI for the SESPy library (Horizon Europe Marine-SABRES)";
  - packages `sespy_app*`; package data `sespy_app/www/*.css`;
  - dependencies `sespy[pdf,bayes] @ git+https://github.com/razinkele/SESPy@v1.18.0`, `shiny>=1.7`, `htmltools>=0.5`, `pyvis-optimized>=4.4`;
  - extras `test` (pytest, pytest-playwright, pytest-asyncio, pytest-cov) and `lint`;
  - `[tool.pytest.ini_options]` keeps `pythonpath = ["."]`;
  - ruff config is copied.
- **`tests/test_version.py`** (two tests):
  - `test_pyproject_version_matches_dunder` (pyproject == `sespy_app.__version__`);
  - `test_version_line_is_sed_able`: the regex `^__version__ = "\d+\.\d+\.\d+"$` matches a line of `sespy_app/__init__.py`.

- [ ] **Step 1: Write `tests/test_version.py`** and a new `tests/test_about_versions.py::test_about_shows_both_versions`. Build the About content the way `test_topbar_reference_data` / `test_manual` do, and assert that the string contains `SESPy app 1.0.0` and `sespy library 1.18.0`. Run with `PYTHONPATH=<app>;<lib18>`. Expected: import errors (`sespy_app` has no `__init__`).
- [ ] **Step 2: Create `sespy_app/__init__.py`; apply the import rule; make the `app.py`, `dashboard.py`, `topbar_actions.py` and `pyproject.toml` changes.**
- [ ] **Step 3: Verify.**
  - `git grep -nE "^\s*from \.\.? import|^\s*from \.\.[a-z]" -- sespy_app app.py` prints only intra-`modules` relatives (`from ._notify`, `from . import`).
  - `micromamba run -n shiny python -c "import app"`, under the split-layout `PYTHONPATH`, prints nothing and exits 0. The same run prints `find_spec('sespy.modules') is None`.
  - Run the two new tests. Expected: PASS.
- [ ] **Step 4: Commit** with the message `feat(app): sespy_app package — absolute imports onto the sespy library, own version, both versions in About`.

---

### Task 5: App: retarget the tests; guard against the monolith; CI; docs

**Tree:** `sespy-app`.

**Files:**
- Modify: every `tests/*.py`. That means imports and string targets (`"sespy.modules.…"`, `"sespy.dashboard…"`, `sespy/www`, `sespy/logs`), plus `MOSAIC_IMPORTS` in `test_mosaicses_contract.py` retargeted to `sespy_app.*` names, and `tests/run_e2e.py` / `tests/make_docs_screenshots.py` if they name those paths.
- Modify:
  - `test_manual.py`: the MANUAL version line → `sespy_app.__version__`.
  - `docs/MANUAL.md:3`: `**Version 1.0.0 · November 2026**`, with the About wording updated to both versions.
- Create:
  - `tests/conftest.py`: a session-scoped autouse fixture. It fails the run with "the monolith sespy is on the path (sespy.modules importable): set PYTHONPATH to the library checkout" if `importlib.util.find_spec("sespy.modules")` is not None. It also prints `sespy.__file__` and `sespy.__version__` once.
  - `tests/test_no_monolith_strings.py::test_no_monolith_strings`: `git ls-files` over `sespy_app app.py tests .github pyproject.toml deploy` contains no match of `sespy\.(modules|dashboard|event_bus|browser_token|feedback_store|ui_i18n|ui_r_kb)\b|sespy/(www|logs|modules)`. This file and `CHANGELOG.md` are excluded.
- Rewrite: `.github/workflows/ci.yml`. Keep these jobs, all installing the library from the pinned tag through `pip install -e .[test]` (the direct reference):
  - lint (`ruff check sespy_app tests app.py`, mypy on `sespy_app`, non-blocking);
  - `unit-tests` (3.11/3.12);
  - `full-app` (micromamba `environment.yml` + `pip install -e .[test]`);
  - `e2e` (`tests/run_e2e.py`).
- Rewrite:
  - `README.md` (app README: what it is, install, run `shiny run app.py`, depends on the sespy library tag);
  - `CLAUDE.md` (keep the Shiny-skill note; drop library-only notes);
  - `CHANGELOG.md` (top note + `## 1.0.0`, per Global Constraints).

**Interfaces:**
- Consumes: Task 4's package and `sespy_app.__version__`.

- [ ] **Step 1: Write `test_no_monolith_strings.py` and the conftest guard.** Run the unit suite with the split-layout `PYTHONPATH`. Expected: the strings test FAILS, listing the files to retarget. Separately run with no `PYTHONPATH`. Expected: the conftest guard aborts with its message.
- [ ] **Step 2: Retarget the tests; rewrite the CI, README, CLAUDE.md and CHANGELOG; update the MANUAL line.**
- [ ] **Step 3: Verify.** Run, with the split layout and the version line printed: `micromamba run -n shiny python -m pytest tests -q -p no:cacheprovider --ignore-glob="*e2e*" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`. Detach it with Start-Process through `micromamba.bat run` and poll in bounded calls. Expected: 0 failed. Then run ruff. Expected: no new findings.
- [ ] **Step 4: Commit** with the message `test(app): tests, CI and docs target sespy_app; guard against the monolith on the path`.

---

### Task 6: App: deploy vendors the pinned library and moves feedback.db

**Tree:** `sespy-app`.

**Files:**
- Modify: `deploy/deploy.sh`, `deploy/config.env.example`, `tests/test_deploy_script.py`

**Interfaces:**
- **New required setting** `DEPLOY_LIBRARY_ROOT`, an absolute path to a SESPy library checkout, set in env or `config.env`.
- **Before staging, abort with a clear message unless all of these hold:**
  - `git -C "$LIB" describe --tags --exact-match` equals `v$PIN`;
  - `git -C "$LIB" status --porcelain` is empty;
  - `sespy/__init__.py`'s `__version__` equals `$PIN`.
  - `PIN` is parsed from the app's `pyproject.toml` direct reference (`@v(\d+\.\d+\.\d+)`).
- **Stage:**
  - `RUNTIME=(app.py sespy_app data www environment.yml pyproject.toml README.md CHANGELOG.md)` + `docs/MANUAL.md` + `docs/screenshots/`;
  - plus `cp -R "$LIB/sespy" "$STAGE/sespy"`;
  - strip `__pycache__`/`*.pyc`, `$STAGE/sespy/logs` and `$STAGE/sespy_app/logs`.
- **Pre-flight.** `CHECK_LIVE="$LIB/tests/parity/check_live.py"` with `PYTHONPATH=$LIB`. The settings-parse functions and `DEFAULT_R_DATA_DIR` are unchanged. `test_deploy_default_matches_app_constant` now compares against `sespy_app.kb_reads.LAGUNA_R_DATA_DIR`.
- **Logs** (spec §9).
  - **Recovery prologue:** generalise `rescue_logs` to take the package name (`sespy_app` from now on). Also handle a `sespy.old`/`sespy.incoming` from a pre-cutover run.
  - **One-time migration**, before the swap: if `sespy/logs/feedback.db` exists and `sespy_app/logs/feedback.db` does not, it moves into `sespy_app.incoming/logs/`. If **both** exist, abort before any swap: "two feedback DBs: merge $APP_DIR/sespy/logs and $APP_DIR/sespy_app/logs by hand".
  - **After the swap:** if the new `sespy/logs` exists (an old worker recreated it), move it to `logs.rescued-<ts>` with a warning. Never delete it.
- **Swap order.** Each step is a rename pair, as today:
  1. `sespy_app.incoming` → `sespy_app` (MosaicSES then resolves `sespy_app` with the still-old `sespy/`, which is compatible because 1.17.1 ⊇ the 1.18.0 library API);
  2. `sespy.incoming` → `sespy`;
  3. the other runtime items by scp;
  4. settings file and `restart.txt`;
  5. MosaicSES `restart.txt` (`DEPLOY_MOSAIC_DIR`, unchanged).
- **`--rollback`:** app-version to app-version. `DEPLOY_REPO_ROOT` points at an older sespy-app worktree, `DEPLOY_LIBRARY_ROOT` at its pinned library tag, and the live check is warn-only as today.
- **Harness** (`tests/test_deploy_script.py`):
  - The fake setup builds a **second tree**, a fake library root: a git repo tagged `v<PIN>` with `sespy/__init__.py` and a stub `tests/parity/check_live.py`.
  - The fake server starts in the **old layout** (`sespy/` with `modules/` and `logs/feedback.db`) for the cutover tests, and in the new layout for the repeat-deploy tests.
  - The existing 42 tests are kept and adapted.

- [ ] **Step 1: Write the new failing tests:**
  - `test_library_root_must_match_pin`: parametrized over wrong tag / dirty / version mismatch. Expect exit ≠ 0, nothing uploaded, and the message names `v<PIN>`.
  - `test_cutover_moves_feedback_db_once`: in the old layout, after the deploy, `sespy_app/logs/feedback.db` has the original bytes and `sespy/logs` is absent.
  - `test_two_feedback_dbs_abort_before_swap`.
  - `test_swap_order_app_package_first`: in the stub log, the `mv -T sespy_app.incoming sespy_app` command precedes `mv -T sespy.incoming sespy`, and both precede the `app.py` scp.
  - `test_old_worker_db_after_swap_is_rescued`: use `STUB_SSH_PRELUDE` to create `sespy/logs/feedback.db` after the swap command. Expect `logs.rescued-*` to exist and nothing deleted.
  - `test_repeat_deploy_keeps_app_db`: in the new layout, the DB survives byte-identical.
  - `test_check_live_runs_from_library_root`: the stub log shows `$LIB/tests/parity/check_live.py`.
  
  Run `micromamba run -n shiny python -m pytest tests/test_deploy_script.py -q`. Expected: the new tests FAIL.
- [ ] **Step 2: Implement** per Interfaces. Keep every existing guarantee: abort before upload on a failed check, rename-pair swap, settings file, and the MosaicSES restart.
- [ ] **Step 3: Run the deploy tests.** Expected: all pass (bash available). Then run `bash -n deploy/deploy.sh`. Expected: exit 0.
- [ ] **Step 4: Commit** with the message `feat(deploy): vendor the pinned sespy library; app package swapped first; feedback.db moves to sespy_app/logs once`.

---

### Task 7: Gates on the split layout (no tags yet)

**Trees:** `sespy-lib18` (Task 2 HEAD), `sespy-app` (Task 6 HEAD), MosaicSES at `de94990` (v0.9.2) in a fresh worktree `C:/Users/arturas.baziukas/AppData/Local/mosaicses-split-gate`.

- [ ] **Step 1: Pre-flight.** Nothing on port 8000. No orphan `python -` processes. Note free RAM. Run nothing else concurrently.
- [ ] **Step 2: Library.** Run the full `tests/` with `SESPY_BLOCK_UI=1 PYTHONPATH=<lib18>` via `scripts/run_library_tests.py`, then plain `pytest tests`. Expected: both 0 failed.
- [ ] **Step 3: App.** Run unit, then full e2e (`tests/run_e2e.py --port 8000`) with `PYTHONPATH=<app>;<lib18>`.
  - The conftest guard proves the test process.
  - For the e2e server, check that `run_e2e.py`'s server log, or a one-off `curl` of the About content, shows `sespy library 1.18.0`.
  - Expected: unit 0 failed; e2e all pass except the known `test_intervention_e2e.py` flake (rerun it alone, 3×).
- [ ] **Step 4: MosaicSES on the split layout** (spec §8 stage 4, deferred here by plan 2 Ruling 3).
  - Run `PYTHONPATH=<mosaic-split-gate>;<app>;<lib18> micromamba run -n shiny python -c "from multises_app import sespy_ui; print(sespy_ui.UI_PACKAGE)"`. Expected: `sespy_app`.
  - Then run the full MosaicSES suite. Expected: reds only from plan 2's baseline set (the topbar modal race, equity editor, beforeunload, composite timer, file flows, heatmap_card, risk knot); rerun any other red 3×.
  - Assert also: `sespy_ui.set_default is sespy.i18n.set_default`, and `(Path(sespy_app.__file__).parent / "www" / "sespy-skin.css").is_file()`.
- [ ] **Step 5: Round-trip.** Load `data/sample_ses.json` and one saved v1.17 project into the split-layout app (`Project.from_dict` → `to_dict`), and through MosaicSES's example loader. Expected: equal dicts and no warnings.
- [ ] **Step 6: Record** all results in the ledger. Any new red stops the plan before Task 8.

---

### Task 8: Hand-offs: repos, PRs, tags (user runs; no deploy)

**Trees:** both. Each is a short one-line `!` command for the user, in this order.

- [ ] **Step 1: Library PR.**
  - The user pushes `feat/split-stage3-library` and opens a PR into SESPy `main`.
  - Wait for CI: lint, unit 3.11/3.12 and `library-no-ui` green; the `full-app` and `e2e` jobs are gone.
  - The user merges, then tags `v1.18.0` on the merge commit and pushes the tag.
  - I verify that the merge tree equals Task 2's HEAD (`git diff --stat`).
- [ ] **Step 2: App repo.**
  - The user creates `razinkele/sespy-app` (`gh repo create razinkele/sespy-app --private` or `--public`; their choice).
  - I run `git remote add origin https://github.com/razinkele/sespy-app.git` locally; the user pushes `main`.
  - App CI now resolves the `@v1.18.0` direct reference. Wait for green, apart from the known e2e intervention flake.
- [ ] **Step 3: App tag.** The user tags `v1.0.0` and pushes it.
- [ ] **Step 4: Hand-off note for plan 4:**
  - cutover deploy from a `v1.0.0` worktree with `DEPLOY_LIBRARY_ROOT=<v1.18.0 worktree>`;
  - spec §9's cross-layout rollback steps (remove `$APP_DIR/sespy_app/` after moving `feedback.db` back);
  - MosaicSES cleanup release (drop the fallback, `sespy>=1.18`, the `app` extra);
  - Nid4Ocean re-pin to `@v1.18.0`;
  - worktree cleanup: `sespy-stage1`, `sespy-v1171`, `sespy-split`, `sespy-fr-rehearsal`.
