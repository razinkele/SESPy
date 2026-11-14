"""Task 16 -- tests/parity/check_live.py, the live reference-data pre-flight."""
from __future__ import annotations

import ast
import fnmatch
import json
import shlex
import shutil
import subprocess
import sys
import tomllib
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


def test_perms_kernel_class_precedence(trees, tmp_path):
    stage, live = trees

    def ok(**kw):
        return run(stage, live, "--perms", str(_perms(tmp_path, _stat_lines(**kw))))

    assert ok(file_mode="044", owner="shiny", group="shiny") == 2  # owner class wins: u=0
    assert ok(file_mode="400", owner="shiny", group="razinka") == 0
    assert ok(file_mode="604", owner="razinka", group="shiny") == 2  # group class wins: g=0
    assert ok(file_mode="640", owner="razinka", group="shiny") == 0
    assert ok(file_mode="4644", owner="razinka", group="razinka") == 0  # 4 digits: last 3 only


def test_perms_directories_need_only_x(trees, tmp_path):
    stage, live = trees
    assert run(stage, live, "--perms", str(_perms(tmp_path, _stat_lines(dir_mode="711")))) == 0
    assert run(stage, live, "--perms", str(_perms(tmp_path, _stat_lines(dir_mode="700")))) == 2
    assert run(stage, live, "--perms", str(_perms(tmp_path, _stat_lines(dir_mode="744")))) == 2


def test_bad_pin_is_structural_not_a_traceback(trees, tmp_path):
    stage, live = trees
    assert check_live.main(["--pin", str(tmp_path / "nope.json"), "--stage", str(stage)]) == 2


# ---------------------------------------------------------------------------
# --fetch (subprocess.run monkeypatched; nothing leaves the machine)
# ---------------------------------------------------------------------------
class Remote:
    """A scripted ssh/scp peer."""

    def __init__(self, live_src, settings="SESPY_R_DATA_DIR=/data/live\n", settings_rc=0,
                 scp_rc=0, scp_err="", stat_mode="644"):
        self.live_src, self.settings, self.settings_rc = live_src, settings, settings_rc
        self.scp_rc, self.scp_err, self.stat_mode = scp_rc, scp_err, stat_mode
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kw):
        self.calls.append(list(cmd))
        cp = subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[0] == "ssh" and "server_settings.env" in cmd[3]:
            cp.returncode, cp.stdout = self.settings_rc, (self.settings if self.settings_rc == 0 else "")
        elif cmd[0] == "scp":
            if self.scp_rc:
                cp.returncode, cp.stderr = self.scp_rc, self.scp_err
            else:
                shutil.copy(self.live_src / cmd[3].rsplit("/", 1)[1], cmd[4])
        elif cmd[0] == "ssh":  # the stat command
            paths = shlex.split(cmd[3])[3:]
            cp.stdout = "".join(
                f"stat {self.stat_mode if p.endswith('.json') else '755'} root shiny {p}\n" for p in paths)
        # Like the real subprocess.run: bytes unless text=True, and text=True
        # decodes with the locale codec (cp1252 on a Windows checkout).
        for attr in ("stdout", "stderr"):
            v = getattr(cp, attr)
            b = v if isinstance(v, bytes) else v.encode("utf-8")
            setattr(cp, attr, b.decode("cp1252") if kw.get("text") else b)
        return cp


@pytest.fixture
def fetch_run(monkeypatch, trees):
    stage, live_src = trees

    def go(remote, *extra):
        monkeypatch.setattr(subprocess, "run", remote)
        return check_live.main(["--pin", str(PIN), "--stage", str(stage), "--fetch",
                                "--server", "deploy@example.test", "--app-dir", "/srv/app", *extra])

    return go, live_src


def test_fetch_reads_config_env(monkeypatch, tmp_path, trees):
    stage, live_src = trees
    cfg_dir = tmp_path / "cfgroot"
    monkeypatch.setattr(check_live, "REPO_ROOT", cfg_dir)
    (cfg_dir / "deploy").mkdir(parents=True)
    (cfg_dir / "deploy" / "config.env").write_text(
        'DEPLOY_SERVER=deploy@example.test\nDEPLOY_DIR="/srv/app"\n', encoding="utf-8")
    remote = Remote(live_src)
    monkeypatch.setattr(subprocess, "run", remote)
    rc = check_live.main(["--pin", str(PIN), "--stage", str(stage), "--fetch"])
    assert rc == 0  # complete stat output: the happy path
    assert remote.calls[0][:3] == ["ssh", "--", "deploy@example.test"]
    assert "/srv/app/server_settings.env" in remote.calls[0][3]  # settings read comes first
    scps = [c for c in remote.calls if c[0] == "scp"]
    assert any(c[3] == "deploy@example.test:/data/live/ses_knowledge_db.json" for c in scps)
    assert any(c[3] == "deploy@example.test:/data/VERSION_INFO.json" for c in scps)


def test_fetch_connection_failure_exits_3(fetch_run):
    go, live_src = fetch_run
    assert go(Remote(live_src, settings_rc=255), "--warn-only") == 3


def test_fetch_scp_255_exits_3(fetch_run):
    go, live_src = fetch_run
    assert go(Remote(live_src, scp_rc=255, scp_err="Connection reset")) == 3


