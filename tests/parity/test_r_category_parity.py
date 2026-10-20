"""P2 — content parity of the gallery category rule with R (spec §8).

tests/parity/r_source/template_loader.R is R's file at the pin (hash-checked
by test_r_sync.py, rewritten by the sync script). A hash alone would be
silently re-pinned, so this test reads R's `.determine_template_category`
and asserts that its branches, regex table and order equal the Python port
in sespy.r_template_catalogue. A red here means R changed the rule: port the
change, never edit the fixture.
"""
from __future__ import annotations

import re
from pathlib import Path

from sespy import r_template_catalogue as C

ROOT = Path(__file__).resolve().parents[2]
R_SOURCE = ROOT / "tests" / "parity" / "r_source" / "template_loader.R"


def _function_body() -> str:
    # The working copy is CRLF under core.autocrlf=true: normalise first.
    src = R_SOURCE.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.search(r"^\.determine_template_category <- function\(json_data\) \{\n(.*?)\n\}\n",
                  src, re.S | re.M)
    assert m, "R's .determine_template_category not found in template_loader.R"
    return m.group(1)


def test_null_branch():
    m = re.search(r'if \(is\.null\(json_data\$regional_context\$main_issues\)\) return\("([^"]+)"\)',
                  _function_body())
    assert m and m.group(1) == C.CATEGORY_NULL


def test_multi_issue_branch():
    body = _function_body()
    assert "issues <- json_data$regional_context$main_issues" in body
    m = re.search(r'if \(length\(issues\) > 1\) return\("([^"]+)"\)', body)
    assert m and m.group(1) == C.CATEGORY_MULTI


def test_regex_table_and_order():
    rules = re.findall(
        r'if \(any\(grepl\("([^"]+)", issues, ignore\.case = TRUE\)\)\) return\("([^"]+)"\)',
        _function_body())
    assert tuple(rules) == C.CATEGORY_RULES


def test_fallback():
    m = re.search(r'\n\s*"([^"]+)"\s*$', _function_body())
    assert m and m.group(1) == C.CATEGORY_FALLBACK


def test_no_unparsed_branch():
    # NULL + length + one `if (` per regex rule: any new branch in R turns this red.
    assert _function_body().count("if (") == 2 + len(C.CATEGORY_RULES)
