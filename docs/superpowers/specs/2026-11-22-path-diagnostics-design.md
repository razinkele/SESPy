# Causal path diagnostics and path sensitivity — design

Date: 2026-11-22. Status: **approved 2026-11-22** (user signed off all [proposal] items); plan next.
Version: proposed library 1.20.0, app 1.2.0 (decision 13).
R parity: **SESPy-first**. R (`SESToolbox/MarineSABRES_SES_Shiny/functions/network_analysis.R`) has `find_pathways` (line 266) and `find_all_paths(nodes, edges, from_id, to_id, max_length = 10)` (line 1271), which return plain node-id paths with no polarity. A grep found no callers of either outside tests. R has no path scoring, bottleneck reporting or path sensitivity.

## Source
- `docs/Marine_intervention_causal_pathways_and_propagation_development_note.docx`, a Copilot-generated note dated 2026-11-21. **It is not in git and was not synced to this laptop on 2026-11-22.** It was read from the online OneDrive copy (`SESPy/docs/`), and a duplicate sits in `Documents/Copilot/Created/`. Whether to commit it is the user's call. Sections used: §2 (paths), §5.2 (`causal_paths` and `path_sensitivity` return fields), §6.2 (P1, P2, P7, P8, P10), Appendix A.
- **Why the note overlaps with shipped work.** Its basis (Appendix C) is `LITERATURE/proposed-issues.md`, written before #16 (`causal_paths`, shipped 2026-08-16) and before #17/#19–#21 (diffusion). Only what is genuinely new is specified here.

## Decisions (2026-11-22)
Each decision is marked: **[user]** = answered by the user; **[proposal]** = Claude's proposal, approved by the user on 2026-11-22.

1. **[user] Strength to weight: `bayes.STRENGTH_LINK`** (weak 0.30, medium 0.55, strong 0.80).
   - A missing or unknown strength falls back to `medium`, as `STRENGTH_LINK.get(…, medium)` already does.
   - No third mapping. Import the constant; never copy its values.
2. **[user] Path score:** `score = Π w_e · exp(−λ · (L − 1))` with **λ = 0.2, fixed** (module constant `PATH_SCORE_LAMBDA = 0.2`, not user-settable). `L` is the path's edge count, so a single strong edge scores 0.80. `causal_paths` **sorts its rows by score, descending**, and the panel shows score and length as columns.
   - **[proposal] Exact ties.** Compute the product from per-level counts: `w_weak**n_weak * w_medium**n_medium * w_strong**n_strong`, multiplied in that fixed order. Two paths with the same strengths in a different order then get bit-identical scores. A product taken in path order can differ in the last bit and break ties unpredictably.
   - Equal scores fall back to the old key (length, then path). The sample-data test `test_causal_paths_sample_two_negative_sorted` (two paths, each with one strong and one medium edge on the differing stretch) therefore keeps its order.
3. **[proposal] Ranking on a truncated set: score the enumerated set; no best-first search.**
   - **Probe 1 (2026-11-22):** Caribbean template (78 nodes, 140 edges), 16 source/target pairs (top-4 out-degree × top-4 in-degree).
     - `nx.shortest_simple_paths` with cost `−log w + λ` hit a 30 s cap on **every** pair: it has no length cutoff, so it walks thousands of over-long paths.
     - `causal_paths(max_length=8, max_paths=100)` enumerated every path (≤ 41) in about 0.01 s.
   - **Probe 2:** all 12 templates under `sespy/templates`, 3,740 ordered pairs (all pairs, or a seeded sample of 400 per large template), at the panel's defaults (`max_length=8`, `max_paths=100`): **0 truncated**. Worst pair 0.017 s.
   - Scripts are in `docs/superpowers/specs/path-diagnostics-probes/` (`probe_bestfirst.py`, `probe_paths_templates.py`; run with PYTHONPATH at a sespy checkout and that checkout as the argument).
   - **Rule:** truncation does not occur on shipped models but can on dense user models. When `truncated` is True, the score order covers only the paths found. The result and the panel must say so: "Ranked among the first {n} paths found; a stronger path may exist beyond them." (*erratum, plan writing: the panel has no path-limit control, so it cannot tell users to raise one*). `strongest_positive` / `strongest_negative` carry the same caveat through `truncated`.
