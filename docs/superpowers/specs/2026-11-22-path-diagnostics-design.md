# Causal path diagnostics and path sensitivity — design (SKELETON)

Date: 2026-11-22. Status: **skeleton for review**. Open decisions come first; no plan is written yet.
Version: library TBD (after 1.19.0), app TBD (after 1.1.0). Both of those releases are in flight on `feat/boolean-scale`.
R parity: **SESPy-first**. R (`SESToolbox/MarineSABRES_SES_Shiny/functions/network_analysis.R`) has `find_pathways` (line 266) and `find_all_paths(nodes, edges, from_id, to_id, max_length = 10)` (line 1271), which return plain node-id paths with no polarity. A grep found no callers of either outside tests. R has no path scoring, bottleneck reporting or path sensitivity.

## Source
- `docs/Marine_intervention_causal_pathways_and_propagation_development_note.docx`, a Copilot-generated note dated 2026-11-21. **It is not in git and was not synced to this laptop on 2026-11-22.** It was read from the online OneDrive copy (`SESPy/docs/`), and a duplicate sits in `Documents/Copilot/Created/`. Whether to commit it is the user's call. Sections used: §2 (paths), §5.2 (`causal_paths` and `path_sensitivity` return fields), §6.2 (P1, P2, P7, P8, P10), Appendix A.
- **Why the note overlaps with shipped work.** Its basis (Appendix C) is `LITERATURE/proposed-issues.md`, written before #16 (`causal_paths`, shipped 2026-08-16) and before #17/#19–#21 (diffusion). Only what is genuinely new is specified here.

## Open decisions (user)
1. **Strength to weight.** The note scores paths on weights in 0–1, but SESPy stores `weak | medium | strong`. Two mappings already exist:
   - `bayes.STRENGTH_LINK` = {0.30, 0.55, 0.80}, used by the Bayesian noisy-OR;
   - `network._STRENGTH_RANK` = {1, 2, 3}, used by the Boolean rules, the adjacency matrix and rater aggregation.

   Recommendation: reuse `STRENGTH_LINK`, since it is already on a 0–1 scale. Never invent a third mapping.
2. **Path score formula.** The note gives `Π|w| · exp(−λ(L−1))`. Decide the default λ, whether λ is user-settable, and whether to show the score next to the existing length-sorted listing or to sort by it.
3. **Ranking on a truncated set.** `causal_paths` stops at `max_paths` **in enumeration order**, so a score-sorted top-k drawn from a truncated set can miss the strongest path.
   - Candidate: best-first enumeration with `nx.shortest_simple_paths` and edge cost `−log(w) + λ`, which yields paths in descending score.
   - It has no length cutoff, and its cost on dense graphs is unmeasured. **Probe it before choosing.**
4. **Delay per path.** `Connection.delay` has 3 levels (`immediate | short | long`, `constants.DELAY_LEVELS`), with no step counts. Options:
   - report counts per level ("2 short, 1 long");
   - report an ordinal maximum;
   - define steps.

   Recommendation: counts per level. No new numbers.
5. **Edge evidence fields** (`evidence_type`, `source_reference`, `spatial_scope`). Out of scope here; they need a schema bump. Decide them together with the evidenced-polarity work (SESPy#41, spec `sespy-evpol/docs/superpowers/specs/2026-11-19-evidenced-polarity-design.md`, which adds no field). Until then, "evidence profile" means the existing `confidence`, `ratings` and `description`.
6. **Bottleneck rule.** Options: the lowest strength with ties broken by the lowest `confidence`, the lowest `confidence` first, or both reported separately. The note says "lowest-weight or highest-uncertainty".
7. **The worked example (10 nodes, 12 edges).** Its weights are decimals. Decide whether it becomes a test fixture, a shipped template, or both, and how its weights snap to the 3 strength levels.

## Scope (library)
- **Extend `causal_paths`** (signature and output stay backwards-compatible; new keys only), or add `causal_path_diagnostics`. Decide which in review. Per path:
  - `score` (decision 2);
  - `bottleneck_edge` (decision 6);
  - `delay_profile` (decision 4);
  - `min_confidence`.
- **Result-level fields:**
  - `contradictory`: both + and − paths exist (already derivable from `counts`; make it explicit);
  - `strongest_positive` and `strongest_negative`;
  - `redundancy`: edge-disjoint and node-disjoint path counts (`nx.edge_disjoint_paths` / `node_disjoint_paths`).
- **New `path_sensitivity(isa, source, target, *, n_draws, seed, …)`**, built on the existing Monte-Carlo and multi-rater machinery (`uncertainty_scores`, `bayesian_contested`, the rating Dirichlet). Per path it returns `rank_probability`, `polarity_probability` and `fragile_edges`, the edges whose perturbation most often changes the top path. Perturbations:
  - edge dropout;
  - a sign flip for contested edges;
  - a strength draw from the ratings.
- **Note interpretive rule:** report the strongest benefit path, the strongest counter-path, and the edge whose uncertainty most changes their ranking.

## Scope (app)
- **Panel:** `sespy_app/modules/analysis_metrics.py` (the Causal Paths section; `causal_paths` is called at line 465 in 1.0.1). Add columns: score, bottleneck, delay, confidence. Add a "strongest + / strongest −" summary, a contradictory-routes notice and a "Sensitivity" run (background task if slow).
- **Export:** CSV of the full path list (note P10).
- **MosaicSES embeds this panel.** `mosaicses-split-gate` (`origin/main`) loads `modules.analysis_metrics` (`sespy_ui.py:48`) and mounts the Network Metrics nav panel (`compartments.py:190`, server at `:383`). So `analysis_metrics_server`'s signature must not change, and the MosaicSES suite gates the release. Check `tests/test_compartments_module.py` for the pinned parameter set.

## Acceptance (from note §6.2, adapted)
- **P1:** compound polarity equals the product of edge signs. Covered in 1.18.0 by `test_network.py::test_causal_paths_diamond_polarity`; keep it.
- **P2:** simple paths have no repeated node and respect max_length. Covered in 1.18.0 by `test_network.py::test_causal_paths_cycles_yield_simple_paths_only`; check that a max_length test exists, and add one if not.
- **New:**
  - the score is monotone in weights and length;
  - the bottleneck is the minimum edge;
  - redundancy is correct on fixtures;
  - `path_sensitivity` is reproducible for a seed;
  - dropping the only path gives `rank_probability` 0 (cf. P8).
- **No NaN or Infinity** for missing strength: the fallback is `medium`, as `STRENGTH_LINK.get(…, medium)` already does (cf. P7).

## Later (not this spec)
- `compare_interventions`: overlaps roadmap P7b "Compare" and P8 Scenario Builder (`sespy-roadmap/docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md`).
- Spatial leakage (note P2 tier).
- Edge evidence fields (decision 5).
