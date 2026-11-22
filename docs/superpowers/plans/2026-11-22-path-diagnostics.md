# Causal Path Diagnostics and Path Sensitivity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every causal path between two elements gets a transparent score, a weakest link, a delay profile and a minimum confidence. The result also reports the strongest positive and negative routes, contradiction and redundancy, plus a Monte-Carlo robustness check. All of it is shown in the Network Metrics panel, with a CSV export.

**Architecture:**
- **Library (sespy 1.20.0).**
  - `network.causal_paths` gains new keys only and sorts its rows by score.
  - A new `network.path_sensitivity` reuses `_perturbed_connections`.
  - All new UI strings go in `core.json`.
- **App (sespy-app 1.2.0).**
  - A pure helper module `_paths_view.py` builds the table rows and the CSV.
  - `analysis_metrics.py` renders them and runs the sensitivity check in an ExtendedTask, with the 1.1.0 generation-counter and stale-run guard.
- **Deploy.** Then the third split-layout deploy.

**Tech Stack:** Python 3.11+, networkx, numpy, Shiny for Python ≥ 1.7 (`@reactive.extended_task`, `@render.download`), pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-22-path-diagnostics-design.md` (approved 2026-11-22). Decisions 1–13 are binding. Probes are in `docs/superpowers/specs/path-diagnostics-probes/`.

## Global Constraints

- **Environment.**
  - Python only via `micromamba run -n shiny`. No venvs, no `pip install`, no new dependencies.
  - Single-line commands or `.py` files, never multi-line `python -c` or `python - <<EOF`.
- **Trees you must not touch.**
  - `AppData/Local/sespy-app` is the v1.0.1 rollback tree with the real `config.env`.
  - `AppData/Local/sespy-lib-v1180` is the rollback library; `sespy-app/config.env` points at it.
  - `AppData/Local/sespy-app-v110` is the live deploy tree with the real `config.env`. Read only; never run anything there.
  - `AppData/Local/sespy-lib-v1190` is the live library.
  - `AppData/Local/sespy-v1171` and `sespy-v1171-rb`.
  - Never read any `deploy/config.env`. No ssh.
- **User-only steps.** The user runs every push, PR merge, tag and deploy via short `!` one-liners. Use `~/` helper scripts when a line would wrap.
- **Weights:** `bayes.STRENGTH_LINK`, imported inside the function (`from .bayes import STRENGTH_LINK`). `bayes` imports `network` at module level, so a top-level import is a cycle. Never copy the values. Missing or unknown strength falls back to `"medium"`.
- **Score:** `PATH_SCORE_LAMBDA = 0.2` (public module constant in `sespy/network.py`).
  - `score = (w_weak**n_weak * w_medium**n_medium * w_strong**n_strong) * math.exp(-PATH_SCORE_LAMBDA * (L - 1))`, multiplied in exactly that order, with `L` = edge count.
  - Rows sort by `(-score, length, path)`.
- **Per-edge attributes:** the connection that wins polarity for a (source, target) pair (the last one in `isa.connections`) also supplies strength, confidence and delay.
- **Delay levels:** `constants.normalize_delay(c.delay)`. This is a spec erratum, see Task 1.
- **`causal_paths` compatibility.** The signature and the existing keys `path`, `length`, `polarity`, `counts` and `truncated` are unchanged; only the row order changes. The empty shape gains the new result-level keys.
- **`path_sensitivity` signature:** `path_sensitivity(isa, source, target, *, n_draws=500, seed=0, base=0.5, flip_mode="confidence", max_length=8, max_paths=100, draw_strength=False) -> dict`.
- **Translations:** all new keys go in the library `sespy/translations/core.json`, inside `"translation"`, with English text in all 9 languages (`en es fr de lt pt it no el`). Existing keys stay.
- **Versions.**
  - Library 1.20.0 (tag `v1.20.0`).
  - App 1.2.0 (tag `v1.2.0`), pinning `sespy[pdf,bayes] @ git+https://github.com/razinkele/SESPy@v1.20.0`.
  - If a 1.19.1 / 1.1.1 batch ships first, take the next minor number (spec decision 13) and ledger the change.
