"""K1 Task 5: registry - live override, settings file, change detection, fallback."""
from __future__ import annotations

import copy
import json
import logging
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sespy import r_kb  # noqa: E402
from sespy.r_sync import sha256_norm  # noqa: E402

KB, GOV = r_kb.KB_NAME, r_kb.GOVERNANCE_NAME


class Env:
    def __init__(self, tmp_path: Path, monkeypatch):
        self.root = tmp_path
        self.app = tmp_path / "app"
        self.app.mkdir()
        self.data = tmp_path / "r" / "data"
        self.data.mkdir(parents=True)
        self.mp = monkeypatch
        monkeypatch.setattr(r_kb, "_REGISTRY", r_kb._Registry())
        monkeypatch.setenv(r_kb.ENV_VAR, str(self.data))
        r_kb.configure(self.app)

    def doc(self, name, marker="m1"):
        data = copy.deepcopy(r_kb.VENDORED.files[name].data)
        data["x_marker"] = marker
        return data

    def write(self, name, data=None, marker="m1"):
        data = self.doc(name, marker) if data is None else data
        path = self.data / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return data

    def write_both(self, marker="m1"):
        return self.write(KB, marker=marker), self.write(GOV, marker=marker)


@pytest.fixture
def env(tmp_path, monkeypatch):
    return Env(tmp_path, monkeypatch)


def transitions(caplog):
    return [r.getMessage() for r in caplog.records
            if "r_kb.transition" in r.getMessage() and r.name == "sespy.r_kb"]


# ---- settings helper (single parse rule) -----------------------------------

def test_parse_settings_text_rules():
    p = r_kb.parse_settings_text
    assert p("") is None
    assert p("OTHER=1\n") is None
    assert p("SESPY_R_DATA_DIR=/a\n") == "/a"
    assert p("SESPY_R_DATA_DIR=/a\nSESPY_R_DATA_DIR=/b\n") == "/b"
    assert p("SESPY_R_DATA_DIR=/a\r\n") == "/a"
    assert p("SESPY_R_DATA_DIR=  /a b  \n") == "/a b"
    assert p("SESPY_R_DATA_DIR=\n") == ""
    assert p(" SESPY_R_DATA_DIR=/x\n") is None          # anchored at line start
    assert p("# SESPY_R_DATA_DIR=/x\n") is None
    assert p("XSESPY_R_DATA_DIR=/x\n") is None
    assert p("SESPY_R_DATA_DIR=/a\nSESPY_R_DATA_DIRX=/b\n") == "/a"


def test_override_dir_from_precedence():
    f = r_kb.override_dir_from
    assert f({}, None) == r_kb.DEFAULT_OVERRIDE_DIR
    assert f({}, "nothing here\n") == r_kb.DEFAULT_OVERRIDE_DIR
    assert f({}, "SESPY_R_DATA_DIR=/s\n") == "/s"
    assert f({"SESPY_R_DATA_DIR": "/e"}, "SESPY_R_DATA_DIR=/s\n") == "/e"     # env wins
    assert f({"SESPY_R_DATA_DIR": ""}, "SESPY_R_DATA_DIR=/s\n") is None       # empty env = off
    assert f({"SESPY_R_DATA_DIR": "OFF"}, "SESPY_R_DATA_DIR=/s\n") is None
    assert f({}, "SESPY_R_DATA_DIR=\n") is None
    assert f({}, "SESPY_R_DATA_DIR= Off \n") is None


def test_settings_file_last_line_wins_and_off(tmp_path, monkeypatch):
    monkeypatch.setattr(r_kb, "_REGISTRY", r_kb._Registry())
    monkeypatch.delenv(r_kb.ENV_VAR, raising=False)
    app = tmp_path / "app"
    app.mkdir()
    data = tmp_path / "r" / "data"
    data.mkdir(parents=True)
    e = Env.__new__(Env)
    e.data = data
    e.write = Env.write.__get__(e)
    e.doc = Env.doc.__get__(e)
    e.write(KB)
    e.write(GOV)
    r_kb.configure(app)
    (app / r_kb.SETTINGS_FILE).write_text(
        f"SESPY_R_DATA_DIR={tmp_path / 'nowhere'}\nSESPY_R_DATA_DIR={data}\n", encoding="utf-8")
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "shared"
    (app / r_kb.SETTINGS_FILE).write_text(
        f"SESPY_R_DATA_DIR={data}\nSESPY_R_DATA_DIR=OFF\n", encoding="utf-8")
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"


# ---- registry ---------------------------------------------------------------

