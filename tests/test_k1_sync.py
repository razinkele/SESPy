"""K1 Task 1 - sync script: build_pin, manifest, local-pin hashing, tag guard."""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest

from sespy import r_template_catalogue as C
from sespy.r_template_catalogue import build_manifest, build_pin, fixture_r_tag, hash_local_pin

sys.path.insert(0, str(Path(__file__).parent))
import test_r_template_catalogue as T  # noqa: E402  (shared fake-repo helpers)


def _gz(path: Path, obj, mtime: int) -> None:
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=mtime) as g:
        g.write(json.dumps(obj).encode("utf-8"))


def test_build_pin_fails_on_dropped_path():
    old = {"r_tag": "v1.33.0", "r_commit": "4017feb",
           "files": {"a": "1", "b": "2"}, "accepted_warnings": []}
    with pytest.raises(ValueError, match="b"):
        build_pin(old, {"a": "1"}, [], r_tag="v1.35.6", r_commit="d1a655a")


def test_build_pin_allows_declared_removal():
    old = {"r_tag": "v1.33.0", "r_commit": "x", "files": {"a": "1", "b": "2"},
           "accepted_warnings": []}
    pin = build_pin(old, {"a": "1"}, [], r_tag="v1.35.6", r_commit="d1a655a",
                    removed_inputs=frozenset({"b"}))
    assert pin["files"] == {"a": "1"} and pin["r_tag"] == "v1.35.6"


def test_build_pin_regenerates_warnings():
    old = {"r_tag": "v", "r_commit": "c", "files": {}, "accepted_warnings": [{"kind": "stale"}]}
    assert build_pin(old, {}, [], r_tag="v1.35.6", r_commit="c")["accepted_warnings"] == []


def test_removed_inputs_is_a_deliberate_empty_constant():
    assert C.REMOVED_INPUTS == frozenset()


def test_gz_hash_ignores_gzip_mtime(tmp_path):
    p1, p2 = tmp_path / "a.json.gz", tmp_path / "b.json.gz"
    obj = {"r_tag": "v1.35.6", "k": ["é", 1]}
    _gz(p1, obj, 1)
    _gz(p2, obj, 999999)
    assert p1.read_bytes() != p2.read_bytes()
    assert hash_local_pin(p1) == hash_local_pin(p2)
    from sespy.r_sync import sha256_norm
    assert hash_local_pin(p1) == sha256_norm(obj)


def test_fixture_r_tag(tmp_path):
    p = tmp_path / "a.json.gz"
    _gz(p, {"r_tag": "v1.35.6"}, 0)
    assert fixture_r_tag(p) == "v1.35.6"
    _gz(p, {"other": 1}, 0)
    assert fixture_r_tag(p) == ""


def test_manifest_shape():
    raw = build_manifest("v1.35.6", "d1a655a", {"sespy/data/r_kb/ses_knowledge_db.json": "h1"})
    assert raw.endswith(b"}\n") and b"\r" not in raw
    assert json.loads(raw) == {"r_tag": "v1.35.6", "r_commit": "d1a655a",
                               "files": {"ses_knowledge_db.json": "h1"}}
    assert raw == (json.dumps(json.loads(raw), indent=2, ensure_ascii=False) + "\n").encode()


def test_constants():
    assert C.RUNTIME_INPUTS == {
        "data/ses_knowledge_db.json": "sespy/data/r_kb/ses_knowledge_db.json",
        "data/country_governance_db.json": "sespy/data/r_kb/country_governance_db.json"}
    assert C.MANIFEST_PATH == "sespy/data/r_kb/manifest.json"
    assert C.LOCAL_PINS == (
        *(f"tests/parity/r_fixtures/k1/{n}.json.gz"
          for n in ("lookup", "suggestions_grid", "habitat_specific", "countries", "report")),
        *(f"tests/parity/r_fixtures/k1b/{n}.json.gz"
          for n in ("connections", "lookup", "polarity")))
    for r in C.K1_R_SOURCES:
        assert C.INPUTS[r] == f"tests/parity/r_source/{r.rsplit('/', 1)[-1]}"
    assert C.GENERATED_RUNTIME == {
        "scripts/export_r_connection_db.R": "sespy/data/r_kb/ses_connection_db.json"}
    for r in C.K1B_R_SOURCES:
        assert C.INPUTS[r] == f"tests/parity/r_source/{r.rsplit('/', 1)[-1]}"
    assert len(C.TRANSLATION_SUBSETS["isa_data_entry"]) == 7
    assert C.TRANSLATION_SUBSETS["report_context"] == ("modules.report_context.include_context",)


