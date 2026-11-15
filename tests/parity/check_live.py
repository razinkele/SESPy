"""Live reference-data pre-flight checker (K1 spec 4.8).

Not collected by pytest (no ``test_`` prefix). Run from the working tree:

    check_live.py --live DIR --stage DIR --pin tests/parity/r_sync.json
    check_live.py --fetch            # fetch over ssh itself, then check

Checks:
  1. structural (exit 2): a live file is missing/unreadable, fails its
     allow-list row, or is not readable by user ``shiny`` (``--perms``);
  2. shipped copy (exit 2): the staged runtime files and manifest differ
     from their pins in r_sync.json;
  3. drift (warns, exit 0; exit 2 with ``--strict``): a live hash differs
     from the pin.
``--warn-only`` forces exit 0 (including an unusable pin; a ``--fetch``
without server/app-dir is a usage error and still exits 2). Exit 3 is
``--fetch`` only: ssh/scp itself failed (rc 255). An absent or unreadable
remote file is structural, never exit 3.
"""
from __future__ import annotations

import argparse
import json
import posixpath
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

# Always import THIS checkout's sespy (a stale editable install or a rollback
# worktree must not win).
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sespy import r_kb  # noqa: E402
from sespy.r_sync import sha256_norm  # noqa: E402
from sespy.r_template_catalogue import GENERATED_RUNTIME, MANIFEST_PATH, RUNTIME_INPUTS  # noqa: E402

DEFAULT_PIN = REPO_ROOT / "tests" / "parity" / "r_sync.json"
VENDORED_DIR = Path("sespy") / "data" / "r_kb"
SHINY_USER = "shiny"


def _load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


# --------------------------------------------------------------------------
# check 2: shipped copy
# --------------------------------------------------------------------------
def check_shipped(stage: Path, pin: dict) -> list[str]:
    problems: list[str] = []
    pinned = pin.get("files", {})
    for rel in (*RUNTIME_INPUTS.values(), *GENERATED_RUNTIME.values(), MANIFEST_PATH):
        path = stage / rel
        want = pinned.get(rel)
        if want is None:
            problems.append(f"shipped copy: {rel} has no pin in r_sync.json")
            continue
        try:
            got = sha256_norm(_load_json(path))
        except Exception as exc:
            problems.append(f"shipped copy: {rel} is missing or unreadable ({exc})")
            continue
        if got != want:
            problems.append(f"shipped copy: {rel} differs from its pin ({got} != {want}); stale or dehydrated build")
    return problems


def _staged_major(stage: Path, row: r_kb.AllowRow) -> int | None:
    try:
        data = _load_json(stage / VENDORED_DIR / row.name)
        return r_kb.version_major(data[row.version_key])
    except Exception:
        return None


# --------------------------------------------------------------------------
# checks 1 and 3: live files
# --------------------------------------------------------------------------
def _live_r_version(live: Path) -> str:
    try:
        info = _load_json(live / r_kb.VERSION_INFO_NAME)
        return str(info.get("version", "unknown")) if isinstance(info, dict) else "unknown"
    except Exception:
        return "unknown"


def check_live(live: Path, stage: Path, pin: dict) -> tuple[list[str], list[str]]:
    structural: list[str] = []
    drift: list[str] = []
    pinned = pin.get("files", {})
    target_of = {Path(t).name: t for t in RUNTIME_INPUTS.values()}

    missing_txt = live / "missing.txt"
    if missing_txt.is_file():
        for line in missing_txt.read_text(encoding="utf-8-sig").splitlines():
            name = line.strip()
            if name:
                structural.append(f"live: {name} could not be fetched (listed in missing.txt)")

    version = _live_r_version(live)
    for row in r_kb.ALLOW_LIST:
        if not row.override:
            continue
        path = live / row.name
        try:
            data = _load_json(path)
        except FileNotFoundError:
            structural.append(f"live: {row.name} is missing")
            continue
        except Exception as exc:
            structural.append(f"live: {row.name} is unreadable ({exc})")
            continue
        major = _staged_major(stage, row)
        if major is None:
            continue  # the shipped-copy check reports the staged file
        reason = r_kb.validate(row, data, major)
        if reason:
            structural.append(f"live: {row.name} fails its allow-list row: {reason}")
            continue
        got = sha256_norm(data)
        want = pinned.get(target_of.get(row.name, ""))
        if want is not None and got != want:
            drift.append(
                f"DRIFT: live {row.name} (R {version}) differs from the pin "
                f"(live {got}, pinned {want}); consider re-vendoring"
            )
    return structural, drift


# --------------------------------------------------------------------------
# --perms
# --------------------------------------------------------------------------
def _class_ok(mode3: str, owner: str, group: str, need: int) -> bool:
    """Kernel class precedence: owner shiny -> only the u bits; else group
    shiny -> only the g bits; else the o bits. Only the primary group is
    visible to `stat %G`: supplementary groups and ACLs are not modelled."""
    try:
        u, g, o = (int(c, 8) for c in mode3)
    except ValueError:
        return False
    bits = u if owner == SHINY_USER else g if group == SHINY_USER else o
    return bits & need == need


