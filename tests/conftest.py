"""Opt-in Shiny-free gate: with SESPY_BLOCK_UI=1, importing shiny, htmltools
or pyvis raises ModuleNotFoundError("blocked: <name>"). Otherwise a no-op."""
import importlib.util
import os
from pathlib import Path

if os.environ.get("SESPY_BLOCK_UI") == "1":
    _path = Path(__file__).resolve().parent / "_ui_blocker.py"
    _spec = importlib.util.spec_from_file_location("_sespy_ui_blocker", _path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _mod.install()
