# AI-ISA Wizard SP2: Regional Seas Knowledge Base — Design

Status: **Implemented** · merged to `main` 2026-05-02 at commit `3c18fd8` (4 commits from `feat/ai-isa-wizard-sp2`, fast-forward: `ce569f1` JSON data, `8b4ca90` loader + 12 unit tests, `984effd` `sespy/wizard.py` swap, `3c18fd8` README bump). Subsequent post-SP2 cleanup commit `d14960e` (same day) renamed `REGIONAL_SEAS_PLACEHOLDER → REGIONAL_SEAS`, **superseding §5's misnomer-acceptance subsection** ("Why keep the misnomer name `REGIONAL_SEAS_PLACEHOLDER`?") — the rename was deferred to SP3 in this spec but executed sooner as a focused post-merge cleanup. Stale touch points (left as historical context, tagged inline with `[HISTORICAL]` where relevant): §2 modified-files row references the old name; §5's "After" code block keeps the old name; §7 Test 11 description still references `REGIONAL_SEAS_PLACEHOLDER`; §11 Definition of Done's `REGIONAL_SEAS_PLACEHOLDER` checkpoint. Shipped code uses `REGIONAL_SEAS` everywhere; the SP1 wizard module (`sespy/modules/ai_isa_wizard.py`) imports `REGIONAL_SEAS` (4 use sites at lines 34, 46, 55, 71). Test count delta verified: post-SP2 baseline is 134 unit + 21 e2e as targeted.
**Sub-project context:** SP2 of 4 in the AI-Assisted SES Creation series. SP1 shipped 2026-05-01 (commit `dfedd28` on main). SP3 (TF-IDF connection scoring) and SP4 (Claude API backend) follow.

---

## 1. Goal

Replace SP1's `REGIONAL_SEAS_PLACEHOLDER` (5 hardcoded seas in `sespy/wizard.py`) with the real knowledge base ported from R's `modules/ai_isa_knowledge_base.R`. SP2 is a **drop-in data swap** — no wizard renderer or state-machine changes. The SP1→SP2 contract documented in SP1 §9 ("SP2 may add fields but must not rename or restructure") is preserved.

**Source of truth for all data values:**
`..\SESToolbox\MarineSABRES_SES_Shiny\modules\ai_isa_knowledge_base.R` (sibling repo to SESPy, not in SESPy itself):
- Lines 16-91: `get_regional_seas_knowledge_base()` — sea metadata (`name_en`, `common_issues`, `ecosystem_types`).
- Lines 104-241: `get_countries_for_sea()` — per-sea country lookups (`code`, `name`, `eu_member`).
- Lines 262-264: hardcoded EU member ISO-2 codes (the 22-code list SP2 reproduces in `eu_member_codes`).

When implementing Task 1 (JSON authoring) or debugging a Test 10 spot-check failure, this is the file to read. **All list-typed fields (`countries`, `country_codes`, `ecosystem_types`, `common_issues`) preserve R's source order verbatim** — the parallel-index invariant between `countries[i]` and `country_codes[i]` depends on this.

**Identifier stability contract.** Slug keys (`baltic`, `mediterranean`, …, `arctic`) and ISO-2 country codes (`SE`, `DE`, …) are **stable identifiers** — they appear in persisted user data (`ProjectMetadata.regional_sea`) and in code paths (governance lookups in SP3). They MUST NOT be renamed without a documented migration plan. The display strings (`name`, `countries[*]`) are mutable — they are subject to future localization (i18n is deferred per §10) and may carry geographic context suffixes (e.g., `"France (overseas)"`, `"Denmark (Greenland)"`). Callers needing stable references MUST use slugs/codes; callers needing display labels MUST use the name fields.

**In scope:**
- 11 regional seas with full attribute set (name, ecosystem types, common issues, countries).
- ISO-2 country codes alongside country names (parallel-indexed).
- Flat `eu_member_codes` index for SP3's governance lookups.
- JSON storage at `sespy/regional_seas.json` (matches `sespy/templates/*.json` pattern).

**Out of scope (deferred to SP3+):**
- Country-aware suggestion helpers (governance/socioeconomic logic from R lines 242+) — SP3 territory.
- i18n for sea/country display names — future cleanup, not SP2.
- Refresh API (data is static; reload is "restart Python").
- Schema validation at runtime — `tests/test_regional_seas.py` validates at CI time only.

---

## 2. File organization

**New files:**
- `sespy/regional_seas.py` — pure-Python loader module (~30 LOC)
- `sespy/regional_seas.json` — KB data (~250 LOC of JSON)
- `tests/test_regional_seas.py` — schema + content validation (~130 LOC, 12 tests including a 16-row spot-check table for Test 10)

