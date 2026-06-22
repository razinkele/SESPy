# SESPy Quadrant Median-Split Toggle (QSEM follow-up) — Design

Date: 2026-06-22
Status: **Draft** (spec review gate)

**Context.** Follow-up to improvement **A** (Factor Quadrant, `9be151b`). The
quadrant splits each axis at its **mean** (`influence_dependence`,
`network.py:194`). A's review noted that on hub-skewed graphs the mean is pulled
up by one high-degree node, pushing the long tail below it into
`reactive`/`buffering` and hiding secondary leverage points — and deferred a
**median split** (more robust on skewed data) and a **data-triggered skew
warning**. This chunk adds both. Mean stays the default; median is the opt-in.

## 1. Goal & scope

### 1.1 In scope
- `influence_dependence(isa, *, split="mean")` — a `"mean"|"median"` keyword
  selecting the per-axis cross-hair statistic. Default `"mean"` keeps every
  existing caller/test unchanged.
- A shared `axis_threshold(values, split)` helper used by BOTH the classifier and
  the plot's cross-hairs, so they can never disagree.
- `influence_skew(isa) -> bool` — true when the influence distribution is
  hub-skewed (`max > k·median` on non-zero nodes, k=3).
- Quadrant module: a sidebar mean/median control; the plot's cross-hairs follow
  the chosen split; a skew-warning caption when skewed and on mean.
- 4 i18n keys × 9 languages; unit + e2e tests.

### 1.2 Out of scope
- No data-model / schema change. No `PROJECT_SCHEMA_VERSION` bump.
- No change to the classification *rule* (`>= threshold` = high side), the
  degeneracy guard, the quadrant labels, or the return shape of
  `influence_dependence`.
- No third split option (no configurable numeric threshold) — mean/median only.
- No change to any other analysis module.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Default split | `"mean"` | Backward-compatible; mean preserves "above-average influence" and a sparse Active quadrant when drivers are genuinely few. |
| Median for even N | `statistics.median` (averages the two middle values) | Standard; no new convention. |
| Tie at threshold | `>= threshold` = high side (unchanged) | Identical rule for mean and median; a node exactly at the median lands high, deterministic. |
| Threshold sharing | one `axis_threshold(values, split)` helper used by classifier AND plot | The plot currently recomputes the mean itself (`analysis_quadrant.py:99-100,116-117`); without sharing, a median classification would draw mean cross-hairs. One definition → always consistent. |
| Skew predicate | **strict** `max(v) > 3 · median(v)` over **non-zero** influence values; false if <2 non-zero | A single hub more than 3× the typical non-zero node is the case where mean misleads. Strict `>` (so `max == 3·median` is NOT skewed). Non-zero-only avoids a zero-inflated median. |
| Skew warning visibility | shown only when `influence_skew` is true **and** `split == "mean"` | The warning ("consider median") is only actionable on mean; once you've switched to median it's addressed — no nagging. |

## 2. No data-model change
`data_structure.py` untouched. The toggle is a UI input + a pure-function
keyword; nothing is persisted. No schema bump.

## 3. Pure layer (`sespy/network.py`)

### 3.1 `axis_threshold` (new)
```python
def axis_threshold(values: list[float], split: str) -> float:
    """Cross-hair statistic for one quadrant axis. 'mean' -> arithmetic mean;
    'median' -> median (statistics.median; averages the two middle values for
    even N). Used by BOTH influence_dependence (classification) and the quadrant
    plot (cross-hair lines) so they always agree. Assumes a non-empty list (the
    callers guard the empty-graph case first)."""
    import statistics
    return statistics.median(values) if split == "median" else statistics.mean(values)
```

