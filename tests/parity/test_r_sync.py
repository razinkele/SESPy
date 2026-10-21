"""P1a/P2 — the R fixtures are pinned to one MarineSABRES release.

tests/parity/r_sync.json is the machine-readable pin; docs/parity/R_SYNC.md
is the human record and must list the same hashes and the same release in
its generated block. A new R release is adopted with
`python -m scripts.sync_r_templates`, which rewrites the fixtures, the pin
and the block together, so the release is not a literal here.
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
    assert re.fullmatch(r"v\d+\.\d+\.\d+", PIN["r_tag"]), PIN["r_tag"]
    assert re.fullmatch(r"[0-9a-f]{7}", PIN["r_commit"]), PIN["r_commit"]
    paths = sorted(PIN["files"])
    assert len(paths) == 18
    assert "tests/parity/r_rules/dapsiwrm_connection_rules.R" in paths
    assert "tests/parity/r_source/template_loader.R" in paths
    assert sum(p.startswith("tests/parity/r_templates/") for p in paths) == 7
    # P1b (R v1.33.0): register / stakeholder sources and 6 translation files
    for name in ("constants.R", "response_measures_schema.R", "stakeholder_schema.R"):
        assert f"tests/parity/r_source/{name}" in paths
    assert sum(p.startswith("tests/parity/r_translations/") for p in paths) == 6
    assert not any("backup" in p for p in paths)
    assert isinstance(PIN["accepted_warnings"], list)


def test_r_sync_md_pin_line_equals_the_pin():
    md = (ROOT / "docs" / "parity" / "R_SYNC.md").read_text(encoding="utf-8")
    assert md.count("<!-- r-sync:begin -->") == 1 and md.count("<!-- r-sync:end -->") == 1
    block = md.split("<!-- r-sync:begin -->")[1].split("<!-- r-sync:end -->")[0]
    m = re.search(r"\*\*R release:\*\* MarineSABRES_SES_Shiny \*\*(v\d+\.\d+\.\d+)\*\*, "
                  r"commit `([0-9a-f]{7})`\.", block)
    assert m, "no generated pin line between the r-sync markers"
    assert (m.group(1), m.group(2)) == (PIN["r_tag"], PIN["r_commit"])


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
