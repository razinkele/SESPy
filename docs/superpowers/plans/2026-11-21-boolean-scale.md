# Boolean Attractor Search at Scale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The app runs exhaustive Boolean attractor search up to 20 nodes without blocking the worker (R parity), and adds a clearly labelled sampled search for larger networks.

**Architecture:**
- **Library (1.19.0).** The library gets a vectorised next-state kernel shared by two searches:
  - the existing `boolean_attractors`, rewritten without a per-state Python loop but output-identical;
  - a new `boolean_attractors_sampled`.
- **App (1.1.0).**
  - It runs either search in an ExtendedTask.
  - It raises the slider to 20 and adds a method choice.
- **Deploy.** Then a second split-layout deploy.

**Tech Stack:** Python 3.11+, numpy, Shiny for Python ≥ 1.7 (`@reactive.extended_task`), pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-21-boolean-scale-design.md` (same branch, `docs/boolean-scale`).

## Global Constraints

- **Environment.**
  - Python only via `micromamba run -n shiny`. No venvs, no `pip install`.
  - Single-line commands or `.py` files, never multi-line `python -c` or `python - <<EOF`.
- **Trees you must not touch.**
  - `AppData/Local/sespy-app` is the v1.0.1 rollback tree and holds the real `config.env`.
  - `AppData/Local/sespy-lib-v1180` is the live library tree.
  - `AppData/Local/sespy-v1171` and `sespy-v1171-rb`.
  - Never read any `deploy/config.env`. No ssh.
- **User-only steps.** The user runs every push, PR merge, tag and deploy via `!` one-liners unless they explicitly ask the agent. Keep those commands short: long ones wrap and break.
- **Exhaustive API is frozen.**
  - `boolean_attractors(rules, max_nodes=12, *, ceiling=BOOLEAN_MAX_NODES_CEILING)`.
  - `BOOLEAN_MAX_NODES_CEILING = 20`.
  - The `too_large` sentinel `{"attractors": [], "error": "too_large", "n_nodes", "max_nodes", "total_states": 0}`.
  - The success shape `{"attractors": [{"type","states","period","basin_size"}], "total_states": 2**n}`.
  - Output is identical, including order, to the current implementation.
- **Kernel summation order.** For node j: `inflow = 0.0`, add `w * bit_i` for each activator in list order, then for each inhibitor in list order. Then `bit_j' = inflow > threshold`. No matmul.
- **Sampled API:** `boolean_attractors_sampled(rules, n_samples=1000, *, max_steps=1000, seed=0, max_nodes=BOOLEAN_SAMPLED_MAX_NODES)`, with `BOOLEAN_SAMPLED_MAX_NODES = 62`. The result shape is in spec §3.3. It never contains `basin_size` or `total_states`.
- **App limits:**
  - `max_nodes` slider 4–20, default 20, server clamp [4, 20];
  - `n_samples` 100–5000, default 1000, server clamp [100, 5000];
  - Sampled uses `seed=0`, `max_steps=1000`.
- **Translations.** New UI strings go in the library's `sespy/translations/core.json`, English text in all 9 languages (`en es fr de lt pt it no el`). Keep `boolean.cap_below_12` and `boolean.cap_above_12`.
- **Versions.** Library 1.19.0 (tag `v1.19.0`). App 1.1.0 (tag `v1.1.0`), pinning `sespy[pdf,bayes] @ git+https://github.com/razinkele/SESPy@v1.19.0`.
- **Long test runs** (full e2e, MosaicSES suite):
  - Launch them detached with PowerShell `Start-Process` through `micromamba.bat run`, logging to a file.
  - Poll with bounded `Start-Sleep`.
  - Make sure port 8000 is free before and after.
  - Never edit a tree while its suite runs.

## Review Focus

1. **Float ties in the kernel.** Weights like 0.1 + 0.2 − 0.3 must resolve as the old loop does. Pin it with a differential test over random float weights (Task 1).
2. **Order preservation.** Nid4Ocean and the UI read `attractors[i]["states"][0]`, so attractor order and cycle start must match the old loop exactly. Pin it with differential equality, not set equality (Task 1).
3. **Sampled results can't pass as exhaustive.** Pin it in the result-shape test (Task 2) and the UI note e2e (Task 6).
4. **Stale or failed background runs.** A run superseded by another click, or a task exception, must not overwrite or crash the panel. Pin it with a generation-drop and an error-path unit test (Task 5).
5. **A crafted input past the clamps.** `max_nodes=50`, `n_samples=10**7`, or junk input must clamp on the server (Task 5).

