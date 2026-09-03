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

Two of seven conflict outright. This is the reconciliation the issue was
deferred over.

**What is genuinely new in #23's framing is that depth should be structural,
not purely type-based** — "an Activity *inside a loop* → feedback structure".
`leverage_realm()` is a pure function of element type and cannot express that.

**Decision:** keep one classification and give it the thing it lacks. No
second column, no competing ladder.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | One classification, made structural | Two near-identical Meadows columns that disagree is worse than either alone. |
| 2 | Non-breaking sibling functions | `leverage_scores()` is consumed by MosaicSES (through an explicit import allowlist), `sespy/report.py:203`, `cascade_vulnerability` (`sespy/network.py:563`) and the Leverage module. The composite is not changing — only what is displayed beside it. |

> **Note for the implementer:** `build/` is git-ignored but present in the
> working tree and holds a stale copy of the package. A bare
> `grep -rn leverage_scores .` returns `build/lib/sespy/...` hits with line
> numbers that do not match the source tree — one such number reached the
> first draft of this spec. Scope greps to `sespy/` and `tests/`.
| 3 | ALC is polarity-signed | Collapsing reinforcing and balancing into one magnitude discards the distinction that makes loop-based leverage worth having. |

## The library

Three additions to `sespy/network.py`, all pure and translation-free.

### 1. `loop_gain(cycle, isa) -> float`

`loop_dominance` already computes a structural gain inline
(`sespy/network.py:226-231`): the product of numeric-matrix entries around the
cycle, then `abs()`. Lift it into one helper and let both callers use it.

```python
def loop_gain(cycle: list[str], isa: IsaData) -> float:
    """Signed product of the edge weights around `cycle`.

    The SIGN is the polarity: an even number of negative edges gives a
    positive product, which is exactly loop_polarity()'s rule. Callers that
    want magnitude only take abs().
    """
```

`loop_dominance` becomes `abs(loop_gain(...))` — arithmetically identical, no
behaviour change. ALC uses the signed value directly.

This is the same "one definition, two views" arrangement the file already
documents for `governance_actor_influence` re-deriving the leverage composite.

### 2. `adjusted_loop_centrality(isa, *, cycles=None) -> dict[str, float]`

```
ALC(n) = Σ over loops L containing n of loop_gain(L)
```

- **positive** — the node sits in amplifying structure
- **negative** — the node sits in damping structure
- **`0.0`** — the node is in no detected loop

Every node in the ISA appears in the mapping, so it aligns key-for-key with
`leverage_scores()`.

`cycles=` mirrors the existing parameter on `loop_dominance`: it lets a caller
enumerate loops once and share them, and it makes the function testable with
injected cycles. When omitted, the function calls `feedback_loops(isa)` with
its shipped bounds.

### 3. `leverage_realms(isa, *, cycles=None) -> dict[str, str]`

Returns the realm token for every node. Exactly one rule is layered on top of
`leverage_realm(element_type)`:

> An **Activity** that participates in a detected feedback loop reports
> `feedbacks` instead of `design`. Every other type, and an Activity in no
> loop, is unchanged.

`leverage_realm(element_type)` itself stays exactly as it is — pure, type-only,
still used wherever a type alone is all that is available.

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
| All edge strengths zero | ALC is `0.0` throughout. No error. |
| Empty ISA | Empty mappings. No error. |

## The Leverage module

`sespy/modules/analysis_leverage.py`:

- `ranked()` (`:148-163`) enumerates loops once and passes the same list to
  both `leverage_realms(isa, cycles=…)` and
  `adjusted_loop_centrality(isa, cycles=…)`, replacing the per-row
  `leverage_realm(el.type)` call at `:154`.
- `alc` joins `base_cols` (`:208`) between `realm` and `leverage`, rounded to
  3dp to match `leverage`. The uncertainty path (`:217-227`) extends
  `base_cols` rather than replacing it, so it inherits the column.

## i18n

Almost nothing, which is worth stating because #22 cost 81 strings across nine
languages.

- Realm **values** are already translated in all nine:
  `leverage.realm.{parameters,feedbacks,design,intent}`
  (`sespy/translations/core.json:5500-5503`). The structural rule reuses the
  **existing** `feedbacks` token and introduces no new realm.
- Column **headers** are untranslated DataFrame keys (`rank`, `id`, `label`,
  …), so `alc` follows that convention and needs no key.
- **One new key**: a caption explaining ALC's sign, in all nine languages. A
  signed number with no explanation is a trap — a reader will read negative as
  "bad" rather than "damping".

## Testing

Load-bearing first.

1. **`loop_gain`'s sign equals `loop_polarity`'s verdict** on every shipped
   fixture. A property test tying the two definitions together so they cannot
   drift apart.
2. **`loop_dominance`'s goldens must not move.** The refactor swaps an inline
   product for `abs(loop_gain(...))`. Those goldens pin a numpy PCG64 stream
   and are the most fragile asset in `tests/test_dynamics.py`. If they move,
   the refactor is wrong — do not re-baseline them.
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
