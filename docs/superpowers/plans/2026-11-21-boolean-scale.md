# Boolean Attractor Search at Scale Implementation Plan (rev. 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exact Boolean attractors for any network whose feedback core has at most 20 nodes, with exact or labelled-estimate basins, a sampled fallback for larger cores, and a plain-language all-off result, all computed in a background task.

**Architecture:**
- **Library (1.19.0).** A shared uint8-matrix kernel feeds two new public functions: `boolean_attractors_core` (partition, constant propagation, core search, reconstruction, basins) and `boolean_attractors_sampled`. `boolean_attractors` stays untouched as the oracle.
- **App (1.1.0).** It routes core → sampled in an ExtendedTask and drops the slider.
- **Deploy.** Then a second split-layout deploy.

**Tech Stack:** Python 3.11+, numpy, networkx (already declared), Shiny for Python ≥ 1.7 (`@reactive.extended_task`), pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-21-boolean-scale-design.md` (rev. 2). Evidence: `docs/superpowers/specs/2026-11-21-boolean-scale-research.md` and `docs/superpowers/specs/boolean-scale-probes/`, where `core_reduction.py` is a working, unoptimised prototype of §3.3 steps 1–5.

## Global Constraints

- **Environment.**
  - Python only via `micromamba run -n shiny`. No venvs, no `pip install`, no new dependencies.
  - Single-line commands or `.py` files, never multi-line `python -c` or `python - <<EOF`.
- **Trees you must not touch.**
  - `AppData/Local/sespy-app` is the v1.0.1 rollback tree and holds the real `config.env`.
  - `AppData/Local/sespy-lib-v1180` is the live library tree.
  - `AppData/Local/sespy-v1171` and `sespy-v1171-rb`.
  - Never read any `deploy/config.env`. No ssh.
- **User-only steps.** The user runs every push, PR merge, tag and deploy via short `!` one-liners. Use a `~/` helper script when a line would wrap.
- **`boolean_attractors` is unchanged:** code, signature, defaults and output. It is the test oracle.
- **Kernel summation order.** For node j: `inflow = 0.0` (float64), add `w * X[:, i]` for each activator in list order, then for each inhibitor in list order. Then `X'[:, j] = inflow > threshold`. No matmul.
- **Constants:**
  - `BOOLEAN_MAX_CORE = 20`;
  - `BOOLEAN_BASIN_BUDGET = 1 << 24`;
  - `BOOLEAN_MAX_NODES_TOTAL = 200`.
- **Result shapes and sentinels:** exactly as spec §3.3 and §3.4. Sampled results never contain `basin_size`. States are Python ints, with bit i for node i.
- **App fallback:** fixed at `n_samples=2000`, `seed=0`, `max_steps=1000`; none is client-settable. The max-nodes slider is removed.
- **Translations:**
  - The spec §3.5 keys go in the library's `sespy/translations/core.json`, inside the top-level `"translation"` object, with English text in all 9 languages (`en es fr de lt pt it no el`).
  - Keep the existing `boolean.*` keys.
- **Versions.** Library 1.19.0 (tag `v1.19.0`). App 1.1.0 (tag `v1.1.0`), pinning `sespy[pdf,bayes] @ git+https://github.com/razinkele/SESPy@v1.19.0`.
- **Long runs** (full e2e, MosaicSES suite):
  - Launch them detached with PowerShell `Start-Process` through `micromamba.bat run`, logging to a file.
  - Poll with bounded `Start-Sleep`.
  - Port 8000 must be free before and after.
  - Never edit a tree while its suite runs.

## Review Focus

