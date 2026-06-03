# AI-ISA Wizard SP2 Implementation Plan

> **Status: Implemented** · 6 plan tasks shipped on `feat/ai-isa-wizard-sp2`, fast-forwarded to `main` 2026-05-02 (commits `ce569f1` JSON data → `8b4ca90` loader + 12 unit tests → `984effd` `sespy/wizard.py` swap → `3c18fd8` README bump). Three plan-review rounds before execution (`b9ad2a3` round-1, `21ae6e7` round-2, `090b871` round-3) plus one post-merge plan-fix backport (`c92f62c` selectize-aware DOM probe in Task 4). Subsequent post-SP2 cleanup commit `d14960e` (same day) renamed `REGIONAL_SEAS_PLACEHOLDER` → `REGIONAL_SEAS`, **superseding Task 3's misnomer-keeping intent** — the rename was deferred to SP3 in the spec but executed sooner as a focused commit. The plan's 17 references to `REGIONAL_SEAS_PLACEHOLDER` are stale post-rename but were correct at execution time; the plan is a frozen operational artifact.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SP1's `REGIONAL_SEAS_PLACEHOLDER` (5 hardcoded seas in `sespy/wizard.py`) with the real 11-sea knowledge base ported from R's `modules/ai_isa_knowledge_base.R`. Drop-in data swap — no wizard renderer or state-machine changes; the SP1→SP2 contract is preserved.

**Architecture:** Two new files at the `sespy/` package root: `sespy/regional_seas.py` (a ~30-LOC pure-Python loader exposing `get_regional_seas()` and `get_eu_member_codes()`) and `sespy/regional_seas.json` (the data file — 11 seas + 22-code EU index). One new test file `tests/test_regional_seas.py` (12 tests). One small edit to `sespy/wizard.py` swaps the inline `REGIONAL_SEAS_PLACEHOLDER` literal for a loader call.

**Tech Stack:** Python 3.11, Shiny for Python (unchanged from SP1), `dataclasses`, `json`, `pathlib`, Playwright (only for the SP1 e2e re-run in Task 4). Existing micromamba env `shiny`. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-05-02-ai-isa-wizard-sp2-design.md`](../specs/2026-05-02-ai-isa-wizard-sp2-design.md) (~400 LOC, converged after 9 rounds of multi-agent review).

**Source of truth for all data values** (read once for Task 1, again on any Test 10 spot-check failure):
`..\SESToolbox\MarineSABRES_SES_Shiny\modules\ai_isa_knowledge_base.R` (sibling repo to SESPy, not in SESPy itself):
- Lines 16-91: `get_regional_seas_knowledge_base()` — sea metadata.
- Lines 104-241: `get_countries_for_sea()` — per-sea country lookups.
- Lines 262-264: hardcoded EU member ISO-2 codes.

**Sub-project context.** SP2 of 4 in the AI-Assisted SES Creation series. SP1 shipped 2026-05-01 at commit `dfedd28` on main (122 unit + 21 e2e baseline). SP3 (TF-IDF + governance helpers) and SP4 (Claude API backend) follow as separate sub-projects. SP2 is the smallest of the four — a pure data swap with zero behavioral change.

**Branch:** `feat/ai-isa-wizard-sp2` cut from main at HEAD `dfedd28`. **Expected ~5 commits** (Task 0 read-only; Task 4 commits only on fix). Total estimated effort ~3 hours.

---

## Task 0: Verify environment and branch

- [ ] **Step 1: Confirm working tree is clean and on `main`**

```bash
git status --short
git branch --show-current
```
Expected: no output from `git status --short` (or only `?? .claude/`, `?? .tmp/`); branch is `main`.

- [ ] **Step 2: Confirm main is at the SP1 ship commit**

```bash
git log --oneline -1
```
Expected: starts with `dfedd28` or a newer commit on main (later docs commits are fine — the spec was committed after SP1 shipped).

- [ ] **Step 3: Cut the feature branch**

```bash
git checkout -b feat/ai-isa-wizard-sp2
```
Expected: `Switched to a new branch 'feat/ai-isa-wizard-sp2'`.

- [ ] **Step 4: Confirm spec and SP1 plan exist**

```bash
ls docs/superpowers/specs/2026-05-02-ai-isa-wizard-sp2-design.md
ls docs/superpowers/plans/2026-05-01-ai-isa-wizard-sp1.md
```
Expected: both paths print without "No such file" errors.

- [ ] **Step 5: Verify the unit test suite is green at start (exactly 122 baseline)**

```bash
micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py tests/test_report.py tests/test_templates.py tests/test_network.py tests/test_data_structure.py tests/test_utils.py tests/test_wizard.py
```
Expected: `122 passed`. **If a different number appears, STOP** — main has drifted from the spec's baseline at commit `dfedd28`, and Task 5's hardcoded `122 → 134` README edits would write a stale number. The fix is to update Task 5 Steps 2-3 substitutions to use the actual baseline `→ baseline + 12` before continuing (don't try to roll back to `dfedd28` directly — this plan and spec live on later commits, and checking out `dfedd28` would lose access to them). The plan assumes 122 throughout; do not proceed past this step without resolving the discrepancy.

- [ ] **Step 6: Verify the wait-for-port helper exists**

```bash
ls .tmp/wait_port.py
```
Expected: file exists. If missing, create it (gitignored, used in Task 4):

```python
import urllib.request, time, sys

for i in range(60):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000", timeout=1).read(1)
        print(f"ready after {i*0.5:.1f}s")
        sys.exit(0)
    except Exception:
        time.sleep(0.5)