**Modified files:**
- `sespy/wizard.py` — `REGIONAL_SEAS_PLACEHOLDER` reassigned from `get_regional_seas()` instead of inline literal. *[HISTORICAL — post-`d14960e` the constant is renamed to `REGIONAL_SEAS`.]*
- `tests/test_wizard.py` — comment update only; existing `test_regional_seas_placeholder_has_at_least_baltic` still passes (it's a shape check).
- `README.md` — unit test count 122 → 134.

**Pattern reference:** SP2 uses the same `Path(__file__).parent` resolution technique as `sespy/templates/__init__.py:_templates_dir()`. The structural placement differs slightly — `sespy/templates/` is a sub-package containing a loader `__init__.py` plus multiple `*.json` files (one per template), whereas `sespy/regional_seas.json` is a single data file at the package root with a sibling loader `sespy/regional_seas.py`. The single-file shape is appropriate here because the KB is a single-document atomic data asset. The file-resolution technique is the canonical pattern; the directory shape is justified by data scope.

---

## 3. Data shape

`sespy/regional_seas.json` is a single document with two top-level keys:

```json
{
  "regional_seas": {
    "baltic": {
      "name": "Baltic Sea",
      "ecosystem_types": [
        "Open coast", "Rocky coast (Schären)", "Archipelago",
        "Island", "Estuary", "Coastal lagoon", "Offshore waters"
      ],
      "common_issues": [
        "Eutrophication", "Overfishing", "Pollution",
        "Invasive species", "Climate change"
      ],
      "countries": [
        "Sweden", "Finland", "Denmark", "Germany", "Poland",
        "Lithuania", "Latvia", "Estonia", "Russia"
      ],
      "country_codes": [
        "SE", "FI", "DK", "DE", "PL", "LT", "LV", "EE", "RU"
      ]
    },
    "mediterranean": { /* same shape */ },
    /* ... 9 more seas: north_sea, irish_sea, east_atlantic, black_sea,
       atlantic, pacific, indian, caribbean, arctic */
  },
  "eu_member_codes": [
    "SE", "FI", "DK", "DE", "PL", "LT", "LV", "EE",
    "ES", "FR", "IT", "GR", "HR", "SI", "MT", "CY",
    "NL", "BE", "PT", "IE", "BG", "RO"
  ]
}
```

### Per-sea fields

| Field | Type | Source | SP1 contract |
|---|---|---|---|
| `name` | str | R: `name_en` | ✓ same |
| `ecosystem_types` | list[str] | R: `ecosystem_types` | ✓ same |
| `common_issues` | list[str] | R: `common_issues` | ✓ same |
| `countries` | list[str] | R: `get_countries_for_sea()` → name fields | ✓ same |
| `country_codes` | list[str] | R: `get_countries_for_sea()` → code fields | NEW (SP2 addition) |

### Invariants

- **Parallel indexing**: `len(countries) == len(country_codes)`, and for every `i`: `countries[i]` is the human name for `country_codes[i]`.
- **ISO-2 codes**: every entry in `country_codes` matches `^[A-Z]{2}$`.
- **No empty arrays**: every sea has ≥1 ecosystem type, ≥1 common issue, ≥1 country.
- **EU codes are real**: every code in `eu_member_codes` appears in at least one sea's `country_codes`. (The reverse isn't required — non-EU countries appear too.)

### Sea slug list (11 total)

`baltic, mediterranean, north_sea, irish_sea, east_atlantic, black_sea, atlantic, pacific, indian, caribbean, arctic`

**Note 1 — `macaronesia` is dropped:** SP1's placeholder included `macaronesia` (a fictional addition not in R). SP2 drops it. Users in Macaronesia (the Atlantic islands of Portugal/Spain) may select `east_atlantic` (which includes PT and ES); this is a user choice, not a code-level substitution claim.

**Note 2 — R has a 12th entry `other` that SP2 explicitly excludes:** R's `get_regional_seas_knowledge_base()` (line 84) defines a 12th entry `other` with `name_en = "Other/Regional"`, ecosystem types and common issues but **no countries** (R's `get_countries_for_sea("other")` returns an empty list). SP2 excludes this entry for two reasons: (a) it would violate the "≥1 country per sea" invariant in §3, and (b) `other` is a catch-all not a geographic sea, so country-aware SP3 logic has no basis to operate on it. If a future need for "Other" reappears, that's a separate spec/plan cycle (e.g. by reshaping the invariant or by allowing optional country-less entries with their own SP3 fallback).

### Carried-over seas: data deltas from SP1