1. **Multi-attractor basin splits.** The prototype was verified on single-cluster random cores and two shipped networks. A reasonable user expects correct basins on multi-cluster cores with bridges and fan-in. Pin it with the shape-diverse differential test (Task 1).
2. **Float ties through the kernel and the partial-column evaluation.** Weights like 0.1 + 0.2 − 0.3 must resolve as `boolean_attractors` does. Pin it with differential tests using float weights (Task 1).
3. **Results honest about their method.** An estimated basin must never be shown as exact, and a sampled search never as complete. Pin it in the result-shape tests (Tasks 1–2) and the UI tests (Tasks 5–6).
4. **Networks over 62 nodes.** No int64 packing may sneak in (Caribbean has 78). Pin it with a Caribbean test in Task 2.
5. **Stale or failed background runs** must not overwrite or crash the panel. Pin it with generation-drop and error-path tests (Task 5).

---

## Part A — Library (repo SESPy)

Worktree: `git -C "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy" worktree add -b feat/boolean-scale C:/Users/arturas.baziukas/AppData/Local/sespy-boolscale-lib origin/main`. Test PYTHONPATH is the worktree itself.

### Task 1: Kernel and exact core search

**Files:**
- Modify: `sespy/dynamics.py` (comment at 228–231; new code after `boolean_attractors`)
- Create: `tests/test_boolean_core.py`
- Create: `tests/_boolean_shapes.py` (random network generator for tests)

**Interfaces:**
- Produces:
  - `_boolean_step(rules, X: np.ndarray, nodes: Sequence[int] | None = None) -> np.ndarray` (uint8 `(S, n)` in and out);
  - `_boolean_partition(rules) -> tuple[list[int], list[int], list[int]]` (U, C, R);
  - `boolean_attractors_core(rules, *, max_core=BOOLEAN_MAX_CORE, basin_budget=BOOLEAN_BASIN_BUDGET, basin_samples=10_000, seed=0) -> dict`;
  - the constants `BOOLEAN_MAX_CORE`, `BOOLEAN_BASIN_BUDGET` and `BOOLEAN_MAX_NODES_TOTAL`.
- Task 2 reuses `_boolean_step` and `_boolean_partition`.

- [ ] **Step 1: Write the shape generator.** `tests/_boolean_shapes.py` provides `random_shape(rng, n_max=14) -> np.ndarray`, a signed matrix in the orientation `create_boolean_rules` reads. It mixes: 1–3 cycle clusters (rings plus random chords), bridges between clusters, upstream chains with fan-in into the core, read-out chains, some upstream-to-read-out edges, and weights from `{±1, ±0.1, ±0.2, ±0.3, ±0.7}`. Include a `shape_counts()` helper so a test can assert the mix is exercised.
- [ ] **Step 2: Write the failing tests** in `tests/test_boolean_core.py`:
  ```python
  def _as_sets(res):  # {frozenset(states): basin_size}
  @pytest.mark.parametrize("seed", range(200))
  def test_core_equals_boolean_attractors_on_random_shapes(seed):
      rules = create_boolean_rules(random_shape(np.random.default_rng(seed)))
      got = boolean_attractors_core(rules)
      want = boolean_attractors(rules, max_nodes=20)
      assert got["basin_method"] == "exact"
      assert _as_sets(got) == _as_sets(want)
  def test_shape_generator_exercises_multi_cluster_and_bridges():  # >= 25% of seeds have >= 2 clusters, etc.
  def test_core_on_shipped_multi_attractor_networks():  # minimal_demo, offshore_wind: equal to boolean_attractors incl. basins
  def test_fisheries_template_is_all_off_only():  # n_nodes 26, core_size 14, all_off_only True, basin_size == 2**26
  def test_lagoon_central_has_four_attractors():  # MosaicSES venice lagoon_central project dict copied to tests/data
  def test_result_shape_and_ordering():  # keys per spec §3.3; cycles start at min state; basin_fraction desc
  def test_core_too_large_sentinel():  # a 21-node single ring -> error "core_too_large", core_size 21
  def test_step_matches_reference_transition():  # _boolean_step on all states of a 10-node net == per-state loop
  def test_basin_sampled_path_when_budget_tiny():  # basin_budget=1 -> basin_method "sampled", basin_size None, fractions sum ~1, attractor set still exact
  def test_acyclic_network_core_zero():  # small_scale_fisheries: core_size 0, one all-off attractor
  ```
  Copy the shipped files the tests need into `tests/data/boolean/`, and use only public library templates or MosaicSES example data.
