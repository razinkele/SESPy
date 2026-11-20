# Split Stage 1: decouple the library in place (SESPy 1.17.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every library-side SESPy module and test import and run with shiny, htmltools and pyvis absent. No file moves between packages yet. Ship as SESPy 1.17.1.

**Architecture:**
- The reactive parts of `sespy.i18n` and `sespy.r_kb` move into two new app-layer modules, `sespy/ui_i18n.py` and `sespy/ui_r_kb.py`. Stage 2 moves them into `sespy_app/`.
- The library keeps a plain `Translator` and a resolver hook. Importing `ui_i18n` installs the hook, so session-scoped translation keeps working.
- The laguna data path leaves `r_kb`.
- A blocker-backed runner proves the library suite is Shiny-free.

**Tech Stack:** Python 3.11+, Shiny for Python 1.7, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-19-library-app-split-design.md` (§5, §7, §8 stage 1). This is plan 1 of 4. Plans 2–4 cover the MosaicSES bridge, stages 2–3, and the cutover.

## Global Constraints

- **Baseline:** `origin/main` @ `0c38fbb` (v1.17.0). Work in a new worktree outside OneDrive on branch `feat/split-stage1`.
- **Python:** only the micromamba `shiny` env, via `micromamba run -n shiny …`. Never create a venv. Never `pip install`.
- **Running python.exe directly** loses DLLs (WeasyPrint's `OSError`), so every command goes through `micromamba run`.
- **The agent never** pushes, merges, tags or deploys, never uses ssh, and never reads `deploy/config.env`.
- **No behaviour change** in the app or in saved project files (spec §2 anti-goals).
- **No file moves across packages** in this stage. New app-layer modules live in `sespy/` with the `ui_` prefix.
- **The library must not re-export app-layer names:** `sespy/i18n.py` and `sespy/r_kb.py` never import `ui_i18n` / `ui_r_kb`.
- **App-layer import rule:** every file under `sespy/modules/`, plus `sespy/dashboard.py` and `app.py`, imports translator names **only** from `sespy.ui_i18n` (or `..ui_i18n`), never from `sespy.i18n`. Stage 2 then renames one module.
- **`sespy.i18n._default_translator` keeps its name.** MosaicSES's tests write it.
- **Version:** `1.17.1` in both `pyproject.toml` and `sespy/__init__.py`. `docs/MANUAL.md` line 3 becomes `**Version 1.17.1 · November 2026**`.
- **Lint:** `ruff check sespy tests app.py scripts` must stay clean (line length 120).
- **Shiny reference:** read `references/reactivity.md` and `testing.md` from `micromamba run -n shiny shiny skills path shiny-for-python` before touching reactive code (repo CLAUDE.md).

## Review Focus

1. **Two concurrent sessions with different languages.** Switching language in one must not change the other or the process default. Test: Task 2, `test_sessions_are_isolated`.
2. **Import-time static UI** (`app.py` calls `T.t("ui.app.title")` at module load, where no session exists, but the resolver is installed). It must return the process default's text. Test: Task 2, `test_resolver_outside_session_returns_process_default`.
3. **`t()` before any `set_default`,** with and without the resolver installed. It must return the key itself. Test: Task 2, `test_t_without_default_returns_key`.
4. **Local dev with no `server_settings.env`** and the laguna default path absent. The registry must serve the vendored snapshot without raising. Test: Task 3, `test_missing_default_dir_serves_vendored`.
5. **MosaicSES-shaped usage:**
   ```python
   from sespy.ui_i18n import Translator, load_translations, set_default
   set_default(Translator(...))
   ```
   Inside a session, `get_default()` returns a reactive clone, and writing `sespy.i18n._default_translator` directly still takes effect. Test: Task 2, `test_mosaicses_usage_shape`.

---

### Task 1: Shiny-free gate infrastructure and version check

**Files:**
- Create: `tests/conftest.py`, `tests/library_tests.txt`, `scripts/run_library_tests.py`, `tests/test_split_manifest.py`, `tests/test_version.py`

**Interfaces:**
- Produces:
  - **The env var `SESPY_BLOCK_UI=1`.** When set, `tests/conftest.py` inserts a `sys.meta_path` finder at position 0. For any module whose top-level name is in `("shiny", "htmltools", "pyvis")`, the finder raises `ModuleNotFoundError(f"blocked: {name}", name=name)`. It also first deletes already-imported entries for those names from `sys.modules`. When the variable is unset, the conftest does nothing.
  - **`tests/library_tests.txt`:** one repo-relative path per line, `#` comments allowed. It lists every library test file from spec Appendix A ("core-unit"), plus `tests/test_version.py`, `tests/test_split_manifest.py` and the directory `tests/parity`.
    - Leave out `test_feedback_store.py`; it goes to the app later.
    - Include the split-test library halves `test_network.py`, `test_qsem_import.py`, `test_templates.py`, `test_wizard.py`, `test_connection_polarity.py` and `test_i18n.py`. Task 4 and Task 2 make them clean.
  - **`scripts/run_library_tests.py`:**
    - `main(argv: list[str] | None = None) -> int`.
    - Reads `tests/library_tests.txt`.
    - Runs `python -m pytest -q -p no:cacheprovider <paths> <argv>` in a subprocess, with env `SESPY_BLOCK_UI=1` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. The second is needed because shiny's autoloaded pytest plugin imports shiny before any conftest runs.
    - Returns pytest's exit code. `if __name__ == "__main__": sys.exit(main())`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_version.py
