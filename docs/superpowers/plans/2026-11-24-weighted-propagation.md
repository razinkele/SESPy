# Weighted Signed Propagation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Influence from an intervention spreads along links weighted by strength. It keeps its sign and dissipates (decay, stop, sinks). The Intervention panel reports, per element:
- reach, first arrival, signed mass and the positive/negative shares;
- an uncertainty check over perturbed maps, led by "Reached in % of variants" and "Sign holds in %";
- a CSV export.

**Architecture:**
- **Library (sespy 1.21.0).**
  - New `dynamics.signed_propagation`: one vectorised walk with token-indexed draws and a batch-means sign rule.
  - New `dynamics.propagation_sensitivity`: its own same-token baseline plus variants perturbed by `network._perturbed_connections`, each with the shared walk seed.
  - `token_diffusion` is untouched.
- **App (sespy-app 1.3.0).**
  - A pure helper `_propagation_view.py` builds rows, the uncertainty join, summary lines, the CSV and presets.
  - `analysis_intervention.py` replaces the diffusion section and runs both computations in ExtendedTasks with the generation guard.
- **Deploy.** Then deploy as for 1.2.0.

**Tech Stack:** Python 3.11+, numpy, Shiny for Python ≥ 1.7 (`@reactive.extended_task`, `@render.download`), matplotlib, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-22-weighted-propagation-design.md` (approved 2026-11-24, `e38e735`). Its decisions 1–4 and every "my call" are binding. Read the spec before each task; this plan argues from it.

## Global Constraints

- **Machine: DELL.**
  - Python only via `C:/Users/DELL/miniconda3/envs/mosaicses/python.exe` (written `PY` below).
  - The conda `shiny` env has a broken SciPy (`scipy._cyutility … slice_memviewslice`), and there is no micromamba on DELL.
  - No venvs, no `pip install`, no new dependencies, and no changes to the `mosaicses` env.
- **Editable-install shim (round-2 blocker).**
  - The `mosaicses` env holds a finder-based editable install of the monolith sespy 1.17.1 (`site-packages/__editable__.sespy-1.17.1.pth`). It resolves `sespy.modules` even with the library first on PYTHONPATH, so the app's `tests/conftest.py` monolith guard aborts every session.
  - Part B setup creates `C:/Users/DELL/AppData/Local/sespy-pyshim/sitecustomize.py` with exactly:
    ```python
    import sys
    sys.meta_path[:] = [f for f in sys.meta_path if "__editable___sespy_" not in (getattr(f, "__module__", "") or "")]
    ```
  - `SHIM = C:/Users/DELL/AppData/Local/sespy-pyshim` goes **first** on every app, e2e, screenshot, perf and MosaicSES PYTHONPATH.
  - The library's own suite does not need it; the library has no monolith guard.
- **bash from PowerShell.** A PowerShell-launched run that shells out to `bash` (`test_deploy_script.py`) first sets `$env:PATH = "C:\Program Files\Git\usr\bin;C:\Program Files\Git\bin;" + $env:PATH`. Otherwise `bash` resolves to WSL and the tests fail. The Bash tool already uses Git Bash.
  - Single-line commands or `.py` files, never multi-line `python -c`.
- **Git safety.**
  - **Never run `git worktree prune`, `git gc --prune` or `git worktree remove` on another machine's entries in SESPy.** Its `.git` is OneDrive-synced with the X1 laptop.
  - Do not check out `docs/intervention-pathways` anywhere.
- **Trees you must not touch:**
  - `AppData/Local/sespy-app-v120`: the live deploy tree with the real `config.env`.
  - `AppData/Local/sespy-lib-v1200`: the live library.
  - `AppData/Local/sespy-app-v110` and `sespy-lib-v1190`: the rollback pair.
  - `AppData/Local/MosaicSES` stays on branch `main` at its checked-out commit (`d382147`); Task 7 only runs its suite there.
  - Any run that puts a must-not-touch tree on PYTHONPATH sets `PYTHONDONTWRITEBYTECODE=1` and passes `-p no:cacheprovider`.
  - Never read any `deploy/config.env`.
- **User-only steps.** The user runs every push, PR merge and tag, via short `!` one-liners or `~/` helper scripts.
- **Weights:** `bayes.STRENGTH_LINK`, imported at the top of `dynamics.py` (`from .bayes import STRENGTH_LINK`). `bayes` does not import `dynamics`, so this is cycle-free (checked in round-1 review). Missing or unknown strength counts as `"medium"` and is counted.
- **Batches:** reuse `dynamics._DIFFUSION_BATCHES` (20) and the t-critical value computed as in `token_diffusion` (lazy `from scipy import stats`).
- **Signatures (exact):**
  - `signed_propagation(isa, source, *, n_steps=8, n_tokens=1000, decay=0.8, stop_prob=0.15, transition="weighted", seed=0) -> dict`
  - `propagation_sensitivity(isa, source, *, n_runs=200, base=0.5, flip_mode="confidence", draw_strength=False, seed=0, n_steps=8, n_tokens=1000, decay=0.8, stop_prob=0.15, transition="weighted") -> dict`
- **Clamps:**
  - `n_steps` [1, 100], `n_tokens` [1, 100000], `decay` and `stop_prob` [0, 1];
  - `n_runs` [1, 2000], `base` [0, 1].
  - Clamped values are echoed.
  - `transition` not in `{"weighted", "equal"}` raises `ValueError`; `flip_mode` is validated as in `path_sensitivity`.
- **Translations:** new `propagation.*` keys in the library's `sespy/translations/core.json`, inside `"translation"`, with English text in all 9 languages (`en es fr de lt pt it no el`). The `diffusion.*` keys stay.
- **Versions.**
  - Library 1.21.0 (tag `v1.21.0`).
  - App 1.3.0 (tag `v1.3.0`), pinning `sespy[pdf,bayes] @ git+https://github.com/razinkele/SESPy@v1.21.0`.
