# MosaicSES Phase-2 — Emerald Justice Equity Overlay — Design

**Repository:** `razinkele/MosaicSES` (code location: `multises/` library + `multises_app/modules/comparative.py`; this spec + its plan live in `razinkele/SESPy` `docs/superpowers/`).

**Date:** 2026-06-13
**Status:** **Planned** — not yet implemented. (Revised after a 4-angle review: code-integration, scientific/domain, test-readiness, design-consistency.)
**Parent spec:** [`2026-05-08-mosaicses-design.md`](2026-05-08-mosaicses-design.md) §11 item #20; alignment matrix [`2026-05-09-mosaicses-scientific-basis.md`](2026-05-09-mosaicses-scientific-basis.md) §8a (`equity_dimensions` deferred row) and §2.0 (Emerald Justice as parallel EG concept).
**Sibling increment / template:** [`2026-06-09-mosaicses-phase2-tenets-design.md`](2026-06-09-mosaicses-phase2-tenets-design.md) (#19, first Phase-2 increment) — this increment mirrors its shape (overlay field + analysis + read-only comparative card + Curonian seed).
**Phase-2 item:** #20 (second Phase-2 increment).

## 1. Goal & scope

Add **Emerald Justice equity dimensions** — the equity layer that Maciej Nyka and the user's research group are developing on top of Emerald Growth (scientific basis §2.0, §8a) — as an **evaluative overlay** over the human-relevant *outcome* elements of the DAPSI(W)R(M) chain, plus an **equity-exposure lens** on the existing `response_pressure_gap()` analysis and a read-only **Emerald Justice exposure** card in the Comparative dashboard. This operationalises the analytical claim that management Pressures should be **screened for potential exposure to equity-flagged outcomes**: which ungoverned Pressures have a graph-path to an outcome element that carries an equity concern.

The equity dimensions (canonical set from parent spec §11 #20, **extended** here with a sixth — see §3.1):

1. Ocean grabbing
2. Livelihood displacement
3. Gender inequity
4. Indigenous rights
5. Exclusion from decision-making
6. **Cultural heritage loss** *(added this increment; a deviation from Nyka's canonical 5 — flagged for his sign-off, see §3.1)*

Each outcome element may carry **zero or more** dimensions (a set, not a 1–5 score — unlike the tenet scale). An equity-flagged outcome reachable downstream from an ungoverned Pressure is the headline screening signal.

### 1.1 In scope

- A canonical `EQUITY_DIMENSIONS` vocabulary (6 slugs + display labels) in the `multises` library.
- `Compartment.outcome_equity_dimensions: dict[str, list[str]] | None` — a MosaicSES **overlay** keyed by *outcome* element id (type `"Ecosystem Services"` = Impact, **or** type `"Goods & Benefits"` = Welfare), so SESPy's `Element` is **NOT modified** (see §2).
- Validation: hard intrinsic invariant (each value a list of slugs ∈ `EQUITY_SLUGS`, no duplicates; empty list allowed) in `Compartment.__post_init__`; soft referential invariant (id resolves to a real outcome element) in the `validate(ms)` pass.
- `MULTISES_SCHEMA_VERSION` stays **1** — no schema bump; additive optional field loaded via `.get()` defaults (see §3.4). Lossless `to_dict`/`from_dict` round-trip, plus preservation through `replace_compartment` (see §3.5).
- **Augmentation** of `response_pressure_gap(ms)` in `multises/comparative.py` with three equity-exposure columns (see §4).
- A read-only **Emerald Justice exposure** card in `multises_app/modules/comparative.py`.
- Example equity dimensions seeded onto a small number of Curonian outcome elements so the panel is non-empty on the demo seed.
- Unit tests (library + module) and a comparative e2e assertion.

### 1.2 Out of scope (deferred)

- Editing equity dimensions in the UI (this increment is **read-only** display; an editor is a later increment, mirroring how #19 shipped read-only before any edit UI).
- Promoting `equity_dimensions` onto SESPy's `Element` (see §2 — rejected for this increment).
- **Forward-causal-limb-only reachability** (restricting the walk to Driver→Activity→Pressure→State→Impact→Welfare and excluding feedback back-edges + ignoring polarity). v1 uses plain directed reachability and *documents* the coarseness; a polarity/edge-type-aware walk is a future refinement (§11).
- Equity *weighting* or a composite equity index (a single defensible default — presence/absence of dimensions + downstream reachability).
- Wider Emerald Justice EG-monograph deliverables beyond this overlay + lens + seed (#22 monograph items, CCS #24 remain separate increments).

## 2. Key design decision — equity as a MosaicSES overlay on *outcome* elements (SESPy untouched)

### 2.1 Overlay, not Element modification (same fork & resolution as #19)

§11 #20 task (a) says "add `equity_dimension: list[str] | None` to `Element` (Impact type)." `Element` is a **SESPy** type (`sespy.data_structure.Element`), shared with the SESPy app. This is the same fork #19 faced, with the same resolution:

- **Option A — modify SESPy `Element`.** Bump `PROJECT_SCHEMA_VERSION` (5 → 6), ripple through SESPy app + tests. High blast radius for an evaluative field only MosaicSES consumes.
- **Option B — MosaicSES overlay (CHOSEN).** Store equity dimensions on the MosaicSES `Compartment` as `outcome_equity_dimensions: dict[str, list[str]]` (outcome element id → list of equity slugs). SESPy untouched.

**Decision: Option B**, per the scientific basis (§8a): *"evaluative dimensions are layers on top of an already-correct structural model."* Matches the `Compartment.response_tenet_scores` precedent (#19 §2).

### 2.2 What counts as an "outcome" element — attach to *both* the Impact and Welfare nodes

The scientific reviewer raised a substantive point: in DAPSI(W)R(M), equity harms are harms to **people**, which the framework reserves for the **Welfare** node ("Impacts on human Welfare" → Welfare). This codebase models the human-relevant end of the chain as **two distinct nodes** (`sespy/data_structure.py:41-48`, `ELEMENT_TYPE_MAP`):

- the `"impacts"` slug → display string **`"Ecosystem Services"`** (the impact-on-ecosystem-service-supply node), and
- the `"welfare"` slug → display string **`"Goods & Benefits"`** (the human-welfare node).

Backlog #20 literally says "Impact type," but the framework-faithful home for *who-is-harmed* is the Welfare node. **Decision (user, this increment): attach to BOTH.** An **outcome element** is any element with `type == "Ecosystem Services"` **or** `type == "Goods & Benefits"`. The overlay may flag either; the analysis (§4) collects equity exposure from whichever the Pressure reaches. This covers the ecological-supply impact and the human goods-&-benefits outcome in one signal, sidestepping the Impact-vs-Welfare attachment dispute while staying framework-aware.

**Implementation predicate (used in validation §3.3, analysis §4, seed §6):** `element.type in ("Ecosystem Services", "Goods & Benefits")`. This element-type predicate is the single fact most likely to be mis-coded; it is stated here and repeated where used. (Authoritative source: `ELEMENT_TYPE_MAP`, `sespy/data_structure.py:46-47`. Note: `response_pressure_gap` already filters on these display-string `type` values, e.g. `el.type == "Pressures"` at `multises/comparative.py:210`, so this predicate is consistent with existing code. The Impact seed *labels* live under the `default_es` arrays in `multises/archetypes.json`, but the type string itself is defined only by `ELEMENT_TYPE_MAP`.)

## 3. Data model

### 3.1 `EQUITY_DIMENSIONS` vocabulary (`multises/data_structure.py`)

```python
# Emerald Justice equity dimensions (Nyka & group; EG monograph; spec §11 #20).
# Order is load-bearing: it is the canonical display order. Slugs are stable
# ids; labels are display strings. The first five are Nyka's canonical set
# (parent §11 #20); `cultural_heritage` is added this increment (see note).
EQUITY_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("ocean_grabbing",          "Ocean grabbing"),
    ("livelihood_displacement", "Livelihood displacement"),
    ("gender_inequity",         "Gender inequity"),
    ("indigenous_rights",       "Indigenous rights"),
    ("decision_exclusion",      "Exclusion from decision-making"),
    ("cultural_heritage",       "Cultural heritage loss"),
)
EQUITY_SLUGS: tuple[str, ...] = tuple(slug for slug, _ in EQUITY_DIMENSIONS)
```

Add `EQUITY_DIMENSIONS`, `EQUITY_SLUGS` to the package `__all__` re-exports **and** to the `from .data_structure import (...)` block in `multises/__init__.py` (both places — the `TENETS`/`TENET_SLUGS` precedent appears in both).

**`cultural_heritage` provenance note (in scope to record, requires ratification):** the sixth dimension is added so the Curonian seed can express the cross-border Kursenieki / Klaipėda fisheries-heritage equity concern *without* mis-applying `indigenous_rights` (see §6 and the scientific review). It is a deviation from Nyka's canonical five and must be confirmed with him before any publication uses it; the spec records it as provisional. Adding it is additive (no schema bump) and reversible.

### 3.2 `Compartment.outcome_equity_dimensions` (overlay)

Add to `Compartment` alongside `response_tenet_scores` (`data_structure.py:376`):

```python
    # Phase-2 evaluative overlay: outcome element id -> [equity slugs].
    # Keys are sespy outcome element ids — type "Ecosystem Services" (Impact)
    # or "Goods & Benefits" (Welfare) — within this compartment's project.
    # Keys are unique within this compartment; global element-id uniqueness is
    # never assumed. None / absent = no outcomes flagged. SESPy Element is
    # deliberately NOT modified (evaluative layer; see design §2).
    outcome_equity_dimensions: dict[str, list[str]] | None = None
```

Data shape is `dict[str, list[str]]` (not `set`): JSON has no set type, the round-trip goes through `dataclasses.asdict`/`.get()`, and order is display-meaningful — a `list` with a no-duplicates hard invariant gives set-semantics without a non-serializable type (matches #19's `dict[str, int]`).

**Hard invariant** (intrinsic; runs in `Compartment.__post_init__`): a new module-level helper `_validate_equity_dimensions(dims, *, where)` — mirroring `_validate_tenet_scores` (`data_structure.py:173`) — raises `_ChannelValidationError` with a new `ErrorCode.M207_INVALID_EQUITY_DIMENSION` when, for any entry, the value is not a list, contains a slug ∉ `EQUITY_SLUGS`, or contains a duplicate slug. An **empty list is allowed** (an explicitly-flagged-but-empty outcome contributes nothing; the analysis treats it as unflagged — §4.2).

```python
        if self.outcome_equity_dimensions is not None:
            for eid, dims in self.outcome_equity_dimensions.items():
                _validate_equity_dimensions(
                    dims, where=f"Compartment {self.id!r} outcome {eid!r}")
```

(`_ChannelValidationError` is the generic hard-invariant carrier that holds an `ErrorCode` in `.code` despite its name — `_validate_tenet_scores` already reuses it from `Compartment.__post_init__`.)

### 3.3 Referential integrity (soft, validate-pass only)

The check that each key resolves to an actual outcome element (`type in ("Ecosystem Services", "Goods & Benefits")`) in this compartment's project is a **soft** invariant emitted by the dedicated `validate(ms)` pass — new code `ErrorCode.W305_EQUITY_DIM_UNKNOWN_ELEMENT` (W304 is taken by `W304_TENET_SCORE_UNKNOWN_RESPONSE`; W305 is free). A new `_check_equity_element_refs(ms)` is appended in `validate()` (`validate.py`, after the W304 `_check_tenet_response_refs` at ~line 167), mirroring W304 exactly but filtering on the outcome predicate. It is **not** emitted on the load path: `persistence.load()` / `MultiSES.from_json()` / `from_dict` do not run `validate()`, so the overlay survives an outcome-element deletion without hard-failing the load; callers wanting referential warnings call `validate(ms)` explicitly.

### 3.4 No schema bump — round-trip via additive optional field

**Decision: keep `MULTISES_SCHEMA_VERSION = 1` (no bump).** The new field is optional and loads via `.get(...)` defaults, exactly as `response_tenet_scores` (#19 §3.4). Bumping would emit a spurious `W400_SCHEMA_VERSION_MIGRATED` on every existing file/seed and break the tests asserting `MULTISES_SCHEMA_VERSION == 1` / `report.warnings == ()`.

- `Compartment` construction in `MultiSES.from_dict`: add `outcome_equity_dimensions=c_raw.get("outcome_equity_dimensions")` to the existing kwarg list (alongside `response_tenet_scores=c_raw.get(...)` at `data_structure.py:648`).
- `to_dict`: `MultiSES.to_dict` serializes compartments via `dataclasses.asdict` excluding only `{"project", "_unknown_archetype_original"}` (`_COMPARTMENT_EXCLUDE`, `data_structure.py:543`), so the new field **emits as `null` when unset** — no bespoke None-filtering.

### 3.5 Preserve the overlay through `replace_compartment` (pre-existing gap)

`MultiSES.replace_compartment` (`data_structure.py:803-811`) reconstructs a `Compartment` and currently **omits both `response_tenet_scores` and the new `outcome_equity_dimensions`**, so an in-compartment project swap silently drops the overlays (a pre-existing bug for `response_tenet_scores`, surfacing through the UI edit path). This increment adds `outcome_equity_dimensions=old.outcome_equity_dimensions` to that reconstruction; it also fixes the existing `response_tenet_scores` omission in the same edit (both are one-line additions, and a regression test guards them — §7).

## 4. Analysis — augment `response_pressure_gap(ms)`

Per the chosen approach, the equity lens is **added to the existing `response_pressure_gap`** (in `multises/comparative.py`) rather than a sibling function — coherent because both share the same row grain (**one row per Pressure element**).

### 4.1 Existing columns (today, for reference)

`response_pressure_gap` currently emits exactly (`comparative.py:223-230`): `compartment_id`, `pressure_id`, `pressure_label`, `within_compartment_response_count`, `incoming_governance_channel_count`, `pressure_compartment_has_no_governance`. The three equity columns are **appended after** these. (`within_compartment_response_count` is the per-Pressure-honest count of direct Response→Pressure connections; `incoming_governance_channel_count` is compartment-level and the existing docstring warns it is *not* per-Pressure.)

### 4.2 Reachability semantics (v1) and new columns

For each Pressure, compute the set of **outcome elements reachable downstream** within the compartment's own graph, then union their equity dimensions. Implementation uses a new module-private helper `_downstream_outcome_ids(isa_data, start_id)` built on the **already-imported** `sespy.network`:

```python
from sespy.network import to_digraph   # add to existing sespy.network imports
# g = to_digraph(isa_data); reachable = nx.descendants(g, start_id)
# return {eid for eid in reachable if elements[eid].type in OUTCOME_TYPES}
```

`nx.descendants` is **cycle-safe** (returns a set, terminates on the feedback cycles the DAPSI graph contains — `responses→pressures`, `welfare→drivers`, etc.) and reuses tested SESPy code instead of a hand-rolled BFS. The walk is **strictly downstream** (the start Pressure itself is excluded — `nx.descendants` never includes the source; a Pressure is never an outcome element anyway) and operates **only on the one compartment's `isa_data`** (cross-compartment Channels are never followed).

**Honesty caveat (documented in the augmented docstring + the UI disclaimer):** v1 reachability ignores connection **polarity** and **edge-type**, and traverses any directed path (including DAPSI feedback back-edges). So a column value means *"there exists a directed graph-path from this Pressure to an equity-flagged outcome"* — a **screening signal (where to look)**, **not** an attribution of harm. A forward-causal-limb-only, polarity-aware walk is a deferred refinement (§11). This mirrors #19's gap-first humility (`response_pressure_gap`/`tenet_gap_analysis` both document their v1 coarseness).

Three appended columns:

| column | type | meaning |
|---|---|---|
| `downstream_equity_outcome_count` | int | number of equity-flagged **outcome** elements reachable downstream from this Pressure (0 if none). An outcome whose dimension list is empty (`[]`) is **unflagged** and does NOT count. |
| `affected_equity_dimensions` | str | union of equity **slugs** over those reached outcomes, **alphabetically sorted**, comma-joined (`""` when none). Slugs (not labels) for deterministic, language-stable analysis output; the UI maps to display labels (§5). |
| `is_equity_relevant_orphan` | bool | `within_compartment_response_count == 0` **and** `downstream_equity_outcome_count > 0` |

`is_equity_relevant_orphan` is built **only** on the per-Pressure-honest `within_compartment_response_count` (never the misleading compartment-level governance count). Empty-list and unreachable both yield count 0 / `affected_equity_dimensions == ""`.

### 4.3 Column ordering & empty-frame behavior

Equity columns are appended after existing columns. The empty case is unchanged: `response_pressure_gap` returns a column-less empty frame when there are no Pressures (`comparative.py:231`); the equity columns appear only once there is ≥1 Pressure row.

## 5. UI — Comparative "Emerald Justice exposure" card

Add one card to `multises_app/modules/comparative.py`'s `comparative_ui`, after the "Response–Pressure gap" card (its source function), preserving the `comparative-card` class:

```python
ui.card(ui.card_header("Emerald Justice exposure"),
        ui.output_ui("equity_disclaimer"),
        ui.output_data_frame("equity_table"),
        class_="comparative-card"),
```

Server renders (read-only, reactive on `state.active_multises`):

- `equity_disclaimer` (`@render.ui`): a short caveat — "Screening signal only: a row means a Pressure has a directed graph-path to an equity-flagged outcome (an Impact or Goods-&-Benefits element); it does not establish that the Pressure causes that inequity. Reachability ignores edge polarity/type. 'Equity-relevant orphan' = a Pressure with no within-compartment Response that nonetheless reaches an equity-flagged outcome." Plus an empty-state hint when the slice is empty ("No equity-flagged outcomes reached in this MultiSES yet.").
- `equity_table` (`@render.data_frame`): `render.DataGrid` of `response_pressure_gap(ms)` **sliced** to columns `compartment_id`, `pressure_label`, `within_compartment_response_count`, `downstream_equity_outcome_count`, `affected_equity_dimensions`, `is_equity_relevant_orphan`; **filtered** to rows where `downstream_equity_outcome_count > 0`; **sorted** with `is_equity_relevant_orphan` rows first, then `compartment_id`, `pressure_label`. The `affected_equity_dimensions` cell is rendered with **slugs mapped to display labels** via `EQUITY_DIMENSIONS`, joined in **canonical `EQUITY_DIMENSIONS` order** (not the raw alpha-sorted slug string), so the panel reads in human terms (consistent with #19, which displays tenet labels).

No layout restructure, no new nav item, no new analysis function. The MosaicSES app is not i18n'd, so no translation keys.

**Card count:** the comparative dashboard goes from **6 → 7** `comparative-card`s (the tenet-readiness card took it 5 → 6 in #19; current count of 6 verified). Module and e2e count assertions must be updated (§7).

## 6. Seed data (Curonian)

Add example equity dimensions to the Curonian seed (`multises/curonian/curonian_loac.json`) so the panel is non-empty out of the box. **Two parts are required — the tags AND the connecting edges:**

1. **Flag 2–3 outcome elements** (`type in ("Ecosystem Services", "Goods & Benefits")`) with `outcome_equity_dimensions`, grounded in the transboundary LT/RU small-scale-fishery narrative already in the scientific basis (§2.0; the cci transboundary-friction context):
   - a fisheries-livelihood outcome → `livelihood_displacement` + `decision_exclusion`;
   - a heritage/identity outcome → **`cultural_heritage`** (NOT `indigenous_rights` — the Curonian Spit has no internationally-recognized indigenous people; the Kursenieki are a near-extinct ethnic minority and the appropriate frame is cultural-heritage, per the scientific review).
2. **Add the connecting directed edges** Pressure → … → flagged outcome in the seed's `connections`, because the seed's DAPSI defaults may be elements-only (no connections). At least one flagged outcome **must be downstream of a Pressure that has no within-compartment Response**, so the seed produces ≥1 `is_equity_relevant_orphan` row. (The lagoon's existing `R001→P001` Response→Pressure edge means a flagged outcome reached *from P001* would NOT be an orphan; hang the orphan demonstration off a different, un-responded Pressure.)

Dimensions are illustrative-but-defensible; the seed gains a short comment block marking them **demonstrative** (and noting `cultural_heritage` is provisional pending Nyka's ratification).

## 7. Testing

### Library unit tests (`tests/test_equity.py`, new — mirror `tests/test_tenets.py` idioms)

- `EQUITY_DIMENSIONS` has 6 entries; `EQUITY_SLUGS` length 6, unique, order stable.
- `Compartment(outcome_equity_dimensions={...valid...})` constructs; round-trips through `MultiSES.from_json(ms.to_json())` losslessly; an **unset** field serializes/reloads as `None` with **no** `W400`.
- `M207`: unknown slug, non-list value, and duplicate slug each raise `_ChannelValidationError` with `M207_INVALID_EQUITY_DIMENSION` from `__post_init__`; an **empty list** value is accepted.
- `W305` (via explicit `validate(ms)`, NOT on load): (a) id resolving to a real **Impact** (`Ecosystem Services`) element → **no** W305; (b) id resolving to a real **Welfare** (`Goods & Benefits`) element → **no** W305; (c) id resolving to a **non-outcome** element (e.g. a `Responses` or `Drivers` id) → **W305**; (d) id resolving to nothing → **W305**. Assert these surface only when `validate()` is called, not from `from_json`.
- `MULTISES_SCHEMA_VERSION == 1` (unchanged); a fixture with the field absent loads with `None` default.

### Analysis tests (`tests/test_comparative.py` — `response_pressure_gap` coverage, extend)

Hand-built MultiSES cases (reuse the existing per-compartment fixtures):
- **Orphan-with-equity:** Pressure with a directed path to an equity-flagged outcome and no within-compartment Response → `downstream_equity_outcome_count == 1`, `affected_equity_dimensions` == expected alpha-sorted slug string, `is_equity_relevant_orphan is True`.
- **Governed-with-equity:** same but the Pressure has a within-compartment Response → `is_equity_relevant_orphan is False`, count still > 0.
- **Reachable-but-unflagged / no-equity:** Pressure reaches an outcome with no overlay entry → count 0, `affected_equity_dimensions == ""`.
- **Empty-list outcome:** Pressure reaches only an outcome flagged with `[]` → count 0, `""` (empty list = unflagged).
- **Multi-outcome dedupe:** Pressure reaches two flagged outcomes with overlapping dims → union, deduped, alpha-sorted.
- **Both node types:** a flagged `Goods & Benefits` (Welfare) outcome is reached and counted (proves the Welfare half of the "both nodes" decision, not just Impact).
- **Cycle / self-loop termination:** a `Pressure→A→B→Pressure` cycle and a `P→P` self-loop both return (terminate) with correct counts — guards the cycle-safety of `_downstream_outcome_ids`.
- **Cross-compartment isolation:** Pressure in compartment A, flagged outcome in compartment B → count 0 (reachability must not cross compartments).
- **Append-not-replace:** assert the three new columns are **present** in the output (the existing column assertions are non-closed-set `in df.columns` checks — confirmed they do **not** break; we add positive assertions, we do not rewrite a closed set).

### Round-trip / preservation

- `replace_compartment` preserves `outcome_equity_dimensions` (and `response_tenet_scores`) — regression test for §3.5.

### Seed test (`tests/test_curonian_seed.py`, extend)

- The seed loads with no warnings beyond expected; `response_pressure_gap(seed)` has ≥ 1 row with `downstream_equity_outcome_count > 0` **and** ≥ 1 row with `is_equity_relevant_orphan is True`. (Requires the §6 connecting edges to exist — this test is the guard against the "tags but no connections" flake.)

### Module + e2e

- `tests/test_comparative_module.py`: `comparative_ui` renders an "Emerald Justice exposure" card; output ids `equity_disclaimer`, `equity_table` present; bump the two `comparative-card == 6` assertions (`:19`, `:142`) to `7` (the `>= 5` smoke assertion stays valid).
- `tests/test_comparative_e2e.py`: after loading the seed, the table is visible with ≥ 1 data row and the disclaimer text is present; bump the `cards.count() == 6` assertion (`:34`) to `7`.

## 8. Files touched

| File | Change |
|---|---|
| `multises/data_structure.py` | `EQUITY_DIMENSIONS`/`EQUITY_SLUGS` (6 dims); `_validate_equity_dimensions` helper + `M207`; `Compartment.outcome_equity_dimensions` + `__post_init__` validation; `from_dict` `.get(...)`; `replace_compartment` preserves the overlay (+ the existing `response_tenet_scores` omission); `W305` code constant. **No `MULTISES_SCHEMA_VERSION` bump.** |
| `multises/validate.py` | `_check_equity_element_refs` emitting `W305_EQUITY_DIM_UNKNOWN_ELEMENT` (in the `validate()` pass, not load) |
| `multises/comparative.py` | `_downstream_outcome_ids` helper (via `to_digraph`+`nx.descendants`); augment `response_pressure_gap` with 3 equity columns; add `to_digraph` to the `sespy.network` import |
| `multises/__init__.py` | re-export `EQUITY_DIMENSIONS`, `EQUITY_SLUGS` in **both** the import block and `__all__` |
| `multises/curonian/curonian_loac.json` | demonstrative equity dims on 2–3 outcome elements + connecting Pressure→outcome edges (≥1 producing an equity-relevant orphan); demonstrative comment |
| `multises_app/modules/comparative.py` | "Emerald Justice exposure" card + `equity_disclaimer`/`equity_table` renders (slug→label mapping) |
| `tests/test_equity.py` (new) | library unit tests (M207/W305/round-trip/vocab) |
| `tests/test_comparative.py` | `response_pressure_gap` augmented-column + reachability cases + `replace_compartment` preservation |
| `tests/test_curonian_seed.py` | seed equity-row + orphan-row assertions |
| `tests/test_comparative_module.py` | card-count (6→7, lines :19/:142) + new ids |
| `tests/test_comparative_e2e.py` | panel visible + card-count sync (:34) |

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Hand-rolled BFS infinite-loops on DAPSI feedback cycles | High (avoided) | Use cycle-safe `nx.descendants` via `to_digraph`; explicit cycle + self-loop tests (§7) |
| Outcome predicate mis-coded (`"Impacts"` instead of `"Ecosystem Services"`/`"Goods & Benefits"`) | Medium | §2.2 states the exact predicate; W305 wrong-type tests use real ES + GB + non-outcome elements |
| Reachability read as harm attribution rather than screening | Medium | Docstring + disclaimer state "screening, ignores polarity/edge-type"; §1 framing softened to "screened for potential exposure" |
| Overlay dropped by `replace_compartment` on UI edit | Medium (fixed) | §3.5 adds preservation + regression test |
| Overlay element-id drift (outcome deleted, flag orphaned) | Medium | `W305` soft warning, not a hard fail; orphan keys contribute no reachable outcome |
| Equity content read as authoritative rather than demonstrative | Medium | Seed comment marks dims demonstrative; `indigenous_rights` deliberately not used in the Curonian seed; `cultural_heritage` flagged provisional |
| `cultural_heritage` deviates from Nyka's canonical 5 without sign-off | Medium | §3.1 records it as provisional pending ratification; additive + reversible |
| Appending columns breaks existing `response_pressure_gap` tests | Low (verified none) | Test reviewer confirmed no closed-set/column-count assertion exists; we only **add** positive column assertions |
| Card-count assertions go stale (6→7) | High (certain) | §5/§7 name the exact assertion lines (:19/:142 module, :34 e2e) |
| Scope creep into editor / weighting / polarity-aware walk | Low | All deferred in §1.2/§11 |

## 10. Definition of done

- `EQUITY_DIMENSIONS` (6 dims incl. provisional `cultural_heritage`) in the library, re-exported in both `__init__` locations.
- `Compartment.outcome_equity_dimensions` validated (hard `M207`; soft `W305` in `validate()` only, accepting both Impact and Welfare element types), round-tripped, preserved through `replace_compartment`, `MULTISES_SCHEMA_VERSION` unchanged at 1; existing v1 files load unaffected.
- `response_pressure_gap(ms)` carries the three equity columns with documented cycle-safe, screening-only reachability; `is_equity_relevant_orphan` built only on the per-Pressure-honest response count; empty-list outcomes excluded.
- Comparative "Emerald Justice exposure" card renders the equity-relevant slice with label-mapped dimensions + disclaimer; read-only; card count 6 → 7.
- Curonian seed carries demonstrative equity dims (no `indigenous_rights`; `cultural_heritage` used for heritage) **and** the connecting edges producing ≥1 equity-relevant orphan row.
- Full unit suite green (new `test_equity.py`; augmented `response_pressure_gap` + `replace_compartment` + card-count assertions; seed assertions) + comparative e2e green.
- Manual: the panel shows the seed's equity-exposed Pressures with their reached dimensions (human labels), orphans first.

## 11. Out-of-scope follow-ups (future Phase-2 increments)

- **Forward-causal-limb-only, polarity-aware reachability** — restrict the walk to D→A→P→S→I→W, exclude feedback back-edges, and weight by edge polarity so "exposure" approaches "harm."
- Ratify (or revise) the provisional `cultural_heritage` dimension with Nyka; reconcile the parent scientific-basis prose ("fisheries livelihoods") with the slug set if needed.
- Equity **editor** UI (per-outcome dimension assignment) + autosave.
- Equity **weighting / composite equity-risk index**.
- Promotion to SESPy `Element` if/when equity becomes a SESPy-core concern (currently rejected, §2).
- Wider Emerald Justice monograph deliverables, CCS indicators (#24), per-archetype deliverables (#22).
