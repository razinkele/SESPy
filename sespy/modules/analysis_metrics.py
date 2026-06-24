"""Network Metrics Analysis module.

Mirrors the structure of `modules/analysis_metrics.R` (677 lines, 4 tabs in R).
This POC keeps the most useful slice — a metric-picker + top-N table + a
distribution histogram + a pyvis network sized by the chosen metric. The R
module's tabs ("Leverage", "Distribution", "Network View") collapse into
one panel here; per CLAUDE.md, the analysis-module signature contract is
preserved (event_bus, project_data_reactive, i18n).

Why this matters for the port: this is the third reactive consumer of
`event_bus.isa_change` after `cld_visualization` and `analysis_loops`. With
project_io now live, an upload or "New Project" click triggers
`emit_isa_change`, which means three modules invalidate their derived state
in the same tick. If the event-bus pattern can survive three-way coupling
without re-entrancy bugs, the architecture scales.
"""

from __future__ import annotations

from pyvis.network import Network
from pyvis.shiny import output_pyvis_network, render_pyvis_network
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from .. import network as net_analysis
from ..constants import (
    DEFAULT_GROUP_COLOR,
    DEFAULT_GROUP_SHAPE,
    EDGE_COLORS,
    ELEMENT_COLORS,
    ELEMENT_SHAPES,
)
from ..data_structure import IsaData, Project
from ..event_bus import EventBus
from ..i18n import Translator, t

METRIC_LABEL_KEYS: dict[str, str] = {
    "degree":      "metrics.degree",
    "indegree":    "metrics.indegree",
    "outdegree":   "metrics.outdegree",
    "betweenness": "metrics.betweenness",
    "closeness":   "metrics.closeness",
    "eigenvector": "metrics.eigenvector",
    "pagerank":    "metrics.pagerank",
}


def _scaled_size(value: float, lo: float, hi: float, *, smin: int = 18, smax: int = 60) -> int:
    """Linear-interpolate `value` from [lo, hi] to [smin, smax] for vis-network
    node sizing. Equal min and max yield the midpoint so isolated nodes don't
    collapse to a point on graphs where a metric is constant.
    """
    if hi <= lo:
        return (smin + smax) // 2
    frac = (value - lo) / (hi - lo)
    return int(smin + frac * (smax - smin))


def _build_metrics_network(
    isa: IsaData,
    metric: str,
    scores: dict[str, float],
) -> Network:
    """A pyvis Network with node sizes proportional to the chosen metric.
    Layout is force-directed (the metric tells you which nodes are central
    — hierarchical would defeat that)."""
    net = Network(
        height="500px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#2c3e50",
        cdn_resources="local",
    )
    net.set_options(
        '{"physics": {"enabled": true, "stabilization": {"iterations": 200}},'
        ' "interaction": {"hover": true, "tooltipDelay": 150}}'
    )

    if not isa.elements:
        return net

    values = [scores.get(el.id, 0.0) for el in isa.elements]
    lo, hi = min(values), max(values)

    for el in isa.elements:
        v = scores.get(el.id, 0.0)
        net.add_node(
            el.id,
            label=el.label,
            title=f"{el.type}: {el.label}\n{metric}: {v:.4f}",
            color=ELEMENT_COLORS.get(el.type, DEFAULT_GROUP_COLOR),
            shape=ELEMENT_SHAPES.get(el.type, DEFAULT_GROUP_SHAPE),
            size=_scaled_size(v, lo, hi),
            font={"size": 14, "multi": "html"},
            widthConstraint={"maximum": 160},
        )
    for c in isa.connections:
        net.add_edge(
            c.source, c.target,
            label=c.polarity,
            color=EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
            arrows="to",
            width=1.5,
            **net_analysis.delay_edge_kwargs(c),
        )
    return net


@module.ui
def analysis_metrics_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("card.metrics")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("metrics.metric")),
                ui.input_radio_buttons(
                    "metric",
                    None,
                    {k: k.title() for k in net_analysis.CENTRALITY_METRICS},
                    selected="degree",
                ),
                ui.tags.hr(),
                ui.input_slider(
                    "top_n", t("metrics.show_top_n"),
                    min=3, max=20, value=10, step=1,
                ),
                width=240,
            ),
            ui.div(
                ui.output_ui("fit_summary"),
                ui.tags.hr(),
                ui.h4(t("metrics.top_ranked")),
                ui.output_data_frame("metrics_table"),
                ui.tags.hr(),
                ui.h4(t("metrics.distribution")),
                ui.output_plot("metrics_hist", height="220px"),
                ui.tags.hr(),
                ui.h4(t("metrics.network_sized")),
                output_pyvis_network(
                    "metrics_network",
                    height="500px",
                    show_toolbar=False, show_search=False,
                    show_layout_switcher=False, show_export=False,
                    show_status=False,
                ),
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_metrics_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @reactive.calc
    def metrics() -> dict[str, dict[str, float]]:
        # Subscribe to isa_change so a project load/new resets memoization
        # via the reactive graph re-running this calc.
        event_bus.isa_change.get()
        return net_analysis.centrality_metrics(project_data.get().isa_data)

    @reactive.calc
    def chosen_metric() -> str:
        return input.metric() or "degree"

    @reactive.calc
    def top_rows() -> list[dict]:
        return net_analysis.top_n_by_metric(
            project_data.get().isa_data,
            chosen_metric(),
            n=int(input.top_n() or 10),
        )

    @output
    @render.data_frame
    def metrics_table():
        import pandas as pd

        rows = top_rows()
        if not rows:
            return pd.DataFrame(columns=["rank", "id", "label", "type", "value"])
        return pd.DataFrame(rows)

    @output
    @render.plot
    def metrics_hist():
        import matplotlib.pyplot as plt

        scores = list(metrics()[chosen_metric()].values())
        fig, ax = plt.subplots(figsize=(8, 2.4))
        if scores:
            ax.hist(scores, bins=12, color="#4a90b8", edgecolor="#2d5a7b", alpha=0.85)
        ax.set_xlabel(chosen_metric())
        ax.set_ylabel("count")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    @output
    @render.ui
    def fit_summary():
        event_bus.isa_change.get()
        r = net_analysis.social_ecological_fit(project_data.get().isa_data)
        if r["total_edges"] == 0:
            return ui.p(t("metrics.fit_none"), class_="text-muted")
        return ui.div(
            ui.h5(t("metrics.fit")),
            ui.tags.strong(f"{r['fit']:.2f}"),
            ui.p(t("metrics.fit_caption", cross=r["cross_edges"], total=r["total_edges"]),
                 class_="text-muted", style="font-size: 0.85rem;"),
        )

    @output(id="metrics_network")
    @render_pyvis_network(
        height="500px",
        show_toolbar=False, show_search=False,
        show_layout_switcher=False, show_export=False, show_status=False,
    )
    def _network():
        return _build_metrics_network(
            project_data.get().isa_data,
            chosen_metric(),
            metrics()[chosen_metric()],
        )