The 4 seas that SP1 already had as placeholders (`baltic, mediterranean, north_sea, irish_sea`) get their attribute lists updated to R's authoritative values. **Persisted user data is unaffected** — `wizard_answers` only stores chosen values (e.g., `["Lithuania"]`), and those values remain valid choices because R's lists are supersets of (or overlap with) SP1's lists for these seas. But the *available* choices for new wizard sessions change:

- **Baltic countries** order changes from SP1's alphabetical to R's insertion order (`SE, FI, DK, DE, PL, LT, LV, EE, RU`). The set of countries is unchanged. The new `country_codes` field is parallel-indexed with `countries` and inherits R's order.
- **North Sea ecosystem_types**: R adds "Rocky shore" (5 → 6 entries). `common_issues`: R adds "Climate change" and reorders so Eutrophication moves to position 6 (5 → 6 entries). `countries`: SP1 had 7 (`United Kingdom, Norway, Denmark, Germany, Netherlands, Belgium, France`); R has 8 (adds Sweden). All SP1 countries survive into R as a strict superset.
- **Mediterranean ecosystem_types**: R adds "Offshore waters" (6 → 7); `common_issues` adds "Climate change" (5 → 6); `countries`: SP1 had 7 (`Italy, Spain, France, Greece, Croatia, Tunisia, Egypt`); R has 19 (adds Slovenia, Malta, Cyprus, Turkey, Algeria, Morocco, Libya, Israel, Lebanon, Syria, Montenegro, Albania). The SP1 set is a strict subset of R's; persisted user selections remain valid.
- **Irish Sea ecosystem_types**: R adds "Offshore waters" (5 → 6); `common_issues` adds "Climate change" (5 → 6); `countries`: SP1 had 2 (`Ireland, United Kingdom`); R has the same 2 in the same order. Set unchanged.

**Multi-sea country membership is allowed.** A country may appear in several seas (e.g., Denmark borders the Baltic, North Sea, and Arctic; France appears in Mediterranean, North Sea, East Atlantic, Atlantic, and Caribbean). The same ISO-2 code may carry **different display names** across seas — `FR` is `"France"` in Mediterranean but `"France (overseas)"` in Caribbean (per R lines 222-223), and `DK` is `"Denmark"` in Baltic but `"Denmark (Greenland)"` in Arctic (per R line 230). These suffixes are intentional and load-bearing — Test 10 pins them as a falsifiable invariant (see §7).

These deltas matter for code review — a reader comparing SP1's placeholder to SP2's KB should not be surprised by them. They do not require migration code (see SP1-data-compatibility section below).

---

## 4. Loader API (`sespy/regional_seas.py`)

```python
"""Regional seas knowledge base — replaces SP1's placeholder dict.

Loaded eagerly at module import via _load_kb(). The seas dict is
exposed via get_regional_seas() (matches SP1's contract shape) and
EU membership is exposed via get_eu_member_codes() for SP3.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

_KB_PATH = Path(__file__).parent / "regional_seas.json"


def _load_kb() -> dict[str, Any]:
    with _KB_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_KB = _load_kb()


def get_regional_seas() -> dict[str, dict[str, Any]]:
    """Return the seas dict in SP1's contract shape: {slug: {name,
    ecosystem_types, common_issues, countries, country_codes}}."""
    return _KB["regional_seas"]


def get_eu_member_codes() -> set[str]:
    """Return ISO-2 codes of EU member states as a fresh `set` for fast
    membership tests. Used by SP3's governance suggestions. (A `set` is
    constructed each call rather than cached; it's microseconds for 22
    elements and avoids any caller mutating a shared object.)"""
    return set(_KB["eu_member_codes"])
```

### Design choices

- **Eager load at module import.** The KB is ~10 KB and never changes at runtime; lazy loading would add complexity for zero benefit. Matches `sespy/templates/__init__.py`'s pattern.
- **No defensive copy on `get_regional_seas()`.** Callers in SP1 only read; future mutation would be a caller bug. Defensive copying everywhere has measurable cost in Python and obscures read-only intent.
- **`get_eu_member_codes()` returns a fresh `set` per call**, not a cached one — `set` construction from a 22-element list is microseconds and avoids any caller mutating a shared set.
- **No public refresh API.** A future hot-reload requirement can add `_KB = _load_kb()` to a refresh function; SP2 doesn't speculate.

---

## 5. Migration of `sespy/wizard.py`

**Before (SP1, lines 70-119 of `sespy/wizard.py`):**

The full block to be replaced consists of:
- Lines 70-86: a docstring-style comment describing the placeholder shape and the SP1→SP2 contract.
- Lines 88-119: the `REGIONAL_SEAS_PLACEHOLDER: dict[str, dict[str, Any]] = { ... }` literal with 5 seas (baltic, mediterranean, north_sea, irish_sea, macaronesia).