def test_unconfigured_registry_is_vendored(monkeypatch):
    monkeypatch.setattr(r_kb, "_REGISTRY", r_kb._Registry())
    r_kb.refresh()
    assert r_kb.current() is r_kb.VENDORED


def test_override_valid_becomes_shared(env):
    kb, gov = env.write_both()
    r_kb.refresh()
    snap = r_kb.current()
    assert snap.files[KB].source == "shared" and snap.files[GOV].source == "shared"
    assert snap.kb()["x_marker"] == "m1"
    assert snap.files[KB].sha256_norm == sha256_norm(kb)
    assert snap.provenance(KB)["source"] == "shared"


def test_env_off_disables_file(env):
    env.write_both()
    (env.app / r_kb.SETTINGS_FILE).write_text(f"SESPY_R_DATA_DIR={env.data}\n", encoding="utf-8")
    env.mp.setenv(r_kb.ENV_VAR, "off")
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"


def test_env_empty_disables_file(env):
    env.write_both()
    (env.app / r_kb.SETTINGS_FILE).write_text(f"SESPY_R_DATA_DIR={env.data}\n", encoding="utf-8")
    env.mp.setenv(r_kb.ENV_VAR, "")
    if os.environ.get(r_kb.ENV_VAR) != "":
        pytest.skip("platform drops empty environment variables")
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"


def test_settings_file_reread_each_refresh(env):
    env.write_both()
    env.mp.delenv(r_kb.ENV_VAR)
    settings = env.app / r_kb.SETTINGS_FILE
    settings.write_text(f"SESPY_R_DATA_DIR={env.data}\n", encoding="utf-8")
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "shared"
    settings.write_text("SESPY_R_DATA_DIR=off\n", encoding="utf-8")
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"
    settings.write_text(f"SESPY_R_DATA_DIR={env.data}\n", encoding="utf-8")
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "shared"


# ---- a bad settings file never stops a session (final review F1) -------------
# app.py calls r_kb.refresh() then r_kb.current() at every session start.

def _shared_via_settings(env) -> Path:
    env.write_both()
    env.mp.delenv(r_kb.ENV_VAR)                  # the env var would win over the file
    settings = env.app / r_kb.SETTINGS_FILE
    settings.write_text(f"SESPY_R_DATA_DIR={env.data}\n", encoding="utf-8")
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "shared"
    return settings


def test_non_utf8_settings_does_not_raise(env):
    settings = _shared_via_settings(env)
    comment = "# Šiauliai: R data\n".encode("cp1257")
    settings.write_bytes(comment + f"SESPY_R_DATA_DIR={env.data}\n".encode())
    r_kb.refresh()                               # the ASCII key line still counts
    assert r_kb.current().files[KB].source == "shared"
    settings.write_bytes(comment + b"SESPY_R_DATA_DIR=off\n")
    r_kb.refresh()                               # off, not "absent" = the default dir
    assert r_kb.current().files[KB].source == "vendored"
    settings.write_bytes(b"\xef\xbb\xbf" + comment + b"SESPY_R_DATA_DIR=off\r\n")
    r_kb.refresh()                               # BOM + bad byte + CRLF
    assert r_kb.current().files[KB].source == "vendored"


def test_nul_in_settings_value_does_not_raise(env, caplog):
    settings = _shared_via_settings(env)
    settings.write_bytes(f"SESPY_R_DATA_DIR={env.data}\x00x\n".encode())
    caplog.set_level(logging.WARNING, logger="sespy.r_kb")
    r_kb.refresh()
    snap = r_kb.current()
    assert all(e.source == "vendored" for e in snap.files.values())
    assert any("override directory unavailable: ValueError" in m for m in transitions(caplog))


def test_refresh_failure_falls_back_to_vendored(env, monkeypatch, caplog):
    _shared_via_settings(env)

    def boom(*_a, **_kw):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(r_kb, "override_dir_from", boom)
    caplog.set_level(logging.WARNING, logger="sespy.r_kb")
    r_kb.refresh()                               # must not raise
    snap = r_kb.current()
    assert all(e.source == "vendored" for e in snap.files.values())
    assert snap.live_r_version is None
    assert any("r_kb.refresh failed (RuntimeError" in r.getMessage() for r in caplog.records)
    caplog.clear()
    r_kb.refresh()                               # already vendored: still logged
    assert r_kb.current().files[KB].source == "vendored"
    assert any("r_kb.refresh failed" in r.getMessage() for r in caplog.records)