- **MosaicSES pins** `analysis_metrics_server(id, project_data, event_bus, translator=None)` (`tests/test_compartments_module.py:295`). That signature must not change.
- **Long runs** (full e2e, MosaicSES suite):
  - Launch detached with PowerShell `Start-Process` through `C:\Users\arturas.baziukas\micromamba\condabin\micromamba.bat run -n shiny …`, logging to a file.
  - Poll with bounded `Start-Sleep`.
  - Port 8000 must be free before and after. Never edit a tree while its suite runs.
- **Unit-test note:** `analysis_metrics` imports the pyvis fork at module load. Its unit tests use `pytest.importorskip("pyvis.shiny")`, so put testable logic in `_paths_view.py`, which imports no pyvis.

## Review Focus

1. **Bit-identical score ties.** Two paths with the same strength multiset in a different order must tie exactly and keep the length-then-path order. Pin it with a test that builds two such paths and asserts `score` equality with `==` and the order (Task 1).
2. **Truncated rankings shown as complete.** A truncated result must never present "strongest" as definitive. Pin it with a library test on `truncated` plus the strongest keys (Task 1), and an app helper test that the partial-ranking notice renders (Task 5).
3. **Duplicate connections.** Strength, confidence and delay must come from the polarity-winning connection. Pin it with a test with two connections on one pair that differ in every field (Task 1).
4. **Stale or overlapping sensitivity runs.** A changed pair or model, or repeated clicks, must not show an old result or queue full runs. Pin it with generation-drop and queued-click tests (Task 6).
5. **Missing or odd edge data.** Unknown strength, out-of-range confidence and free-text delay must give no NaN, no Infinity and no crash. Pin it with a library test using `strength="?"`, `confidence=9` and `delay="2 years"` (Task 1).

---

## Part A — Library (repo SESPy)

**Worktree:** `git -C "<OneDrive SESPy>" worktree add -b feat/path-diagnostics C:/Users/arturas.baziukas/AppData/Local/sespy-paths-lib origin/main`. Then `git cherry-pick 81004ad..docs/intervention-pathways` (every docs commit on that branch: both specs, the probes, this plan and its errata), so they ship with the code. Run with cwd and PYTHONPATH set to that worktree.

### Task 1: `causal_paths` diagnostics

