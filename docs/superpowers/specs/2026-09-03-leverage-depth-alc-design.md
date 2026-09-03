# Leverage depth + Adjusted Loop Centrality — design

**Issue:** [#23](https://github.com/razinkele/SESPy/issues/23), plus the ALC
part of [#22](https://github.com/razinkele/SESPy/issues/22) (which shipped in
v1.4.0 without it).

**Status:** design approved 2026-09-03. Implementation plan not yet written.

---

## Why this is not the issue as filed

#23 proposes a `leverage_depth` column classifying each node by intervention
depth: *parameter → feedback structure → rules → goals/paradigm*.

SESPy already ships that ladder. `leverage_realm(element_type)`
(`sespy/network.py:684`) returns `parameters | feedbacks | design | intent`
from `_DAPSIWRM_REALM` (`:673-681`), and the Leverage module already displays
it as a translated "realm" column (`sespy/modules/analysis_leverage.py:154`,
`:160`). Implemented verbatim, #23 would put a second Meadows ladder beside
the first — and the two **disagree**:

| Element type | shipped `leverage_realm()` | #23 as filed |
|---|---|---|
| Pressures | `parameters` | parameter ✓ |
| Marine Processes & Functioning | `feedbacks` | **parameter** ✗ |
| Activities | `design` | **feedback structure** ✗ |
| Responses | `design` | rules (same idea, different label) |
| Drivers | `intent` | goals / paradigm (same idea) |

Two rows differ substantively, and this design treats them differently:
**Activities** is where #23 is *right* — its position is adopted, conditionally, as the structural rule below. **Marine Processes & Functioning** is a genuine unresolved disagreement, and this design keeps the shipped `feedbacks`. The remaining rows are the same concept under different labels. This is the reconciliation the issue was deferred over.

**What is genuinely new in #23's framing is that depth should be structural,
not purely type-based** — "an Activity *inside a loop* → feedback structure".
`leverage_realm()` is a pure function of element type and cannot express that.

**Decision:** keep one classification and give it the thing it lacks. No
second column, no competing ladder.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | One classification, made structural | Two near-identical Meadows columns that disagree is worse than either alone. |
| 2 | Non-breaking sibling functions | `leverage_scores()` is consumed by MosaicSES (through an explicit import allowlist), `sespy/report.py:203`, `cascade_vulnerability` (`sespy/network.py:563`), `uncertainty_scores`' perturbation loop (`sespy/network.py:1254`) and the Leverage module. The composite is not changing — only what is displayed beside it. |

| 3 | ALC is polarity-signed | Collapsing reinforcing and balancing into one magnitude discards the distinction that makes loop-based leverage worth having. |

> **Note for the implementer:** `build/` is git-ignored but present in the
> working tree and holds a stale copy of the package. A bare
> `grep -rn leverage_scores .` returns `build/lib/sespy/...` hits with line
> numbers that do not match the source tree — one such number reached the
> first draft of this spec. Scope greps to `sespy/` and `tests/`.

## The library

Three additions to `sespy/network.py`, all pure and translation-free.

### 1. `loop_gain(cycle, M, pos) -> float`

`loop_dominance` already computes a structural gain inline
(`sespy/network.py:226-231`): the product of numeric-matrix entries around the
cycle, then `abs()`. Lift it into one helper and let both callers use it.

```python
def loop_gain(cycle: list[str], M, pos: dict[str, int]) -> float:
    """Signed product of the edge weights around `cycle`.

    Takes the PREPARED matrix and its id->index mapping, not an IsaData: the
    matrix is built once per call site and shared across every cycle. A
    `loop_gain(cycle, isa)` signature would rebuild it per cycle, undoing the
    sharing the rest of this design exists to get.

    `M` must be the same matrix `loop_dominance` uses. v1.4.0 fixed a
    direction bug in which isa_to_dynamics_matrix is the TRANSPOSE of
    isa_to_numeric_matrix; passing the wrong one silently changes every gain.
    """
```

`loop_dominance` becomes `abs(loop_gain(...))` over the matrix it already
builds — arithmetically identical, no behaviour change. ALC uses the signed
value directly.

This is the same "one definition, two views" arrangement the file already
documents for `governance_actor_influence` re-deriving the leverage composite.

**How far the "sign is the polarity" claim actually goes.** For a cycle whose
edges are each a single connection, an even number of negative edges gives a
positive product — the same verdict `loop_polarity()` reaches. Two exceptions
must not be papered over:

- **Parallel edges.** The numeric matrix *sums* the signed weights of
  connections sharing a `(source, target)` pair, while `loop_polarity()` reads
  a last-wins dict (`_edge_polarity_lookup`). On a model with duplicate edges
  the two can disagree outright.
- **A zero product carries no sign at all.** Cancelling parallel edges make
  the entry — and so the gain — exactly `0.0`, which is neither reinforcing
  nor balancing.

The property test in Testing item 1 is therefore scoped to fixtures without
parallel edges, and the disagreement is documented rather than asserted away.

### 2. `adjusted_loop_centrality(isa, *, cycles=None) -> dict[str, float]`

```
ALC(n) = Σ over loops L containing n of loop_gain(L)
```

- **positive** — the node sits in amplifying structure
- **negative** — the node sits in damping structure
- **`0.0`** — the node is in no detected loop, **or** its loop gains cancel

Every node in the ISA appears in the mapping, so it aligns key-for-key with
`leverage_scores()`.

`cycles=` mirrors the existing parameter on `loop_dominance`: it lets a caller
enumerate loops once and share them, and it makes the function testable with
injected cycles. When omitted, the function calls `feedback_loops(isa)` with
its shipped bounds.

#### Truncation makes the sign non-deterministic — this must be handled

`feedback_loops()` caps enumeration at `max_loops=50`. Its own docstring
(`sespy/network.py:52-59`) warns that the bounded Gupta–Suzumura path has no
documented ordering guarantee, and `_canonical_cycles`' docstring (`:70-88`)
records that `nx.simple_cycles`' order varies with hash seeding. Above the cap,
*which* 50 cycles come back therefore varies between processes.

For `loop_dominance` that is survivable: it takes `abs()`, so there is no sign
to flip. For ALC it is not. Measured on a 14-node p=0.25 signed digraph that
returns exactly 50 cycles, the same node's ALC across five separate
interpreter runs was `+290 / +1172 / −382 / +1172 / +381` — the **sign flips**.
The Leverage table would report "amplifying" or "damping" for the same node
depending on which app restart the reader is looking at.

This is latent rather than shipped — every bundled model is under the cap
(`Food_web_V_00` and `Food_web_V_01` return 42 cycles, `qsem-model-2026-01-12 (3)`
returns 43) — but a marginally denser user model crosses it.

**Resolution.** `adjusted_loop_centrality` returns its scores **and** a
truncation flag; the Leverage module suppresses the ALC column and shows a
short note when the flag is set, rather than printing a number whose sign is
unstable. Concretely, the function grows a companion:

```python
def alc_is_truncated(isa, *, cycles=None) -> bool:
    """True when the detected loop set hit feedback_loops()' max_loops cap,
    so an ALC sum over it is not reproducible across processes."""
```

**Rejected alternative:** canonicalising or sorting the cycles before the cap.
`_canonical_cycles`' docstring forbids exactly this — "Do not sort before the
max_loops cap: that would require enumerating every eligible cycle and defeat
the length_bound tractability fix (#18 — >5 min unbounded vs ~10 ms bounded)."
Raising the cap for this path only would reintroduce the same cost.

### 3. `leverage_realms(isa, *, cycles=None) -> dict[str, str]`

Returns the realm token for every node. Exactly one rule is layered on top of
`leverage_realm(element_type)`:

> An **Activity** that participates in a detected feedback loop reports
> `feedbacks` instead of `design`. Every other type, and an Activity in no
> loop, is unchanged.

`leverage_realm(element_type)` itself stays exactly as it is — pure, type-only,
still used wherever a type alone is all that is available.

**Everything that references the realm concept, and why none of it moves:**
`analysis_leverage.py:154` is the only code caller and is the one line this
design changes. `sespy/network.py:772` refers to the "highest-leverage
'intent' realm per `leverage_realm`" in `governance_gap`'s docstring — a
*documentation* reference to the type-based function, which is unchanged, so
it stays accurate. No test pins realm output for an Activity.

**Why a mapping rather than the `leverage_realm_for(isa, node_id)` shape
sketched during brainstorming:** both this and ALC need `feedback_loops()`,
which is bounded but not free. A per-node call would re-enumerate the loop set
for every row of the table. A mapping computes once and matches the shape of
`leverage_scores()` and `adjusted_loop_centrality()`.

### Degenerate cases

| Case | Behaviour |
|---|---|
| No loops detected | Every realm falls back to the type-based mapping; ALC is `0.0` for every node. |
| Unknown element type (e.g. `Measures`) | `""`, exactly as `leverage_realm()` does today. |
| Cancelling parallel edges | The summed matrix entry is `0.0`, so that loop's gain is `0.0` and contributes nothing. (An *all-zero-strength* model is NOT reachable: `_STRENGTH_RANK` is `{weak:1, medium:2, strong:3}` — `sespy/network.py:983` — and has no zero.) |
| Empty ISA | Empty mappings. No error. |

## The Leverage module

`sespy/modules/analysis_leverage.py`:

- `ranked()` (`:146-163`) enumerates loops once and passes the same list to
  both `leverage_realms(isa, cycles=…)` and
  `adjusted_loop_centrality(isa, cycles=…)`, replacing the per-row
  `leverage_realm(el.type)` call at `:154`.
- `alc` joins `base_cols` (`:208`) between `realm` and `leverage`, rounded to
  3dp. That is display consistency only, NOT comparability: `leverage` is a
  sum of three z-scores (roughly -3..+8), while ALC is a sum of raw signed
  gain products whose magnitude scales with loop count and edge strength and
  is unbounded. The two columns must not be read against each other. The uncertainty path (`:217-227`) extends
  `base_cols` rather than replacing it, so it inherits the column.

## i18n

Almost nothing, which is worth stating because #22 cost 81 strings across nine
languages.

- Realm **values** are already translated in all nine:
  `leverage.realm.{parameters,feedbacks,design,intent}`
  (`sespy/translations/core.json:5500-5503`). The structural rule reuses the
  **existing** `feedbacks` token and introduces no new realm.
- Column **headers** are mixed: `base_cols` are untranslated DataFrame keys
  (`rank`, `id`, `label`, …), but the uncertainty path appends *translated*
  ones — `t("uncertainty.ci")` and `t("uncertainty.unstable")`
  (`analysis_leverage.py:222-224`). `alc` joins `base_cols`, so it follows
  the untranslated convention and needs no key. Translating it later is not
  precluded; it would simply move it out of `base_cols`.
- **One new key**: a caption, in all nine languages, covering BOTH new
  behaviours. A signed number with no explanation is a trap — a reader will
  read negative as "bad" rather than "damping". The realm split needs the
  same courtesy: after this change two Activities can show *different*
  realms with no visible cause, because one is in a detected loop and the
  other is not. The caption must say so, or the column looks broken.

## Testing

Load-bearing first.

1. **`loop_gain`'s sign equals `loop_polarity`'s verdict** on every shipped
   fixture. A property test tying the two definitions together so they cannot
   drift apart.
2. **`loop_dominance`'s existing tests must still pass, but do not lean on
   them.** They live in `tests/test_network.py:1569-1866` — 33 references,
   and **zero** in `tests/test_dynamics.py`. They are assertions, not
   goldens, and no RNG is involved (the trajectory is passed in). The PCG64
   goldens in `tests/test_dynamics.py` belong to `token_diffusion`, not to
   `loop_dominance`; an earlier draft of this spec attributed them wrongly.

   They are a weak net for exactly the two errors this refactor can introduce:

   - **Sign errors are invisible to them.** `loop_dominance` takes `abs()`, so
     a flipped sign in `loop_gain` never reaches one of its assertions. Sign
     correctness rests *entirely* on Testing item 1.
   - **Transpose errors are nearly invisible.** On a 2-cycle the numeric
     matrix and its transpose give the identical product, and every
     `loop_dominance` fixture is a 2-cycle except one. The sole transpose
     guard in the suite is `test_loop_dominance_length_comparability`'s
     3-cycle assertion (`:1593`), where the two orientations measurably
     differ. Add a direct `loop_gain` test on a 3-cycle rather than relying
     on it.
3. `adjusted_loop_centrality`: a node in no loop is exactly `0.0`; in a
   reinforcing loop, positive; in a balancing loop, negative; in both, the
   signed sum.
4. `leverage_realms`: an Activity in a loop reports `feedbacks`; the same
   Activity with the loop edge removed reports `design`; and for every
   non-Activity type it agrees with `leverage_realm()` exactly.
5. Module: `alc` present in `base_cols`. E2e: the Leverage panel renders.

Gate: the CI ignore-set unit suite (baseline **559**), then the full e2e
(**32/32**), then MosaicSES (**526**) — which must be unaffected, since
`leverage_scores()` does not change.

## Assumptions and risks

- **The depth semantics are unverified against their source.** #23's own text
  records that the Geekiyanage abstract was never returned by the literature
  API. The structural rule is defensible on Meadows' own terms — a variable
  inside a feedback loop acts at the feedback level, not the parameter level —
  but it is a documented assumption, not fidelity to the paper. Re-check when
  the full text is reachable.
- **ALC's formula is likewise reconstructed**, from #22's one-line description
  ("loop strength, and whether the node initiates or reinforces"). This design
  implements loop strength and polarity; it does **not** model whether a node
  *initiates* versus *reinforces* a loop, which the description mentions and
  which would need a node-role notion the codebase does not have. Recorded as
  a deliberate gap, not an oversight.
- `_DAPSIWRM_REALM` stays hard-coded. #23 asks for a configurable mapping
  table; the existing dict is already the single source of truth and is
  editable in one place. Making it runtime-configurable is deferred until
  something actually needs to vary it.

## Out of scope

- Changing `leverage_scores()`, the composite formula, or
  `governance_actor_influence`'s golden equality with it.
- A `leverage_table()` convenience function returning composite + ALC + realm
  in one call. Rejected under YAGNI: it creates two supported paths to the
  same number that must be kept in agreement.
- #24 (cross-tier hypermodule detection) — separate issue, separate design.
- Any MosaicSES change. It consumes `leverage_scores()`, which is untouched.
- **Sorting the table by realm.** #23 asks to "allow sorting by it". The
  Leverage table is a `render.data_frame` whose sort affordances are the
  grid's own; no bespoke sort control is added here. Named explicitly because
  it is a stated part of the issue, not an oversight.
- **Re-classifying `Measures`.** #23 maps "Measure / response node → rules";
  `_DAPSIWRM_REALM` has no `Measures` entry, so it returns `""` today and
  still will. Adding it is a change to the shipped type mapping, which
  Decision 1 deliberately leaves alone. A departure from the issue, recorded.