```python
REGIONAL_SEAS_PLACEHOLDER: dict[str, dict[str, Any]] = {
    "baltic": {
        "name": "Baltic Sea",
        "ecosystem_types": ["Open coast", "Archipelago", ...],
        # etc.
    },
    "mediterranean": { ... },
    # ... 5 seas total
}
```

**After (SP2): replace lines 70-119 entirely with this block.** The old comment block is superseded by the new one; the inline literal is replaced by the loader call.

```python
from .regional_seas import get_regional_seas

# REGIONAL_SEAS_PLACEHOLDER kept for backwards-compatibility with
# sespy/modules/ai_isa_wizard.py imports. The "PLACEHOLDER" suffix is
# now a misnomer — SP2 (2026-05-02) replaced the inline 5-sea mock
# with the real 11-sea KB loaded from sespy/regional_seas.json. The
# constant name stays so the SP1 wizard module's import doesn't break.
REGIONAL_SEAS_PLACEHOLDER: dict[str, dict[str, Any]] = get_regional_seas()
```

> **[HISTORICAL — post-`d14960e`.]** The "After" snippet above represents the immediate SP2 ship state (commit `984effd`), where the old name was kept as accepted technical debt. The post-SP2 cleanup commit `d14960e` (same day) renamed the constant to `REGIONAL_SEAS` and updated the comment accordingly. Current `sespy/wizard.py:81` reads `REGIONAL_SEAS: dict[str, dict[str, Any]] = get_regional_seas()`, with the misnomer-context comment dropped. See the post-implementation footer at the top of this spec for full commit lineage.

**SP1 wizard renderer impact: zero.** `_render_choice_one` (steps 0-1) and `_render_choice_many` (steps 2-3) read `data.get("ecosystem_types", [])`, `data.get("countries", [])`, `data.get("common_issues", [])`. All three field names are unchanged in SP2. `_render_choice_one` also reads `data["name"]` for the radio-button display label — `name` is also preserved in SP2's contract. The new `country_codes` field is ignored by SP1 (not read anywhere) and consumed only by SP3+.

**`ELEMENT_TYPE_MAP` and `WIZARD_STEPS`** in `sespy/wizard.py` are unchanged. SP2 only touches the seas constant.

### SP1-data compatibility

What the wizard persists to the project file (per SP1 `_on_next` in `sespy/modules/ai_isa_wizard.py`):

- **Step 0 (`regional_sea`) IS persisted to `ProjectMetadata.regional_sea`** via `_replace_metadata`.
- **Step 1 (`ecosystem_type`) IS persisted to `ProjectMetadata.ecosystem_type`** via `_replace_metadata`.
- **Steps 2-3 (`countries`, `main_issue`) are ephemeral** (handler does `pass`). They live in `wizard_answers: reactive.Value[dict]` for the active session only and are gone on app restart.
- **Steps 4-10 persist `Element` objects** to `IsaData.elements`.
- **Step 11 (Finish) optionally persists accepted `Connection` objects** to `IsaData.connections`.

So a user who completed SP1's wizard and saved their project has: their elements, their connections, AND a `regional_sea` slug + `ecosystem_type` string in metadata. The `countries` and `main_issue` lists are NOT in the saved file.

