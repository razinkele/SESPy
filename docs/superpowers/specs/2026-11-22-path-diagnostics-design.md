# Causal path diagnostics and path sensitivity — design

Date: 2026-11-22. Status: **decisions taken 2026-11-22**; plan next.
Version: library 1.20.0, app 1.2.0 (after the live 1.19.0 / 1.1.0).
R parity: **SESPy-first**. R (`SESToolbox/MarineSABRES_SES_Shiny/functions/network_analysis.R`) has `find_pathways` (line 266) and `find_all_paths(nodes, edges, from_id, to_id, max_length = 10)` (line 1271), which return plain node-id paths with no polarity. A grep found no callers of either outside tests. R has no path scoring, bottleneck reporting or path sensitivity.

## Source
- `docs/Marine_intervention_causal_pathways_and_propagation_development_note.docx`, a Copilot-generated note dated 2026-11-21. **It is not in git and was not synced to this laptop on 2026-11-22.** It was read from the online OneDrive copy (`SESPy/docs/`), and a duplicate sits in `Documents/Copilot/Created/`. Whether to commit it is the user's call. Sections used: §2 (paths), §5.2 (`causal_paths` and `path_sensitivity` return fields), §6.2 (P1, P2, P7, P8, P10), Appendix A.
- **Why the note overlaps with shipped work.** Its basis (Appendix C) is `LITERATURE/proposed-issues.md`, written before #16 (`causal_paths`, shipped 2026-08-16) and before #17/#19–#21 (diffusion). Only what is genuinely new is specified here.

## Decisions (user, 2026-11-22)
1. **Strength to weight: `bayes.STRENGTH_LINK`** (weak 0.30, medium 0.55, strong 0.80). A missing or unknown strength falls back to `medium`, as `STRENGTH_LINK.get(…, medium)` already does. No third mapping. Import the constant; never copy its values.
2. **Path score:**
   - formula `score = Π w_e · exp(−λ · (L − 1))` with **λ = 0.2, fixed** (a module constant `PATH_SCORE_LAMBDA = 0.2`, not user-settable);
   - `L` is the path's edge count, so a single strong edge scores 0.80;
   - `causal_paths` **sorts its rows by score, descending**, with ties broken by the old key (length, then path), so equal-score order is unchanged;
   - the panel shows score and length as columns.
3. **Ranking on a truncated set: score the enumerated set; no best-first search.**
   - **Probe (2026-11-22):** Caribbean template (78 nodes, 140 edges), 16 source/target pairs (top-4 out-degree × top-4 in-degree).
     - `nx.shortest_simple_paths` with cost `−log w + λ` hit a 30 s cap on **every** pair: it has no length cutoff, so it walks thousands of over-long paths.
     - `causal_paths(max_length=8, max_paths=100)` enumerated every path (≤ 41, never truncated) in about 0.01 s per pair, and the strongest path was always in its set.
     - Probe script: `docs/superpowers/specs/path-diagnostics-probes/probe_bestfirst.py` (run with PYTHONPATH at a sespy checkout; argument = that checkout).
   - **Rule:** when `truncated` is True, the score order covers only the paths found. The result and the panel must say so: "ranked among the first {n} paths found; raise the path limit for a complete ranking". `strongest_positive` / `strongest_negative` carry the same caveat through `truncated`.
4. **Delay per path: counts per level.** `delay_profile = {"immediate": i, "short": s, "long": l}` from `Connection.delay` (`constants.DELAY_LEVELS`). An unknown delay counts as `immediate`, matching the existing default. No step numbers are invented.
5. **Edge evidence fields: out of scope.** They need a schema bump and are decided with SESPy#41. "Evidence" here means the existing `confidence` (and `min_confidence` per path).
6. **Bottleneck: the weakest edge, ties broken by the lowest `confidence`**, then by the edge's position on the path (first wins). `bottleneck_edge = {"source", "target", "strength", "confidence"}`. One edge per path.
7. **The note's worked example: a test fixture only, not a shipped template.**
   - It is 10 nodes and 12 edges, with weights snapped to strength levels: w < 0.45 → weak, w < 0.70 → medium, otherwise strong.
   - Pin its expected ranking, bottlenecks, delay profiles and redundancy in library tests.
   - The note is not in git, so transcribe the example into the fixture file with a comment naming its source section.
8. **API shape: extend `causal_paths`, adding new keys only.**
   - The signature is unchanged.
   - Existing keys (`path`, `length`, `polarity`, `counts`, `truncated`) keep their meaning; only the row order changes (decision 2).
   - Callers:
     - Nid4Ocean (`ses_boolean.py:250`) re-sorts by length itself, so it is unaffected;
     - the app panel (`analysis_metrics.py:465`).
   - The empty shape gains the new result-level keys. `tests/test_network.py::_EMPTY_PATHS` and any `==` comparison against it must be updated, and the CHANGELOG must say so.
9. **`path_sensitivity`: same spec, a second task set in the same plan.** Diagnostics ship first; sensitivity is the later tasks. The app runs it as a background task with the generation-counter and stale-run guard pattern from sespy-app 1.1.0 (`analysis_boolean.py`).

## Scope (library)
- **Extend `causal_paths`** (decision 8: signature unchanged, new keys only, rows sorted by score). Per path:
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
