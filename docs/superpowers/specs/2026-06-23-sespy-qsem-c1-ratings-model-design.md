# QSEM-C1 — Multi-rater ratings model + migration (design)

**Date:** 2026-06-23
**Status:** approved (brainstorm)
**Sub-project:** C1 of QSEM-C (multi-rater elicitation). C2 (elicitation UI) and
C3 (aggregation surfacing + contested view) follow as separate cycles.
**Roadmap:** `docs/superpowers/2026-06-22-qsem-followups-roadmap.md` (Follow-up 2).

## Problem

A SESPy diagram is single-author ground truth: each `Connection` carries scalar
`strength`/`confidence`/`polarity`/`delay`. QSEM's collaborative core is letting
multiple stakeholders independently rate the same connection and then seeing the
consensus *and* the disagreement. C1 lays the data foundation: store N ratings per
connection and derive a consensus, **without changing any existing behaviour** for
single-author projects. No UI in this chunk.

## Decisions (from brainstorm)

**Schema shape (Q1): materialized-consensus cache.** Keep the scalar
`strength`/`confidence`/`polarity`/`delay` on `Connection` as the *consensus*, and
add a `ratings: list[Rating]` field. The scalars are a **materialization** of the
ratings: a single `recompute_consensus()` is their *only* writer. This leaves all
~7 existing readers (`_edge_weight`, quadrant, leverage, metrics, simplify, loops,
`uncertainty_scores`) byte-for-byte unchanged — they keep reading the scalars.
Rejected: removing the scalars and deriving on every read (option a) — it ripples a
derived accessor through every analysis call-site for no behavioural gain.

**Migration (Q2): additive, no auto-lift.** Old projects load with `ratings=[]` and
their authored scalars untouched; `recompute_consensus` is a no-op on empty ratings.
No synthetic one-rater list is created for legacy authors (avoids inventing a fake
`rater_id`). `PROJECT_SCHEMA_VERSION` 5 → 6. The loader already filters unknown keys
for metadata/stakeholders; connections get the same treatment.

**Aggregation rule (Q3)** — what `recompute_consensus(connection)` computes when
`ratings` is non-empty:
- **confidence** → arithmetic mean of the N confidences, rounded to nearest int,
  clamped to [1, 5].
- **strength** → confidence-weighted mean of strength ranks
  (`weak/medium/strong = 1/2/3`, reusing `network._STRENGTH_RANK`), rounded to the
  nearest rank and mapped back to a category. If total confidence weight is 0, use a
  plain (unweighted) mean of ranks.
- **polarity** → majority sign; an exact tie resolves to `"+"` (the existing
  `Connection.polarity` default).
- **delay** → mode (most frequent value); ties broken by first occurrence.
- **empty ratings** → no-op (scalars left exactly as authored).

**Disagreement (part of Q3/Q5, foundation only):** a pure
`connection_disagreement(connection)` helper, computed on demand (not stored), that
C3 will surface.

## Architecture / components

### `sespy/data_structure.py`
- New `@dataclass Rating`:
  ```python
  @dataclass
  class Rating:
      rater_id: str                 # keyed to Stakeholder.id (free-form for now)
      strength: str = "medium"      # weak | medium | strong
      confidence: int = 3
      polarity: str = "+"           # "+" | "-"
      delay: str = "immediate"
  ```
- `Connection` gains `ratings: list[Rating] = field(default_factory=list)` (after
  the existing scalar fields, so positional construction in existing code/tests is
  unaffected).
- `PROJECT_SCHEMA_VERSION = 6`.
- `_isa_from_dict` must hydrate nested ratings — `Connection(**c)` would set
  `ratings` to a list of raw dicts, not `Rating` objects. Pop `ratings` from each
  connection dict, build `Rating(**r)` (filtering unknown keys, mirroring the
  Stakeholder pattern), and pass the rebuilt list. Unknown top-level connection keys
  are likewise filtered so forward-saved files load.
- `to_dict` is unchanged: `asdict(connection)` already recurses into the `ratings`
  list of dataclasses.

### `sespy/network.py`
- `recompute_consensus(connection: Connection) -> Connection` — **pure**; returns a
  copy (`dataclasses.replace`) with the four scalar fields rewritten from `ratings`
  per the aggregation rule. No-op (returns an equivalent copy) when `ratings` is
  empty. The sole writer of the consensus scalars.
- `connection_disagreement(connection: Connection) -> dict` — **pure**; returns
  `{"polarity_contested": bool, "strength_spread": float, "confidence_spread": float}`.
  `polarity_contested` is True when the ratings are not unanimous in sign (False for
  0 or 1 rating). `strength_spread` = max−min of strength ranks; `confidence_spread`
  = max−min of confidences. Both 0.0 for <2 ratings.

These live in `network.py` beside `_edge_weight`/`_STRENGTH_RANK` (the strength-rank
vocabulary they share), keeping `data_structure.py` a pure data tree with no
analysis logic.

## Data flow

Load: JSON → `_isa_from_dict` hydrates `Connection.ratings` as `Rating` objects (or
`[]`). Analyses read the consensus scalars exactly as today. Save: `asdict` writes
the ratings list back. `recompute_consensus` is invoked by the *writer* (C2/C3, when
a rating is added/edited) — C1 only provides the function and its tests; nothing in
C1 calls it automatically, so single-author projects never trigger it.

## Error handling / edge cases

- Empty `ratings`: `recompute_consensus` returns an equivalent connection (scalars
  unchanged); `connection_disagreement` returns all-zero / not-contested.
- One rating: consensus equals that rating's values; not contested.
- Unknown keys in a serialized `Rating`/`Connection` are filtered on load (no crash
  on forward-compat files).
- Confidence values outside [1,5] in a rating are clamped when averaging (mirrors
  `_edge_weight`'s existing clamp).
- Unknown `strength` string in a rating ranks as `medium` (mirrors
  `_STRENGTH_RANK.get(s, 2)`).

## Testing

`tests/test_data_structure.py` (or the existing persistence test file):
- **Round-trip:** a Project with a connection carrying ≥2 `Rating`s saves
  (`to_json`) and loads (`from_json`) to an equal object (ratings are `Rating`
  instances, not dicts).
- **v5 back-compat:** a JSON blob with no `ratings` key and `schema_version: 5`
  loads with `ratings == []`, scalars unchanged, and `schema_version` stamped to 6.
- **No behavioural change:** an existing single-author sample loads and
  `_edge_weight`/`influence_dependence`/`leverage_scores` produce identical results
  to before (ratings empty ⇒ untouched scalars).

`tests/test_network.py`:
- **`recompute_consensus` golden values:** confidence-weighted strength (a
  high-confidence "strong" outweighs a low-confidence "weak"); mean confidence
  rounding; polarity majority; polarity exact tie → "+"; delay mode; empty-ratings
  no-op.
- **`connection_disagreement`:** +/− split → `polarity_contested True`; unanimous →
  False; <2 ratings → False and zero spreads; strength/confidence spread values on a
  known fixture.

## Out of scope (later chunks)

- C2: elicitation UI; the writer that calls `recompute_consensus` on rating
  add/edit; reusing the PIMS Stakeholders register as the rater list (Q4/Q6).
- C3: surfacing consensus + a contested-edges view / disagreement column (Q5),
  using `connection_disagreement`.
- C4 (optional): disagreement-aware analyses (flag loops/quadrant nodes hinging on
  contested edges).
- Live multi-session / real-time sync — explicitly out of scope (SESPy is local).
