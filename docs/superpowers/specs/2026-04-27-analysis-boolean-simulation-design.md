# Analysis: Boolean & Simulation Modules — Design

Date: 2026-04-27
Status: **Implemented** · shipped on `feat/analysis-boolean-simulation` (tip `a55583b`), fast-forwarded to `main` 2026-04-28. Final delivery overran the spec's LOC and test-count estimates modestly (e.g. `test_dynamics.py` ended at 33 tests vs the "about 25" estimated below); estimates were not updated post-merge so the file reads as a pre-implementation snapshot. The module-signature contract changed in commit `af051c1` (2026-04-30) — `project_data` is now `reactive.Value[Project]` rather than `reactive.Value[IsaData]`; module callsites read `project_data.get().isa_data`. **Spec-vs-ship naming deltas** (intentionally not back-edited into the body — the spec is a frozen pre-implementation snapshot): the spec writes `event_bus.on_isa_change` throughout but the shipped name is `event_bus.isa_change` (a `reactive.Value[int]`); subscriber effects read it via `event_bus.isa_change.get()` inside `with reactive.isolate():`. The spec's i18n key namespaces (`modules.analysis_boolean.*`, `modules.analysis_simulation.*`, `modules.analysis.common.data_changed_rerun`) shipped as flat `boolean.*`, `simulation.*`, and `analysis.common.data_changed_rerun` (no `modules.` prefix). The §4 diagram label `@reactive.calc` for the result store is stale — the shipped result store is a `reactive.Value[dict | None]` written by a `@reactive.event` effect, not a `@reactive.calc`. **Post-implementation note**: i18n keys added to `core.json` MUST go inside the top-level `"translation"` wrapper object — `Translator._load_one` reads `raw.get("translation", {})`, so keys at the file root are silently invisible. This trap was discovered during PIMS implementation (after Boolean+Simulation had shipped); these modules' keys were correctly nested.
Source modules in R app:
- `../SESToolbox/MarineSABRES_SES_Shiny/modules/analysis_boolean.R` (629 LOC)
- `../SESToolbox/MarineSABRES_SES_Shiny/modules/analysis_simulation.R` (626 LOC)
- `../SESToolbox/MarineSABRES_SES_Shiny/functions/ses_dynamics.R` (1436 LOC; subset ported)

## 1. Scope

Port two analysis modules from the R MarineSABRES SES Toolbox to the Shiny-for-Python SESPy port. Bundled because they share a numerics substrate (`ses_dynamics.R`).

**In scope (core + headline features):**
- Boolean: Laplacian eigenvalue analysis + Boolean network attractor analysis (both tabs from R).
- Simulation: deterministic linear-matrix time-series simulation + Monte Carlo state-shift analysis.

**Deferred to follow-up specs:**
- Participation ratio panel (simulation module).
- PCA phase-space trajectory visualization (simulation module).
- BOT (Behaviour Over Time) module — independent, gets its own spec.

## 2. Architecture

### New files

- `sespy/dynamics.py` — pure-Python numerics layer (numpy + standard library, no Shiny imports). Mirrors the role of `sespy/network.py`.
- `sespy/modules/analysis_boolean.py` — UI + server for Boolean / Laplacian module.
- `sespy/modules/analysis_simulation.py` — UI + server for Simulation / Monte Carlo module.
- `tests/test_dynamics.py` — unit tests for the numerics layer.
- `tests/test_boolean_e2e.py` — Playwright e2e for the Boolean module.
- `tests/test_simulation_e2e.py` — Playwright e2e for the Simulation module.

### Wire-up changes

