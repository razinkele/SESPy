"""Live feedback #19 and #20 (2026-11-12), CLD Visualization.

#19: "There should be a legend for the network, showing what each of the
elements mean." Element types are drawn with Kumu colours and shapes, but the
page never said which is which; edge colours (polarity) were unexplained too.
#20: "In CLD visualisation, what is density, maybe there could be an
explanation, or information dot, on which if mouse was put, the explanation
would be shown." The Nodes/Edges/Density labels were also hardcoded English.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from html import escape
from pathlib import Path

import pytest

pytest.importorskip("pyvis.shiny")

from shiny import reactive  # noqa: E402
from shiny.testserver import test_server  # noqa: E402

from sespy import i18n  # noqa: E402
from sespy.constants import DAPSIWRM_ELEMENTS, EDGE_COLORS, ELEMENT_COLORS  # noqa: E402
from sespy.data_structure import Project  # noqa: E402
from sespy.event_bus import create_event_bus  # noqa: E402
from sespy.i18n import Translator, load_translations  # noqa: E402
from sespy.modules.cld_visualization import cld_viz_server, cld_viz_ui  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
LANGS = ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el")
KEYS = ["cld.legend", "cld.legend_reinforcing", "cld.legend_opposing",
        "cld.stat_nodes", "cld.stat_edges", "cld.stat_density", "cld.density_help"]


def _sample() -> Project:
    raw = json.loads((ROOT / "data" / "sample_ses.json").read_text(encoding="utf-8"))
    return Project.from_dict(raw)


@contextmanager
def _cld(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)

    def server(input, output, session):
        cld_viz_server("cld", project_data=reactive.value(_sample()),
                       event_bus=create_event_bus())

    with test_server(server, timeout_secs=30) as ts:
        scope = ts.make_scope("cld")
        scope.set_inputs(element_types=list(DAPSIWRM_ELEMENTS))
        yield scope


def _value(scope, output):
    out = scope.get_output(output)
    assert out.status == "ok", (output, out.status, out.error)
    return out.value


def test_legend_shows_each_drawn_type_with_its_colour(monkeypatch):
    sample_types = {el.type for el in _sample().isa_data.elements}
    with _cld(monkeypatch) as cld:
        html = _value(cld, "legend")["html"]
        for typ in sample_types:
            assert escape(typ, quote=False) in html, typ
            assert ELEMENT_COLORS[typ].lower() in html.lower(), typ
        assert TR.t("cld.legend") in html


def test_legend_explains_link_colours(monkeypatch):
    with _cld(monkeypatch) as cld:
        html = _value(cld, "legend")["html"]
        assert escape(TR.t("cld.legend_reinforcing"), quote=False) in html
        assert escape(TR.t("cld.legend_opposing"), quote=False) in html
        assert EDGE_COLORS["reinforcing"] in html and EDGE_COLORS["opposing"] in html


def test_canvas_nodes_carry_the_colours_the_legend_shows():
    """Found while building the legend: the pyvis fork drops `color` when a
    node also has `group`, so vis.js painted each type from its default group
    palette (pink Ecosystem Services, purple Goods & Benefits ...) and the
    canvas never matched the R app's Kumu colours."""
    from sespy.modules.cld_visualization import _build_pyvis_network
    net = _build_pyvis_network(_sample().isa_data, layout_kind="hierarchical",
                               direction="DU", level_sep=90, node_sp=200,
                               size_scale=1.0, font_scale=1.0)
    types = {el.id: el.type for el in _sample().isa_data.elements}
    for node in net.nodes:
        assert node.get("color") == ELEMENT_COLORS[types[node["id"]]], node["id"]
        assert node.get("group") == types[node["id"]]   # e2e checks read types from it


def test_legend_follows_the_type_filter(monkeypatch):
    with _cld(monkeypatch) as cld:
        cld.set_inputs(element_types=["Drivers"])
        html = _value(cld, "legend")["html"]
        assert "Drivers" in html
        assert ELEMENT_COLORS["Pressures"].lower() not in html.lower()


def test_stats_are_translated(monkeypatch):
    with _cld(monkeypatch) as cld:
        assert _value(cld, "stat_nodes").startswith(TR.t("cld.stat_nodes"))
        assert _value(cld, "stat_edges").startswith(TR.t("cld.stat_edges"))
        assert _value(cld, "stat_density").startswith(TR.t("cld.stat_density"))


def test_density_has_an_info_dot_with_the_explanation(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    html = str(cld_viz_ui("cld"))
    assert "bslib-tooltip" in html
    assert escape(TR.t("cld.density_help"), quote=False) in html
    assert 'id="cld-legend"' in html


@pytest.mark.parametrize("key", KEYS)
def test_keys_cover_all_languages(key):
    tr = load_translations(ROOT / "sespy" / "translations")
    assert key in tr
    for lang in LANGS:
        assert tr[key].get(lang, "").strip(), (key, lang)
    if key not in ("cld.stat_density",):        # "Density" is the same word in some languages
        assert sum(tr[key][lang] != tr[key]["en"] for lang in LANGS[1:]) >= 6, key