print("TIMEOUT")
sys.exit(1)
```

- [ ] **Step 7: Confirm the SP1 wizard.py block to be replaced (Task 3 reference)**

```bash
sed -n '70,119p' sespy/wizard.py
```
Expected: the output starts with the comment block `# Regional-seas placeholder (SP1 mock; SP2 ports the real KB).` (line 70) and ends with the closing `}` of the `REGIONAL_SEAS_PLACEHOLDER` dict (line 119). 5 sea entries: `baltic`, `mediterranean`, `north_sea`, `irish_sea`, `macaronesia`. If the line range or content differs, update Task 3 sed/edit invocations to match the actual current state.

No commit. This task is environment verification only.

---

## Task 1: Create `sespy/regional_seas.json` with all 11 seas + EU codes

**Files:**
- Create: `sespy/regional_seas.json`

This is the largest task by line count (~250 LOC of JSON), but mechanical — every value is a verbatim port from R's `ai_isa_knowledge_base.R`. The 4 invariants from spec §3 must hold once authored:
1. Parallel index: `len(countries) == len(country_codes)` per sea, and `countries[i]` is the human name for `country_codes[i]`.
2. ISO-2 codes match `^[A-Z]{2}$`.
3. Every sea has ≥1 entry in each list-typed field.
4. Every code in `eu_member_codes` appears in at least one sea's `country_codes`.

The full JSON is given verbatim below; copy it as-is. Task 2's tests verify these invariants automatically.

- [ ] **Step 1: Create `sespy/regional_seas.json` with this exact content**

```json
{
  "regional_seas": {
    "baltic": {
      "name": "Baltic Sea",
      "ecosystem_types": ["Open coast", "Rocky coast (Schären)", "Archipelago", "Island", "Estuary", "Coastal lagoon", "Offshore waters"],
      "common_issues": ["Eutrophication", "Overfishing", "Pollution", "Invasive species", "Climate change"],
      "countries": ["Sweden", "Finland", "Denmark", "Germany", "Poland", "Lithuania", "Latvia", "Estonia", "Russia"],
      "country_codes": ["SE", "FI", "DK", "DE", "PL", "LT", "LV", "EE", "RU"]
    },
    "mediterranean": {
      "name": "Mediterranean Sea",
      "ecosystem_types": ["Open coast", "Island", "Coastal lagoon", "Rocky shore", "Sandy beach", "Seagrass meadow", "Offshore waters"],
      "common_issues": ["Overfishing", "Coastal development", "Tourism pressure", "Marine litter", "Invasive species", "Climate change"],
      "countries": ["Spain", "France", "Italy", "Greece", "Croatia", "Slovenia", "Malta", "Cyprus", "Turkey", "Tunisia", "Algeria", "Morocco", "Libya", "Egypt", "Israel", "Lebanon", "Syria", "Montenegro", "Albania"],
      "country_codes": ["ES", "FR", "IT", "GR", "HR", "SI", "MT", "CY", "TR", "TN", "DZ", "MA", "LY", "EG", "IL", "LB", "SY", "ME", "AL"]
    },
    "north_sea": {
      "name": "North Sea",
      "ecosystem_types": ["Open coast", "Estuary", "Tidal flat", "Offshore waters", "Rocky shore", "Sandy beach"],
      "common_issues": ["Overfishing", "Oil and gas extraction", "Shipping", "Wind energy development", "Climate change", "Eutrophication"],
      "countries": ["United Kingdom", "Netherlands", "Belgium", "Germany", "Denmark", "Norway", "Sweden", "France"],
      "country_codes": ["GB", "NL", "BE", "DE", "DK", "NO", "SE", "FR"]
    },
    "irish_sea": {
      "name": "Irish Sea",
      "ecosystem_types": ["Open coast", "Estuary", "Coastal lagoon", "Rocky shore", "Sandy beach", "Offshore waters"],
      "common_issues": ["Overfishing", "Coastal development", "Shipping", "Marine litter", "Eutrophication", "Climate change"],
      "countries": ["Ireland", "United Kingdom"],
      "country_codes": ["IE", "GB"]
    },
    "east_atlantic": {
      "name": "East Atlantic",
      "ecosystem_types": ["Open coast", "Continental shelf", "Offshore waters", "Rocky shore", "Sandy beach", "Estuary"],
      "common_issues": ["Overfishing", "Climate change", "Ocean acidification", "Shipping", "Coastal erosion", "Marine litter"],
      "countries": ["Portugal", "Spain", "France", "Ireland", "United Kingdom", "Norway", "Iceland", "Morocco", "Mauritania", "Senegal"],
      "country_codes": ["PT", "ES", "FR", "IE", "GB", "NO", "IS", "MA", "MR", "SN"]
    },
    "black_sea": {
      "name": "Black Sea",
      "ecosystem_types": ["Open coast", "Delta", "Coastal lagoon", "Offshore waters", "Estuary"],
      "common_issues": ["Eutrophication", "Overfishing", "Pollution", "Invasive species", "Coastal erosion"],
      "countries": ["Bulgaria", "Romania", "Turkey", "Georgia", "Ukraine", "Russia"],
      "country_codes": ["BG", "RO", "TR", "GE", "UA", "RU"]
    },
    "atlantic": {
      "name": "Atlantic Ocean",
      "ecosystem_types": ["Open ocean", "Island", "Estuary", "Continental shelf", "Coastal upwelling", "Open coast", "Offshore waters"],
      "common_issues": ["Overfishing", "Climate change", "Ocean acidification", "Shipping", "Deep-sea mining"],
      "countries": ["Portugal", "Spain", "France", "Ireland", "United Kingdom", "United States", "Canada", "Brazil", "Norway", "Iceland"],
      "country_codes": ["PT", "ES", "FR", "IE", "GB", "US", "CA", "BR", "NO", "IS"]
    },
    "pacific": {
      "name": "Pacific Ocean",
      "ecosystem_types": ["Coral reef", "Island", "Atoll", "Open ocean", "Coastal waters", "Mangrove", "Offshore waters"],
      "common_issues": ["Overfishing", "Coral bleaching", "Plastic pollution", "Climate change", "Illegal fishing"],
      "countries": ["Australia", "New Zealand", "Japan", "Philippines", "Indonesia", "Fiji", "Papua New Guinea", "United States", "Chile", "China"],
      "country_codes": ["AU", "NZ", "JP", "PH", "ID", "FJ", "PG", "US", "CL", "CN"]
    },
    "indian": {
      "name": "Indian Ocean",
      "ecosystem_types": ["Coral reef", "Island", "Mangrove", "Open coast", "Lagoon", "Offshore waters"],
      "common_issues": ["Overfishing", "Coastal erosion", "Mangrove loss", "Climate change", "Illegal fishing"],
      "countries": ["India", "Sri Lanka", "Maldives", "Kenya", "Tanzania", "Mozambique", "Madagascar", "Australia", "South Africa", "Oman"],
      "country_codes": ["IN", "LK", "MV", "KE", "TZ", "MZ", "MG", "AU", "ZA", "OM"]
    },
    "caribbean": {
      "name": "Caribbean Sea",
      "ecosystem_types": ["Coral reef", "Island", "Mangrove", "Seagrass bed", "Sandy beach", "Open coast"],
      "common_issues": ["Coral bleaching", "Overfishing", "Tourism pressure", "Hurricanes", "Sargassum blooms"],
      "countries": ["Cuba", "Jamaica", "Dominican Republic", "Trinidad and Tobago", "Barbados", "Bahamas", "Mexico", "Colombia", "Venezuela", "Belize", "Honduras", "France (overseas)", "Netherlands (overseas)"],
      "country_codes": ["CU", "JM", "DO", "TT", "BB", "BS", "MX", "CO", "VE", "BZ", "HN", "FR", "NL"]
    },
    "arctic": {
      "name": "Arctic Ocean",
      "ecosystem_types": ["Sea ice", "Island", "Open ocean", "Fjord", "Coastal waters", "Continental shelf"],
      "common_issues": ["Climate change", "Sea ice loss", "Oil and gas exploration", "Shipping increase", "Arctic fisheries"],
      "countries": ["Norway", "Russia", "Canada", "United States", "Denmark (Greenland)", "Iceland", "Sweden", "Finland"],
      "country_codes": ["NO", "RU", "CA", "US", "DK", "IS", "SE", "FI"]
    }
  },
  "eu_member_codes": ["SE", "FI", "DK", "DE", "PL", "LT", "LV", "EE", "ES", "FR", "IT", "GR", "HR", "SI", "MT", "CY", "NL", "BE", "PT", "IE", "BG", "RO"]
}
```