def _ancestors(path: str) -> list[str]:
    out: list[str] = []
    cur = posixpath.dirname(path.rstrip("/"))
    while cur and cur != "/":
        out.append(cur)
        parent = posixpath.dirname(cur)
        if parent == cur:   # "//" is its own dirname: stop at the fixed point
            break
        cur = parent
    out.append("/")
    return out


def check_perms(perms_text: str) -> list[str]:
    sudo: dict[str, str] = {}
    stats: dict[str, tuple[str, str, str]] = {}
    for raw in perms_text.splitlines():
        parts = raw.split()
        if not parts:
            continue
        if parts[0] == "sudo-test" and len(parts) >= 3:
            sudo[" ".join(parts[1:-1])] = parts[-1]
        elif parts[0] == "stat" and len(parts) >= 5:
            stats[" ".join(parts[4:])] = (parts[1][-3:], parts[2], parts[3])
    names = {row.name for row in r_kb.ALLOW_LIST if row.override}
    files = {p for p in (*sudo, *stats) if posixpath.basename(p) in names}
    problems: list[str] = []
    for name in sorted(names):
        if not any(posixpath.basename(p) == name for p in files):
            problems.append(f"perms: no permission line for {name}")
    for f in sorted(files):
        if f in sudo:
            if sudo[f] != "ok":
                problems.append(f"perms: user shiny cannot read {f} (sudo test: {sudo[f]})")
            continue
        mode, owner, group = stats[f]
        if not _class_ok(mode, owner, group, 4):
            problems.append(f"perms: user shiny cannot read {f} (mode {mode} {owner}:{group})")
        for d in _ancestors(f):
            if d not in stats:
                problems.append(f"perms: {f} has no stat line for parent directory {d}")
                continue
            dmode, downer, dgroup = stats[d]
            if not _class_ok(dmode, downer, dgroup, 1):
                problems.append(
                    f"perms: user shiny cannot traverse {d} (mode {dmode} {downer}:{dgroup}) for {f}"
                )
    return problems


# --------------------------------------------------------------------------
# --fetch
# --------------------------------------------------------------------------
class ConnectionFailed(Exception):
    pass


