"""Intervention Analysis — "what if we ablate node(s) X?" scenarios.

Mirrors `modules/analysis_intervention.R`. The user picks one or more
nodes to remove; the module shows the change in centrality (selected
metric) for every remaining node, sorted by delta. Nodes most affected
by the ablation are the ones structurally dependent on the removed
node(s) — useful counterpart to leverage analysis ("removing this
high-leverage node ripples through these other nodes").
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


def _build_intervention_network(
    isa: IsaData,
    impact: dict[str, dict[str, float]],
    removed_ids: list[str],
) -> Network:
    """Pyvis network: removed nodes greyed out + dashed border;
    surviving nodes coloured by abs(delta) heatmap-style."""
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

    # Heatmap range from max abs delta on surviving nodes
    deltas = [abs(d["delta"]) for d in impact.values()]
    max_delta = max(deltas) if deltas else 0.0

    for el in isa.elements:
        if el.id in removed_ids:
            net.add_node(
                el.id,
                label=el.label + " (ablated)",
                title=f"{el.type}: {el.label}\nRemoved in this scenario",
                color={"background": "#cccccc", "border": "#666",
                       "highlight": {"background": "#cccccc", "border": "#666"}},
                shape="dot",
                size=20,
                opacity=0.4,
                borderDashes=[6, 4],
                font={"size": 12, "color": "#666"},
            )
            continue
        info = impact.get(el.id, {"delta": 0.0})
        delta = info["delta"]
        # Surviving-node colouring: pull toward bio-cyan if positive delta
        # (gained influence), toward coral if negative.
        if max_delta > 0:
            ratio = abs(delta) / max_delta
        else:
            ratio = 0.0
        if delta > 0:
            tint = f"rgba(0, 212, 170, {0.15 + 0.6 * ratio:.2f})"
        elif delta < 0:
            tint = f"rgba(255, 107, 107, {0.15 + 0.6 * ratio:.2f})"
        else:
            tint = ELEMENT_COLORS.get(el.type, DEFAULT_GROUP_COLOR)
        net.add_node(
            el.id,
            label=el.label,
            title=(f"{el.type}: {el.label}\n"
                   f"before: {info['before']:.4f}\n"
                   f"after:  {info['after']:.4f}\n"
                   f"Δ:      {delta:+.4f}"),
            color=tint,
            shape=ELEMENT_SHAPES.get(el.type, DEFAULT_GROUP_SHAPE),
            size=int(22 + ratio * 28),
            font={"size": 14, "multi": "html"},
            widthConstraint={"maximum": 160},
        )

    for c in isa.connections:
        edge_opacity = (
            0.25 if c.source in removed_ids or c.target in removed_ids else 1.0
        )
        net.add_edge(
            c.source, c.target,
            label=c.polarity,
            color={
                "color": EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
                "opacity": edge_opacity,
            },
            arrows="to",
            width=1.5,
            **net_analysis.delay_edge_kwargs(c),
        )
    return net


@module.ui
def analysis_intervention_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.intervention")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("intervention.scenario")),
                ui.p(
                    t("intervention.about_text"),
                    class_="text-muted",
                    style="font-size: 0.85rem;",
                ),
                ui.tags.hr(),
                ui.output_ui("ablate_picker"),
                ui.input_radio_buttons(
                    "metric",
                    t("metrics.metric"),
                    {k: k.title() for k in net_analysis.CENTRALITY_METRICS},
                    selected="pagerank",
                ),
                ui.tags.hr(),
                ui.input_action_button(
                    "reset", t("intervention.reset"),
                    class_="btn btn-sm btn-outline-secondary",
                ),
                width=280,
            ),
            ui.div(
                ui.h4(t("intervention.most_affected")),
                ui.output_data_frame("impact_table"),
                ui.tags.hr(),
                ui.h4(t("intervention.network_with")),
                output_pyvis_network(
                    "intervention_network",
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
def analysis_intervention_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @output
    @render.ui
    def ablate_picker():
        event_bus.isa_change.get()
        choices = {el.id: f"{el.id} · {el.label}"
                   for el in project_data.get().isa_data.elements}
        return ui.input_selectize(
            "ablate", t("intervention.remove_nodes"),
            choices=choices,
            multiple=True,
            options={"plugins": ["remove_button"]},
        )

    @reactive.effect
    @reactive.event(input.reset, ignore_init=True)
    def _reset():
        ui.update_selectize("ablate", selected=[])

    @reactive.calc
    def chosen_ids() -> list[str]:
        try:
            sel = input.ablate()
        except Exception:
            sel = None
        return list(sel) if sel else []

    @reactive.calc
    def impact() -> dict[str, dict[str, float]]:
        event_bus.isa_change.get()
        ids = chosen_ids()
        if not ids:
            # Empty ablation: every node has zero delta — useful baseline.
            isa = project_data.get().isa_data
            scores = net_analysis.centrality_metrics(isa)[input.metric() or "pagerank"]
            return {nid: {"before": v, "after": v, "delta": 0.0}
                    for nid, v in scores.items()}
        return net_analysis.intervention_impact(
            project_data.get().isa_data,
            ids,
            metric=input.metric() or "pagerank",
        )

    @output
    @render.data_frame
    def impact_table():
        import pandas as pd

        rows = impact()
        if not rows:
            return pd.DataFrame(columns=["id", "label", "before", "after", "delta"])
        by_id = {el.id: el for el in project_data.get().isa_data.elements}
        data = sorted(
            rows.items(),
            key=lambda kv: abs(kv[1]["delta"]),
            reverse=True,
        )
        return pd.DataFrame([
            {
                "id": nid,
                "label": (by_id[nid].label if nid in by_id else nid),
                "type":  (by_id[nid].type  if nid in by_id else ""),
                "before": round(info["before"], 4),
                "after":  round(info["after"], 4),
                "delta":  round(info["delta"], 4),
            }
            for nid, info in data[:15]
        ])

    @output(id="intervention_network")
    @render_pyvis_network(
        height="500px",
        show_toolbar=False, show_search=False,
        show_layout_switcher=False, show_export=False, show_status=False,
    )
    def _network():
        return _build_intervention_network(
            project_data.get().isa_data, impact(), chosen_ids(),
        )