**Critical authoring notes** — these are not optional:
- The `(overseas)` suffixes in `caribbean` (`"France (overseas)"`, `"Netherlands (overseas)"`) and the `(Greenland)` suffix in `arctic` (`"Denmark (Greenland)"`) are intentional and load-bearing per spec §3 and R lines 222-223 / 230. **Don't normalize them.** Test 10 will catch a stripped suffix.
- The `mediterranean` entry has 19 countries (the largest); double-check the count when copying.
- R's 12th sea entry `other` (R line 84) is deliberately excluded — see spec §3 Note 2. It would have no `countries` and would violate the ≥1-country invariant.
- `eu_member_codes` is exactly 22 codes (post-Brexit; 5 landlocked EU states are correctly absent). See spec §7 Test 12 explanation.

- [ ] **Step 2: Verify the JSON parses**

```bash
micromamba run -n shiny python -c "import json; data = json.load(open('sespy/regional_seas.json', encoding='utf-8')); print(f'parse: OK ({len(data[\"regional_seas\"])} seas, {len(data[\"eu_member_codes\"])} EU codes)')"
```
Expected: `parse: OK (11 seas, 22 EU codes)`. Any other output (or a `JSONDecodeError`) means a syntax mistake in Step 1; fix and re-run.

- [ ] **Step 3: Quick invariant sanity check (engineer pre-flight)**

```bash
micromamba run -n shiny python -c "
import json, re
d = json.load(open('sespy/regional_seas.json', encoding='utf-8'))
seas = d['regional_seas']
eu = set(d['eu_member_codes'])
assert len(seas) == 11, f'expected 11 seas, got {len(seas)}'
assert 'other' not in seas, '\"other\" must be excluded (spec §3 Note 2)'
for slug, info in seas.items():
    assert len(info['countries']) == len(info['country_codes']), f'{slug}: parallel-index length mismatch'
    for code in info['country_codes']:
        assert re.fullmatch(r'[A-Z]{2}', code), f'{slug}: bad ISO-2 code {code!r}'
    assert info['countries'], f'{slug}: empty countries'
    assert info['country_codes'], f'{slug}: empty country_codes'
    assert info['ecosystem_types'], f'{slug}: empty ecosystem_types'
    assert info['common_issues'], f'{slug}: empty common_issues'
all_codes = {c for s in seas.values() for c in s['country_codes']}
missing = eu - all_codes
assert not missing, f'EU codes missing from sea data: {sorted(missing)}'
print(f'invariants OK: {len(seas)} seas, all parallel, {len(eu)} EU codes all in seas')
"
```
Expected: `invariants OK: 11 seas, all parallel, 22 EU codes all in seas`. Any `AssertionError` points to the field that failed; fix the JSON and re-run.