---

## Part A — Library (repo SESPy)

Worktree: `git -C "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy" worktree add -b feat/boolean-scale C:/Users/arturas.baziukas/AppData/Local/sespy-boolscale-lib origin/main`. Test PYTHONPATH is the worktree itself.

### Task 1: Vectorised kernel and output-identical exhaustive search

**Files:**
- Modify: `sespy/dynamics.py:228-345` (ceiling comment, `boolean_attractors`)
- Create: `tests/_boolean_reference.py` (the current loop, verbatim, as `boolean_attractors_reference(rules)`)
- Create: `tests/test_boolean_vectorised.py`
- Create: `tests/bench_boolean.py` (not collected by pytest)

**Interfaces:**
- Produces: `_boolean_next_states(rules: list[dict], states: np.ndarray) -> np.ndarray` (int64 in, int64 out, 1 ≤ len(rules) ≤ 62). Task 2 uses it.

- [ ] **Step 1: Copy the oracle.** Copy the current body of `boolean_attractors`, from the `n_states = 1 << n` line to the end, into `tests/_boolean_reference.py` as `boolean_attractors_reference(rules)`, which returns the same dict. Include the `n == 0` branch.
- [ ] **Step 2: Write the failing tests** in `tests/test_boolean_vectorised.py`:
  ```python
  def _random_rules(n, rng, float_weights):  # random signed matrix -> create_boolean_rules
      ...
  @pytest.mark.parametrize("seed", range(40))
  def test_exhaustive_equals_reference_random_int_weights(seed): # n = rng.integers(1, 13)
      assert boolean_attractors(rules, max_nodes=12) == boolean_attractors_reference(rules)
  @pytest.mark.parametrize("seed", range(40))
  def test_exhaustive_equals_reference_random_float_weights(seed):  # weights from {±0.1, ±0.2, ±0.3, ±0.7}
      ...same assertion...
  def test_next_states_matches_reference_transition():  # n=10, all states, vs a per-state loop in the test
  def test_next_states_rejects_more_than_62_nodes():  # ValueError
  def test_exhaustive_does_not_loop_in_python_over_states(monkeypatch):
      # n=16 completes in < 2 s (the old loop takes far longer); marks the vectorisation
  ```
  The full `==` on the dict pins type, states order, period, basin_size and attractor order.
- [ ] **Step 3: Run them and watch them fail.** Run `micromamba run -n shiny python -m pytest tests/test_boolean_vectorised.py -q`. Expected: FAIL. `_boolean_next_states` is not defined, and the timing test fails.
- [ ] **Step 4: Implement** `_boolean_next_states` and the new `boolean_attractors` body, as in spec §3.2:
  1. the kernel on `np.arange(1 << n, dtype=np.int64)`;
  2. N rounds of `m = np.minimum(m, m[fp]); fp = fp[fp]`;
  3. `label = m[fp]`;
  4. `np.unique(label, return_index=True, return_counts=True)` with attractors ordered by first index;
  5. per attractor, walk `next` from its first index `s0`, recording visited states in a dict until the first repeat, and take `states` as the path from that repeated state onward. This mirrors the old loop: the walk runs once per attractor, never per state.

  Keep the sentinel and `n == 0` code unchanged. Update the comment at 228–231: the app now runs the search in an ExtendedTask, and the vectorised search makes 20 practical.
- [ ] **Step 5: Run the tests to verify they pass.** Run `micromamba run -n shiny python -m pytest tests/test_boolean_vectorised.py tests/test_dynamics.py -q`. Expected: all pass, including the existing `test_boolean_*` tests in `test_dynamics.py`.
- [ ] **Step 6: Benchmark.** `tests/bench_boolean.py` times the search and reports peak memory (`tracemalloc`) for random rules at n = 16, 18 and 20, 3 runs each. Run `micromamba run -n shiny python tests/bench_boolean.py`. Expected gate: n = 20 median ≤ 5 s and peak ≤ 300 MB. Record the numbers in the report. If the gate fails, stop and report: the app's cap of 20 depends on it.
- [ ] **Step 7: Commit.** `git add sespy/dynamics.py tests/_boolean_reference.py tests/test_boolean_vectorised.py tests/bench_boolean.py && git commit -m "perf(dynamics): vectorised exhaustive Boolean attractor search, output-identical"`

### Task 2: Sampled attractor search