def test_fetch_override_off_skips_live(fetch_run):
    go, live_src = fetch_run
    remote = Remote(live_src, settings="SESPY_R_DATA_DIR=off\n")
    assert go(remote) == 0
    assert all(c[0] == "ssh" for c in remote.calls)  # nothing is scp'd when the override is off


def test_fetch_absent_settings_uses_default_path(fetch_run):
    go, live_src = fetch_run
    remote = Remote(live_src, settings_rc=3)  # exit 3 = file absent
    go(remote)
    default = check_live.r_kb.DEFAULT_OVERRIDE_DIR
    assert any(c[0] == "scp" and c[3].endswith(f":{default}/ses_knowledge_db.json") for c in remote.calls)


def test_fetch_unreadable_settings_is_structural(fetch_run):
    go, live_src = fetch_run
    remote = Remote(live_src, settings_rc=4)  # exists, cat failed
    assert go(remote) == 2
    assert not any(c[0] == "scp" for c in remote.calls)  # must not fall back to the default path
    assert go(Remote(live_src, settings_rc=4), "--warn-only") == 0


def test_fetch_scp_permission_denied_is_structural_not_exit_3(fetch_run):
    go, live_src = fetch_run
    assert go(Remote(live_src, scp_rc=1, scp_err="scp: open remote: Permission denied")) == 2


def test_fetch_quotes_remote_paths(fetch_run):
    go, live_src = fetch_run
    evil = "/x'; touch /tmp/pwned; '"
    remote = Remote(live_src, settings=f"SESPY_R_DATA_DIR={evil}\n")
    assert go(remote) == 2  # unsafe to fetch: structural
    assert not any(c[0] == "scp" for c in remote.calls)
    stat = remote.calls[-1]
    assert stat[0] == "ssh"
    assert shlex.quote(evil + "/ses_knowledge_db.json") in stat[3]
    assert evil + "/ses_knowledge_db.json" in shlex.split(stat[3])  # one literal argument


def test_fetch_settings_bom_is_stripped_like_the_app(fetch_run):
    # final review F3: decoded as utf-8-sig bytes, as Registry._read_settings does
    go, live_src = fetch_run
    remote = Remote(live_src, settings=b"\xef\xbb\xbfSESPY_R_DATA_DIR=off\n")
    assert go(remote) == 0
    assert all(c[0] == "ssh" for c in remote.calls)  # off: not the default path
    remote = Remote(live_src, settings=b"\xef\xbb\xbfSESPY_R_DATA_DIR=/data/live\r\n")
    assert go(remote) == 0
    assert any(c[0] == "scp" and c[3].endswith(":/data/live/ses_knowledge_db.json")
               for c in remote.calls)


def test_fetch_settings_bytes_undefined_in_cp1252_do_not_crash(fetch_run):
    go, live_src = fetch_run
    remote = Remote(live_src, settings=b"# \x81\x8d\x8f\x90\x9d\nSESPY_R_DATA_DIR=off\n")
    assert go(remote) == 0
    assert all(c[0] == "ssh" for c in remote.calls)


@pytest.mark.parametrize("value", ["relative/dir", "/a\x00b"])
def test_fetch_rejects_non_absolute_or_nul_dir(fetch_run, value):
    go, live_src = fetch_run
    remote = Remote(live_src, settings=f"SESPY_R_DATA_DIR={value}\n")
    assert go(remote) == 2
    assert [c[0] for c in remote.calls] == ["ssh"]


# ---------------------------------------------------------------------------
# collection guard
# ---------------------------------------------------------------------------
def _python_files_patterns() -> list[str]:
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pats = cfg.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("python_files")
    if pats is None:
        return ["test_*.py", "*_test.py"]
    return pats.split() if isinstance(pats, str) else list(pats)


def test_not_collected_by_pytest(tmp_path):
    name = "check_live.py"
    pats = _python_files_patterns()
    assert not any(fnmatch.fnmatch(name, p) for p in pats), (name, pats)
    tree = ast.parse((ROOT / "tests" / "parity" / name).read_text(encoding="utf-8"))
    leaked = [n.name for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name.lower().startswith("test")]
    assert not leaked, f"{name} defines pytest-looking objects: {leaked}"
    # canary: the same pattern list does collect a matching name, so the checks above can fail
    body = "def test_canary():\n    pass\n"
    (tmp_path / "check_live.py").write_text(body, encoding="utf-8")
    (tmp_path / "test_check_live_cli.py").write_text(body, encoding="utf-8")
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "-o", "python_files=" + " ".join(pats), "--rootdir", str(tmp_path), str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True).stdout
    assert "test_check_live_cli.py::test_canary" in out
    assert "\ncheck_live.py::" not in "\n" + out


@pytest.mark.parametrize("path, want", [
    ("/srv/data/kb.json", ["/srv/data", "/srv", "/"]),
    ("//srv/data/kb.json", ["//srv/data", "//srv", "//", "/"]),
    ("/kb.json", ["/"]),
])
def test_ancestors_terminates_on_double_slash_root(path, want):
    # PR #33 review: posixpath.dirname("//") == "//", so a SESPY_R_DATA_DIR of
    # //srv/... looped forever in fetch()/check_perms(). Stop at a fixed point.
    assert check_live._ancestors(path) == want