This is a pre-Task-2 smoke gate — Task 2's `tests/test_regional_seas.py` will assert the same invariants more comprehensively, but catching them now means Task 2's tests pass on first run.

- [ ] **Step 4: Commit**

```bash
git add sespy/regional_seas.json
git commit -m "feat(regional_seas): knowledge base data file (11 seas, 22 EU codes)"
```

---

## Task 2: Create `sespy/regional_seas.py` loader + `tests/test_regional_seas.py` (TDD: 12 tests)

**Files:**
- Create: `sespy/regional_seas.py`
- Create: `tests/test_regional_seas.py`

Strict TDD: write the 12 tests first (red), then the loader (green). The loader is so small (~30 LOC) that the green step is one block of code, not a per-test progression.

- [ ] **Step 1: Create `tests/test_regional_seas.py` with all 12 failing tests**

```python
"""Unit tests for sespy.regional_seas — knowledge base loader.

Validates schema, invariants, and SP1 wizard module integration. The
tests are listed in spec §7 of 2026-05-02-ai-isa-wizard-sp2-design.md.
"""
from __future__ import annotations

import re

from sespy.regional_seas import get_regional_seas, get_eu_member_codes


# Test 1
def test_get_regional_seas_returns_11_seas():
    """Spec §3: 11 seas in scope; R's 12th 'other' entry deliberately
    excluded per Note 2."""
    seas = get_regional_seas()
    assert len(seas) == 11
    assert "other" not in seas


# Test 2
def test_all_expected_sea_slugs_present():
    """Set-equality on the 11-slug list in spec §3."""
    seas = get_regional_seas()
    expected = {
        "baltic", "mediterranean", "north_sea", "irish_sea",
        "east_atlantic", "black_sea", "atlantic", "pacific",
        "indian", "caribbean", "arctic",
    }
    assert set(seas.keys()) == expected


# Test 3
def test_every_sea_has_required_fields():
    """Schema check + non-empty for the 4 list-typed fields. Each sea
    must have name, ecosystem_types, common_issues, countries,
    country_codes (the new SP2 field)."""
    required = {"name", "ecosystem_types", "common_issues",
                "countries", "country_codes"}
    list_fields = ("ecosystem_types", "common_issues",
                   "countries", "country_codes")
    for slug, data in get_regional_seas().items():
        assert required.issubset(data.keys()), (
            f"{slug} missing fields: {required - data.keys()}"
        )
        for field in list_fields:
            assert len(data[field]) >= 1, (
                f"{slug}: {field} is empty (≥1 required)"
            )


# Test 4
def test_countries_and_country_codes_are_parallel():
    """Length invariant — `countries[i]` is the human name for
    `country_codes[i]`. Catches a hand-edit that adds or drops one
    element from only one of the two arrays."""
    for slug, data in get_regional_seas().items():
        assert len(data["countries"]) == len(data["country_codes"]), (
            f"{slug}: {len(data['countries'])} names vs "
            f"{len(data['country_codes'])} codes"
        )


# Test 5
def test_country_codes_are_iso2_format():
    """Every code is exactly 2 uppercase Latin letters. Pattern uses
    no ^/$ anchors because `fullmatch()` already anchors both ends —
    keeping anchors would be redundant and would silently mask future
    refactors to `match()` (which doesn't anchor the end)."""
    pattern = re.compile(r"[A-Z]{2}")
    for slug, data in get_regional_seas().items():
        for code in data["country_codes"]:
            assert pattern.fullmatch(code), (
                f"{slug}: invalid ISO-2 code {code!r}"
            )


# Test 6
def test_ecosystem_types_non_empty():
    """Focused regression test (overlaps with Test 3's tightening)."""
    for slug, data in get_regional_seas().items():
        assert len(data["ecosystem_types"]) >= 1, (
            f"{slug}: no ecosystem types"
        )


# Test 7
def test_common_issues_non_empty():
    """Focused regression test (overlaps with Test 3's tightening)."""
    for slug, data in get_regional_seas().items():
        assert len(data["common_issues"]) >= 1, (
            f"{slug}: no common issues"
        )


# Test 8
def test_eu_member_codes_returns_set():
    """Type check + spot value check."""
    codes = get_eu_member_codes()
    assert isinstance(codes, set)
    assert "SE" in codes  # Sweden is EU
    assert "US" not in codes  # USA is not EU


# Test 9
def test_eu_member_codes_subset_of_sea_codes():
    """Every EU code must appear in at least one sea's country_codes.
    Catches drift where eu_member_codes references a code never listed
    in any sea (e.g., a typo or a stale entry)."""
    all_codes = set()
    for data in get_regional_seas().values():
        all_codes.update(data["country_codes"])
    eu = get_eu_member_codes()
    missing = eu - all_codes
    assert not missing, (
        f"EU codes missing from sea data: {sorted(missing)}"
    )


# Test 10
def test_country_name_code_spot_checks():
    """Per-sea name↔code pair sanity. Catches silent index transposition
    (e.g., country_codes[i] reading "LV" when countries[i] reads
    "Lithuania"). The (overseas) and (Greenland) suffix rows pin those
    suffixes as a test-enforced invariant; a future "name normalization"
    pass that drops them will fail this test."""
    seas = get_regional_seas()
    spot_checks = [
        ("baltic", "Lithuania", "LT"),
        ("baltic", "Sweden", "SE"),
        ("mediterranean", "Spain", "ES"),
        ("mediterranean", "Greece", "GR"),
        ("north_sea", "Netherlands", "NL"),
        ("irish_sea", "Ireland", "IE"),
        ("east_atlantic", "Portugal", "PT"),
        ("black_sea", "Romania", "RO"),
        ("atlantic", "United States", "US"),
        ("pacific", "Japan", "JP"),
        ("indian", "India", "IN"),
        ("caribbean", "Cuba", "CU"),
        ("caribbean", "France (overseas)", "FR"),
        ("caribbean", "Netherlands (overseas)", "NL"),
        ("arctic", "Norway", "NO"),
        ("arctic", "Denmark (Greenland)", "DK"),
    ]
    for sea, name, expected_code in spot_checks:
        data = seas[sea]
        assert name in data["countries"], (
            f"{sea}: expected name {name!r} not found "
            f"(check the suffix? — see spec §3)"
        )
        i = data["countries"].index(name)
        actual_code = data["country_codes"][i]
        assert actual_code == expected_code, (
            f"{sea}: countries[{i}]={name!r} but "
            f"country_codes[{i}]={actual_code!r} (expected {expected_code!r})"
        )


# Test 11
def test_sp1_wizard_module_imports_real_kb():
    """Smoke check: the SP1 wizard module's REGIONAL_SEAS_PLACEHOLDER
    alias still works after Task 3's swap, AND it now exposes the new
    SP2-only `country_codes` field. Without the country_codes asserts,
    this test would pass against SP1's pre-merge state and miss a
    regression where the loader returned the old shape."""
    from sespy.wizard import REGIONAL_SEAS_PLACEHOLDER

    assert len(REGIONAL_SEAS_PLACEHOLDER) == 11
    assert "baltic" in REGIONAL_SEAS_PLACEHOLDER
    # macaronesia was an SP1-only fictional addition; SP2 drops it.
    assert "macaronesia" not in REGIONAL_SEAS_PLACEHOLDER

    baltic = REGIONAL_SEAS_PLACEHOLDER["baltic"]
    assert baltic["name"] == "Baltic Sea"
    assert "Sweden" in baltic["countries"]
    # New SP2 field — also visible through the alias:
    assert "country_codes" in baltic
    assert "SE" in baltic["country_codes"]


# Test 12
def test_eu_member_codes_count():
    """Pin the count at 22 (post-Brexit, only EU members bordering the
    11 KB seas; 5 landlocked EU states correctly absent — see spec §7
    Test 12 note). If EU membership changes AND the new member borders
    a KB sea, update both regional_seas.json and this assertion in the
    same commit."""
    assert len(get_eu_member_codes()) == 22
```