**Files:**
- Modify: `sespy/dynamics.py` (new function and constant after `boolean_attractors`)
- Modify: `tests/test_public_api.py:32` (add `boolean_attractors_sampled`, `BOOLEAN_SAMPLED_MAX_NODES` if constants are listed)
- Create: `tests/test_boolean_sampled.py`

**Interfaces:**
- Consumes: `_boolean_next_states` (Task 1).
- Produces: `boolean_attractors_sampled(...)` and `BOOLEAN_SAMPLED_MAX_NODES = 62`, as in the Global Constraints. Task 5 consumes them.

- [ ] **Step 1: Check the BoolNet semantics.** Look up BoolNet `getAttractors(method="random", startStates=...)` (CRAN reference manual or Context7). Note in the report what it reports for basins in random mode. The docstring will cite it.
- [ ] **Step 2: Write the failing tests:**
  ```python
  def test_sampled_result_shape():  # keys == {"method","attractors","n_samples","n_unconverged","seed","max_steps","n_nodes"}
      # method == "sampled"; no "basin_size"/"total_states" anywhere in the result
  @pytest.mark.parametrize("seed", range(20))
  def test_sampled_attractors_subset_of_exhaustive(seed):  # n <= 12; compare frozenset(states)
  def test_sampled_hits_sum_and_fraction():  # sum(hits) + n_unconverged == n_samples; fraction == hits/n_samples
  def test_sampled_is_deterministic_for_a_seed():  # same seed -> equal dicts; different seed may differ
  def test_sampled_cycle_rotated_to_min_state_and_order():  # states[0] == min(states); hits desc then min state
  def test_sampled_unconverged_counted_with_tiny_max_steps():  # 3-node positive ring (cycle period 3), max_steps=1 -> n_unconverged > 0
  def test_sampled_runs_on_26_nodes_quickly():  # random 26-node rules, n_samples=1000, < 5 s, no error
  def test_sampled_too_large_sentinel():  # 63 nodes -> error "too_large", attractors []
  def test_sampled_empty_rules():  # attractors [], n_samples echoed
  def test_sampled_clamps_args():  # n_samples=0 -> 1; n_samples=10, max_steps=10**9 -> 100_000 (assert echoed values)
  def test_sampled_history_budget_lowers_max_steps():  # n_samples=1000, max_steps=100_000 -> echoed max_steps == 10**7 // 1000 - 1
  ```
  Also add the new name to `tests/test_public_api.py`.
- [ ] **Step 3: Run them and watch them fail.** Run `micromamba run -n shiny python -m pytest tests/test_boolean_sampled.py tests/test_public_api.py -q`. Expected: FAIL, because the names are not defined.
- [ ] **Step 4: Implement.** Draw the starts as `rng.integers(0, 2, size=(n_samples, n))`, packed to int64. Step all live trajectories with the kernel, keeping an int64 history of shape `(n_samples, max_steps + 1)`. Bound it with a budget of `n_samples * (max_steps + 1) <= 10**7` (80 MB): after clamping, lower `max_steps` to `10**7 // n_samples - 1` when needed, and echo the effective value in the result. The app's limits (5000 × 1001) fit inside the budget. Detect each trajectory's first repeat and take the cycle from the history. Canonicalise and aggregate as the spec says. The docstring states that the result is non-exhaustive and gives the BoolNet comparison.
- [ ] **Step 5: Run the tests to verify they pass.** Run `micromamba run -n shiny python -m pytest tests/test_boolean_sampled.py tests/test_boolean_vectorised.py tests/test_dynamics.py tests/test_public_api.py -q`. Expected: all pass.
- [ ] **Step 6: Commit.** `git commit -am "feat(dynamics): sampled Boolean attractor search for networks above the exhaustive cap"` (git add the new test file first).

### Task 3: Translation keys and the 1.19.0 release commit

**Files:**
- Modify: `sespy/translations/core.json` (after `boolean.cap_above_12`)
- Modify: `sespy/__init__.py` (`__version__`), `pyproject.toml` version, `CHANGELOG.md`

- [ ] **Step 1: Write the failing test.** In `tests/test_translations_boolean_scale.py`, every key in spec §3.4 exists, with all 9 languages and non-empty values. The placeholders are exactly:
  - `boolean.sampled_note`: `{n} {seed} {unconverged} {max_steps}`;
  - `boolean.cap_above_max`: `{n} {max}`.