**No migration code is required because:**
- Persisted slugs (e.g., `"baltic"`, `"mediterranean"`, `"north_sea"`, `"irish_sea"`) survive into SP2's KB unchanged.
- The `ecosystem_type` is a free-text string from R's `ecosystem_types` list; it remains valid even if R's list expanded (e.g., a project saved with `"Estuary"` is still in baltic's ecosystem types).
- Active sessions aren't affected — SP2 ships in a separate deployment cycle (fresh app boot rebuilds the constant from JSON).
- Mid-flow upgrade is not a scenario — SESPy doesn't hot-reload modules; app restart is implicit in any deploy.

**One latent risk worth noting:** if a user selected `macaronesia` under SP1 (the SP1-only fictional addition), their saved project has `metadata.regional_sea = "macaronesia"`. After SP2 deploys, that slug no longer matches any key in `REGIONAL_SEAS_PLACEHOLDER`. SP1's wizard `_render_choice_one` uses the slug as a `selected=` argument to `ui.input_radio_buttons`; if the choices dict no longer contains it, Shiny falls back to the first choice or no selection (radio behavior depends on version). The wizard will not crash, but the saved value will display as unselected and a future Next would write the new selection over it.

**SP3 (the next consumer of `metadata.regional_sea`) MUST use `get_regional_seas().get(slug, {})` rather than a bare `[slug]` lookup.** The fallback is specifically `{}` (empty dict). SP3 should treat an empty-dict result as "no sea context available — skip all sea-dependent suggestion branches" (governance suggestions, country-list-derived inference, etc.). This is the same pattern as the SP1 wizard renderer's `data.get("ecosystem_types", [])` chain — degrade gracefully, never `KeyError`. The SP3 spec should call this out explicitly with the same `{}` fallback semantics so all stale-slug paths share one disposition.

**The same removal pattern generalizes**: any future spec that drops a sea slug from the KB creates a dangling reference for any saved project that used that slug. Mitigate via the `get(slug, {})` fallback at every consumer.

**Aside on regional-convention country sets (forward-compat note for SP3).** R's `.get_governance_elements_hardcoded` (lines 253-296) checks four regional-convention memberships (HELCOM, OSPAR, Barcelona, Arctic Council) by hardcoded country-code sets. **These do NOT coincide with per-sea `country_codes`** in the general case.

Three of the four happen to match a single sea exactly today:
- HELCOM matches `regional_seas["baltic"]["country_codes"]` exactly (same 9 codes in same order, R lines 109-118 vs 279).
- Barcelona Convention matches `regional_seas["mediterranean"]["country_codes"]` exactly (same 19 codes in same order, R lines 119-138 vs 282-284).
- Arctic Council matches `regional_seas["arctic"]["country_codes"]` exactly (same 8 codes in same order: `NO, RU, CA, US, DK, IS, SE, FI`, R lines 226-233 vs 291).

But these three coincidences are **not invariants** — treaty memberships are fixed by international law while the geographic country lists could evolve (e.g., a future R update could add a country to `arctic` for geographic completeness without that country joining the Arctic Council).

OSPAR is the structurally different case: `GB, NL, BE, DE, DK, NO, SE, FR, PT, ES, IE, IS` is a strict subset of `north_sea ∪ east_atlantic` that matches neither alone (PT, ES, IE, IS only appear in east_atlantic; NL, BE, DE, DK, SE only in north_sea; the rest in both). OSPAR CANNOT be derived from any single sea's `country_codes` even today.

**SP3 must own all four convention sets as its own constants** rather than attempting to derive them from `get_regional_seas()` — this is the only forward-compatible approach for both the structurally-different OSPAR case and the today-coincident HELCOM/Barcelona/Arctic Council cases. Documenting here so SP3 doesn't make the silent-derivation error.

The "carried-over seas data deltas" enumerated in §3 (Mediterranean adds Climate change, etc.) therefore have no migration consequences. They only affect what choices new wizard sessions present.

### Why keep the misnomer name `REGIONAL_SEAS_PLACEHOLDER`?

> **[HISTORICAL — superseded 2026-05-02 by post-SP2 cleanup commit `d14960e`.]** This subsection captured the design-time decision to defer the rename to SP3. The rename actually happened the same day SP2 merged, as a focused 1-commit cleanup on main (the "future cleanup PR" mentioned below arrived sooner than expected, ahead of SP3). The reasoning below is preserved as historical context for the architectural discussion at the time. The shipped post-rename name is `REGIONAL_SEAS`; SP3 inherits that name with no Task 0 chore required.

The architect-review of this spec flagged that keeping the name is technical debt: every future consumer (SP3, SP4, and beyond) will see `PLACEHOLDER` in their import and have to re-derive that "no, it's actually the real KB now." The cost of renaming is small — exactly two files (`sespy/wizard.py`: 1 definition; `sespy/modules/ai_isa_wizard.py`: 1 import + 3 use sites at lines 46, 55, 71 as of SP1 commit `dfedd28`; SP3 will likely move them when it touches that file). Approximately 5 lines of mechanical change.

This spec keeps the original name **as an explicit, accepted technical debt** for SP2 because: (a) the user-confirmed scope of SP2 is "drop-in data swap with zero touch on SP1's renderer," (b) keeping the name guarantees zero risk of breaking the SP1 wizard module, and (c) a future cleanup PR (or the start of SP3, which will already be touching `ai_isa_wizard.py` to wire `suggest_connections`) can do the rename in a focused commit. SP3 is the natural rename moment — it'll be touching the imports anyway.

The misnomer is documented at the rename site (the comment in §5's "After" snippet). SP3's plan should include the rename as a Task 0-style chore.

---

## 6. Error handling

Three failure modes, all hard-fail at import time (preferred over silent fallback because a missing/broken KB is a build/install bug, not user input):

| Failure | Where it raises | Behavior |
|---|---|---|
| `regional_seas.json` missing | `_load_kb()` → `FileNotFoundError` | App fails to boot with clear traceback |
| JSON malformed | `_load_kb()` → `json.JSONDecodeError` | Same — fails at boot |
| Schema mismatch (missing field) | NOT checked at runtime | Caught by `tests/test_regional_seas.py` at CI time |

### Why no runtime schema validation

The data is static and version-controlled. Once the test suite passes at commit time, the JSON is provably correct. Adding pydantic or similar runtime validation would:
- Add a dependency for zero benefit (errors caught by tests instead).
- Slow module import.
- Obscure where the contract lives (the schema would be in code AND prose).

This matches the existing pattern in `sespy/templates/__init__.py`, which loads its JSON files with no runtime validation and relies on tests for correctness. (`data/sample_ses.json` at the repo root is a different category — it's loaded by `data_structure.load_sample()` for end-user sample-project loading, not a package-internal data file. The `sespy/templates/*.json` analogy is the right one for SP2.)

---

## 7. Testing (`tests/test_regional_seas.py`)

12 unit tests covering schema, invariants, and integration. **Note on schema validation**: tests verify *presence* of required top-level keys (`regional_seas`, `eu_member_codes`) rather than *exact* key-set equality. This is deliberate forward-compat: SP3 may add new top-level keys to `regional_seas.json` (e.g., `governance_frameworks` for OSPAR/HELCOM/Barcelona/Arctic-Council member sets) without breaking SP2's tests. SP2's loader (`_load_kb`) reads only the two keys it cares about and ignores extras — this is just JSON's natural behavior.

The 12 tests:

1. `test_get_regional_seas_returns_11_seas` — count check (`len() == 11` and `"other" not in seas`, the latter explicit because R has 12 entries and SP2 excludes one — see §3 Note 2).
2. `test_all_expected_sea_slugs_present` — set-equality on slug names (matches the 11-slug list in §3).
3. `test_every_sea_has_required_fields` — schema check (name, ecosystem_types, common_issues, countries, country_codes) AND that all 4 list-typed fields are non-empty (`len >= 1`).
4. `test_countries_and_country_codes_are_parallel` — `len()` invariant per sea.
5. `test_country_codes_are_iso2_format` — every code matches `^[A-Z]{2}$`.
6. `test_ecosystem_types_non_empty` — every sea has ≥1 ecosystem type. (Redundant with test 3's tightened version; kept as a focused regression test.)
7. `test_common_issues_non_empty` — every sea has ≥1 common issue. (Same as test 6 rationale.)
8. `test_eu_member_codes_returns_set` — type check + spot value check (`"SE" in codes`, `"US" not in codes`).
9. `test_eu_member_codes_subset_of_sea_codes` — every EU code appears in at least one sea's `country_codes` (catches drift where the EU index references a code never listed in any sea).
10. `test_country_name_code_spot_checks` — per-sea name↔code pair sanity. Catches silent index transposition (e.g., `country_codes[i]` reading `"LV"` when `countries[i]` reads `"Lithuania"`). Per-sea reference table:

    | sea | expected name | expected code |
    |---|---|---|
    | baltic | Lithuania | LT |
    | baltic | Sweden | SE |
    | mediterranean | Spain | ES |
    | mediterranean | Greece | GR |
    | north_sea | Netherlands | NL |
    | irish_sea | Ireland | IE |
    | east_atlantic | Portugal | PT |
    | black_sea | Romania | RO |
    | atlantic | United States | US |
    | pacific | Japan | JP |
    | indian | India | IN |
    | caribbean | Cuba | CU |
    | caribbean | France (overseas) | FR |
    | caribbean | Netherlands (overseas) | NL |
    | arctic | Norway | NO |
    | arctic | Denmark (Greenland) | DK |

    For each row: `i = data["countries"].index(name)` then `assert data["country_codes"][i] == code`. The `(overseas)` and `(Greenland)` suffix rows are deliberate — they pin the suffix as a test-enforced invariant so a future "name normalization" pass can't silently strip them (the suffixes are load-bearing context per R lines 222-223 and 230).

11. `test_sp1_wizard_module_imports_real_kb` — smoke check on `sespy.wizard.REGIONAL_SEAS_PLACEHOLDER`. *[HISTORICAL — post-`d14960e` the test imports `REGIONAL_SEAS` instead; assertion content is unchanged.]* Asserts: `len() == 11`, `"baltic" in placeholder`, `"macaronesia" not in placeholder` (the SP1 fictional addition was dropped), `placeholder["baltic"]["name"] == "Baltic Sea"`, `"Sweden" in placeholder["baltic"]["countries"]`, AND the new SP2-only field is also visible through the alias: `"country_codes" in placeholder["baltic"]` and `"SE" in placeholder["baltic"]["country_codes"]`. (Without this final pair, the test would pass against SP1's pre-merge state and not catch a regression where the loader returned the old shape.)

12. `test_eu_member_codes_count` — `len(get_eu_member_codes()) == 22`. Exact count (post-Brexit, as of 2026-05-02) catches accidental additions/removals. The 22-code list in `regional_seas.json` is the truth source; this test pins it.

    **Note on the count:** the EU has 27 member states. The KB's `eu_member_codes` is 22, not 27, because it tracks only EU members that border at least one of the 11 KB seas. The 5 landlocked EU states (Austria `AT`, Hungary `HU`, Luxembourg `LU`, Slovakia `SK`, Czech Republic `CZ`) don't border any sea in the catalog and are correctly absent. This is consistent with the §3 invariant "every code in `eu_member_codes` appears in at least one sea's `country_codes`" — a landlocked country can't satisfy that invariant. R's hardcoded EU list at line 262 also has 22 codes for the same reason.

    **Maintenance note**: if EU membership changes (e.g., Albania joins) AND the new member borders one of the 11 KB seas, update both `eu_member_codes` in `regional_seas.json` AND the `== 22` assertion in this test in the same commit, with a commit message referencing the accession event. If the new member doesn't border any KB sea, no change is needed (the invariant still holds — they wouldn't appear in any sea's `country_codes`).

**SP1 wizard tests** (`tests/test_wizard.py`): the existing `test_regional_seas_placeholder_has_at_least_baltic` is a shape check (it asserts `"baltic" in REGIONAL_SEAS_PLACEHOLDER` and that baltic has `name`/`ecosystem_types`/`countries`/`common_issues`). It still passes after SP2 — Baltic is still in the KB with all those fields. **No SP1 test changes required.**

**E2e impact: zero.** `tests/test_wizard_e2e.py` uses `'baltic'`, `'Open coast'`, `'Lithuania'`, `'Eutrophication'` — all present in the real KB. All 6 e2e cases pass unchanged.

**Test count delta:** +12 unit. New baseline: **134 unit + 21 e2e**.

---

## 8. Build sequence (preview)

This section is a **task summary** — not a substitute for an executable implementation plan. Per SESPy convention (matching `docs/superpowers/plans/2026-05-01-ai-isa-wizard-sp1.md` and `2026-04-29-pims-project-setup.md`), a separate plan file at `docs/superpowers/plans/2026-05-02-ai-isa-wizard-sp2.md` MUST be written before implementation begins. The plan file expands each task below into TDD step-by-step sequences with exact bash commands, expected outputs at each step, and explicit commit operations. The next step after spec approval is to invoke `superpowers:writing-plans`.

The 6 tasks below set the contract for that plan:

| Task | What | Commit | Effort |
|---|---|---|---|
| 0 | Verify env, cut `feat/ai-isa-wizard-sp2`, baseline 122 unit + 21 e2e green | (no commit — read-only) | 5 min |
| 1 | Create `sespy/regional_seas.json` with all 11 seas + EU codes | `feat(regional_seas): knowledge base data file (11 seas, 22 EU codes)` | ~90 min |
| 2 | Create `sespy/regional_seas.py` loader + `tests/test_regional_seas.py` (TDD: 12 tests) | `feat(regional_seas): Python loader module + 12 unit tests` | ~30 min |
| 3 | Modify `sespy/wizard.py` lines 70-119 to use loader; verify SP1 tests still pass | `refactor(wizard): swap REGIONAL_SEAS_PLACEHOLDER inline to loader call` | ~10 min |
| 4 | Run SP1 e2e + browser smoke test (11 seas visible, country lists per sea) | (no commit — verification step; if a fix is needed, commit `fix(...)` for the specific issue) | ~30 min |
| 5 | Update `README.md`: 122 → 134 unit tests at **both** occurrences (currently lines 73 and 139); final verification | `docs(readme): bump unit test count to 134 after SP2 KB swap` | ~10 min |

**Total estimate: ~3 hours** focused work. Tasks 2-3-5 are mechanical; Task 1 is data porting; Task 4 is the only manual verification step.

**Branch:** `feat/ai-isa-wizard-sp2` cut from main at HEAD `dfedd28`. **Expected ~5 commits** (Task 0 is read-only; Task 4 commits only if a fix is needed).

The implementation plan should target SP1's plan file as its template — same task granularity, same TDD discipline, same expected-output assertions at each step.

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| KB drifts from R as R adds seas/countries | Out of scope for SP2 — current snapshot. Future R-side updates require a separate sync task. |
| `country_codes` order doesn't match `countries` order in some hand-edit | Test 4 (`test_countries_and_country_codes_are_parallel`) catches length mismatch. Test 10 (`test_country_name_code_spot_checks`) catches per-index transposition for ≥1 named pair per sea. The combination of these two is sufficient for the static-data context: a transposition that swaps two non-spot-checked entries within the same sea would still pass both tests, but the JSON is authored once from R and reviewed at commit. The accepted residual risk is documented here. |
| `eu_member_codes` index gets stale (country leaves/joins EU) | Static data; future EU membership change requires a separate update task. As of 2026-05-02, the 22-state list reflects post-Brexit reality. Test 12 pins the count at 22 to catch accidental edits. |
| SP1 renderer reads a field SP2 renames | None — SP2 only ADDS fields (`country_codes`). All SP1-consumed names (`name`, `ecosystem_types`, `countries`, `common_issues`) are preserved. |
| JSON file path resolution breaks when SESPy is installed as a package | `Path(__file__).parent / "regional_seas.json"` works for both source-tree and installed-package layouts. Mirrors `sespy/templates/__init__.py:_templates_dir()`. |
| Caribbean has display names "France (overseas)" / "Netherlands (overseas)" | Authentic to R (lines 222-223) — these are real countries with real EU-overseas-territory status. The display name is what users see in the country chooser; the ISO code (FR / NL) is what SP3 governance lookups consume. The display-name suffix is intentional and not a defect; spec note documents it for future readers who might see the "(overseas)" suffix and try to "clean it up." Don't. **Test 10's caribbean and arctic spot-check rows enforce the suffixes** — a normalization that drops them will fail tests. |
| Step 0's `ui.input_radio_buttons` widget shows 11 sea radios (was 5 in SP1) | SP1 spec §2 noted "use `ui.input_radio_buttons`, or `ui.input_select` if list >5". SP1's renderer hard-coded `input_radio_buttons` and SP2 doesn't change the renderer. 11 radios + a "—" sentinel = 12 vertical entries — workable on desktop, tall on small viewports. Accepted UX trade-off for SP2 (drop-in data swap, zero renderer touch). A widget swap is deferred to a future polish PR or to SP3 (which will already be touching `ai_isa_wizard.py`). |
| `get_regional_seas()` returns the inner dict by reference, not a copy | Caller-mutation safety is enforced socially (callers MUST treat the result as read-only — see §4 design choice). A future tightening could wrap the return value in `types.MappingProxyType` to make mutation raise immediately; SP2 doesn't do this because (a) all current callers are read-only and (b) `MappingProxyType` only freezes the top level and inner dicts/lists remain mutable, which gives a false sense of safety. If a future consumer needs hard immutability, it can build it on top of `get_regional_seas()`. |

---

## 10. Out of scope, explicitly

- Real i18n for sea/country names (English-only for SP2). **Future retrofit shape**: the most likely path is to add an optional `name_i18n_key: str` to each sea record (e.g., `"regional_sea.baltic"`) and corresponding entries in `sespy/translations/core.json` under that key prefix. The wizard renderer would then prefer `t(data["name_i18n_key"])` if present, falling back to `data["name"]` otherwise. Country-name i18n would follow the same pattern with per-country keys. This is additive (`name` stays as the English fallback) so it doesn't break SP2's contract — but the schema change means it's not zero-touch and should be its own spec/plan cycle, not an inline cleanup.
- Country-aware suggestion helpers (governance, socioeconomic) — SP3.
- TF-IDF connection scoring backend — SP3.
- Claude API backend — SP4.
- A "regional seas admin UI" for editing the KB at runtime — never planned.
- Map-based sea picker — possible future enhancement, not part of any SP.
- Per-country detail beyond `code`/`name`/`eu_member` — SP3 may extend per its needs.

---

## 11. Definition of done

- `sespy/regional_seas.json` exists and parses; `sespy/regional_seas.py` loads it.
- `get_regional_seas()` returns 11 seas with the SP1 contract shape + `country_codes` field.
- `get_eu_member_codes()` returns a set of 22 ISO-2 codes.
- `tests/test_regional_seas.py`: 12 tests pass.
- `sespy/wizard.py` imports from the loader; `REGIONAL_SEAS_PLACEHOLDER` works as before. *[HISTORICAL — post-`d14960e` the constant is named `REGIONAL_SEAS`; the loader-call substitution shipped first (commit `984effd`), the rename followed (commit `d14960e`).]*
- All existing SP1 unit tests pass (122 → unchanged behavior).
- All 6 SP1 e2e cases pass unchanged.
- New baseline: 134 unit tests + 21 e2e scripts.
- Wizard step 0 shows 11 radio buttons in browser; step 1 ecosystem types are sea-specific; step 2 country list is sea-specific.
- `README.md` reflects 134 unit tests.
- Branch ready for fast-forward merge to main.
