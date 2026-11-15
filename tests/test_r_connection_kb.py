"""K1b Task 4: KB lookup, synonym match and enhanced relevance vs R v1.35.6."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent / "parity"))

from k1b_fixtures import load_k1b_fixture  # noqa: E402

from sespy import r_connection_kb as kb  # noqa: E402
from sespy.r_connection_kb import calculate_enhanced_relevance, lookup_knowledge_base  # noqa: E402
from sespy.r_kb import VENDORED  # noqa: E402

DB = VENDORED.connection_db()
ROWS = load_k1b_fixture("lookup")["rows"]
IDS = [f"{i}-{r['from_name']}>{r['to_name']}" for i, r in enumerate(ROWS)]


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_lookup_matches_r(row):
    got = lookup_knowledge_base(row["from_name"], row["from_type"],
                                row["to_name"], row["to_type"], DB)
    want = row["match"]
    assert (got is None) == (want is None)
    if want:
        assert (got.polarity, got.strength, got.match_quality) == \
               (want["polarity"], want["strength"], want["match_quality"])
        assert got.probability == pytest.approx(want["probability"], abs=1e-12)


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_relevance_matches_r(row):
    assert calculate_enhanced_relevance(row["from_name"], row["to_name"],
        row["from_type"], row["to_type"], DB) == pytest.approx(row["relevance"], abs=1e-12)


def test_fixture_covers_all_match_kinds():
    kinds = {(r["match"] or {}).get("match_quality") for r in ROWS}
    assert kinds == {None, "exact", "synonym"}


def test_synonym_hit_beats_weak_exact_hit():
    m = lookup_knowledge_base("Fish farming", "activities", "Chemical pollution", "pressures", DB)
    assert m is not None and (m.match_quality, m.strength, m.polarity) == ("synonym", "strong", "+")
    assert calculate_enhanced_relevance("Fish farming", "Chemical pollution",
        "activities", "pressures", DB) == pytest.approx(0.7533, abs=5e-5)


def test_idf_weights():
    assert kb._keyword_idf_weight("trawl") == 2.0
    assert kb._keyword_idf_weight("anti-foul") == 2.0
    assert kb._keyword_idf_weight("ecosystem") == 0.6
    assert kb._keyword_idf_weight("fish") == 1.0
