from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _entries():
    lines = (ROOT / "tests" / "library_tests.txt").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]

def test_every_entry_exists():
    missing = [e for e in _entries() if not (ROOT / e).exists()]
    assert missing == []

def test_blocker_blocks_shiny_in_a_child_run():
    # A throwaway test that imports shiny must fail under the runner's env.
    # The probe lives under tests/ so that tests/conftest.py (which installs
    # the blocker) applies to it; it is always deleted afterwards.
    import os
    import subprocess
    import sys
    probe = ROOT / "tests" / "test__split_probe_tmp.py"
    probe.write_text("def test_p():\n    import shiny\n", encoding="utf-8")
    try:
        env = {**os.environ, "SESPY_BLOCK_UI": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(probe)],
                           env=env, capture_output=True, text=True, cwd=ROOT)
    finally:
        probe.unlink(missing_ok=True)
    assert r.returncode != 0 and "blocked: shiny" in r.stdout
