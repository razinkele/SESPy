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
    env["SHINY_TESTMODE"] = "1"   # 1.7.0: serve /session/{id}/dataobj/shinytest
    # _child_env is used for both the app server and the Playwright client
    # scripts, so SHINY_TESTMODE also reaches those client processes; it is
    # a no-op there (only the Shiny server side reads it) and harmless.
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


def port_busy(url: str) -> bool:
    """True if something is already serving here — it is not ours.

    A surviving server from an earlier run answers instantly, and wait_ready()
    would happily connect to it: the gate would then test that orphan's code,
    not this tree. Checked before each phase's launch, because the documented
    failure is a Phase-1 server outliving stop_server and stealing Phase 2.
    """
    try:
        urllib.request.urlopen(url, timeout=2)
    except Exception:
        return False
    return True


def warm_session(url: str, timeout_ms: int = 90_000) -> bool:
    """Open one real browser session so the server pays its first-flush cost here.

    wait_ready() only proves the HTTP handler answers. The sidebar nav is a
    @render.ui output (`sespy_nav_render`, sespy/dashboard.py) that exists only
    after a session's first flush, and the first session on a cold server also
    pays every lazy import session-scoped code triggers. Without this the first
    script in the batch absorbs that cost.

    Bounded and non-fatal: if the nav never renders we say so and let the
    scripts' own 60 s waits report the real failure with their own diagnostics.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(f"  [warm] skipped, playwright unavailable: {exc}", flush=True)
        return False
    t0 = time.monotonic()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_context().new_page()
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_selector(".sespy-nav-btn", timeout=timeout_ms)
                page.wait_for_selector(".sespy-stepper-item", timeout=timeout_ms)
            finally:
                browser.close()
    except Exception as exc:
        print(f"  [warm] first session never rendered the nav in "
              f"{timeout_ms // 1000}s: {exc}", flush=True)
        return False
    print(f"  [warm] nav rendered in {time.monotonic() - t0:.1f}s", flush=True)
    return True


def start_server(port: int, env_extra: dict[str, str]) -> subprocess.Popen:
    # Run the server through the interpreter, NOT the `shiny` console-script
    # launcher. On Windows that launcher is a stub .exe that spawns python as a
    # child: stop_server() terminated only the stub, the real server survived
    # on the port, the next phase's server failed to bind, and wait_ready()
    # happily connected to the orphan — Phase 2 then ran its fake-key wizard
    # against the no-key server and failed at case 8 ("button missing").
    return subprocess.Popen(
        [sys.executable, "-m", "shiny", "run", "--port", str(port), "app.py"],
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


def _txt(v: object) -> str:
    """Decode a TimeoutExpired stream, which may be bytes even in text mode."""
    if v is None:
        return ""
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)


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

    # Every e2e script hardcodes http://127.0.0.1:8000 (none reads an env var
    # for it), so --port only ever moved the SERVER, never the clients: a
    # non-default port boots a server nothing talks to while the scripts drive
    # whatever is on 8000.
    if port != 8000:
        print("::error::--port is not wired through: tests/test_*_e2e.py hardcode "
              "http://127.0.0.1:8000. Free port 8000 and rerun without --port.",
              flush=True)
        return 1

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
            # Keep what the script actually produced. Discarding e.stderr meant
            # a 300 s hang reported only "TIMEOUT": no partial diagnostics.
            # _txt is load-bearing, not defensive: on POSIX (where CI runs this)
            # CPython builds TimeoutExpired from the raw accumulated chunks, so
            # both streams are BYTES even under text=True; only Windows re-reads
            # and decodes the pipes after the kill. Storing bytes here made the
            # summary's "\n  ".join(...) raise TypeError and abort the report.
            return False, subprocess.CompletedProcess(
                e.cmd, 1, _txt(e.stdout),
                # The marker goes LAST so the 25-line stderr tail keeps it.
                (_txt(e.stderr).rstrip() + f"\nTIMEOUT after {SCRIPT_TIMEOUT}s").lstrip(),
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
                first = r
                ok, r = _run_once(script, args)
                tag = "PASS (retry)"
                if ok:
                    # Attempt 1's output is otherwise dropped (only failures
                    # reach the FAIL block below), so a retry-pass is a flake
                    # with no evidence. Print enough to tell a cold-start
                    # timeout from a real assertion failure. 25 stderr lines
                    # matches the FAIL block's tail: a Playwright TimeoutError
                    # puts its "Call log:" AFTER the exception line.
                    err = (first.stderr or "").strip().splitlines()
                    out = (first.stdout or "").strip().splitlines()
                    print(f"    {label}: attempt 1 failed, retry passed", flush=True)
                    print("    attempt 1 stderr tail:\n      "
                          + "\n      ".join(err[-25:] or ["(no stderr)"]), flush=True)
                    # Not joined: on a TIMEOUT, first.stdout is forwarded from
                    # TimeoutExpired and can be bytes on POSIX.
                    print(f"    attempt 1 last stdout: {out[-1] if out else '(no stdout)'}",
                          flush=True)
            results.append((label, ok, r))
            print(f"  [{tag if ok else 'FAIL'}] {label}", flush=True)

    # ---- Phase 1: no ANTHROPIC_API_KEY ----
    print(f"\n=== Phase 1 (no key): {len(discover_scripts())} scripts + wizard no-key ===", flush=True)
    if port_busy(url):
        print(f"::error::something is already listening on {url} -- kill it first "
              "(the runner would otherwise gate on that orphan, not this tree).",
              flush=True)
        return 1
    proc = start_server(port, {})
    try:
        if not wait_ready(url):
            print("::error::server (no-key) did not become ready", flush=True)
            return 1
        warm_session(url)
        batch = [(s, (), s.name) for s in discover_scripts()]
        if _WIZARD.exists():
            batch.append((_WIZARD, ("--mode=no-key",), "test_wizard_e2e.py --mode=no-key"))
        run_against(batch, proc)
    finally:
        stop_server(proc)

    # ---- Phase 2: fake key (wizard consent/auth path) ----
    if _WIZARD.exists():
        print("\n=== Phase 2 (fake key): wizard fake-key ===", flush=True)
        # Phase 1's server was just stopped, and its listening socket can take a
        # moment to go away — so wait for the port rather than erroring on our
        # own teardown. Only a server that outlives this window is an orphan.
        for _ in range(15):
            if not port_busy(url):
                break
            time.sleep(1)
        else:
            print(f"::error::{url} still busy after Phase 1 teardown -- a server "
                  "survived stop_server; kill it, or Phase 2 would run against it.",
                  flush=True)
            return 1
        proc = start_server(port, {"ANTHROPIC_API_KEY": "test-fake-key"})
        try:
            if not wait_ready(url):
                print("::error::server (fake-key) did not become ready", flush=True)
                return 1
            warm_session(url)
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
