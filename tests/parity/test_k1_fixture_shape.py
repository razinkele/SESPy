"""K1 Task 2: shape and coverage of the five R-captured knowledge-base fixtures."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from k1_fixtures import K1_FIXTURE_TAG, load_k1_fixture, load_k1_fixture_raw  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
NAMES = ["lookup", "suggestions_grid", "habitat_specific", "countries", "report"]
CATEGORIES = ["drivers", "activities", "pressures", "states", "impacts", "welfare", "responses"]
ISSUE_SETS = [[], ["Eutrophication", "Overfishing"]]
COVER_SET = ["FR", "RU", "FM", "ZA", "BZ", "DK", "AU"]


def _seas():
    raw = json.loads((ROOT / "sespy" / "regional_seas.json").read_text(encoding="utf-8"))
    return {sea: v["ecosystem_types"] for sea, v in raw["regional_seas"].items()}


def _country_sets(sea: str) -> list[list[str]]:
    codes = [c["code"] for c in load_k1_fixture("countries")[sea]]
    return [[], codes[:2], codes[:2][::-1], COVER_SET]


def test_tag_constant():
    assert K1_FIXTURE_TAG == "v1.35.6"


@pytest.mark.parametrize("name", NAMES)
def test_fixture_loads_and_is_tagged(name):
    assert load_k1_fixture(name)
    raw = load_k1_fixture_raw(name)
    assert raw["r_tag"] == "v1.35.6"
    assert raw["r_commit"] == "d1a655a"


def test_lookup_shape():
    data = load_k1_fixture("lookup")
    assert len(data["choices"]) == 69
    assert len(data["free_text"]) == 3
    for row in data["choices"] + data["free_text"]:
        assert set(row) == {"sea", "ecosystem", "key", "match"}
        assert row["match"] in {"exact", "prefix", "sea_only", "fallback"}
        assert (row["key"] is None) == (row["match"] == "fallback")
    assert {(r["sea"], r["ecosystem"]) for r in data["choices"]} == {
        (s, e) for s, ecos in _seas().items() for e in ecos
    }
    assert [(r["sea"], r["ecosystem"]) for r in data["free_text"]] == [
        ("baltic", "Coastal lagoon and delta"),
        ("mediterranean", "Posidonia meadows"),
        ("baltic", "Schären archipelago"),
    ]


def test_countries_shape():
    data = load_k1_fixture("countries")
    assert set(data) == set(_seas()) and len(data) == 11
    for rows in data.values():
        assert rows
        for r in rows:
            assert set(r) == {"code", "name_en", "eu_member"}
            assert isinstance(r["eu_member"], bool)


def test_grid_covers_every_cell():
    seas = _seas()
    expected = {
        (sea, eco, cat, tuple(iss), tuple(cs))
        for sea, ecos in seas.items()
        for eco in ecos
        for cat in CATEGORIES
        for iss in ISSUE_SETS
        for cs in _country_sets(sea)
    }
    data = load_k1_fixture("suggestions_grid")
    got = [
        (c["sea"], c["ecosystem"], c["category"], tuple(c["issues"]), tuple(c["countries"]))
        for c in data["cells"]
    ]
    assert len(got) == len(set(got)), "duplicate grid cells"
    assert set(got) == expected
    n_ecos = sum(len(e) for e in seas.values())
    assert len(got) == n_ecos * len(CATEGORIES) * len(ISSUE_SETS) * 4 == 3864
    for cell in data["cells"]:
        assert cell["items"] in data["sources"]
    for items in data["sources"].values():
        for pair in items:
            assert len(pair) == 2 and all(isinstance(p, str) for p in pair)


def test_issue_sets_do_not_change_items():
    """R >= v1.35.0 ignores main_issue: both issue sets give identical lists."""
    data = load_k1_fixture("suggestions_grid")
    by_key = defaultdict(set)
    for c in data["cells"]:
        by_key[(c["sea"], c["ecosystem"], c["category"], tuple(c["countries"]))].add(
            (tuple(c["issues"]), c["items"])
        )
    assert by_key
    for key, pairs in by_key.items():
        assert len(pairs) == len(ISSUE_SETS), key
        items = {tuple(map(tuple, data["sources"][i])) for _, i in pairs}
        assert len(items) == 1, f"issues changed the suggestions for {key}"


def test_habitat_specific_shape():
    data = load_k1_fixture("habitat_specific")
    n_ecos = sum(len(e) for e in _seas().values())
    assert len(data) == n_ecos * len(CATEGORIES)
    for row in data:
        assert set(row) == {"sea", "ecosystem", "category", "items"}
        assert isinstance(row["items"], list)


def test_report_shape():
    data = load_k1_fixture("report")
    assert set(data) == {"baltic_lagoon", "med_seagrass", "irish_sea"}
    for case in data.values():
        assert set(case) == {"sea", "ecosystem", "edges", "markdown"}
        assert case["markdown"].startswith("# Regional Context\n\n")
    assert len(data["baltic_lagoon"]["edges"]) == 5
    assert data["baltic_lagoon"]["edges"][4][0] == ""
    assert data["med_seagrass"]["edges"] == []
    assert data["irish_sea"]["edges"] == []
