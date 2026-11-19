# SESPy library / sespy-app split: design

Date: 2026-11-19 · Status: draft for approval · Baseline: `origin/main` @ `0c38fbb` (SESPy v1.17.0, schema 9, R pin v1.35.6)

## 1. Intent

SESPy becomes a **pure Python library** for social-ecological system (SES) modelling. Other applications build on it:
- Nid4Ocean DST: offshore-wind nature-inclusive-design assessment, using interventions and delay-link analysis;
- MosaicSES;
- future apps.

The current Shiny for Python app moves to a **new repository, `sespy-app`**. It continues as a **research-oriented UI**, developed on its own schedule. It is not a copy of the stakeholder-facing R SES Toolbox.

Why:
- Consumers want SESPy's model, analysis and R-parity knowledge base without pulling in Shiny, htmltools and pyvis.
- The UI should be able to change without a library release, and the reverse.

Nid4Ocean shows the problem today. It pins `sespy @ git+…@v1.8.0` and gets the whole Shiny stack, yet uses only `data_structure`, `constants`, `network` and `dynamics`.

## 2. Goals, non-goals, anti-goals

**Goals**
1. **Library dependencies.** `pip install sespy` installs no shiny, htmltools or pyvis. Every library module imports and runs without them.
2. **App repository.** A new repo, `razinkele/sespy-app`, holds the app (package `sespy_app`). It keeps the git history of the files it takes over and depends on a pinned `sespy` library version.
3. **The live site.** laguna.ku.lt/SESPy keeps working and is deployed from sespy-app.
4. **MosaicSES.** It keeps working through the cutover in both directions (deploy and rollback), with no broken window.
5. **Nid4Ocean.** It can re-pin to the library release and drop the Shiny stack.

**Non-goals** (this split only does what the split forces; each item goes on the follow-up list, §11):
- moving UI strings (`core.json`) out of the library;
- re-cutting matplotlib, openpyxl, python-docx, reportlab, jinja2 or anthropic into extras;
- deleting dead code (`claude_session_import.py`, the `prod`/igraph extra);
- moving pure-but-UI-only helpers (`autosave`, `recent_projects`, `bookmark`, `wizard`, `claude_backend`);
- any feature work, including #41 evidenced polarity. #41 resumes after the split, split by layer.

**Anti-goals** (failure even if it "works"):
- Behaviour changes in the app or in saved project files. A project saved before the split loads identically after it, in both the app and MosaicSES.
- A library that still reaches Shiny lazily, through a call path the import tests don't exercise.
- Compatibility shims inside the library that re-export app modules (`sespy.modules` → `sespy_app.modules`). The library must not know the app exists.
- Losing the server-owned feedback database during the cutover deploy.

## 3. Decided (by the user)

- SESPy is the library. The app moves to a new repo named `sespy-app`, as a research UI that depends on the library.
- The app's history is split out with `git filter-repo`.
- laguna.ku.lt/SESPy stays live and is deployed from sespy-app.
- The library keeps SESPy's version line. Its first split release is **1.18.0**. The app gets its own version line.
- MosaicSES depends on the library, and on sespy-app **optionally**.
- Nid4Ocean uses the library only. It has no compatibility constraint, since it is at an early stage.
- The split happens before #41.
- Standing rule: the user runs every push, merge, repo creation, tag and deploy, as `!` commands. No ssh. `deploy/config.env` is never read.

## 4. Where things go

### 4.1 Stays in the library (`razinkele/SESPy`, package `sespy`)

- **Core models and analysis:** `constants`, `data_structure`, `network`, `dynamics`, `bayes`, `utils`, `input_utils`.
- **Storage, import and R parity:**
  - `persistent_storage`, `excel_import`, `qsem_import`;
  - `regional_seas` (+ `regional_seas.json`);
  - `r_sync`, `r_kb` (minus `add_reads`; see §5.2), `r_connection_kb`, `connection_scorer`, `kb_suggestions`, `kb_report`;
  - `r_template_mapper`, `r_template_catalogue` (a dev tool: not public API, works only from a repo checkout), `templates/`.
- **Reports and registers:** `report`, `response_register`, `response_reports`, `stakeholders`, `stakeholder_reports`.
- **Kept for this split** (pure, used by the app; see the non-goals): `wizard`, `claude_backend`, `bookmark`, `autosave`, `recent_projects`, `claude_session_import`, `link_rules`.
- **`i18n`, plain core only** (see §5.1).
- **Package data:**
  - `data/r_kb/`;
  - `templates/**.json`;
  - **all of `translations/`, including `core.json`.**
  - Library code returns keys and looks one up itself (`link_rules` → `entry.off_rule_link`).
  - The app and MosaicSES read the directory via `Path(sespy.__file__).parent / "translations"`. That keeps working unchanged.