- **MosaicSES contract.** It pins `analysis_intervention_server(id, project_data, event_bus, translator)`, which stays unchanged. A grep of the MosaicSES clone (`d382147`) finds no `diffusion_*` ids or `diffusion.` keys.
- **Long runs** (full e2e, MosaicSES suite, `test_deploy_script.py`):
  - Launch detached with PowerShell `Start-Process` running `PY`, logging to a file in the scratchpad.
  - Poll with bounded `Start-Sleep`.
  - Port 8000 must be free before and after. Never edit a tree while its suite runs.
- **Shiny reference:** before Tasks 6–7, read `references/reactivity.md`, `extended-tasks.md`, `test-server.md` (server-side tests) and `testing.md` (Playwright) from `PY -m shiny skills path shiny-for-python` (project `CLAUDE.md`).
- **Spec erratum E2:** spec §Walk claimed a token "whose route avoids a changed link" keeps its route. That is false: a dropped out-edge renormalises its node. The spec now says tokens that never visit a changed node keep their routes, and `test_untouched_subtree_keeps_routes` pins it.
- **Spec erratum E1:** spec §Rows says "`np.median`, `method="lower"`", but `np.median` has no `method` keyword (TypeError on numpy 2.5.4). Use `int(np.quantile(first_steps, 0.5, method="lower"))`.

## Translation keys

Added by Task 3 to the library `core.json`. Tasks 5 and 6 use them by these names. The library is tagged before Part B, so **no task in Part B may add a key**.

| Key | English | Placeholders |
|---|---|---|
| `propagation.title` | "Signed propagation" | – |
| `propagation.source` | "Intervention (source)" | – |
| `propagation.preset` | "Settings" | – |
| `propagation.preset_interactive` | "Interactive (1,000 tokens)" | – |
| `propagation.preset_report` | "Report (10,000 tokens)" | – |
| `propagation.preset_equal` | "Equal links, no decay (Donlan et al. 2026)" | – |
| `propagation.preset_custom` | "Custom" | – |
| `propagation.advanced` | "Advanced settings" | – |
| `propagation.steps` | "Steps" | – |
| `propagation.decay` | "Decay per step" | – |
| `propagation.stop` | "Stop chance per step" | – |
| `propagation.transition` | "Link choice" | – |
| `propagation.transition_weighted` | "By link strength" | – |
| `propagation.transition_equal` | "Equal" | – |
| `propagation.run` | "Run propagation" | – |
| `propagation.hint` | "Not simulated yet: choose an intervention and press Run propagation." | – |
| `propagation.computing` | "Simulating {n} tokens…" | n |
| `propagation.none` | "Nothing is reached from this element: it has no outgoing links in the current model." | – |
| `propagation.col_element` | "Element" | – |
| `propagation.col_reach` | "Reach" | – |
| `propagation.col_first` | "Median first step" | – |
| `propagation.col_pos` | "+ share" | – |
| `propagation.col_neg` | "− share" | – |
| `propagation.col_net` | "Net mass" | – |
| `propagation.col_sign` | "Sign" | – |
| `propagation.mass_line` | "Of the injected influence: {decayed}% decayed, {stopped}% stopped, {absorbed}% absorbed at dead ends, {moving}% still moving after step {n}." | decayed, stopped, absorbed, moving, n |
| `propagation.default_strength` | "{k} links have no strength rating; counted as medium." | k |
| `propagation.caption` | "Structural simulation under stated assumptions; not a forecast or effect size." | – |
| `propagation.unc_run` | "Estimate uncertainty" | – |
| `propagation.unc_computing` | "Running {n} perturbed versions of the network…" | n |
| `propagation.unc_caption` | "{n} perturbed versions (seed {seed}): each link may drop out or flip sign, more often the lower its confidence." | n, seed |
| `propagation.unc_default_conf` | "{k} links have no confidence; counted as 3." | k |
| `propagation.unc_tokens` | "Uncertainty used {n} tokens per version." | n |
| `propagation.col_reached` | "Reached in % of variants" | – |
| `propagation.col_holds` | "Sign holds in %" | – |
| `propagation.balanced` | "—, balanced" | – |
| `propagation.rarely` | "—, rarely reached" | – |
| `propagation.download` | "Download propagation (CSV)" | – |
| `propagation.error` | "The propagation run failed: {error}" | error |

## Review Focus

1. **Degenerate parameters** (`decay=0`, `decay=1`, `stop_prob=1`, `n_tokens=1`).
   - The person expects numbers or "—", never NaN, an error, or a blank panel.
   - Pinned by `test_degenerate_parameters_no_nan` (Task 1) and `test_rows_render_none_shares_as_dash` (Task 5).
2. **The source is removed by the ablation above, or has no out-links.**
   - The person expects the "none" message and no uncertainty button, not a crash.
   - Pinned by `test_source_without_out_links_shows_none_and_no_uncertainty_button` (Task 6).
3. **A Report-preset row with no counterpart in the 1,000-token uncertainty result.**
   - The person expects "—, rarely reached", not a shifted row or a KeyError.
   - Pinned by `test_join_marks_rows_missing_from_uncertainty` (Task 5).
4. **The settings change while "Estimate uncertainty" runs.**
   - The person expects the old shares never to appear beside the new table.
   - Pinned by `test_stale_uncertainty_dropped_when_settings_change` (Task 6).
5. **Element labels starting with `=`, `+`, `-` or `@` in the CSV.**
   - The person expects them neutralised as in the path CSV.
   - Pinned by `test_csv_neutralises_formula_labels` (Task 5).

---

## Part A — Library (repo SESPy)

