# Deferred Issues Roadmap — #4, #5, #6

**Date:** 2026-06-25
**Status:** sequencing plan (not yet specced — each issue still goes through the standard pipeline below).

Three open GitHub issues remain after the v1.1.0 release, all deferred follow-ups
from shipped features. They are **independent** — no hard dependencies — so they can
be tackled in any order, but the recommended sequence below front-loads the smallest,
highest-value, most plan-ready work.

## Recommended sequence

| Order | Issue | Size | Readiness | Why this slot |
|---|---|---|---|---|
| 1 | **#4** D2D async offload | S–M | **Plan-ready** | Fixes a UX wart in a *shipped* feature; the off-thread pattern already exists in the codebase; the core function is pure and untouched. Lowest risk, immediate payoff. |
| 2 | **#6** C2 anchoring mode | S | Near-ready (tiny brainstorm) | Small, self-contained UI change to one module; one design decision (toggle scope). |
| 3 | **#5** QSEM-C4 | L | **Needs brainstorm** | Two distinct sub-features with real design questions (visual encoding + which analyses). Split before building. |

Each issue still runs the full pipeline used all session: **brainstorm → spec →
in-loop Workflow spec-review → writing-plans → in-loop Workflow plan-review →
subagent-driven TDD → final review → full-e2e gate → merge**. #4 is mechanical enough
that its brainstorm can be a single design decision; #5 genuinely needs the full
brainstorm.

---

## #4 — D2D: offload `uncertainty_scores` Monte Carlo off the reactive thread

**Problem.** `network.uncertainty_scores()` runs synchronously on the reactive thread,
so toggling the uncertainty view freezes the UI for several seconds (~78 ms/sample ×
default 100 ≈ 8 s; 500 froze it ~39 s).

**Current state (grounded).**
- Two identical call sites: `analysis_leverage.py:158-167` and
  `analysis_loops.py:~190` — each a `@reactive.calc uncertainty()` that calls
  `net_analysis.uncertainty_scores(...)` inline and is consumed by the table render.
- The off-thread pattern **already exists**: `ai_isa_wizard.py:681` uses
  `@reactive.extended_task` (the Claude backend call) — a working template to copy.
- `uncertainty_scores` itself is pure (no reactive deps) — **no change to
  `network.py`**; the work is entirely module-side.

**Approach.** Replace each `@reactive.calc uncertainty()` with:
1. a `@reactive.extended_task` wrapping `uncertainty_scores(isa, n_samples, seed)`,
2. a `@reactive.effect` that `.invoke()`s it when `show_uncertainty` is on and the
   inputs (`isa_change`, `n_samples`) change,
3. a small `@reactive.calc` exposing `task.result()` when ready / `None` while pending,
4. a spinner / "computing…" state in the table + CI columns while pending.

**Readiness:** plan-ready after one design decision (spinner UX + whether to debounce
`n_samples` changes). Likely **2 tasks** (leverage module, loops module) sharing a tiny
extracted helper, since the two call sites are near-identical — DRY the invoke/read
into one reusable shape. Watch for the shared-pattern duplication a reviewer would
flag.

**Effort:** S–M. **Risk:** low (pure function untouched; established pattern). e2e:
the existing leverage/loops e2e exercise the toggle — they must stay green and may
need a wait-for-result step.

---

## #6 — QSEM-C2: anchoring-independent ("blind") rating mode

**Problem.** Rate Connections shows the existing peer ratings (`current_ratings`,
`rate_connections.py:42-43`) while a stakeholder enters theirs — risking **anchoring
bias** (raters pulled toward the visible consensus).

**Current state (grounded).** `rate_connections.py:43` renders
`ui.output_ui("current_ratings")` unconditionally; the editor and the consensus
machinery are untouched by this issue.

**Approach.** An optional "blind mode" that hides individual peer ratings for the
selected connection until the current rater has saved their own (Delphi-style). The
consensus scalars and `connection_disagreement` are unaffected — purely a display gate
on the `current_ratings` output.

**Brainstorm questions to resolve first (small):**
1. Toggle scope — a per-session checkbox in the sidebar, or a per-project setting?
   (Recommend: per-session sidebar checkbox, default off, so it's opt-in and stateless.)
2. "Has the rater rated this connection?" gate — reuse the existing `mine` check
   (`rate_connections.py:108`: `any(r.rater_id == rater for r in c.ratings)`).
3. Does blind mode also hide the `disagreement` column / contested count, or only the
   per-rater list? (Recommend: only the per-rater `current_ratings` list — the
   aggregate disagreement signal is not individually anchoring.)

**Readiness:** near-ready; a 2-3 question brainstorm settles it, then a small spec +
1-2 task plan. **Effort:** S. **Risk:** low (one module, display-only).

---

## #5 — QSEM-C4: disagreement-aware analyses + CLD edge styling for contested edges

**Two distinct sub-features — recommend splitting into #5a and #5b before building.**

**Current state (grounded).**
- `network.connection_disagreement(connection)` (`network.py:452`) already returns
  `{polarity_contested, strength_spread, confidence_spread}` — the data exists.
- CLD edges are drawn in `cld_visualization.py:232` with `color=EDGE_COLORS[...]`
  (polarity) and a fixed `width=2`. Existing visual channels are largely spoken for:
  **color = polarity, opacity = confidence, dashes = delay** — so disagreement needs a
  *new* channel.

### #5a — CLD edge styling by disagreement (visual)
**The honest blocker (why it was deferred):** the free edge channels are scarce, and
`polarity_contested` is a boolean *about the edge's own color* — so it can't be shown
by re-coloring. Needs a deliberate encoding.
**Brainstorm questions:** which channel for contestedness — edge **width** (currently
fixed at 2), a badge/label, a glow, or an animated dash? Does it apply only to
`polarity_contested` edges or scale with `strength_spread`? Legend treatment?
**Effort:** M (mostly design + a focused `add_edge` change + a legend entry).

### #5b — disagreement-aware analyses (analytical)
**Goal:** flag conclusions that *hinge on* a contested edge — e.g. a loop, a
quadrant placement, or a leverage rank that depends on an edge the team disagrees on.
**Brainstorm questions:** which analyses get the flag (loops? quadrant? leverage?);
is a result "contested" if *any* edge on it is contested, or weighted by how many; how
to surface it (a column, an icon, a caption)? This overlaps conceptually with the D2D
uncertainty work (#4) — both express "how robust is this result" — so consider whether
contestedness feeds the *same* CI/contested surfacing rather than a parallel one.
**Effort:** M–L.

**Readiness:** **needs a full brainstorm** (both sub-features). Recommend filing #5a
and #5b as separate issues, brainstorming each, and doing #5a first (smaller, visual,
self-contained) — or deferring #5b until after #4 ships, since they may share a
"result robustness" surface.

---

## How to proceed

Pick the next slot (recommended: **#4**) and start its brainstorm. #4 and #6 are small
enough that their brainstorm is a short design conversation; #5 needs the full
treatment and a split first. None blocks the others, so the order is purely
value/effort-driven — #4 gives the biggest immediate return (a shipped feature stops
freezing the UI).
