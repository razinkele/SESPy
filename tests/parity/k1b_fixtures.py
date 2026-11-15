"""Loader for the K1b R-captured connection-scorer fixtures.

The fixtures are written by ``scripts/capture_k1b_fixtures.R`` against one R
release and live gzipped in ``tests/parity/r_fixtures/k1b/``. Each file is
``{"r_tag", "r_commit", <"cases" | "rows">}``.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

K1B_FIXTURE_TAG = "v1.35.6"
FIXTURE_DIR = Path(__file__).resolve().parent / "r_fixtures" / "k1b"
FIXTURE_NAMES = ("connections", "lookup", "polarity")


def load_k1b_fixture(name: str) -> dict:
    """The whole file; fails if it was captured at another R tag."""
    if name not in FIXTURE_NAMES:
        raise KeyError(f"unknown K1b fixture {name!r}; expected one of {FIXTURE_NAMES}")
    path = FIXTURE_DIR / f"{name}.json.gz"
    doc = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    if doc["r_tag"] != K1B_FIXTURE_TAG:
        raise ValueError(f"{name}: captured at {doc['r_tag']}, expected {K1B_FIXTURE_TAG}")
    return doc
