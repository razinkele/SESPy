# Weighted signed propagation — design

Date: 2026-11-24 (skeleton 2026-11-22). Status: **draft, awaiting user approval**.
Versions: library **sespy 1.21.0** (after 1.20.0), app **sespy-app 1.3.0** (after 1.2.0).
R parity: **SESPy-first**. R SESTool has no token diffusion.
Order: follows path diagnostics (`2026-11-22-path-diagnostics-design.md`, live since 2026-11-24). It reuses that work's strength weights and perturbation model.

## Intent

Today's Intervention panel can only say "tokens wander everywhere, uniformly". It ignores how strong each link is and how sure we are of it, and counts that loops inflate. The development note's "v2" asks for propagation that answers three questions:
- How likely is an intervention's influence to reach each element?
- How soon does it get there?
- With what sign, weighted by link strength and dissipating along the way?

Its uncertainty should come from **doubt about the map itself**, not from sampling noise. Path diagnostics explain *why* an effect is possible. Propagation shows *how broadly and how fast* influence may spread under stated assumptions (note §1, §4).

## Source

- `SESPy/docs/Marine_intervention_causal_pathways_and_propagation_development_note.docx`.
  - Untracked; it stays uncommitted, but is readable on the DELL machine.
  - Sections used: §3 (simulation and configuration), §5.1–5.2 (workflow and return fields), §6.1 (safeguards), §6.2 (P3–P10), Appendix B.
- Shipped baseline: `sespy.dynamics.token_diffusion` (`dynamics.py:1316`).
  - Each step picks a uniformly random out-neighbour.
  - Tokens stop only at sinks.
  - Repeat visits count, so loops inflate the totals.
  - Intervals come from batch means of token noise.
  - It implements step 2 of Donlan et al. 2026 (MANUAL §40).
- Reused:
  - `bayes.STRENGTH_LINK` (weak 0.30, medium 0.55, strong 0.80);
  - `network._perturbed_connections`: each link drops with probability `base·(5−confidence)/4`, then flips sign by confidence or rater posterior;
  - the app's path-robustness pattern (background task plus CSV guard).

## Decisions (user, 2026-11-24)

1. **Strength to weight:** `bayes.STRENGTH_LINK`. Missing or unknown strength counts as medium and is counted in the result (decided 2026-11-22 in the path spec).
2. **Intervals show uncertainty about the map** (option b).
   - The repeated runs each use a perturbed map: links drop or flip by confidence, as in the path robustness check.
   - The single run on the map as given is the point estimate.
   - Token-noise intervals are not reported.
3. **Approach B: a new function pair.** `signed_propagation` (one run, map as given) and `propagation_sensitivity` (repeated perturbed runs) mirror `causal_paths` and `path_sensitivity`.
   - `token_diffusion` stays in the library, unchanged, for API compatibility.
   - The app's diffusion section becomes the propagation section.
4. **The uncertainty display leads with robustness shares** (option 1).
   - Two columns: "Reached in % of variants" and "Sign holds in %".
   - The q05/q50/q95 ranges go in the CSV only.
   - Reason, measured on the sample model (D001, default settings, 200 variants): the reach q05 was 0.00 for every element, because D001's single out-link drops in about 12% of variants. A range would read "0 to something" everywhere.

## Approaches considered

| | Approach | Trade-off | Outcome |
|---|---|---|---|
| A | New keyword options on `token_diffusion` plus a separate runs function | Defaults would have to reproduce 1.18.0 exactly, including the RNG draw order. Weighted choice draws differently, so the code forks anyway, and the return fields don't match the note. | Rejected |
| **B** | **New `signed_propagation` + `propagation_sensitivity`** | Mirrors the shipped path pair, has clean note-aligned fields and no compatibility trap. Costs two more public functions. | **Chosen** |
| C | One function with `n_runs` | Simple call, but the interactive and slow report results share one shape. The quick result can't show first with the slow one in the background. | Rejected |

Replacing `token_diffusion` outright was dropped: it breaks the library API.