- [ ] **Step 2: Run it and watch it fail.** Expected: FAIL with missing keys.
- [ ] **Step 3: Add the keys** with this English text, copied into all 9 languages:
  - `boolean.method` "Search method"; `boolean.method_exhaustive` "Exhaustive (up to 20 nodes)"; `boolean.method_sampled` "Sampled (any size)";
  - `boolean.n_samples` "Random start states"; `boolean.computing` "Computing attractors…";
  - `boolean.sampled_note` "Sampled search: {n} random start states (seed {seed}). Rare attractors may be missed; basin fractions are estimates. {unconverged} trajectories did not settle within {max_steps} steps.";
  - `boolean.cap_above_max` "Network has {n} nodes. Exhaustive search is capped at {max}. Choose the Sampled method, or use Simplify Network first.";
  - `boolean.col_hits` "Hits"; `boolean.col_basin_fraction` "Basin fraction (%)".
- [ ] **Step 4: Run the full library suite.** Run `micromamba run -n shiny python -m pytest -q`. Expected: all pass (the 1.18.0 baseline was 2451 passed).
- [ ] **Step 5: Release commit.** Bump to 1.19.0. The CHANGELOG `## [1.19.0]` entry lists the vectorised exhaustive search (output-identical), `boolean_attractors_sampled` and the new translation keys. Commit: `git commit -am "release: 1.19.0 — vectorised and sampled Boolean attractor search"`.

### Task 4: Library hand-off (user)

- [ ] **Step 1:** The agent pushes nothing. Give the user these one-liners:
  - push `feat/boolean-scale`;
  - `gh pr create`, with the body written to a file;
  - after CI is green, the merge;
  - `git tag -a v1.19.0 -m v1.19.0 <merge sha>` and `git push origin v1.19.0`. Use a `~/` helper script if the line would wrap.
- [ ] **Step 2: Verify.** `git ls-remote origin "refs/tags/v1.19.0^{}"` must equal the merge commit, and its tree must equal the tested HEAD (`git diff --stat <head> v1.19.0` is empty).

---

## Part B — App (repo sespy-app)

Worktree: `git -C C:/Users/arturas.baziukas/AppData/Local/sespy-app worktree add -b feat/boolean-scale C:/Users/arturas.baziukas/AppData/Local/sespy-app-boolscale origin/main`. Library tree for tests: `git -C "<OneDrive SESPy>" worktree add --detach C:/Users/arturas.baziukas/AppData/Local/sespy-lib-v1190 v1.19.0`. PYTHONPATH is `<sespy-app-boolscale>;<sespy-lib-v1190>`, with cwd = the app worktree.

### Task 5: Boolean module — ExtendedTask, method choice, cap 20

**Files:**
- Modify: `sespy_app/modules/analysis_boolean.py`
- Modify: `tests/test_analysis_boolean_clamp.py`
- Create: `tests/test_analysis_boolean_sampled.py`

**Interfaces:**
- Consumes: `dynamics.boolean_attractors`, `dynamics.boolean_attractors_sampled`, `dynamics.clamp_max_nodes`, and the translation keys from Task 3.
- Keeps: `analysis_boolean_server(id, project_data, event_bus, translator=None)` and the input ids `direction`, `max_nodes` and `run_boolean`. MosaicSES's `test_compartments_module.py:297` pins this signature. Adds the inputs `method` (`"exhaustive"`/`"sampled"`) and `n_samples`.

- [ ] **Step 1: Write the failing tests.**
  - Update the clamp test parametrisation to `[(50, 20), (2, 4), (8, 8), ("junk", 20)]`. Results now arrive through the ExtendedTask, so assert on the spy after the task settles; see `tests/` for how leverage's uncertainty task is tested, or add a `ts.flush()`/wait loop.
  - New tests:
  ```python
  @pytest.mark.parametrize("ui,want", [(10**7, 5000), (5, 100), (1000, 1000), ("junk", 1000)])
  def test_sampled_clamps_n_samples(monkeypatch, ui, want):  # spy boolean_attractors_sampled; seed==0, max_steps==1000
  def test_sampled_result_renders_note_and_columns():  # attractor_panel HTML contains the sampled_note text and Hits / Basin fraction headers
  def test_exhaustive_over_20_shows_cap_above_max():  # 26-node project, method exhaustive -> alert-warning with cap_above_max text
  def test_stale_generation_is_dropped():  # two runs back to back; only the second result is stored
  def test_task_exception_shows_error_not_crash(monkeypatch):  # boolean_attractors raises -> alert-danger, server alive
  ```
