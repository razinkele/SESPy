"""Every sespy module must import, and must not source, deprecated Shiny APIs.

Shiny deprecates APIs one minor release before removing them; a warning at
import time is the earliest, cheapest signal that an upgrade will break the
app. This guard uses two mechanisms, each covering a different slice:

1. Fresh-interpreter import-time check. Decorators such as @render.download
   warn when *instantiated*. A module-level decorator use would trigger this
   on the module's very first import. This has to run in a *subprocess*: under
   the full test suite, every sespy submodule is already sitting in
   sys.modules by the time this test runs (18+ other test files import them
   at collection), so a plain `importlib.import_module` in-process would just
   return the cached module object and re-execute nothing — the decorator
   would never re-run and the check could never fail. Running in a fresh
   `sys.executable` subprocess guarantees a clean sys.modules. This check
   covers a module-level deprecated Shiny API call; it does NOT cover a
   deprecated call that only executes inside a function body invoked later
   (e.g. per-session, inside a @module.server callback) — importing the
   module doesn't call that function.

2. Static source scan. sespy's four @render.download sites are inside
   @module.server-decorated functions (report_export, project_io,
   pims_stakeholders, analysis_bot) — those function bodies only execute
   per-session, when a server callback runs, not at import — so mechanism
   (1) cannot see them at all. Instead we grep every sespy .py file's source
   text for the literal `render.download(` call (trailing paren, so
   `render.download_button(` does not match) and fail if found. This is
   what actually goes red on the four modules above and green once they are
   migrated to `render.download_button`; it only catches a reappearance of
   this exact deprecated call, not other deprecated APIs.

Together: (1) catches a module-level deprecation at the next Shiny upgrade;
(2) catches this specific deprecated call anywhere, including inside a
server-scoped function. Neither, alone or together, is a general-purpose
runtime guard against every possible future Shiny deprecation that only
fires inside a module's server function — that would need a harness that
actually instantiates each @module.server callback (e.g. a mock session),
which is out of scope here.
"""
from __future__ import annotations

import pkgutil
import re
import subprocess
import sys
from pathlib import Path

import pytest

import sespy

_DEPRECATED_CALL_RE = re.compile(r"\brender\.download\(")
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _module_names() -> list[str]:
    names = []
    for info in pkgutil.walk_packages(sespy.__path__, prefix="sespy."):
        names.append(info.name)
    return sorted(names)


def _module_files() -> list[Path]:
    root = Path(sespy.__file__).parent
    files = list(root.rglob("*.py"))
    app_py = _REPO_ROOT / "app.py"
    if app_py.exists():
        files.append(app_py)
    return sorted(files)


def test_fresh_interpreter_imports_without_shiny_deprecation():
    """Import every sespy module in a brand-new interpreter and fail if any
    of them raises ShinyDeprecationWarning-as-error.

    Must run out-of-process: see module docstring mechanism (1). The
    subprocess inherits this process's environment (PATH etc. set up by the
    active micromamba env), so `sys.executable` resolves the same
    interpreter/env this test itself runs under.
    """
    names = _module_names()
    script = (
        "import warnings, importlib, sys\n"
        "from shiny._deprecated import ShinyDeprecationWarning\n"
        "warnings.filterwarnings('error', category=ShinyDeprecationWarning)\n"
        f"names = {names!r}\n"
        "deprecations = []\n"
        "import_errors = []\n"
        "for n in names:\n"
        "    try:\n"
        "        importlib.import_module(n)\n"
        "    except ShinyDeprecationWarning as e:\n"
        "        deprecations.append((n, str(e)))\n"
        "    except ImportError as e:\n"
        "        import_errors.append((n, str(e)))\n"
        "if deprecations or import_errors:\n"
        "    for n, msg in import_errors:\n"
        "        print(f'IMPORT-ERROR {n}: {msg}', file=sys.stderr)\n"
        "    for n, msg in deprecations:\n"
        "        print(f'DEPRECATION {n}: {msg}', file=sys.stderr)\n"
        "    sys.exit(1)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    has_import_error = "IMPORT-ERROR" in result.stderr
    has_deprecation = "DEPRECATION" in result.stderr
    if has_import_error and not has_deprecation:
        reason = "one or more sespy modules failed to import (missing optional dependency?)"
    elif has_deprecation and not has_import_error:
        reason = "one or more sespy modules raised ShinyDeprecationWarning while importing"
    else:
        reason = (
            "one or more sespy modules failed to import (missing optional "
            "dependency?) and/or raised ShinyDeprecationWarning while importing"
        )
    assert result.returncode == 0, (
        f"a fresh interpreter reported: {reason} (see mechanism 1 in this "
        f"file's docstring):\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.parametrize(
    "path", _module_files(), ids=lambda p: p.relative_to(_REPO_ROOT).as_posix()
)
def test_module_source_has_no_deprecated_render_download_call(path):
    src = path.read_text(encoding="utf-8")
    assert not _DEPRECATED_CALL_RE.search(src), (
        f"{path} still calls the deprecated render.download(...) — "
        "use render.download_button(...) instead"
    )
