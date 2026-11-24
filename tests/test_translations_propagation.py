"""Translation keys for weighted signed propagation (development note, Nov 2026)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import sespy

CORE = Path(sespy.__file__).parent / "translations" / "core.json"
LANGS = ["en", "es", "fr", "de", "lt", "pt", "it", "no", "el"]
EN = {
    "propagation.title": "Signed propagation",
    "propagation.source": "Intervention (source)",
    "propagation.preset": "Settings",
    "propagation.preset_interactive": "Interactive (1,000 tokens)",
    "propagation.preset_report": "Report (10,000 tokens)",
    "propagation.preset_equal": "Equal links, no decay (Donlan et al. 2026)",
    "propagation.preset_custom": "Custom",
    "propagation.advanced": "Advanced settings",
    "propagation.steps": "Steps",
    "propagation.decay": "Decay per step",
    "propagation.stop": "Stop chance per step",
    "propagation.transition": "Link choice",
    "propagation.transition_weighted": "By link strength",
    "propagation.transition_equal": "Equal",
    "propagation.run": "Run propagation",
    "propagation.hint": "Not simulated yet: choose an intervention and press Run propagation.",
    "propagation.computing": "Simulating {n} tokens…",
    "propagation.none": "Nothing is reached from this element: it has no outgoing links in the current model.",
    "propagation.col_element": "Element",
    "propagation.col_reach": "Reach",
    "propagation.col_first": "Median first step",
    "propagation.col_pos": "+ share",
    "propagation.col_neg": "− share",
    "propagation.col_net": "Net mass",
    "propagation.col_sign": "Sign",
    "propagation.mass_line": "Of the injected influence: {decayed}% decayed, {stopped}% stopped, {absorbed}% absorbed at dead ends, {moving}% still moving after step {n}.",
    "propagation.default_strength": "{k} links have no strength rating; counted as medium.",
    "propagation.caption": "Structural simulation under stated assumptions; not a forecast or effect size.",
    "propagation.unc_run": "Estimate uncertainty",
    "propagation.unc_computing": "Running {n} perturbed versions of the network…",
    "propagation.unc_caption": "{n} perturbed versions (seed {seed}): each link may drop out or flip sign, more often the lower its confidence.",
    "propagation.unc_default_conf": "{k} links have no confidence; counted as 3.",
    "propagation.unc_tokens": "Uncertainty used {n} tokens per version.",
    "propagation.col_reached": "Reached in % of variants",
    "propagation.col_holds": "Sign holds in %",
    "propagation.balanced": "—, balanced",
    "propagation.rarely": "—, rarely reached",
    "propagation.download": "Download propagation (CSV)",
    "propagation.error": "The propagation run failed: {error}",
}
KEYS = {k: set(re.findall(r"\{(\w+)\}", v)) for k, v in EN.items()}


@pytest.fixture(scope="module")
def tr():
    return json.loads(CORE.read_text(encoding="utf-8"))["translation"]


def test_key_count():
    assert len(EN) == 39


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


def test_existing_diffusion_key_kept(tr):
    assert "diffusion.title" in tr
