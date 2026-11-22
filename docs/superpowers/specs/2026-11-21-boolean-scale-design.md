# Boolean attractor search at scale — design (rev. 2)

Date: 2026-11-21. Status: draft for review. Revision 2 follows the investigation in
`2026-11-21-boolean-scale-research.md` and the user's decisions of 2026-11-21:
- **No R parity** for this analysis. SESPy keeps its weighted-threshold rules; the difference from R/BoolNet is intentional and recorded in the research note.
- **Scope:** feedback-core search as the main route, sampling only above the core limit, a plain-language all-off result, no new dependencies. **Driver scenarios come later, as a separate phase (§7).**

This pulls the Boolean part of roadmap item P7a forward.

## 1. Problem

A user's 26-node project gets "Exhaustive Boolean attractor search is hard-capped at 12". The
current search enumerates all 2^n states in a pure-Python loop, synchronously in the shared worker.

The investigation measured three things:
- **Core sizes.** Only the **feedback core** (nodes downstream of a cycle and upstream of one) determines the attractors. Among the 32 shipped networks above 20 nodes, 31 have a core of 20 or fewer; the Caribbean template (core 64) is the exception.
- **What the analysis returns.** Under SESPy's rules, all-off is always a fixed point, and **52 of 57** shipped networks have no other attractor.
- **Speed.** A core search returns the attractor set of every shipped network except Caribbean in ≤ 0.4 s.

## 2. Goals

1. **Exact attractors** for any network whose feedback core is at most `BOOLEAN_MAX_CORE` (20, confirmed by the benchmark gate). The whole-network size doesn't matter.
2. **Basin sizes:** exact within a computation budget, otherwise estimated by sampling. The result always says which.
3. **Large cores:** for a core above the limit, a **sampled** search over the whole network, labelled non-exhaustive.
4. **All-off in plain words:** when the only attractor is all-off, the UI says so instead of showing one opaque row.
5. **Non-blocking:** the search runs in a background task.

**Non-goals:**
- R/BoolNet semantics.
- New dependencies (numba, MILP, SAT/BDD).
- Fixed-point enumeration through a feedback vertex set.
- Solving cluster by cluster.
- Driver scenarios: phase 2.

## 3. Library (sespy 1.19.0)

### 3.1 Shared kernel
`_boolean_step(rules, X, *, cols, nodes, fixed=None) -> np.ndarray` (private).
- **Inputs.** `X` is a `(S, len(cols))` uint8 matrix whose column `k` holds node `cols[k]`. `fixed` maps every other node an evaluated rule reads to a constant 0/1.
- **Output.** A `(S, len(nodes))` uint8 matrix of the next values of `nodes`.
- **Summation order.** For node `j`, set `inflow = 0.0` (float64 per row), add `w * x_i` for each activator in list order, then for each inhibitor in list order. `x_i` is `X[:, k]` for a live node and the constant `fixed[i]` otherwise, added **in its list position**. The new value is `inflow > threshold`. No matmul, so float ties resolve exactly as `boolean_attractors` does.
- **Memory.** Only live columns are materialised: the core search holds `2^|C| × |C|` bytes, not `2^|C| × n`.
- **Representation.** The matrix form has no 62-node limit. Whole-network stepping uses `cols = nodes = range(n)`.

### 3.2 `boolean_attractors` — unchanged
Its code, signature and output stay as they are. It is the oracle for the differential tests, and Nid4Ocean calls it with `max_nodes=12`.

### 3.3 `boolean_attractors_core` (new, public)
```
boolean_attractors_core(rules, *, max_core=BOOLEAN_MAX_CORE, basin_budget=BOOLEAN_BASIN_BUDGET,
                        basin_samples=10_000, seed=0) -> dict
BOOLEAN_MAX_CORE = 20
BOOLEAN_BASIN_BUDGET = 1 << 24          # core-state evaluations for the exact basin pass; final value set by the benchmark gate (§6)
BOOLEAN_MAX_NODES_TOTAL = 200           # sanity cap on n
```

**Algorithm:**
1. **Partition** with networkx on the rule graph:
   - upstream U: not downstream of any cycle (self-loops count as cycles);
   - core C: downstream ∩ upstream of a cycle;
   - read-out R: downstream only.
