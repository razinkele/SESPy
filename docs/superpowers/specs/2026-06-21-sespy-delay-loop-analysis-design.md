# SESPy Delay-Aware Loop Analysis (QSEM time-delay surfacing, "B") — Design

Date: 2026-06-21
Status: **Draft** (spec review gate)

**Context.** Second improvement from the QSEM (Qualitative Systems Exploration
Model) comparison: surface the **time-delay** dimension. `Connection.delay`
already exists as a `str` field (`data_structure.py:101`, default `"immediate"`)
but is **analytically dead** — only the Excel importer ever reads it
(`excel_import.py:122`), the data-entry form can't set it, the sample carries
none, and no analysis consumes it. This chunk makes `delay` a first-class,
settable, 3-level field and surfaces it through the **Loop Analysis** module —
specifically flagging **delayed balancing loops as oscillating**, the classic
system-dynamics overshoot/oscillation signature.

This mirrors the just-shipped Factor Quadrant ("A") in spirit (reuse existing
structure, isolate pure logic, no schema bump) but, unlike A, must also **close
the capture gap**: nothing currently sets `delay` in-app, so the feature seeds
the data-entry form + the sample so the analysis has something to chew on.

## 1. Goal & scope

### 1.1 In scope
- `DELAY_LEVELS = ("immediate","short","long")` + `normalize_delay(raw)` in
  `sespy/constants.py`.
