"""K1b Task 3: shape and coverage of the three R-captured scorer fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from k1b_fixtures import load_k1b_fixture  # noqa: E402

CATS = ["drivers", "activities", "pressures", "states", "impacts", "welfare", "responses"]
PAIRS = {("drivers", "activities"), ("activities", "pressures"), ("pressures", "states"),
         ("states", "impacts"), ("impacts", "welfare"), ("responses", "pressures"),
         ("welfare", "drivers"), ("welfare", "responses"), ("responses", "drivers"),
         ("responses", "activities")}
ROW_KEYS = ["from_type", "from_index", "from_name", "to_type", "to_index", "to_name",
            "polarity", "strength", "confidence", "scoring_method", "rationale", "relevance"]


def test_connections_cases():
    fx = load_k1b_fixture("connections")
    assert fx["r_tag"] == "v1.35.6"
    ids = [c["id"] for c in fx["cases"]]
    assert len(ids) == 10 and len(set(ids)) == 10      # 7 templates + 3 wizard cases
    worked = next(c for c in fx["cases"] if c["id"] == "wizard_worked_example")
    assert len(worked["rows"]) == 16                   # R notes section 1 worked example


def test_connections_row_shape():
    fx = load_k1b_fixture("connections")
    for case in fx["cases"]:
        assert list(case["elements"]) == CATS
        for r in case["rows"]:
            assert list(r) == ROW_KEYS
            assert (r["from_type"], r["to_type"]) in PAIRS
            assert r["polarity"] in ("+", "-") and r["strength"] in ("weak", "medium", "strong")
            assert r["confidence"] in (3, 4) and r["scoring_method"] in ("kb", "keyword")
            assert isinstance(r["relevance"], float) and 0.3 <= r["relevance"] <= 1.0
            # indices are R's 1-based positions in the element lists
            assert case["elements"][r["from_type"]][r["from_index"] - 1] == r["from_name"]
            assert case["elements"][r["to_type"]][r["to_index"] - 1] == r["to_name"]


def test_connections_cap_and_order():
    fx = load_k1b_fixture("connections")
    for case in fx["cases"]:
        per_pair: dict[tuple[str, str], list[float]] = {}
        pair_order = []
        for r in case["rows"]:
            key = (r["from_type"], r["to_type"])
            if key not in per_pair:
                pair_order.append(key)
            per_pair.setdefault(key, []).append(r["relevance"])
        assert pair_order == [p for p in [
            ("drivers", "activities"), ("activities", "pressures"), ("pressures", "states"),
            ("states", "impacts"), ("impacts", "welfare"), ("responses", "pressures"),
            ("welfare", "drivers"), ("welfare", "responses"), ("responses", "drivers"),
            ("responses", "activities")] if p in per_pair]
        for rel in per_pair.values():
            assert len(rel) <= 15 and rel == sorted(rel, reverse=True)
    stress = next(c for c in fx["cases"] if c["id"] == "wizard_stress")
    assert sum(r["from_type"] == "activities" for r in stress["rows"]) == 15


def test_lookup_covers_all_match_kinds():
    q = {r["match"]["match_quality"] if r["match"] else None
         for r in load_k1b_fixture("lookup")["rows"]}
    assert q == {"exact", "synonym", None}


def test_lookup_rows():
    rows = load_k1b_fixture("lookup")["rows"]
    assert len(rows) >= 200
    for r in rows:
        assert list(r) == ["from_name", "from_type", "to_name", "to_type", "match", "relevance"]
        assert (r["from_type"], r["to_type"]) in PAIRS
        assert isinstance(r["relevance"], float) and 0.2 <= r["relevance"] <= 1.0
        if r["match"]:
            assert list(r["match"]) == ["polarity", "strength", "match_quality", "probability"]


def test_polarity_rows():
    rows = load_k1b_fixture("polarity")["rows"]
    assert len(rows) >= 150
    assert {(r["from_type"], r["to_type"]) for r in rows} == PAIRS
    for r in rows:
        assert list(r) == ["from_name", "to_name", "from_type", "to_type", "polarity"]
        assert r["polarity"] in ("+", "-")


def test_worked_example_first_and_last_rows():
    worked = next(c for c in load_k1b_fixture("connections")["cases"]
                  if c["id"] == "wizard_worked_example")
    first, last = worked["rows"][0], worked["rows"][-1]
    assert (first["from_name"], first["to_name"], first["polarity"], first["strength"],
            first["confidence"], first["scoring_method"]) == (
        "Food security", "Commercial fishing", "+", "strong", 4, "kb")
    assert last["rationale"] == "Fishing quotas restricts Commercial fishing"
