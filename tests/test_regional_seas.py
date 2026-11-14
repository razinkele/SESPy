"""Unit tests for sespy.regional_seas — knowledge base loader.

Validates schema, invariants, and SP1 wizard module integration. The
tests are listed in spec §7 of 2026-05-02-ai-isa-wizard-sp2-design.md.

K1 (Task 11): the JSON no longer carries `countries`, `country_codes` or
`eu_member_codes`, and `get_eu_member_codes()` is gone. The wizard's
countries come from R's governance data; their coverage is tested by
`tests/test_kb_suggestions.py::test_countries_for_sea_matches_r` and
`tests/test_wizard_countries.py::test_country_choices_from_governance`.
SP2's tests 4, 5, 8, 9, 10 and 12 (parallel lists, ISO-2 codes, EU
codes, per-sea country spot checks) were deleted with those fields.
"""
from __future__ import annotations

import sespy.regional_seas as regional_seas
from sespy.regional_seas import get_regional_seas

REMOVED_KEYS = {"countries", "country_codes"}


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
    """Schema check + non-empty for the list-typed fields. Each sea has
    name, ecosystem_types and common_issues (K1 removed the country
    fields)."""
    required = {"name", "ecosystem_types", "common_issues"}
    list_fields = ("ecosystem_types", "common_issues")
    for slug, data in get_regional_seas().items():
        assert required.issubset(data.keys()), (
            f"{slug} missing fields: {required - data.keys()}"
        )
        for field in list_fields:
            assert len(data[field]) >= 1, (
                f"{slug}: {field} is empty (≥1 required)"
            )


def test_country_fields_removed():
    """K1: countries live in R's governance data only."""
    for slug, data in get_regional_seas().items():
        assert not REMOVED_KEYS & data.keys(), slug
    assert "eu_member_codes" not in regional_seas._KB
    assert not hasattr(regional_seas, "get_eu_member_codes")


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


# Test 11
def test_sp1_wizard_module_imports_real_kb():
    """Smoke check: the SP1 wizard module's REGIONAL_SEAS alias works
    after the SP2 KB swap. (The alias was previously named
    `REGIONAL_SEAS_PLACEHOLDER`; renamed post-SP2 to drop the
    misnomer.)"""
    from sespy.wizard import REGIONAL_SEAS

    assert len(REGIONAL_SEAS) == 11
    assert "baltic" in REGIONAL_SEAS
    # macaronesia was an SP1-only fictional addition; SP2 drops it.
    assert "macaronesia" not in REGIONAL_SEAS

    baltic = REGIONAL_SEAS["baltic"]
    assert baltic["name"] == "Baltic Sea"
    assert "Eutrophication" in baltic["common_issues"]
    assert not REMOVED_KEYS & baltic.keys()