- [ ] **Step 2: Run tests to verify they ALL fail with the same import error**

```bash
micromamba run -n shiny python -m pytest tests/test_regional_seas.py -v
```
Expected: 12 errors with `ModuleNotFoundError: No module named 'sespy.regional_seas'`. CONFIRM the module-not-found shape — anything else means a typo in the test file.

- [ ] **Step 3: Create `sespy/regional_seas.py` with this exact content**

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

- [ ] **Step 4: Run tests to verify the 11 KB-only ones pass; Test 11 still fails**

```bash
micromamba run -n shiny python -m pytest tests/test_regional_seas.py -v
```
Expected: 11 passed, 1 failed (`test_sp1_wizard_module_imports_real_kb`). The failing test is expected — it asserts the SP1 wizard alias has the new shape, which won't be true until Task 3 swaps the inline literal for the loader call. Capture this state mentally; Task 2's commit ships with this one known-failing test.

If any of the OTHER 11 tests fail, debug:
- Tests 4/5/9/10 failures usually indicate a JSON authoring error from Task 1. Re-run the Task 1 Step 3 invariant script to localize.
- Test 8 returning a non-set means the loader has a typo — the Step 3 code is correct verbatim.
- Test 12 failing on count means `eu_member_codes` in the JSON is the wrong length.

- [ ] **Step 5: Commit**

```bash
git add sespy/regional_seas.py tests/test_regional_seas.py
git commit -m "feat(regional_seas): Python loader module + 12 unit tests"
```

The commit ships with `test_sp1_wizard_module_imports_real_kb` failing; Task 3 makes it pass.

---

## Task 3: Modify `sespy/wizard.py` to use the loader

**Files:**
- Modify: `sespy/wizard.py:70-119` (replace the inline literal with a loader call) AND add the import at the top of the file.

This is the smallest task. The replacement block at the section site is ~14 lines (comment + assignment, no inline import); a separate single-line import is added near the top of the file alongside the existing imports. Two Edit operations, one task.

- [ ] **Step 1: Open `sespy/wizard.py` and locate the block to replace**

```bash
sed -n '68,121p' sespy/wizard.py
```
Expected: lines 68-69 are blank/comment context; lines 70-86 are the SP1 placeholder docstring-comment; lines 88-119 are the inline `REGIONAL_SEAS_PLACEHOLDER` dict; lines 120+ are the next constant (likely a blank line then the next section). If the line range differs from what Task 0 Step 7 confirmed, adjust the edit accordingly — but the spec was authored against `dfedd28` which has lines 70-119 as the canonical range.

- [ ] **Step 2: Replace lines 70-119 with the loader-based block**

The exact `old_string` to match (50 lines, lines 70-119 inclusive — copy verbatim from your working tree):

