"""Unit tests for sespy.utils — small shared helpers."""
from __future__ import annotations

from sespy.utils import next_id


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