def _read_config_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m:
            val = m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                val = val[1:-1]
            out[m.group(1)] = val
    return out


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run `cmd`; stdout and stderr come back as str. Never the locale codec:
    stdout is decoded as utf-8-sig with replacement, as Registry._read_settings
    reads the settings file (a BOM is dropped, a stray byte cannot crash)."""
    try:
        cp = subprocess.run(cmd, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConnectionFailed(f"{' '.join(cmd)}: {exc}") from exc
    cp.stdout = (cp.stdout or b"").decode("utf-8-sig", errors="replace")
    cp.stderr = (cp.stderr or b"").decode("utf-8", errors="replace")
    return cp


def _conn_fail(cmd: list[str], cp: subprocess.CompletedProcess) -> ConnectionFailed:
    return ConnectionFailed(f"{' '.join(cmd)} exited {cp.returncode}: {(cp.stderr or '').strip()}")


SAFE_REMOTE = re.compile(r"^/[A-Za-z0-9._/@+-]+$")


def _valid_remote_dir(value: str) -> bool:
    return value.startswith("/") and not any(c in value for c in "\n\r\0")


def fetch(server: str, app_dir: str, tmp: Path) -> tuple[Path | None, list[str]]:
    """Fetch the override files into `tmp`. Returns (live dir or None when the
    override is off or unusable, structural problems). Writes tmp/perms.txt.
    Raises ConnectionFailed only for ssh/scp rc 255 (or ssh not runnable)."""
    problems: list[str] = []
    settings_path = posixpath.join(app_dir, r_kb.SETTINGS_FILE)
    q = shlex.quote(settings_path)
    # exit 3 = absent, 4 = present but unreadable, 255 = ssh itself failed
    cmd = ["ssh", "--", server, f"if [ -e {q} ]; then cat {q} || exit 4; else exit 3; fi"]
    cp = _run(cmd)
    if cp.returncode == 0:
        settings_text: str | None = cp.stdout
    elif cp.returncode == 3:
        settings_text = None  # absent: the default path the create step will write
    elif cp.returncode == 4:
        problems.append(f"live: {settings_path} exists but cannot be read; the override setting is unknown")
        return None, problems
    else:
        raise _conn_fail(cmd, cp)
    remote_dir = r_kb.override_dir_from({}, settings_text)
    if remote_dir is None:
        return None, problems
    if not _valid_remote_dir(remote_dir):
        problems.append(f"live: SESPY_R_DATA_DIR {remote_dir!r} is not an absolute single-line path")
        return None, problems

    live = tmp / ".live"
    live.mkdir(parents=True, exist_ok=True)
    rows = [r for r in r_kb.ALLOW_LIST if r.override]
    remote_files = [posixpath.join(remote_dir, r.name) for r in rows]
    missing: list[str] = []
    if not SAFE_REMOTE.match(remote_dir):
        # scp may hand the remote path to a shell (old protocol): never fetch an odd path
        problems.append(f"live: SESPY_R_DATA_DIR {remote_dir!r} has characters that are unsafe to fetch")
        missing = [r.name for r in rows]
    else:
        for row, remote in zip(rows, remote_files):
            cmd = ["scp", "-q", "--", f"{server}:{remote}", str(live / row.name)]
            cp = _run(cmd)
            if cp.returncode == 255:
                raise _conn_fail(cmd, cp)
            if cp.returncode != 0:  # absent or unreadable: a structural problem, not a connection one
                missing.append(row.name)
        version_remote = posixpath.join(posixpath.dirname(remote_dir.rstrip("/")), r_kb.VERSION_INFO_NAME)
        cmd = ["scp", "-q", "--", f"{server}:{version_remote}", str(live / r_kb.VERSION_INFO_NAME)]
        cp = _run(cmd)
        if cp.returncode == 255:
            raise _conn_fail(cmd, cp)
    if missing:
        (live / "missing.txt").write_text("\n".join(missing) + "\n", encoding="utf-8")

    paths: list[str] = []
    for f in remote_files:
        for p in (f, *_ancestors(f)):
            if p not in paths:
                paths.append(p)
    quoted = " ".join(shlex.quote(p) for p in paths)
    cmd = ["ssh", "--", server, f"stat -c 'stat %a %U %G %n' {quoted}"]
    cp = _run(cmd)
    if cp.returncode == 255:
        raise _conn_fail(cmd, cp)  # other nonzero: some path absent; its lines are simply missing
    (tmp / "perms.txt").write_text(cp.stdout, encoding="utf-8")
    return live, problems


# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Live reference-data pre-flight checker")
    ap.add_argument("--pin", type=Path, default=DEFAULT_PIN)
    ap.add_argument("--stage", type=Path, default=REPO_ROOT)
    ap.add_argument("--live", type=Path, default=None)
    ap.add_argument("--strict", action="store_true", help="drift exits 2")
    ap.add_argument("--warn-only", action="store_true", help="report everything, exit 0")
    ap.add_argument("--fetch", action="store_true", help="fetch the live files over ssh first")
    ap.add_argument("--server", default=None)
    ap.add_argument("--app-dir", default=None)
    ap.add_argument("--perms", type=Path, default=None)
    ap.add_argument("--print-override-names", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.print_override_names:
        for r in r_kb.ALLOW_LIST:
            if r.override:
                print(r.name)
        return 0

    tmp_ctx = None
    live: Path | None = args.live
    perms_file: Path | None = args.perms
    fetch_problems: list[str] = []
    if args.fetch:
        cfg = _read_config_env(REPO_ROOT / "deploy" / "config.env")
        server = args.server or cfg.get("DEPLOY_SERVER")
        app_dir = args.app_dir or cfg.get("DEPLOY_DIR")
        if not server or not app_dir:
            print("check_live: --fetch needs DEPLOY_SERVER/DEPLOY_DIR (deploy/config.env) "
                  "or --server/--app-dir", file=sys.stderr)
            return 2
        tmp_ctx = tempfile.TemporaryDirectory(prefix="check_live_")
        try:
            live, fetch_problems = fetch(server, app_dir, Path(tmp_ctx.name))
        except ConnectionFailed as exc:
            print(f"check_live: connection failed: {exc}", file=sys.stderr)
            tmp_ctx.cleanup()
            return 3
        if live is not None:
            perms_file = Path(tmp_ctx.name) / "perms.txt"

    try:
        try:
            pin = _load_json(args.pin)
        except (OSError, ValueError) as exc:
            print(f"STRUCTURAL: pin {args.pin} is missing or unreadable ({exc})")
            return 0 if args.warn_only else 2
        structural = check_shipped(args.stage, pin) + fetch_problems
        drift: list[str] = []
        if live is None:
            print("check_live: live override is off; live checks skipped")
        else:
            s, drift = check_live(live, args.stage, pin)
            structural += s
            if perms_file is not None:
                try:
                    structural += check_perms(perms_file.read_text(encoding="utf-8-sig"))
                except OSError as exc:
                    structural.append(f"perms: {perms_file} is unreadable ({exc})")
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()

    for line in structural:
        print(f"STRUCTURAL: {line}")
    if drift:
        print("=" * 72)
        for line in drift:
            print(line)
        print("=" * 72)
    if not structural and not drift:
        print("check_live: ok")

    if args.warn_only:
        return 0
    if structural or (drift and args.strict):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
