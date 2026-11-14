"""K1 Task 18 -- MosaicSES compatibility contract.

On the server MosaicSES symlinks SESPy's ``sespy/`` package, so a SESPy change
can break MosaicSES without any SESPy test noticing. These tests run the calls
MosaicSES really makes (re-located by content in the MosaicSES checkout), in
exactly its form: the optional ``snapshot=`` / ``include_regional_context=``
keywords K1 added to some modules are never passed.

MosaicSES call sites (at MosaicSES 1b71423):
  multises_app/modules/compartments.py  -- module ``*_server(id, project_data=
      state.active_compartment_project, event_bus=state.event_bus[, translator=
      translator])``; ``translator`` is ``Translator | None`` (None when the
      caller supplies none); ``*_ui(id)``.
  multises_app/modules/project_setup.py -- ``get_regional_seas()`` then
      ``data.get("name", slug)`` per sea.
  multises/archetypes.py, multises_app/state.py -- ``ProjectMetadata.new(...)``.
  multises/bowtie_bridge.py -- ``ProjectMetadata(name=..., description=...)``.
  multises/data_structure.py -- ``c.project.to_dict()``, ``Project.from_dict(raw)``.
"""
from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest
from shiny import reactive
from shiny.testserver import test_server

from sespy.data_structure import IsaData, Project, ProjectMetadata
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.regional_seas import get_regional_seas

ROOT = Path(__file__).resolve().parents[1]

# Every (module, name) MosaicSES imports from sespy, hard-coded so the list
# cannot silently go stale: test_mosaic_import_surface re-derives it from the
# MosaicSES checkout when one is available and fails on any name missing here.
_SERVER_UI = [
    ("analysis_bot", "analysis_bot"),
    ("analysis_boolean", "analysis_boolean"),
    ("analysis_intervention", "analysis_intervention"),
    ("analysis_leverage", "analysis_leverage"),
    ("analysis_loops", "analysis_loops"),
    ("analysis_metrics", "analysis_metrics"),
    ("analysis_simplify", "analysis_simplify"),
    ("analysis_simulation", "analysis_simulation"),
]
MOSAIC_IMPORTS: set[tuple[str, str]] = {
    ("sespy.autosave", "token_key"),
    ("sespy.autosave", "valid_token"),
    ("sespy.regional_seas", "get_regional_seas"),
    ("sespy.constants", "DA_SITES"),
    ("sespy.constants", "SPATIAL_SCALES"),
    ("sespy.constants", "TEMPORAL_SCALES"),
    ("sespy.constants", "ELEMENT_ID_PREFIX"),
    ("sespy.dashboard", "NavItem"),
    ("sespy.dashboard", "StepperItem"),
    ("sespy.data_structure", "Connection"),
    ("sespy.data_structure", "Element"),
    ("sespy.data_structure", "IsaData"),
    ("sespy.data_structure", "Project"),
    ("sespy.data_structure", "ProjectMetadata"),
    ("sespy.event_bus", "EventBus"),
    ("sespy.event_bus", "create_event_bus"),
    ("sespy.i18n", "Translator"),
    ("sespy.utils", "next_id"),
    ("sespy.network", "remove_nodes"),
    ("sespy.network", "CENTRALITY_METRICS"),
    ("sespy.network", "centrality_metrics"),
    ("sespy.network", "leverage_scores"),
    ("sespy.network", "to_digraph"),
    ("sespy.modules.cld_visualization", "cld_viz_server"),
    ("sespy.modules.cld_visualization", "cld_viz_ui"),
    ("sespy.modules.isa_data_entry", "isa_data_entry_server"),
    ("sespy.modules.isa_data_entry", "isa_data_entry_ui"),
    *(
        (f"sespy.modules.{m}", f"{p}_{kind}")
        for m, p in _SERVER_UI
        for kind in ("server", "ui")
    ),
}


def _mosaic_checkout() -> Path | None:
    """SESPY_MOSAIC_CHECKOUT, else <repo>/../MosaicSES, else the main
    checkout's sibling (this repo may be a git worktree)."""
    env = os.environ.get("SESPY_MOSAIC_CHECKOUT")
    cands = [Path(env)] if env else []
    cands.append(ROOT.parent / "MosaicSES")
    try:
        common = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute",
             "--git-common-dir"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
        cands.append(Path(common).parent.parent / "MosaicSES")
    except (OSError, subprocess.SubprocessError):
        pass
    for c in cands:
        if (c / "multises_app").is_dir() and (c / "multises").is_dir():
            return c
    return None


def _derive_imports(checkout: Path) -> tuple[set[tuple[str, str]], list[Path]]:
    found: set[tuple[str, str]] = set()
    files: list[Path] = []
    for pkg in ("multises", "multises_app"):
        for f in (checkout / pkg).rglob("*.py"):
            files.append(f)
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0 \
                        and (node.module or "").split(".")[0] == "sespy":
                    found.update((node.module, a.name) for a in node.names)
    return found, files


# ---------------------------------------------------------------- module calls
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))


