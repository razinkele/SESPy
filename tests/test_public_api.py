"""Pin the library names that downstream consumers import.

MosaicSES and Nid4Ocean import these from ``sespy``; a refactor must not
silently remove or rename any of them.
"""

import importlib
from pathlib import Path

import pytest

import sespy

CONSUMER_API = {
    "constants": [
        "ELEMENT_ID_PREFIX", "DA_SITES", "SPATIAL_SCALES", "TEMPORAL_SCALES",
        "DAPSIWRM_ADJACENCY_RULES", "normalize_delay", "CONFIDENCE_OPACITY",
        "EDGE_COLORS", "ELEMENT_COLORS", "ELEMENT_SHAPES",
    ],
    "data_structure": [
        "Connection", "Element", "IsaData", "Project", "ProjectMetadata",
        "PROJECT_SCHEMA_VERSION", "SCHEMA_MIN_READER", "to_visnetwork",
    ],
    "utils": ["next_id"],
    "network": [
        "CENTRALITY_METRICS", "centrality_metrics", "leverage_scores",
        "to_digraph", "remove_nodes", "feedback_loops", "classify_loops",
        "intervention_impact", "causal_paths", "delay_edge_kwargs",
        "path_sensitivity", "PATH_SCORE_LAMBDA",
    ],
    "dynamics": [
        "token_diffusion", "isa_to_dynamics_matrix", "isa_to_numeric_matrix",
        "randomize_matrix", "create_boolean_rules", "boolean_attractors",
        "boolean_attractors_core", "boolean_attractors_sampled", "BOOLEAN_MAX_CORE",
        "BOOLEAN_BASIN_BUDGET", "BOOLEAN_MAX_NODES_TOTAL", "BOOLEAN_MAX_ATTRACTORS",
    ],
    "regional_seas": ["get_regional_seas"],
    "autosave": ["token_key", "valid_token"],
    # _default_translator is private but written by MosaicSES tests.
    "i18n": [
        "set_default", "get_default", "load_translations", "Translator",
        "_default_translator",
    ],
}

CASES = [(m, n) for m, names in CONSUMER_API.items() for n in names]


@pytest.mark.parametrize("module,name", CASES)
def test_consumer_name_exists(module, name):
    mod = importlib.import_module(f"sespy.{module}")
    assert hasattr(mod, name), f"sespy.{module}.{name} is missing"


def test_project_from_dict_exists():
    from sespy.data_structure import Project

    assert callable(Project.from_dict)


def test_translations_dir_is_package_data():
    core = Path(sespy.__file__).parent / "translations" / "core.json"
    assert core.is_file()