**Worktree:**
- Create it with `git -C "C:/Users/DELL/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy" worktree add -b feat/weighted-propagation C:/Users/DELL/AppData/Local/sespy-prop-lib origin/main`.
- Then `git cherry-pick eff1dd9..docs/weighted-propagation`: the spec commits plus this plan, so they ship with the code. `origin/main` already has the skeleton spec.
- Run with cwd = that worktree and `PYTHONPATH=.`.
- Baseline before starting: `PY -m pytest tests/ -q -p no:cacheprovider` all pass (1.20.0: 2846 passed, 2 skipped).

### Task 1: `signed_propagation`

**Files:**
- Modify: `sespy/dynamics.py` (new function after `token_diffusion`, about line 1466; shared helpers for the graph build and the sign rule may be factored out of `token_diffusion` only if its outputs stay bit-identical, which `test_token_diffusion_sample_golden` guards)
- Create: `tests/test_propagation.py`

**Interfaces:**
- **Produces:** `signed_propagation` with the result shape in spec §"Library: signed_propagation":
  - result keys: `rows`, `source`, `n_steps`, `n_tokens`, `decay`, `stop_prob`, `transition`, `seed`, `n_reached`, `n_default_strength`, `n_batches`, `mass` = `{decayed, stopped, absorbed, in_transit}`, as shares of `n_tokens`;
  - row keys: `id`, `label`, `reach_probability`, `first_arrival_min`, `first_arrival_q50` (int), `positive_mass`, `negative_mass`, `signed_mass_mean`, `positive_share`, `negative_share` (float or `None`), `net_sign` (`"+"`, `"-"` or `"~"`).
- **Empty shape (pinned here; the spec leaves it unnamed):**
  - Every top-level key is present, with the clamped parameters echoed.
  - `rows=[]`, `n_reached=0`, `n_batches=0`, `n_default_strength=0`.
  - `mass = {"decayed": 0.0, "stopped": 0.0, "absorbed": 0.0, "in_transit": 0.0}`: no token moved.
  - Returned for an unknown source, an empty model, or a source with no out-links.
  - The identity `sum(mass) == 1` holds only for non-empty results.
- **Private, also used by Task 2:** `_signed_walk(...)`, which `signed_propagation` itself calls (see the Structure note).
  - It returns at least everything `signed_propagation` needs to build rows and `mass`: per-element reach, first-arrival min and median, positive and negative mass, signed mass, `net_sign`, the mass buckets and `n_default_strength`.
  - Reach, signed mass and `net_sign` are the subset Task 2 reads.
  - The builder picks the exact private signature.

- [ ] **Step 1: Write the failing tests.** Use small `IsaData` fixtures built from `Element`/`Connection` (the `sespy.data_structure` dataclasses):
  ```python
  def test_chain_reaches_in_order():            # P3: S->A->B->C, decay=1, stop_prob=0, n_tokens=200: reach 1.0 each; first_arrival_q50 == 1, 2, 3
  def test_negative_edge_flips_once():          # P4: S->A(+)->B(-)->C(+): positive_share A == 1.0; B and C negative_share == 1.0
  def test_seed_reproducible_and_distinct():    # P5: same args equal (==); seed 1 differs on a branching graph
  def test_mass_identity_random_graphs():       # P6: 30 random graphs (source given >= 1 out-link) x params incl. decay 0/1, stop 0/1: sum(mass.values()) == pytest.approx(1.0, abs=1e-9)
  def test_empty_shape_mass_is_zero():           # no out-links: every mass value 0.0, all top-level keys present
  def test_weighted_choice_follows_strength():  # S->A strong, S->B weak, n_tokens=20000, n_steps=1, stop 0: reach A ≈ 0.80/1.10 within 0.02
  def test_equal_transition_ignores_strength(): # same graph, transition="equal": reach A ≈ 0.5 within 0.02; n_default_strength == 0
  def test_default_strength_counted():          # one connection strength="?" -> n_default_strength == 1, weighted as medium
  def test_degenerate_parameters_no_nan():      # decay=0 -> shares None, masses 0.0; stop_prob=1 -> reach only first hop; n_tokens=1 -> n_batches 1, every net_sign "~"; no NaN/inf in any float
  def test_balanced_node_is_tilde():            # S->A(+)->T(+), S->B(+)->T(-), equal weights: T net_sign "~" at seeds 0 and 1 (as test_token_diffusion_balanced_node_is_contested_at_both_seeds); see the seed note below
  def test_untouched_subtree_keeps_routes():   # token-indexed draws: base S->A, A->E, S->B, B->C, B->D; perturbed copy omits A->E only: tokens that never visit A have identical visited sets (compare _signed_walk per-token outputs, or reach of C and D bit-equal)
  def test_sink_absorbs_and_counts():           # S->A with A a sink, decay=1, stop 0: mass absorbed == 1.0, in_transit == 0
  def test_parallel_connections_last_wins():    # two S->A connections, last one "-": A negative_share == 1.0
  def test_empty_shapes():                      # unknown source / no out-links / empty model -> rows [] and n_reached 0, no raise
  def test_bad_transition_raises():             # transition="x" -> ValueError
  def test_clamps_echoed():                     # n_steps=0 -> 1, decay=2 -> 1.0, stop_prob=-1 -> 0.0
  def test_equal_setting_matches_token_diffusion_reach_set():  # P-equal: 6-node DAG, both called with n_tokens=5000, n_steps=6, seed=0 (signed: decay=1, stop_prob=0, transition="equal"): set of row ids equal
  def test_unchanged_map_token_indexed_reproduces():  # _signed_walk on isa vs on an IsaData with identical connections in a new list: identical arrays
  ```
  **Seed note:** the 95% rule mislabels a truly balanced node about 5% of the time (round-2 dry run: 11 of 200 seeds). If a correct implementation fails a balanced test at seed 0 or 1 because of its draw order, pin two other seeds that pass. Name them in the test and the commit message, and never loosen the sign rule. This applies to the Task 2 balanced test too.

  **Structure for Task 2:** `signed_propagation` must call the module-level `_signed_walk` (looked up at call time), so Task 2's monkeypatch reaches both the baseline and the variants.

  **`n_default_strength`** counts deduplicated kept pairs (after last-wins), not raw connections.

