"""K1 Task 4: allow-list, vendored snapshot, packaging."""
from __future__ import annotations

import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sespy import r_kb  # noqa: E402
from sespy.r_sync import sha256_norm  # noqa: E402


def test_vendored_snapshot_loads():
    manifest = json.loads((ROOT / "sespy/data/r_kb/manifest.json").read_text(encoding="utf-8"))
    for row in r_kb.ALLOW_LIST:
        entry = r_kb.VENDORED.files[row.name]
        assert entry.source == "vendored"
        assert entry.sha256_norm == manifest["files"][row.name]
        assert entry.sha256_norm == sha256_norm(entry.data)
    assert r_kb.VENDORED.kb()["contexts"]
    assert r_kb.VENDORED.governance()["countries"]
    assert r_kb.VENDORED.get("ses_knowledge_db.json") is r_kb.VENDORED.kb()


def test_version_major_int_and_string():
    assert r_kb.version_major(2) == 2
    assert r_kb.version_major("1.0") == 1


def test_validate_rejects_missing_key_and_small_count():
    row = r_kb.ALLOW_LIST[0]
    good = json.loads(json.dumps(r_kb.VENDORED.kb()))
    assert r_kb.validate(row, good, 1) is None
    bad = dict(good)
    del bad["generic_fallback"]
    assert "generic_fallback" in r_kb.validate(row, bad, 1)
    small = dict(good, contexts={})
    assert "contexts" in r_kb.validate(row, small, 1)
    assert r_kb.validate(row, good, 2) is not None  # major mismatch
    assert r_kb.validate(row, [], 1) is not None  # not an object


def test_validate_rejects_wrong_container_type():
    # PR #33 review: a list with enough entries passed the length check, then
    # the wizard's countries.get(code) raised AttributeError on it.
    gov_row = r_kb._row(r_kb.GOVERNANCE_NAME)
    gov = json.loads(json.dumps(r_kb.VENDORED.governance()))
    gov_major = r_kb.version_major(gov[gov_row.version_key])
    assert r_kb.validate(gov_row, gov, gov_major) is None
    as_list = dict(gov, countries=list(gov["countries"].values()))
    assert len(as_list["countries"]) >= gov_row.min_counts["countries"]
    reason = r_kb.validate(gov_row, as_list, gov_major)
    assert reason is not None and "countries" in reason
    kb_row = r_kb._row(r_kb.KB_NAME)
    kb = json.loads(json.dumps(r_kb.VENDORED.kb()))
    links_as_dict = dict(kb, cross_ecosystem_links={"a": 1})
    reason = r_kb.validate(kb_row, links_as_dict, 1)
    assert reason is not None and "cross_ecosystem_links" in reason


def test_every_counted_path_declares_its_container():
    for row in r_kb.ALLOW_LIST:
        assert set(row.containers) == set(row.min_counts), row.name


def test_provenance_has_no_data_key():
    p = r_kb.VENDORED.provenance("ses_knowledge_db.json")
    assert set(p) == {"source", "sha256_norm", "version", "vendored_r_tag"}
    assert p["vendored_r_tag"] == r_kb.VENDORED.manifest["r_tag"]
    assert "data" not in p


def test_label_vendored():
    assert r_kb.VENDORED.label("ses_knowledge_db.json") == "R v1.35.6"


def test_package_data_covers_allow_list():
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    globs = cfg["tool"]["setuptools"]["package-data"]["sespy"]

    def covers(glob: str, path: str) -> bool:
        gp, pp = glob.split("/"), path.split("/")
        return len(gp) == len(pp) and all(fnmatch.fnmatchcase(p, g) for g, p in zip(gp, pp))

    names = [row.name for row in r_kb.ALLOW_LIST] + ["manifest.json"]
    for name in names:
        assert any(covers(g, f"data/r_kb/{name}") for g in globs), name


def test_import_fails_without_vendored_file(tmp_path):
    copy = tmp_path / "sespy"
    shutil.copytree(ROOT / "sespy", copy, ignore=shutil.ignore_patterns("__pycache__"))
    (copy / "data/r_kb/country_governance_db.json").unlink()
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sespy, sys\n"
        f"assert sespy.__file__.startswith({str(tmp_path)!r}), sespy.__file__\n"
        "import sespy.r_kb\n",
        encoding="utf-8",
    )
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    r = subprocess.run([sys.executable, str(probe)], env=env, capture_output=True, text=True)
    assert r.returncode != 0
    assert "country_governance_db.json" in r.stderr
    assert "AssertionError" not in r.stderr


@pytest.mark.slow
def test_wheel_contains_r_kb(tmp_path):
    pytest.importorskip("build")
    import zipfile

    r = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    wheel = next(tmp_path.glob("*.whl"))
    names = zipfile.ZipFile(wheel).namelist()
    for n in ("ses_knowledge_db.json", "country_governance_db.json", "manifest.json"):
        assert f"sespy/data/r_kb/{n}" in names
