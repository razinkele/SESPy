"""Load real-world .qsem models through SESPy's QSEM importer and assert they
parse into a valid Project.

The models originate from the NiD4OCEAN DST "social ecological system map" set
and are vendored into this repo's data/ as sample fixtures, so the tests run
anywhere (CI, other machines). Point at a different model set with the
QSEM_MODELS_DIR environment variable.
"""
import json
import os
from pathlib import Path

import pytest

from sespy.qsem_import import parse_qsem, qsem_to_isa

# Repo-local sample models; override with QSEM_MODELS_DIR.
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data"


def _models_dir() -> Path:
    return Path(os.environ.get("QSEM_MODELS_DIR", _DEFAULT_DIR))


def _discover() -> list[Path]:
    d = _models_dir()
    return sorted(d.glob("*.qsem")) if d.is_dir() else []


_MODELS = _discover()

pytestmark = pytest.mark.skipif(
    not _MODELS,
    reason=f"no .qsem models found in {_models_dir()} (set QSEM_MODELS_DIR)",
)


@pytest.mark.parametrize("path", _MODELS, ids=lambda p: p.name)
def test_qsem_model_parses_to_valid_project(path):
    """Each real model file parses without validation errors."""
    result = parse_qsem(path)
    assert result.valid, f"{path.name} failed to validate: {result.errors}"
    assert result.project is not None


@pytest.mark.parametrize("path", _MODELS, ids=lambda p: p.name)
def test_qsem_model_maps_nodes_and_links_soundly(path):
    """The pure QSEM->ISA map yields a self-consistent graph: at least one
    element, ghost nodes skipped (elements never exceed raw nodes), and every
    connection references real, distinct element ids (no dangling/self-loops)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data.get("canvas", {}).get("nodes", [])
    elements, connections = qsem_to_isa(data)

    assert elements, f"{path.name}: expected at least one element"
    # Ghost nodes are skipped, so mapped elements never exceed raw node count.
    assert len(elements) <= len(nodes)

    element_ids = {e.id for e in elements}
    for c in connections:
        assert c.source in element_ids, f"{path.name}: dangling source {c.source}"
        assert c.target in element_ids, f"{path.name}: dangling target {c.target}"
        assert c.source != c.target, f"{path.name}: self-loop {c.source}"
        assert c.polarity in ("+", "-")
        assert c.strength in ("weak", "medium", "strong")
        assert c.delay in ("immediate", "short", "long")