- [ ] **Step 2: Run them and watch them fail.** Run `micromamba run -n shiny python -m pytest tests/test_analysis_boolean_clamp.py tests/test_analysis_boolean_sampled.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**, following `analysis_leverage.py:203-232` (generation counter, `asyncio.to_thread`, `_COMPUTING` state, logged task errors):
  - The Laplacian stays synchronous in `_run`.
  - The attractor search goes to the task.
  - Controls are as in spec §4.1. The sample-count input is in a `ui.panel_conditional("input.method === 'sampled'", ...)`.
  - Rendering follows spec §4.3. The exhaustive cap message uses `cap_below_12` when n ≤ 20, and `cap_above_max` with `max=20` when n > 20.
  - Read `references/extended-tasks.md` under `micromamba run -n shiny shiny skills path shiny-for-python` first (SESPy CLAUDE.md).
- [ ] **Step 4: Run the tests to verify they pass.** Run the app unit suite (README selection: `pytest tests/ -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py …`). Expected: all pass (the v1.0.1 baseline was 538 passed / 2 skipped, plus the new tests).
- [ ] **Step 5: Commit.** `git commit -am "feat(boolean): exhaustive search to 20 nodes in a background task; sampled method for larger networks"` (add the new test file).

### Task 6: e2e, manual, screenshot, MosaicSES gate

**Files:**
- Modify: `tests/test_boolean_e2e.py` (the 17-node sample is now under the cap: set slider `max_nodes` to 12 before running so the warning path is still covered; update the docstring)
- Modify: `tests/test_boolean_happy_e2e.py` (wait for the task result, not a fixed delay)
- Create: `tests/test_boolean_sampled_e2e.py` (load the 26-node Fisheries template as `test_boolean_happy_e2e.py` loads its template, choose Sampled, run; assert the sampled note and ≥ 1 table row under `#boolean-attractor_panel`, no `.alert-danger`; scope every selector to `#boolean-…`, never a bare `text=`)
- Modify: `docs/MANUAL.md` §17 (controls: method, 4–20 slider, start states; a "Reading it" note that sampled results are estimates)
- Regenerate: `docs/screenshots/boolean.png` via `tests/make_docs_screenshots.py`

- [ ] **Step 1: Write and change the e2e scripts** as listed above.
- [ ] **Step 2: Run the full e2e.** Run `micromamba run -n shiny python tests/run_e2e.py --port 8000`, detached. Expected: all pass, apart from a runner-retried flake. `test_intervention_e2e` is a known load flake: rerun it alone 3× if it is red. The server line names `sespy-lib-v1190` 1.19.0.
- [ ] **Step 3: Update the manual and screenshot.** Update MANUAL §17, then regenerate the screenshot (`micromamba run -n shiny python tests/make_docs_screenshots.py`, or its boolean-only option if it has one). Check the image shows the new controls.
- [ ] **Step 4: Run the MosaicSES gate.**
  - Run the full MosaicSES suite from `AppData/Local/mosaicses-split-gate` (detached at `origin/main`) with PYTHONPATH `<mosaicses-split-gate>;<sespy-app-boolscale>;<sespy-lib-v1190>`.
  - Expected: reds only from the baseline set: topbar modal race, equity editor, beforeunload, composite timer, file flows, heatmap_card, risk knot, comparative-header load flake.
  - Rerun any other red 3× alone.
- [ ] **Step 5: Commit.** `git add tests/test_boolean_e2e.py tests/test_boolean_happy_e2e.py tests/test_boolean_sampled_e2e.py docs/MANUAL.md docs/screenshots/boolean.png && git commit -m "test(boolean): e2e for the 20 cap and sampled method; manual §17"`

### Task 7: App 1.1.0 release, plan-4 deferrals ruling, hand-off

**Files:**
- Modify: `pyproject.toml` (version 1.1.0; pin `@v1.19.0`), `sespy_app/__init__.py` (`__version__`), `deploy/deploy.sh` `PIN` if it is hard-coded there, `CHANGELOG.md`, MANUAL version line