@pytest.mark.parametrize("translator", [None, TR], ids=["translator-None", "translator-set"])
def test_isa_data_entry_mosaic_call(translator):
    """compartments.py: isa_data_entry_server("entry", project_data=...,
    event_bus=..., translator=translator) and cld_viz_server("cld", ...)."""
    from sespy.modules.cld_visualization import cld_viz_server
    from sespy.modules.isa_data_entry import isa_data_entry_server

    def server(input, output, session):
        rv = reactive.value(Project(ProjectMetadata(name="mosaic"), IsaData()))
        bus = create_event_bus()
        isa_data_entry_server("entry", project_data=rv, event_bus=bus,
                              translator=translator)
        cld_viz_server("cld", project_data=rv, event_bus=bus)

    with test_server(server, timeout_secs=90) as ts:
        entry = ts.make_scope("entry")
        for out_id in ("status_line", "elements_table", "connections_table"):
            out = entry.get_output(out_id)
            assert out.status == "ok", (out_id, out.status, out.error)
        cld = ts.make_scope("cld")
        cld.set_inputs(element_types=[])  # the filter input is client-set
        out = cld.get_output("stat_nodes")
        assert out.status == "ok", (out.status, out.error)


def test_all_embedded_modules_mount_in_mosaic_form():
    """Every sespy module compartments.py mounts, with the exact keyword set
    it passes (translator omitted for loops, as in MosaicSES)."""
    import importlib

    def server(input, output, session):
        rv = reactive.value(Project(ProjectMetadata(name="mosaic"), IsaData()))
        bus = create_event_bus()
        for modname, prefix in _SERVER_UI:
            fn = getattr(importlib.import_module(f"sespy.modules.{modname}"),
                         f"{prefix}_server")
            kw = {"project_data": rv, "event_bus": bus}
            if modname != "analysis_loops":
                kw["translator"] = TR
            fn(prefix.removeprefix("analysis_"), **kw)

    with test_server(server, timeout_secs=90):
        pass  # mounting + the initial flush must not raise


def test_module_ui_calls_take_an_id():
    from sespy.modules.cld_visualization import cld_viz_ui
    from sespy.modules.isa_data_entry import isa_data_entry_ui

    assert str(isa_data_entry_ui("entry"))
    assert str(cld_viz_ui("cld"))
    import importlib
    for modname, prefix in _SERVER_UI:
        fn = getattr(importlib.import_module(f"sespy.modules.{modname}"), f"{prefix}_ui")
        assert str(fn(prefix.removeprefix("analysis_")))


# ------------------------------------------------------------ plain functions
def test_plain_function_calls_bind():
    p = Project(ProjectMetadata.new("x"), IsaData())
    inspect.signature(Project.to_dict).bind(p)            # c.project.to_dict()
    inspect.signature(Project.from_dict).bind({})         # Project.from_dict(raw)
    inspect.signature(ProjectMetadata).bind(name="n", description="d")
    inspect.signature(ProjectMetadata.new).bind(name="n")
    inspect.signature(ProjectMetadata.new).bind("n")
    inspect.signature(get_regional_seas).bind()
    inspect.signature(Project).bind(metadata=p.metadata, isa_data=p.isa_data)
    # ...and they actually run, round-tripping.
    d = p.to_dict()
    assert Project.from_dict(d).metadata.name == "x"
    assert ProjectMetadata(name="n", description="d").description == "d"


def test_regional_seas_shape():
    seas = get_regional_seas()
    assert seas
    for slug, sea in seas.items():
        for key in ("name", "ecosystem_types", "common_issues"):
            assert key in sea, f"{slug} lacks {key}"
        assert isinstance(sea.get("name", slug), str)   # project_setup.py reads it


# ------------------------------------------------------------- import surface
def test_mosaic_import_surface():
    import importlib

    for module, name in sorted(MOSAIC_IMPORTS):
        assert hasattr(importlib.import_module(module), name), f"{module}.{name}"

    checkout = _mosaic_checkout()
    if checkout is None:
        pytest.skip("no MosaicSES checkout; hard-coded list verified only")
    derived, _ = _derive_imports(checkout)
    assert derived, "derivation found no sespy imports; the regex/AST is stale"
    missing = derived - MOSAIC_IMPORTS
    assert not missing, f"MosaicSES imports not in the hard-coded list: {sorted(missing)}"


def test_mosaic_does_not_mount_the_ai_isa_wizard():
    """K1 changed the wizard's row ids (entry_{gen}_{target}_{i}) and country
    step; MosaicSES must not depend on it."""
    assert not [m for m, _ in MOSAIC_IMPORTS if "ai_isa_wizard" in m]
    checkout = _mosaic_checkout()
    if checkout is None:
        pytest.skip("no MosaicSES checkout")
    derived, files = _derive_imports(checkout)
    assert not [m for m, _ in derived if "wizard" in m]
    for f in files:
        assert "ai_isa_wizard" not in f.read_text(encoding="utf-8"), f


# ------------------------------------------------------------------- r_kb
def test_r_kb_imports_from_repo_under_test(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    out = subprocess.run(
        [sys.executable, "-c",
         "import sespy, sespy.r_kb; print(sespy.__file__)"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300,
    )
    assert out.returncode == 0, out.stderr
    printed = Path(out.stdout.strip().splitlines()[-1]).resolve()
    assert ROOT.resolve() in printed.parents, printed