def test_corrupt_keeps_last_good_then_retries(env, caplog):
    env.write_both()
    r_kb.refresh()
    good = r_kb.current()
    (env.data / KB).write_text("{ torn", encoding="utf-8")
    caplog.set_level(logging.WARNING, logger="sespy.r_kb")
    r_kb.refresh()
    assert r_kb.current() is good
    assert any("to=last-good" in m and KB in m for m in transitions(caplog))
    r_kb.refresh()                                   # still broken: retried, not "seen"
    assert r_kb.current() is good
    env.write(KB, marker="m2")
    r_kb.refresh()
    assert r_kb.current().kb()["x_marker"] == "m2"


def test_corrupt_without_last_good_stays_vendored(env, caplog):
    env.write(GOV)
    (env.data / KB).write_text("nope", encoding="utf-8")
    caplog.set_level(logging.WARNING, logger="sespy.r_kb")
    r_kb.refresh()
    assert r_kb.current().files[GOV].source == "vendored"
    assert any("to=vendored" in m for m in transitions(caplog))


def test_too_small_and_wrong_major_rejected(env):
    small = env.doc(KB)
    small["contexts"] = dict(list(small["contexts"].items())[:5]) if isinstance(
        small["contexts"], dict) else small["contexts"][:5]
    env.write(KB, small)
    env.write(GOV)
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"
    assert r_kb.current().files[GOV].source == "vendored"     # no partial swap
    env.write(KB)
    wrong = env.doc(GOV)
    wrong["version"] = "9.0"
    env.write(GOV, wrong)
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"
    assert r_kb.current().files[GOV].source == "vendored"


def test_one_bad_file_means_no_swap(env):
    env.write_both(marker="old")
    r_kb.refresh()
    old = r_kb.current()
    env.write(KB, marker="new")
    (env.data / GOV).write_text("{ corrupt", encoding="utf-8")
    r_kb.refresh()
    snap = r_kb.current()
    assert snap is old
    assert snap.kb()["x_marker"] == "old" and snap.governance()["x_marker"] == "old"


def test_missing_dir_goes_vendored_even_after_shared(env, caplog):
    env.write_both()
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "shared"
    env.data.rename(env.data.with_name("data.bak"))
    caplog.set_level(logging.WARNING, logger="sespy.r_kb")
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"
    assert r_kb.current().label(KB).startswith("R ")
    assert any("from=shared to=vendored" in m for m in transitions(caplog))


def test_unreadable_dir_goes_vendored(env, monkeypatch):
    # chmod is ineffective on Windows, so the denial is simulated: os.stat of the
    # override directory raises PermissionError (a real denied dir does the same).
    env.write_both()
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "shared"
    real_stat = os.stat
    target = str(env.data)

    def deny(path, *a, **k):
        if str(path) == target:
            raise PermissionError(13, "denied")
        return real_stat(path, *a, **k)

    monkeypatch.setattr(os, "stat", deny)
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"


@pytest.mark.skipif(sys.platform == "win32", reason="chmod does not deny reads on Windows")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores modes")
def test_real_chmod_unreadable_dir_goes_vendored(env):
    env.write_both()
    r_kb.refresh()
    env.data.chmod(0)
    try:
        r_kb.refresh()
        assert r_kb.current().files[KB].source == "vendored"
    finally:
        env.data.chmod(stat.S_IRWXU)


def test_unreadable_files_fall_back_to_vendored_and_label(env, monkeypatch, caplog):
    # Review Focus 5. Simulated: Path.read_text of the override files raises
    # PermissionError (chmod cannot deny reads on Windows).
    env.write_both()
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "shared"
    real = Path.read_text

    def deny(self, *a, **k):
        if self.parent == env.data:
            raise PermissionError(13, "denied")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", deny)
    # touch the files so the change key differs and they are re-read
    for n in (KB, GOV):
        os.utime(env.data / n, ns=(1, 1))
    caplog.set_level(logging.WARNING, logger="sespy.r_kb")
    r_kb.refresh()
    snap = r_kb.current()
    assert snap.files[KB].source == "vendored" and snap.files[GOV].source == "vendored"
    assert snap.label(KB) == f"R {snap.manifest['r_tag']}"
    assert any("from=shared to=vendored" in m and "unreadable" in m for m in transitions(caplog))


def test_missing_file_in_present_dir(env, caplog):
    env.write_both()
    r_kb.refresh()
    good = r_kb.current()
    (env.data / GOV).unlink()
    caplog.set_level(logging.WARNING, logger="sespy.r_kb")
    r_kb.refresh()
    assert r_kb.current() is good
    assert any("to=last-good" in m and GOV in m for m in transitions(caplog))
    # fresh registry with a missing file and no last good -> vendored
    env.mp.setattr(r_kb, "_REGISTRY", r_kb._Registry())
    r_kb.configure(env.app)
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"


