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
  channels are scarce (color = polarity, opacity = confidence, dashes = delay,
  label = polarity), and `polarity_contested` is a boolean *about the edge's own
  color*, so encoding it on the graph is weak/ambiguous and touches `to_visnetwork`
  + 5 pyvis builders. The table shows consensus and disagreement side by side, so
  the consensus stays unambiguous and the dispute is explicit. CLD edge-styling is
  an explicit later follow-up.
- **Polarity is the headline; spread is context.** A sign disagreement is the
  actionable conflict; strength/confidence spread is softer. The filter keys on
  `polarity_contested`; the column shows both.

## Architecture / components

### `sespy/network.py` — one pure classifier
- `disagreement_state(d: dict) -> str` — takes a `connection_disagreement(...)`
  result and returns one of `"contested"` / `"spread"` / `"none"`:
  ```python
  def disagreement_state(d: dict) -> str:
      if d["polarity_contested"]:
          return "contested"
      if d["strength_spread"] > 0 or d["confidence_spread"] > 0:
          return "spread"
      return "none"
  ```
  Pure, translation-free, trivially unit-testable. Lives beside
  `connection_disagreement`.

### `sespy/modules/rate_connections.py` — surface it
- **Disagreement column** in `connections_table`: append a `disagreement` column
  (raw header, matching the table's other raw headers). Per connection, compute
  `d = network.connection_disagreement(c)` once and
  `state = network.disagreement_state(d)`, then the cell text:
  - `"contested"` → `f"⚠ {t('rate.contested')}"`
  - `"spread"` → `f"~ {d['strength_spread']:.0f}/{d['confidence_spread']:.0f}"`
  - `"none"` → `"—"`
- **"Contested only" filter**: a sidebar `input_checkbox("contested_only", …, value=False)`.
  When on, `connections_table` includes only connections whose `state == "contested"`
  (i.e. `d["polarity_contested"]`). **Selection-index caveat:** filtering changes
  the displayed rows, so the cached `sel_idx` (a row index into the *displayed*
  list) can point at the wrong connection after the filter toggles. Reset `sel_idx`
  to `None` on `input.contested_only` change (a `@reactive.effect @reactive.event`),
  exactly as it already resets on rater change — so editing always re-selects
  against the current view. The editor/save/remove keep operating on the displayed
  list, so the index stays consistent within a given filter state.
- **Contested-count caption**: an `output_ui("contested_count")` above the table
  rendering `t("rate.contested_count", n=<count>)`, where count =
  `sum(1 for c in connections if network.connection_disagreement(c)["polarity_contested"])`.
  Renders for any viewer (no rater needed); depends on `event_bus.isa_change`.

> Because `sel_idx` is an index into the table's *displayed* connection list, the
> filtered `connections_table` and every consumer of `sel_idx` (the
> `_selected()` helper, save, remove) MUST iterate the **same** filtered list. The
> cleanest implementation is a single `@reactive.calc displayed_connections()` that
> returns the (optionally filtered) list of `(original_index_or_connection)` used by
> both the table render and `_selected()`. `_selected()` resolves the row to a
> concrete `Connection` and its index in `project_data.isa_data.connections` for
> persistence. (Persistence still rewrites the full connection list by the
> connection's true index, not the displayed index.)

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
  zero spreads → `state == "none"` → `"—"`; not counted; hidden under "contested
  only".
- Empty project (stub row) → `connection_disagreement` on the stub is harmless
  (no ratings) → `"—"`; count 0.
- Filter on with zero contested edges → table shows the empty-stub row (existing
  behavior); caption reads "0 contested edges".
- `sel_idx` reset on filter toggle prevents a stale index selecting the wrong
  connection across a filter change.

## Testing

`tests/test_network.py` (the pure classifier):
- `disagreement_state` returns `"contested"` when `polarity_contested` True;
  `"spread"` when sign agrees but a spread is > 0; `"none"` when all agree / <2
  ratings. Drive it with literal dicts and with real `connection_disagreement`
  outputs on crafted connections (a +/− 2-rater connection → contested; a
  same-sign weak-vs-strong 2-rater → spread; a unanimous/single → none).

`tests/test_rate_connections_e2e.py` (extend the C2 e2e or add a focused case):
- Add two stakeholders; rate the same connection from each with **opposite
  polarity**; assert (a) that connection's `disagreement` cell shows the contested
  marker (`⚠`), (b) the contested-count caption reads 1, (c) toggling
  `#rate-contested_only` narrows the table to that one row. Reuse the verified
  `_set_select` + TD-cell-click idioms.
- i18n coverage auto-enforced by `test_i18n.py::test_loader_handles_all_supported_languages`.

## Out of scope (deferred follow-up)

- CLD / pyvis graph edge-styling by disagreement (the "free channel" question) —
  revisit once the table view proves the value.
- Disagreement-aware analyses (flagging loops/quadrant nodes that hinge on
  contested edges) — the original optional "C4".
- Sorting the table by disagreement; numeric disagreement scores beyond the
  spread display.
