#!/usr/bin/env python
"""Orchestrate SESPy's standalone Playwright e2e scripts against a live app.

Each `tests/test_*_e2e.py` (plus the burger/stepper server scripts) is a
self-contained `asyncio.run(main())` script that drives the app's DOM over
http://127.0.0.1:<port> and `assert`s on it (so a failure exits non-zero).
This runner boots `shiny run`, runs every such script, and reports pass/fail —
exiting non-zero if any fail.

It handles the one env-sensitive script, `test_wizard_e2e.py`, which needs a
two-pass split around `ANTHROPIC_API_KEY` (the SP4 Claude-backend button):
  * pass 1 (`--mode=no-key`)   — server launched WITHOUT the key (button hidden)
  * pass 2 (`--mode=fake-key`) — server launched WITH a fake key (consent +
    auth-error fallback path); the fake key is rejected by the API, so no cost.

Requires the full-app environment (incl. the pyvis fork providing `pyvis.shiny`)
and `playwright install chromium`.

Usage:  python tests/run_e2e.py [--port 8000]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
SERVER_READY_TIMEOUT = 90      # seconds to wait for shiny run to serve
SCRIPT_TIMEOUT = 300           # per-script wall-clock cap

# `test_topbar_e2e.py` submits feedback through the UI. Without an override that
# lands in the real store (`sespy/logs/feedback.db`), which deploy.sh preserves
# across deploys — so every run buried genuine reports under test rows. Point
# the whole suite at a throwaway DB instead; `feedback_store` reads this env var.
E2E_FEEDBACK_DB = Path(tempfile.gettempdir()) / "sespy-e2e-feedback.db"

# Server scripts that don't follow the *_e2e.py naming but still drive a browser.
_EXTRA_SERVER_SCRIPTS = ("test_burger.py", "test_stepper.py", "test_stepper_click.py")
_WIZARD = TESTS / "test_wizard_e2e.py"


def discover_scripts() -> list[Path]:
    """All standalone browser scripts EXCEPT the wizard (run separately by mode)."""
    scripts = sorted(TESTS.glob("test_*_e2e.py"))
    scripts += [TESTS / n for n in _EXTRA_SERVER_SCRIPTS if (TESTS / n).exists()]
    return [p for p in scripts if p != _WIZARD]


def _child_env(extra: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)   # start from a clean slate every launch
    env.update(extra)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["SESPY_FEEDBACK_DB"] = str(E2E_FEEDBACK_DB)
    return env


def wait_ready(url: str, timeout: int = SERVER_READY_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def start_server(port: int, env_extra: dict[str, str]) -> subprocess.Popen:
    shiny = shutil.which("shiny") or "shiny"
    return subprocess.Popen(
        [shiny, "run", "--port", str(port), "app.py"],
        cwd=str(ROOT), env=_child_env(env_extra),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def run_script(script: Path, args: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT), env=_child_env({}),
        capture_output=True, text=True, timeout=SCRIPT_TIMEOUT,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    port = ap.parse_args().port
    url = f"http://127.0.0.1:{port}/"

    # Start each run from an empty throwaway store (WAL sidecars included) so the
    # topbar roundtrip assertion never sees rows left over from an earlier run.
    for suffix in ("", "-wal", "-shm"):
        stale = Path(str(E2E_FEEDBACK_DB) + suffix)
        if stale.exists():
            stale.unlink()

    results: list[tuple[str, bool, subprocess.CompletedProcess]] = []

    def _run_once(script: Path, args: tuple[str, ...]):
        try:
            r = run_script(script, args)
            return r.returncode == 0, r
        except subprocess.TimeoutExpired as e:
            return False, subprocess.CompletedProcess(
                e.cmd, 1, e.stdout or "", f"TIMEOUT after {SCRIPT_TIMEOUT}s"
            )

    def run_against(label_args, server) -> None:
        for script, args, label in label_args:
            ok, r = _run_once(script, args)
            tag = "PASS"
            if not ok:
                # Retry once. Browser e2e against a live server has inherent
                # render/timing variance (esp. across machines/CI); a second
                # attempt separates transient flakes from genuine failures.
                # A retry-pass is flagged so flakiness stays visible.
                ok, r2 = _run_once(script, args)
                r = r2
                tag = "PASS (retry)"
            results.append((label, ok, r))
            print(f"  [{tag if ok else 'FAIL'}] {label}", flush=True)

    # ---- Phase 1: no ANTHROPIC_API_KEY ----
    print(f"\n=== Phase 1 (no key): {len(discover_scripts())} scripts + wizard no-key ===", flush=True)
    proc = start_server(port, {})
    try:
        if not wait_ready(url):
            print("::error::server (no-key) did not become ready", flush=True)
            return 1
        batch = [(s, (), s.name) for s in discover_scripts()]
        if _WIZARD.exists():
            batch.append((_WIZARD, ("--mode=no-key",), "test_wizard_e2e.py --mode=no-key"))
        run_against(batch, proc)
    finally:
        stop_server(proc)

    # ---- Phase 2: fake key (wizard consent/auth path) ----
    if _WIZARD.exists():
        print("\n=== Phase 2 (fake key): wizard fake-key ===", flush=True)
        proc = start_server(port, {"ANTHROPIC_API_KEY": "test-fake-key"})
        try:
            if not wait_ready(url):
                print("::error::server (fake-key) did not become ready", flush=True)
                return 1
            run_against([(_WIZARD, ("--mode=fake-key",), "test_wizard_e2e.py --mode=fake-key")], proc)
        finally:
            stop_server(proc)

    # ---- Summary ----
    fails = [(label, r) for label, ok, r in results if not ok]
    print(f"\n{len(results) - len(fails)}/{len(results)} e2e scripts passed, {len(fails)} failed", flush=True)
    for label, r in fails:
        print(f"\n===== FAIL: {label} =====")
        out = (r.stdout or "").strip().splitlines()
        err = (r.stderr or "").strip().splitlines()
        if out:
            print("stdout tail:\n  " + "\n  ".join(out[-15:]))
        if err:
            print("stderr tail:\n  " + "\n  ".join(err[-25:]))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