### 3.2 Shared axis-sums helper (refactor, no behaviour change)
The Σ-edge logic in `influence_dependence` (build `weight_by_pair` with dedup +
self-loop skip; accumulate `influence`/`dependence`) is factored into a private
`_axis_sums(isa) -> tuple[dict[str, float], dict[str, float], dict[tuple[str,str], float]]`
returning `(influence, dependence, weight_by_pair)`. Both `influence_dependence`
and `influence_skew` call it — one definition of the per-node sums, no
duplication. **The 3rd element (`weight_by_pair`) is returned so
`influence_dependence` keeps its exact existing `not weight_by_pair` degeneracy
check verbatim** (don't drop it). `influence_skew` uses only the first element.
Pure refactor: the existing `influence_dependence` behaviour is identical
(verified by its 8 existing tests).

### 3.3 `influence_dependence` (extend signature)
Add `*, split: str = "mean"`. Build the sums via `_axis_sums(isa)`. **Keep the
degeneracy guard exactly as-is** — it still computes `mean_inf`/`mean_dep` and
`_variance(...)` about the **mean** and returns `undetermined` on
`not weight_by_pair` or zero-variance. The split ONLY changes the
**classification cross-hair**: add `thr_inf = axis_threshold(list(influence.values()),
split)` / `thr_dep = axis_threshold(list(dependence.values()), split)` and use
`thr_*` (not `mean_*`) in the `i >= thr_inf` / `d >= thr_dep` comparison. Do NOT
route the split into `_variance`/the guard (that would be the trap — the variance
guard centers on the mean by design; for uniform data mean==median so the guard
is split-independent anyway, but keep it on the mean explicitly to avoid
ambiguity). The `undetermined` state and the `{node: {influence, dependence,
quadrant}}` return shape are unchanged.

### 3.4 `influence_skew` (new)
```python
def influence_skew(isa: IsaData, *, k: float = 3.0) -> bool:
    """True when influence is hub-skewed: max(v) > k * median(v) over the
    non-zero influence values. False when there are <2 non-zero values (no
    skew to speak of). Pure; never raises."""
```
`influence, _, _ = _axis_sums(isa)`; `nz = [v for v in influence.values() if v > 0]`;
return `False` if `len(nz) < 2`; else **strict** `max(nz) > k * statistics.median(nz)`.

## 4. Quadrant module (`sespy/modules/analysis_quadrant.py`)
- **Sidebar:** add `ui.input_radio_buttons("split", t("quadrant.split"),
  {"mean": t("quadrant.split_mean"), "median": t("quadrant.split_median")},
  selected="mean", inline=True)` (the sidebar currently has only the About blurb).
- **`rows()` calc:** `influence_dependence(project_data.get().isa_data,
  split=input.split())`.
- **Plot cross-hairs:** replace the inline `mean_inf`/`mean_dep` (lines 99-100)
  with `thr_inf = net_analysis.axis_threshold(infl, input.split())` /
  `thr_dep = net_analysis.axis_threshold(dep, input.split())`; the `axvline`/
  `axhline` use `thr_dep`/`thr_inf`. (Rename the locals to `thr_*` for accuracy.)
- **Skew caption:** add `ui.output_ui("skew_caption")` in the main area
  **immediately after `output_plot("quadrant_plot", ...)` and before the
  `ui.tags.hr()`** that precedes the table. Server:
  ```python
  @output
  @render.ui
  def skew_caption():
      event_bus.isa_change.get()                      # react to data changes
      isa = project_data.get().isa_data
      if input.split() == "mean" and net_analysis.influence_skew(isa):
          return ui.tags.small(t("quadrant.skew_warning"), class_="text-muted")
      return ui.TagList()                             # empty otherwise
  ```
  It reacts to both the split radio (`input.split()`) and data edits
  (`event_bus.isa_change`). Shown only on mean + skewed; empty otherwise.

## 5. i18n (`sespy/translations/core.json`, 9 languages)
New keys: `quadrant.split` ("Cross-hair split"), `quadrant.split_mean` ("Mean"),
`quadrant.split_median` ("Median"), `quadrant.skew_warning` ("Distribution is
hub-skewed — consider the median split"). All 9 languages
(`tests/test_i18n.py` fails on English-only).

## 6. Edge cases
- **Empty graph** → `influence_dependence` returns `{}` before any threshold
  call; the plot's existing `if not data` guard fires; `influence_skew` returns
  `False` (no non-zero values). No `statistics.mean([])` crash.
- **Degenerate / uniform** → the existing zero-variance guard returns
  `undetermined` regardless of split (median == mean == the uniform value).
- **Even N median** → `statistics.median` averages the two middle values;
  classification still `>= threshold`.
- **All-equal influence** → not skewed (`max == median`, `max > 3·median` false).
- **Backward compat** → default `split="mean"`; existing quadrant unit/e2e tests
  and any other behaviour are unchanged.

## 7. Testing
1. **Unit (`tests/test_network.py`, extend; pure):**
   - `axis_threshold([1,2,3,4], "mean") == 2.5`; `("median") == 2.5`;
     `axis_threshold([1,2,3,100], "median") == 2.5` while `"mean" == 26.5`
     (median robust to the outlier).
   - **Default-sample split test (pins the e2e's premise):** with
     `isa = load_sample("data/sample_ses.json")`,
     `influence_dependence(isa, split="mean")` vs `split="median"` differ for
     **≥1 node**, and specifically `D001` is `"buffering"` under mean and
     `"active"` under median (empirically verified). This both proves the switch
     reclassifies and guards the e2e's premise against sample drift.
   - **No regression:** `influence_dependence(isa)` (default) ==
     `influence_dependence(isa, split="mean")` and matches the existing quadrant
     test expectations.
   - `influence_skew`: **True** on a constructed hub-skewed fixture (one node
     with out-weight ~5× several light tail nodes); **False** on a balanced
     fixture, on an empty graph, and at the **boundary** `max == 3·median`
     (strict `>`); **False** on the default sample (`max 23 ≯ 3·12`) — documents
     that the warning is conservative.
   - **Caption coverage note:** the skew caption is a thin `@render.ui` presenter
     fully determined by `influence_skew` + `input.split()=="mean"`; there is no
     Shiny module-server harness in this repo, so its appearance is covered by
     the `influence_skew` unit tests (the decision), not a separate render test —
     consistent with how the quadrant's empty-state captions are covered.
2. **e2e (`tests/test_quadrant_e2e.py`, extend):** build a per-row map
   `{ id-cell (`td:nth-child(2)`) : quadrant-cell (`td:last-child`) }` from the
   data_frame on the mean view (default `en` locale); toggle `#quadrant-split` to
   "median" (e.g. set the radio's "median" input and dispatch change), wait for
   the table to re-render, rebuild the map; assert **`map["D001"]` differs
   between the two views** (a *named* row, so a sample drift to a no-flip state
   fails loudly instead of vacuously). `id` is column 2, `quadrant` is the last
   column — keep both stable. The skew caption is NOT asserted here (the default
   sample isn't skew-flagged — see §7.1). Full gate via `python tests/run_e2e.py`.
3. **i18n:** `pytest tests/test_i18n.py` green (4 new keys × 9 langs).

## 8. Build order (for the plan)
1. `axis_threshold` + `influence_dependence` split param + `influence_skew` in
   `network.py` + unit tests (TDD).
2. 4 i18n keys (9 languages); `test_i18n.py` green.
3. Quadrant module: split radio + `rows()` split + plot `thr_*` cross-hairs +
   skew caption.
4. e2e (toggle changes a quadrant label) + full gate → merge → push.