4. **[user] Delay per path: counts per level.** `delay_profile = {"immediate": i, "short": s, "long": l}`, taken from `Connection.delay` (`constants.DELAY_LEVELS`).
   - **[proposal, amended at plan writing]** Delays are read through `constants.normalize_delay` (empty → immediate, numeric 0 → immediate, other numbers and free text → short, exact level names kept), the library's canonical rule. *Erratum: the approved text said an unknown delay counts as immediate; reusing the existing normaliser avoids a second rule.*
5. **[proposal] Edge evidence fields: out of scope.** They need a schema bump and are decided with SESPy#41. "Evidence" here means the existing `confidence` (`min_confidence` per path).
6. **[user] Bottleneck: the weakest edge, ties broken by the lowest `confidence`.**
   - **[proposal]** Then by position on the path, first wins.
   - `bottleneck_edge = {"source", "target", "strength", "confidence"}`. One edge per path.
7. **[user] The note's worked example becomes a test fixture only.**
   - Source: the note's §1.2–1.3 (10 nodes, 12 edges); its §2.2–2.3 give the expected routes.
   - **[proposal] Snapping:** weight w < 0.45 → weak, w < 0.70 → medium, else strong. Delay step 1 → immediate, 2 → short, 3 → long. `confidence` = 3 everywhere, since the note gives none.
   - Snapped, the two I→F routes score 0.101 (I→C→D→S→N→F, +) and 0.040 (I→X→S→N→F, −), which keeps the note's ranking.
   - Transcribe the example into the fixture with a comment naming the note section, because the note is not in git.
8. **[user] API shape: extend `causal_paths`, adding new keys only.**
   - The signature is unchanged. Existing keys (`path`, `length`, `polarity`, `counts`, `truncated`) keep their meaning; only the row order changes (decision 2).
   - Callers:
     - Nid4Ocean (`ses_boolean.py:250`) re-sorts by length itself, so it is unaffected;
     - the app panel (`analysis_metrics.py:465`, with default limits), whose e2e asserts counts and labels but not row order.
   - The empty shape gains the new result-level keys. `tests/test_network.py::_EMPTY_PATHS` and any `==` comparison against it must be updated, and the CHANGELOG must say so.
   - **[proposal] Duplicate connections:** today the last connection on a (source, target) pair wins for polarity. Strength, confidence and delay must come from that **same** connection. No shipped template has a duplicate pair.
