# Weighted signed propagation — design (SKELETON)

Date: 2026-11-22. Status: **skeleton for review**. Open decisions come first; no plan is written yet.
Version: library TBD (after 1.19.0), app TBD (after 1.1.0).
R parity: **SESPy-first**. R SESTool has no token diffusion.
Order: the note (§7.2) and this skeleton both put **path diagnostics first**
(`2026-11-22-path-diagnostics-design.md`). Propagation shares its strength-to-weight decision.

## Source
- `docs/Marine_intervention_causal_pathways_and_propagation_development_note.docx`. **It is not in git and not synced locally**; see the path spec's Source. Sections used: §3 (simulation), §5.2 (`token_diffusion` return fields), §6.2 (P3–P6, P9), Appendix B.
- **Shipped baseline:** `sespy.dynamics.token_diffusion(isa, source, *, n_steps=10, n_tokens=1000, seed=None)` (#17, #19–#21; app panel `sespy_app/modules/analysis_intervention.py`, run through `asyncio.to_thread`).

## What 1.18.0 does, verified in code (`dynamics.py:603`)
- **Choice:** a uniformly random out-neighbour. Strength is ignored.
- **Stopping:** tokens stop only at sinks. There is no decay and no stop probability.
- **`tokens_received` counts arrivals over all steps,** so loops inflate it. It is **not** the note's "reach probability" (the share of tokens that ever visit the node).
- **First arrival** is the earliest step at which any token arrived. It is not a median or quantile.
- **Uncertainty:** the 95% margin comes from batch means. `net_sign` uses Student's t over the batches. Ranks use a paired-difference test against the group leader.

## Open decisions (user)
1. **Strength to weight: settled — `bayes.STRENGTH_LINK`** (path-diagnostics spec, decision 1, user 2026-11-22). Missing strength falls back to medium.
2. **Backwards compatibility.** The new behaviour comes from new keyword parameters (`transition="uniform"|"weighted"`, `decay=1.0`, `stop_prob=0.0`). Their defaults must reproduce 1.18.0 **exactly** for a fixed seed, **including the RNG draw sequence**, or the new mode goes in a separate function. Pin it with a regression test on stored 1.18.0 outputs.
3. **Reach metric.** Add `reach_probability` (the share of tokens that ever visit) next to `tokens_received`, or replace it in the UI? Recommendation: add it, and show reach in the UI.
4. **First arrival.** Keep the earliest step and add quantiles (`first_arrival_q50`, plus others if cheap)? That needs a per-token first-visit record: `n_tokens × n` int16, which is small.
5. **Repeated runs vs batches.** The note asks for "≥ 100 runs for intervals".
   - The existing batch means (`_DIFFUSION_BATCHES = 20`) give honest **mean** intervals for i.i.d. tokens.
   - But q05 and q95 can barely be estimated from 20 batches.
   - Batch quantiles also describe runs of `n_tokens / 20` tokens, not a full run.
   - Options: (a) intervals on the mean only, with no quantiles; (b) an `n_runs` parameter with run-level quantiles, which multiplies the cost; (c) more batches, which changes 1.18.0 margins (cf. decision 2).
   - No recommendation yet.
6. **Signed mass.** With `decay < 1`, mass differs from counts. Report positive and negative shares separately, never only their net (note §6.1). Mass accounting (P6): propagated + stopped + decayed reconcile.
7. **Presets.** The note suggests 1,000 tokens interactively and 10,000 for reports. App presets or free sliders?

## Scope (library)
Extend `token_diffusion` per decisions 2–6 (new keys only; existing keys unchanged), or add `signed_propagation`. Decide which in review. Note §5.2 fields to cover:
- `reach_probability`;
- `signed_mass_mean` and `signed_mass_q05/q50/q95`;
- `first_arrival_q50`;
- `positive_share` and `negative_share`.

## Scope (app)
- **`analysis_intervention.py`** gains a transition / decay / stop control group (or presets), a reach column and the positive and negative shares.
- **MosaicSES pins `analysis_intervention_server(id, project_data, event_bus, translator)`** (`tests/test_compartments_module.py:300`), so the signature must not change, and the MosaicSES suite gates the release.

## Acceptance (from note §6.2, adapted)
- **P3:** a deterministic chain reaches nodes in order.
- **P4:** one negative edge flips the sign exactly once.
- **P5:** the same seed gives identical output.
- **P6:** mass reconciles.
- **P7:** missing strength falls back explicitly, with no NaN.
- **P9:** the interactive default runs in ≤ 2 s on the reference graph (measure on laguna-like load).
- **New:** default parameters equal the stored 1.18.0 outputs (decision 2).

## Later (not this spec)
- Temporal delays in propagation (note v3; delays are only 3 categories today).
- Capacity limits.
- Calibration.
- `compare_interventions`, which goes to roadmap P7b/P8.
