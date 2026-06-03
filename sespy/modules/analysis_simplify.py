"""Network Simplification — reduce the SES to its strongest connections.

Two modes:
  - "By strength" — drop edges below a strength category (weak / medium / strong)
  - "Top N edges" — keep the N strongest edges by `strength × confidence`

Both render side-by-side stats (before / after) and a pyvis network of the
simplified result. Builds on existing helpers in `sespy.network`.

R counterpart: `modules/analysis_simplify.R` (~1100 LOC). Slimmed to the
two most useful reductions.
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


def _build_simplified_network(isa: IsaData) -> Network:
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
    for el in isa.elements:
        net.add_node(
            el.id,
            label=el.label,
            title=f"{el.type}: {el.label}",
            color=ELEMENT_COLORS.get(el.type, DEFAULT_GROUP_COLOR),
            shape=ELEMENT_SHAPES.get(el.type, DEFAULT_GROUP_SHAPE),
            size=30,
            font={"size": 14, "multi": "html"},
            widthConstraint={"maximum": 160},
        )
    for c in isa.connections:
        net.add_edge(
            c.source, c.target,
            label=c.polarity,
            color=EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
            arrows="to",
            width=1.5 + 0.5 * net_analysis._STRENGTH_RANK.get(c.strength, 2),
        )
    return net


@module.ui
def analysis_simplify_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.simplify")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("simplify.mode")),
                ui.input_radio_buttons(
                    "mode",
                    None,
                    {
                        "strength": t("simplify.mode.strength"),
                        "top_n":    t("simplify.mode.top_n"),
                    },
                    selected="strength",
                ),
                ui.tags.hr(),
                ui.panel_conditional(
                    "input.mode == 'strength'",
                    ui.input_radio_buttons(
                        "min_strength",
                        t("simplify.min_strength"),
                        {
                            "weak":   t("simplify.strength.weak"),
                            "medium": t("simplify.strength.medium"),
                            "strong": t("simplify.strength.strong"),
                        },
                        selected="medium",
                    ),
                ),
                ui.panel_conditional(
                    "input.mode == 'top_n'",
                    ui.input_slider(
                        "keep_n",
                        t("simplify.keep_top_n"),
                        min=3, max=40, value=10, step=1,
                    ),
                ),
                ui.input_checkbox(
                    "drop_isolated",
                    t("simplify.drop_isolated"),
                    value=True,
                ),
                width=260,
            ),
            ui.div(
                ui.h4(t("simplify.summary")),
                ui.output_ui("simplify_summary"),
                ui.tags.hr(),
                ui.h4(t("simplify.preview")),
                output_pyvis_network(
                    "simplified_network",
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
def analysis_simplify_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @reactive.calc
    def reduced() -> IsaData:
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        drop = bool(input.drop_isolated())
        if (input.mode() or "strength") == "top_n":
            return net_analysis.simplify_top_n_edges(
                isa,
                keep_top_n=int(input.keep_n() or 10),
                drop_isolated=drop,
            )
        return net_analysis.simplify_by_strength(
            isa,
            min_strength=input.min_strength() or "medium",
            drop_isolated=drop,
        )

    @output
    @render.ui
    def simplify_summary():
        before = project_data.get().isa_data
        after = reduced()
        return ui.tags.div(
            ui.tags.div(
                ui.tags.span(
                    f"{before.element_count()} → {after.element_count()}",
                    style="font-family: var(--font-mono); font-weight: 600;",
                ),
                ui.tags.span(" elements", class_="text-muted"),
                style="margin-bottom: 4px;",
            ),
            ui.tags.div(
                ui.tags.span(
                    f"{before.connection_count()} → {after.connection_count()}",
                    style="font-family: var(--font-mono); font-weight: 600;",
                ),
                ui.tags.span(" connections", class_="text-muted"),
            ),
            style="font-size: 1.05rem;",
        )

    @output(id="simplified_network")
    @render_pyvis_network(
        height="500px",
        show_toolbar=False, show_search=False,
        show_layout_switcher=False, show_export=False, show_status=False,
    )
    def _network():
        return _build_simplified_network(reduced())