- `loop_has_delay(cycle, isa)` in `sespy/network.py`; extend `classify_loops` to
  emit `delayed: bool` and a mutually-exclusive `behavior` field
  (`reinforcing`/`balancing`/**`oscillating`**).
- Loop Analysis surfacing (`sespy/modules/analysis_loops.py`): Oscillating count
  in the summary, `behavior`/`delayed` table columns, narrative badge + delay
  chip, and **dashed delayed edges** in the rendered loop network.
- Capture: a `delay` `input_select` in the data-entry connection form
  (`isa_data_entry.py`) + a `delay` column in its connections table;
  `normalize_delay` applied on Excel import (`excel_import.py`).
- Seed `data/sample_ses.json`: mark one edge on a balancing loop `"short"` →
  a demonstrable oscillating loop.
- i18n keys (delay levels, "oscillating", "delayed", axis/column labels) × 9
  languages.
- Unit + e2e tests.

### 1.2 Out of scope
- **No data-model / schema change / `PROJECT_SCHEMA_VERSION` bump.**
  `Connection.delay` is already a `str`; we constrain its *values* via the UI
  vocabulary and `normalize_delay` on load — the dataclass is untouched.
- **Main CLD-module edge styling** (`cld_visualization.py`) — styling delayed
  edges in the *primary* CLD network is a separate surface ("B2"). This chunk
  styles delayed edges only in the **Loop Analysis** loop network, per the
  agreed scope.
- **A fourth "delayed-reinforcing" behavior category.** A delayed reinforcing
  loop keeps `behavior=reinforcing` and only carries the `delayed` flag
  (secondary badge + dashed styling). The SD signal there ("slower build") is
  weaker; a fourth bucket would dilute the oscillating headline.
- **Continuous/numeric lag values.** 3-level categorical only (no one hand-enters
  numeric lags in a participatory CLD).
- **Dynamic simulation of delays** (`dynamics.py` is untouched).

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Vocabulary | `immediate` / `short` / `long` (ordered) | Mirrors `strength`'s 3-level categorical; same `input_select` idiom; satisfies both the loop flag (delayed = short\|long) and graded edge styling. |
| "Delayed" predicate | `normalize_delay(c.delay) != "immediate"` | Single definition; short and long both count as delayed for the loop flag. |
| `normalize_delay(raw)` | empty/None/`"immediate"`→`immediate`; `"short"`→`short`; `"long"`→`long`; any other non-empty→`short` | Case-insensitive; legacy/Excel free-text ("lag","delayed","5y") lands safely as "delayed, magnitude unknown". |
| Behavior model | mutually exclusive `reinforcing` / `balancing` / `oscillating`; **oscillating = balancing AND delayed** (replaces balancing for those loops) | Three non-overlapping counts summing to total — no double-counting. Oscillating is the headline new state (overshoot signature). |
| `delayed` flag | separate boolean, orthogonal to `behavior` | Lets the UI count by `behavior` while independently driving dashed styling + the secondary "delay" badge (e.g. a delayed reinforcing loop). Two fields, two jobs. |
| Delayed reinforcing | `behavior=reinforcing`, `delayed=True` | No fourth category (see §1.2). |
| Placement | extend the existing **Loop Analysis** module | It already enumerates cycles + classifies R/B; delay surfacing is purely additive, no new graph traversal in the UI. |
| Delayed edge cue | vis.js `dashes: true` in `_build_loop_network` | One-line per-edge; immediate edges stay solid; polarity colour unchanged. |
| Sample seed | mark one edge on a balancing loop `"short"` | The default project is every user's first surface and every e2e's target; one seed documents-by-example AND gives the test a real assertion. Done-criterion: `classify_loops(sample)` yields ≥1 `oscillating`. |

## 2. No data-model change
`sespy/data_structure.py` is **not** modified. `Connection.delay: str = "immediate"`
already exists. We constrain values via the data-entry `input_select` and
`normalize_delay` (applied on Excel import and inside the delay predicate). No
`PROJECT_SCHEMA_VERSION` bump; legacy projects (no `delay` key) load with the
dataclass default and read as `immediate`.

## 3. Pure logic

### 3.1 `sespy/constants.py` (append)
```python
DELAY_LEVELS: tuple[str, ...] = ("immediate", "short", "long")

def normalize_delay(raw: object) -> str:
    """Map any stored/imported delay value to DELAY_LEVELS.
    empty/None/'immediate' -> 'immediate'; 'short'/'long' -> themselves
    (case-insensitive); any other non-empty value -> 'short' (delayed,
    magnitude unknown)."""
```
Algorithm: `s = str(raw).strip().lower()` (guard `None`/empty → `"immediate"`);
exact match to `short`/`long`/`immediate` returns that; anything else non-empty
→ `"short"`.

### 3.2 `sespy/network.py` (append + extend)
```python
def loop_has_delay(cycle: list[str], isa: IsaData) -> bool:
    """True if any edge traversed by `cycle` is delayed
    (normalize_delay(delay) != 'immediate'). Mirrors loop_polarity's
    edge-walk over (cycle[i], cycle[(i+1)%n])."""
```
Build a `{(source,target): delay}` lookup (parallel to `_edge_polarity_lookup`),
walk the cycle edges, return `True` on the first delayed edge.

**`classify_loops` gains two fields** per loop dict (keeping `id`, `length`,
`type`, `nodes`, `path` unchanged):
- `delayed: bool` = `loop_has_delay(cycle, isa)`
- `behavior: str` = `"oscillating"` if (`type == "Balancing"` and `delayed`)
  else `type.lower()` (`"reinforcing"` / `"balancing"`)

(`behavior` is lower-case to key i18n; the UI maps it to a display label.)

## 4. Loop Analysis surfacing (`sespy/modules/analysis_loops.py`)

All read the new fields from `classify_loops`; no new graph work in the module.

1. **Classification summary (sidebar).** Count by `behavior` into three
   mutually-exclusive buckets — **Reinforcing**, **Balancing**, **Oscillating** —
   each in its own colour (oscillating distinct, e.g. amber). Replaces today's
   2-count (Reinforcing/Balancing) summary.
2. **Loops table.** Add a `behavior` column (display label) and a `delayed`
   column (`✓`/`—`). Keep existing `type`, `length`, `path`.
3. **Loop narrative (selected loop).** Badge shows `behavior` (Oscillating in its
   colour); if `delayed and behavior != "oscillating"` (a delayed reinforcing
   loop), append a small **"delay"** chip.
4. **`loop_picker` choices.** Use `behavior` in the label
   (`L001 · Oscillating · len 4`).
5. **`_build_loop_network`.** For each edge, if `normalize_delay(delay) !=
   "immediate"`, render `dashes=True` and include the delay level in the edge
   `title` (tooltip, e.g. `"+ · short"`). Immediate edges unchanged.

## 5. Capture side

1. **Data-entry form (`isa_data_entry.py`).** Add `ui.input_select("new_delay",
   t("entry.delay"), DELAY_LEVEL_LABELS, selected="immediate")` into the
   connection-add `layout_columns` (refit `col_widths`, e.g. source/target/
   polarity/delay = 3/3/2/2 with the add button wrapping or `(3,3,2,2,2)`), and
   set `delay=input.new_delay() or "immediate"` in the `Connection(...)` at the
   add handler. Add a `delay` column to the `connections_table` rows.
2. **Excel import (`excel_import.py`).** Wrap the existing delay read:
   `delay=normalize_delay(_pick(row, CONN_DELAY_COLS, default="immediate"))`.
   Column fallbacks (`delay`/`Delay`/`lag`/`Lag`) already exist.
3. **Sample seed (`data/sample_ses.json`).** Set `"delay": "short"` on one edge
   that lies on an existing balancing loop. The implementer identifies it by
   running `feedback_loops` + `classify_loops` on the sample and choosing an edge
   inside a balancing cycle. **Done-criterion:** `classify_loops` on the seeded
   sample yields ≥1 `behavior == "oscillating"`.

## 6. i18n (`sespy/translations/core.json`, 9 languages)
New keys: `entry.delay`; delay level labels `delay.immediate`/`delay.short`/
`delay.long`; behavior labels `loops.behavior.reinforcing`/`.balancing`/
`.oscillating`; `loops.delayed`, `loops.behavior` (column headers), and a
`loops.oscillating_count` label. Mirror `loops.*` coverage; English authoritative
(loader falls back to English at `i18n.py:100`).

## 7. Edge cases & error handling
- **Legacy data (no `delay` key)** → dataclass default `immediate`;
  `normalize_delay(None/"")` → `immediate`. No migration.
- **Free-text / case** → `normalize_delay` case-insensitive; unknown non-empty →
  `short`.
- **Loop with mixed immediate+delayed edges** → `delayed=True` (any delayed link
  counts).
- **No delayed edges anywhere** → `behavior == type` for all loops; 0 Oscillating;
  zero behavioural change from today (backward-compatible).
- **Self-loops / dangling edges** → the existing loop detection is unchanged;
  delay is read via the same `(source,target)` lookup and simply absent → treated
  immediate.
- **Empty / no loops** → summary shows zeros; unchanged from today.

## 8. Testing
1. **Unit (`tests/test_network.py`, extend; pure):** `normalize_delay` table
   (`immediate`/`short`/`long`/`""`/`None`/`"Lag"`/`"SHORT"`/`"5y"`);
   `loop_has_delay` on a fixture (delayed vs all-immediate cycle); `classify_loops`
   emits `delayed` + `behavior` — a **delayed balancing** loop → `oscillating`;
   a **delayed reinforcing** loop → `behavior=reinforcing, delayed=True`; immediate
   loops → `reinforcing`/`balancing`, `delayed=False`.
2. **Sample done-criterion (`tests/test_network.py` or a data test):** assert
   `classify_loops` on `data/sample_ses.json` yields ≥1 `oscillating` (locks the
   seed; fails loudly if the seeded edge isn't on a balancing loop).
3. **e2e:**
   - **New `tests/test_loops_e2e.py`** (standalone asyncio Playwright, modelled on
     `tests/test_leverage_e2e.py`): nav to Loop Analysis (`#sespy_nav_loops`),
     click **Detect**, assert the summary/table shows ≥1 **Oscillating** and that a
     delayed edge in the rendered loop network is dashed (read vis.js edge
     `dashes`).
   - **Extend `tests/test_data_entry_e2e.py`:** assert the `new_delay` select
     exists with the three options and a connection can be added with a
     non-immediate delay.
   - Full gate: `python tests/run_e2e.py` — never `-k "not e2e"`, never `pytest`
     on the e2e scripts.

## 9. Build order (for the plan)
1. `DELAY_LEVELS` + `normalize_delay` in `constants.py` + unit tests (TDD).
2. `loop_has_delay` + `classify_loops` `delayed`/`behavior` in `network.py` +
   unit tests (incl. oscillating).
3. Sample seed + the ≥1-oscillating done-criterion test.
4. i18n keys.
5. Loop Analysis surfacing (`analysis_loops.py`): summary, table, narrative,
   picker, dashed edges.
6. Data-entry delay input + table column + Excel `normalize_delay`.
7. e2e: new `test_loops_e2e.py` + extend `test_data_entry_e2e.py`.
8. Full e2e gate via `python tests/run_e2e.py` → merge → push.
