"""Translation keys for the scaled Boolean panel (spec 2026-11-21 §3.5)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import sespy

CORE = Path(sespy.__file__).parent / "translations" / "core.json"
LANGS = ["en", "es", "fr", "de", "lt", "pt", "it", "no", "el"]
KEYS = {
    "boolean.core_info": {"n", "core"},
    "boolean.basins_exact": set(),
    "boolean.basins_sampled": {"samples"},
    "boolean.all_off": set(),
    "boolean.core_too_large": {"core", "max"},
    "boolean.sampled_note": {"n", "seed", "unconverged", "max_steps"},
    "boolean.computing": set(),
    "boolean.col_hits": set(),
    "boolean.col_basin_fraction": set(),
    "boolean.truncated": {"shown", "total"},
}
EN = {
    "boolean.core_info": "{n} nodes · {core} in the feedback core",
    "boolean.basins_exact": "basin sizes exact",
    "boolean.basins_sampled": "basin fractions estimated from {samples} random starts",
    "boolean.all_off": "Without external drivers, no feedback loop keeps any element active: every state settles to all elements off.",
    "boolean.core_too_large": "The feedback core has {core} nodes, above the exact limit of {max}. Showing a sampled search instead.",
    "boolean.sampled_note": "Sampled search: {n} random start states (seed {seed}). Rare attractors may be missed; basin fractions are estimates. {unconverged} trajectories did not settle within {max_steps} steps.",
    "boolean.computing": "Computing attractors…",
    "boolean.col_hits": "Hits",
    "boolean.col_basin_fraction": "Basin fraction (%)",
    "boolean.truncated": "Showing the {shown} attractors with the largest basins, of {total} found.",
}


@pytest.fixture(scope="module")
def tr():
    return json.loads(CORE.read_text(encoding="utf-8"))["translation"]


@pytest.mark.parametrize("key", sorted(KEYS))
def test_key_has_all_languages_and_placeholders(tr, key):
    assert key in tr, key
    entry = tr[key]
    for lang in LANGS:
        text = entry.get(lang)
        assert isinstance(text, str) and text.strip(), (key, lang)
        assert set(re.findall(r"\{(\w+)\}", text)) == KEYS[key], (key, lang)


@pytest.mark.parametrize("key", sorted(KEYS))
def test_english_text_matches_spec(tr, key):
    assert tr[key]["en"] == EN[key]


def test_existing_boolean_keys_kept(tr):
    for key in ("boolean.no_attractors", "boolean.cap_below_12", "boolean.cap_above_12",
                "boolean.max_nodes", "boolean.run"):
        assert key in tr
