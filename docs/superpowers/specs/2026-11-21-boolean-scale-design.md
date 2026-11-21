# Boolean attractor search at scale — design

Date: 2026-11-21. Status: draft for review. Pulls the Boolean part of roadmap item **P7a** forward
(`docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md`, on branch `docs/r-parity-roadmap`).

## 1. Problem

A user's 26-node project gets "Exhaustive Boolean attractor search is hard-capped at 12. Use
Simplify Network first." The cap is set in two places:
- The app (`sespy_app/modules/analysis_boolean.py`): the slider runs from 4 to 12, and the server clamps to that range.
- The library (`sespy/dynamics.py`): `BOOLEAN_MAX_NODES_CEILING = 20` (R's `DYNAMICS_MAX_BOOLEAN_NODES`).

The UI stays at 12 because `boolean_attractors` is a pure-Python loop over `2^N` states, and it runs
synchronously in the shared worker.

R reference (`SESToolbox/MarineSABRES_SES_Shiny`):
- `functions/ses_dynamics.R:527` runs BoolNet's exhaustive `getAttractors`, hard-capped at 20.
- The slider in `modules/analysis_boolean.R:144` runs from 5 to 20, with default 20.
- R has no sampled search.

## 2. Goals

- **A (R parity).** The app runs the exhaustive search up to **20** nodes without blocking the worker.
- **B (beyond R).** For networks above 20 nodes, a **sampled** search from random start states.
  - It reports the attractors it reached, estimated basin fractions and trajectories that did not converge.
  - It is labelled as non-exhaustive everywhere it is shown.

Non-goals:
- SAT- or BDD-based exact search.
- Asynchronous update schemes.
- Changing `create_boolean_rules` semantics.
- Raising the 20 ceiling.

## 3. Library (sespy 1.19.0)

### 3.1 Shared next-state kernel
`_boolean_next_states(rules, states: np.ndarray) -> np.ndarray` (private) maps an int64 array of
encoded states to their synchronous successors. Bit `i` is node `i`, as today.
- **Summation order.** For node `j`, it accumulates inflow in the existing order: activators in list order, then inhibitors in list order. Use float64 element-wise adds, never a matmul, so `inflow > threshold` ties resolve exactly as the current loop does.
- **Bounds.** It is valid for `1 <= len(rules) <= 62` (int64 packing).

### 3.2 `boolean_attractors` (exhaustive) — same API, same output
- **Signature, defaults, sentinel and result shape stay identical.** `max_nodes=12` default, ceiling 20, `too_large` sentinel. Nid4Ocean calls it with `max_nodes=12` and reads `error`, `attractors` and `total_states`.
- **Output stays bit-identical to the current implementation,** including order. Attractors are ordered by the smallest state in their basin. A cycle's `states` list starts at the first cycle state reached when walking from that smallest basin state.
- **Algorithm.** No Python loop over `2^N` states:
  1. `next = kernel(arange(2^N))`.
  2. Pointer doubling, N rounds: square the map and carry a running orbit-minimum. That yields, for every state, the minimum state of the cycle it falls into.
  3. `np.unique` on that label, with first indices, gives the attractors in discovery order and their basin sizes. The first index of each label is the basin's smallest state.
  4. Per attractor only, walk from that smallest state to its cycle entry and list the cycle.
- **Oracle.** The current loop moves to the tests as `_boolean_attractors_reference`, the oracle for differential tests.

### 3.3 `boolean_attractors_sampled` (new, public)
```
boolean_attractors_sampled(rules, n_samples=1000, *, max_steps=1000, seed=0,
                           max_nodes=BOOLEAN_SAMPLED_MAX_NODES) -> dict
BOOLEAN_SAMPLED_MAX_NODES = 62
```
- **Starts.** `n_samples` start states drawn uniformly, one random bit per node from `np.random.default_rng(seed)`. Duplicates are allowed: they are samples.
- **Stepping.** Each trajectory is stepped with the shared kernel, all trajectories at once, for at most `max_steps` steps. A trajectory that revisits a state has found its attractor. One that has not revisited a state after `max_steps` steps counts as **unconverged**.
- **Result:**
  ```
  {"method": "sampled", "attractors": [{"type", "states", "period", "hits", "basin_fraction"}],
   "n_samples", "n_unconverged", "seed", "max_steps", "n_nodes"}
  ```
  - `hits` counts the trajectories ending in that attractor.
  - `basin_fraction = hits / n_samples`.
  - Cycle `states` are rotated to start at their minimum state.
  - Attractors are ordered by `hits` descending, then by minimum state.
  - The result has no `basin_size` or `total_states`, whose documented meaning is exhaustive.
- **Sentinels:**
  - more than `max_nodes` nodes gives `{"method": "sampled", "attractors": [], "error": "too_large", "n_nodes", "max_nodes"}`;
  - 0 nodes gives an empty result with `n_samples` echoed.
- **Arguments.** `n_samples` and `max_steps` are each clamped to `[1, 100_000]`. Then a history budget, `n_samples × (max_steps + 1) ≤ 10⁷`, lowers `max_steps` if needed, and the result echoes the effective `max_steps`. The app clamps tighter.
- **BoolNet.** `getAttractors(method="random", startStates=k)` is the closest R analogue. Its documented semantics (what it reports for basins) are checked during implementation and noted in the docstring. SESPy's fractions are its own estimate.

### 3.4 Release
- **Version.** 1.19.0, since there is a new public name. It goes in `tests/test_public_api.py`.
- **Comment.** Update the ceiling comment at `dynamics.py:228-231` (the UI now uses an ExtendedTask and the vectorised search).
- **Translation keys.** New keys in `sespy/translations/core.json`, English text copied into all nine languages as the file does today:
  - `boolean.method`, `boolean.method_exhaustive`, `boolean.method_sampled`;
  - `boolean.n_samples`, `boolean.computing`;
  - `boolean.sampled_note` (`{n}`, `{seed}`, `{unconverged}`, `{max_steps}`);
  - `boolean.cap_above_max` (`{n}`, `{max}`; suggests the Sampled method), `boolean.col_hits`, `boolean.col_basin_fraction`.
  - `boolean.cap_below_12` and `boolean.cap_above_12` stay, for apps still on 1.0.x.

## 4. App (sespy-app 1.1.0)

### 4.1 Controls
- **Method:** radio buttons, Exhaustive (default) or Sampled.
- **Max nodes:** slider 4–20, default 20 (R's default).
- **Start states:** numeric 100–5000, default 1000. Shown only for Sampled.

### 4.2 Execution
- **Background task.** The run happens in a `@reactive.extended_task` via `asyncio.to_thread`. It follows the generation-counter pattern in `analysis_leverage.py:203-232`: a stale result is dropped, and a task error is logged and shown as the module's error alert.
- **While it runs,** the attractor panel shows `boolean.computing`.
- **Server-side clamps:** `max_nodes` to [4, 20] and `n_samples` to [100, 5000]. Sampled uses `seed=0` and `max_steps=1000`, both fixed.
- **Laplacian.** The stability result stays synchronous: it is cheap.

### 4.3 Output
- **Exhaustive:** the table is unchanged.
  - If the network has at most 20 nodes but more than the slider: `boolean.cap_below_12`, the existing "raise the slider" text.
  - If it has more than 20: `boolean.cap_above_max`.
- **Sampled:**
  - A note above the table: `boolean.sampled_note`, which says the result is non-exhaustive, with samples, seed and unconverged count.
  - Columns: type, period, hits, basin fraction (%), representative state.

### 4.4 Docs and tests
- MANUAL §17 describes both methods and the 20 cap. Regenerate the screenshot.
- `tests/test_boolean_e2e.py` assumes the 17-node sample exceeds the cap. It now sets the slider to 12 to keep testing the warning path, and a new e2e covers Sampled.
- MosaicSES embeds this panel ("Boolean & Laplacian"), so its full suite gates the app release.

## 5. Deploy

This is the **second** split-layout deploy, so plan-4's parked rerun states (N1–N4) become reachable. They are reviewed before the deploy, and each one is either fixed in 1.1.0 or accepted by a ruling.

Rollback is app-to-app:
- Run `deploy.sh --rollback` from the existing `sespy-app` clone, which stays detached at `v1.0.1`, with its `config.env` pointing at `sespy-lib-v1180`.
- The new deploy runs from a separate `sespy-app` worktree at `v1.1.0`, with its own `config.env` pointing at a new `sespy-lib-v1190` worktree.

## 6. Done when

- Exhaustive results are identical to the reference oracle on random rule sets with n ≤ 12.
- n = 20 exhaustive runs within the benchmark gate on this laptop.
- Sampled attractors are a subset of the exhaustive ones (n ≤ 12).
- The live app runs a 20-node exhaustive search and a 26-node sampled search, with the page responsive throughout.
- The About box shows "SESPy app 1.1.0 · sespy library 1.19.0".
