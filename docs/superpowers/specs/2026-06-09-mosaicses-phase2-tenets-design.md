# MosaicSES Phase-2 — 10-Tenets Evaluation Framework — Design

**Repository:** `razinkele/MosaicSES` (code location: `multises/` library + `multises_app/modules/comparative.py`; this spec + its plan live in `razinkele/SESPy` `docs/superpowers/`).

**Date:** 2026-06-09
**Status:** **Implemented** ✓ — shipped in MosaicSES `main` (`fced2f6`..`23086da`, 2026-06-09); unit suite green (16 tenet tests + seed/module updates) + comparative e2e green.
**Parent spec:** [`2026-05-08-mosaicses-design.md`](2026-05-08-mosaicses-design.md) §11 item #19; alignment matrix §8a (`tenet_scores` deferred row); scientific basis [`2026-05-09-mosaicses-scientific-basis.md`](2026-05-09-mosaicses-scientific-basis.md) §8a.
**Phase-2 item:** #19 (first Phase-2 increment).

## 1. Goal & scope

Add the **10-tenets of sustainable adaptive management** (Elliott, Burdon & Atkins 2017, `10.1016/j.marpolbul.2017.03.049`; revisited 2025) as an **evaluative layer** over management Responses and governance Channels, plus a `tenet_gap_analysis()` analysis function and a read-only **Tenet readiness** panel in the Comparative dashboard. This is the EG monograph's analytical claim — that proposed policies/measures should be scored against all ten tenets — made operational.

The ten tenets (canonical order):

1. Ecologically sustainable
2. Technologically feasible
3. Economically viable
4. Socially desirable / tolerable
5. Legally permissible
6. Administratively achievable
7. Politically expedient
8. Ethically defensible
9. Culturally inclusive
10. Effectively communicable

Each is scored **1–5** (1 = tenet not met / high risk; 5 = fully met). A Response or governance Channel is "tenet-ready" only when all scored tenets clear a threshold; un-scored tenets are **gaps** (the headline output).

### 1.1 In scope

- A canonical `TENETS` vocabulary (10 slugs + display labels) in the `multises` library.
- `Channel.tenet_scores: dict[str, int] | None` — native field on the MosaicSES `Channel` (governance type), following the existing phase-2-reserved-field pattern (`units`/`timestep`/`lifestage`).
- `Compartment.response_tenet_scores: dict[str, dict[str, int]] | None` — a MosaicSES **overlay** keyed by Response element id, so SESPy's `Element` is **NOT modified** (see §2).
- Validation (hard invariants) for both: keys ∈ `TENETS`, values int 1–5.
- `MULTISES_SCHEMA_VERSION` stays **1** — no schema bump; both fields are additive optional fields that load via `.get()` defaults (see §3.4). Lossless `to_dict`/`from_dict` round-trip.
- `tenet_gap_analysis(ms) -> pd.DataFrame` in the `multises` library (sibling to `response_pressure_gap`).
- A read-only **Tenet readiness** card in `multises_app/modules/comparative.py`.
- Example tenet scores seeded onto a small number of Curonian governance Channels + Responses so the panel is non-empty on the demo seed.
- Unit tests (library + module) and a comparative e2e assertion.

### 1.2 Out of scope (deferred)