- [ ] **Step 2: Run them and watch them fail.** `PY -m pytest tests/test_propagation.py -q -p no:cacheprovider`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement `signed_propagation` in `sespy/dynamics.py`,** following spec §Walk exactly:
  - the order move → sign → decay → deposit → stop → sink;
  - every arrival deposits;
  - token-indexed draws: `n_tokens` uniforms for the choice and `n_tokens` for the stop, every step, whether live or not;
  - out-edges ordered by target position in `isa.elements`;
  - choice by cumulative weights with `searchsorted`;
  - per-token first-visit step as an int16 array;
  - `first_arrival_q50` per spec erratum E1.

  Sign rule: batch-means Student t at 95% over `min(_DIFFUSION_BATCHES, n_tokens)` batches, `"~"` with one batch, the same as `token_diffusion`'s `net_sign`. The docstring states the semantics, the conventions and that it never raises except on a bad `transition`.
- [ ] **Step 4: Run the new tests and the full library suite.** Expected: all pass. `test_token_diffusion_*` unchanged.
- [ ] **Step 5: Commit.** `git commit -m "feat(dynamics): signed_propagation — weighted signed walk with decay, stop and mass accounting"`

### Task 2: `propagation_sensitivity`

**Files:**
- Modify: `sespy/dynamics.py`
- Modify: `tests/test_propagation.py`

**Interfaces:**
- **Consumes:**
  - Task 1's `signed_propagation` and `_signed_walk`;
  - `network._perturbed_connections(isa, base, rng, flip_mode)` and `network._coerce_confidence`, imported inside the function;
  - `path_sensitivity`'s `draw_strength` rule (`replace(c, strength=rng.choice(c.ratings).strength) if c.ratings else c`).
- **Produces:**
  - result keys: `rows`, `source`, `n_runs`, `base`, `flip_mode`, `draw_strength`, `seed`, `n_steps`, `n_tokens`, `decay`, `stop_prob`, `transition`, `n_default_confidence`, `n_default_strength`;
  - rows follow the baseline at the same `n_tokens`, carrying `id`, `label`, `reach_probability`, `net_sign`, plus `reached_share`, `sign_holds_share` (float or `None`), `reach_q05`, `reach_q50`, `reach_q95`, `signed_mass_q05`, `signed_mass_q50`, `signed_mass_q95`.

- [ ] **Step 1: Write the failing tests:**
  ```python
  def test_confidence5_map_is_certain():          # P8: branching map, all confidence=5: every reached_share == 1.0; sign_holds_share == 1.0 or None where net_sign "~"
  def test_dropping_only_path_lowers_reached():   # P8: S->A->B confidence=1, base=1.0: B reached_share < 1.0
  def test_tilde_baseline_gives_none():           # balanced T -> sign_holds_share is None, at seeds 0 and 1
  def test_tilde_variant_counts_not_held():       # fixture where A's baseline is "+"; monkeypatch _signed_walk with a fake that passes the FIRST call (the baseline) to the real function and returns "~" for A on every later call: sign_holds_share == 0.0
  def test_source_cut_counts_as_zero_not_skipped():  # S->A confidence=1, base=1.0 (always dropped): A reached_share == 0.0, n_runs echoed
  def test_seed_reproducible():                   # P5
  def test_seed_scheme():                         # run k perturbs with default_rng(SeedSequence(seed).spawn(n_runs)[k]) and walks with seed=seed (spy on _signed_walk seeds)
  def test_quantiles_include_unreached_as_zero(): # reach_q05 == 0.0 when reached_share <= 0.05
  def test_default_confidence_counts_unparseable_only():  # confidence None and "x" counted (2); 0 and 7 not counted
  def test_bad_flip_mode_raises():
  def test_empty_baseline_shape():                # unknown source -> rows [], no raise
  ```
- [ ] **Step 2: Run them and watch them fail.**
- [ ] **Step 3: Implement `propagation_sensitivity`** per spec §"Library: propagation_sensitivity", including the "why a shared walk seed" rationale and the "elements reached only in variants are not listed" note in the docstring.
- [ ] **Step 4: Timing sanity.**
  - Write `tests/test_propagation.py::test_defaults_fast_on_sample`, marked to skip unless `SESPY_TIMING=1`.
  - Load `data/sample_ses.json` if the library has it, else build a 17-node fixture.
  - Warm up first (`from scipy import stats` plus one tiny call) so the cold scipy import (~1–15 s) is not timed.
  - Assert `signed_propagation` defaults < 2 s and `propagation_sensitivity` defaults < 30 s.
  - Run it once with `SESPY_TIMING=1`. The real benchmark is in Task 7.
- [ ] **Step 5: Run the full library suite.** Expected: all pass.
- [ ] **Step 6: Commit.** `git commit -m "feat(dynamics): propagation_sensitivity — map-uncertainty robustness over perturbed variants"`

### Task 3: Translations, public API, release 1.21.0

**Files:**
- Modify: `sespy/translations/core.json`, `tests/test_public_api.py`, `sespy/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `README.md` (pin line)
- Create: `tests/test_translations_propagation.py`, modelled on `tests/test_translations_paths.py`

- [ ] **Step 1: Write the key test** for every key in the header section **Translation keys**: exact English text and placeholder sets.
  Assert all 9 languages and the placeholder sets. Assert that `diffusion.title` still exists.
- [ ] **Step 2: Run it and watch it fail, then add the keys.** English text in every language, matching the neighbouring formatting.
- [ ] **Step 3: Public API and release.**
  - Add `"signed_propagation"` and `"propagation_sensitivity"` to the dynamics list in `tests/test_public_api.py`, and export them if `sespy/__init__.py` re-exports dynamics names.
  - Version 1.21.0 in `pyproject.toml` and `sespy/__init__.py`.
  - CHANGELOG 1.21.0: the new functions, `token_diffusion` unchanged, citing the development note.
  - README pin `@v1.21.0`.
- [ ] **Step 4: Run the full library suite.** Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "release: sespy 1.21.0 — weighted signed propagation and map-uncertainty sensitivity"`

