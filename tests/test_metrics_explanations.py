"""Live feedback #21 and #22 (2026-11-12), Network Metrics page.

#21: "terms would not be clear for a beginner ... Social-Ecological fit,
Governance gap [should] be explained under. And all the metrics like Degree,
Indegree, and others should be explained."
#22: "What is 'Show top N'? When the numeric value is changed, nothing
happens." The slider drives only the "Top-ranked elements" table, which sat
below six summary panels, so nothing visible changed near it.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from html import escape
from pathlib import Path

import pytest

pytest.importorskip("pyvis.shiny")

from shiny.testserver import test_server  # noqa: E402

from sespy import i18n  # noqa: E402
from sespy.data_structure import Project  # noqa: E402
from sespy.event_bus import create_event_bus  # noqa: E402
from sespy.i18n import Translator, load_translations  # noqa: E402
from sespy.modules.analysis_metrics import analysis_metrics_server, analysis_metrics_ui  # noqa: E402
from sespy.network import CENTRALITY_METRICS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
LANGS = ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el")
NEW_KEYS = [f"metrics.desc_{m}" for m in CENTRALITY_METRICS] + [
    "metrics.fit_explain", "metrics.gov_gap_explain", "metrics.show_top_n_help",
]


def _sample() -> Project:
    raw = json.loads((ROOT / "data" / "sample_ses.json").read_text(encoding="utf-8"))
    return Project.from_dict(raw)


@contextmanager
def _metrics(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)

    def server(input, output, session):
        from shiny import reactive
        analysis_metrics_server("metrics", project_data=reactive.value(_sample()),
                                event_bus=create_event_bus(), translator=TR)

    with test_server(server, timeout_secs=30) as ts:
        yield ts.make_scope("metrics")


def _html(scope, output: str) -> str:
    out = scope.get_output(output)
    assert out.status == "ok", (output, out.status, out.error)
    return out.value["html"]


@pytest.mark.parametrize("metric", CENTRALITY_METRICS)
def test_the_selected_metric_is_explained_beside_the_choice(monkeypatch, metric):
    with _metrics(monkeypatch) as m:
        m.set_inputs(metric=metric, top_n=10)
        assert escape(TR.t(f"metrics.desc_{metric}"), quote=False) in _html(m, "metric_help")


def test_fit_and_governance_gap_say_what_they_measure(monkeypatch):
    with _metrics(monkeypatch) as m:
        m.set_inputs(metric="degree", top_n=10)
        assert escape(TR.t("metrics.fit_explain"), quote=False) in _html(m, "fit_summary")
        assert escape(TR.t("metrics.gov_gap_explain"), quote=False) in _html(m, "governance_gap_summary")


def test_top_n_controls_sit_right_above_the_table_they_drive(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    html = str(analysis_metrics_ui("metrics"))
    table = html.index('id="metrics-metrics_table"')
    # the ranking table comes before the six summary panels ...
    for summary in ("fit_summary", "governance_gap_summary", "actor_influence_summary",
                    "cascade_summary", "paths_summary", "hypermodules_summary"):
        assert table < html.index(f'id="metrics-{summary}"'), summary
    # ... and the slider says what it changes
    assert TR.t("metrics.show_top_n") in html
    assert TR.t("metrics.show_top_n_help") in html
    assert 'id="metrics-metric_help"' in html


def test_the_table_follows_the_slider(monkeypatch):
    with _metrics(monkeypatch) as m:
        m.set_inputs(metric="degree", top_n=3)
        assert len(m.get_output("metrics_table").value["payload"]["data"]) == 3
        m.set_inputs(top_n=5)
        assert len(m.get_output("metrics_table").value["payload"]["data"]) == 5


@pytest.mark.parametrize("key", NEW_KEYS + ["metrics.show_top_n"])
def test_explanations_cover_all_languages(key):
    tr = load_translations(ROOT / "sespy" / "translations")
    assert key in tr
    for lang in LANGS:
        assert tr[key].get(lang, "").strip(), (key, lang)
    for lang in LANGS[1:]:
        assert tr[key][lang] != tr[key]["en"], f"{key} [{lang}] is untranslated English"


def test_the_slider_label_names_the_table():
    tr = load_translations(ROOT / "sespy" / "translations")
    assert "top n" not in tr["metrics.show_top_n"]["en"].lower()
