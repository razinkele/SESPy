"""K1b Task 5: R polarity rules, verb table and relevance-based dedup."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent / "parity"))

from k1b_fixtures import load_k1b_fixture  # noqa: E402

from sespy.connection_scorer import _select_verb, detect_polarity  # noqa: E402
from sespy.data_structure import ConnectionSuggestion  # noqa: E402
from sespy.r_kb import VENDORED  # noqa: E402

DB = VENDORED.connection_db()
ROWS = load_k1b_fixture("polarity")["rows"]
IDS = [f"{i}-{r['from_name']}>{r['to_name']}" for i, r in enumerate(ROWS)]


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_polarity_matches_r(row):
    assert detect_polarity(row["from_name"], row["to_name"], row["from_type"],
                           row["to_type"], DB) == row["polarity"]


def test_verbs_match_r_table():
    want = {("drivers", "+"): "drives", ("drivers", "-"): "drives",
            ("activities", "+"): "increases", ("activities", "-"): "causes",
            ("pressures", "+"): "increases", ("pressures", "-"): "decreases",
            ("states", "+"): "impacts", ("states", "-"): "impacts",
            ("impacts", "+"): "increases", ("impacts", "-"): "reduces",
            ("responses", "+"): "enables", ("responses", "-"): "restricts",
            ("welfare", "+"): "motivates", ("welfare", "-"): "reduces"}
    assert {k: _select_verb(*k) for k in want} == want


def test_suggestion_defaults():
    s = ConnectionSuggestion("a", "b", "+", 0.5, "r")
    assert (s.relevance, s.strength, s.confidence) == (0.5, "medium", 3)
