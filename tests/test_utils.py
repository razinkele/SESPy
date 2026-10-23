"""Unit tests for sespy.utils — small shared helpers."""
from __future__ import annotations

from sespy.utils import next_id, safe_counter


def test_next_id_empty_list_returns_001():
    assert next_id([], "D") == "D001"


def test_next_id_fills_lowest_gap():
    """Gap-filling semantics — matches the existing _next_id behavior in
    isa_data_entry.py. ["D001","D003"] → "D002" (fills the gap),
    NOT "D004" (max-plus-one). Preserves stable ids across deletions."""
    assert next_id(["D001", "D003"], "D") == "D002"


def test_next_id_appends_when_contiguous():
    assert next_id(["D001", "D002", "D003"], "D") == "D004"


def test_next_id_ignores_other_prefixes():
    assert next_id(["D001", "P002", "A005"], "D") == "D002"
    assert next_id(["D001", "P002", "A005"], "P") == "P001"
    assert next_id(["D001", "P002", "A005"], "MPF") == "MPF001"


# --- P1b: R safe_counter (data_structure.R:25-33, v1.33.0) ------------------

def test_safe_counter_cases():            # R data_structure.R:25-33
    assert safe_counter(0, ["RM001", "RM012", "RMabc", "SH099"], "RM") == 12
    assert safe_counter(None, [], "RM") == 0
    assert safe_counter("5", ["RM002"], "RM") == 5
    assert safe_counter(3.0, ["SH001"], "SH") == 3
    assert safe_counter(True, ["SH002"], "SH") == 2      # a bool is not a count
    assert safe_counter("x", ["SH007", None], "SH") == 7


def test_safe_counter_reads_suffixes_as_numbers_like_r():
    # pending D4: R as.numeric(sub("^RM", "", ids)) -- exponent, padding and
    # fractions parse; non-finite suffixes are dropped; result int(max(...)).
    assert safe_counter(0, ["RM1e2"], "RM") == 100
    assert safe_counter(0, ["RM 7"], "RM") == 7
    assert safe_counter(0, ["RM12.5"], "RM") == 12
    assert safe_counter(0, ["RMinf", "RMnan", "RM3"], "RM") == 3
    assert safe_counter(float("inf"), ["RM4"], "RM") == 4     # non-finite counter -> 0
    assert safe_counter(float("nan"), [], "RM") == 0
    assert safe_counter(" 6 ", [], "SH") == 6                 # numeric string, padded


def test_append_xlsx_row_keeps_formula_like_text_as_text():
    from openpyxl import Workbook

    from sespy.utils import append_xlsx_row

    ws = Workbook().active
    append_xlsx_row(ws, ["=1+1", 2, "plain"])
    assert [(c.value, c.data_type) for c in ws[1]] == [("=1+1", "s"), (2, "n"), ("plain", "s")]
