# MosaicSES Phase-2 — Emerald Justice Equity Overlay — Design

**Repository:** `razinkele/MosaicSES` (code location: `multises/` library + `multises_app/modules/comparative.py`; this spec + its plan live in `razinkele/SESPy` `docs/superpowers/`).

**Date:** 2026-06-13
**Status:** **Planned** — not yet implemented.
**Parent spec:** [`2026-05-08-mosaicses-design.md`](2026-05-08-mosaicses-design.md) §11 item #20; alignment matrix [`2026-05-09-mosaicses-scientific-basis.md`](2026-05-09-mosaicses-scientific-basis.md) §8a (`equity_dimensions` deferred row) and §2.0 (Emerald Justice as parallel EG concept).
**Sibling increment / template:** [`2026-06-09-mosaicses-phase2-tenets-design.md`](2026-06-09-mosaicses-phase2-tenets-design.md) (#19, first Phase-2 increment) — this increment deliberately mirrors its shape (overlay field + analysis + read-only comparative card + Curonian seed).
**Phase-2 item:** #20 (second Phase-2 increment).

## 1. Goal & scope

Add **Emerald Justice equity dimensions** — the equity layer that Maciej Nyka and the user's research group are developing on top of Emerald Growth (scientific basis §2.0, §8a) — as an **evaluative overlay** over Impact elements, plus an **equity-exposure lens** on the existing `response_pressure_gap()` analysis and a read-only **Emerald Justice exposure** card in the Comparative dashboard. This operationalises the analytical claim that management Pressures should be examined for *who* they harm: which ungoverned Pressures flow downstream to Impacts that carry equity concerns.

The five equity dimensions (canonical set, from parent spec §11 #20):

1. Ocean grabbing
2. Livelihood displacement
3. Gender inequity
4. Indigenous rights
5. Exclusion from decision-making

Each Impact element may carry **zero or more** dimensions (a set, not a score — unlike the 1–5 tenet scale). An equity-flagged Impact reachable downstream from an ungoverned Pressure is the headline risk.

### 1.1 In scope

- A canonical `EQUITY_DIMENSIONS` vocabulary (5 slugs + display labels) in the `multises` library.
- `Compartment.impact_equity_dimensions: dict[str, list[str]] | None` — a MosaicSES **overlay** keyed by Impact element id, so SESPy's `Element` is **NOT modified** (see §2).
- Validation: hard intrinsic invariant (each value a list of slugs ∈ `EQUITY_SLUGS`, no duplicates) in `Compartment.__post_init__`; soft referential invariant (id resolves to a real Impact element) in the `validate(ms)` pass.
- `MULTISES_SCHEMA_VERSION` stays **1** — no schema bump; additive optional field loaded via `.get()` defaults (see §3.4). Lossless `to_dict`/`from_dict` round-trip.
- **Augmentation** of `response_pressure_gap(ms)` in `multises/comparative.py` with three equity-exposure columns (see §4).
- A read-only **Emerald Justice exposure** card in `multises_app/modules/comparative.py`.
- Example equity dimensions seeded onto a small number of Curonian Impact elements so the panel is non-empty on the demo seed.
- Unit tests (library + module) and a comparative e2e assertion.

### 1.2 Out of scope (deferred)

- Editing equity dimensions in the UI (this increment is **read-only** display; an editor is a later increment, mirroring how #19 shipped read-only before any edit UI).
- Promoting `equity_dimensions` onto SESPy's `Element` (see §2 — rejected for this increment).
- Equity *weighting* or a composite equity index (a single defensible default — presence/absence of dimensions + downstream reachability; weighting is a future refinement).
- The wider Emerald Justice EG-monograph deliverables beyond this overlay + lens + seed (#22 monograph items, CCS #24 remain separate increments).

## 2. Key design decision — equity as a MosaicSES overlay (SESPy untouched)

§11 #20 task (a) says "add `equity_dimension: list[str] | None` to `Element` (Impact type)." `Element` is a **SESPy** type (`sespy.data_structure.Element`), shared with the SESPy app. This is the **same fork #19 faced**, and it gets the **same resolution**:

- **Option A — modify SESPy `Element`.** Add `equity_dimensions` to `sespy.Element`, bump `PROJECT_SCHEMA_VERSION` (currently 5 → 6), update SESPy `to_dict`/`from_dict`, and ripple through the SESPy app + its tests. High blast radius for an evaluative field only MosaicSES consumes.
- **Option B — MosaicSES overlay (CHOSEN).** Store equity dimensions on the MosaicSES `Compartment` as `impact_equity_dimensions: dict[str, list[str]]` (Impact element id → list of equity slugs). SESPy is untouched.

**Decision: Option B.** Rationale, directly from the scientific basis (§8a): *"evaluative dimensions are layers on top of an already-correct structural model … structural dimensions need to be in the data model from v1 to avoid breaking schema changes; evaluative dimensions are layers on top."* Emerald Justice is definitionally evaluative, so it belongs in the MosaicSES overlay, not the SESPy structural core. This keeps the SESPy schema stable and matches the precedent set by `Compartment.response_tenet_scores` (#19 §2).

Consequence: the parent spec's §11 #20 task (a) wording ("field on Element") is refined here to "MosaicSES overlay keyed by Impact element id"; this spec is the authority for the implementation, and a one-line note will be added to the parent spec's §11 #20 pointing here.

### 2.1 What counts as an "Impact" element

A subtlety that the analysis and the soft-validation check both depend on: in this codebase, an Impact element's `Element.type` string is literally **`"Ecosystem Services"`** — the `ELEMENT_TYPE_MAP` maps the `"impacts"` slug to the display string `"Ecosystem Services"` (`sespy/data_structure.py:46`; confirmed in `multises/archetypes.json` row `("Ecosystem Services", "default_es", "impacts")`). So everywhere this spec says "Impact element," the implementation predicate is `element.type == "Ecosystem Services"`. This is the single fact most likely to be mis-coded; it is called out here and in §4 and §6.

## 3. Data model

### 3.1 `EQUITY_DIMENSIONS` vocabulary (`multises/data_structure.py`)

```python
# Emerald Justice equity dimensions (Nyka & group; EG monograph; spec §11 #20).
# Order is load-bearing: it is the display order. Slugs are stable ids;
# labels are display strings.
EQUITY_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("ocean_grabbing",          "Ocean grabbing"),
    ("livelihood_displacement", "Livelihood displacement"),
    ("gender_inequity",         "Gender inequity"),
    ("indigenous_rights",       "Indigenous rights"),
    ("decision_exclusion",      "Exclusion from decision-making"),
)
EQUITY_SLUGS: tuple[str, ...] = tuple(slug for slug, _ in EQUITY_DIMENSIONS)
```

Add `EQUITY_DIMENSIONS`, `EQUITY_SLUGS` to the package `__all__` re-exports.

### 3.2 `Compartment.impact_equity_dimensions` (overlay)

Add to `Compartment` alongside `response_tenet_scores`:

```python
    # Phase-2 evaluative overlay: Impact element id -> [equity slugs].
    # Keys are sespy Impact element ids (type == "Ecosystem Services") within
    # this compartment's project. None / absent = no Impacts flagged. SESPy
    # Element is deliberately NOT modified (evaluative layer; see design §2).
    impact_equity_dimensions: dict[str, list[str]] | None = None
```

**Hard invariant** (intrinsic; runs in `Compartment.__post_init__`): a new module-level helper `_validate_equity_dimensions(dims, *, where)` — mirroring `_validate_tenet_scores` — raises `_ChannelValidationError` with a new `ErrorCode.M207_INVALID_EQUITY_DIMENSION` when, for any entry, the value is not a list, contains a slug ∉ `EQUITY_SLUGS`, or contains a duplicate slug. An **empty list is allowed** (an explicitly-flagged-but-empty Impact = no dimensions; treated the same as absent by the analysis). (Verified free: `M206` is the highest `M2xx` code in use today; `M207` is unused.)

```python
        if self.impact_equity_dimensions is not None:
            for eid, dims in self.impact_equity_dimensions.items():
                _validate_equity_dimensions(
                    dims, where=f"Compartment {self.id!r} impact {eid!r}")
```

(Note: `_validate_equity_dimensions` raises `_ChannelValidationError` despite the class name — that class is the generic hard-invariant carrier that holds an `ErrorCode` in `.code`, exactly as `_validate_tenet_scores` already reuses it from `Compartment.__post_init__`.)

### 3.3 Referential integrity (soft, validate-pass only)

The check that each key resolves to an actual Impact element (`type == "Ecosystem Services"`) in this compartment's project is a **soft** invariant emitted by the dedicated `validate(ms)` pass — new code `ErrorCode.W305_EQUITY_DIM_UNKNOWN_IMPACT` (W304 is already taken by `W304_TENET_SCORE_UNKNOWN_RESPONSE`; W305 is unused). It is **not** emitted on the load path: `persistence.load()` / `MultiSES.from_json()` do not run `validate()`, so callers wanting referential warnings call `validate(ms)` explicitly (same as every other `Wxxx` referential check). This keeps the overlay surviving an Impact deletion without hard-failing the load.

### 3.4 No schema bump — round-trip via additive optional field

**Decision: keep `MULTISES_SCHEMA_VERSION = 1` (no bump).** The new field is optional and loads via `.get(...)` defaults, exactly as `response_tenet_scores` (#19 §3.4) and the existing optional fields (`units`/`timestep`/`lifestage`/`delay_units`) already do — so old files load unchanged with `None` defaults and need no migration. Bumping would emit a spurious `W400_SCHEMA_VERSION_MIGRATED` warning on every existing file/seed and break the tests that assert `MULTISES_SCHEMA_VERSION == 1` and `report.warnings == ()`. This mirrors the #19 precedent exactly.

- `Compartment.from_dict` (in `MultiSES.from_dict`): parse `impact_equity_dimensions` via `.get(...)`, added to the existing kwarg list alongside `response_tenet_scores`.
- `to_dict`: `MultiSES.to_dict` serializes compartments via `dataclasses.asdict`, so the new field **emits as `null` when unset** (same as `response_tenet_scores` today — no bespoke None-filtering). v1 seeds gain an explicit `"impact_equity_dimensions": null` key after a load→save cycle; acceptable and consistent.

## 4. Analysis — augment `response_pressure_gap(ms)`

Per the chosen approach, the equity lens is **added to the existing `response_pressure_gap`** (in `multises/comparative.py`) rather than a sibling function. This is coherent because both analyses share the same unit of analysis — **one row per Pressure element** — so the equity columns slot onto the existing rows without changing the row grain.

### 4.1 Reachability semantics (v1)

For each Pressure element, perform a **directed downstream reachability walk** within the compartment's own graph: BFS along directed connections (`conn.source → conn.target`, the same fields `response_pressure_gap` already reads at `comparative.py:211-215`) starting from the Pressure id, collecting every reachable Impact element (`type == "Ecosystem Services"`). The Pressure's equity exposure is the **union** of `impact_equity_dimensions` over those reached Impacts.

This is honest per-Pressure semantics (a Pressure is exposed to an Impact only if a causal path connects them), and it is **stronger** than the compartment-level coarseness `response_pressure_gap` already documents for governance channels (`comparative.py:180-198`). The directed-reachability semantics and their v1 caveats are documented in the augmented docstring.

### 4.2 New columns (appended after the existing columns)

| column | type | meaning |
|---|---|---|
| `downstream_equity_impact_count` | int | number of equity-flagged Impact elements reachable downstream from this Pressure (0 if none) |
| `affected_equity_dimensions` | str | sorted, comma-joined union of equity slugs reached (`""` when none) |
| `is_equity_relevant_orphan` | bool | `within_compartment_response_count == 0` **and** `downstream_equity_impact_count > 0` |

`is_equity_relevant_orphan` is built **only** on the per-Pressure-honest `within_compartment_response_count` (the column `response_pressure_gap` already computes per-Pressure via direct Response→Pressure connections) — **never** on `incoming_governance_channel_count`, which the existing docstring explicitly warns is compartment-level and would be misleading as a per-Pressure orphan signal. This keeps the equity flag as honest as the function's existing self-imposed contract.

### 4.3 Column ordering & empty-frame behavior

Equity columns are **appended after** the existing columns so column-position-dependent consumers are minimally disturbed (the existing tests still need their column assertions updated — see §7). The empty case is unchanged: `response_pressure_gap` returns a column-less empty frame when there are no Pressures (`comparative.py:205-231`); this increment does not alter that (the equity columns appear only once there is ≥1 Pressure row). A short reachability helper (`_downstream_impact_ids(isa_data, start_id)`) is added as a module-private function.

## 5. UI — Comparative "Emerald Justice exposure" card

Add one card to `multises_app/modules/comparative.py`'s `comparative_ui`, after the "Response–Pressure gap" card (its source function), preserving the `comparative-card` class on every card:

```python
ui.card(ui.card_header("Emerald Justice exposure"),
        ui.output_ui("equity_disclaimer"),
        ui.output_data_frame("equity_table"),
        class_="comparative-card"),
```

Server renders (read-only, reactive on `state.active_multises`):

- `equity_disclaimer` (`@render.ui`): a short caveat — "Equity exposure traces Impacts reachable downstream from each Pressure within its compartment; blank = no equity-flagged Impact reached. 'Equity-relevant orphan' = a Pressure with no within-compartment Response that nonetheless reaches an equity-flagged Impact." Plus an empty-state hint when the table is empty ("No equity-flagged Impacts in this MultiSES yet.").
- `equity_table` (`@render.data_frame`): `render.DataGrid` of `response_pressure_gap(ms)` **sliced** to the equity-relevant view — columns `compartment_id`, `pressure_label`, `within_compartment_response_count`, `downstream_equity_impact_count`, `affected_equity_dimensions`, `is_equity_relevant_orphan` — **filtered** to rows where `downstream_equity_impact_count > 0`, sorted with `is_equity_relevant_orphan` rows first (then by `compartment_id`, `pressure_label`).

No layout restructure, no new nav item, no new analysis function. The MosaicSES app is not i18n'd (panel titles are plain English, matching "Vital signs"/"Tenet readiness"), so no translation keys are added.

**Card count:** the comparative dashboard goes from **6 → 7** `comparative-card`s (the tenet-readiness card took it 5 → 6 in #19). The module and e2e count assertions must be updated (§7).

## 6. Seed data (Curonian)

Add example equity dimensions to the Curonian seed (`multises/curonian/curonian_loac.json`) so the panel is non-empty out of the box:

- **2–3 Impact elements** (`type == "Ecosystem Services"`) across the lagoon / coastal compartments get `impact_equity_dimensions` entries grounded in the transboundary LT/RU small-scale-fishery narrative already in the scientific basis (§2.0 Emerald Justice; the cci transboundary-friction context): e.g. a fisheries-livelihood Impact tagged `livelihood_displacement` + `decision_exclusion`; a heritage/cultural Impact tagged `indigenous_rights`. At least one of these Impacts must be **downstream of a Pressure that has no within-compartment Response**, so the seed surfaces ≥1 `is_equity_relevant_orphan` row (demonstrating the headline signal).

Dimensions are illustrative-but-defensible (grounded in the transboundary-friction narrative the `cci_index` already encodes), and the seed gains a short comment block noting they are demonstrative. This keeps the seed honest: a partially-flagged, gap-bearing example is exactly what the panel is meant to surface.

## 7. Testing

### Library unit tests (`tests/test_equity.py`, new)

- `EQUITY_DIMENSIONS` has 5 entries; `EQUITY_SLUGS` length 5, unique, order stable.
- `Compartment(impact_equity_dimensions={...valid...})` constructs; round-trips through `to_dict`/`from_dict`.
- `Compartment` with an unknown equity slug / non-list value / duplicate slug raises `_ChannelValidationError` with `M207_INVALID_EQUITY_DIMENSION` from `__post_init__`. An **empty list** value is accepted.
- An id that doesn't resolve to an Impact element (`type == "Ecosystem Services"`) yields the `W305_EQUITY_DIM_UNKNOWN_IMPACT` soft warning when `validate(ms)` is run (NOT on load — assert via an explicit `validate()` call, since `from_json` does not validate).
- `MULTISES_SCHEMA_VERSION == 1` (unchanged); a fixture with the field absent loads with `None` default and **no** new `W400` warning. A fixture that *includes* the field round-trips it losslessly.

### Analysis tests (`tests/` — `response_pressure_gap` coverage, extend)

- Hand-built MultiSES with a directed Pressure→…→Impact path where the Impact carries equity dimensions and the Pressure has no within-compartment Response → that Pressure's row has `downstream_equity_impact_count == 1`, `affected_equity_dimensions` == the expected sorted union, `is_equity_relevant_orphan is True`.
- A Pressure with a within-compartment Response but a reachable equity Impact → `is_equity_relevant_orphan is False`, count still > 0.
- A Pressure with no reachable equity Impact → count 0, `affected_equity_dimensions == ""`, flag False.
- **Update the existing `response_pressure_gap` column assertions** to include the three appended equity columns (called out because this is the contract churn the augment-vs-sibling trade-off accepts).

### Seed test (`tests/test_curonian_seed.py`, extend)

- The seed loads with no warnings beyond expected; `response_pressure_gap(seed)` has ≥ 1 row with `downstream_equity_impact_count > 0`, and ≥ 1 row with `is_equity_relevant_orphan is True`.

### Module + e2e

- `tests/test_comparative_module.py`: `comparative_ui` renders an "Emerald Justice exposure" card; output ids `equity_disclaimer`, `equity_table` present; `comparative-card` count increments by 1 (6 → 7) — update the existing count assertion.
- `tests/test_comparative_e2e.py`: after loading the seed, the Emerald-Justice-exposure table is visible and has ≥ 1 data row; the disclaimer text is present. Keep the card-count assertion in sync (6 → 7).

## 8. Files touched

| File | Change |
|---|---|
| `multises/data_structure.py` | `EQUITY_DIMENSIONS`/`EQUITY_SLUGS`; `_validate_equity_dimensions` helper + `M207`; `Compartment.impact_equity_dimensions` + `__post_init__` validation; `from_dict` `.get(...)`; `W305` code constant. **No `MULTISES_SCHEMA_VERSION` bump.** |
| `multises/validate.py` | `W305_EQUITY_DIM_UNKNOWN_IMPACT` referential-integrity soft check (in the `validate()` pass, not load) |
| `multises/comparative.py` | augment `response_pressure_gap` with 3 equity columns + `_downstream_impact_ids` reachability helper |
| `multises/__init__.py` | re-export `EQUITY_DIMENSIONS`, `EQUITY_SLUGS` |
| `multises/curonian/curonian_loac.json` | demonstrative equity dimensions on 2–3 Impacts (≥1 producing an equity-relevant orphan) |
| `multises_app/modules/comparative.py` | "Emerald Justice exposure" card + `equity_disclaimer`/`equity_table` renders |
| `tests/test_equity.py` (new) | library unit tests |
| `tests/` `response_pressure_gap` tests | augmented-column assertions + reachability cases |
| `tests/test_curonian_seed.py` | seed assertion |
| `tests/test_comparative_module.py` | card-count (6→7) + new ids |
| `tests/test_comparative_e2e.py` | panel visible + card-count sync |

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Augmenting `response_pressure_gap` churns its column contract | High (certain) | #19 made a sibling to avoid exactly this; trade-off accepted by design choice. Equity columns **appended** after existing ones; §7 calls out the test updates explicitly |
| "Impact" mis-coded as `type == "Impacts"` instead of `"Ecosystem Services"` | Medium | §2.1, §4.1, §6 all state the predicate explicitly; a unit test uses a real `"Ecosystem Services"` element |
| Directed-reachability semantics misread as compartment-level | Medium | Disclaimer line + augmented docstring; flag built only on per-Pressure-honest `within_compartment_response_count` |
| Overlay element-id drift (Impact deleted, flag orphaned) | Medium | `W305` soft warning, not a hard fail; orphan keys simply contribute no reachable Impact |
| Equity content read as authoritative rather than demonstrative | Medium | Seed comment block marks dimensions demonstrative; grounded in existing cci transboundary narrative |
| Card-count assertions in module/e2e tests go stale (6→7) | High (certain) | Spec calls out the 6→7 update explicitly in §5 and §7 |
| Scope creep into an equity editor / weighting | Low | Read-only display fixed in §1.2; editor + weighting deferred |

## 10. Definition of done

- `EQUITY_DIMENSIONS` vocab in the library, re-exported.
- `Compartment.impact_equity_dimensions` validated (hard intrinsic via `M207`; soft referential via `W305` in `validate()` only), round-tripped, `MULTISES_SCHEMA_VERSION` unchanged at 1 (additive optional field; no migration), existing v1 files load unaffected.
- `response_pressure_gap(ms)` carries the three equity columns with documented directed-reachability semantics; `is_equity_relevant_orphan` built only on the per-Pressure-honest response count.
- Comparative "Emerald Justice exposure" card renders the equity-relevant slice + disclaimer; read-only; card count 6 → 7.
- Curonian seed carries demonstrative equity dimensions producing ≥1 equity-relevant orphan row.
- Full unit suite green (new `test_equity.py` + updated `response_pressure_gap` column + card-count assertions) + comparative e2e green.
- Manual: the panel shows the seed's equity-flagged Pressures with their reached dimensions, orphans first.

## 11. Out-of-scope follow-ups (future Phase-2 increments)

- Equity **editor** UI (per-Impact dimension assignment) + autosave.
- Equity **weighting / composite equity-risk index** (once a defensible weighting is agreed).
- Promotion to SESPy `Element` if/when equity becomes a SESPy-core concern (currently rejected, §2).
- Wider Emerald Justice monograph deliverables, CCS indicators (#24), per-archetype deliverables (#22) — separate increments.