- `sespy/dashboard.py` — add two nav buttons + two stepper entries, ordered between "Leverage Points" and "Intervention" to match the R workflow.
- `sespy/translations/core.json` — add `modules.analysis_boolean.*` and `modules.analysis_simulation.*` namespaces. Also verify `modules.analysis.common.data_changed_rerun` is present (used by both modules' stale-data notification — port from R if missing). English keys first; the other 8 languages (es, fr, de, lt, pt, it, no, el) get the same keys with English placeholder values, mirroring the established pattern when adding a new module.
- `app.py` — register both modules with `project_data` and `event_bus`.

### Dependencies

No new packages. `numpy` is already pulled transitively by pandas and networkx; `numpy.linalg.eig` is sufficient for the dense, sub-100-node matrices typical of SES networks. `matplotlib` is already pulled by Shiny for `@render.plot`. No scipy and no plotly — both are alternatives discussed and rejected on cost/benefit grounds (scipy: ~80 MB binaries for routines that don't outperform numpy at this scale; plotly: 5 MB JS bundle for interactive plots that aren't required).

## 3. Components

### `sespy/dynamics.py` (~400 LOC)

Public functions, each a port of a named function in `ses_dynamics.R`. All functions are pure (no side effects, no Shiny imports). Every stochastic function takes a `seed` parameter for reproducible tests. Result dicts are declared as `TypedDict` at the top of the file so that consumers (the module files) get IDE/type-check support on key access.

| Python | R source | Purpose |
|---|---|---|
| `isa_to_numeric_matrix(isa: IsaData) -> tuple[np.ndarray, list[str]]` | `isa_to_numeric_matrix` (ses_dynamics.R:215) | Build signed weighted adjacency: `M[i,j] = polarity * strength` for edge i→j. Returns matrix and ordered node-id list. |
| `laplacian_eigenvalues(mat, direction="cols") -> np.ndarray` | `laplacian_eigenvalues` (:322) | Compute Laplacian L = D − A and return eigenvalues sorted by real part. |
| `laplacian_stability(mat, direction="cols") -> dict` | `laplacian_stability` (:381) | Returns `{eigenvalues, dominant, spectral_radius, algebraic_connectivity, stability_class}`. |
| `create_boolean_rules(mat) -> list[dict]` | `ses_create_boolean_rules` (:455) | One rule per node: `{node_id, activators, inhibitors, threshold}`. |
| `boolean_attractors(rules, max_nodes=12) -> dict` | `ses_boolean_attractors` (:527) | Exhaustive 2^N state-space search, capped by `max_nodes`. Returns `{attractors: [{type: "fixed"\|"cyclic", states, period, basin_size}], total_states, error?}`. |
| `simulate_dynamics(mat, n_iter=200, initial_state="zeros", seed=None) -> np.ndarray` | `simulate_dynamics` (:680) | Linear iteration `x_{t+1} = M @ x_t`. `initial_state` accepts a preset string (`"zeros"`, `"random"`, `"uniform"`) or an explicit `np.ndarray` of shape `(n_nodes,)`. `seed` only affects `"random"`. Returns array of shape `(n_iter+1, n_nodes)`. |
| `randomize_matrix(mat, kind="uniform", rng=None) -> np.ndarray` | `ses_randomize_matrix` (:845) | Perturb non-zero entries; `kind ∈ {"uniform", "sign_flip", "gaussian"}`. Takes an `rng` (numpy `Generator`) rather than a seed because callers (notably `state_shift_monte_carlo`) invoke this in a loop and need a single RNG to advance state across calls — reseeding from the same seed every call would produce identical perturbations across simulations. |
| `state_shift_monte_carlo(mat, n_simulations=100, n_iter=200, kind="uniform", seed=None) -> dict` | `state_shift_monte_carlo` (:896) | Runs N simulations on perturbed matrices. Internally builds `rng = np.random.default_rng(seed)` and passes it to every `randomize_matrix` call. Returns `{final_states: ndarray (n_succeeded, n_nodes), summary: dict per node with mean/sd/p5/p95, n_simulations: int, n_failed: int}` — the array contains only finite-valued runs; failures are counted in `n_failed`. |

NaN/Inf handling: Monte Carlo checks each simulation's final state with `np.isfinite(...).all()`; failures are dropped from aggregates and counted in `n_failed`, never raised as exceptions.

### `sespy/modules/analysis_boolean.py` (~250 LOC)

UI:
- `module_ui(id)` — header (reactive title/subtitle), CLD validation gate, main UI behind `@render.ui`.
- Controls (left card): Laplacian direction radio (rows / cols, default `cols` to match function signature), `max_nodes` slider (4–12, default 12), Run button.
- Results (right tabset):
  - **Laplacian** tab: eigenvalue spectrum bar chart (`@render.plot`), stability summary text (`@render.ui`).
  - **Boolean** tab: attractor table (`@render.data_frame` — columns: type, period, basin_size, representative state). The `representative state` column is derived in the module: for fixed attractors, it's the (only) state formatted as a binary string keyed to node ids; for cyclic attractors, it's the first state in `attractors[i].states` with a `+ N more` suffix when `period > 1`. The function output (`states`) carries the full state list for each attractor; the table is a presentation layer over it.

Server:
- `numeric_matrix = reactive.calc(...)` derived from `project_data` plus the ordered node-id list.
- `result = reactive.event(input.run_boolean, ignore_init=True)` runs `laplacian_stability`, `create_boolean_rules`, and `boolean_attractors`.
- `event_bus.on_isa_change` subscriber posts a stale-data notification when `result is not None`.

### `sespy/modules/analysis_simulation.py` (~300 LOC)

UI:
- Header + CLD validation gate.
- Controls (left card, two subsections):
  - **Simulation**: `n_iter` slider (50–2000, default 200), `initial_state` radio (zeros / random / uniform-1.0), seed numeric input, Run Simulation button.
  - **Monte Carlo**: `n_simulations` slider (10–500, default 100), perturbation `kind` radio (uniform / sign_flip / gaussian), seed numeric input, Run Monte Carlo button.
- Results (right tabset):
  - **Trajectories**: multi-line matplotlib plot (one line per node, viridis colormap, legend on side).
  - **Final State**: bar chart of final values per node.
  - **Monte Carlo**: per-node small-multiples histogram + summary table (mean, sd, p5, p95, n_failed).

Server:
- Two independent `reactive.event` blocks for the two Run buttons, two stored result reactives.
- Same stale-data warning pattern.

## 4. Data flow

### Freshness, not recomputation

ISA edits do not auto-recompute results. Both modules subscribe to `event_bus.on_isa_change` and, when a result is currently stored, post a notification *"Data changed — re-run analysis to update results"*. Auto-recomputing on every edit is wrong here because Monte Carlo can take seconds; the user must opt in by clicking Run. This mirrors the R modules' `observe({ event_bus$on_isa_change(); ... })` pattern at `analysis_boolean.R:53` and `analysis_simulation.R:50`.

### Compute pipeline (per Run click)

```
project_data() reactive ──►  isa_to_numeric_matrix(isa)  ──►  (M, node_ids)
                                                                   │
                                                                   ▼
   ┌──────────────── Boolean ───────────────┐    ┌───── Simulation ─────┐
   │   laplacian_stability(M, direction)    │    │  simulate_dynamics(M,│
   │   create_boolean_rules(M)              │    │      n_iter, x0)     │
   │   boolean_attractors(rules, max_nodes) │    │                      │
   │     ▼                                  │    │  state_shift_monte_  │
   │   stored in @reactive.calc             │    │      carlo(M, n_sim, │
   │     (laplacian_result, boolean_result) │    │      n_iter, kind,   │
   └────────────────────────────────────────┘    │      seed)           │
                                                  │     ▼                │
                                                  │  stored in two       │
                                                  │  separate            │
                                                  │  @reactive.calc      │
                                                  │  (sim_result,        │
                                                  │   mc_result)         │
                                                  └──────────────────────┘
                              ▼
                  Outputs read result reactives:
                  - @render.plot (eigenvalue bars,
                    trajectories, MC histograms)
                  - @render.data_frame (attractor table,
                    MC summary table)
                  - @render.ui (stability text)


Independent freshness channel (does NOT trigger recompute):

   event_bus.on_isa_change ──►  observer checks "is a result currently stored?"
                                       │
                                       ▼ (yes)
                                show stale-data notification only
```

### Action button reactivity

All three Run buttons (one in Boolean, two in Simulation: Run Simulation + Run Monte Carlo) use `@reactive.event(input.run_*, ignore_init=True)`, the canonical pattern from `analysis_intervention.py`. Without `ignore_init=True`, action buttons fire once at session init because they start at 0, not None.

### Persistence boundary

Results are not persisted to the project file. They are transient session state — re-deriving them from saved ISA data is fast enough and they are parameterized by sliders the user is actively tuning. This matches every other analysis module and keeps the project JSON schema unchanged.

## 5. Error handling

Five error surfaces. Each gets a specific UI response, never a stack trace.

### No CLD data yet

- **Where:** before any user input — module just opened.
- **Detection:** existing `cld_validation` helper used by every analysis module.
- **Response:** main UI hidden; a card with an info icon and a localized message *"Add elements and connections in Edit Data before running this analysis"* (i18n keys `modules.analysis_boolean.no_cld_data` / `modules.analysis_simulation.no_cld_data`).

### Matrix construction fails

- **Where:** `isa_to_numeric_matrix` called inside the Run reactive.
- **Detection:** `isa_to_numeric_matrix` raises `ValueError` with a specific message (orphan node, dangling edge, malformed strength).
- **Response:** Run reactive catches `ValueError` and stores `{error: msg, result: None}` in the result reactive. The Results tabset shows a single error alert *"Could not build matrix: {msg}"*.

### Boolean attractor search exceeds `max_nodes`

- **Where:** Boolean run on a network larger than the cap.
- **Detection:** `boolean_attractors` returns `{attractors: [], error: "too_large", n_nodes, max_nodes}` (no exception).
- **Response:** Boolean tab shows alert with branched guidance:
  - If `n_nodes <= 12`: *"Network has {n_nodes} nodes. Raise the cap slider to at least {n_nodes} and re-run."*
  - If `n_nodes > 12`: *"Network has {n_nodes} nodes. Exhaustive Boolean attractor search is hard-capped at 12 (2^12 = 4096 states). Use Simplify Network to reduce the network first."*

  The Laplacian tab still renders normally — the two analyses are independent.

### Per-simulation NaN/Inf in Monte Carlo

- **Where:** a perturbation produces a divergent trajectory.
- **Detection:** `state_shift_monte_carlo` checks each simulation's final state with `np.isfinite(...).all()`.
- **Response:** failures are dropped from the aggregate, counted in `n_failed`. Summary table includes a row *"Simulations completed: {n_succeeded} of {n_simulations} ({n_failed} diverged)"*. Plots use only succeeded runs.

### Stale results after ISA edit

- **Where:** user runs analysis, switches to Edit Data, makes changes, switches back.
- **Detection:** `event_bus.on_isa_change` subscriber checks `result is not None`.
- **Response:** transient notification *"Data changed — re-run analysis to update results"* (i18n key `modules.analysis.common.data_changed_rerun` — port the existing R key). Results stay visible (so the user has reference) but flagged as stale.

### Out of scope

- Recovery from corrupt project files — handled upstream in `project_io.py`.
- Network/disk errors — neither module touches I/O.
- Translation key fallback — `t()` already handles missing keys with the English value.

## 6. Testing

Three test files, mirroring the per-module pattern (`tests/test_intervention_e2e.py`, `tests/test_leverage_e2e.py`).

### `tests/test_dynamics.py` — unit tests, no Shiny

About 25 tests covering the pure `sespy.dynamics` API.

**Matrix construction (4):**
- 2-node ISA → 2×2 signed matrix with correct polarity placement.
- Multiple edges between same pair → sum of weights.
- Isolated node → zero row/column, still in node list.
- Empty ISA → returns `(np.zeros((0,0)), [])`.

**Laplacian (4):**
- Path graph P_3 (3 nodes, 2 edges) — Laplacian has closed-form eigenvalues `{0, 1, 3}`. Test computes them and asserts match within `1e-9`. (Closed-form, not derived from `numpy.linalg.eig`, so not circular.)
- Asymmetric directed matrix → `direction="rows"` vs `direction="cols"` produce *different* eigenvalues (asserts inequality, since the in-degree and out-degree Laplacians differ).
- Complete graph K_4: spectral radius equals 4 (max abs eigenvalue).
- Complete graph K_n: algebraic connectivity equals `n` — closed-form check on second-smallest eigenvalue.

**Boolean rules + attractors (5):**
- Single-node positive self-loop (`M = [[1]]`) → at least one fixed-point attractor; basin_sizes sum to `2^1 = 2`. (Specific attractor states depend on threshold semantics in `create_boolean_rules`; the conservation property does not.)
- Two-node mutual inhibition (`M = [[0,-1],[-1,0]]`) → at least one attractor returned; basin_sizes sum to `2^2 = 4`.
- Three-node positive ring (cyclic graph A→B→C→A, all positive) → at least one cyclic attractor with `period >= 2`; basin_sizes sum to `8`.
- `max_nodes` cap returns `error: "too_large"`, no exception.
- Conservation invariant: for any network within `max_nodes`, `sum(attractor.basin_size for attractor in result.attractors) == 2 ** n_nodes`.

**Deterministic simulation (4):**
- Identity matrix + non-zero initial state → constant trajectory (every step equals the initial state).
- 1×1 with stable eigenvalue (|λ|<1) → trajectory decays toward zero.
- 1×1 with unstable eigenvalue (|λ|>1) → trajectory grows.
- `seed` reproducibility: same seed → identical trajectory (when `initial_state="random"`).

**Monte Carlo (5):**
- Same seed → identical `final_states` array.
- `n_failed` accounting: deliberately divergent matrix → `n_failed > 0` and `final_states` shape is `(n_succeeded, n_nodes)`.
- Summary statistics keys present for every node: `mean`, `sd`, `p5`, `p95`.
- Perturbation `kind="sign_flip"` only changes signs, never magnitudes.
- Empty matrix raises `ValueError`.

**Edge cases (3):**
- Non-square matrix → `ValueError` with informative message.
- All-zero matrix → simulation returns zeros, MC returns zeros, Boolean attractors finds **one absorbing fixed-point attractor at the all-zero state** with basin_size = 2^n. Reason: under threshold-strict semantics (`inflow > threshold`), every node always receives 0 input, `0 > 0` is False, so every starting state collapses to state-zero in one step. (An earlier draft said "2^n fixed points"; that wording assumed a tiebreaker semantics which would have broken the ring-oscillator test elsewhere in this spec — see plan §Task 8.)
- Single-node network handled by every function.

### `tests/test_boolean_e2e.py` — Playwright e2e

One scenario, mirroring `test_intervention_e2e.py` style:
- App starts with sample/template data preloaded.
- Navigate to Boolean module via stepper click.
- Wait for main UI to render (CLD gate passed).
- Click Run.
- Assert: eigenvalue plot image renders (`.shiny-plot-output img` non-empty), attractor table shows ≥1 row, no error alert visible.

### `tests/test_simulation_e2e.py` — Playwright e2e

Two scenarios in one file:
- **Deterministic**: navigate, click Run Simulation, assert trajectory plot renders and Final State bar chart populated.
- **Monte Carlo**: click Run Monte Carlo with `n_simulations=20` (small for speed), assert summary table shows N rows and `n_failed` cell visible.

Both e2e tests require the Shiny server running on `localhost:8000`, consistent with the existing e2e suite.

### Coverage targets

- **Numerics layer:** ~95% line coverage. The dynamics module is the substrate everything else depends on; regressions there are silent and corrupting.
- **Module layer:** smoke-tested via e2e only. Reactive callbacks are not unit-tested — the e2e tests cover the wiring, the unit tests cover the math.

## 7. Implementation ordering hint

A natural sequence (the writing-plans skill will refine this):

1. `sespy/dynamics.py` and `tests/test_dynamics.py` — write the math first, with tests, before any UI.
2. Translation keys — add both module namespaces to `core.json` so module files can use `t()` from the start.
3. `sespy/modules/analysis_boolean.py` (smaller surface, simpler controls) — get the module-shape pattern down first.
4. `sespy/modules/analysis_simulation.py` (two run buttons, more outputs).
5. Wire-up: `dashboard.py` nav + stepper, `app.py` registration.
6. `tests/test_boolean_e2e.py` and `tests/test_simulation_e2e.py`.

## 8. Non-goals

- Refactoring `sespy/network.py` or any existing module.
- Porting BOT, PIMS, AI-assisted SES creation, or other deferred R modules.
- Changing the project JSON schema or autosave format.
- Plotting library switch (matplotlib stays the standard).
- Any change to existing translation keys in `core.json`.
