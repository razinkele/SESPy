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
| Vocabulary | `immediate` / `short` / `long` (ordered) | Mirrors the existing 3-level `strength` categorical in the data model; the data-entry select follows the existing `new_type`/polarity input idiom (`isa_data_entry.py`). Satisfies both the loop flag (delayed = short\|long) and graded edge styling. |
| "Delayed" predicate | `normalize_delay(c.delay) != "immediate"` | Single definition; short and long both count as delayed for the loop flag. |
| `normalize_delay(raw)` | exact `short`/`long`; explicit immediate/negation sentinels → `immediate`; numeric 0 → `immediate`, positive → `short`; only genuine non-empty free-text → `short` (see §3.1) | **Conservative/asymmetric** so a negated value (`"no"`, `"none"`, `"0"`, `"false"`) is NOT mislabelled delayed; unknown free-text in a delay/lag column lands as "delayed, magnitude unknown". |
| Behavior model | mutually exclusive `reinforcing` / `balancing` / `oscillating`; **oscillating = balancing AND delayed** (replaces balancing for those loops) | Three non-overlapping counts summing to total — no double-counting. Oscillating is the headline new state. **Display hedged** (see below): it's a *structural* signature, not a simulated result. |
| Oscillating wording | internal key `oscillating`; **display "Oscillation-prone"** + a disclaimer tooltip (i18n) | A delayed balancing loop is *prone to* overshoot/oscillation, but actual behaviour depends on gains/delay magnitude (not simulated here). Avoids over-claiming a structural mark as dynamics. |
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

_DELAY_IMMEDIATE_SENTINELS = frozenset({
    "", "none", "immediate", "instant", "now", "no", "n/a", "na",
    "false", "f", "-",
})

def normalize_delay(raw: object) -> str:
    """Map any stored/imported delay value to DELAY_LEVELS — conservatively,
    so a negated/zero value is NOT mislabelled as delayed.

    Order (case-insensitive, stripped):
      1. exact 'short' / 'long' / 'immediate' -> itself
      2. an immediate/negation sentinel (none, no, n/a, false, 0-meaning, '-')
         -> 'immediate'
      3. parses as a number: 0 -> 'immediate', > 0 -> 'short'
      4. any remaining non-empty free-text (e.g. 'lag', 'delayed') -> 'short'
         ('delayed, magnitude unknown')
    """
```
Algorithm: `s = str(raw).strip().lower()`; if `s in {"short","long","immediate"}`
return it; if `s in _DELAY_IMMEDIATE_SENTINELS` return `"immediate"`; try
`float(s)` → `"immediate"` if `== 0` else `"short"`; on `ValueError`, return
`"short"`. (`long` is only ever produced by an exact `"long"` match or by the
data-entry select — numeric/free-text never auto-promotes to `long`; that's a
deliberate floor, not a bug.)

### 3.2 `sespy/network.py` (append + extend)
```python
def loop_has_delay(cycle: list[str], isa: IsaData) -> bool:
    """True if any edge traversed by `cycle` is delayed
    (normalize_delay(delay) != 'immediate'). Mirrors loop_polarity's
    edge-walk over (cycle[i], cycle[(i+1)%n])."""