### Task 4: Library hand-off (user)

- The controller runs the whole-branch review (most capable model).
- The agent writes `~/pr121.sh`, `~/tag121.sh` and `~/pr121-body.md`, modelled on the 1.20.0 scripts if present on DELL, otherwise fresh. The tag script has a null-safe merge-commit guard.
- The user pushes, opens the PR, waits for CI (lint red only in files this branch did not touch), merges, and tags `v1.21.0` on the merge commit.
- The agent runs `git fetch origin tag v1.21.0` (the tag is made on GitHub), then verifies that `git ls-remote origin "refs/tags/v1.21.0^{}"` equals the merge commit and that `git diff --stat <reviewed head> v1.21.0` is empty.

---

## Part B — App (repo sespy-app)

**Worktrees:**
- App: `git -C C:/Users/DELL/AppData/Local/sespy-app worktree add -b feat/weighted-propagation C:/Users/DELL/AppData/Local/sespy-app-prop origin/main`.
- Library: `git -C "<OneDrive SESPy>" worktree add --detach C:/Users/DELL/AppData/Local/sespy-lib-v1210 v1.21.0`. Before the tag exists, use the reviewed library head and move the worktree to the tag afterwards; `deploy.sh` requires the exact tag.
- Shim: create `C:/Users/DELL/AppData/Local/sespy-pyshim/sitecustomize.py` (Global Constraints) if absent.
- PYTHONPATH is `C:/Users/DELL/AppData/Local/sespy-pyshim;C:/Users/DELL/AppData/Local/sespy-app-prop;C:/Users/DELL/AppData/Local/sespy-lib-v1210`, with cwd = the app worktree.
- Check: the conftest session line prints `sespy 1.2x.x from …sespy-lib-v1210` (or the reviewed head), not an abort.
- Unit suite = the README selection: `PY -m pytest tests/ -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`. Record its 1.2.0 baseline first.

### Task 5: Propagation view helpers

**Files:**
- Create: `sespy_app/modules/_propagation_view.py` (no Shiny, no pyvis imports)
- Create: `tests/test_propagation_view.py`

**Interfaces:**
- **Consumes:**
  - From the `signed_propagation` result: `rows` (keys `id`, `label`, `reach_probability`, `first_arrival_min`, `first_arrival_q50`, `positive_mass`, `negative_mass`, `signed_mass_mean`, `positive_share`, `negative_share`, `net_sign`), `source`, `n_steps`, `n_tokens`, `decay`, `stop_prob`, `transition`, `seed`, `n_default_strength`, `mass` (`decayed`, `stopped`, `absorbed`, `in_transit`, shares of tokens).
  - From the `propagation_sensitivity` result: `rows` (keys `id`, `reached_share`, `sign_holds_share`, `reach_q05/q50/q95`, `signed_mass_q05/q50/q95`), `n_runs`, `base`, `flip_mode`, `draw_strength`, `seed`, `n_tokens`, `n_default_confidence`.
  - Translation keys from the header section **Translation keys**. Placeholders feed as follows:
    - `mass_line`: `decayed`, `stopped`, `absorbed`, `moving` ← `mass["in_transit"]`, as int percent; `n` ← `n_steps`;
    - `default_strength`: `k` ← `n_default_strength`;
    - `unc_caption`: `n` ← `n_runs`, `seed` ← sensitivity `seed`;
    - `unc_default_conf`: `k` ← `n_default_confidence`;
    - `unc_tokens`: `n` ← sensitivity `n_tokens`.
  - `_paths_view._csv_safe(s: str) -> str`, imported, not copied.
- **Produces:**
  - `PRESETS: dict[str, dict]`, with keys `"interactive"`, `"report"`, `"equal"`; values `{n_tokens, n_steps, decay, stop_prob, transition}`:
    - interactive: 1000, 8, 0.8, 0.15, `"weighted"`;
    - report: 10000, 8, 0.8, 0.15, `"weighted"`;
    - equal: 1000, 8, 1.0, 0.0, `"equal"`.
  - `UNCERTAINTY_MAX_TOKENS = 1000`.
  - `propagation_rows(result: dict, t) -> list[dict]`, with keys `id`, `element`, `reach`, `first`, `pos`, `neg`, `net`, `sign`. `id` is the element id the panel joins on:
    - reach `f"{x:.2f}"`, shares `f"{x:.0%}"` or `"—"` when `None`, net `f"{x:+.3f}"`;
    - element is `"label"`.
  - `join_uncertainty(rows_result: dict, sens: dict, t) -> dict[str, tuple[str, str]]`: element id → (reached, holds).
    - reached `f"{x:.0%}"`; holds `f"{x:.0%}"` or `t("propagation.balanced")` when `None`.
    - Ids missing from `sens` map to `(t("propagation.rarely"), t("propagation.rarely"))`.
  - `summary_lines(result: dict, t) -> list[str]`:
    1. `propagation.mass_line`, percentages rounded to an int;
    2. `propagation.default_strength`, only if k > 0.
  - `uncertainty_lines(sens: dict, table_tokens: int, t) -> list[str]`:
    1. `unc_caption`;
    2. `unc_default_conf` if k > 0;
    3. `unc_tokens` if `sens["n_tokens"] < table_tokens`.
  - `propagation_csv(result: dict, sens: dict | None) -> str`, written with the `csv` module.
    - Leading rows: `# source,…`, then one `# key,value` row each for `n_steps`, `n_tokens`, `decay`, `stop_prob`, `transition`, `seed`.
      - When `sens` is present, add `# n_runs`, `# base`, `# flip_mode`, `# draw_strength`, `# uncertainty_n_tokens` and `# uncertainty_seed`. They are prefixed so they never collide with the walk rows.
    - Table rows missing from `sens` get empty uncertainty cells.
    - Then the header, exactly `id,label,reach_probability,first_arrival_min,first_arrival_q50,positive_mass,negative_mass,signed_mass_mean,positive_share,negative_share,net_sign`, plus `,reached_share,sign_holds_share,reach_q05,reach_q50,reach_q95,signed_mass_q05,signed_mass_q50,signed_mass_q95` when `sens`.
    - Raw values, `None` as an empty cell.
    - `id`, `label` and the `# source` value go through `_csv_safe`, as the path CSV does (`_paths_view.py:85-94`).

