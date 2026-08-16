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

from .. import dynamics as dyn
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
                ui.tags.hr(),
                ui.h5(t("diffusion.title")),
                ui.output_ui("diffusion_controls"),
                ui.input_slider("n_steps", t("diffusion.steps"),
                                min=3, max=30, value=10, step=1),
                ui.input_slider("n_tokens", t("diffusion.tokens"),
                                min=100, max=5000, value=1000, step=100),
                ui.input_action_button(
                    "run_diffusion", t("diffusion.run"),
                    class_="btn btn-sm btn-outline-primary",
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
                ui.tags.hr(),
                ui.h4(t("diffusion.title")),
                ui.output_ui("diffusion_summary"),
                ui.output_plot("diffusion_chart", height="260px"),
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

    _diffusion_result = reactive.value(None)

    @output
    @render.ui
    def diffusion_controls():
        event_bus.isa_change.get()
        els = project_data.get().isa_data.elements
        if not els:
            return ui.div()
        choices = {el.id: f"{el.id} · {el.label}" for el in els}
        # Keep the user's pick across re-renders (isolate so choosing a
        # source doesn't itself re-render this block), falling back when
        # the model no longer has that element.
        with reactive.isolate():
            try:
                current = input.diffusion_source()
            except Exception:
                current = None
        return ui.input_select(
            "diffusion_source", t("diffusion.source"), choices,
            selected=current if current in choices else els[0].id,
        )

    @reactive.effect
    def _reset_diffusion():
        event_bus.isa_change.get()
        _diffusion_result.set(None)

    @reactive.effect
    @reactive.event(input.run_diffusion, ignore_init=True)
    def _run_diffusion():
        try:
            src = input.diffusion_source()
        except Exception:
            src = None
        if not src:
            return
        # Fixed seed: two intervention points then differ by structure
        # rather than by chance, which is the point of comparing them.
        _diffusion_result.set(dyn.token_diffusion(
            project_data.get().isa_data, src,
            n_steps=int(input.n_steps() or 10),
            n_tokens=int(input.n_tokens() or 1000),
            seed=0,
        ))

    @output
    @render.ui
    def diffusion_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if len(isa.elements) < 2:
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        r = _diffusion_result.get()
        if r is None:
            return ui.p(t("diffusion.hint"), class_="text-muted",
                        style="font-size: 0.85rem;")
        if not r["rows"]:
            return ui.p(t("diffusion.none"), class_="text-muted")
        header = ui.tags.tr(
            ui.tags.th(""), ui.tags.th("tokens"),
            ui.tags.th("net sign"), ui.tags.th("first step"),
        )
        body = [
            ui.tags.tr(
                ui.tags.td(f"{row['id']} · {row['label']}"),
                ui.tags.td(str(row["tokens_received"])),
                ui.tags.td(ui.tags.strong(row["net_sign"])),
                ui.tags.td(str(row["first_arrival_step"])),
            )
            for row in r["rows"]
        ]
        return ui.div(
            ui.p(ui.tags.strong(t(
                "diffusion.summary", reached=r["n_reached"],
                total=len(isa.elements), tokens=r["n_tokens"],
                steps=r["n_steps"]))),
            ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body),
                          class_="table table-sm"),
            ui.p(t("diffusion.caption"), class_="text-muted",
                 style="font-size: 0.85rem;"),
        )

    @output
    @render.plot
    def diffusion_chart():
        import matplotlib.pyplot as plt

        r = _diffusion_result.get()
        rows = (r or {}).get("rows", [])[:12]
        fig, ax = plt.subplots(figsize=(8, 2.6))
        if rows:
            colours = {"+": "#2e7d32", "-": "#c62828", "~": "#757575"}
            ax.bar(
                range(len(rows)),
                [row["tokens_received"] for row in rows],
                color=[colours[row["net_sign"]] for row in rows],
            )
            ax.set_xticks(range(len(rows)))
            ax.set_xticklabels([row["label"] for row in rows],
                               rotation=30, ha="right", fontsize=8)
            ax.set_ylabel("tokens")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig
