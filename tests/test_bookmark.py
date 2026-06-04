"""Tests for sespy.bookmark.parse_view (URL bookmarking)."""
from sespy.bookmark import parse_view

VIEWS = {"cld", "metrics", "loops"}


def test_parse_view_valid():
    assert parse_view("?view=metrics", VIEWS) == "metrics"


def test_parse_view_no_leading_question_mark():
    assert parse_view("view=cld", VIEWS) == "cld"


def test_parse_view_not_in_valid_set_is_none():
    assert parse_view("?view=does_not_exist", VIEWS) is None


def test_parse_view_missing_key_is_none():
    assert parse_view("?lang=es", VIEWS) is None


def test_parse_view_empty_and_none_are_none():
    assert parse_view("", VIEWS) is None
    assert parse_view(None, VIEWS) is None


def test_parse_view_empty_value_is_none():
    assert parse_view("?view=", VIEWS) is None


def test_parse_view_repeated_first_valid_wins():
    assert parse_view("?view=metrics&view=cld", VIEWS) == "metrics"