- [ ] **Step 3: Run them and watch them fail.** Run `micromamba run -n shiny python -m pytest tests/test_boolean_core.py -q`. Expected: FAIL, because the names are not defined.
- [ ] **Step 4: Implement it per spec §3.3.**
  - `docs/superpowers/specs/boolean-scale-probes/core_reduction.py` is a correct but slow reference for the steps.
  - Replace its int64 packing with the uint8-matrix kernel.
  - Evaluate only core columns in the core map: the full matrix with U = u* and R = 0.
  - Basins dedupe the upstream input sequences, as the spec says.
  - Update the comment at 228–231 to say the app uses `boolean_attractors_core` and that `boolean_attractors` keeps its cap for library callers.
- [ ] **Step 5: Run the tests to verify they pass.** Run `micromamba run -n shiny python -m pytest tests/test_boolean_core.py tests/test_dynamics.py -q`. Expected: all pass.
- [ ] **Step 6: Commit.** `git add sespy/dynamics.py tests/test_boolean_core.py tests/_boolean_shapes.py tests/data/boolean && git commit -m "feat(dynamics): exact feedback-core Boolean attractor search"`

### Task 2: Sampled search for large cores

**Files:**
- Modify: `sespy/dynamics.py`
- Create: `tests/test_boolean_sampled.py`

**Interfaces:**
- Consumes: `_boolean_step` (Task 1).
- Produces: `boolean_attractors_sampled(rules, n_samples=2000, *, max_steps=1000, seed=0) -> dict` (spec §3.4).

- [ ] **Step 1: Write the failing tests:**
  ```python
  def test_sampled_result_shape():  # keys per spec; method "sampled"; no "basin_size" anywhere
  @pytest.mark.parametrize("seed", range(30))
  def test_sampled_attractors_subset_of_exact(seed):  # random_shape, n <= 14; frozensets subset of boolean_attractors'
  def test_sampled_hits_sum():  # sum(hits) + n_unconverged == n_samples; fraction == hits / n_samples
  def test_sampled_deterministic_for_seed():
  def test_sampled_unconverged_counted():  # 3-node positive ring, max_steps=1 -> n_unconverged > 0
  def test_sampled_caribbean_78_nodes():  # runs, no error, states are ints >= 2**62 possible, < 10 s
  def test_sampled_history_budget_lowers_max_steps():  # n_samples=1000, max_steps=100_000 -> echoed 10**7 // 1000 - 1
  def test_sampled_clamps_and_too_large():  # n_samples=0 -> 1; 201 nodes -> "too_large"
  ```
