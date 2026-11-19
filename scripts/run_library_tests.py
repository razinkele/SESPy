"""Run the library-side unit suite with shiny/htmltools/pyvis blocked."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "library_tests.txt"


def _paths() -> list[str]:
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def main(argv: list[str] | None = None) -> int:
    extra = list(sys.argv[1:] if argv is None else argv)
    env = {
        **os.environ,
        "SESPY_BLOCK_UI": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        # an editable sespy install may point at another checkout
        "PYTHONPATH": os.pathsep.join(
            [str(ROOT)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])
        ),
    }
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *_paths(), *extra]
    return subprocess.run(cmd, env=env, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
