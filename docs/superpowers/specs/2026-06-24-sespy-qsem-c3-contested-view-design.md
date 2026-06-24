# QSEM-C3 — Aggregation + contested-edges view design

**Date:** 2026-06-24
**Status:** approved (brainstorm)
**Sub-project:** C3 of QSEM-C (final chunk). Builds on C1
(`connection_disagreement`, shipped) and C2 (the Rate Connections module,
shipped `e3f75cc`).
**Roadmap:** `docs/superpowers/2026-06-22-qsem-followups-roadmap.md` (Follow-up 2,
resolves Q5).

## Problem

C1 computes per-connection disagreement and C2 lets stakeholders enter ratings,
but nothing makes the disagreement *visible* — the QSEM collaborative payoff
("which edges do stakeholders disagree on?") is still invisible. C3 surfaces it in
the Rate Connections table: a disagreement column, a "contested only" filter, and a
contested-count caption. Pure surfacing of the already-shipped
`connection_disagreement` — no new analysis.

## Decisions (from brainstorm, Q5)

- **Table-first, graph styling deferred.** Surface disagreement in the Rate
  Connections connections-table, not on the CLD graph. The graph's free edge
  channels are scarce (`to_visnetwork` uses color = polarity + opacity = confidence
  + label = polarity; the pyvis builders add dashes = delay via
  `network.delay_edge_kwargs`), and `polarity_contested` is a boolean *about the edge's own
  color*, so encoding it on the graph is weak/ambiguous and touches `to_visnetwork`
  + 5 pyvis builders. The table shows consensus and disagreement side by side, so
  the consensus stays unambiguous and the dispute is explicit. CLD edge-styling is
  an explicit later follow-up.
- **Polarity is the headline; spread is context.** A sign disagreement is the
  actionable conflict; strength/confidence spread is softer. The filter keys on
  `polarity_contested`; the column shows both.

## Architecture / components

### `sespy/network.py` — one pure cell formatter
- `disagreement_cell(d: dict, *, contested_label: str) -> str` — takes a
  `connection_disagreement(...)` result and a pre-translated contested label, and
  returns the column cell text. Pure (no `t()` inside → fully unit-testable on all
  three branches, including the spread numbers). Lives beside
  `connection_disagreement`:
  ```python
  def disagreement_cell(d: dict, *, contested_label: str) -> str:
      if d["polarity_contested"]:
          return f"⚠ {contested_label}"
      if d["strength_spread"] > 0 or d["confidence_spread"] > 0:
          return f"~ {d['strength_spread']:.0f}/{d['confidence_spread']:.0f}"
      return "—"
  ```
  The filter and count read `d["polarity_contested"]` directly — they do not go
  through this formatter.