## Goals

- Weighted, signed, dissipating propagation from one source with note-aligned per-element fields.
- Map-uncertainty robustness that reads like the path robustness table.
- Explicit fallbacks with no NaN or Inf, mass that reconciles, and seed-reproducible results.
- The app shows a quick result at once and runs the uncertainty in the background, with CSV export.

## Non-goals

- Temporal delays in propagation. Note v3: delays have only three categories today.
- Capacity limits, calibration, spatial leakage.
- `compare_interventions`, which goes to roadmap P7b/P8.
- A no-revisit sensitivity run (note §3.2), which is a later option.
- Changing `token_diffusion`.
- Edge evidence fields, which wait on SESPy#41.

## Anti-goals (a failure even if it works)

- Precise-looking intervals that only measure token noise.
- A single net-sign label from one run with no noise rule. That brings back issue #19, which mislabelled balanced nodes.
- Netting positive and negative mass into one score without both shares beside it (note §6.1).
- Results presented as effect sizes. Every caption says "structural simulation, not a forecast".

## Library: `sespy.dynamics.signed_propagation`

```python
signed_propagation(isa, source, *, n_steps=8, n_tokens=1000, decay=0.8,
                   stop_prob=0.15, transition="weighted", seed=0) -> dict
```

Defaults are the note's development defaults (§3.2).

**Graph.** Same conventions as `token_diffusion`:
- parallel connections deduplicate last-wins;
- self-loops and dangling references are skipped;
- only `"-"` flips a sign.

Weights:
- `transition="weighted"`: `STRENGTH_LINK[c.strength]`; anything else counts as medium.
- `"equal"`: uniform choice.
- Any other value raises `ValueError`.

**Inputs.** Clamped and echoed:
- `n_steps` to [1, 100];
- `n_tokens` to [1, 100000];
- `decay` and `stop_prob` to [0, 1].

An unknown source, an empty model, or a source with no out-links returns the empty shape and never raises.

**Walk.** Every token starts at the source with sign +1 and mass 1. For step = 1..n_steps, each *live* token does the following, in this order:
1. **Move:** pick an out-edge with probability proportional to its weight.
2. **Sign:** multiply the token's sign by the edge sign.
3. **Decay:** the token's mass becomes `mass·decay`, and the lost `mass·(1−decay)` is added to `decayed`.
4. **Deposit** at the node it landed on:
   - mark the node visited (once per token);
   - record the first-visit step;
   - add the token's mass to that node's positive or negative mass. Every arrival deposits, so revisits count but are discounted by decay.
5. **Stop:** with probability `stop_prob` the token stops, and its mass goes to `stopped`.
6. **Sink:** if it hasn't stopped and the node has no out-links, the token is absorbed and its mass goes to `absorbed`.

Live tokens left after the last step add their mass to `in_transit`.

- **Mass identity (P6):** `decayed + stopped + absorbed + in_transit == n_tokens`, within 1e-9·n_tokens.
- **Vectorised:** a fixed number of RNG draws per step over the live tokens, as in `token_diffusion`. The builder chooses the method, e.g. a per-node cumulative-weight table with `searchsorted`.
- **Reproducibility:** `np.random.default_rng(seed)`; the same inputs reproduce bit-for-bit.

**Rows.** One per element other than the source that has `reach_probability > 0`:

| key | meaning |
|---|---|
| `id`, `label` | element |
| `reach_probability` | share of tokens that visited it at least once in steps 1..n_steps |
| `first_arrival_min` | earliest first-visit step over tokens |
| `first_arrival_q50` | median first-visit step over the tokens that visited (`np.median`, `method="lower"`, so an int) |
| `positive_mass`, `negative_mass` | deposited mass per token: sum / n_tokens |
| `signed_mass_mean` | `positive_mass − negative_mass` |
| `positive_share`, `negative_share` | of `positive_mass + negative_mass`; `None` when that sum is 0, e.g. `decay=0` |

Sort by `reach_probability` descending, ties in `isa.elements` order.