```python
# ---------------------------------------------------------------------------
# Regional-seas placeholder (SP1 mock; SP2 ports the real KB).
#
# Shape:
#   {
#     "<slug>": {
#       "name": "<display name>",
#       "ecosystem_types": [...],
#       "countries": [...],
#       "common_issues": [...],
#     },
#     ...
#   }
#
# SP2 must produce data with this same shape to satisfy SP1's renderer.
# Shape is the SP1→SP2 contract (see spec §9).
# ---------------------------------------------------------------------------

REGIONAL_SEAS_PLACEHOLDER: dict[str, dict[str, Any]] = {
    "baltic": {
        "name": "Baltic Sea",
        "ecosystem_types": ["Open coast", "Archipelago", "Estuary", "Coastal lagoon", "Offshore waters"],
        "countries": ["Denmark", "Estonia", "Finland", "Germany", "Latvia", "Lithuania", "Poland", "Russia", "Sweden"],
        "common_issues": ["Eutrophication", "Overfishing", "Pollution", "Invasive species", "Climate change"],
    },
    "mediterranean": {
        "name": "Mediterranean Sea",
        "ecosystem_types": ["Open coast", "Island", "Coastal lagoon", "Rocky shore", "Sandy beach", "Seagrass meadow"],
        "countries": ["Italy", "Spain", "France", "Greece", "Croatia", "Tunisia", "Egypt"],
        "common_issues": ["Overfishing", "Coastal development", "Tourism pressure", "Marine litter", "Invasive species"],
    },
    "north_sea": {
        "name": "North Sea",
        "ecosystem_types": ["Open coast", "Estuary", "Tidal flat", "Offshore waters", "Sandy beach"],
        "countries": ["United Kingdom", "Norway", "Denmark", "Germany", "Netherlands", "Belgium", "France"],
        "common_issues": ["Overfishing", "Oil and gas extraction", "Shipping", "Wind energy development", "Eutrophication"],
    },
    "irish_sea": {
        "name": "Irish Sea",
        "ecosystem_types": ["Open coast", "Estuary", "Coastal lagoon", "Rocky shore", "Sandy beach"],
        "countries": ["Ireland", "United Kingdom"],
        "common_issues": ["Overfishing", "Coastal development", "Shipping", "Marine litter", "Eutrophication"],
    },
    "macaronesia": {
        "name": "Macaronesia",
        "ecosystem_types": ["Open coast", "Volcanic island", "Rocky shore", "Offshore waters"],
        "countries": ["Portugal", "Spain"],
        "common_issues": ["Tourism pressure", "Overfishing", "Coastal development", "Climate change"],
    },
}
```

The `new_string` to substitute (comment block + assignment ONLY — no inline import; the import is added in Step 3 at the top of the file):

```python
# ---------------------------------------------------------------------------
# Regional-seas knowledge base — sourced from sespy/regional_seas.json
# (loaded once at module import via sespy/regional_seas.py).
#
# REGIONAL_SEAS_PLACEHOLDER kept for backwards-compatibility with
# sespy/modules/ai_isa_wizard.py imports. The "PLACEHOLDER" suffix is
# now a misnomer — SP2 (2026-05-02) replaced the inline 5-sea mock
# with the real 11-sea KB. The constant name stays so the SP1 wizard
# module's import doesn't break. SP3 is the natural rename moment;
# it'll be touching ai_isa_wizard.py imports anyway.
# ---------------------------------------------------------------------------

REGIONAL_SEAS_PLACEHOLDER: dict[str, dict[str, Any]] = get_regional_seas()
```

Use the `Edit` tool with that exact `old_string` (50 lines) and `new_string` (14 lines). Don't disturb adjacent sections — the line above the old block is blank; the line below the old block is blank; the next section header is `# suggest_connections — SP1 stub.` Both the `old_string` and `new_string` shown here are bordered by blank lines that already exist in the file — match them.

After this edit, the file references `get_regional_seas()` without an import — Step 3 below adds the import. **Don't run pytest between Step 2 and Step 3** — the file will be in a temporarily broken state (NameError on `get_regional_seas`).

- [ ] **Step 3: Add the import at the top of the file (PEP 8)**

`sespy/wizard.py` currently has all its imports in a conventional PEP-8 block at the top of the file. Locate the existing `from .data_structure import WizardState, ConnectionSuggestion` line (around line 23) and add the new loader import immediately after it (alphabetical: `data_structure` before `regional_seas`).

Use the `Edit` tool with:
- `old_string`: `from .data_structure import WizardState, ConnectionSuggestion`
- `new_string`:
  ```
  from .data_structure import WizardState, ConnectionSuggestion
  from .regional_seas import get_regional_seas
  ```

Verify:
```bash
sed -n '1,25p' sespy/wizard.py
```
Expected: the top imports now include `from .regional_seas import get_regional_seas` immediately after `from .data_structure import ...`. The replacement block at lines ~70+ contains only the comment + `REGIONAL_SEAS_PLACEHOLDER` assignment — no inline import.

- [ ] **Step 4: Run all SP2 tests to verify they pass (including the previously-red Test 11)**

```bash
micromamba run -n shiny python -m pytest tests/test_regional_seas.py -v
```
Expected: `12 passed`.

- [ ] **Step 5: Run the SP1 wizard unit tests to verify no regression**

```bash
micromamba run -n shiny python -m pytest tests/test_wizard.py -v
```
Expected: 7 passed (the SP1 baseline). The existing `test_regional_seas_placeholder_has_at_least_baltic` (lines 53-59) is a pure shape check on Baltic — it asserts `"baltic" in placeholder` and that baltic has `name`/`ecosystem_types`/`countries`/`common_issues`. After SP2 the baltic entry has all four fields (plus the new `country_codes`), so the test still passes. **The spec §2 mentions this file as "modified — comment update only" but inspection of the actual file shows no stale comment to update — the test has no docstring or surrounding prose that references the SP1 mock by name. No edit to `tests/test_wizard.py` is required.** Test 11 in the new `tests/test_regional_seas.py` is the SP2-specific assertion that the alias exposes the `country_codes` field.