**Files:**
- Modify: `sespy/network.py` (`causal_paths` at about lines 762–826; add `PATH_SCORE_LAMBDA` near it)
- Modify: `tests/test_network.py` (`_EMPTY_PATHS` at about line 1541, plus new tests after the causal_paths block)
- Create: `tests/_paths_fixtures.py` (the note's worked example)

**Interfaces:**
- **Produces, per row:** the existing keys plus
  - `score: float`;
  - `bottleneck_edge: {"source", "target", "strength", "confidence"}`;
  - `delay_profile: {"immediate": int, "short": int, "long": int}`;
  - `min_confidence: int`.
- **Produces, result level:** the existing keys plus
  - `strongest_positive: dict | None` and `strongest_negative: dict | None` (the row dict itself);
  - `contradictory: bool`;
  - `redundancy: {"edge_disjoint": int, "node_disjoint": int}`.
- **Empty shape:** `{"paths": [], "counts": {"+": 0, "-": 0, "0": 0}, "truncated": False, "strongest_positive": None, "strongest_negative": None, "contradictory": False, "redundancy": {"edge_disjoint": 0, "node_disjoint": 0}}`.

- [ ] **Step 1: Write the worked-example fixture.** In `tests/_paths_fixtures.py`, write `worked_example_isa() -> IsaData` from the note's §1.2–1.3 (comment: "Development note 2026-11-21, §1.2–1.3; synthetic values").
  - Nodes `I C D S N F W R A X`; element `type` can be any valid DAPSI(W)R(M) type, and labels are the note's names.
  - Edges (sign, strength after snapping w < 0.45 weak / < 0.70 medium / else strong, delay 1→immediate 2→short 3→long), all at confidence 3:
    - I→C + strong immediate;
    - C→D − strong immediate;
    - D→S − strong short;
    - S→N + strong short;
    - N→F + medium long;
    - S→W + medium short;
    - W→R + medium short;
    - S→R + medium long;
    - R→A + weak short;
    - A→C + medium immediate;
    - I→X + medium immediate;
    - X→S − weak short.
- [ ] **Step 2: Write the failing tests** in `tests/test_network.py`:
  ```python
  def test_causal_paths_worked_example_ranking():
      # I->F: exactly 2 rows; first I,C,D,S,N,F "+" score==pytest.approx(0.8**4*0.55*math.exp(-0.8));
      # second I,X,S,N,F "-" score==pytest.approx(0.55*0.30*0.80*0.55*math.exp(-0.6))
  def test_causal_paths_worked_example_bottleneck_and_delay():
      # first row: bottleneck N->F (medium, conf 3); delay_profile {"immediate":2,"short":2,"long":1}; min_confidence 3
  def test_causal_paths_worked_example_strongest_and_contradictory():
      # I->F: strongest_positive is row 0, strongest_negative is row 1, contradictory True
  def test_causal_paths_worked_example_redundancy():
      # I->R: 4 paths, score order I,C,D,S,R > I,C,D,S,W,R > I,X,S,R > I,X,S,W,R;
      # greedy edge_disjoint 2 (I,C,D,S,R and I,X,S,W,R share no link), node_disjoint 1 (all pass S)
  def test_causal_paths_score_ties_are_exact():
      # diamond s->a->t (strong, medium) and s->b->t (medium, strong): scores == exactly, order by path (a before b)
  def test_causal_paths_bottleneck_tie_breaks_on_confidence_then_position():
  def test_causal_paths_duplicate_connection_uses_polarity_winner_fields():
      # two s->t connections differing in polarity/strength/confidence/delay: row uses the LAST one's fields
  def test_causal_paths_odd_edge_data_is_finite():
      # strength "?", confidence 9, delay "2 years": score finite, uses medium; min_confidence 9 (stored);
      # delay counted as normalize_delay("2 years") == "short"
  def test_causal_paths_truncated_keeps_strongest_but_flags_it():
      # sample ES02->D001 max_paths=1: truncated True, strongest_negative is the one row
  def test_causal_paths_adjacent_pair_redundancy():
      # s->t direct + s->m->t: edge_disjoint 2, node_disjoint 2
  def test_path_score_lambda_constant():
      assert network.PATH_SCORE_LAMBDA == 0.2
  ```
  Update `_EMPTY_PATHS` to the new empty shape.
- [ ] **Step 3: Run them and watch them fail.** Run `micromamba run -n shiny python -m pytest tests/test_network.py -q -k causal_paths`. Expected: the new tests FAIL; the existing ones still pass apart from the `_EMPTY_PATHS` equality cases.
- [ ] **Step 4: Implement in `causal_paths`.**
  - Build `conn: dict[(s, t), Connection]` in the same loop as `pol` (last wins), and derive `pol` from it.
  - Compute the per-row fields from `conn[(a, b)]` along each path.
  - Sort by `(-score, length, path)`.
  - Compute the result-level keys:
    - strongest: first row with that polarity;
    - redundancy: greedy over the sorted rows. Edge-disjoint means no shared `(a, b)`; node-disjoint means no shared interior node.
  - Update the docstring.
- [ ] **Step 5: Run the library suite.** Run `micromamba run -n shiny python -m pytest -q`. Expected: all pass.
  - If tests in `tests/test_bayes*.py` assert path order through `bayes` (which passes `causal_paths` rows through), update only their expected order to score order, and say so in the report.
- [ ] **Step 6: Commit.** `git commit -m "feat(paths): score, weakest link, delay profile, strongest routes and redundancy in causal_paths"`

### Task 2: `path_sensitivity`

**Files:**
- Modify: `sespy/network.py` (new function after `causal_paths`)
- Create: `tests/test_path_sensitivity.py`

**Interfaces:**
- **Consumes:** `causal_paths` (Task 1); `_perturbed_connections(isa, base, rng, flip_mode)` (existing).
- **Produces:**
  ```
  {"n_draws": int, "seed": int, "base": float, "flip_mode": str,
   "paths": [{"path", "polarity", "score", "rank_probability", "polarity_probability", "survival_probability"}],
   "fragile_edges": [{"source", "target", "share"}],
   "truncated": bool}
  ```
  The paths are the baseline rows, in baseline order. `fragile_edges` holds at most 5 edges, sorted by `-share`, then `(source, target)`.

- [ ] **Step 1: Write the failing tests:**
  ```python
  def test_seed_reproducible():            # same args twice -> identical dicts
  def test_base_zero_is_deterministic():   # base=0: every probability is 0.0 or 1.0; top path rank_probability 1.0
  def test_only_path_dropped_gives_zero_rank():  # chain s->m->t with confidence 1 on s->m, base=1.0 (p_drop 1): rank_probability 0.0, survival 0.0
  def test_rank_probability_is_within_same_sign():  # worked example I->F: both rows can have rank_probability > 0 (one per sign)
  def test_fragile_edges_bounded_and_sorted():
  def test_off_path_edge_never_fragile():  # worked example I->F plus an extra confidence-1 edge W->A (on no I->F path): never in fragile_edges
  def test_flipped_path_does_not_count_towards_rank():  # base=1.0 flip on a 1-path chain: polarity_probability < survival, rank counts only same-sign draws
  def test_no_route_returns_empty_shape():  # paths [], fragile_edges [], truncated False
  def test_draw_strength_uses_ratings_only_when_rated():
  def test_clamps():                        # n_draws clamped to [1, 10000]; base to [0, 1]; flip_mode validated like uncertainty_scores
  ```
- [ ] **Step 2: Run and watch them fail.** Run `micromamba run -n shiny python -m pytest tests/test_path_sensitivity.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Use `rng = np.random.default_rng(seed)`.
  - For each draw:
    - perturbed connections (with `draw_strength`, a rated edge takes `rng.choice(c.ratings).strength`);
    - `causal_paths` on `IsaData(elements=isa.elements, connections=perturbed)` with the same `max_length` / `max_paths`;
    - map the surviving rows by `tuple(path)`.
  - Per baseline path, follow spec decision 10 exactly:
    - survival: present in the draw;
    - polarity: present with the baseline polarity;
    - rank: present with the baseline polarity **and** the top-scoring row of that polarity in the draw.
  - Detect drops and flips by comparing each baseline-path edge's `(source, target)` against the draw's connections, last wins as in Task 1:
    - absent → dropped;
    - polarity differs from the baseline winner → flipped.
  - Fragile edges, as defined in decision 10: count only edges on listed baseline paths, in draws where the top row changed in path or polarity, or where the draw has no rows. Share = count / n_draws.
- [ ] **Step 4: Run the tests and the library suite.** Expected: all pass. Record the time for `path_sensitivity` on Caribbean W2→W6 at `n_draws=500` in the report (the spec's probe was about 3.5 s).
- [ ] **Step 5: Commit.** `git commit -m "feat(paths): path_sensitivity — rank, polarity and survival probabilities and fragile edges"`

### Task 3: Translations, public API, release 1.20.0

**Files:**
- Modify: `sespy/translations/core.json`, `tests/test_public_api.py`, `sespy/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `README.md` (pin line)
- Create: `tests/test_translations_paths.py` (modelled on `tests/test_translations_boolean_scale.py`)

- [ ] **Step 1: Write the key test.** Use these keys, with this exact English text and these placeholder sets:

  | Key | English | Placeholders |
  |---|---|---|
  | `metrics.paths_col_route` | "Route" | – |
  | `metrics.paths_col_score` | "Score" | – |
  | `metrics.paths_col_length` | "Links" | – |
  | `metrics.paths_col_polarity` | "Sign" | – |
  | `metrics.paths_col_bottleneck` | "Weakest link" | – |
  | `metrics.paths_col_delay` | "Delays" | – |
  | `metrics.paths_col_confidence` | "Min. confidence" | – |
  | `metrics.paths_delay_fmt` | "{immediate} immediate, {short} short, {long} long" | immediate, short, long |
  | `metrics.paths_score_note` | "Score = product of link weights (weak 0.30, medium 0.55, strong 0.80) × e^(−0.2 × (links − 1)). It ranks structural routes; it is not an effect size." | – |
  | `metrics.paths_strongest` | "Strongest positive route: {pos}. Strongest negative route: {neg}." | pos, neg |
  | `metrics.paths_none_sign` | "none" | – |
  | `metrics.paths_contradictory` | "Positive and negative routes both connect these elements; the net effect depends on which dominates." | – |
  | `metrics.paths_redundancy` | "Disjoint routes among the paths listed: {edge} sharing no link, {node} sharing no intermediate element." | edge, node |
  | `metrics.paths_ranked_partial` | "Ranked among the first {n} paths found; a stronger path may exist beyond them." | n |
  | `metrics.paths_download` | "Download paths (CSV)" | – |
  | `metrics.paths_sens_run` | "Test robustness" | – |
  | `metrics.paths_sens_computing` | "Running {n} perturbed versions of the network…" | n |
  | `metrics.paths_sens_caption` | "{n} perturbed versions (seed {seed}): each link may drop out or flip sign, more often the lower its confidence." | n, seed |
  | `metrics.paths_sens_col_rank` | "Top route of its sign (%)" | – |
  | `metrics.paths_sens_col_polarity` | "Keeps its sign (%)" | – |
  | `metrics.paths_sens_col_survival` | "Survives (%)" | – |
  | `metrics.paths_sens_fragile` | "Links whose uncertainty most often changes the top route: {edges}" | edges |
  | `metrics.paths_sens_error` | "The robustness check failed: {error}" | error |

  Assert all 9 languages and the placeholder sets. Keep `metrics.paths_truncated`.
- [ ] **Step 2: Run it and watch it fail, then add the keys.** Add all keys to `core.json`, with English text in every language and the same formatting as the neighbouring entries.
- [ ] **Step 3: Public API and release.**
  - Add `"path_sensitivity"` and `"PATH_SCORE_LAMBDA"` to the network list in `tests/test_public_api.py`.
  - Version 1.20.0 in `pyproject.toml` and `sespy/__init__.py`.
  - CHANGELOG 1.20.0. It must note the row-order change and the larger empty shape for `causal_paths` callers.
  - README pin `@v1.20.0`.
- [ ] **Step 4: Run the full library suite.** Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "release: sespy 1.20.0 — causal path diagnostics and path sensitivity"`

### Task 4: Library hand-off (user)

- The controller runs the whole-branch review (most capable model) before the hand-off.
- The user pushes, opens the PR and waits for CI (lint red only in files this branch did not touch), merges, and tags `v1.20.0` on the merge commit. The agent writes `~/pr120.sh`, `~/tag120.sh` and `~/pr120-body.md`, with a null-safe merge-commit guard as in `~/tag119.sh`.
- The agent verifies that `git ls-remote origin "refs/tags/v1.20.0^{}"` equals the merge commit and that `git diff --stat <reviewed head> v1.20.0` is empty.

---

## Part B — App (repo sespy-app)

**Worktrees:**
- App: `git -C C:/Users/arturas.baziukas/AppData/Local/sespy-app worktree add -b feat/path-diagnostics C:/Users/arturas.baziukas/AppData/Local/sespy-app-paths origin/main`.
- Library: `git -C "<OneDrive SESPy>" worktree add --detach C:/Users/arturas.baziukas/AppData/Local/sespy-lib-v1200 v1.20.0`.
  - Before the tag exists, use the reviewed library head and move the worktree to the tag afterwards; `deploy.sh` requires the exact tag.
  - Ledger that ruling if used.
- PYTHONPATH is `<sespy-app-paths>;<sespy-lib-v1200>`, with cwd = the app worktree.

### Task 5: Paths table, summary lines and CSV export

**Files:**
- Create: `sespy_app/modules/_paths_view.py`
- Modify: `sespy_app/modules/analysis_metrics.py` (`paths_summary` at about lines 470–535, `_compute_paths` at about line 465)
- Create: `tests/test_paths_view.py`

**Interfaces:**
- **Consumes:** the Task 1 result keys and the Task 3 translation keys.
- **Produces:**
  - `path_rows(result: dict, labels: dict[str, str]) -> list[dict]`, one dict per path with the keys `route`, `score`, `links`, `sign`, `weakest`, `delays`, `min_confidence`:
    - `score` formatted `f"{score:.3f}"`;
    - `weakest` is `"label A → label B (strength, conf N)"`;
    - `delays` comes from `metrics.paths_delay_fmt`.
  - `paths_csv(result: dict, labels: dict[str, str]) -> str`: written with the `csv` module, with a header row plus one row per path and raw values. The header is exactly `rank,path_ids,path_labels,polarity,length,score,bottleneck_source,bottleneck_target,bottleneck_strength,bottleneck_confidence,delay_immediate,delay_short,delay_long,min_confidence,truncated`.
    - `path_ids` and `path_labels` are `" > "`-joined.
    - The score is unrounded (`repr` of the float).
    - `truncated` repeats the result flag on every row.
    - The column names stay English; they are machine-readable.
  - `summary_lines(result: dict, labels) -> list[str]`, in this order:
    1. the existing `metrics.paths_summary`;
    2. `metrics.paths_strongest`;
    3. `metrics.paths_contradictory`, only if contradictory;
    4. `metrics.paths_redundancy`;
    5. `metrics.paths_ranked_partial`, only if truncated.

- [ ] **Step 1: Write the failing tests** with a hand-built result dict (no Shiny, no pyvis):
  ```python
  def test_path_rows_columns_and_formatting():
  def test_summary_lines_order_and_conditionals():   # contradictory/partial lines appear only when flagged
  def test_strongest_none_renders_none_word():
  def test_paths_csv_matches_rows():                 # same count; score column unrounded; header names fixed
  def test_partial_ranking_line_when_truncated():
  ```
- [ ] **Step 2: Run them and watch them fail.** Run `micromamba run -n shiny python -m pytest tests/test_paths_view.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement `_paths_view.py`, then wire the panel.**
  - The table headers use the `metrics.paths_col_*` keys.
  - The summary paragraph shows `summary_lines`, then `metrics.paths_score_note` in small muted text.
  - The table keeps its `table table-sm` class, and the panel keeps the `#metrics-paths_summary` id.
  - Add `ui.download_button("paths_csv", t("metrics.paths_download"))` under the table, with a `@render.download(filename="causal_paths.csv")` that yields `paths_csv(...)` from `_paths_result`.
  - Drop the old `metrics.paths_truncated` line from the render, since `metrics.paths_ranked_partial` replaces it; the key stays in the library.
- [ ] **Step 4: Run the app unit suite** (README selection). Expected: all pass (the 1.1.0 baseline is 551 passed / 2 skipped).
- [ ] **Step 5: Commit.** `git commit -m "feat(paths): score, weakest link, delays and route summary in Causal pathways; CSV export"`

### Task 6: Robustness check in a background task

**Files:**
- Modify: `sespy_app/modules/analysis_metrics.py`
- Modify: `sespy_app/modules/_paths_view.py` (adds `sensitivity_rows(sens, labels) -> list[dict]` and `fragile_text(sens, labels) -> str`)
- Create: `tests/test_paths_sensitivity_route.py` (modelled on `tests/test_analysis_boolean_route.py`, with `pytest.importorskip("pyvis.shiny")` at the top)

**Interfaces:**
- **Consumes:** `network.path_sensitivity` (Task 2), called with the defaults only. No client-settable arguments: `n_draws=500`, `seed=0`, `base=0.5`, `flip_mode="confidence"`.
- **Produces:** a `#metrics-paths_sens_run` action button, shown only when a traced result has at least 1 path, and the output `#metrics-paths_sensitivity`.

- [ ] **Step 1: Write the failing tests:**
  ```python
  def test_sensitivity_called_with_fixed_defaults(monkeypatch):
  def test_sensitivity_shows_computing_then_table():
  def test_stale_result_dropped_when_pair_changes():      # trace A->B, run, re-trace C->D before it finishes: no A->B table
  def test_queued_clicks_run_at_most_two_searches():       # 3 clicks behind a gate -> spy called twice
  def test_sensitivity_uses_traced_pair_not_current_selects(monkeypatch):  # trace A->B, change selects to C->D without re-tracing, click: spy gets A, B
  def test_sensitivity_error_shows_alert_not_crash(monkeypatch):   # alert text from metrics.paths_sens_error
  def test_isa_change_clears_sensitivity():
  def test_sensitivity_rows_percentages():                 # helper: shares -> "%.0f"
  ```
- [ ] **Step 2: Run them and watch them fail.**
- [ ] **Step 3: Implement**, copying the 1.1.0 pattern from `analysis_boolean.py`:
  - a plain-list generation cell;
  - inside the task, `if gen != _gen[0]: return (gen, None)` before `asyncio.to_thread`;
  - task exceptions returned with their generation;
  - `_COMPUTING` sentinel; the observer drops stale generations;
  - a new trace or an ISA change bumps the generation and clears the result;
  - `_compute_paths` stores the traced pair with the result (`{"source", "target", "result"}`, or a separate `reactive.value`), and the robustness run always uses that stored pair, never the current selects;
  - a task error renders `metrics.paths_sens_error` in a `.alert-danger` inside `#metrics-paths_sensitivity`.
  
  Render `metrics.paths_sens_caption`, a table (route, the three `%` columns) and `metrics.paths_sens_fragile`.
- [ ] **Step 4: Run the new tests and the app unit suite.** Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "feat(paths): robustness check in a background task with stale-run guard"`

### Task 7: e2e, manual, screenshot, MosaicSES gate

**Files:**
- Modify: `tests/test_metrics_e2e.py`. On the sample ES02→D001 pair, keep the existing count and label assertions and add:
  - the `Score` and `Weakest link` headers inside `#metrics-paths_summary table thead`;
  - the "Strongest negative route:" text in `#metrics-paths_summary`;
  - a visible `#metrics-paths_csv` download button;
  - click `#metrics-paths_sens_run`, wait up to 120 s for `#metrics-paths_sensitivity table tbody tr`, and assert ≥ 1 row and no `.alert-danger` in `#metrics-paths_sensitivity`.
  
  All selectors are scoped; there are no bare `text=` selectors and no fixed sleeps for results.
- Modify: `docs/MANUAL.md`, the Network Metrics section on causal pathways:
  - the score formula and its caveat;
  - the weakest link, delays and minimum confidence;
  - strongest routes, contradiction, redundancy and the partial-ranking notice;
  - the robustness check (what is perturbed, 500 draws, seed 0);
  - CSV export.
- Modify: `tests/make_docs_screenshots.py` only if the metrics shot must show the paths block; regenerate only the affected PNG.

- [ ] **Step 1: Write the e2e changes and the manual text.**
- [ ] **Step 2: Run the full e2e detached** (`tests/run_e2e.py --port 8000`). Expected: all pass, apart from a runner-retried flake. The server line names `sespy-lib-v1200` 1.20.0.
- [ ] **Step 3: Run the MosaicSES gate** from `AppData/Local/mosaicses-split-gate`, after `git fetch origin main` and `git checkout --detach FETCH_HEAD`, with PYTHONPATH `<gate>;<sespy-app-paths>;<sespy-lib-v1200>`.
  - Expected: reds only from the baseline set: topbar modal race, equity editor, beforeunload, composite timer, file flows, heatmap_card, risk knot, comparative-header load flake, and the aria-live cold-nav timeout.
  - Rerun any other red 3× alone.
- [ ] **Step 4: Commit.** `git commit -m "test(paths): e2e for diagnostics, CSV and robustness; manual"`

### Task 8: App 1.2.0 release and hand-off

**Files:** `pyproject.toml` (1.2.0; pin `@v1.20.0`), `sespy_app/__init__.py`, the MANUAL version line, `CHANGELOG.md`, README pin text.

- [ ] **Step 1: Bump the version and re-pin.** Then run `tests/test_deploy_script.py` (detached; about 15 min). Expected: pass.
- [ ] **Step 2: Release commit.** `git commit -am "release: 1.2.0 — causal path diagnostics (sespy 1.20.0)"`. Then run the app unit suite: all pass.
- [ ] **Step 3: Whole-branch review** (the controller, most capable model) before the tag.
- [ ] **Step 4: User hand-off.** The agent writes `~/pr12.sh`, `~/tag12.sh` and `~/pr12-body.md`. The user pushes, opens the PR, waits for green CI, merges and tags `v1.2.0`. The agent verifies the tag target and an empty diff against the reviewed head.

---

## Part C — Deploy

### Task 9: Third split-layout deploy (user runs; agent verifies)

- [ ] **Step 0: Pre-checks (agent).**
  - `git -C …/sespy-app worktree add --detach …/sespy-app-v120 v1.2.0`, describing exactly `v1.2.0` and clean.
  - `sespy-lib-v1200` describes exactly `v1.20.0` and is clean.
  - `sespy-app-v110` and `sespy-lib-v1190` are untouched; they become the rollback pair.
  - `check-ignore -v deploy/config.env` in the new tree names `.gitignore`.
  - Live MosaicSES `verify_live.py` passes (run from the config-less gate tree).
- [ ] **Step 1: Config hand-off.** The agent writes `~/cfg120.sh`. It copies `sespy-app-v110/deploy/config.env` to `sespy-app-v120/deploy/config.env`, refusing to overwrite. Then it `sed`s `DEPLOY_LIBRARY_ROOT=` to `…/sespy-lib-v1200` and prints both grep counts, each of which must be 1. The agent never reads the file.
- [ ] **Step 2: Deploy (user).** Run `bash …/sespy-app-v120/deploy/deploy.sh`. Expected:
  - "Deploying SESPy app v1.2.0 with sespy library v1.20.0";
  - check_live ok, no `!!` lines;
  - MosaicSES restarted.
  
  If the swap dies, rerun `deploy.sh`; don't roll back.
- [ ] **Step 3: Live checks (agent, read-only).**
  - Playwright on `https://laguna.ku.lt/SESPy/`:
    - About shows `SESPy app 1.2.0 · sespy library 1.20.0`;
    - the sample's Network Metrics shows the scored table, the strongest-route line and a robustness table;
    - no `.alert-danger`.
  - MosaicSES: `verify_live.py`, plus Compartments → Network Metrics renders without `Error:`.
  - The user runs `ssh razinka@laguna.ku.lt ls /srv/shiny-server/SESPy/sespy_app/logs`, which must list `feedback.db`.
- [ ] **Step 4: Rollback trigger.** On a non-cosmetic failure, the user runs `bash …/sespy-app-v110/deploy/deploy.sh --rollback`. That tree's config points at `sespy-lib-v1190`.
- [ ] **Step 5:** Update memory and offer worktree cleanup.

## Follow-up (not in this plan)
- Weighted signed propagation (`2026-11-22-weighted-propagation-design.md`); its decision 1 is now settled.
- Edge evidence fields with SESPy#41.
- `compare_interventions` (roadmap P7b/P8).
