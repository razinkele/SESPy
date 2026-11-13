"""Loader for the K1 R-captured knowledge-base fixtures.

The fixtures are written by ``scripts/capture_k1_fixtures.R`` against one R
release and live gzipped in ``tests/parity/r_fixtures/k1/``. Each file is
``{"r_tag", "r_commit", "data"}``.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

K1_FIXTURE_TAG = "v1.35.6"
FIXTURE_DIR = Path(__file__).resolve().parent / "r_fixtures" / "k1"
FIXTURE_NAMES = ("lookup", "suggestions_grid", "habitat_specific", "countries", "report")


def load_k1_fixture_raw(name: str) -> dict:
    """The whole file: ``r_tag``, ``r_commit`` and ``data``."""
    if name not in FIXTURE_NAMES:
        raise KeyError(f"unknown K1 fixture {name!r}; expected one of {FIXTURE_NAMES}")
    path = FIXTURE_DIR / f"{name}.json.gz"
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def load_k1_fixture(name: str) -> dict:
    """The fixture's ``data``; fails if it was captured at another R tag."""
    raw = load_k1_fixture_raw(name)
    if raw["r_tag"] != K1_FIXTURE_TAG:
        raise ValueError(f"{name}: captured at {raw['r_tag']}, expected {K1_FIXTURE_TAG}")
    return raw["data"]
