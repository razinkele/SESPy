"""Task 16 -- tests/parity/check_live.py, the live reference-data pre-flight."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import check_live  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / "tests" / "parity" / "r_sync.json"
VENDORED = ROOT / "sespy" / "data" / "r_kb"
KB = "ses_knowledge_db.json"
GOV = "country_governance_db.json"
SETTINGS_PATH = "/srv/shiny-server/marinesabres/data"


@pytest.fixture
def trees(tmp_path):
    stage = tmp_path / "stage"
    dst = stage / "sespy" / "data" / "r_kb"
    dst.mkdir(parents=True)
    for f in (KB, GOV, "manifest.json"):
        shutil.copy(VENDORED / f, dst / f)
    live = tmp_path / "live"
    live.mkdir()
    for f in (KB, GOV):
        shutil.copy(VENDORED / f, live / f)
    (live / "VERSION_INFO.json").write_text('{"version": "9.9.9"}', encoding="utf-8")
    return stage, live


def run(stage, live, *extra):
    argv = ["--pin", str(PIN), "--stage", str(stage)]
    if live is not None:
        argv += ["--live", str(live)]
    return check_live.main(argv + list(extra))


def _edit(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_ok(trees, capsys):
    stage, live = trees
    assert run(stage, live) == 0
    assert "ok" in capsys.readouterr().out


def test_structural_missing_key_exits_2(trees):
    stage, live = trees
    _edit(live / KB, lambda d: d.pop("contexts"))
    assert run(stage, live) == 2


def test_shipped_copy_mismatch_exits_2(trees):
    stage, live = trees
    _edit(stage / "sespy/data/r_kb" / KB, lambda d: d.update(extra=1))
    assert run(stage, live) == 2


def test_override_off_still_checks_shipped_copy(trees):
    stage, _ = trees
    assert run(stage, None) == 0
    _edit(stage / "sespy/data/r_kb" / GOV, lambda d: d.update(extra=1))
    assert run(stage, None) == 2


def test_drift_warns_exit_0(trees, capsys):
    stage, live = trees
    _edit(live / KB, lambda d: d.update(note="newer"))
    assert run(stage, live) == 0
    out = capsys.readouterr().out
    assert "DRIFT" in out and KB in out and "9.9.9" in out


def test_drift_strict_exits_2(trees):
    stage, live = trees
    _edit(live / KB, lambda d: d.update(note="newer"))
    assert run(stage, live, "--strict") == 2


def test_warn_only_forces_0(trees):
    stage, live = trees
    _edit(live / KB, lambda d: d.pop("contexts"))
    _edit(stage / "sespy/data/r_kb" / GOV, lambda d: d.update(extra=1))
    assert run(stage, live, "--warn-only") == 0


def test_missing_txt_is_structural(trees):
    stage, live = trees
    (live / "missing.txt").write_text(GOV + "\n", encoding="utf-8")
    assert run(stage, live) == 2


def test_missing_txt_warn_only_exits_0(trees):
    stage, live = trees
    (live / "missing.txt").write_text(GOV + "\n", encoding="utf-8")
    assert run(stage, live, "--warn-only") == 0


def _stat_lines(file_mode="644", dir_mode="755", owner="razinka", group="razinka", skip=()):
    lines = []
    for name in (KB, GOV):
        lines.append(f"stat {file_mode} {owner} {group} {SETTINGS_PATH}/{name}")
    for d in check_live._ancestors(f"{SETTINGS_PATH}/{KB}"):
        if d not in skip:
            lines.append(f"stat {dir_mode} root root {d}")
    return "\n".join(lines) + "\n"


def _perms(tmp_path, text):
    p = tmp_path / "perms.txt"
    p.write_text(text, encoding="utf-8")
    return p


def test_unreadable_by_shiny_exits_2(trees, tmp_path):
    stage, live = trees
    assert run(stage, live, "--perms", str(_perms(tmp_path, _stat_lines()))) == 0
    bad = _perms(tmp_path, _stat_lines(file_mode="600", owner="razinka", group="razinka"))
    assert run(stage, live, "--perms", str(bad)) == 2
    group_ok = _perms(tmp_path, _stat_lines(file_mode="640", group="shiny"))
    assert run(stage, live, "--perms", str(group_ok)) == 0


def test_perms_four_digit_mode(trees, tmp_path):
    stage, live = trees
    ok = _perms(tmp_path, _stat_lines(file_mode="2640", dir_mode="2755", group="shiny"))
    assert run(stage, live, "--perms", str(ok)) == 0
    # the leading setgid digit must not be read as the owner class
    bad = _perms(tmp_path, _stat_lines(file_mode="2600", group="shiny"))
    assert run(stage, live, "--perms", str(bad)) == 2


def test_perms_missing_parent_line_fails(trees, tmp_path):
    stage, live = trees
    p = _perms(tmp_path, _stat_lines(skip=(SETTINGS_PATH,)))
    assert run(stage, live, "--perms", str(p)) == 2


def test_perms_sudo_test_fail(trees, tmp_path):
    stage, live = trees
    good = f"sudo-test {SETTINGS_PATH}/{KB} ok\nsudo-test {SETTINGS_PATH}/{GOV} ok\n"
    assert run(stage, live, "--perms", str(_perms(tmp_path, good))) == 0
    bad = f"sudo-test {SETTINGS_PATH}/{KB} ok\nsudo-test {SETTINGS_PATH}/{GOV} fail\n"
    assert run(stage, live, "--perms", str(_perms(tmp_path, bad))) == 2


def test_print_override_names(capsys):
    assert check_live.main(["--print-override-names"]) == 0
    assert capsys.readouterr().out.split() == [KB, GOV]


def test_fetch_reads_config_env(monkeypatch, tmp_path, trees):
    stage, live_src = trees
    cfg_dir = tmp_path / "cfgroot"
    monkeypatch.setattr(check_live, "REPO_ROOT", cfg_dir)
    (cfg_dir / "deploy").mkdir(parents=True)
    (cfg_dir / "deploy" / "config.env").write_text(
        'DEPLOY_SERVER=deploy@example.test\nDEPLOY_DIR="/srv/app"\n', encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        cp = subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[0] == "ssh" and "server_settings.env" in cmd[2]:
            cp.stdout = "SESPY_R_DATA_DIR=/data/live\n"
        elif cmd[0] == "scp":
            name = cmd[2].rsplit("/", 1)[1]
            shutil.copy(live_src / name, cmd[3])
        elif cmd[0] == "ssh":
            cp.stdout = "stat 644 razinka shiny /data/live/ses_knowledge_db.json\n"
        return cp

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = check_live.main(["--pin", str(PIN), "--stage", str(stage), "--fetch"])
    assert rc == 2  # perms deliberately incomplete: no governance line, no parent lines
    assert calls[0][:2] == ["ssh", "deploy@example.test"]
    assert "/srv/app/server_settings.env" in calls[0][2]  # settings read comes first
    scps = [c for c in calls if c[0] == "scp"]
    assert any(c[2] == "deploy@example.test:/data/live/ses_knowledge_db.json" for c in scps)
    assert any(c[2] == "deploy@example.test:/data/VERSION_INFO.json" for c in scps)


def test_fetch_connection_failure_exits_3(monkeypatch, tmp_path, trees):
    stage, _ = trees
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 255, "", "ssh: no route"))
    rc = check_live.main(["--pin", str(PIN), "--stage", str(stage), "--fetch",
                          "--server", "x@y", "--app-dir", "/a", "--warn-only"])
    assert rc == 3


def test_fetch_override_off_skips_live(monkeypatch, trees):
    stage, _ = trees

    def fake_run(cmd, **kw):
        assert cmd[0] == "ssh"  # nothing is scp'd when the override is off
        return subprocess.CompletedProcess(cmd, 0, "SESPY_R_DATA_DIR=off\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert check_live.main(["--pin", str(PIN), "--stage", str(stage), "--fetch",
                            "--server", "x@y", "--app-dir", "/a"]) == 0


def test_not_collected_by_pytest():
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/parity", "-p", "no:cacheprovider"],
        cwd=ROOT, env=env, capture_output=True, text=True).stdout
    assert "test_check_live.py" in out
    assert "check_live.py::" not in out.replace("test_check_live.py::", "")
