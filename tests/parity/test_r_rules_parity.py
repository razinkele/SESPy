"""P1a — content parity of DAPSIWRM_ADJACENCY_RULES with R's
functions/dapsiwrm_connection_rules.R (v1.29.0 fixture copy, unchanged at v1.31.0).

A hash pin alone would let a hand-copy error pass, so this parses the R
table's `targets`, `extension_targets` and `target_polarities` vectors with
regexes and compares them with the Python table. Rule ids are not in R;
they stay pinned by tests/test_link_rules.py against the spec.
"""
from __future__ import annotations

import re
from pathlib import Path

from sespy.constants import DAPSIWRM_ADJACENCY_RULES

ROOT = Path(__file__).resolve().parents[2]
R_RULES = ROOT / "tests" / "parity" / "r_rules" / "dapsiwrm_connection_rules.R"

# One source block: `  Drivers = list(` or `  "Goods & Benefits" = list(`
# at two-space indent, inside `DAPSIWRM_ADJACENCY_RULES <- list(`.
_BLOCK = re.compile(r'^  (?:"([^"]+)"|(\w+)) = list\($', re.M)


def _vector(body: str, key: str) -> list[str]:
    m = re.search(rf"^\s*{key} = (c\((.*?)\)|character\(0\))", body, re.M | re.S)
    assert m, f"{key} not found"
    return re.findall(r'"([^"]+)"', m.group(2) or "")


def parse_r_rules(text: str) -> dict[str, tuple[dict[str, str], dict[str, str]]]:
    start = text.index("DAPSIWRM_ADJACENCY_RULES <- list(")
    end = text.index("\nget_allowed_targets <- function", start)
    table = text[start:end]
    heads = list(_BLOCK.finditer(table))
    out = {}
    for i, h in enumerate(heads):
        body = table[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(table)]
        # target_polarities may span two lines (the Responses block).
        pol_src = re.search(r"target_polarities = c\((.*?)\),\s*\n", body, re.S).group(1)
        pol = dict(re.findall(r'"([^"]+)"\s*=\s*"([+-])"', pol_src))
        targets = _vector(body, "targets")
        ext = _vector(body, "extension_targets")
        out[h.group(1) or h.group(2)] = ({t: pol[t] for t in targets},
                                         {t: pol[t] for t in ext})
    return out


def _python_table():
    return {src: ({t.to_type: t.polarity for t in r.targets},
                  {t.to_type: t.polarity for t in r.extension_targets})
            for src, r in DAPSIWRM_ADJACENCY_RULES.items()}


def test_parser_sees_all_seven_sources_and_the_two_line_responses_block():
    parsed = parse_r_rules(R_RULES.read_text(encoding="utf-8"))
    assert len(parsed) == 7
    assert parsed["Responses"][0]["Marine Processes & Functioning"] == "+"
    assert parsed["Responses"][1] == {"Responses": "+"}
    assert parsed["Ecosystem Services"][1] == {}


def test_rule_table_matches_r():
    assert _python_table() == parse_r_rules(R_RULES.read_text(encoding="utf-8"))