**Return:**

```text
{rows, source, n_steps, n_tokens, decay, stop_prob, transition, seed, n_reached,
 n_default_strength, mass: {decayed, stopped, absorbed, in_transit}}
```

- `mass` values are shares of `n_tokens`.
- `n_default_strength` counts kept connections whose strength fell back to medium. It is 0 under `"equal"`.

## Library: `sespy.dynamics.propagation_sensitivity`

```python
propagation_sensitivity(isa, source, *, n_runs=200, base=0.5,
                        flip_mode="confidence", draw_strength=False, seed=0,
                        n_steps=8, n_tokens=1000, decay=0.8, stop_prob=0.15,
                        transition="weighted") -> dict
```

- **Baseline:** `signed_propagation(isa, source, …, seed=seed)` on the map as given. The rows follow the baseline rows, in their order, as in `path_sensitivity`.
- **Runs:**
  - `n_runs` is clamped to [1, 2000] and `base` to [0, 1].
  - `flip_mode` is validated as in `path_sensitivity`.
  - Run k uses `np.random.default_rng(child_k)`, where `child_k = np.random.SeedSequence(seed).spawn(n_runs)[k]`. That generator:
    1. perturbs the map with `_perturbed_connections(isa, base, rng, flip_mode)`;
    2. with `draw_strength`, gives each rated kept edge the strength of one uniformly drawn rating, as in `path_sensitivity`;
    3. draws the walk seed with `rng.integers(2**63)`.
  - A run where the source lost every out-link counts as zero reach and zero mass for every element. It is never skipped.
- **Per baseline row, added keys:**
  - `reached_share`: share of runs with reach > 0.
  - `sign_holds_share`: share of runs whose `signed_mass_mean` has the same nonzero sign as the baseline's. It is `None` when the baseline net is exactly 0. A run with zero net counts as "not held".
  - `reach_q05`, `reach_q50`, `reach_q95` and `signed_mass_q05`, `signed_mass_q50`, `signed_mass_q95`: over all runs, unreached runs counting as 0. These go to the CSV only (decision 4).
- **Return:**

  ```text
  {rows, source, n_runs, base, flip_mode, draw_strength, seed, the walk parameters,
   n_default_confidence, n_default_strength}
  ```

  - `n_default_confidence` counts connections whose stored confidence is not an int in 1..5, so `_coerce_confidence` used 3.
- **Elements reached only in variants** are not listed. That matches `path_sensitivity`, and the doc string says so.

**Translations.** New `propagation.*` keys in `core.json` for all 9 languages. The unused `diffusion.*` keys stay, since any external consumer may read them.

## App: Intervention panel (`sespy_app/modules/analysis_intervention.py`)

**Constraints:**
- It still runs on `diffusion_isa()`, so elements picked for removal stay removed.
- The `analysis_intervention_server(id, project_data, event_bus, translator)` signature is unchanged; MosaicSES pins it in `tests/test_compartments_module.py:300`.
- The old input ids (`diffusion_source`, `n_steps`, `n_tokens`, `run_diffusion`) are replaced by `prop_*` ids. GitHub code search finds none of them in MosaicSES; the MosaicSES suite confirms this at release.

**Controls:**
- **Source:** select. It keeps the current pick across re-renders, as today.
- **Preset:** radio.
  - "Interactive (1,000 tokens)" (default).
  - "Report (10,000 tokens)".
  - "Equal links, no decay (Donlan et al. 2026)": equal transition, decay 1, stop 0, 1,000 tokens. This is the old method's semantics with the new fields.