2. **Constant propagation.** Step U |U| + 1 times, with any start, to its fixed pattern u*. Assert it is fixed: U depends only on U, and its sources have inflow 0.
3. **Core search.** Build the `2^|C|` core states as a `(2^|C|, |C|)` matrix. Step it with `_boolean_step(cols=C, nodes=C, fixed=u*)`; core rules read only core and upstream nodes. Label cycles on the compact core map with pointer doubling and an orbit minimum. No Python loop over states.
4. **Reconstruction.** For each core attractor, step the full matrix from (u*, core state, R = 0) until the full state repeats. That gives the full attractor, read-outs included.
5. **Basins.**
   - **One attractor:** its basin is `2^n` by definition. Skip the pass and report `basin_method = "exact"`. This covers 52 of 57 shipped networks, including every all-off one.
   - **Exact factors:** read-outs, and upstream nodes that are **not ancestors of the core**, multiply basins by exactly `2^k`.
   - **Upstream ancestors of the core** (U_a) perturb the core during the transient:
   - Simulate U_a alone from all `2^|U_a|` starts (only when `2^|U_a| ≤ 2^20`).
     *Erratum (Task 3 benchmark):* the cap is `|U_a| ≤ 16` (`2^|U_a| ≤ 2^16`), not 2^20. Case (d) of `tests/bench_boolean_core.py` (a 20-ancestor delay chain into a 4-node core) took 31 s and peaked at 1036 MB at the cap of 20, and 6.9 s / 233 MB at 18; at 16 it takes 0.76 s / 52 MB. Above the cap the attractor set stays exact and the basins fall back to `basin_method = "sampled"`.
   - Deduplicate by the sequence of values the core's upstream inputs take over the transient.
   - If `(distinct sequences) × 2^|C| ≤ basin_budget`, compute basins exactly by driving every core state with each sequence and labelling the result. `basin_method = "exact"`.
   - Otherwise, estimate fractions from `basin_samples` random full starts (seed `seed`), each run until its core state reaches a labelled attractor. `basin_method = "sampled"`.

**Result:**
```
{"method": "core", "n_nodes", "core_size", "upstream_size", "readout_size",
 "basin_method": "exact" | "sampled",
 "attractors": [{"type": "fixed"|"cyclic", "states": [int, ...], "period": int,
                 "basin_size": int | None, "basin_fraction": float}],
 "all_off_only": bool}
```
- **States** are Python ints, with bit `i` for node `i`. There is no width limit, and JSON is safe.
- **Cycles** are rotated to start at their minimum state.
- **Order:** attractors by `basin_fraction` descending, then by minimum state.
- `basin_size` is set when `basin_method == "exact"`; the sizes sum to `2^n`. `basin_fraction` is always set.
- `all_off_only` is true when there is exactly one attractor and it is the fixed state 0.

**Sentinels:**
- core above `max_core`: `{"method": "core", "attractors": [], "error": "core_too_large", "n_nodes", "core_size", "max_core"}`;
- n above `BOOLEAN_MAX_NODES_TOTAL`: `"error": "too_large"`;
- n = 0: an empty result.

### 3.4 `boolean_attractors_sampled` (new, public) — whole network, for cores above the limit
```
boolean_attractors_sampled(rules, n_samples=2000, *, max_steps=1000, seed=0) -> dict
```
- **Starts:** uniform random start rows from `np.random.default_rng(seed)`.
- **Stepping:** all trajectories are stepped at once with `_boolean_step` for at most `max_steps` steps. History is kept as packed rows, bounded by a budget of `n_samples × (max_steps + 1) ≤ 10^7`; `max_steps` is lowered to fit and the effective value is echoed.
- **Convergence:** a trajectory converges at its first repeated state. One that hasn't repeated after `max_steps` is **unconverged**.
- **Result:** `{"method": "sampled", "attractors": [{"type","states","period","hits","basin_fraction"}], "n_samples", "n_unconverged", "seed", "max_steps", "n_nodes"}`.
  - There is no `basin_size`.
  - Attractors are ordered by hits descending, then by minimum state.
  - Cycles are rotated to start at their minimum state.
- **Clamps:** `n_samples` and `max_steps` to [1, 100 000]. n above `BOOLEAN_MAX_NODES_TOTAL` gives `too_large`.

### 3.5 Release
- **Version:** 1.19.0. The new names go in `tests/test_public_api.py`.
- **Comment:** update the comment at `dynamics.py:228-231`.
- **Translation keys:** new keys in `core.json`, English text in all nine languages, as the file does today:

  | Key | Text |
  |---|---|
  | `boolean.core_info` | "{n} nodes · {core} in the feedback core" |
  | `boolean.basins_exact` | "basin sizes exact" |
  | `boolean.basins_sampled` | "basin fractions estimated from {samples} random starts" |
  | `boolean.all_off` | "Without external drivers, no feedback loop keeps any element active: every state settles to all elements off." |
  | `boolean.core_too_large` | "The feedback core has {core} nodes, above the exact limit of {max}. Showing a sampled search instead." |
  | `boolean.sampled_note` | "Sampled search: {n} random start states (seed {seed}). Rare attractors may be missed; basin fractions are estimates. {unconverged} trajectories did not settle within {max_steps} steps." |
  | `boolean.computing` | "Computing attractors…" |
  | `boolean.col_hits` | "Hits" |
  | `boolean.col_basin_fraction` | "Basin fraction (%)" |

  Existing keys stay, for apps still on 1.0.x.