- [ ] **Step 1: Write the failing tests** with hand-built result dicts:
  ```python
  def test_presets_match_spec():
  def test_rows_format_and_order():
  def test_rows_render_none_shares_as_dash():
  def test_join_marks_rows_missing_from_uncertainty():
  def test_join_balanced_shows_balanced_text():
  def test_summary_lines_conditional_default_strength():
  def test_uncertainty_lines_tokens_note_only_when_fewer():
  def test_csv_header_and_values_match_rows():          # P10: same ids/order; unrounded floats
  def test_csv_with_sensitivity_columns():              # report table (10000) + sens (1000): rows "# n_tokens,10000" and "# uncertainty_n_tokens,1000"; a row missing from sens has empty uncertainty cells
  def test_csv_neutralises_formula_labels():            # label "=SUM(A1)" -> "'=SUM(A1)"; an id "+X" and the source id are guarded too
  ```
- [ ] **Step 2: Run them and watch them fail.** `PY -m pytest tests/test_propagation_view.py -q -p no:cacheprovider`.
- [ ] **Step 3: Implement `_propagation_view.py`.**
- [ ] **Step 4: Run the new tests and the unit suite.** Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "feat(propagation): view helpers — rows, uncertainty join, summaries, CSV, presets"`

### Task 6: Panel wiring

**Files:**
- Modify: `sespy_app/modules/analysis_intervention.py`:
  - UI around lines 174–216: the diffusion controls and outputs;
  - server around lines 317–485: `diffusion_isa`, the task, controls, reset/invalidate, run, observe, summary, chart.
- Replace: `tests/test_intervention_diffusion.py` → `tests/test_intervention_propagation.py`. Keep the removal and source tests (ported to the new ids); same fixture style.

**Interfaces:**
- **Consumes:**
  - From `_propagation_view`: `PRESETS`, `UNCERTAINTY_MAX_TOKENS`, `propagation_rows`, `join_uncertainty`, `summary_lines`, `uncertainty_lines`, `propagation_csv`, with signatures as in Task 5.
  - `dyn.signed_propagation` and `dyn.propagation_sensitivity`.
  - Translation keys from the header section **Translation keys**:
    - controls: `source`, `preset`, `preset_*`, `advanced`, `steps`, `decay`, `stop`, `transition*`, `run`, `unc_run`, `download`;
    - states: `hint`, `computing{n}`, `unc_computing{n}`, `none`, `error{error}`, `caption`;
    - table header: `col_element`, `col_reach`, `col_first`, `col_pos`, `col_neg`, `col_net`, `col_sign`, plus `col_reached` and `col_holds` once uncertainty is shown.
  - **This task builds the table header itself;** `propagation_rows` returns cell values only.
- **Produces:**
  - Inputs:
    - `prop_source` (select);
    - `prop_preset` (radio: `interactive` / `report` / `equal`);
    - `prop_steps` (slider 2–20, 8);
    - `prop_decay` (slider 0–1, step 0.05, 0.8);
    - `prop_stop` (slider 0–0.5, step 0.05, 0.15);
    - `prop_transition` (radio: `weighted` / `equal`);
    - `prop_run` and `prop_unc_run` (buttons).
  - Outputs: `prop_controls`, `prop_summary` (summary, table, uncertainty columns, captions), `prop_chart`, `prop_csv` (download, `filename="propagation.csv"`).
  - The old `diffusion_*`, `n_steps`, `n_tokens` and `run_diffusion` ids are gone. `diffusion_isa()` keeps its name and behaviour.

- [ ] **Step 1: Write the failing tests:**
  ```python
  def test_run_shows_computing_then_table(gated_propagation):
  def test_run_called_with_preset_values(monkeypatch):           # preset "report" -> n_tokens=10000, seed=0
  def test_run_uses_advanced_sliders(monkeypatch):                # preset "interactive", set prop_decay=0.5 (and prop_steps=12): Run -> decay=0.5, n_steps=12, n_tokens=1000
  def test_preset_sets_advanced_controls(monkeypatch):            # test server never applies ui.update_* (see tests/test_isa_entry_link_rules.py:4,40): monkeypatch mod.ui.update_slider / mod.ui.update_radio_buttons, choose "equal", assert recorded calls prop_decay=1.0, prop_stop=0.0, prop_transition="equal"
  def test_removed_source_shows_none_not_stuck(gated_propagation): # source removed by the ablation before Run: panel shows propagation.none, never stays on "Simulating…"
  def test_input_change_while_running_drops_stale_result(gated_propagation):
  def test_propagation_runs_without_removed_elements(gated_propagation):
  def test_changing_removal_clears_result_and_uncertainty(gated_propagation):
  def test_removed_element_not_offered_as_source():
  def test_source_without_out_links_shows_none_and_no_uncertainty_button():
  def test_uncertainty_button_only_after_run():
  def test_uncertainty_called_with_capped_tokens(monkeypatch):    # report preset -> propagation_sensitivity(n_tokens=1000, n_runs=200, base=0.5, seed=0, same walk settings)
  def test_stale_uncertainty_dropped_when_settings_change(gated_uncertainty):
  def test_task_error_shows_alert_not_crash(monkeypatch):         # propagation.error inside .alert-danger in #…-prop_summary
  def test_isa_change_clears_both():                              # needs the Harness / t_isa pattern of tests/test_paths_sensitivity_route.py:59-75 (emits the ISA event inside the session), not the diffusion fixture
  ```
- [ ] **Step 2: Run them and watch them fail.**
- [ ] **Step 3: Implement**, copying the existing diffusion pattern and the 1.2.0 robustness pattern:
  - plain-list generation cells, one per task;
  - inside each task, `if gen != _gen[0]: return (gen, None)` before `asyncio.to_thread`;
  - the observer drops stale generations;
  - `_COMPUTING` sentinel;
  - task exceptions are logged and render `propagation.error`.

  Idle state (no result) shows `propagation.hint`; the stale-drop and clear tests assert it.

  Removed source: do **not** copy the existing early return at `analysis_intervention.py:388-395`, which leaves the panel on "computing" for good. When the source is missing from `diffusion_isa()`, set the result to the empty shape, so the panel shows `propagation.none` and no uncertainty button.

  **Run parameters:**
  - `n_tokens = PRESETS[input.prop_preset()]["n_tokens"]`; there is no tokens control.
  - `n_steps`, `decay`, `stop_prob` and `transition` come from `prop_steps`, `prop_decay`, `prop_stop` and `prop_transition`, **never from `PRESETS`**, so Advanced edits take effect.
  - Uncertainty uses `min(n_tokens, UNCERTAINTY_MAX_TOKENS)` and the same slider values.

  Preset change: `ui.update_slider` and `ui.update_radio_buttons` on the advanced inputs.
  - Show "custom" with `propagation.preset_custom` when the sliders no longer match the chosen preset's values (builder's call where).
  - No new translation keys may be added in Part B.

  Chart (matplotlib, top 12 by reach):
  - stacked bars, `reach × positive_share` green `#2e7d32` and `reach × negative_share` red `#c62828`;
  - grey `#757575` for the full bar when shares are `None`;
  - y label "reach".

  Table Sign cell coloured with the same three colours (`+` green, `-` red, `~` grey), per spec.

  Captions: `propagation.caption` muted under the table.