9. **[user] `path_sensitivity`: same spec, a second task set in the same plan.** Diagnostics ship first. The app runs it as a background task with the generation-counter and stale-run guard pattern from sespy-app 1.1.0 (`analysis_boolean.py`).
10. **[proposal] `path_sensitivity` model: reuse the shipped Monte-Carlo machinery and invent no new mapping.**
    - **Signature:** `path_sensitivity(isa, source, target, *, n_draws=500, seed=0, base=0.5, flip_mode="confidence", max_length=8, max_paths=100)`.
    - **Each draw** perturbs the graph with the existing `network._perturbed_connections(isa, base, rng, flip_mode)`:
      - **dropout:** drop probability `base·(5−confidence)/4`, so confidence 5 is never perturbed;
      - **sign flip:** flip probability by confidence, or by the rater posterior with `flip_mode="posterior"`;
      - **unrated edges** fall back to the confidence heuristic, as `uncertainty_scores` already does.
    - **Strength per draw (optional, off by default):** `draw_strength=False`. When True, a rated edge takes the strength of one uniformly drawn rating; unrated edges keep their stored strength.
    - **Per baseline path** (the unperturbed `causal_paths` rows):
      - `rank_probability`: the share of draws in which this path survives **with its baseline polarity** and is the top-scoring row of that polarity (a draw that flips the path's sign does not count towards it);
        - *Erratum (Task 2 review): when k rows of that polarity tie exactly on the draw's top score for it (`==`; scores are bit-exact by construction), each tied baseline path present with its baseline polarity gets 1/k credit, instead of the win going to the row that sorts first by node id. `rank ≤ polarity ≤ survival` still holds.*
      - `polarity_probability`: the share of draws in which the path survives with its baseline polarity;
      - `survival_probability`: the share of draws in which all its edges survive.
    - **Result level:** `fragile_edges`. *Precision added at plan writing.*
      - "The top changed" means the overall top row of the draw differs from the baseline top row in path **or** polarity, or the draw has no rows.
      - In those draws, count each edge **on a listed baseline path** that was dropped (no connection on that pair in the draw) or flipped (the winning connection's polarity differs from baseline).
      - Edges on no listed path are never counted, since a low-confidence edge elsewhere would otherwise dominate.
      - Share = count / n_draws. Return the top 5 by share, then by (source, target).
      - *Erratum (Task 2 review): share alone ranks edges by how often they drop, not by how much they matter (Caribbean W2→W6: an off-top-path edge ranked #2, and an edge whose change slightly lowers P(top changed) was listed). Each entry keeps `share` (same meaning) and gains `lift` = P(top changed | edge dropped or flipped) − P(top changed | edge intact), over the draws. An edge that never changes or always changes has no lift and is left out; so is any edge with lift ≤ 0. Sort by −lift, then −share, then (source, target); return the top 5. Entries are `{"source", "target", "share", "lift"}`, still only edges on listed baseline paths.*
    - **Probe 3:** 200 draws on the heaviest shipped pair (Caribbean W2→W6) took 1.4 s, so 500 draws is about 3.5 s. That is acceptable in a background task.
    - **Acceptance:** the same seed gives identical output. Dropping the only path gives `rank_probability` 0 for it in that draw (note P8). At `base=0` every probability is 0 or 1.
11. **[proposal] Redundancy semantics.** Count disjoint routes **greedily among the enumerated paths, strongest first**: take a path if it shares no edge (for `edge_disjoint`) or no interior node (for `node_disjoint`) with any path already taken.
    - This respects `max_length` and is deterministic.
    - It is a lower bound on the true maximum, so label it "disjoint routes among the paths listed".
    - **No route:** 0 and 0.
    - **Adjacent source and target:** the direct edge is a path with no interior node, so it counts towards both.
    - Not `nx.edge_disjoint_paths`: max-flow ignores `max_length` and can exceed the listed paths.
12. **[proposal] Strongest paths:** `strongest_positive` is the top-score path with polarity "+", and `strongest_negative` the top-score path with polarity "−". Ambiguous ("0") paths are never chosen; either key is `None` when that polarity has no path. `contradictory = counts["+"] > 0 and counts["-"] > 0`.
13. **[proposal] Versions:** library 1.20.0 and app 1.2.0, unless the 1.19.1 / 1.1.1 follow-up batch or SESPy#41 ships first, in which case take the next minor number.

## Scope (library)
- **Extend `causal_paths`** (decision 8: signature unchanged, new keys only, rows sorted by score). Per path:
  - `score` (decision 2);
  - `bottleneck_edge` (decision 6);
  - `delay_profile` (decision 4);
  - `min_confidence`.
- **Result-level fields:**
  - `contradictory`: both + and − paths exist (already derivable from `counts`; make it explicit);
  - `strongest_positive` and `strongest_negative`;
  - `redundancy`: `{"edge_disjoint", "node_disjoint"}`, counted greedily among the listed paths (decision 11).
- **New `path_sensitivity`**, defined in decision 10 (reuses `_perturbed_connections`; per path `rank_probability`, `polarity_probability`, `survival_probability`; result-level `fragile_edges`).
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
