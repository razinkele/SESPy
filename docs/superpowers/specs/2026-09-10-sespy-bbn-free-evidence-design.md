# Path-set BBN: free evidence and path attribution — design

**Origin:** owner request 2026-09-10 ("continue developing bayesian
analysis") after v1.10.0 shipped both options of the
2026-09-08 Bayesian design. The owner picked, from four candidate
directions, "free evidence + path attribution" for the path-set belief
network (Option B), and then chose *solo-path effect* as the attribution
semantics and *presets plus extra pickers* as the evidence UI.

**Status:** design approved in conversation 2026-09-10; revised 2026-09-11
after a three-lens adversarial review (5 confirmed findings folded in:
evidence pickers get their own output, None-safe picker reads, conflict
check before the pgmpy import, golden e2e values, path-table tie order).
Implemented as v1.11.0 on 2026-09-11 (plan
`docs/superpowers/plans/2026-09-11-bbn-free-evidence.md`); two sentences
amended after the final review to match what shipped (e2e picker-clear
step, path-column width).

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
| 4 | The pickers live in their own `output_ui`, not inside `bbn_controls` (review 2026-09-11) | `bbn_controls` renders the source/target selects and deliberately reads them under `isolate()` so a pick never re-renders the select being used. Picker choices depend on the pair, so they must be a separate output that reacts to the pair. |

---

## Library (`sespy/bayes.py`)

All additions are pure except the two that build pgmpy models, which import
pgmpy lazily and raise `BayesUnavailable` exactly like `build_path_bbn`.

```python
def model_from_dag(info: dict):
    """pgmpy DiscreteBayesianNetwork over a path_set_dag result (or any dict
    with the same "nodes"/"edges" shape). Parentless nodes get P(high) = 0.5;
    every other CPT is noisy-OR over its in-edges via noisy_or_p_high. This
    is the body of today's build_path_bbn, factored so the pgmpy
    column-order comment and the CPT derivation live in one place and so a
    caller that already holds `info` (the worker, attribute_paths) need not
    enumerate paths twice. Returns None when info has no nodes. Raises
    BayesUnavailable when pgmpy is missing.
    build_path_bbn(isa, s, t) == (model_from_dag(info), info) with
    info = path_set_dag(isa, s, t) — behaviourally unchanged; the CPD values
    on the sample pair D001→GB01 are asserted against hard-coded rows."""

def merge_evidence(preset: dict[str, int], high, low, nodes: list[str]) -> dict:
    """Pure. `high`/`low` are any iterable of ids or None (a multi-select
    with nothing chosen is None in Shiny). Returns
    {"evidence": {id: 0|1}, "ignored": [ids], "conflicts": [ids]}.
    Order of rules, per id:
    1. not in `nodes` → `ignored` (outside the path set: not part of the
       question) and dropped — checked first, so an unknown id is never a
       conflict;
    2. in both `high` and `low` → `conflicts`;
    3. in a picker with the opposite state to `preset` → `conflicts`
       (the source and target are in `nodes`, so naming them in a picker
       reaches this rule; agreeing with the preset is not a conflict);
    4. otherwise merged, preset first.
    All three lists are sorted and deduplicated. Any conflict means the
    caller must not run inference."""

def focus_node(source: str, target: str, evidence: dict[str, int]) -> str | None:
    """Pure. The node whose posterior the summary and the attribution are
    about: target unless the target is in evidence, then source; None when
    both are in evidence (no focus line, no attribution)."""

def attribute_paths(info: dict, evidence: dict[str, int], focus: str) -> list[dict]:
    """Solo-path effect. Precondition: focus ∉ evidence (focus_node
    guarantees it; ValueError otherwise). For each row of info["paths"]
    (the routes still intact after cuts) build a chain model with
    model_from_dag over that route's edges only, restrict `evidence` to the
    route's nodes, and query the focus node. Returns rows
      {"path": [ids], "length": int, "polarity": "+"|"-"|"0",
       "baseline": float, "p_high": float, "delta": float}
    sorted by (-round(|delta|, 9), path) — the explicit rounding makes the
    lexicographic tiebreak deterministic when two routes share a prefix and
    tie (D001→GB01 does: both routes give −0.0301). `baseline` is the
    chain's own no-evidence marginal and differs from the joint baseline.
    Empty list when info has no paths. Values are computed on the chain
    alone and DO NOT sum to the joint delta of query_path_bbn — the
    docstring and the UI legend both say so. Deterministic."""
```

`query_path_bbn`, `path_set_dag`, `link_probability`, `noisy_or_p_high` and
`LEAK` / `STRENGTH_LINK` are unchanged.

---

## UI (`sespy/modules/analysis_intervention.py`)

### Sidebar

`bbn_controls` is untouched. A new `ui.output_ui("bbn_evidence_controls")`
is placed directly after it (before the direction radio):

- Its render reads `event_bus.isa_change`, `input.bbn_source()` and
  `input.bbn_target()` **reactively** (each in a try/except; a missing input
  renders nothing), computes `path_set_dag(isa, source, target)["nodes"]`
  minus the pair, and renders
  `ui.input_selectize("bbn_high", t("bbn.also_high"), choices, multiple=True)`
  and `ui.input_selectize("bbn_low", t("bbn.also_low"), choices, multiple=True)`
  with `choices` labelled `id · label`. Previous selections are restored
  from `input.bbn_high()` / `input.bbn_low()` under `reactive.isolate()`,
  tolerating None, filtered to the new choices.
- `path_set_dag` is networkx only and bounded by `max_paths` / `max_length`;
  measured 2026-09-11 over every ordered pair of all five shipped projects
  (sample plus four templates, up to 19 nodes / 22 edges): worst 3 ms. It
  runs in the render.
- When the pair has no path the output renders a single muted line
  (`bbn.no_path`) and no pickers (`input_selectize` has no disabled
  parameter). The worker then reports `bbn.no_path` as today.
- Both pickers join `_invalidate_bbn` (rule: invalidate on every feeding
  input), read inside try/except like the others.

### Worker

`_run_bbn` reads the pickers inside its existing try/except and coerces
each with the `chosen_ids` pattern (`list(v) if v else []`) before handing
them to `_bbn_task`. `_bbn_work(isa, src, tgt, direction, high, low)` keeps
the threading and generation-counter discipline and runs, in order:

1. `info = path_set_dag(isa, src, tgt)`; no nodes → `{"error": "bbn.no_path"}`.
2. `preset = {src: 1}` or `{tgt: 1}`;
   `m = merge_evidence(preset, high, low, info["nodes"])`.
   Conflicts → `{"error": "bbn.conflict", "ids": m["conflicts"]}`. This
   happens **before** the pgmpy import, so a conflict is reported instantly
   even on a cold server.
3. `model = model_from_dag(info)` (catch `BayesUnavailable` →
   `{"error": "bbn.unavailable"}`).
4. `r = query_path_bbn(model, info, m["evidence"])`;
   `r["ignored"] = m["ignored"]`; `r["focus"] = focus_node(src, tgt, m["evidence"])`;
   `r["paths"] = attribute_paths(info, m["evidence"], r["focus"])` if the
   focus is not None else `[]`; `r["source"], r["target"] = src, tgt`.

### Main panel

- `bbn_summary` error branch: `t(r["error"], ids=", ".join(r.get("ids", [])))`
  — `bbn.conflict` uses `{ids}`; the other error keys have no placeholder
  and ignore the kwarg. Conflict renders with class `text-danger`.
- The focus line uses `r["focus"]` instead of today's inline rule at
  line 521; when it is None the line is omitted.
- New evidence line: `bbn.evidence` with `{items}` = comma-joined
  `f"{id} {t('bbn.high' | 'bbn.low')}"` over `r["evidence"]` in sorted id
  order (always present: the preset is evidence too).
- When `r["ignored"]` is non-empty, a muted `bbn.ignored` line with `{ids}`.
- Under the node table: `ui.h5(t("bbn.paths_title"))`, a muted legend
  `bbn.paths_legend` ("Each row applies the evidence along that route
  alone. Solo baselines are the route's own no-evidence values; solo
  changes do not add up to the joint change above."), and
  `ui.output_data_frame("bbn_paths")` with columns
  `path` (labels joined with " → "), `length`, `polarity`,
  `solo baseline`, `solo posterior`, `solo delta` (3 decimals). Same guard
  as `bbn_table`: empty frame unless the result is a dict without
  `"error"`; also empty when `r["paths"]` is `[]`. The populated frame is
  returned as `render.DataGrid(df, styles=[{"cols": [0], "style":
  {"min-width": "14rem"}}])` so the path column does not wrap to ten
  lines per row (added 2026-09-11 after the manual capture exposed it).

### i18n, docs, screenshots

- `sespy/translations/core.json`, all nine languages, inserted with the
  other `bbn.*` keys: `bbn.also_high`, `bbn.also_low`, `bbn.evidence`
  (`{items}`), `bbn.ignored` (`{ids}`), `bbn.conflict` (`{ids}`),
  `bbn.paths_title`, `bbn.paths_legend`, `bbn.high`, `bbn.low`.
  Data-frame column headers stay plain English, as `bbn_table` does today.
  `tests/test_i18n.py::test_bbn_keys_present` gains the nine keys, and a
  placeholder-consistency check across languages for the three keys with
  placeholders (pattern: `test_governance_concentration_placeholders_match_across_languages`).
- `docs/MANUAL.md`: section 19 controls list gains "Also high", "Also low";
  section 43 gains an "Extra evidence" paragraph (merge rules, ignored,
  conflicts) and a "Per-route effect" paragraph with the does-not-add-up
  caveat, referencing a new screenshot `docs/screenshots/intervention_bbn.png`.
  Bump the manual version line to 1.11.0.
- `tests/make_docs_screenshots.py`: a new capture `intervention_bbn.png`
  taken after a forward run D001→GB01 with MPF1 low, scrolled so the BBN
  summary and both tables are in view (reuse the cascade-block scroll
  helper pattern at ~line 345). Budget: the existing 65 s cold-import wait.

---

## Testing

Unit (`tests/test_bayes.py`; pgmpy tests keep `@needs_pgmpy`):

- `model_from_dag` refactor: the CPD values for every node of
  `path_set_dag(sample, "D001", "GB01")` equal hard-coded rows captured
  from the v1.10.0 builder before the refactor (the plan's first step
  records them); `build_path_bbn` still returns `(model, info)`.
- `merge_evidence`: plain merge; None pickers; ids outside `nodes` →
  ignored (and never conflicts); same id in both pickers → conflict; picker
  contradicting the preset → conflict; picker agreeing with the preset → no
  conflict; output lists sorted and deduplicated.
- `focus_node`: four cases (neither, target only, source only, both).
- `attribute_paths` on D001→GB01 forward: two rows, both solo deltas
  negative and equal at −0.030 (3 dp), ordered
  `[..., "ES01", "GB01"]` before `[..., "ES03", "GB01"]` by the path
  tiebreak; each row's path matches a `path_set_dag` route; the joint
  delta from `query_path_bbn` is no larger in magnitude than the sum of the
  solo deltas (documents sub-additivity); ValueError when focus ∈ evidence;
  empty info gives `[]`; `BayesUnavailable` when pgmpy is monkeypatched
  away.
- Three-node chain fixture A→B→C with `{A: 1, B: 0}`: P(C high) is below
  the forward-only value; the same on the sample with MPF1 low gives a
  GB01 delta of −0.28 (2 dp) against −0.05 for forward only (the e2e
  goldens).

E2E (`tests/test_intervention_e2e.py`, id-scoped selectors only). Insert
the new steps **after** the existing forward-run assertions and **before**
the direction-change invalidation step, so the preset is still forward:

- Assert `#intervention-bbn_paths table tbody tr` count is 2 and the
  summary target line contains `(-0.05)`.
- Set MPF1 low via the selectize widget, falling back to
  `Shiny.setInputValue('intervention-bbn_low', ['MPF1'], {priority: 'event'})`
  (the make_docs_screenshots pattern); wait for "not computed"
  (invalidation); click run; wait until the summary contains "Evidence";
  assert it names `MPF1` and the target line contains `(-0.28)`.
- Set MPF1 high as well; wait for "not computed"; click run; wait until
  the summary contains the conflict text (wait predicate written for that
  string, not for "causal paths"); assert `MPF1` appears in it.
- Clear both pickers (setInputValue `[]`), wait for "not computed", run
  again and wait for the "2 causal paths" summary, then the existing
  direction-change step runs unchanged on a genuinely computed result
  (amended 2026-09-11 after the final review: clearing alone already
  invalidates, which made that step's assertion tautological).
- Cold-server warm-up flake (memory) applies: the first two hand runs may
  fail; the gate runner is the authority.

Gate: full unit suite + full e2e (never `-k "not e2e"`), nothing heavy
running concurrently. Then release v1.11.0: version bump, screenshots,
deploy, verify_live, re-check MosaicSES.

---

## Out of scope

Edge-ablation attribution, a "custom" preset that drops the source/target
evidence, Shapley-style exact decompositions, and any change to the CPT
derivation or the stored project. Each would be a separate design.