- [ ] **Step 4: Run the new tests and the unit suite.** Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "feat(propagation): Intervention panel — signed propagation with presets, uncertainty in background, CSV"`

### Task 7: Benchmark, e2e, manual, screenshot, MosaicSES gate

**Files:**
- Create: `tests/test_propagation_perf.py`, marked `@pytest.mark.slow` (the app's `-m slow` marker).
  - Load `data/qsem-model-2026-01-12 (3).qsem` (121 elements, 386 links) with `qsem_to_isa`, wrapped in `IsaData`.
  - Source = the element with the most out-links (ties: first in order).
  - Source = N080 (25 out-links), found by that rule in round-1 review.
  - Warm up first (`from scipy import stats` plus one small call) so the cold import is not timed.
  - Measure with `time.perf_counter` and record the timings. Assert at the spec budgets **with margin for slow machines**: `signed_propagation` defaults < 2 s × 1.5, the report preset (`n_tokens=10000`) < 30 s × 1.5, `propagation_sensitivity` defaults < 30 s × 1.5. The laguna manual check in Task 9 holds the real budgets.
- Modify: `tests/test_intervention_e2e.py`.
  - Replace the diffusion block at lines 91–185 **wholesale**. It covers the hint, "7 of 17 elements reached", ± margins, the chart fingerprint, the P002 stale check and "of 16 elements"; none of those exist any more.
  - Keep an ablation check: remove P001, run, and assert P001's label is absent from the `prop_summary` table.
  - On the sample model:
  - pick D001 and click `#…-prop_run`;
  - wait up to 60 s for the `#…-prop_summary table tbody tr` rows, and assert the "Reach" and "Sign" headers;
  - click `#…-prop_unc_run` and wait up to 120 s for the "Reached in % of variants" header;
  - assert a visible `#…-prop_csv` and no `.alert-danger`.

  Scoped selectors only, no fixed sleeps for results. Use the module's real namespace prefix, read from the existing e2e.
- Modify: `docs/MANUAL.md`:
  - §40 becomes "Signed propagation": the walk, presets, reach, first step, shares and sign rule, mass line, uncertainty columns and what they mean, the 1,000-token cap, CSV.
  - Cite the development note and keep the Donlan et al. 2026 reference (line 534) for the equal-links preset.
  - In the Intervention section (§20), rewrite lines 332–340. Lines 332, 334 and 338 describe the "Steps"/"Tokens" sliders, "arrivals", 95% error bars, ranks and "±". Replace them with the new controls, the table and the uncertainty columns. Fix the stale caveat at line 340: the propagation now honours the ablation.
  - Update the §-index name.
- Modify: `tests/make_docs_screenshots.py:330-340`. The intervention shot waits on "elements reached"; wait for the `prop_summary` table instead.
  - Regenerate: start a server yourself with the shim PYTHONPATH, run the script with `--out <scratchpad dir>`, and copy only `intervention.png` into `docs/screenshots/`. There is no single-shot flag.