import tomllib
from pathlib import Path
import sespy

def test_pyproject_version_matches_dunder():
    data = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == sespy.__version__

# tests/test_split_manifest.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def _entries():
    lines = (ROOT / "tests" / "library_tests.txt").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]

def test_every_entry_exists():
    missing = [e for e in _entries() if not (ROOT / e).exists()]
    assert missing == []

def test_no_e2e_or_app_tests_listed():
    assert not [e for e in _entries() if "e2e" in e or e.endswith(("test_feedback_store.py", "test_k1_wiring.py"))]

def test_blocker_blocks_shiny_in_a_child_run(tmp_path):
    # a throwaway test file that imports shiny must fail under the runner's env
    import os, subprocess, sys
    probe = tmp_path / "test_probe.py"
    probe.write_text("def test_p():\n    import shiny\n", encoding="utf-8")
    env = {**os.environ, "SESPY_BLOCK_UI": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "--rootdir", str(ROOT), "-c", str(ROOT / "pyproject.toml"),
                        "--confcutdir", str(ROOT / "tests"), str(probe)],
                       env=env, capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0 and "blocked: shiny" in r.stdout
```

If the probe can't pick up `tests/conftest.py` from `tmp_path`, write the probe under `tests/` and delete it in a `finally`. Either way, the assertion must stay "a shiny import fails with `blocked: shiny`".

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_version.py tests/test_split_manifest.py -q`
Expected: `test_version` passes (both versions are already 1.17.0). The manifest tests fail, because `library_tests.txt` and the conftest don't exist yet.

- [ ] **Step 3: Implement `tests/conftest.py`, `tests/library_tests.txt`, `scripts/run_library_tests.py`** as described under Interfaces.

- [ ] **Step 4: Verify**

Run: `micromamba run -n shiny python -m pytest tests/test_version.py tests/test_split_manifest.py -q`. Expected: all pass.

Run: `micromamba run -n shiny python scripts/run_library_tests.py --continue-on-collection-errors`. Expected: it exits non-zero, and the **only** failures and errors are the known pre-stage-1 set:
- collection errors in `test_link_rules`, `test_wizard`, `test_connection_polarity` and `test_i18n`;
- failures in `test_r_template_catalogue::test_vendored_translations_match_fixture_subsets`, `test_qsem_import::test_parse_upload_dispatches_by_extension` and `test_templates::test_names_unique_across_both_groups_and_fit_the_wired_buttons`.

Record the list in the task report. Anything else is a new leak: report it as BLOCKED, with the traceback.

- [ ] **Step 5: Commit**

`git add tests/conftest.py tests/library_tests.txt scripts/run_library_tests.py tests/test_split_manifest.py tests/test_version.py && git commit -m "test(split): Shiny-free library gate runner + version check"`