- [ ] **Step 6: Run the full unit suite to confirm 134 total**

```bash
micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py tests/test_report.py tests/test_templates.py tests/test_network.py tests/test_data_structure.py tests/test_utils.py tests/test_wizard.py tests/test_regional_seas.py
```
Expected: `134 passed` (122 SP1 baseline + 12 new). Task 0 Step 5 already gated on the 122 baseline — if you reached this step, 134 is the only correct outcome.

- [ ] **Step 7: Verify `import app` is clean**

```bash
micromamba run -n shiny python -c "import app; print('ok')"
```
Expected: `ok`. This catches any circular-import or import-time-error introduced by the new `sespy.regional_seas` module load.

- [ ] **Step 8: Commit**

```bash
git add sespy/wizard.py
git commit -m "refactor(wizard): swap REGIONAL_SEAS_PLACEHOLDER inline to loader call"
```

---

## Task 4: SP1 e2e + browser smoke test (verification)

**Files:** none modified (verification only — commit only on a fix).

The SP1 e2e suite uses `'baltic'`, `'Open coast'`, `'Lithuania'`, `'Eutrophication'` — all preserved in SP2's KB. All 6 cases should pass unchanged. The browser smoke test additionally confirms 11 sea radios appear at step 0 (was 5 in SP1) and that the country list per sea is sea-specific.

- [ ] **Step 1: Boot the app on port 8000 in the background**

```bash
micromamba run -n shiny shiny run --port 8000 app.py
```
Run with `run_in_background=True`. Then wait for it to be ready:

```bash
micromamba run -n shiny python .tmp/wait_port.py
```
Expected: `ready after Xs` for some X under 30. If it times out, check the background output for an import error.

- [ ] **Step 2: Run the SP1 e2e suite**

```bash
micromamba run -n shiny python tests/test_wizard_e2e.py
```
Expected output ends with:
```
wizard e2e: 6 cases passed
```

If any case fails, the regression is in SP2's data swap, not in SP1's renderer (which is unchanged). Most likely causes:
- Test 4 (`case_mid_nav_resume`) or Test 6 (`case_validation_failure`) reach step 4 (drivers, freeform_multiple) — if those fail, check that step 0/1/2/3 transitions still work (any `t()` lookup that used a missing slug would break). Re-read the e2e test to see which step the assertion is at, then run the step manually in the browser to see what's wrong.
- Test 3 (`case_modal_replace`) asserts the Edit Data table is empty after Replace — unrelated to SP2; would only break if the Replace flow itself was broken (it isn't — SP2 doesn't touch handlers).

- [ ] **Step 3: Quick browser smoke check — 11 seas visible at step 0**

In a separate terminal (the background app is still running), run:

```bash
micromamba run -n shiny python -c "
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.goto('http://127.0.0.1:8000', wait_until='networkidle')
        await page.wait_for_selector('#sespy_nav_wizard', timeout=15000)
        await page.click('#sespy_nav_wizard')
        await page.wait_for_timeout(1500)
        await page.click('#wizard-wizard_start')
        await page.wait_for_timeout(800)
        # SESPy boots with data/sample_ses.json loaded (a non-empty SES),
        # so Start opens the confirmation modal. Branch on whether the
        # Replace button exists — if the project happened to be empty
        # (rare; would only happen if the boot was customized), the
        # Start click would have advanced directly to step 0.
        replace_present = await page.evaluate(
            \"() => document.getElementById('wizard-wizard_replace') !== null\"
        )
        if replace_present:
            await page.click('#wizard-wizard_replace')
            await page.wait_for_timeout(1500)
        # Step 0: count regional_sea radio buttons
        radio_count = await page.evaluate(
            \"() => document.querySelectorAll('#wizard-answer_regional_sea input[type=radio]').length\"
        )
        print(f'regional_sea radios (incl. \"—\" sentinel): {radio_count}')
        assert radio_count == 12, f'expected 12 radios (11 seas + sentinel), got {radio_count}'
        # Pick Baltic, advance to step 1
        await page.evaluate(\"() => Shiny.setInputValue('wizard-answer_regional_sea', 'baltic', {priority: 'event'})\")
        await page.wait_for_timeout(300)
        await page.click('#wizard-wizard_next')
        await page.wait_for_timeout(800)
        # Step 1: count ecosystem_type radios for Baltic
        eco_count = await page.evaluate(
            \"() => document.querySelectorAll('#wizard-answer_ecosystem_type input[type=radio]').length\"
        )
        print(f'baltic ecosystem_types radios (incl. sentinel): {eco_count}')
        assert eco_count == 8, f'expected 8 (7 baltic + sentinel), got {eco_count}'
        # Pick Open coast (a baltic ecosystem type), advance to step 2
        await page.evaluate(\"() => Shiny.setInputValue('wizard-answer_ecosystem_type', 'Open coast', {priority: 'event'})\")
        await page.wait_for_timeout(300)
        await page.click('#wizard-wizard_next')
        await page.wait_for_timeout(800)
        # Step 2: countries — verify Baltic-specific list (9 entries per spec).
        # Selectize strips <option> children from the underlying <select>
        # and renders choices in its own overlay — the underlying select
        # is empty (display: none). To probe the actual choices, click
        # the `-selectized` input to open the dropdown, then query
        # `.selectize-dropdown-content [data-value]`. Querying the raw
        # <option> elements returns 0; this is NOT a regression in the
        # data, just a DOM-shape quirk of the selectize library.
        await page.click('#wizard-answer_countries-selectized')
        await page.wait_for_timeout(500)
        country_choices = await page.evaluate(
            \"() => Array.from(document.querySelectorAll('.selectize-dropdown-content [data-value]')).map(o => o.textContent.trim())\"
        )
        print(f'baltic country choices: {len(country_choices)} ({country_choices[:3]}...)')
        assert len(country_choices) >= 9, f'expected ≥9 baltic countries, got {len(country_choices)}: {country_choices}'
        assert 'Sweden' in country_choices and 'Lithuania' in country_choices, (
            f'baltic countries missing expected entries: {country_choices}'
        )
        await browser.close()
        print('ok')

asyncio.run(main())
"
```
Expected:
```
regional_sea radios (incl. "—" sentinel): 12
baltic ecosystem_types radios (incl. sentinel): 8
baltic country choices: 9 (['Sweden', 'Finland', 'Denmark']...)
ok
```