- [ ] **Step 1: Write the perf test, e2e changes and manual text.**
- [ ] **Step 2: Run the perf test.** `PY -m pytest tests/test_propagation_perf.py -m slow -q -s`. Expected: pass. The test prints its three timings; put them in the Step 5 commit message body as `Timings (DELL): default X s, report Y s, uncertainty Z s`.
- [ ] **Step 3: Run the full e2e detached** (`tests/run_e2e.py --port 8000`). Expected: all pass, apart from a runner-retried flake; the server line names `sespy-lib-v1210` 1.21.0.
- [ ] **Step 4: Run the MosaicSES gate** in `C:/Users/DELL/AppData/Local/MosaicSES`, at `d382147` on `main`. No fetch and no checkout.
  - Baseline first:
    - PYTHONPATH `<SHIM>;<MosaicSES>;C:/Users/DELL/AppData/Local/sespy-app-v120;C:/Users/DELL/AppData/Local/sespy-lib-v1200`, with `PYTHONDONTWRITEBYTECODE=1`;
    - `PY -m pytest tests/ -q -p no:cacheprovider`;
    - record DELL's baseline reds.
  - Then the branch: PYTHONPATH `<SHIM>;<MosaicSES>;<sespy-app-prop>;<sespy-lib-v1210>`.
  - Expected: no new reds against that baseline. Rerun any new red 3× alone.
- [ ] **Step 5: Commit.** `git commit -m "test(propagation): benchmark, e2e, manual and screenshot"`

### Task 8: App 1.3.0 release and hand-off

**Files:** `pyproject.toml` (1.3.0; pin `@v1.21.0`), `sespy_app/__init__.py`, the MANUAL version line, `CHANGELOG.md` (timings: `git log --grep "test(propagation): benchmark" -1 --format=%b`, the "Timings (DELL)" line), README pin text.

- [ ] **Step 1: Bump the version and re-pin.** Then run `tests/test_deploy_script.py` detached, with the Git-bash PATH prefix and the shim PYTHONPATH. Expected: pass.
- [ ] **Step 2: Release commit.** `git commit -am "release: 1.3.0 — signed propagation (sespy 1.21.0)"`. Then the unit suite: all pass.
- [ ] **Step 3: Whole-branch review** (the controller, most capable model) before the tag.
- [ ] **Step 4: User hand-off.** The agent writes `~/pr13.sh`, `~/tag13.sh` and `~/pr13-body.md`. The user pushes, opens the PR, waits for green CI, merges and tags `v1.3.0`. The agent verifies the tag target and an empty diff against the reviewed head.

---

## Part C — Deploy

### Task 9: Deploy 1.3.0 (agent runs with user go-ahead; agent verifies)

- [ ] **Step 0: Pre-checks.**
  - `git -C C:/Users/DELL/AppData/Local/sespy-app worktree add --detach C:/Users/DELL/AppData/Local/sespy-app-v130 v1.3.0`; it describes exactly `v1.3.0` and is clean.
  - `sespy-lib-v1210` describes exactly `v1.21.0` and is clean.
  - `sespy-app-v120` and `sespy-lib-v1200` are untouched and become the rollback pair.
  - `git check-ignore -v deploy/config.env` in the new tree names `.gitignore`.
- [ ] **Step 1: Config.**
  - Copy `sespy-app-v120/deploy/config.env` to `sespy-app-v130/deploy/config.env`, refusing to overwrite.
  - `sed` `DEPLOY_LIBRARY_ROOT=` to `C:/Users/DELL/AppData/Local/sespy-lib-v1210`.
  - Print only the per-key counts `grep -c '^KEY='` for `DEPLOY_SERVER`, `DEPLOY_DIR`, `DEPLOY_MOSAIC_DIR` and `DEPLOY_LIBRARY_ROOT`; each must be 1. Never print values.
- [ ] **Step 2: Deploy,** after the user's explicit go-ahead in the session.
  - Run `SESPY_PY=C:/Users/DELL/miniconda3/envs/mosaicses/python.exe bash C:/Users/DELL/AppData/Local/sespy-app-v130/deploy/deploy.sh`.
  - Expected: "Deploying SESPy app v1.3.0 with sespy library v1.21.0", `check_live: ok`, no `!!` lines, MosaicSES restarted.
  - If the swap dies, rerun `deploy.sh`; don't roll back.
- [ ] **Step 3: Live checks (read-only).**
  - ssh: `sespy_app/logs` lists `feedback.db`; the versions read 1.21.0 / 1.3.0; there are no `*.old` or `*.incoming` leftovers.
  - Playwright on `https://laguna.ku.lt/SESPy/`:
    - About shows `SESPy app 1.3.0 · sespy library 1.21.0`;
    - Intervention → propagation from D001 shows the table;
    - "Estimate uncertainty" adds both columns;
    - no `.alert-danger`.
  - MosaicSES: run `deploy/verify_live.py` from the clone, plus Compartments → Intervention renders without `Error:`.
  - **Spec P9 manual check on laguna**, from D001: time the Interactive run (budget ≤ 2 s), the Report run (≤ 30 s) and "Estimate uncertainty" (≤ 30 s), from click to rendered result.
    - Record all three in memory and the hand-off.
    - Over budget is reported to the user with the numbers. It is **not** a rollback trigger unless the panel fails to render.
- [ ] **Step 4: Rollback trigger.** On a non-cosmetic failure, run `SESPY_PY=C:/Users/DELL/miniconda3/envs/mosaicses/python.exe DEPLOY_REPO_ROOT=C:/Users/DELL/AppData/Local/sespy-app-v120 DEPLOY_LIBRARY_ROOT=C:/Users/DELL/AppData/Local/sespy-lib-v1200 bash C:/Users/DELL/AppData/Local/sespy-app-v120/deploy/deploy.sh --rollback`, with the user's go-ahead.
- [ ] **Step 5:** Update memory. Offer cleanup of the DELL-only worktrees: list them, never prune.

## Follow-up (not in this plan)

- No-revisit sensitivity run (note §3.2).
- Temporal delays in propagation, capacity, calibration (note v3).
- An app control for `base`.
- `compare_interventions` (roadmap P7b/P8).
- Edge evidence fields with SESPy#41.
