"""K1 Task 7: Regional Context content, an exact port of R's report helpers.

Parity cases compare with the markdown R v1.35.6 itself produced
(``tests/parity/r_fixtures/k1/report``); the rest are literal R behaviours
(substring matching, pipe escaping) checked on small hand-built knowledge bases.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent / "parity"))

from k1_fixtures import load_k1_fixture  # noqa: E402

from sespy import kb_report as kr  # noqa: E402
from sespy.r_kb import VENDORED  # noqa: E402

KB = VENDORED.kb()
GOV = VENDORED.governance()
REPORT = load_k1_fixture("report")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _fake_kb(connections, description="A test site."):
    return {
        "contexts": {
            "baltic_lagoon": {
                "description": description,
                "drivers": [{"name": "Fishing demand", "relevance": 0.9}],
                "connections": connections,
            }
        }
    }


def _build(kb, edges, gov=None):
    return kr.build_regional_context(kb, gov, "baltic", "Coastal lagoon", edges)


@pytest.mark.parametrize("case", ["baltic_lagoon", "med_seagrass", "irish_sea"])
def test_report_markdown_matches_r(case):
    c = REPORT[case]
    rc = kr.build_regional_context(KB, GOV, c["sea"], c["ecosystem"],
                                   [tuple(e) for e in c["edges"]])
    assert rc is not None
    md = kr.to_markdown(rc)
    assert md.startswith("# Regional Context")
    assert _norm(md) == _norm(c["markdown"])
    assert md == c["markdown"]


def test_baltic_matches_two_edges_and_skips_the_rest():
    c = REPORT["baltic_lagoon"]
    rc = kr.build_regional_context(KB, GOV, c["sea"], c["ecosystem"],
                                   [tuple(e) for e in c["edges"]])
    assert len(rc.evidence) >= 2
    assert all(isinstance(r, kr.EvidenceRow) for r in rc.evidence)


def test_irish_sea_governance_only():
    c = REPORT["irish_sea"]
    rc = kr.build_regional_context(KB, GOV, c["sea"], c["ecosystem"], [])
    assert rc.site_description is None
    assert rc.top_elements == []
    assert rc.evidence == []
    assert rc.frameworks
    assert rc.country_groups


def test_empty_label_matches_all():
    kb = _fake_kb([{"from": "Fishing pressure", "to": "Cod stock", "rationale": "r1",
                    "references": ["R1"], "temporal_lag": "years", "reversibility": "partial"}])
    rc = _build(kb, [("", "Cod stock decline")])
    assert [r.connection for r in rc.evidence] == [" → Cod stock decline"]
    # the empty label is on the from side: R's grepl("", x, fixed = TRUE) is TRUE
    rc = _build(kb, [("Fishing pressure on cod", "")])
    assert len(rc.evidence) == 1


def test_first_match_wins_and_short_kb_names_skipped():
    kb = _fake_kb([
        {"from": "ab", "to": "Cod stock", "rationale": "short, skipped"},
        {"from": "Fishing", "to": "Cod", "rationale": "first", "references": ["A", "B"]},
        {"from": "Fishing", "to": "Cod", "rationale": "second"},
    ])
    rc = _build(kb, [("fishing effort", "cod")])
    assert [r.rationale for r in rc.evidence] == ["first"]
    assert rc.evidence[0].references == "A; B"
    assert rc.evidence[0].temporal_lag == ""


def test_pipe_and_newline_in_rationale_escaped():
    kb = _fake_kb([{"from": "Fishing", "to": "Cod", "rationale": "a|b\nc",
                    "references": ["R|1", "R\n2"], "temporal_lag": "x\ny",
                    "reversibility": "z"}])
    rc = _build(kb, [("Fishing\nfleet", "Cod")])
    md = kr.to_markdown(rc)
    rows = [ln for ln in md.split("\n") if ln.startswith("| ") and "Fishing" in ln]
    assert len(rows) == 1
    row = rows[0]
    assert "a\\|b" in row and "R\\|1" in row
    assert len(re.findall(r"(?<!\\)\|", row)) == 6  # 5 cells -> 6 unescaped pipes
    # no stray table fragments left on their own lines
    assert all("c |" not in ln for ln in md.split("\n") if not ln.startswith("| Fishing"))
    # the structured rows keep the raw text
    assert rc.evidence[0].rationale == "a|b\nc"


def test_no_content_returns_none():
    assert kr.build_regional_context(KB, GOV, "other", "Coastal lagoon", []) is None
    assert kr.build_regional_context(KB, GOV, "other", "Coastal lagoon",
                                     [("a", "b")]) is None
    assert kr.build_regional_context(None, None, "baltic", "Coastal lagoon", []) is None


def test_does_not_mutate_kb():
    before = copy.deepcopy(KB)
    c = REPORT["baltic_lagoon"]
    kr.build_regional_context(KB, GOV, c["sea"], c["ecosystem"], [tuple(e) for e in c["edges"]])
    assert KB == before


def test_headings_and_labels_are_r_literals():
    assert kr.HEADINGS == (
        "Regional Context",
        "Site Ecological Context",
        "Key DAPSI(W)R(M) Elements from Knowledge Base",
        "Scientific Evidence for Connections",
        "Relevant Governance Frameworks",
        "Country-Specific Governance Groups",
    )
    assert kr.CATEGORY_LABELS["states"] == "States/Components (C)"
    assert kr.CATEGORY_LABELS["welfare"] == "Welfare (HW/GB)"
    assert len(kr.CATEGORY_LABELS) == 7


def test_blank_description_skips_site_heading_but_keeps_elements():
    rc = _build(_fake_kb([], description="   "), [])
    assert rc.site_description is None
    md = kr.to_markdown(rc)
    assert "## Site Ecological Context" not in md
    assert "### Key DAPSI(W)R(M) Elements from Knowledge Base" in md
    assert "- Fishing demand" in md