- Editing tenet scores in the UI (this increment is **read-only** display; an editor is a later increment, mirroring how SH2 read SH1 data before SH-edit UIs).
- Promoting `tenet_scores` onto SESPy's `Element` (see §2 — rejected for this increment).
- Emerald Justice equity dimensions (Phase-2 #20), CCS indicators (#24), and the per-archetype monograph deliverables (#22) — separate increments.
- Weighting / aggregation schemes beyond a simple mean + gap count (a single defensible default; weighting is a future refinement).

## 2. Key design decision — tenets as a MosaicSES overlay (SESPy untouched)

§11 #19 says "add `tenet_scores` to Element (Response type) and to Channel (governance type)." Element is a **SESPy** type (`sespy.data_structure.Element`), shared with the SESPy app. Two options:

- **Option A — modify SESPy `Element`.** Add `tenet_scores` to `sespy.Element`, bump `PROJECT_SCHEMA_VERSION` (currently 5 → 6), update SESPy `to_dict`/`from_dict`, and ripple through the SESPy app + its tests. High blast radius for an evaluative field that only MosaicSES consumes.
- **Option B — MosaicSES overlay (CHOSEN).** Store Response tenet scores on the MosaicSES `Compartment` as `response_tenet_scores: dict[str, dict[str, int]]` (Response element id → {tenet slug → score}). SESPy is untouched. Governance-Channel scores live natively on the MosaicSES `Channel` (which is already a MosaicSES type).

**Decision: Option B.** Rationale, directly from the scientific basis (§8a): *"evaluative dimensions are layers on top of an already-correct structural model … structural dimensions need to be in the data model from v1 to avoid breaking schema changes; evaluative dimensions are layers on top."* The 10-tenets layer is definitionally evaluative, so it belongs in the MosaicSES overlay, not the SESPy structural core. This also keeps the SESPy schema stable and avoids a cross-repo change for a single Phase-2 feature.

Consequence: the parent spec's §11 #19 wording ("field on Element") is refined here to "MosaicSES overlay keyed by Response element id" — this spec is the authority for the implementation; a one-line note will be added to the parent spec's §11 #19 pointing here.

## 3. Data model

### 3.1 `TENETS` vocabulary (`multises/data_structure.py`)

```python
# Canonical 10 tenets of sustainable adaptive management (Elliott et al. 2017).
# Order is load-bearing: it is the display order and the column order in
# tenet_gap_analysis(). Slugs are stable ids; labels are display strings.
TENETS: tuple[tuple[str, str], ...] = (
    ("ecological",      "Ecologically sustainable"),
    ("technological",   "Technologically feasible"),
    ("economic",        "Economically viable"),
    ("social",          "Socially desirable"),
    ("legal",           "Legally permissible"),
    ("administrative",  "Administratively achievable"),
    ("political",       "Politically expedient"),
    ("ethical",         "Ethically defensible"),
    ("cultural",        "Culturally inclusive"),
    ("communicable",    "Effectively communicable"),
)
TENET_SLUGS: tuple[str, ...] = tuple(slug for slug, _ in TENETS)
TENET_SCORE_MIN: int = 1
TENET_SCORE_MAX: int = 5
```

Add `TENETS`, `TENET_SLUGS`, `TENET_SCORE_MIN`, `TENET_SCORE_MAX` to the package `__all__` re-exports.

### 3.2 `Channel.tenet_scores` (governance)

Add to `Channel` alongside the phase-2-reserved fields:

```python
    # Phase-2 evaluative overlay (10-tenets). None when unscored. Only
    # meaningful on governance channels, but not hard-restricted to them
    # (a soft validation warning flags non-governance use).
    tenet_scores: dict[str, int] | None = None
```

Hard invariants in `__post_init__` (raise `_ChannelValidationError` with a new `ErrorCode.M206_INVALID_TENET_SCORES`): when `tenet_scores is not None`, every key ∈ `TENET_SLUGS` and every value is an `int` (reject `bool`) in `TENET_SCORE_MIN..TENET_SCORE_MAX`. Partial dicts are allowed (an absent tenet = an un-scored gap). (Verified free: `M206` is unused in the `ErrorCode` class today.)

### 3.3 `Compartment.response_tenet_scores` (overlay)

Add to `Compartment`:

```python
    # Phase-2 evaluative overlay: Response element id -> {tenet slug -> score}.
    # Keys are sespy Response element ids within this compartment's project.
    # None / absent = no Responses scored. SESPy Element is deliberately NOT
    # modified (evaluative layer; see design §2).
    response_tenet_scores: dict[str, dict[str, int]] | None = None
```

Validation: the **value-range/key** checks (each inner dict obeys the same key/value rules as §3.2) run in `Compartment.__post_init__` and raise on bad data — these are intrinsic and need no cross-object context. **Referential integrity** (the element id resolves to an actual Response element in this compartment's project) is a **soft** invariant emitted by the dedicated `validate(ms)` pass — new code `ErrorCode.W304_TENET_SCORE_UNKNOWN_RESPONSE` (W303 is already taken by `W303_TRANSBOUNDARY_CCI_MISSING`). It is **not** emitted on the load path: `persistence.load()` / `MultiSES.from_json()` do not run `validate()`, so callers wanting referential warnings call `validate(ms)` explicitly (same as every other `Wxxx` referential check). This keeps the overlay surviving a Response deletion without hard-failing the load.

### 3.4 No schema bump — round-trip via additive optional fields

**Decision: keep `MULTISES_SCHEMA_VERSION = 1` (no bump).** Both new fields are optional and load via `.get(...)` defaults, exactly as the existing optional fields (`units`/`timestep`/`lifestage`/`delay_units`) already do — so old files load unchanged with `None` defaults and need no migration. Bumping 1→2 would buy nothing for compatibility (verified: `from_dict` reads each field with `.get`) while emitting a spurious `W400_SCHEMA_VERSION_MIGRATED` warning on *every* existing file/seed and breaking ~15 existing tests that assert `MULTISES_SCHEMA_VERSION == 1`, `schema_version: 1`, and `report.warnings == ()`. This mirrors the SH2/SH5 precedent (additive read-layer → no `PROJECT_SCHEMA_VERSION` bump).

- `Channel.from_dict`/`Compartment.from_dict`: parse `tenet_scores` / `response_tenet_scores` via `.get(...)` (add to the existing kwarg lists in `MultiSES.from_dict`).
- `to_dict`: `MultiSES.to_dict` serializes channels/compartments via `dataclasses.asdict`, so the new fields **emit as `null` when unscored** (same as `units`/`timestep` today — no bespoke None-filtering). v1 seeds gain explicit `"tenet_scores": null` / `"response_tenet_scores": null` keys after a load→save cycle; acceptable and consistent.
- Trade-off accepted: an *older* MosaicSES build reading a file that contains `tenet_scores` (with `schema_version` still 1) would silently drop the field on load rather than refuse. Since there is no separately-deployed older MosaicSES, this theoretical loss is preferable to the concrete test/warning breakage a bump causes. If a hard cross-version guard is later needed, the bump can be introduced then with the migration-test updates batched.

## 4. Analysis — `tenet_gap_analysis(ms)`

New pure function in `multises/comparative.py` (sibling to `response_pressure_gap`), returning a tidy `pd.DataFrame`. One row per **scored subject** (a Response element OR a governance Channel) that carries any tenet scores.

Columns:

| column | type | meaning |
|---|---|---|
| `subject_kind` | str | `"response"` or `"governance_channel"` |
| `source_compartment_id` | str | response: its owning compartment; governance channel: `Channel.source` |
| `target_compartment_id` | str | response: its owning compartment (same as source); governance channel: `Channel.target` |
| `subject_id` | str | element id or channel id |
| `subject_label` | str | element label or a channel summary (`"{source}→{target} governance"`) |
| `scored_count` | int | number of tenets scored (0–10) |
| `gap_count` | int | `10 - scored_count` (un-scored tenets) |
| `mean_score` | float | mean of scored tenets (NaN if none) |
| `min_score` | int | lowest scored tenet (the binding constraint) |
| `weakest_tenet` | str | slug of the lowest-scoring tenet (ties → canonical order) |
| one column per tenet slug | int \| NA | the 1–5 score, NA when un-scored |

**Compartment columns — why two.** Governance channels are directional (`source`→`target`); `response_pressure_gap` already counts governance coverage as *incoming to the `target`* (`comparative.py:200-203`). A scored governance measure is authored at `source` but governs `target`, so collapsing to a single `compartment_id` would be ambiguous. Exposing both `source_compartment_id` and `target_compartment_id` (equal for responses) keeps the readiness table unambiguous and lets the UI group by either.

Semantics + caveats (documented in the docstring, mirroring `response_pressure_gap`'s honesty about v1 semantics):

- **Gap-first framing.** The headline is `gap_count` + `min_score`: a measure with three high tenets and seven un-scored is *not* ready — gaps are unevaluated risk, not zeros.
- **No fabricated aggregate.** `mean_score` is over *scored* tenets only; it is explicitly NOT a readiness score (a partially-scored measure can have a high mean and many gaps). The panel shows mean, gap count, and min together so the mean is never read alone.
- Deterministic row order: `subject_kind`, then `source_compartment_id`, then `subject_id`.
- Returns an **empty DataFrame with the full column set** when nothing is scored (so the UI renders headers, not an error). NB: this is a deliberately *stronger* contract than `response_pressure_gap`, which returns a column-less empty frame (`comparative.py:205-231`) — do not assume the two are identical; the tenet table needs stable columns for the DataGrid.

Add `tenet_gap_analysis` to the `multises` package `__all__`.

## 5. UI — Comparative "Tenet readiness" card

Add one card to `multises_app/modules/comparative.py`'s `comparative_ui`, after the "Response–Pressure gap" card (it is the closest evaluative sibling), preserving the `comparative-card` class on every card:

```python
ui.card(ui.card_header("Tenet readiness"),
        ui.output_ui("tenet_disclaimer"),
        ui.output_data_frame("tenet_table"),
        class_="comparative-card"),
```

Server renders (read-only, reactive on `state.active_multises`):

- `tenet_disclaimer` (`@render.ui`): a short caveat line — "Scores are 1–5; blank = un-scored gap. Mean is over scored tenets only and is not a readiness score." Plus an empty-state hint when the table is empty ("No tenet scores in this MultiSES yet.").
- `tenet_table` (`@render.data_frame`): `render.DataGrid` of `tenet_gap_analysis(ms)`, with the 10 tenet columns shown as their display labels and gap cells blank. The hero columns (`subject_label`, `gap_count`, `min_score`, `weakest_tenet`, `mean_score`) lead; per-tenet score columns follow.

No layout restructure, no new nav item, no server contract change beyond the two new outputs. The MosaicSES app is not i18n'd (panel titles are plain English, matching "Vital signs"/"Centrality heatmap"), so no translation keys are added.

## 6. Seed data (Curonian demo)

Add example tenet scores to the Curonian seed (`multises/curonian/curonian_loac.json`) so the panel is non-empty out of the box:

- **2–3 governance Channels** (e.g. the eutrophication–governance balancing-loop governance edge, §8.4 Loop 1) get partial `tenet_scores` reflecting a realistic transboundary measure: high `ecological`/`legal`, lower `political`/`administrative` (the LT/RU cross-border friction the `cci_index` already encodes), and an un-scored `cultural`/`communicable` gap.
- **1–2 Response elements** in the lagoon compartment get `response_tenet_scores` entries.

Scores are illustrative-but-defensible (grounded in the transboundary-friction narrative already in the scientific basis), and the seed gains a short comment block noting they are demonstrative. This keeps the seed honest: a partially-scored, gap-bearing example is exactly what the panel is meant to surface.

## 7. Testing

### Library unit tests (`tests/test_tenets.py`, new)

- `TENETS` has 10 entries; `TENET_SLUGS` length 10, unique, order stable.
- `Channel(tenet_scores={...valid...})` constructs; round-trips through `to_dict`/`from_dict`.
- `Channel` with an unknown tenet slug / out-of-range / bool / non-int value raises `_ChannelValidationError` with `M206_INVALID_TENET_SCORES`.
- Partial `tenet_scores` (subset of tenets) is accepted.
- `Compartment.response_tenet_scores` valid case round-trips; invalid score raises in `__post_init__`; an id that doesn't resolve to a Response yields the `W304_TENET_SCORE_UNKNOWN_RESPONSE` soft warning when `validate(ms)` is run (NOT on load — assert via an explicit `validate()` call, since `from_json` does not validate).
- `MULTISES_SCHEMA_VERSION == 1` (unchanged — no bump); a v1 fixture with the two new fields absent loads with `None` defaults and **no** new `W400` warning (the additive fields don't trigger migration). A fixture that *includes* the fields round-trips them losslessly.
- `tenet_gap_analysis`: empty MultiSES → empty DataFrame with full columns; a hand-built MultiSES with one scored channel + one scored response → 2 rows, correct `gap_count`/`min_score`/`weakest_tenet`/`mean_score`; tie-break picks the canonical-order tenet.

### Seed test (`tests/test_curonian_seed.py`, extend)

- The seed loads at `schema_version 2` with no warnings beyond expected; `tenet_gap_analysis(seed)` returns ≥ 1 row; at least one row has `gap_count > 0` (demonstrating the gap-first framing).

### Module + e2e

- `tests/test_comparative_module.py`: `comparative_ui` renders a "Tenet readiness" card; output ids `tenet_disclaimer`, `tenet_table` present; `comparative-card` count increments by 1 (5 → 6) — update the existing count assertion.
- `tests/test_comparative_e2e.py`: after loading the seed, the Tenet-readiness table is visible and has ≥ 1 data row; the disclaimer text is present. (Keep the existing card-count assertion in sync: 5 → 6.)

## 8. Files touched

| File | Change |
|---|---|
| `multises/data_structure.py` | `TENETS`/`TENET_SLUGS`/score bounds; `Channel.tenet_scores` + validation + `M206`; `Compartment.response_tenet_scores` + value/key validation; `from_dict` `.get(...)` for both fields; `W304` code constant. **No `MULTISES_SCHEMA_VERSION` bump.** |
| `multises/validate.py` | `W304_TENET_SCORE_UNKNOWN_RESPONSE` referential-integrity soft check (in the `validate()` pass, not load) |
| `multises/comparative.py` | `tenet_gap_analysis(ms)` |
| `multises/__init__.py` | re-export `TENETS`, `TENET_SLUGS`, `tenet_gap_analysis`, bounds |
| `multises/curonian/curonian_loac.json` | demonstrative tenet scores on 2–3 governance channels + 1–2 responses |
| `multises_app/modules/comparative.py` | "Tenet readiness" card + `tenet_disclaimer`/`tenet_table` renders |
| `tests/test_tenets.py` (new) | library unit tests |
| `tests/test_curonian_seed.py` | seed assertion |
| `tests/test_comparative_module.py` | card-count + new ids |
| `tests/test_comparative_e2e.py` | panel visible + card-count sync |

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Mean-score misread as a readiness score | Medium | Panel always shows `gap_count` + `min_score` beside the mean; disclaimer line; docstring states mean is over scored tenets only |
| Overlay element-id drift (Response deleted, score orphaned) | Medium | `W303` soft warning, not a hard fail; orphan rows simply don't render |
| Schema-version churn breaks existing v1 seeds/tests | N/A (avoided) | Decision §3.4: no `MULTISES_SCHEMA_VERSION` bump — additive optional fields only; existing schema tests untouched |
| Card-count assertions in module/e2e tests go stale | High (certain) | Spec calls out the 5→6 update explicitly in §7 |
| Scope creep into a tenet editor / weighting | Low | Read-only display fixed in §1.2; editor + weighting deferred |

## 10. Definition of done

- `TENETS` vocab + bounds in the library, re-exported.
- `Channel.tenet_scores` and `Compartment.response_tenet_scores` validated, round-tripped, `MULTISES_SCHEMA_VERSION` unchanged at 1 (additive optional fields; no migration), existing v1 files load unaffected.
- `tenet_gap_analysis(ms)` returns the documented tidy frame (gap-first; mean never presented alone).
- Comparative "Tenet readiness" card renders the table + disclaimer; read-only.
- Curonian seed carries demonstrative, gap-bearing scores; seed loads at v2.
- Full unit suite green (new `test_tenets.py` + updated counts) + comparative e2e green.
- Manual: the panel shows the seed's scored measures with visible gaps.

## 11. Out-of-scope follow-ups (future Phase-2 increments)

- Tenet **editor** UI (per-Response / per-Channel score entry) + autosave.
- Tenet **weighting / aggregate readiness index** (once a defensible weighting is agreed).
- Promotion to SESPy `Element` if/when tenets become a SESPy-core concern (currently rejected, §2).
- Emerald Justice equity overlay (#20), CCS indicators (#24), monograph deliverables (#22).