---

### Task 2: Split i18n into a plain library translator and an app-layer reactive translator

**Files:**
- Modify: `sespy/i18n.py`, `sespy/link_rules.py:9,23,83`
- Create: `sespy/ui_i18n.py`, `tests/test_ui_i18n.py`
- Modify (imports only, per the app-layer import rule):
  - `app.py:30,82,179`, `sespy/dashboard.py:28`;
  - every `sespy/modules/*.py` that imports from `..i18n` / `sespy.i18n`. 22 files, listed by `grep -rn "i18n import" sespy/modules`.
- Modify: `tests/test_i18n.py`. Move `test_module_scopes_share_the_root_session_translator` (L290–325) and any other test that needs shiny into `tests/test_ui_i18n.py`.
- Modify: tests that build a translator and rely on reactivity, or that import `Translator` for app modules. They switch to `sespy.ui_i18n.Translator`: `test_cld_legend_density`, `test_intervention_diffusion`, `test_isa_entry_edit`, `test_isa_entry_link_rules`, `test_metrics_explanations`, and any other that `grep -rln "Translator(" tests` shows feeding a UI module.

**Interfaces:**
- Produces, in `sespy/i18n.py` (it imports no shiny):
  - `DEFAULT_FALLBACK`, `SUPPORTED_LANGUAGES`, `load_translations(directory) -> dict[str, dict[str, str]]`, `detect_initial_language(...)`: all unchanged.
  - `@dataclass class Translator`, with fields `translations`, `languages`, `fallback` and `_lang`.
    - `t(key, **fmt) -> str` uses the same lookup, fallback and format rules as today.
    - `set_language(lang) -> None` ignores unsupported codes.
    - It has **no** `language` field.
  - `_default_translator: Translator | None` (the name is kept), `set_default(translator) -> None`.
  - `Resolver = Callable[[Translator | None], Translator | None]`.
  - `_resolver: Resolver | None = None`, `set_resolver(fn: Resolver | None) -> None`.
  - `get_default() -> Translator | None` returns `_resolver(_default_translator)` when a resolver is set, else `_default_translator`.
  - `t(key, **fmt) -> str` returns the key when `get_default()` is None.