- **Repo-level:**
  - `tests/parity/` (fixtures, `r_sync.json` pin, `check_live.py`), `scripts/` (sync and R capture scripts), `docs/parity/`;
  - `LITERATURE/`, `.superpowers/`;
  - the parity spec and plan docs.

### 4.2 Moves to sespy-app (package `sespy_app`)

- `app.py` (repo root of sespy-app).
- `sespy/modules/**` → `sespy_app/modules/**`, including `_notify.py`.
- `sespy/dashboard.py`, `sespy/browser_token.py`, `sespy/event_bus.py` → `sespy_app/`.
- `sespy/www/*.css` → `sespy_app/www/` (served by `dashboard._SKIN_DEP`).
- The reactive i18n layer → `sespy_app/i18n.py` (see §5.1).
- `r_kb.add_reads` → `sespy_app` (see §5.2).
- `sespy/feedback_store.py` → `sespy_app/feedback_store.py` (see §5.3).
- **Repo-level:**
  - `www/` (static root), `data/sample_ses.json` + `data/*.qsem` (copied: the library tests need them too);
  - `docs/MANUAL.md`, `docs/screenshots/`, `CHANGELOG.md` (the app's from now on);
  - `deploy/`, `environment.yml`;
  - the app tests (§7) and `tests/make_docs_screenshots.py`, `tests/run_e2e.py`, `tests/_testmode.py`, `tests/fixtures/bot_*.csv`.

The app's imports change from relative to absolute: `from ..data_structure import …` becomes `from sespy.data_structure import …`. The package moves one level, so `topbar_actions._REPO_ROOT` (`parents[2]`) must be re-derived. It still has to find `docs/MANUAL.md` and `CHANGELOG.md` beside the package.

## 5. Decoupling inside the library

All of this lands in **stage 1** (§8), inside the current repo, before anything moves.

### 5.1 i18n

**Today**
- `sespy.i18n.Translator` is a dataclass whose `language` is a `shiny.reactive.Value`.
- `get_default()` reads the current Shiny session.
- `link_rules.off_rule_message(translator=None)` lazily calls `sespy.i18n.t`, which pulls in Shiny.

**After stage 1**
- **`sespy.i18n` (library):**
  - `load_translations`, `SUPPORTED_LANGUAGES`, `detect_initial_language`;
  - a plain `Translator` whose lookup and fallback are identical to today's, and whose language is a plain attribute;
  - a process-wide default (`set_default` / `get_default` / `t`) with **one injection point**: a resolver hook that the app sets, so `t()` returns the session-scoped translator when one exists.
  - It imports no shiny.
- **`sespy_app.i18n` (app; in stage 1 still inside the repo, e.g. `sespy/ui_i18n.py`, moved in stage 2):**
  - `ReactiveTranslator(Translator)` holding the `reactive.Value`, `set_language` with `reactive.isolate()`;
  - the session-clone logic now in `get_default()`, which installs itself via the library's resolver hook.
- Every UI module, `dashboard`, `app.py` and the MosaicSES-facing names (`Translator`, `load_translations`, `set_default`) use the app-side module.
- **Behaviour must not change:**
  - per-session language;
  - process-wide fallback;
  - the per-session reset that broke once before (memory `sespy-translator-global-lang-reset`).

### 5.2 r_kb

- `add_reads()` (it takes a session `reactive.Value[frozenset]`) moves to the app. Its callers are `report_export` and the wizard.
- `DEFAULT_OVERRIDE_DIR = "/srv/shiny-server/marinesabres/data"` and the `server_settings.env` lookup relative to `configure(app_dir)` leave the library's defaults:
  - the app passes the override dir and app dir in;
  - the library takes them as parameters, with the `SESPY_R_DATA_DIR` env var still honoured.
- The vendored-KB loading, `Snapshot`, `ALLOW_LIST` and the registry stay in the library unchanged.

### 5.3 feedback_store

- It writes `Path(__file__).parent/"logs"/"feedback.db"`, inside the package. That is impossible from site-packages.
- It moves to the app (its only user) and keeps a package-relative path there (`sespy_app/logs/feedback.db`).
- The deploy's preserve-logs dance moves with it (§9).

### 5.4 Version

- `sespy.__version__` and `min_sespy_version` / `SCHEMA_MIN_READER` keep meaning **the library version**. Keeping the version line makes this free.
- The app gets `sespy_app.__version__`, starting at **1.0.0** (my call).
- About shows both versions, e.g. "SESPy app 1.0.0 · sespy library 1.18.0". The brand in `dashboard` shows the app version.
- `test_manual.py` retargets the MANUAL version line to `sespy_app.__version__`.
- Each repo gets a test asserting its `pyproject` version equals its `__version__`. Today they are duplicated with no check.

### 5.5 Stage-1 gate: prove the library is Shiny-free

- The existing subprocess "imports without shiny" tests aren't enough, because the leaks are lazy and fire only when called.
- **Local run:** the library-side unit suite runs with an import blocker that makes `import shiny`, `htmltools` or `pyvis` raise. It is a pytest plugin or conftest active only for that run. No new environment is created (the machine rule is a single `shiny` micromamba env).
- **CI:** a job installs the library without those three packages and runs the same suite.
- **The suite:** every test classified "core" in §7.

## 6. Packaging

**Library `pyproject.toml`**
- version `1.18.0`. The description and the `sespy/__init__.py` docstring are reworded from "Shiny for Python port…" to a library description.
- `dependencies` = today's list **minus** `shiny`, `htmltools`, `pyvis-optimized`. Everything else stays a hard dependency for this split.
- Extras `pdf`, `bayes`, `test` (without playwright), `lint` unchanged.
- Package data: `www/*.css` dropped, the rest unchanged.

**sespy-app `pyproject.toml`**
- name `sespy-app`, package `sespy_app`.
- dependencies:
  - `sespy[pdf,bayes]==<pinned>` (exact pin; the app is released against one library version);
  - `shiny>=1.7`, `htmltools>=0.5`, `pyvis-optimized>=4.4`.
- package data: `www/*.css`.
- `environment.yml` (pyvis from the razinka channel) moves with the app.

**Local development**
- The `shiny` env already has SESPy installed editable from the main checkout (metadata shows a stale 1.14.4).
- sespy-app gets its own editable install into the same env. The library stays editable from its checkout.
- Per the machine rule, no venvs. The builder gives the user the exact install commands to run; I don't install anything.

## 7. Tests and CI

The split follows the survey's classification.

**Library**
- core-unit (≈45 files): `test_data_structure`, `test_network`, `test_dynamics`, schema tests, `r_kb*`, `k1_sync`, parity, …
- These tests currently import one UI helper and **are split**, with the UI half moving to the app:
  - `test_network` (`build_loop_payload`);
  - `test_qsem_import` (`parse_upload`);
  - `test_templates` (`MAX_TEMPLATES`);
  - `test_wizard` and `test_connection_polarity` (`_dedup_accepted`).
- **New `test_public_api.py`.** It imports every name the known consumers use, recorded once from:
  - the MosaicSES `multises/` imports listed in the survey;
  - Nid4Ocean's `network` / `dynamics` / `constants` / `data_structure.to_visnetwork`.
  
  It pins them, so a library refactor can't silently break a consumer.
- **CI:** lint (ruff on `sespy tests scripts`), plus unit tests on 3.11/3.12 without UI deps (§5.5).

**sespy-app**
- app-unit tests (`test_server` based, `sespy_app` imports), `test_manual`, `test_skin_card_header`, `test_no_deprecations`, `test_deploy_script`;
- all e2e scripts and `run_e2e.py`;
- `test_mosaicses_contract.py`, whose `MOSAIC_IMPORTS` is retargeted at `sespy_app.*`;
- **CI:** lint, unit, the full-app job (micromamba `environment.yml`), and e2e. The library is installed from its pinned git tag.

The tests rely on `pythonpath=["."]` for `app`, `scripts` and `_testmode`, and on `test_k1_sync` importing another test file. Each repo keeps whichever of these it still needs.

## 8. Stages

**Stage 1: decouple in place.** Ships as an ordinary SESPy release (**1.17.1**), with no consumer change and no file moves across packages.
- Does: §5.1 i18n split, §5.2 r_kb, the §5.4 version-equality test, §5.5 gate.
- `feedback_store` stays put in this stage.
- Normal SESPy gates (full unit + full e2e), deployed as usual. MosaicSES is unaffected because names keep working in the monolith.

**Stage 2: make sespy-app.** Done in a fresh clone **outside OneDrive** (e.g. `AppData/Local/sespy-app-split`).
1. Run `git filter-repo` with `--path` for the moved files and `--path-rename sespy/modules/:sespy_app/modules/` (and the other renames), so module history follows. `git-filter-repo` is already in the `shiny` env.
2. In one commit on top:
   - absolute imports;
   - `pyproject`, `__version__ = "1.0.0"`, `_REPO_ROOT`, the feedback store, and both-versions About;
   - deploy (§9);
   - test retargeting;
   - the README.
3. Gates: app unit + full e2e, against the stage-1 library installed editable.

**Stage 3: shrink the library.** On a branch of SESPy:
- delete the moved files; this keeps full history, with no rewrite;
- drop the UI deps and www package data, and split the 5 mixed tests;
- add `test_public_api.py` and the README / CHANGELOG / `__init__` wording;
- release **1.18.0**.
- sespy-app pins `sespy==1.18.0` and releases **1.0.0**.

**Stage 4: consumers.**
1. **MosaicSES bridge release.** Ships first, before any laguna change:
   - its UI imports try `sespy_app.*` and fall back to `sespy.*`;
   - its deploy symlinks `sespy_app` when it exists;
   - `pyproject`: `sespy>=1.18` (for `multises`), optional extra `app = ["sespy-app>=1.0"]`;
   - its `release.sh:80-88` check compares both versions.
2. **Cutover deploy** of sespy-app to laguna (§9).
3. **MosaicSES cleanup release:** drop the fallback.
4. **Nid4Ocean:** re-pin `[ses]` to `sespy @ git+https://github.com/razinkele/SESPy@v1.18.0`. Its tests use names `test_public_api.py` pins.

**Done when:**
- laguna serves sespy-app 1.0.0 on library 1.18.0;
- MosaicSES live runs on both packages;
- a saved v1.17 project round-trips in both apps;
- Nid4Ocean's `[ses]` install contains no shiny;
- library CI is green without UI deps.

## 9. Deploy and cutover

**How the library reaches laguna**
- The server env isn't writable and the app runs from its app dir (memory `laguna-env-not-writable-user-site-trap`). So **no `pip install` on the server.**
- sespy-app's `deploy.sh` vendors the pinned library: it takes `DEPLOY_LIBRARY_ROOT`, a library checkout.
- It checks that the checkout's `sespy.__version__` equals the app's pin and that it sits on that tag. Then it stages `sespy/` beside `sespy_app/` and `app.py`.
- The pre-flight runs `tests/parity/check_live.py` **from that library checkout**, because `tests/parity/` is not installed.
- Shipped tree: `app.py`, `sespy/`, `sespy_app/`, `data/`, `www/`, `environment.yml`, `pyproject.toml`, README, CHANGELOG, MANUAL, screenshots.

**feedback.db**
- The live DB is at `$APP_DIR/sespy/logs/feedback.db`.
- The cutover deploy moves it, once, to `$APP_DIR/sespy_app/logs/`. The preserve dance targets the new path from then on.
- The script refuses to continue if it finds DBs at both paths.

**Order**
1. MosaicSES bridge release is live (works on old and new layout).
2. sespy-app deploy: the app is switched; MosaicSES now picks up `sespy_app` through the symlink and touches `restart.txt` as today.
3. Verify: About shows both versions; MosaicSES's live check; a project load in each.

**Rollback**
- Re-deploy SESPy v1.17.1 with the existing `deploy.sh --rollback` from a v1.17.1 worktree.
- The MosaicSES bridge falls back to `sespy.*`.
- `feedback.db` is moved back by the same rule in reverse. The rollback path must handle it; the builder adds that to the old-layout rollback instructions rather than editing the v1.17.1 script.

## 10. Repositories and commands the user runs

- **`gh repo create razinkele/sespy-app`**: private or public is the user's choice when running it.
- The push of the stage-2 result, the library 1.17.1 / 1.18.0 and app 1.0.0 tags, the MosaicSES and Nid4Ocean pushes, and every deploy.
- All are given as single-line `!` commands at the point they're needed.
- **Open branches in SESPy** not merged to `origin/main`:
  - `docs/evidenced-polarity`, `docs/r-parity-roadmap`, `docs/p2-design`, `docs/mosaicses-allowlist-token`, `docs/spinner-smoke-results`, `backup/pre-rebase-2026-08-25`.
  - All are docs or backups. They stay in the library repo.
  - #41's UI half is re-homed when #41 resumes.

## 11. Follow-ups (not in this split)

- Move UI strings (`core.json`) to the app; the library keeps the R-vendored module files plus the few keys it looks up.
- Move `autosave` / `recent_projects` / `bookmark` / `wizard` / `claude_backend` to the app if nothing else uses them. MosaicSES uses `autosave.token_key`.
- Re-cut heavy optional deps into extras (`reports`, `excel`, `ai`); delete `claude_session_import` and the `prod` extra.
- Make `r_template_catalogue`'s repo-path assumptions explicit (move it to `scripts/`).
- #41 evidenced polarity, split by layer: review-round-2 findings B1–B11.

## 12. Left to the builder

- The exact resolver-hook API in §5.1, as long as the behaviours listed there hold.
- The `filter-repo` path list (derived from §4.2) and commit layout within each stage.
- How the import blocker is wired (§5.5).
- Wording of READMEs, CHANGELOG entries and the About line.
