# Path-set BBN: free evidence and path attribution — design

**Origin:** owner request 2026-09-10 ("continue developing bayesian
analysis") after v1.10.0 shipped both options of the
2026-09-08 Bayesian design. The owner picked, from four candidate
directions, "free evidence + path attribution" for the path-set belief
network (Option B), and then chose *solo-path effect* as the attribution
semantics and *presets plus extra pickers* as the evidence UI.

**Status:** design approved in conversation 2026-09-10. Implementation plan
not yet written.

---

## What this is

Two extensions of the existing path-set BBN block on the Intervention card.
Neither changes the model class, the CPT derivation, the stored project, or
the two existing query presets.

- **Free evidence.** Besides the forward / diagnostic preset, the user can
  mark any other node of the path set as *high* or *low*. All evidence is
  merged into one dict and answered by the same exact inference.
- **Path attribution.** For every surviving source→target path the table
  reports how much the evidence, applied along that route *alone*, moves
  the focus node. It answers "which route carries the effect?".

## Decisions (made by the owner, 2026-09-10)

| # | Decision | Rationale |
|---|---|---|
| 1 | Attribution = solo-path effect, not edge ablation | Noisy-OR is sub-additive and routes share edges, so no per-route decomposition sums to the joint delta. A chain built from one route alone is cheap (≤ 100 tiny chains), deterministic, and answers the question practitioners ask through the causal-path tracer. Edge ablation answers "which link", a different question; deferred. |
| 2 | Evidence UI = keep the forward / diagnostic radio as a preset and add two multi-select pickers ("also high", "also low") that merge into it | Existing workflow, e2e and manual text stay valid. "Source low" is not askable; nobody has asked for it. Conflicts are reported and block the run rather than being silently resolved. |
| 3 | Per-route numbers are labelled *solo* and carry a legend that they do not add up | Stakeholders will otherwise sum them and compare with the joint delta. |

---

## Library (`sespy/bayes.py`)

All additions are pure except the two that build pgmpy models, which import
pgmpy lazily and raise `BayesUnavailable` exactly like `build_path_bbn`.

```python
def _model_from_edges(nodes: list[str], edges: list[tuple[str, str, Connection]]):
    """pgmpy DiscreteBayesianNetwork over the given DAG. Parentless nodes get
    P(high) = 0.5; every other CPT is noisy-OR over its in-edges via
    noisy_or_p_high. This is the body of today's build_path_bbn, factored so
    the pgmpy column-order comment and the CPT derivation live in one place.
    build_path_bbn becomes path_set_dag + this call and is behaviourally
    unchanged (CPTs bit-identical, asserted in tests)."""

def merge_evidence(preset: dict[str, int], high: list[str], low: list[str],
                   nodes: list[str]) -> dict:
    """Pure. Returns {"evidence": {id: 0|1}, "ignored": [ids], "conflicts": [ids]}.
    - ids in `high`/`low` that are not in `nodes` go to `ignored` (outside the
      path set: not part of the question) and are dropped;
    - an id in both `high` and `low`, or in a picker with the opposite state
      to `preset`, goes to `conflicts`;
    - everything else merges, preset first. Lists are sorted and
      deduplicated. Any conflict means the caller must not run."""

def focus_node(source: str, target: str, evidence: dict[str, int]) -> str | None:
    """Pure. The node whose posterior the summary and the attribution are
    about: target unless the target is in evidence, then source; None when
    both are in evidence (no focus line, no attribution)."""

def attribute_paths(info: dict, evidence: dict[str, int], focus: str) -> list[dict]:
    """Solo-path effect. For each row of info["paths"] (the routes still
    intact after cuts) build a chain model over that route's edges with
    _model_from_edges, restrict `evidence` to the route's nodes, and query
    the focus node. Returns rows
      {"path": [ids], "length": int, "polarity": "+"|"-"|"0",
       "baseline": float, "p_high": float, "delta": float}
    sorted by (-|delta|, path). Routes on which the focus is itself in
    evidence report p_high = evidence value and delta 0 and are still
    listed. Empty list when info has no paths. Values are computed on the
    chain alone and DO NOT sum to the joint delta of query_path_bbn — the
    docstring and the UI legend both say so. Deterministic."""
```

`query_path_bbn`, `path_set_dag`, `link_probability`, `noisy_or_p_high` and
`LEAK` / `STRENGTH_LINK` are unchanged.

---

## UI (`sespy/modules/analysis_intervention.py`)

Sidebar, inside the existing `bbn_controls` output (so the new inputs get
the isolate()-restore treatment already there):

- `ui.input_selectize("bbn_high", t("bbn.also_high"), choices, multiple=True)`
  and `ui.input_selectize("bbn_low", t("bbn.also_low"), choices, multiple=True)`.
  `choices` are the nodes of `path_set_dag(isa, source, target)["nodes"]`
  minus the source and target, labelled `id · label`. `path_set_dag` is
  networkx only and bounded by `max_paths` / `max_length`, so it may run in
  the render; the plan measures it on the largest sample project and, if it
  exceeds ~50 ms, falls back to listing all elements and relying on
  `ignored`. The pickers render empty (disabled) when the pair has no path.
- The two pickers join `_invalidate_bbn` (rule: invalidate on every feeding
  input). Their selections are restored from `input.bbn_high()` /
  `input.bbn_low()` under `reactive.isolate()`, filtered to the new
  choices, exactly like the source/target selects.

Worker (`_bbn_work`, unchanged threading and generation-counter discipline):

1. `build_path_bbn` → unavailable / no-path errors as today.
2. `preset = {src: 1}` or `{tgt: 1}`; `m = merge_evidence(preset, high, low, info["nodes"])`.
   Conflicts → `{"error": "bbn.conflict", "ids": [...]}`; the summary renders
   the message with the ids and nothing else.
3. `r = query_path_bbn(model, info, m["evidence"])`; `r["ignored"] = m["ignored"]`;
   `r["focus"] = focus_node(src, tgt, m["evidence"])`;
   `r["paths"] = attribute_paths(info, m["evidence"], r["focus"])` when the
   focus is not None, else `[]`.

Main panel:

- `bbn_summary` uses `r["focus"]` instead of the inline rule at today's
  line 521; when it is None the target line is omitted. New lines: an
  evidence line ("Evidence: D001 high, A002 low" — ids joined, one
  `bbn.evidence` key with an `items` placeholder) and, when non-empty, a
  muted `bbn.ignored` line listing ids that were outside the path set.
- A new `ui.h5(t("bbn.paths_title"))`, a one-sentence muted legend
  `bbn.paths_legend` ("Each row applies the evidence along that route alone;
  solo values do not add up to the joint change above."), and
  `ui.output_data_frame("bbn_paths")` with columns
  `path` (labels joined with " → "), `length`, `polarity`,
  `solo baseline`, `solo posterior`, `solo delta` (3 decimals). Empty frame
  while not computed, on error, or when focus is None.

i18n (`sespy/translations/core.json`, all nine languages, inserted with the
other `bbn.*` keys): `bbn.also_high`, `bbn.also_low`, `bbn.evidence`,
`bbn.ignored`, `bbn.conflict`, `bbn.paths_title`, `bbn.paths_legend`,
`bbn.high`, `bbn.low`. Data-frame column headers stay plain English, as
`bbn_table` does today.
`tests/test_i18n.py` gains the keys in `test_bbn_keys_present` or a sibling.

Docs: `docs/MANUAL.md` sections 19 (controls list) and 43 (a short
"Extra evidence" and "Per-route effect" paragraph including the
does-not-add-up caveat). `tests/make_docs_screenshots.py` gains a dedicated
Intervention capture that scrolls the BBN block into view after a run —
the v1.10.0 plan deferred this. Bump the manual version line.

---

## Testing

Unit (`tests/test_bayes.py`):

- `_model_from_edges` refactor: CPD values for every node on the sample
  project pair D001→GB01 equal those of the pre-refactor builder (capture
  in the test by building through both code paths, or by hard-coding the
  known CPT rows).
- `merge_evidence`: plain merge; ids outside `nodes` → ignored; same id in
  both pickers → conflict; picker contradicting the preset → conflict; picker
  agreeing with the preset → no conflict; output lists sorted and
  deduplicated.
- `focus_node`: four cases (neither, target only, source only, both).
- `attribute_paths` on D001→GB01: two rows, both solo deltas negative,
  each row's path matches a `path_set_dag` route; on this fixture the joint
  delta from `query_path_bbn` is no larger in magnitude than the sum of the
  solo deltas (documents sub-additivity); a route on which the focus is in
  evidence gives delta 0; empty info gives `[]`; `BayesUnavailable` when
  pgmpy is monkeypatched away. pgmpy tests keep the `@needs_pgmpy` skip.
- Three-node chain fixture with intermediate evidence: evidence
  `{A: 1, B: 0}` lowers P(C high) below the forward-only value.

E2E (`tests/test_intervention_e2e.py`, id-scoped selectors only):

- After the existing forward run, assert `#intervention-bbn_paths` has 2
  rows.
- Select one intermediate node in `#intervention-bbn_low`, assert the
  result invalidates, re-run, assert the summary contains an "Evidence"
  line naming that node and that the delta text changed.
- Select the same node in `#intervention-bbn_high`, run, assert the
  conflict message appears.
- Existing assertions are untouched. Cold-server warm-up flake (memory)
  applies: the first two hand runs may fail; the gate runner is the
  authority.

Gate: full unit suite + full e2e (never `-k "not e2e"`), nothing heavy
running concurrently. Then release v1.11.0: version bump, screenshots,
deploy, verify_live, re-check MosaicSES.

---

## Out of scope

Edge-ablation attribution, a "custom" preset that drops the source/target
evidence, Shapley-style exact decompositions, and any change to the CPT
derivation or the stored project. Each would be a separate design.
