"""P1a — the R fixtures are pinned to MarineSABRES v1.29.0 (e33faea).

tests/parity/r_sync.json is the machine-readable pin; docs/parity/R_SYNC.md
is the human record and must list the same hashes. A new R release is
adopted by re-copying the fixtures and updating both in one commit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from sespy.r_sync import sha256_norm, sha256_text_norm

ROOT = Path(__file__).resolve().parents[2]
PIN = json.loads((ROOT / "tests" / "parity" / "r_sync.json").read_text(encoding="utf-8"))


def test_pin_shape():
    assert PIN["r_tag"] == "v1.29.0" and PIN["r_commit"] == "e33faea"
    paths = sorted(PIN["files"])
    assert len(paths) == 8
    assert "tests/parity/r_rules/dapsiwrm_connection_rules.R" in paths
    assert sum(p.startswith("tests/parity/r_templates/") for p in paths) == 7
    assert not any("backup" in p for p in paths)


@pytest.mark.parametrize("rel", sorted(PIN["files"]))
def test_fixture_hash_matches_pin(rel):
    data = (ROOT / rel).read_bytes().decode("utf-8-sig")
    got = sha256_norm(json.loads(data)) if rel.endswith(".json") else sha256_text_norm(data)
    assert got == PIN["files"][rel], f"{rel} drifted from the R pin"


def test_r_sync_md_lists_exactly_the_pinned_hashes():
    md = (ROOT / "docs" / "parity" / "R_SYNC.md").read_text(encoding="utf-8")
    assert set(re.findall(r"\b[0-9a-f]{64}\b", md)) == set(PIN["files"].values())


# ---- the helpers ------------------------------------------------------------

def test_sha256_norm_ignores_key_order_and_formatting():
    a = {"b": 1, "a": ["é", {"y": 2, "x": None}]}
    b = json.loads('{\r\n  "a": ["\\u00e9", {"x": null, "y": 2}],\r\n  "b": 1\r\n}')
    assert sha256_norm(a) == sha256_norm(b)


def test_sha256_norm_is_the_documented_encoding():
    import hashlib
    obj = {"k": "é"}
    want = hashlib.sha256('{"k":"é"}'.encode("utf-8")).hexdigest()
    assert sha256_norm(obj) == want          # ensure_ascii=False, compact separators


def test_sha256_text_norm_normalises_crlf(tmp_path):
    p = tmp_path / "x.R"
    p.write_bytes(b"a <- 1\r\nb <- 2\r\n")
    assert sha256_text_norm(p.read_bytes().decode("utf-8")) == sha256_text_norm("a <- 1\nb <- 2\n")


def test_r_sync_imports_without_shiny():
    import subprocess
    import sys
    code = "import sys, sespy.r_sync; sys.exit(1 if 'shiny' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 0