- **Advanced:** a collapsed accordion.
  - steps slider 2–20 (default 8);
  - decay 0–1 (0.8);
  - stop chance 0–0.5 (0.15);
  - link choice: "By link strength" or "Equal".

  Picking a preset sets these. Editing them leaves the preset as is (builder's call how to show "custom").
- **Run propagation:** an extended task through `asyncio.to_thread`, seed 0. The same seed keeps two sources differing by structure, not chance, as today.

**Results:**
- **Summary lines:**
  - mass bookkeeping: "Of the injected influence: x% decayed, y% stopped, z% absorbed at dead ends, w% still moving after step n";
  - "k links have no strength rating; counted as medium", when k > 0;
  - the caption: "structural simulation under stated assumptions; not a forecast or effect size".
- **Table:** Element, Reach, Median first step, + share, − share, Net mass. No net-sign label (anti-goal).
- **Chart:** reach per element, split into positive and negative parts by the shares. It replaces the arrivals chart, top 12 as today.
- **Estimate uncertainty:** a button, enabled once a run is shown.
  - Runs `propagation_sensitivity` (200 runs, base 0.5, the same walk settings) in a background extended task with a computing state, as "Test robustness" does.
  - Adds the "Reached in % of variants" and "Sign holds in %" columns.
  - Adds a caption: "200 perturbed versions (seed 0): each link may drop out or flip sign, more often the lower its confidence", plus "k links have no confidence; counted as 3" when k > 0.
  - Base is fixed at 0.5 in the app, as in the path robustness check. It is a library parameter.
- **Download (CSV):** the table plus, when computed, `reached_share`, `sign_holds_share` and the six quantile columns, with the parameters in the header rows. It uses the same formula-injection guard as the path CSV.
- **Invalidation:** the same generation pattern as today. Any change to the model, removals, source or settings clears the result and any uncertainty result; a stale task result is dropped. Clearing the run clears its uncertainty.

**Docs:**
- MANUAL §40 is rewritten as "Signed propagation". It keeps the Donlan et al. citation for the equal-links setting and cites the note.
- Fix the stale caveat at MANUAL line 340, which says the diffusion ignores the ablation. It has used `diffusion_isa()` since the MosaicSES tester report of 23 Oct.
- Regenerate the screenshot with `tests/make_docs_screenshots.py`.

**Tests:**
- Replace the coverage in `tests/test_intervention_diffusion.py`.
- Update `test_intervention_e2e.py`.
- Add e2e for the uncertainty button and CSV.

## Acceptance (note §6.2, adapted)

- **P3:** on a chain with one out-edge per node, `decay=1` and `stop_prob=0`, reach is 1 along the chain and `first_arrival_q50` equals the hop index.
- **P4:** one negative edge on that chain flips the sign exactly once: positive share 1 before it, negative share 1 after.
- **P5:** the same inputs and seed give identical output, for both functions.
- **P6:** the mass identity holds for random graphs and parameters, including `decay` 0 and 1 and `stop_prob` 0 and 1.
- **P7:** missing strength or confidence falls back to medium or 3, is counted, and no NaN or Inf appears anywhere. Zero-mass shares are `None`.
- **P8:** dropping the only path in a variant lowers `reached_share`. A confidence-5 chain has `reached_share` 1 and `sign_holds_share` 1.
- **P9:** on the reference graph (`data/sample_ses.json`), on laguna-like load:
  - `signed_propagation` defaults finish in ≤ 2 s;
  - the Report preset in ≤ 30 s;
  - `propagation_sensitivity` defaults in ≤ 30 s.
- **P10:** the CSV values match the visible table.
- **Equal setting:** with `transition="equal"`, `decay=1`, `stop_prob=0`, the same elements are reached as by `token_diffusion` for the same graph and step count.

## Release

1. The library goes through a PR, merge and the `v1.21.0` tag, with the user's manual steps as before.
2. The app pins `@v1.21.0` and is released as 1.3.0.
3. The MosaicSES suite gates the app release.
   - **There is no MosaicSES clone or `verify_live.py` on the DELL machine.** Either clone it here or run the gate on X1.
4. Deploy to laguna as for 1.2.0.

## Left to the builder

- The vectorised sampling technique.
- How to show a "custom" preset.
- Chart styling.
- Doc-string wording.
- Exact `propagation.*` key names and translations (9 languages, reviewed as in 1.20.0).
- Test fixture shapes.