### `sespy/modules/rate_connections.py` — surface it
- **Disagreement column** in `connections_table`: append a `disagreement` column
  (raw header, matching the table's other raw headers). Per displayed connection,
  `d = network.connection_disagreement(c)` then cell =
  `network.disagreement_cell(d, contested_label=t("rate.contested"))`.
- **"Contested only" filter**: a sidebar `input_checkbox("contested_only", …, value=False)`.
- **Legend** (so the `⚠`/`~` markers are self-explanatory): an unconditional
  `ui.tags.small` footnote below the table reading
  `⚠ contested sign · ~ strength/confidence spread (0–2 / 0–4)`. ASCII-light; no new
  i18n key required for the MVP (keep it as a fixed legend string).

#### Index contract (REQUIRED — prevents silent wrong-connection corruption)

`sel_idx` is the row index from `cell_selection()`, i.e. an index into the
**displayed** list. Today `_selected()` indexes the full
`project_data.isa_data.connections` directly (`conns[idx]`) — safe only because no
filter exists yet. Once the filter ships, the displayed list is a subset, so the raw
lookup would resolve the WRONG connection and `_save`/`_remove` would corrupt it.
The implementation MUST therefore:

1. Add `@reactive.calc displayed_connections() -> list[tuple[int, Connection]]`
   returning `(true_idx, conn)` pairs, where `true_idx` is the position in
   `project_data.get().isa_data.connections`:
   ```python
   @reactive.calc
   def displayed_connections():
       conns = project_data.get().isa_data.connections
       if not input.contested_only():
           return list(enumerate(conns))
       return [(i, c) for i, c in enumerate(conns)
               if network.connection_disagreement(c)["polarity_contested"]]
   ```
2. `connections_table` MUST iterate this same list (unpacking `conn` from each pair)
   so render and selection share one filtered list.
3. `_selected()` MUST be REFACTORED so its ONLY path is `displayed_connections()` —
   the existing `return idx, conns[idx]` against `conns = isa_data.connections` MUST
   be removed, with no other lookup path reachable:
   ```python
   def _selected():
       idx = sel_idx.get()
       if idx is None:
           return None, None
       pairs = displayed_connections()
       if idx >= len(pairs):
           return None, None
       return pairs[idx]   # (true_idx, conn)
   ```
4. `_save`/`_remove` need NO change: `_selected()` now hands them the **true**
   full-list index, which they already use to rewrite `list(...isa_data.connections)`.
5. FORBIDDEN: any value/identity scan such as `isa_data.connections.index(conn)` —
   `Connection` is a value dataclass, so duplicates on hand-edited JSON would
   mis-resolve. Resolution is by integer true-index only.
6. Reset `sel_idx` to `None` on BOTH `input.rater` (already shipped) AND
   `input.contested_only` change (new `@reactive.effect @reactive.event`), so a
   stale index never survives a filter/rater change.

- **Contested-count caption**: an `output_ui("contested_count")` above the table
  rendering `t("rate.contested_count", n=<count>)`, where count =
  `sum(1 for c in project_data.get().isa_data.connections if network.connection_disagreement(c)["polarity_contested"])`
  (always the FULL list, not the filtered one). Renders for any viewer (no rater
  needed); depends on `event_bus.isa_change`.

### i18n — `sespy/translations/core.json`
3 new keys × 9 languages: `rate.contested` ("Contested"), `rate.contested_only`
("Show contested only"), `rate.contested_count` ("{n} contested edges", `{n}`
interpolation — the translator already supports `t(key, n=…)`).

## Data flow

`connections_table` and `contested_count` read `event_bus.isa_change` so they
refresh after any rating save/remove (C2 already emits it). `connection_disagreement`
is called per row at render time (cheap: it is O(ratings) over a handful of
ratings). The filter and caption are pure reads; no persistence in C3.

## Error handling / edge cases

- <2 ratings on a connection → `connection_disagreement` returns not-contested,
  zero spreads → `disagreement_cell` returns `"—"`; not counted; hidden under
  "contested only".
- Empty project (stub row) → `connection_disagreement` on the stub is harmless
  (no ratings) → `"—"`; count 0.
- Filter on with zero contested edges → table shows the empty-stub row (existing
  behavior); caption reads "0 contested edges".
- `sel_idx` reset on filter toggle prevents a stale index selecting the wrong
  connection across a filter change.

## Testing

`tests/test_network.py` (the pure formatter — covers ALL three branches incl.
spread numbers):
- `disagreement_cell(d, contested_label="X")` returns `"⚠ X"` when
  `polarity_contested` True; `"~ {s}/{c}"` when sign agrees but a spread > 0 (assert
  the leading `~` AND the exact `n/n` numbers — strength spread 0–2 from ranks
  1/2/3, confidence spread 0–4 from 1–5); `"—"` when all agree / <2 ratings. Drive
  it with literal dicts AND with real `connection_disagreement` outputs on crafted
  connections (a +/− 2-rater → contested; a same-sign weak-vs-strong 2-rater →
  spread; unanimous/single → "—").

`tests/test_rate_connections_e2e.py` (extend the C2 e2e). The two ratings must come
from DIFFERENT raters, and switching rater resets `sel_idx` (C2's
`_reset_selection_on_rater`), so the row MUST be re-clicked after each rater switch
or the second save silently no-ops (`_selected()` returns None → "select a
connection" warning). Explicit sequence:
1. Add two stakeholders (`_set_select` for `sh_type`, per C2).
2. Go to Rate Connections; select rater SH-A; click the first connection row (TD).
3. Set polarity `+`; click `#rate-save_rating`; assert that row's `#ratings` → 1.
4. Switch rater to SH-B (this clears `sel_idx`); **re-click the same row** (TD).
5. Set polarity `-`; save; assert `#ratings` → 2.
6. Assert that row's `disagreement` cell contains `⚠`.
7. Assert the contested-count caption (`#rate-contested_count`) reads 1.
8. Check `#rate-contested_only`; assert the table narrows to exactly one row.
- Index-contract guard (unit or e2e): with `contested_only` on, selecting the first
  displayed row and saving writes to the first CONTESTED connection in
  `isa_data.connections`, NOT `isa_data.connections[0]`.
- i18n coverage auto-enforced by `test_i18n.py::test_loader_handles_all_supported_languages`.

## Out of scope (deferred follow-up)

- CLD / pyvis graph edge-styling by disagreement (the "free channel" question) —
  revisit once the table view proves the value.
- Disagreement-aware analyses (flagging loops/quadrant nodes that hinge on
  contested edges) — the original optional "C4".
- Sorting the table by disagreement; numeric disagreement scores beyond the
  spread display.
