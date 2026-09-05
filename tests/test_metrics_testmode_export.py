"""analysis_metrics exposes the cascade result to Shiny test mode (1.7.0)."""
import pytest

# analysis_metrics imports the pyvis fork (`pyvis.shiny`) at module load, so
# skip this module when the fork is absent (e.g. the stock-pyvis unit-CI
# job). It runs for real in the conda full-app/e2e jobs where the fork is
# installed.
pytest.importorskip("pyvis.shiny")

from sespy.modules import analysis_metrics


def test_cascade_snapshot_value_passes_dict_through():
    r = {"steps": [{"step": 1, "removed_id": "MPF1"}], "cascade_threshold_node": "MPF1"}
    assert analysis_metrics.cascade_snapshot_value(r) == r


def test_cascade_snapshot_value_none_when_not_computed():
    assert analysis_metrics.cascade_snapshot_value(None) is None