- [ ] **Step 1: Bump the version.** Bump to 1.1.0 and re-pin to `v1.19.0`. Run `micromamba run -n shiny python -m pytest tests/test_deploy_script.py -q`. Expected: pass, since the pin and version checks agree.
- [ ] **Step 2: Rule on the plan-4 deferrals.** Read plan 4's Follow-ups "plan-4 deferrals, for 1.0.2" (`AppData/Local/sespy-plan4/docs/superpowers/plans/2026-11-21-split-stage4-cutover.md`, §Follow-ups) and plan 4's ledger line on N1–N4 (`…/.superpowers/sdd/2026-11-21-split-stage4-cutover/progress.md`, "N1–N4 PARKED"). This is the second split-layout deploy. For each item, decide whether a normal second deploy (no crash mid-chain) can reach it and whether it can lose a feedback row.
  - **Reachable and can lose a row:** fix it here with a test in `tests/test_deploy_script.py`.
  - **Otherwise:** ledger a `Ruling:` that accepts it for 1.1.x.
- [ ] **Step 3: Release commit.** Commit: `git commit -am "release: 1.1.0 — Boolean search to 20 nodes and sampled method (sespy 1.19.0)"`.
- [ ] **Step 4: Run the whole-branch review** (subagent-driven final review) before the tag.
- [ ] **Step 5: User hand-off.** The user pushes the branch, opens the PR and waits for green CI (unit, lint, full app, e2e). Then the user merges and runs `git tag -a v1.1.0 -m v1.1.0 <merge sha>` and pushes the tag. The agent verifies `v1.1.0^{}` with `ls-remote`, and that the merge tree equals the reviewed HEAD.

---

## Part C — Deploy

### Task 8: Second split-layout deploy (user runs; agent verifies)

- [ ] **Step 0: Agent pre-checks.**
  - The deploy tree: `git -C C:/Users/arturas.baziukas/AppData/Local/sespy-app worktree add --detach C:/Users/arturas.baziukas/AppData/Local/sespy-app-v110 v1.1.0`. It must be clean and describe as exactly `v1.1.0`.
  - `sespy-lib-v1190` describes as exactly `v1.19.0` and is clean.
  - `sespy-app` (the rollback tree) is still at `v1.0.1` and clean.
  - `git -C sespy-app-v110 check-ignore -v deploy/config.env` names `.gitignore`.
  - Live MosaicSES `verify_live.py --expect-version 0.9.3` passes.
- [ ] **Step 1: Config hand-off (user, via a `~/` helper script the agent writes; the agent never reads the file).**
  1. Copy `sespy-app/deploy/config.env` to `sespy-app-v110/deploy/config.env`.
  2. Rewrite its `DEPLOY_LIBRARY_ROOT=` line to `C:/Users/arturas.baziukas/AppData/Local/sespy-lib-v1190` with `sed -i 's#^DEPLOY_LIBRARY_ROOT=.*#DEPLOY_LIBRARY_ROOT=…#'`.
  3. Print `grep -c '^DEPLOY_LIBRARY_ROOT=…sespy-lib-v1190$'`, which must be 1, and `grep -c '^DEPLOY_MOSAIC_DIR='`, which must be 1.
- [ ] **Step 2: Deploy (user).** Run `bash C:/Users/arturas.baziukas/AppData/Local/sespy-app-v110/deploy/deploy.sh`. Expected:
  - "Deploying SESPy app v1.1.0 with sespy library v1.19.0";
  - check_live ok;
  - no `!!` lines;
  - MosaicSES restarted.
- [ ] **Step 3: Live checks (agent, read-only).**
  - Playwright on `https://laguna.ku.lt/SESPy/`:
    - About shows `SESPy app 1.1.0 · sespy library 1.19.0`;
    - Boolean & Laplacian on the 17-node sample with method Exhaustive at slider 20 renders an attractor table;
    - on the Fisheries template (26 nodes) with method Sampled, it renders the sampled note and table, with no `.alert-danger`.
  - MosaicSES: run `verify_live.py --expect-version 0.9.3`, plus the Compartments → Edit Data and Boolean & Laplacian tabs, which must render without `Error:`.
  - The user runs `ssh razinka@laguna.ku.lt ls /srv/shiny-server/SESPy/sespy_app/logs`, which must list `feedback.db`.
- [ ] **Step 4: Rollback trigger.** On a non-cosmetic failure, the user runs `bash C:/Users/arturas.baziukas/AppData/Local/sespy-app/deploy/deploy.sh --rollback`. That is the v1.0.1 tree, whose `config.env` names `sespy-lib-v1180`. Ledger the outcome.
- [ ] **Step 5: Memory.** Update the project memory (live versions, rollback tree), and offer worktree cleanup (`sespy-boolscale*`, `sespy-app-boolscale`).
