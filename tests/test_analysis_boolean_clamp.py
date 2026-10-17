"""P1a — the Boolean module clamps max_nodes to its UI range on the server
(spec §7). tests/test_dynamics.py stays Shiny-free, so this lives here."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from shiny import reactive
from shiny.testserver import test_server

from sespy import dynamics
from sespy.data_structure import Project
from sespy.event_bus import create_event_bus
from sespy.modules.analysis_boolean import analysis_boolean_server

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_ses.json"


@pytest.mark.parametrize("ui_value,want", [(50, 12), (2, 4), (8, 8), ("junk", 12)])
def test_boolean_module_clamps_max_nodes_to_ui_range(monkeypatch, ui_value, want):
    seen: list[int] = []
    real = dynamics.boolean_attractors

    def spy(rules, max_nodes=12, **kw):
        seen.append(max_nodes)
        return real(rules, max_nodes=max_nodes, **kw)

    monkeypatch.setattr(dynamics, "boolean_attractors", spy)
    project = Project.from_dict(json.loads(SAMPLE.read_text(encoding="utf-8")))

    def server(input, output, session):
        analysis_boolean_server("boolean", project_data=reactive.value(project),
                                event_bus=create_event_bus())

    with test_server(server) as ts:
        scope = ts.make_scope("boolean")
        # Action buttons ignore their initial value: set 0, then 1.
        scope.set_inputs(direction="cols", max_nodes=ui_value, run_boolean=0)
        scope.set_inputs(run_boolean=1)
    assert seen == [want]