- Produces, in `sespy/ui_i18n.py`:
  - `class Translator(sespy.i18n.Translator)`, the reactive one, with the same name so imports stay one-line changes.
    - It adds the field `language: reactive.Value[str]`, created in `__post_init__` exactly as today.
    - `t` touches `self.language.get()` (exceptions swallowed), then calls `super().t`.
    - `set_language` calls super, then sets `language` under `reactive.isolate()` (exceptions swallowed).
  - `_session_resolver(default)`. This holds the body of today's `get_default()` session branch:
    - It takes the root scope and caches `_translator` on it.
    - The clone is **always** a `ui_i18n.Translator` built from the default's `translations` / `languages` / `fallback` / `_lang`.
    - With no session it returns `default`.
    - With a session but no default it returns None.
  - At import: `sespy.i18n.set_resolver(_session_resolver)`.
  - Re-exports for app code: `load_translations`, `detect_initial_language`, `set_default`, `get_default`, `t`, `SUPPORTED_LANGUAGES`, `DEFAULT_FALLBACK` (the library's objects).
- `sespy/link_rules.py`: `from .i18n import t` becomes a top-level import, and the "Shiny-free at import" docstring note is updated. The `TYPE_CHECKING` import of `Translator` stays.

- [ ] **Step 1: Write the failing tests.**

In `tests/test_i18n.py` (library):
- `test_plain_translator_has_no_reactive_field`: `not hasattr(Translator(translations={}), "language")`.
- `test_t_without_default_returns_key`: monkeypatch `_default_translator=None` and `_resolver=None`, then `t("x.y") == "x.y"`. Then set the resolver to `lambda d: d` and check again.
- `test_resolver_hook_is_used`: `set_resolver(lambda d: sentinel)`, then `get_default() is sentinel`. Restore via monkeypatch.
- `test_library_i18n_imports_without_shiny`: run a subprocess with `SESPY_BLOCK_UI` semantics, i.e. a child python with the blocker installed first, then `import sespy.i18n, sespy.link_rules`. Assert exit 0.

In `tests/test_ui_i18n.py` (app):
- the moved `test_module_scopes_share_the_root_session_translator`, unchanged except that its imports come from `sespy.ui_i18n`;
- `test_import_installs_resolver`: `import sespy.ui_i18n as u; from sespy import i18n; assert i18n._resolver is u._session_resolver`.
- `test_resolver_outside_session_returns_process_default`: `set_default(u.Translator(translations={"a": {"en": "A", "de": "Ä"}}))`, then `get_default()` outside a session is that object, and `t("a") == "A"`.
- `test_sessions_are_isolated`: two `test_server` runs in sequence.
  - Session one calls `get_default().set_language("de")`.
  - Session two's `get_default()._lang == "en"`.
  - The process default's `_lang == "en"`.
- `test_session_clone_is_reactive_even_for_plain_default`: monkeypatch `i18n._default_translator` with a **library** `Translator`. Inside `test_server`, `get_default()` is a `ui_i18n.Translator` with a `language` attribute.
- `test_mosaicses_usage_shape`:
  - `from sespy.ui_i18n import Translator, load_translations, set_default`;
  - `set_default(Translator(translations=load_translations(<repo>/sespy/translations)))`;
  - inside `test_server`, `get_default()` returns a reactive clone;
  - then `monkeypatch.setattr(sespy.i18n, "_default_translator", other)`, and outside a session `get_default() is other`.

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py tests/test_ui_i18n.py -q`
Expected: failures on the missing `set_resolver` / `ui_i18n` names and on `hasattr(..., "language")`.

- [ ] **Step 3: Implement `sespy/i18n.py` and `sespy/ui_i18n.py`** per Interfaces. Move today's docstring section on reactive integration to `ui_i18n.py`.

- [ ] **Step 4: Switch the app-layer imports.**
- `app.py`: `from sespy.ui_i18n import Translator, detect_initial_language, load_translations`, and `import sespy.ui_i18n as _i18n` in place of its current `sespy.i18n` alias. `set_default` and `get_default` go through `_i18n`.
- `sespy/dashboard.py` and each module: `from ..ui_i18n import …`, keeping the names it imports today. That includes `pims_stakeholders.py` and `response_register.py`, which use `sespy.i18n` absolutely.
- `link_rules.py`: top-level `from .i18n import t`.

Verify: `grep -rnE "from (\.\.|sespy\.)i18n import|import sespy\.i18n" sespy/modules sespy/dashboard.py app.py` prints nothing.

- [ ] **Step 5: Update the tests listed under Files** so UI-module tests build `sespy.ui_i18n.Translator`. Tests that monkeypatch `i18n._default_translator` keep targeting `sespy.i18n`.

- [ ] **Step 6: Run**

`micromamba run -n shiny python -m pytest tests/test_i18n.py tests/test_ui_i18n.py tests/test_link_rules.py tests/test_r_template_catalogue.py tests/test_cld_legend_density.py tests/test_intervention_diffusion.py tests/test_isa_entry_edit.py tests/test_isa_entry_link_rules.py tests/test_metrics_explanations.py tests/test_mosaicses_contract.py -q`
Expected: all pass.

Then `micromamba run -n shiny python scripts/run_library_tests.py --continue-on-collection-errors`. Expected: the `test_link_rules`, `test_i18n` and `test_r_template_catalogue` entries are gone from the known set.

- [ ] **Step 7: Commit**

`git commit -am "refactor(split): plain library Translator + resolver hook; reactive Translator moves to sespy.ui_i18n"` (add the new files first).

---

### Task 3: Move the laguna path and `add_reads` out of `r_kb`

**Files:**
- Modify: `sespy/r_kb.py:147-165,237,259-276,292-300,328,455-456`
- Create: `sespy/ui_r_kb.py`
- Modify: `app.py:86`, `sespy/modules/report_export.py:20,103`, `sespy/modules/ai_isa_wizard.py:872,1100,1474`
- Modify: `tests/parity/check_live.py:265,312-323`, `tests/parity/test_check_live.py:277`
- Modify: `tests/test_r_kb_registry.py:94-97`, `tests/test_deploy_script.py:815-821`, `tests/test_k1_wiring.py:111,146-163`

**Interfaces:**
- Produces, in `sespy/r_kb.py`:
  - `override_dir_from(env: Mapping[str, str], settings_text: str | None, default: str | None) -> str | None`.
    - Same rules as today, except that "no matching line / no file" returns `default`.
    - `DEFAULT_OVERRIDE_DIR` is **deleted**.
  - `configure(app_dir: Path, *, default_override_dir: str | None = None) -> None`. `_Registry.configure` stores it, and `_refresh` passes it to `override_dir_from`.
  - `add_reads` is **deleted** from `r_kb`.
- Produces, in `sespy/ui_r_kb.py`:
  - `LAGUNA_R_DATA_DIR = "/srv/shiny-server/marinesabres/data"`.
  - `add_reads(reads, names) -> None`, moved verbatim, with `from shiny import reactive` at module top.
- `app.py`: `r_kb.configure(Path(__file__).parent, default_override_dir=LAGUNA_R_DATA_DIR)`. It stays a top-level statement starting `r_kb.configure(` (`test_k1_wiring.py:387` checks this).
- `check_live.py`:
  - new option `--default-override-dir` (str, default None);
  - with `--fetch` it is **required**: `ap.error("--fetch needs --default-override-dir")`;
  - it is passed as `default` at L265.
  - `deploy/deploy.sh` doesn't call `--fetch` (it uses its own `DEFAULT_R_DATA_DIR`, L64), so the script is unchanged.
  - *Ruling vs spec §5.2:* the argument is required only with `--fetch`, the one path that reads the default. The spec's intent, no laguna path in the library, holds.

- [ ] **Step 1: Write the failing tests**
- `test_r_kb_registry.py::test_override_dir_from_precedence`:
  - `f({}, None, "/d") == "/d"`;
  - `f({}, "nothing here\n", "/d") == "/d"`;
  - `f({}, None, None) is None`;
  - the existing env/settings precedence cases, with a `default` argument added.
- `test_r_kb_registry.py::test_missing_default_dir_serves_vendored`: `configure(tmp_path, default_override_dir=str(tmp_path / "absent"))`, then `refresh()`, then `current() is r_kb.VENDORED` (or equal in hashes, as the existing vendored-fallback tests assert). No exception.
- `test_r_kb_registry.py::test_library_has_no_laguna_path`: `"/srv/" not in Path(r_kb.__file__).read_text()`.
- `test_check_live.py`:
  - `test_fetch_absent_settings_uses_default_path` passes `--default-override-dir /srv/shiny-server/marinesabres/data` and asserts that path;
  - new `test_fetch_requires_default_override_dir`: `build_parser().parse_args(["--fetch"])`, or `main(["--fetch"])`, exits with status 2.
- `test_deploy_script.py` L815-821: call `override_dir_from({}, _app_text(t), LAGUNA_R_DATA_DIR)`, and add `test_deploy_default_matches_app_constant`. That test asserts the `DEFAULT_R_DATA_DIR="…"` value parsed from `deploy/deploy.sh` equals `sespy.ui_r_kb.LAGUNA_R_DATA_DIR`.
- `test_k1_wiring.py`: `add_reads` tests import from `sespy.ui_r_kb`.

- [ ] **Step 2: Run to verify they fail.** Run the five test files above; expect signature and import errors.

- [ ] **Step 3: Implement** per Interfaces.

- [ ] **Step 4: Run** `micromamba run -n shiny python -m pytest tests/test_r_kb.py tests/test_r_kb_registry.py tests/parity tests/test_deploy_script.py tests/test_k1_wiring.py tests/test_wizard_chips.py tests/test_report_regional.py -q`. Expected: all pass.

- [ ] **Step 5: Commit** with the message `refactor(split): r_kb takes the default override dir; laguna path and add_reads move to sespy.ui_r_kb`.

---

### Task 4: Split the mixed tests

**Files:**
- Modify: `tests/test_network.py` (remove the `build_loop_payload` test, ~L351), `tests/test_qsem_import.py` (remove `test_parse_upload_dispatches_by_extension`, ~L150), `tests/test_templates.py` (remove `test_names_unique_across_both_groups_and_fit_the_wired_buttons`, ~L110), `tests/test_wizard.py` (~L86), `tests/test_connection_polarity.py` (L17 and its users)
- Create: `tests/test_analysis_loops_payload.py`, `tests/test_import_data_module.py`, `tests/test_wizard_dedup.py`
- Modify: `tests/test_templates_module.py` (receives the templates test)

**Interfaces:**
- Moves only. Each moved test body is unchanged; only its imports come along.
- After the move, none of the five library files imports `sespy.modules`, `shiny`, `htmltools` or `pyvis`, at module level or inside a test.
- The new files are app tests. They are **not** added to `library_tests.txt`.

- [ ] **Step 1: Move the tests.**

Verify: `grep -nE "sespy\.modules|from shiny|import shiny|pyvis" tests/test_network.py tests/test_qsem_import.py tests/test_templates.py tests/test_wizard.py tests/test_connection_polarity.py` prints nothing.

- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_network.py tests/test_qsem_import.py tests/test_templates.py tests/test_wizard.py tests/test_connection_polarity.py tests/test_analysis_loops_payload.py tests/test_import_data_module.py tests/test_wizard_dedup.py tests/test_templates_module.py -q`.

Expected: all pass, with the same total test count as before the move. Compare against `--co -q` on the baseline files.

- [ ] **Step 3: Run the gate**

`micromamba run -n shiny python scripts/run_library_tests.py`. Expected: exit 0, no collection errors, no failures.

- [ ] **Step 4: Commit** with the message `test(split): move UI halves of mixed tests into app test files`.

---

### Task 5: CI gate job, release 1.17.1, full gates

**Files:**
- Modify: `.github/workflows/ci.yml`, `pyproject.toml:3`, `sespy/__init__.py:3`, `docs/MANUAL.md:3`, `CHANGELOG.md`

**Interfaces:**
- New CI job `library-no-ui`:
  - matrix 3.11 / 3.12;
  - `pip install -e .[test]`, then `pip uninstall -y shiny htmltools pyvis-optimized`;
  - `python scripts/run_library_tests.py`.
- Existing jobs are unchanged.

- [ ] **Step 1: Add the CI job; bump the versions.**
- Versions: `1.17.1` in `pyproject.toml` and `sespy/__init__.py`, and the MANUAL line in Global Constraints.
- CHANGELOG entry `## 1.17.1`: "Internal: library code no longer needs Shiny (translator and reference-data reads split into `sespy.ui_i18n` / `sespy.ui_r_kb`); no user-visible change."

- [ ] **Step 2: Run the gates.**
- `micromamba run -n shiny python scripts/run_library_tests.py`. Expected: exit 0.
- Full unit suite, run the way CI does: `micromamba run -n shiny python -m pytest tests -q --ignore-glob="*e2e*" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`.
  - Expected: 0 failed.
  - Detach it with Start-Process through `micromamba.bat run` and poll in bounded PowerShell calls. Background bash dies at 10 minutes.
- Full e2e: `micromamba run -n shiny python tests/run_e2e.py --port 8000`.
  - Expected: all scripts pass.
  - Before starting, check that nothing is listening on port 8000 and that no orphan `python -` processes are running. Run it detached, like the unit suite.
- Lint: `micromamba run -n shiny ruff check sespy tests app.py scripts`. Expected: clean.

- [ ] **Step 3: Commit** with the message `release: 1.17.1 — library is Shiny-free (split stage 1)`.

- [ ] **Step 4: Hand-off note, in the task report** (not executed by the agent):
  - **Deploy order:** 1.17.1 must **not** be deployed to laguna before the MosaicSES bridge release (plan 2) is live. MosaicSES imports `Translator` from `sespy.i18n` and needs the reactive one (spec §5.1).
  - **Commands:** give the user single-line `!` commands for push, PR, merge and tag `v1.17.1`, and mark the deploy command "after plan 2's bridge is live".
