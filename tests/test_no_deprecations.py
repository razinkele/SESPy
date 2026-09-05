"""Every sespy module must import, and must not source, deprecated Shiny APIs.

Shiny deprecates APIs one minor release before removing them; a warning at
import time is the earliest, cheapest signal that an upgrade will break the
app. This guard uses two mechanisms:

1. Import-time warning capture. Decorators such as @render.download warn
   when *instantiated*. For a module-level decorator that runs at import
   time, this alone would be enough. In sespy, however, the four
   @render.download sites live inside @module.server-decorated functions
   (report_export, project_io, pims_stakeholders, analysis_bot) — those
   function bodies only execute per-session, when a server callback runs,
   not at import. So a plain `importlib.import_module` never instantiates
   the decorator and never triggers the warning. This test is kept because
   it is cheap and does catch a *module-level* deprecated-API use, but it
   cannot by itself catch a deprecation nested inside a server function.

2. Static source scan. Because (1) is blind to server-scoped decorators,
   we also grep every sespy .py file's source text for the literal
   `render.download(` call (trailing paren, so `render.download_button(`
   does not match) and fail if found. This is what actually goes red on
   the four modules above and green once they are migrated to
   `render.download_button`.
"""
from __future__ import annotations

import importlib
import pkgutil
import re
import warnings
from pathlib import Path

import pytest
from shiny._deprecated import ShinyDeprecationWarning

import sespy

_DEPRECATED_CALL_RE = re.compile(r"\brender\.download\(")


def _module_names() -> list[str]:
    names = []
    for info in pkgutil.walk_packages(sespy.__path__, prefix="sespy."):
        names.append(info.name)
    return sorted(names)


def _module_files() -> list[Path]:
    root = Path(sespy.__file__).parent
    return sorted(root.rglob("*.py"))


@pytest.mark.parametrize("name", _module_names())
def test_module_imports_without_shiny_deprecation(name):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ShinyDeprecationWarning)
        importlib.import_module(name)
    deprecations = [w for w in caught if issubclass(w.category, ShinyDeprecationWarning)]
    assert not deprecations, [str(w.message) for w in deprecations]


@pytest.mark.parametrize("path", _module_files(), ids=lambda p: str(p))
def test_module_source_has_no_deprecated_render_download_call(path):
    src = path.read_text(encoding="utf-8")
    assert not _DEPRECATED_CALL_RE.search(src), (
        f"{path} still calls the deprecated render.download(...) — "
        "use render.download_button(...) instead"
    )