The 12-radio count is the visible signal of SP2: SP1 had 6 (5 seas + sentinel); SP2 has 12 (11 seas + sentinel). The 8-eco-radio count for Baltic is the data-correctness signal: R has 7 ecosystem types for baltic (`Open coast, Rocky coast (Schären), Archipelago, Island, Estuary, Coastal lagoon, Offshore waters`), plus the `—` sentinel = 8. The 9-country count covers spec §11 DoD's "step 2 country list is sea-specific" — Baltic has 9 countries in R; if the user picked another sea (e.g., irish_sea has 2), the count would differ.

- [ ] **Step 4: Stop the background app**

Stop the background shiny process. (Use `TaskStop` if you launched via the background-task tool, or `kill` the PID otherwise.) Verify nothing is left on port 8000:

```bash
netstat -ano | grep ':8000' | head -3
```
Expected: empty (no `LISTENING` entries on 127.0.0.1:8000). If a process is still bound, kill it before Task 5.

No commit. If this task surfaced a fix, commit the fix with `fix(...)` and the specific issue — but the spec promises zero behavioral drift, so a fix here would be unexpected.

---

## Task 5: README update + final verification

**Files:**
- Modify: `README.md` lines 73 and 139 (both `122 unit tests` mentions become `134 unit tests`)

The module count stays at 16 — SP2 doesn't add a registered nav module; `sespy/regional_seas.py` is a support file, not a module-with-its-own-page. Only the test count changes.

- [ ] **Step 1: Confirm both README occurrences of `122 unit tests`**

```bash
grep -n "122 unit\|21 e2e\|21 end-to-end" README.md
```
Expected: 3 lines printed:
- Line 73: `122 unit tests + 21 e2e scripts. ...`
- Line 139: `**122 unit tests** across:`
- Line 153: `**21 end-to-end test scripts** in ...`

The 21 e2e count stays unchanged (SP2 adds zero e2e files).

- [ ] **Step 2: Edit `README.md` line 73**

Change:
```
122 unit tests + 21 e2e scripts. ...
```
to:
```
134 unit tests + 21 e2e scripts. ...
```
(rest of the line unchanged.)

- [ ] **Step 3: Edit `README.md` line 139**

Change:
```
**122 unit tests** across:
```
to:
```
**134 unit tests** across:
```

- [ ] **Step 4: Verify the README change is exactly the two intended edits**

```bash
git diff README.md
```
Expected: 2 hunks, each replacing the 3-digit number `122` with `134` (positions 2 and 3 differ). No other edits. If you see additional changes, revert and try again.

- [ ] **Step 5: Verify `import app` is still clean**

```bash
micromamba run -n shiny python -c "import app; print('ok')"
```
Expected: `ok`.

- [ ] **Step 6: Run the full unit suite one more time for final confirmation**

```bash
micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py tests/test_report.py tests/test_templates.py tests/test_network.py tests/test_data_structure.py tests/test_utils.py tests/test_wizard.py tests/test_regional_seas.py 2>&1 | tail -3
```
Expected: `134 passed` in the final line.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs(readme): bump unit test count to 134 after SP2 KB swap"
```

- [ ] **Step 8: Print the final branch summary**

```bash
git log --oneline main..feat/ai-isa-wizard-sp2
```
Expected: 4 commits in this order (newest first):
- `docs(readme): bump unit test count to 134 after SP2 KB swap`
- `refactor(wizard): swap REGIONAL_SEAS_PLACEHOLDER inline to loader call`
- `feat(regional_seas): Python loader module + 12 unit tests`
- `feat(regional_seas): knowledge base data file (11 seas, 22 EU codes)`

If a Task 4 fix was needed, expect a 5th commit between the loader and the wizard-refactor commits. Otherwise, 4 commits total.

---

## Definition of done

- `sespy/regional_seas.json` exists and parses; `sespy/regional_seas.py` loads it on import.
- `get_regional_seas()` returns 11 seas with the SP1 contract shape + `country_codes` field.
- `get_eu_member_codes()` returns a set of 22 ISO-2 codes.
- `tests/test_regional_seas.py`: all 12 tests pass.
- `sespy/wizard.py` imports from the loader; `REGIONAL_SEAS_PLACEHOLDER` works as before for SP1's renderer.
- All existing SP1 unit tests pass (122 → unchanged behavior; full suite now 134).
- All 6 SP1 e2e cases pass unchanged.
- Browser smoke shows 11 sea radios at step 0 (was 5 in SP1), Baltic shows 7 ecosystem types at step 1 (was 5), and the step 2 country list is sea-specific (Baltic shows 9 countries including Sweden and Lithuania).
- `README.md` reflects 134 unit tests at both occurrences (lines 73 and 139); 21 e2e count unchanged.
- Branch ready for fast-forward merge to main.