- [ ] **Step 2: Run them and watch them fail.** Run `micromamba run -n shiny python -m pytest tests/test_boolean_sampled.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement it per spec §3.4.** Store history as packed bytes (`np.packbits` per row) and detect repeats per trajectory with a dict of row bytes. Cycle states become Python ints via `int.from_bytes` of the bit-reversed row, matching bit i = node i, with a test for the encoding.
- [ ] **Step 4: Run the tests to verify they pass.** Run `micromamba run -n shiny python -m pytest tests/test_boolean_sampled.py tests/test_boolean_core.py tests/test_dynamics.py -q`. Expected: all pass.
- [ ] **Step 5: Commit.** `git add sespy/dynamics.py tests/test_boolean_sampled.py && git commit -m "feat(dynamics): sampled Boolean attractor search for cores above the exact limit"`

### Task 3: Benchmark, translations, public API, release 1.19.0

**Files:**
- Create: `tests/bench_boolean_core.py` (not collected)
- Create: `tests/test_translations_boolean_scale.py`
- Modify: `sespy/translations/core.json`, `tests/test_public_api.py`, `sespy/__init__.py`, `pyproject.toml`, `CHANGELOG.md`

- [ ] **Step 1: Benchmark.** `tests/bench_boolean_core.py` builds a random network of about 40 nodes with a 20-node core, then times the attractor set and peak memory (`tracemalloc`), 3 runs. Run `micromamba run -n shiny python tests/bench_boolean_core.py`. Gate: median ≤ 5 s and peak ≤ 300 MB. If it fails, stop and report: `BOOLEAN_MAX_CORE` depends on it.
- [ ] **Step 2: Write the failing tests.**
  - The translation test checks that every spec §3.5 key exists with all 9 languages, non-empty values and exactly the placeholders `{n} {core}` / `{samples}` / `{core} {max}` / `{n} {seed} {unconverged} {max_steps}`.
  - Add `boolean_attractors_core`, `boolean_attractors_sampled` and the three constants to `tests/test_public_api.py`.
- [ ] **Step 3: Run them and watch them fail.** Then add the keys with the spec's English text in all 9 languages.
- [ ] **Step 4: Run the full library suite.** Run `micromamba run -n shiny python -m pytest -q`. Expected: all pass (the 1.18.0 baseline was 2451).
- [ ] **Step 5: Release commit.** Bump to 1.19.0. The CHANGELOG lists the core search, the sampled search, the translation keys, and `boolean_attractors` as unchanged. Commit: `git commit -am "release: 1.19.0 — feedback-core and sampled Boolean attractor search"`.

### Task 4: Library hand-off (user)

- [ ] **Step 1:** Give the user one-liners: push the branch; `gh pr create` with a body file; after CI is green, merge; `git tag -a v1.19.0 -m v1.19.0 <merge sha>` and push the tag. Use a `~/` helper script if a line would wrap.
- [ ] **Step 2: Verify.** `git ls-remote origin "refs/tags/v1.19.0^{}"` must equal the merge commit, and `git diff --stat <tested head> v1.19.0` must be empty.

---

## Part B — App (repo sespy-app)

Worktrees:
- App: `git -C C:/Users/arturas.baziukas/AppData/Local/sespy-app worktree add -b feat/boolean-scale C:/Users/arturas.baziukas/AppData/Local/sespy-app-boolscale origin/main`.
- Library: `git -C "<OneDrive SESPy>" worktree add --detach C:/Users/arturas.baziukas/AppData/Local/sespy-lib-v1190 v1.19.0`.
- PYTHONPATH is `<sespy-app-boolscale>;<sespy-lib-v1190>`, with cwd = the app worktree.

### Task 5: Boolean module — background core search, sampled fallback, all-off sentence

**Files:**
- Modify: `sespy_app/modules/analysis_boolean.py`
- Replace: `tests/test_analysis_boolean_clamp.py` with `tests/test_analysis_boolean_route.py`

**Interfaces:**
- Consumes: `dynamics.boolean_attractors_core`, `dynamics.boolean_attractors_sampled`, and the spec §3.5 keys.
- Keeps: `analysis_boolean_server(id, project_data, event_bus, translator=None)` (pinned by MosaicSES `test_compartments_module.py:297`) and the inputs `direction` and `run_boolean`. The `max_nodes` input is removed.

- [ ] **Step 1: Write the failing tests.** Use `shiny.testserver.test_server`, as the old clamp test does, and wait for the ExtendedTask to settle:
  ```python
  def test_routes_to_core_search(monkeypatch):  # spy: core called once with defaults; sampled not called
  def test_core_too_large_falls_back_to_sampled_with_fixed_args(monkeypatch):  # sampled called with n_samples=2000, seed=0, max_steps=1000
  def test_all_off_renders_sentence_not_table():  # sample project -> panel HTML has boolean.all_off text, no <table>
  def test_core_info_line():  # Fisheries project -> "26 nodes · 14 in the feedback core"
  def test_sampled_renders_note_and_hits_column():
  def test_stale_generation_is_dropped():
  def test_task_exception_shows_error_not_crash(monkeypatch):
  def test_no_max_nodes_input_in_ui():  # rendered UI has no #boolean-max_nodes
  ```
- [ ] **Step 2: Run them and watch them fail.** Run `micromamba run -n shiny python -m pytest tests/test_analysis_boolean_route.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement it per spec §4.**
  - Read `references/extended-tasks.md` under `micromamba run -n shiny shiny skills path shiny-for-python` first.
  - Follow `analysis_leverage.py:203-232` (generation counter, `asyncio.to_thread`, `_COMPUTING`, logged errors).
  - The Laplacian stays synchronous.