```
Build a `{(source,target): delay}` lookup (parallel to `_edge_polarity_lookup`),
walk the cycle edges, return `True` on the first delayed edge. **Note:** like
`_edge_polarity_lookup`, this is last-wins on parallel `(source,target)` edges
(the in-app UI blocks duplicate edges at `isa_data_entry.py:240`; only Excel /
hand-edited JSON can produce them). Documented in the docstring; a parallel-edge
unit test pins the behaviour (§8).

**`classify_loops` gains two fields** per loop dict (keeping `id`, `length`,
`type`, `nodes`, `path` unchanged):
- `delayed: bool` = `loop_has_delay(cycle, isa)`
- `behavior: str` — derived **explicitly** (total, no silent fallthrough):
  `"oscillating"` if (`type == "Balancing"` and `delayed`); else `"balancing"`
  if `type == "Balancing"`; else `"reinforcing"` (covers `type == "Reinforcing"`
  and any unexpected value — `loop_polarity` is binary today, so the else is a
  documented safety floor).

(`behavior` is lower-case to key i18n; the UI maps it to a display label. The
three buckets are mutually exclusive and sum to `len(loops)` — pinned by a unit
test in §8.)

## 4. Loop Analysis surfacing (`sespy/modules/analysis_loops.py`)

All read the new fields from `classify_loops`; no new graph work in the module.

**Display wording (applies to summary, table, narrative, picker):** the
`oscillating` behavior is shown as **"Oscillation-prone"** (i18n
`loops.behavior.oscillating`), with a disclaimer tooltip/footnote (i18n
`loops.oscillating_disclaimer`): *"Structural signature only — delayed balancing
loops are prone to overshoot/oscillation; actual behaviour depends on gains and
delay magnitude, which are not simulated here."* This keeps the data-layer key
crisp (`oscillating`) while the UI does not over-claim simulated behaviour.

1. **Classification summary (sidebar).** Count by `behavior` into three
   mutually-exclusive buckets — **Reinforcing**, **Balancing**, **Oscillation-prone**
   — each in its own colour (oscillation-prone distinct, e.g. amber), with the
   disclaimer footnote beneath the oscillation-prone count. Replaces today's
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

1. **Data-entry form (`isa_data_entry.py`).** Add
   `ui.input_select("new_delay", t("entry.delay"),
   {lvl: t(f"delay.{lvl}") for lvl in DELAY_LEVELS}, selected="immediate")` into
   the connection-add `layout_columns` — choices built **inline at render time**
   from `DELAY_LEVELS` + the i18n level keys (matching the existing `new_type`
   `{x: x}` idiom; there is no static `DELAY_LEVEL_LABELS` constant — a
   module-level constant could not be localized). Refit `col_widths` to the
   committed **`(3, 3, 2, 2, 2)`** (source/target/polarity/delay/add-button, all
   five inline); if the "Add connection" label truncates at width 2, shorten it
   or move the button to its own full-width row below. Set
   `delay=input.new_delay() or "immediate"` in the `Connection(...)` at the add
   handler. Add a `delay` column to the `connections_table` rows **and to the
   empty/placeholder frame** (`{"source":"","target":"","polarity":"",
   "strength":"","delay":""}`) so the header is consistent when empty; display the
   raw stored value (normalization happens at import/predicate time, not display).
2. **Excel import (`excel_import.py`).** Wrap the existing delay read:
   `delay=normalize_delay(_pick(row, CONN_DELAY_COLS, default="immediate"))`.
   Column fallbacks (`delay`/`Delay`/`lag`/`Lag`) already exist.
3. **Sample seed (`data/sample_ses.json`).** Set `"delay": "short"` on one edge
   that lies on an existing balancing loop. **Confirmed feasible:** the sample
   already has 3 balancing loops — e.g. the cycle
   `MPF2→ES02→GB02→D002→A002→P002`; seed an edge on it (e.g. `MPF2→ES02`).
   **Done-criterion:** with `cycles = feedback_loops(sample.isa_data)`,
   `classify_loops(cycles, sample.isa_data)` yields ≥1 `behavior == "oscillating"`
   (note `classify_loops` takes `(cycles, isa)` — `feedback_loops` runs first).

## 6. i18n (`sespy/translations/core.json`)
Every new key MUST be authored in **all 9 catalog languages** (en, es, fr, de,
lt, pt, it, no, el). The runtime English fallback (`i18n.py:100`) does **not**
satisfy the drift test `tests/test_i18n.py::test_loader_handles_all_supported_languages`,
which fails on any English-only key — so all 9 are required, not optional.

Full key inventory:
- `entry.delay` (data-entry input label)
- delay level labels: `delay.immediate`, `delay.short`, `delay.long`
- behavior display labels: `loops.behavior.reinforcing`, `loops.behavior.balancing`,
  `loops.behavior.oscillating` (= "Oscillation-prone")
- `loops.oscillating_disclaimer` (the structural-signature footnote, §4)
- narrative delay chip: `loops.delay_chip`

(Table column *headers* stay untranslated English — matching the existing
`loops_table` headers `id`/`type`/`length`/`path` — so no `loops.col_*` keys; only
the cell *values* are translated. The summary count line reuses
`loops.behavior.oscillating` as its label, so no separate `loops.oscillating_count`
key. Net: 9 new keys.)

(The existing Reinforcing/Balancing summary labels are reused, not retro-keyed.)

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
- **Backward compatibility (verified against existing tests):** `classify_loops`
  **retains** `type` and only *adds* `delayed`/`behavior` — so
  `test_network.py::test_loop_polarity_rule` (asserts `type ∈
  {Reinforcing,Balancing}`) and `test_report.py::test_render_html_includes_loop_classifications`
  (asserts "Reinforcing" in HTML) still pass. The sample seed **edits an existing
  edge's `delay`** (does not add/remove an edge), so
  `test_network.py::test_sample_loads` (`connection_count() == 20`,
  `element_count() == 17`) still passes. No existing assertion depends on the
  2-bucket summary.

## 8. Testing
1. **Unit (`tests/test_network.py`, extend; pure):**
   - `normalize_delay` table — exact `immediate`/`short`/`long`; case
     (`"SHORT"`,`"Long"`); sentinels that must be **immediate** (`""`, `None`,
     `"no"`, `"none"`, `"false"`, `"0"`, `"0.0"`, `"-"`); numeric (`"3"`→`short`,
     `"0"`→`immediate`); free-text (`"lag"`,`"delayed"`,`"5y"`→`short`).
   - `loop_has_delay` on a fixture (delayed vs all-immediate cycle); a
     **parallel-edge** fixture pinning the last-wins lookup behaviour.
   - `classify_loops` emits `delayed` + `behavior` — a **delayed balancing** loop
     → `oscillating`; a **delayed reinforcing** loop → `behavior=reinforcing,
     delayed=True`; immediate loops → `reinforcing`/`balancing`, `delayed=False`.
   - **Behavior totality:** on any fixture, the three behavior-bucket counts sum
     to `len(loops)` (pins mutual exclusivity / no silent fallthrough).
2. **Sample done-criterion (`tests/test_network.py`):** with `cycles =
   feedback_loops(isa)`, assert `classify_loops(cycles, isa)` on
   `data/sample_ses.json` yields ≥1 `oscillating` (locks the seed; fails loudly if
   the seeded edge isn't on a balancing loop).
3. **i18n:** `pytest tests/test_i18n.py` passes (all new keys present in all 9
   languages — part of the i18n task's done-criteria).
4. **e2e:**
   - **New `tests/test_loops_e2e.py`** (standalone asyncio Playwright, modelled on
     `tests/test_leverage_e2e.py`): nav to Loop Analysis (`#sespy_nav_loops`),
     click **Detect**, **poll** until the loops table populates (the data_frame
     `<tbody>` late-mounts; use `wait_for_selector` on the table rows, not a fixed
     sleep), assert the summary/table shows ≥1 **Oscillation-prone**, then select
     that loop and read the rendered network's edges via
     `window.pyvisNetworks['loops-loop_network'].edges.get().map(e => e.dashes)`,
     asserting `dashes.some(d => d === true)` **and** at least one solid edge
     (`dashes.some(d => !d)`) — guards against an all-dashed or field-undefined
     read. (This edge-attribute read is novel in this repo — no prior e2e reads
     `.edges.get()`; the loop network is empty until a loop is selected, so select
     first.)
   - **Extend `tests/test_data_entry_e2e.py`:** assert the `#entry-new_delay`
     select exists with the three options and a connection can be added with a
     non-immediate delay (budget for the reactive `output_ui` source/target picker
     late-mount; pick two distinct existing sample element ids).
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