## 4. App (sespy-app 1.1.0)

### 4.1 Controls
- **The max-nodes slider is removed,** because the limit now applies to the core and is fixed by the library.
- **"Laplacian direction" and "Run analysis" stay.**
- **No new controls.** The sampled fallback uses n_samples = 2000, seed = 0 and max_steps = 1000. None of these can be set from the client.

### 4.2 Execution
- **Background task.** `@reactive.extended_task` via `asyncio.to_thread`, using the generation-counter pattern from `analysis_leverage.py:203-232`. A stale result is dropped; a task error is logged and shown as the module's error alert.
- **While it runs:** the panel shows `boolean.computing`.
- **Route:** call `boolean_attractors_core`. On `core_too_large`, call `boolean_attractors_sampled` and show the `core_too_large` note above its result.
- **The Laplacian stays synchronous.**

### 4.3 Output
- **Header line:** `core_info` plus `basins_exact` or `basins_sampled`.
- **`all_off_only`:** show the `all_off` sentence as an info alert. The single-row table is not shown.
- **Otherwise:** a table with type, period, basin fraction (%), basin size (exact only) and representative state.
- **Sampled:** the `sampled_note`, then type, period, hits, basin fraction (%) and representative state.

### 4.4 Docs and tests
- **MANUAL §17** describes the feedback core, the exact limit, the sampled fallback and the all-off reading. Regenerate the screenshot.
- **`tests/test_boolean_e2e.py`** asserts the 17-node sample's all-off info alert, instead of the old cap warning.
- **`tests/test_boolean_happy_e2e.py`** keeps a multi-attractor template.
- **New e2e** on the Caribbean template asserts the sampled path.
- **MosaicSES gate:** MosaicSES embeds this panel, so its full suite gates the release.

## 5. Deploy
This is the second split-layout deploy, so plan 4's parked rerun states (N1–N4) are reviewed first, and each is either fixed or accepted by a ruling.
- **Rollback** is app-to-app: `deploy.sh --rollback` from the existing `sespy-app` clone. Its checkout, files and `config.env` stay at `v1.0.1` with `sespy-lib-v1180`. Adding linked worktrees to its repository and fetching tags there are allowed, because they don't change its working tree.
- **The deploy** runs from a new `sespy-app-v110` worktree with a new `sespy-lib-v1190`.

## 6. Done when
- The core search's attractor sets and exact basins equal `boolean_attractors` on random networks (n ≤ 14) whose shapes include multiple cycle clusters, bridges, fan-in and upstream-to-read-out edges, and on the shipped multi-attractor networks within 20 nodes.
- **Benchmark gates hold**, each ≤ 5 s and ≤ 300 MB peak:
  - the attractor set for a 20-node core inside a 200-node network;
  - the exact basin pass at `BOOLEAN_BASIN_BUDGET`, whose value is lowered until it passes;
  - `boolean_attractors_sampled` on Caribbean at the app's settings (2000 × 1000).
- **Caribbean (measured by probe):** 2000 starts × 1000 steps leave 0 unconverged and reach 4 cyclic attractors (periods 6, 3, 2, 6), with transients ≤ 42.
- Live:
  - Fisheries shows "26 nodes · 14 in the feedback core" and the all-off sentence;
  - a multi-attractor network (`offshore_wind`) shows its table;
  - Caribbean shows the sampled path;
  - the page stays responsive throughout;
  - About shows "SESPy app 1.1.0 · sespy library 1.19.0".

## 7. Phase 2 (later, separate spec): driver scenarios
In this mode, chosen input-less "driver" nodes hold their starting value instead of switching off.
- **Implementation:** force their bits after each step. No kernel change, and they stay out of the core partition.
- **Measured behaviour:** each driver setting gave exactly one outcome (Pollution: the core activates in 176 of 256 settings; OffshoreWind: 32 of 64).
- **Interface:** pick the drivers and get one result. Enumerating every setting doesn't scale (up to 18 drivers in MosaicSES compartments).
- **Needs:** its own UI design and spec once phase 1 has shipped.