- [ ] **Step 4: Run the app unit suite** (README selection). Expected: all pass (the v1.0.1 baseline was 538 passed / 2 skipped; adjust for the replaced clamp test).
- [ ] **Step 5: Commit.** `git add -A sespy_app/modules/analysis_boolean.py tests/test_analysis_boolean_route.py tests/test_analysis_boolean_clamp.py && git commit -m "feat(boolean): feedback-core search in a background task; sampled fallback; all-off sentence"`

### Task 6: e2e, manual, screenshot, MosaicSES gate

**Files:**
- Modify: `tests/test_boolean_e2e.py`. The 17-node sample now shows the all-off info alert under `#boolean-attractor_panel`, and no `.alert-danger`. Update the docstring.
- Modify: `tests/test_boolean_happy_e2e.py`. Load a multi-attractor template (`offshore_wind` or `minimal_demo`) and assert ≥ 2 table rows and the `core_info` line. Wait for the task result, not a fixed delay.
- Create: `tests/test_boolean_sampled_e2e.py`. Load the Caribbean template and run; assert the `core_too_large` note, the `sampled_note` and ≥ 1 row, with every selector scoped to `#boolean-…` (never a bare `text=`).
- Modify: `docs/MANUAL.md` §17. Regenerate `docs/screenshots/boolean.png` via `tests/make_docs_screenshots.py`.

- [ ] **Step 1: Write and change the e2e scripts** as listed above.
- [ ] **Step 2: Run the full e2e.** Run `micromamba run -n shiny python tests/run_e2e.py --port 8000`, detached. Expected: all pass, apart from a runner-retried flake. `test_intervention_e2e` is a known load flake: rerun it alone 3× if it is red. The server line names `sespy-lib-v1190` 1.19.0.
- [ ] **Step 3: Update the manual and screenshot.** MANUAL §17 covers the feedback core, the exact limit of 20 core nodes, the sampled fallback, and the meaning of the all-off result. Regenerate the screenshot and check it.
- [ ] **Step 4: Run the MosaicSES gate.**
  - Run the full suite from `AppData/Local/mosaicses-split-gate` (detached at `origin/main`) with PYTHONPATH `<mosaicses-split-gate>;<sespy-app-boolscale>;<sespy-lib-v1190>`.
  - Expected: reds only from the baseline set: topbar modal race, equity editor, beforeunload, composite timer, file flows, heatmap_card, risk knot, comparative-header load flake.
  - Rerun any other red 3× alone.
- [ ] **Step 5: Commit.** `git add tests/test_boolean_e2e.py tests/test_boolean_happy_e2e.py tests/test_boolean_sampled_e2e.py docs/MANUAL.md docs/screenshots/boolean.png && git commit -m "test(boolean): e2e for core, all-off and sampled paths; manual §17"`

### Task 7: App 1.1.0 release, plan-4 deferrals ruling, hand-off

**Files:**
- Modify: `pyproject.toml` (1.1.0; pin `@v1.19.0`), `sespy_app/__init__.py`, the `deploy/deploy.sh` `PIN` if it is hard-coded, `CHANGELOG.md`, the MANUAL version line

