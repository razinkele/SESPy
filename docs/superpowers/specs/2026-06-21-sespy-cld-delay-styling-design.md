# SESPy CLD Delay Styling (QSEM time-delay, "B2") — Design

Date: 2026-06-21
Status: **Draft** (spec review gate)

**Context.** Improvement **B** (delay-aware Loop Analysis, merged `2e83bb0`) made
`Connection.delay` a first-class 3-level field and styled delayed edges (dashed)
in the **Loop Analysis** loop network. **B2** applies the same treatment to the
**main CLD** network (`cld_visualization.py`) so the delay signal is visible in
the primary diagram — a user scanning the CLD sees where the lags are without
first running loop detection. All the machinery (`normalize_delay`, the
`add_edge(dashes=...)` idiom) already exists from B; this is purely applying it
at one more edge-build site.

## 1. Goal & scope

### 1.1 In scope
- In `_build_pyvis_network` (`cld_visualization.py:229-237`), add `dashes` + a
  delay-aware `title` tooltip to the `net.add_edge(...)` call.
- Unit test (call `_build_pyvis_network`, inspect edge `dashes`) + a new CLD e2e.

### 1.2 Out of scope
- **No data-model / schema / i18n change.** The tooltip uses the raw delay level
  (same as the Loop Analysis loop network); no new strings.
- **No legend.** The CLD module has no legend today; adding one is a separate
  effort (out of scope/YAGNI).
- **No change to the Loop Analysis module** (B already styled its loop network).
- No change to edge colour (polarity-driven) or layout.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Delayed predicate | `normalize_delay(c.delay) != "immediate"` | Single shared definition (reuses B's `normalize_delay`). |
| Edge cue | vis.js `dashes=True` via the `add_edge(..., dashes=...)` **keyword path** (NOT `EdgeOptions`/`options=`) | One-line per edge; mirrors B's loop network; keyword path is the one that propagates `dashes` to the vis.js edge so `e.dashes` is readable (verified in B). |
| Tooltip | `title=f"{c.polarity} · {normalize_delay(c.delay)}"` | Same format as the loop network; shows polarity + delay level on hover. |
| Colour / width / arrows | unchanged | Polarity colour and layout are not part of this change. |

## 2. No data-model change
`data_structure.py` is untouched. `_build_pyvis_network` reads the existing
`Connection.delay`. No `PROJECT_SCHEMA_VERSION` bump.

## 3. The edit (`cld_visualization.py`)
Add `from ..constants import normalize_delay` to the module imports (merge with
the existing `..constants` import block). Replace the edge loop at lines 229-237:

```python
    for c in isa.connections:
        delay = normalize_delay(c.delay)
        net.add_edge(
            c.source,
            c.target,
            label=c.polarity,
            title=f"{c.polarity} · {delay}",
            color=EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
            arrows="to",
            width=2,
            dashes=delay != "immediate",
        )
```

## 4. Edge cases & backward compatibility
- **No delayed edges** (most projects today) → every edge `dashes=False`; visually
  identical to the current CLD. Backward-compatible.
- **`normalize_delay`** already handles empty/None/free-text/sentinels (from B),
  so malformed delay values can't break the build.
- **Topology unchanged** — `dashes`/`title` are presentation attributes only; node
  and edge counts, colours, and layout are unaffected, so existing CLD-reading
  e2e (e.g. `test_data_entry_e2e.py` asserting `cld-network` node counts) still
  pass.

## 5. Testing
1. **Unit (`tests/test_cld.py`, new; pure — no browser):** call
   `_build_pyvis_network(isa, layout_kind="physics",
   direction="UD", level_sep=150, node_sp=120, size_scale=1.0, font_scale=1.0)`
   on a 2-edge fixture (one `delay="short"`, one `delay="immediate"`), then
   `nodes, edges, *_ = net.get_network_data()` and assert the delayed edge has
   `dashes is True` and the immediate edge has `dashes is False`. (Mirrors how
   `analysis_loops.build_loop_payload` is unit-shaped.)
2. **e2e (`tests/test_cld_e2e.py` new, standalone asyncio Playwright modelled on
   `tests/test_leverage_e2e.py`):** load the app (default CLD tab), poll
   `window.pyvisNetworks['cld-network']` until ready, read
   `.edges.get().map(e => e.dashes === true)` and assert `some(d => d === true)`
   **and** `some(d => d === false)` — the seeded sample has exactly one delayed
   edge (`MPF2→ES02`) among 20, so both hold. Full gate via
   `python tests/run_e2e.py` (never `-k "not e2e"` / `pytest` on e2e scripts).

## 6. Build order (for the plan)
1. Unit test (TDD red) → add the `dashes`/`title` to `_build_pyvis_network` →
   green. Commit.
2. `tests/test_cld_e2e.py` + full e2e gate → merge → push.
