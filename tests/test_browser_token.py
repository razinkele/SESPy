"""Unit tests for the per-browser token plumbing (sespy/browser_token.py)."""
from __future__ import annotations

from sespy import browser_token as bt

TOKEN = "0f8c2a4e-1b7d-4c3e-9a55-6d2e8f1a0b3c"


class _Input:
    """Minimal stand-in for Shiny's `input`: attribute access returns a
    callable, a missing input raises like Shiny does before the browser
    has sent a value."""

    def __init__(self, **values):
        self._values = values

    def __contains__(self, name):
        return name in self._values

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._values:
            raise KeyError(name)
        return lambda: self._values[name]


def test_reads_valid_token():
    assert bt.read_browser_token(_Input(**{bt.BROWSER_TOKEN_INPUT: TOKEN})) == TOKEN


def test_missing_input_is_none():
    """Before the browser script runs (or with JS blocked) there is no token."""
    assert bt.read_browser_token(_Input()) is None


def test_invalid_token_is_none():
    assert bt.read_browser_token(_Input(**{bt.BROWSER_TOKEN_INPUT: "../x"})) is None
    assert bt.read_browser_token(_Input(**{bt.BROWSER_TOKEN_INPUT: 42})) is None


def test_script_stores_token_in_local_storage_and_reports_it():
    js = str(bt.browser_token_script())
    assert "localStorage" in js
    assert "randomUUID" in js
    assert f'"{bt.BROWSER_TOKEN_INPUT}"' in js
    assert "shiny:connected" in js