def test_fixture_tag_mismatch_is_reported(tmp_path):
    root = T._tree(tmp_path)
    victim = root / C.LOCAL_PINS[2]
    _gz(victim, {"r_tag": "v0.0.1"}, 0)
    before = T._snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and any(C.LOCAL_PINS[2] in line for line in res.lines)
    assert T._snap(root) == before


def test_missing_local_pin_is_reported(tmp_path):
    root = T._tree(tmp_path)
    (root / C.LOCAL_PINS[0]).unlink()
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and any(C.LOCAL_PINS[0] in line for line in res.lines)


def test_git_mode_tag_mismatch_blocks_before_any_write(tmp_path):
    root, app = T._tree(tmp_path, "v1.31.0"), T._fake_r(tmp_path)
    _gz(root / C.LOCAL_PINS[1], {"r_tag": "v1.30.0"}, 0)
    before = T._snap(root)
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0")
    assert res.code == 1 and any(C.LOCAL_PINS[1] in line for line in res.lines)
    assert T._snap(root) == before


def test_check_reports_local_pin_hash_drift(tmp_path):
    root = T._tree(tmp_path)
    assert C.sync(repo_root=root, from_fixtures=True).code == 0
    assert C.sync(repo_root=root, from_fixtures=True, check=True).code == 0
    tag = T._pin(root)["r_tag"]
    _gz(root / C.LOCAL_PINS[3], {"r_tag": tag, "changed": True}, 0)
    res = C.sync(repo_root=root, from_fixtures=True, check=True)
    assert res.code == 1 and f"differs: {C.LOCAL_PINS[3]}" in res.lines


def test_check_reports_manifest_drift(tmp_path):
    root = T._tree(tmp_path)
    m = json.loads((root / C.MANIFEST_PATH).read_bytes())
    m["files"]["ses_knowledge_db.json"] = "0" * 64
    (root / C.MANIFEST_PATH).write_bytes(json.dumps(m, indent=2).encode())
    res = C.sync(repo_root=root, from_fixtures=True, check=True)
    assert res.code == 1 and f"differs: {C.MANIFEST_PATH}" in res.lines


def test_git_mode_vendors_runtime_inputs_raw_and_pins_all_kinds(tmp_path):
    root, app = T._tree(tmp_path, "v1.31.0"), T._fake_r(tmp_path)
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0")
    assert res.code == 0, res.lines
    for r_path, target in C.RUNTIME_INPUTS.items():
        assert (root / target).read_bytes() == (app / r_path).read_bytes()
    man = json.loads((root / C.MANIFEST_PATH).read_bytes())
    assert sorted(man["files"]) == ["country_governance_db.json", "ses_connection_db.json",
                                    "ses_knowledge_db.json"]
    pin = T._pin(root)
    assert set(C.LOCAL_PINS) <= set(pin["files"]) and C.MANIFEST_PATH in pin["files"]
    assert set(C.RUNTIME_INPUTS.values()) <= set(pin["files"])
    assert set(C.GENERATED_RUNTIME.values()) <= set(pin["files"])


def test_k1b_sources_pinned():
    assert C.K1B_R_SOURCES == ("data/ses_connection_knowledge_base.R",
                               "modules/ai_isa/connection_generator.R")
    pin = json.loads((T.ROOT / C.PIN_PATH).read_text(encoding="utf-8"))
    for r in C.K1B_R_SOURCES:
        assert f"tests/parity/r_source/{r.rsplit('/', 1)[-1]}" in pin["files"]
    assert "sespy/data/r_kb/ses_connection_db.json" in pin["files"]


def test_manifest_lists_connection_db():
    man = json.loads((T.ROOT / C.MANIFEST_PATH).read_text(encoding="utf-8"))
    assert "ses_connection_db.json" in json.dumps(man)


def test_generated_runtime_tag_must_match_pin(tmp_path):
    root = T._tree(tmp_path)
    target = root / "sespy/data/r_kb/ses_connection_db.json"
    doc = json.loads(target.read_bytes())
    doc["r_tag"] = "v1.34.2"
    target.write_bytes(json.dumps(doc).encode("utf-8"))
    res = C.sync(repo_root=root, from_fixtures=True, check=True)
    assert res.code == 1
    assert any("ses_connection_db.json" in m and "v1.34.2" in m for m in res.lines)
