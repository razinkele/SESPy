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
    """Smoke check: the SP1 wizard module's REGIONAL_SEAS alias works
    after the SP2 KB swap, AND it now exposes the SP2 `country_codes`
    field. Without the country_codes asserts, this test would pass
    against SP1's pre-merge state and miss a regression where the
    loader returned the old shape. (The alias was previously named
    `REGIONAL_SEAS_PLACEHOLDER`; renamed post-SP2 to drop the
    misnomer.)"""
    from sespy.wizard import REGIONAL_SEAS

    assert len(REGIONAL_SEAS) == 11
    assert "baltic" in REGIONAL_SEAS
    # macaronesia was an SP1-only fictional addition; SP2 drops it.
    assert "macaronesia" not in REGIONAL_SEAS

    baltic = REGIONAL_SEAS["baltic"]
    assert baltic["name"] == "Baltic Sea"
    assert "Sweden" in baltic["countries"]
    # SP2 country_codes field — also visible through the alias:
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