def test_same_size_same_mtime_rewrite_detected(env):
    env.write_both(marker="aaaa")
    r_kb.refresh()
    assert r_kb.current().kb()["x_marker"] == "aaaa"
    path = env.data / KB
    st = os.stat(path)
    tmp = env.data / (KB + ".tmp")
    tmp.write_text(json.dumps(env.doc(KB, marker="bbbb")), encoding="utf-8")
    assert tmp.stat().st_size == st.st_size
    os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
    os.replace(tmp, path)                    # rename swap, as R's deploy does
    r_kb.refresh()
    assert r_kb.current().kb()["x_marker"] == "bbbb"


def test_unchanged_files_not_reparsed(env, monkeypatch):
    env.write_both()
    r_kb.refresh()
    first = r_kb.current()
    calls = []
    real = r_kb._Registry._parse
    monkeypatch.setattr(r_kb._Registry, "_parse",
                        lambda self, *a, **k: calls.append(1) or real(self, *a, **k))
    r_kb.refresh()
    r_kb.refresh()
    assert calls == []
    assert r_kb.current() is first


def test_hashes_for_load_check(env):
    vk, vg = (r_kb.VENDORED.files[n].sha256_norm for n in (KB, GOV))
    assert r_kb.hashes_for_load_check(KB) == (vk, None)
    kb, _ = env.write_both()
    r_kb.refresh()
    assert r_kb.hashes_for_load_check(KB) == (vk, sha256_norm(kb))
    assert r_kb.hashes_for_load_check(GOV)[0] == vg
    env.data.rename(env.data.with_name("data.bak"))
    r_kb.refresh()
    assert r_kb.current().files[KB].source == "vendored"
    assert r_kb.hashes_for_load_check(KB) == (vk, sha256_norm(kb))     # survives fallback
    with pytest.raises(KeyError):
        r_kb.hashes_for_load_check("nope.json")


def test_label_shared_differs(env):
    env.write_both()
    r_kb.refresh()
    tag = r_kb.current().manifest["r_tag"]
    assert r_kb.current().label(KB) == f"shared, differs from R {tag}"


def test_label_shared_identical_is_r_tag(env):
    # Spec 4.1/4.8: a shared entry whose hash equals the manifest's is labelled "R <tag>".
    env.write(KB, copy.deepcopy(r_kb.VENDORED.files[KB].data))
    env.write(GOV, copy.deepcopy(r_kb.VENDORED.files[GOV].data))
    r_kb.refresh()
    snap = r_kb.current()
    assert snap.files[KB].source == "shared"
    assert snap.label(KB) == f"R {snap.manifest['r_tag']}"


def test_live_r_version_read(env):
    env.write_both()
    r_kb.refresh()
    assert r_kb.current().live_r_version is None
    (env.data.parent / "VERSION_INFO.json").write_text(json.dumps({"version": "1.35.9"}), encoding="utf-8")
    env.write(KB, marker="m2")
    r_kb.refresh()
    assert r_kb.current().live_r_version == "1.35.9"
    (env.data.parent / "VERSION_INFO.json").write_text("garbage", encoding="utf-8")
    env.write(KB, marker="m3")
    r_kb.refresh()
    assert r_kb.current().live_r_version is None


def test_two_sessions_keep_their_snapshots(env):
    env.write_both(marker="old")
    r_kb.refresh()
    a = r_kb.current()
    env.write(KB, marker="new")
    env.write(GOV, marker="new")
    r_kb.refresh()
    b = r_kb.current()
    assert a.kb() != b.kb()
    assert a.kb()["x_marker"] == "old" and b.kb()["x_marker"] == "new"


def test_never_writes(env):
    env.write_both()
    (env.data.parent / "VERSION_INFO.json").write_text("{}", encoding="utf-8")

    def fingerprint():
        out = {}
        for base in (env.data, env.data.parent):
            for p in sorted(base.rglob("*")):
                s = p.stat()
                out[str(p)] = (s.st_mtime_ns, s.st_size if p.is_file() else None)
        return out

    before = fingerprint()
    r_kb.refresh()
    (env.data / KB).write_text("{ torn", encoding="utf-8")
    before = fingerprint()
    r_kb.refresh()
    r_kb.refresh()
    assert fingerprint() == before


def test_transition_logged(env, caplog):
    env.write_both()
    caplog.set_level(logging.WARNING, logger="sespy.r_kb")
    r_kb.refresh()
    msgs = transitions(caplog)
    assert any("r_kb.transition file=" + KB in m and "from=vendored to=shared" in m
               and "reason=" in m and "hash=" in m for m in msgs)
    assert all(r.levelno == logging.WARNING for r in caplog.records if "r_kb.transition" in r.getMessage())
