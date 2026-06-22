# QSEM Follow-ups Roadmap

Date: 2026-06-22
Status: **Roadmap** (not a per-feature spec/plan — each follow-up gets its own
brainstorm → spec → plan cycle as it's picked up)

**Context.** Three improvements from the QSEM (Qualitative Systems Exploration
Model) vs. SESPy analysis have shipped: **A** Factor Quadrant (`9be151b`,
pushed), **B** delay-aware Loop Analysis (`2e83bb0`, pushed), **B2** graph-view
delay styling (`d2a20d5`, merged local). Two follow-ups remain. They are
**independent** and very different in size, so they are two separate
sub-projects — this roadmap decomposes both and recommends sequencing.

| Follow-up | Size | Schema change? | Needs its own brainstorm? | Recommended order |
|---|---|---|---|---|
| 1. Quadrant median-split toggle | Small (1 chunk) | No | Minimal (design below is near-ready) | **First** |
| 2. Multi-rater elicitation (C) | Large (3–4 chunks) | **Yes** (`Connection` → ratings list) | **Yes** — design-first | Second |

Rationale for order: #1 is small, self-contained, and zero-risk (no schema); ship
it to close out the quadrant. #2 is the deepest remaining gap but is a schema-level
effort that ripples through persistence, import, the data-entry UI, and every
analysis that reads `strength`/`confidence` — it deserves a dedicated
brainstorm and should not be rushed behind #1.

---

## Follow-up 1 — Quadrant median-split toggle (near-ready)

**Goal.** Let the user switch the Factor Quadrant's cross-hair split between
**mean** (current default) and **median**, and warn when the distribution is
hub-skewed (where mean collapses most factors into one quadrant). Deferred from
improvement A (quadrant spec §1.2/§5).

**Why median matters.** Each axis is an unbounded Σ of edge weights, so one
high-degree hub raises the mean and can push the whole long tail below it into
`reactive`/`buffering`, hiding secondary leverage points. Mean stays the
*default* (it preserves "above-average influence" and a sparse Active quadrant
when drivers are genuinely few); median is the opt-in for skewed graphs.

**Scope (one chunk, no schema change):**
- `sespy/network.py::influence_dependence(isa, *, split="mean")` — add a `split`
  keyword (`"mean"|"median"`). When `"median"`, compute the per-axis cross-hair
  as the median of the axis values instead of `sum/n`; classification (`>=`
  threshold), the degeneracy guard, and the return shape are otherwise
  unchanged. Default `"mean"` keeps every existing caller and test intact.
- `sespy/modules/analysis_quadrant.py` — add an `input_radio_buttons`/
  `input_select` ("Cross-hair: mean | median") to the sidebar (currently
  controls-free); thread it into the `rows()` calc as `influence_dependence(isa,
  split=input.split())`. The plot's dashed cross-hair lines and the table follow
  automatically (they already read the returned threshold/quadrants).
- **Skew flag (the data-triggered warning, from A's review):** a pure helper
  (e.g. `influence_skew(isa)`) returning a bool when `max(influence) > k *
  median(influence)` (k ≈ 3, on non-zero nodes); the module shows a one-line
  "distribution is hub-skewed — consider median split" caption when true. This
  makes the median a *suggested* response to real data, not a blind toggle.
- i18n: ~4 keys (`quadrant.split`, `quadrant.split_mean`, `quadrant.split_median`,
  `quadrant.skew_warning`) × 9 languages.

**Tests:** unit — `influence_dependence(isa, split="median")` on a hub-skewed
fixture lands a tail node in a *different* quadrant than `split="mean"` (proves
the switch changes classification); `influence_skew` true on a skewed fixture,
false on a balanced one; default-still-mean (existing quadrant tests unchanged).
e2e — extend/clone the quadrant e2e: toggle the control, assert the quadrant
labels in the table change for at least one node.

**Decisions to confirm at spec time:** median tie-handling at the `>=` boundary
(median can equal a node's value); the skew-flag constant `k`; whether the skew
warning is always shown or only under mean. All small.

**Effort:** one brainstorm → spec → plan → execute cycle, ~the size of B2.

---

## Follow-up 2 — Multi-rater elicitation + disagreement view (C)

**Goal.** QSEM's core collaborative draw: let multiple stakeholders independently
rate the same connection (strength/confidence, possibly polarity), then show the
**aggregate** and the **disagreement** — SESPy's deepest gap (today a diagram is
single-author ground truth). This is a **schema-level** effort and **must be
brainstormed before any TDD plan**; below is the decomposition and the open
design questions that brainstorm must resolve, not a finished design.

### Open design questions (resolve in brainstorm)
1. **Schema shape.** Today `Connection` has scalar `strength`/`confidence`/
   `polarity`/`delay`. Options: (a) add a `ratings: list[Rating]` field (each
   `{rater, strength, confidence, polarity}`) and *derive* the scalar
   strength/confidence from it; (b) keep scalars as the "consensus" and add a
   parallel ratings store. (a) is cleaner but a bigger migration. **This is the
   pivotal decision** — it dictates persistence, import, and every analysis that
   reads `strength`/`confidence`.
2. **Migration / back-compat.** `PROJECT_SCHEMA_VERSION` bump + a loader that
   lifts existing single-author scalars into a one-rater list. Every reader of
   `strength`/`confidence` (`_edge_weight`, quadrant, leverage, metrics, simplify,
   loop weighting) must go through the derived consensus, not the raw list.
3. **Aggregation rule.** Mean? median? confidence-weighted mean? How is the
   consensus `strength`/`confidence` (and `delay`) derived from N ratings? How is
   *polarity disagreement* (some `+`, some `-`) represented — a "contested" flag?
4. **Rater identity.** Who is a rater — reuse the PIMS Stakeholders register
   (already in the app) as the rater list, or a lightweight name field? Reusing
   PIMS stakeholders is the natural fit and avoids a second identity concept.
5. **Disagreement view.** How to surface divergence: a per-connection
   spread/variance column, a "contested edges" filter, edge styling (e.g.
   thickness/colour by disagreement) — composes with the existing
   polarity-colour + dashed-delay cues, so pick a *free* channel.
6. **Elicitation UI.** Where stakeholders enter ratings — extend the data-entry
   connection form, a dedicated "rate connections" module, or per-stakeholder
   sessions (URL-scoped, like the bookmarking already in the app).
7. **Scope floor (YAGNI).** Minimum viable: store N ratings per connection,
   derive consensus, show mean + a disagreement indicator. Defer live
   multi-session collaboration / real-time sync (out of scope; SESPy is local).

### Proposed chunk decomposition (each its own spec → plan → execute)
- **C1 — Ratings data model + migration.** Schema change (resolve Q1/Q2),
  `PROJECT_SCHEMA_VERSION` bump, loader lift, derived-consensus accessor that all
  existing analyses route through (so `_edge_weight` etc. are unchanged in
  behaviour for single-rater data). Pure/data layer + persistence + import.
  **No UI.** This is the foundation and the riskiest chunk (touches every reader).
- **C2 — Elicitation UI.** Let stakeholders add/edit their own rating of a
  connection (resolve Q4/Q6), persisted via C1. Reuse PIMS stakeholders as raters.
- **C3 — Aggregation + disagreement view.** Consensus derivation (Q3) surfaced in
  the connection table + a disagreement indicator / "contested edges" view (Q5).
  This is where the QSEM collaborative value becomes visible.
- **(Optional) C4 — disagreement-aware analysis.** Feed contestedness into the
  existing analyses (e.g. flag loops/quadrant nodes that hinge on contested edges).
  Defer until C1–C3 prove the value.

**Effort:** a multi-cycle sub-project. **Start with a dedicated brainstorm on C1**
(the schema decision) — do not write a TDD plan until Q1/Q2/Q3 are settled, because
the schema choice determines everything downstream.

---

## Recommended sequence
1. **Median toggle** — brainstorm (brief) → spec → plan → execute → merge. Small,
   closes out the quadrant.
2. **C1 ratings schema** — full brainstorm (the schema decision) → spec → plan →
   execute. Then C2, then C3, each its own cycle.

Pushing note: `main` is currently 9 commits ahead of `origin/main` (B2 unpushed);
push B2 before starting new feature branches to keep origin current.
