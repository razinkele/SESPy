"""Translation keys for the causal path diagnostics (spec 2026-11-22)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import sespy

CORE = Path(sespy.__file__).parent / "translations" / "core.json"
LANGS = ["en", "es", "fr", "de", "lt", "pt", "it", "no", "el"]
EN = {
    "metrics.paths_col_route": "Route",
    "metrics.paths_col_score": "Score",
    "metrics.paths_col_length": "Links",
    "metrics.paths_col_polarity": "Sign",
    "metrics.paths_col_bottleneck": "Weakest link",
    "metrics.paths_col_delay": "Delays",
    "metrics.paths_col_confidence": "Min. confidence",
    "metrics.paths_delay_fmt": "{immediate} immediate, {short} short, {long} long",
    "metrics.paths_score_note": "Score = product of link weights (weak 0.30, medium 0.55, strong 0.80) × e^(−0.2 × (links − 1)). It ranks structural routes; it is not an effect size.",
    "metrics.paths_strongest": "Strongest positive route: {pos}. Strongest negative route: {neg}.",
    "metrics.paths_none_sign": "none",
    "metrics.paths_contradictory": "Positive and negative routes both connect these elements; the net effect depends on which dominates.",
    "metrics.paths_redundancy": "Disjoint routes among the paths listed: {edge} sharing no link, {node} sharing no intermediate element.",
    "metrics.paths_ranked_partial": "Ranked among the first {n} paths found; a stronger path may exist beyond them.",
    "metrics.paths_download": "Download paths (CSV)",
    "metrics.paths_sens_run": "Test robustness",
    "metrics.paths_sens_computing": "Running {n} perturbed versions of the network…",
    "metrics.paths_sens_caption": "{n} perturbed versions (seed {seed}): each link may drop out or flip sign, more often the lower its confidence.",
    "metrics.paths_sens_col_rank": "Top route of its sign (%)",
    "metrics.paths_sens_col_polarity": "Keeps its sign (%)",
    "metrics.paths_sens_col_survival": "Survives (%)",
    "metrics.paths_sens_fragile": "Links whose uncertainty most often changes the top route: {edges}",
    "metrics.paths_sens_error": "The robustness check failed: {error}",
}
KEYS = {k: set(re.findall(r"\{(\w+)\}", v)) for k, v in EN.items()}


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


def test_existing_truncated_key_kept(tr):
    assert "metrics.paths_truncated" in tr
