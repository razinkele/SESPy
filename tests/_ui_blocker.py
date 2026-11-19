"""Import blocker for the Shiny-free library gate (SESPY_BLOCK_UI=1).

Loaded by file path from tests/conftest.py (and exec-able by path from a
child-process test); never import it as ``tests._ui_blocker``.
"""
import sys

BLOCKED = ("shiny", "htmltools", "pyvis")


class _UiBlocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            top = name.split(".")[0]
            raise ModuleNotFoundError(f"blocked: {top}", name=top)
        return None


def install():
    for mod in [m for m in sys.modules if m.split(".")[0] in BLOCKED]:
        del sys.modules[mod]
    if not any(isinstance(f, _UiBlocker) for f in sys.meta_path):
        sys.meta_path.insert(0, _UiBlocker())
