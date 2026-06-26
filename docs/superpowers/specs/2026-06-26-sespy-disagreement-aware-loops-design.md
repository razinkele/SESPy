# Disagreement-aware loop flagging — design

**Date:** 2026-06-26
**Status:** approved (brainstorm)
**Tracks:** GitHub issue #9 (#5b, split from #5). Pairs with #8/#5a (CLD contested
styling) and the QSEM-C multi-rater work; see memory `sespy-qsem-multirater`.

## Problem / goal

Flag which **conclusions** depend on an edge the raters disagree on, so users know
which results are sensitive to unresolved disagreement. The C3 table and #5a CLD styling
flag the *edges*; this flags the *results*.

## The scoping insight (why loops only)

Rater **polarity** disagreement (`connection_disagreement(c)["polarity_contested"]`) can
only threaten a conclusion that is **sign-based**:
- **Loop classification IS sign-based** — `classify_loops`/`loop_polarity`: "even number
  of negative edges → Reinforcing, odd → Balancing." A contested-sign edge directly
  threatens a loop's Reinforcing/Balancing label. **In scope.**
- **Leverage is structural** — z-scores of betweenness/eigenvector/PageRank (unweighted
  topology, sign-agnostic). Polarity disagreement cannot move it. **Out of scope**
  (flagging it would be meaningless).
- **Quadrant is magnitude-based** — `influence_dependence` uses
  `_edge_weight = strength_rank × confidence` (no sign). It would respond to
  `strength_spread`, a *different* disagreement signal — **deferred** as separate work.

This mirrors the D2D asymmetry (memory `sespy-uncertainty-scoring`): sign → loops,
structure → leverage. v1 does **loops only**, with polarity disagreement.

## Decisions (from brainstorm)

- **Loops only.** A loop is flagged when its classification hinges on a
  rater-polarity-contested edge.
- **Surface = annotate the classification directly:** append `⚠` to the loop's
  **behavior** label in the loops table (`"Reinforcing"` → `"Reinforcing ⚠"`), plus a
  legend. This ties the marker to *exactly* the conclusion at risk and **avoids a new
  column colliding** with the loops table's existing `loops.contested` column (which is
  the opt-in **D2D confidence-MC** signal, #4 — a different thing).
- **Separate from #4, coherent with it.** #4 is the *opt-in, probabilistic* "low-
  confidence edges could flip this loop" (Monte Carlo). #5b is the *always-on,
  deterministic* "raters explicitly disagree on an edge's sign in this loop." Both use
  the `⚠` glyph (consistent with #5a CLD + the Rate Connections table). Not merged —
  merging would conflate "uncertain" with "disputed."
- **Boolean** (any contested edge in the loop) for v1; `strength_spread`-weighting and
  the quadrant deferred.

## Architecture

**Pure helper** (`sespy/network.py`), placed near `loop_polarity`:
```python
def loop_polarity_contested(cycle: list[str], isa: IsaData) -> bool:
    """True if any directed edge of the cycle is rater-polarity-contested.
    Mirrors loop_polarity's edge iteration (consecutive pairs, wrap-around), so
    the flagged edges are exactly those that determine the loop classification.
    Pure; False for loops whose edges have <2 ratings."""
    conn_by_pair = {(c.source, c.target): c for c in isa.connections}
    n = len(cycle)
    for i in range(n):
        c = conn_by_pair.get((cycle[i], cycle[(i + 1) % n]))
        if c is not None and connection_disagreement(c)["polarity_contested"]:
            return True
    return False
```
`connection_disagreement` is already in `network.py`; no new import.

**Loops table** (`sespy/modules/analysis_loops.py`, the `loops_table` render). The module
imports network as **`net_analysis`** (`from .. import network as net_analysis`) — use
that name, NOT `network`. In `loops_table`, after the `if not rows: return ...` guard,
bind `isa = project_data.get().isa_data`; the nested `base_row(r)` (which closes over
`isa`) appends `⚠` to the translated behavior label:
```python
        isa = project_data.get().isa_data

        def base_row(r):
            behavior = t(_BEHAVIOR_KEY[r["behavior"]])
            if net_analysis.loop_polarity_contested(r["nodes"], isa):
                behavior = f"{behavior} ⚠"
            return {
                "id": r["id"],
                "behavior": behavior,        # was: t(_BEHAVIOR_KEY[r["behavior"]])
                "delayed": "✓" if r["delayed"] else "—",
                "type": r["type"],
                "length": r["length"],
                "path": r["path"],
            }
```
`r["nodes"]` is the cycle (the loop dict from `classify_loops` carries `"nodes"`). Only
the `behavior` line changes; the rest of `base_row` is unchanged.

**Legend** — a `ui.tags.small(t("loops.disagreement_legend"), class_="text-muted")`
near the loops table (mirroring the CLD/rate legends).

**i18n** — one new key `loops.disagreement_legend` × 9 languages,
en = `"⚠ = a loop edge has raters disagreeing on its sign (classification disputed)"`.

## Error handling / edge cases

- **Loops with no rated edges** (single-author, imported) → helper returns `False` →
  no `⚠`, table unchanged. Purely additive.
- **A loop edge with <2 ratings** → `connection_disagreement` returns
  `polarity_contested=False` → not counted.
- **Self-loop / 1-node cycle** → `cycle[(0+1)%1]==cycle[0]`; if no `(a,a)` connection
  exists, `conn_by_pair.get` is `None` → skipped. Safe.
- A loop edge whose `(source,target)` isn't in `conn_by_pair` (shouldn't happen for a
  real cycle) → `None` → skipped (no crash).
- The flag is **independent of the uncertainty toggle** — it shows whenever the loops
  table renders (the behavior cell is a base column, always present).

## Testing

- **Unit** (`tests/test_network.py`): `loop_polarity_contested` on a small `IsaData` —
  a 2-cycle `A→B→A` where the `A→B` connection carries two sign-disagreeing ratings
  (`+`/`-`) → `True`; the same topology with unanimous ratings / `<2` ratings → `False`;
  a cycle whose contested edge is not on the loop path → `False` (mirrors the wrap-around
  edge set). Build `Rating` objects directly.
- **i18n** presence test for `loops.disagreement_legend`.
- The existing `test_loops_e2e.py` stays green (the sample project has no multi-rater
  ratings → no behavior cell changes). No new browser test — the pure-helper unit test
  covers the logic (same approach as #5a).

## Out of scope (YAGNI)

- Quadrant flagging by `strength_spread` (a different signal — separate follow-up).
- Leverage flagging (structural → polarity disagreement can't affect it).
- Weighting by how many loop edges are contested (boolean only for v1).
- A separate column or merging with the #4 uncertainty MC "contested" signal.
- Per-loop drill-down of *which* edge is contested (the CLD #5a styling already shows
  that on the graph).