- [ ] **Step 1: Bump the version.** Bump and re-pin, then run `micromamba run -n shiny python -m pytest tests/test_deploy_script.py -q`. Expected: pass.
- [ ] **Step 2: Rule on the plan-4 deferrals.** Read plan 4's "plan-4 deferrals, for 1.0.2" (`AppData/Local/sespy-plan4/docs/superpowers/plans/2026-11-21-split-stage4-cutover.md` §Follow-ups) and its ledger line "N1–N4 PARKED" (`…/.superpowers/sdd/2026-11-21-split-stage4-cutover/progress.md`).
  - For each item, decide whether a normal second deploy can reach it and whether it can lose a feedback row.
  - If both: fix it with a test in `tests/test_deploy_script.py`.
  - Otherwise: ledger a `Ruling:` that accepts it.
- [ ] **Step 3: Release commit.** Commit: `git commit -am "release: 1.1.0 — feedback-core Boolean search (sespy 1.19.0)"`.
- [ ] **Step 4: Whole-branch review** before the tag.
- [ ] **Step 5: User hand-off.** The user pushes, opens the PR and waits for green CI, then merges and tags `v1.1.0` on the merge commit. The agent verifies with `ls-remote` and checks that the tree equals the reviewed HEAD.

---

## Part C — Deploy

### Task 8: Second split-layout deploy (user runs; agent verifies)

- [ ] **Step 0: Agent pre-checks.**
  - Create the deploy tree: `git -C C:/Users/arturas.baziukas/AppData/Local/sespy-app worktree add --detach C:/Users/arturas.baziukas/AppData/Local/sespy-app-v110 v1.1.0`. It must describe as exactly `v1.1.0` and be clean.
  - `sespy-lib-v1190` describes as exactly `v1.19.0` and is clean.
  - `sespy-app` is still at `v1.0.1` and clean.
  - `check-ignore -v deploy/config.env` in the new tree names `.gitignore`.
  - Live MosaicSES `verify_live.py --expect-version 0.9.3` passes.
- [ ] **Step 1: Config hand-off.** The agent writes a `~/` helper script and the user runs it; the agent never reads the file. The script:
  1. copies `sespy-app/deploy/config.env` to `sespy-app-v110/deploy/config.env`;
  2. runs `sed -i` on the `DEPLOY_LIBRARY_ROOT=` line, pointing it at `C:/Users/arturas.baziukas/AppData/Local/sespy-lib-v1190`;
  3. prints both grep counts (the new library line, `DEPLOY_MOSAIC_DIR=`), each of which must be 1.
- [ ] **Step 2: Deploy (user).** Run `bash C:/Users/arturas.baziukas/AppData/Local/sespy-app-v110/deploy/deploy.sh`. Expected: "Deploying SESPy app v1.1.0 with sespy library v1.19.0", check_live ok, no `!!` lines, and MosaicSES restarted.
- [ ] **Step 3: Live checks (agent, read-only).**
  - Playwright on `https://laguna.ku.lt/SESPy/`:
    - About shows `SESPy app 1.1.0 · sespy library 1.19.0`;
    - Fisheries shows "26 nodes · 14 in the feedback core" and the all-off sentence;
    - a multi-attractor template shows its table;
    - Caribbean shows the sampled path;
    - there is no `.alert-danger`.
  - MosaicSES: run `verify_live.py`, plus the Compartments → Edit Data and Boolean & Laplacian tabs, which must render without `Error:`.
  - The user runs `ssh razinka@laguna.ku.lt ls /srv/shiny-server/SESPy/sespy_app/logs`, which must list `feedback.db`.
- [ ] **Step 4: Rollback trigger.** On a non-cosmetic failure, the user runs `bash C:/Users/arturas.baziukas/AppData/Local/sespy-app/deploy/deploy.sh --rollback`.
- [ ] **Step 5:** Update memory and offer worktree cleanup.

## Follow-up (not in this plan)
- **Phase 2, driver scenarios** (spec §7): a separate spec after phase 1 ships.
